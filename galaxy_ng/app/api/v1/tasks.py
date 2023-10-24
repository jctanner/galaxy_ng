import copy
import datetime
import logging
import os
import subprocess
import tempfile
import uuid

import semantic_version

from django.db import transaction

from galaxy_importer.config import Config
from galaxy_importer.legacy_role import import_legacy_role

from galaxy_ng.app.models.auth import User
from galaxy_ng.app.models import Namespace
from galaxy_ng.app.utils.galaxy import upstream_role_iterator
from galaxy_ng.app.utils.legacy import process_namespace
from galaxy_ng.app.utils.namespaces import generate_v3_namespace_from_attributes

from galaxy_ng.app.api.v1.models import LegacyNamespace
from galaxy_ng.app.api.v1.models import LegacyRole
from galaxy_ng.app.api.v1.models import LegacyRoleDownloadCount

from git import Repo


logger = logging.getLogger(__name__)


def parse_version_tag(value):
    value = str(value)
    if not value:
        raise ValueError('Empty version value')
    if value[0].lower() == 'v':
        value = value[1:]
    return semantic_version.Version(value)


def find_real_role(github_user, github_repo):
    """
    Given the github_user and github_repo attributes, find a matching
    role with those matching values and then return the necessary
    properties from the role needed to to do an import.

    :param github_user:
        The github_user as passed in to the CLI for imports.
    :param github_repo:
        The github_repo as passed in to the CLI for imports.
    """

    # if we find a role, this will point at it
    real_role = None

    # figure out the actual namespace name
    real_namespace_name = github_user

    # figure out the actual github user
    real_github_user = github_user

    # figure out the actual github repo
    real_github_repo = github_repo

    # the role role can influence the clone url
    clone_url = None

    # some roles have their github_user set differently from their namespace name ...
    candidates = LegacyRole.objects.filter(
        full_metadata__github_user=github_user,
        full_metadata__github_repo=github_repo
    )
    if candidates.count() > 0:
        real_role = candidates.first()
        logger.info(f'Using {real_role} as basis for import task')
        rr_github_user = real_role.full_metadata.get('github_user')
        rr_github_repo = real_role.full_metadata.get('github_repo')
        real_namespace_name = real_role.namespace.name
        if rr_github_user and rr_github_repo:
            real_github_user = rr_github_user
            real_github_repo = rr_github_repo
            clone_url = f'https://github.com/{rr_github_user}/{rr_github_repo}'
        elif rr_github_user:
            real_github_user = rr_github_user
            clone_url = f'https://github.com/{rr_github_user}/{github_repo}'
        elif rr_github_repo:
            real_github_repo = rr_github_repo
            clone_url = f'https://github.com/{github_user}/{github_repo}'

    return real_role, real_namespace_name, real_github_user, real_github_repo, clone_url


def do_git_checkout(clone_url, checkout_path, github_reference):
    """
    Handle making a clone, setting a branch/tag and
    enumerating the last commit for a role.

    :param clone_url:
        A valid anonymous/public github clone url.
    :param checkout_path:
        Where to make the clone.
    :param github_reference:
        A valid branch or a tag name.

    :return: A tuple with the following members:
        - the git.Repo object
        - the enumerated github_reference (aka branch or tag)
        - the last commit object from the github_reference or $HEAD
    :rtype: tuple(git.Repo, string, git.Commit)
    """
    logger.info(f'CLONING {clone_url}')

    # pygit didn't have an obvious way to prevent interactive clones ...
    pid = subprocess.run(
        f'GIT_TERMINAL_PROMPT=0 git clone --recurse-submodules {clone_url} {checkout_path}',
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if pid.returncode != 0:
        error = pid.stdout.decode('utf-8')
        logger.error(f'cloning failed: {error}')
        raise Exception(f'git clone for {clone_url} failed')

    # bind the checkout to a pygit object
    gitrepo = Repo(checkout_path)

    # the github_reference could be a branch OR a tag name ...
    if github_reference is not None:

        branch_names = [x.name for x in gitrepo.branches]
        tag_names = [x.name for x in gitrepo.tags]

        cmd = None
        if github_reference in branch_names:
            current_branch = gitrepo.active_branch.name
            if github_reference != current_branch:
                cmd = f'git checkout origin/{github_reference}'

        elif github_reference in tag_names:
            cmd = f'git checkout tags/{github_reference} -b local_${github_reference}'

        else:
            raise Exception(f'{github_reference} is not a valid branch or tag name')

        if cmd:
            logger.info(f'switching to {github_reference} in checkout via {cmd}')
            pid = subprocess.run(
                cmd,
                cwd=checkout_path,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if pid.returncode != 0:
                error = pid.stdout.decode('utf-8')
                logger.error('{cmd} failed: {error}')
                raise Exception(f'{cmd} failed')

        last_commit = [x for x in gitrepo.iter_commits()][0]

    else:
        # use the default branch ...
        github_reference = gitrepo.active_branch.name

        # use latest commit on HEAD
        last_commit = gitrepo.head.commit

    return gitrepo, github_reference, last_commit


def compute_all_versions(this_role, gitrepo):
    """
    Build a reconciled list of old versions and new versions.
    """

    # Combine old versions with new ...
    old_metadata = copy.deepcopy(this_role.full_metadata)
    versions = old_metadata.get('versions', [])

    # Clean out non-semver versions due to bad import code
    for version in versions:
        try:
            parse_version_tag(version['version'])
        except ValueError:
            versions.remove(version)

    # ALL semver tags should become versions
    current_tags = []
    for cversion in versions:
        # we want tag but the sync'ed roles don't have it
        # because the serializer returns "name" instead.
        tag = cversion.get('tag')
        if not tag:
            tag = cversion.get('name')
        current_tags.append(tag)
    for tag in gitrepo.tags:

        # must be a semver compliant value ...
        try:
            version = parse_version_tag(tag.name)
        except ValueError:
            continue

        if str(version) in current_tags:
            continue

        ts = datetime.datetime.now().isoformat()
        vdata = {
            'id': str(uuid.uuid4()),
            'tag': tag.name,
            'version': str(version),
            'commit_date': tag.commit.committed_datetime.isoformat(),
            'commit_sha': tag.commit.hexsha,
            'created': ts,
            'modified': ts,
        }
        logger.info(f'adding new version from tag: {vdata}')
        versions.append(vdata)

    # remove old tag versions if they no longer exist in the repo
    git_tags = [x.name for x in gitrepo.tags]
    for version in versions[:]:
        if version.get('version') not in git_tags:
            logger.info(f"removing {version['version']} because it no longer has a tag")
            versions.remove(version)

    return versions


def legacy_role_import(
    request_username=None,
    github_user=None,
    github_repo=None,
    github_reference=None,
    alternate_role_name=None,
    superuser_can_create_namespaces=False
):
    """
    Import a legacy role by user, repo and or reference.

    :param request_username:
        The username of the person making the import.
    :param github_user:
        The github org or username the role lives in.
    :param github_repo:
        The github repository name that the role lives in.
    :param github_reference:
        A commit, branch or tag name to import.
    :param alternate_role_name:
        Override the enumerated role name when the repo does
        not conform to the ansible-role-<name> convention.

    This function attempts to clone the github repository to a
    temporary directory and uses galaxy-importer functions to
    enumerate the metadata and doc strings. If the role already
    exists in the database, the code will attempt to add a new
    version to the full_metadata. Roles can be versionless so
    there will not be any duplicate key errors. However,
    the "commit" field should always reflect the latest import.
    """
    logger.info('START LEGACY ROLE IMPORT')
    logger.info(f'REQUEST_USERNAME:{request_username}')
    logger.info(f'GITHUB_USER:{github_user}')
    logger.info(f'GITHUB_REPO:{github_repo}')
    logger.info(f'GITHUB_REFERENCE:{github_reference}')
    logger.info(f'ALTERNATE_ROLE_NAME:{alternate_role_name}')
    logger.info(f'superuser_can_create_namespaces: {superuser_can_create_namespaces}')

    clone_url = None

    request_user = User.objects.filter(username=request_username).first()
    logger.info(f'REQUEST_USER: {request_user}')

    # prevent empty strings?
    if not github_reference:
        github_reference = None

    # some roles have their github_user set differently from their namespace name ...
    real_role, real_namespace_name, real_github_user, real_github_repo, clone_url = \
        find_real_role(github_user, github_repo)
    if real_role:
        logger.info(f'Using {real_role} as basis for import task')

    # this shouldn't happen but just in case ...
    if request_username and not User.objects.filter(username=request_username).exists():
        logger.error(f'Username {request_username} does not exist in galaxy')
        raise Exception(f'Username {request_username} does not exist in galaxy')

    # the user should have a legacy and v3 namespace if they logged in ...
    namespace = LegacyNamespace.objects.filter(name=real_namespace_name).first()
    if not namespace:

        if not request_user.is_superuser or \
                (request_user.is_superuser and not superuser_can_create_namespaces):
            logger.error(f'No legacy namespace exists for {github_user}')
            raise Exception(f'No legacy namespace exists for {github_user}')

        logger.info(f'create legacynamespace {real_namespace_name}')
        namespace, _ = LegacyNamespace.objects.get_or_create(name=real_namespace_name)

    # we have to have a v3 namespace because of the rbac based ownership ...
    v3_namespace = namespace.namespace
    if not v3_namespace:

        if not request_user.is_superuser or \
                (request_user.is_superuser and not superuser_can_create_namespaces):
            logger.error(f'No v3 namespace exists for {github_user}')
            raise Exception(f'No v3 namespace exists for {github_user}')

        # transformed name ... ?
        v3_name = generate_v3_namespace_from_attributes(username=real_namespace_name)
        logger.info(f'creating namespace {v3_name}')
        v3_namespace, _ = Namespace.objects.get_or_create(name=v3_name)
        namespace.namespace = v3_namespace
        namespace.save()

    with tempfile.TemporaryDirectory() as tmp_path:
        # galaxy-importer requires importing legacy roles from the role's parent directory.
        os.chdir(tmp_path)

        # galaxy-importer wants the role's directory to be the name of the role.
        checkout_path = os.path.join(tmp_path, github_repo)
        if clone_url is None:
            clone_url = f'https://github.com/{github_user}/{github_repo}'

        # process the checkout ...
        gitrepo, github_reference, last_commit = \
            do_git_checkout(clone_url, checkout_path, github_reference)

        # relevant data for this new role version ...
        github_commit = last_commit.hexsha
        github_commit_message = last_commit.message
        github_commit_date = last_commit.committed_datetime.isoformat()

        logger.info(f'GITHUB_REFERENCE: {github_reference}')
        logger.info(f'GITHUB_COMMIT: {github_commit}')
        logger.info(f'GITHUB_COMMIT_MESSAGE: {github_commit_message}')
        logger.info(f'GITHUB_COMMIT_DATE: {github_commit_date}')

        # Parse legacy role with galaxy-importer.
        importer_config = Config()
        result = import_legacy_role(checkout_path, namespace.name, importer_config, logger)
        galaxy_info = result["metadata"]["galaxy_info"]
        logger.debug(f"FOUND TAGS: {galaxy_info['galaxy_tags']}")

        # munge the role name via an order of precedence
        role_name = result["name"] or alternate_role_name or \
            github_repo.replace("ansible-role-", "")

        new_full_metadata = {
            'imported': datetime.datetime.now().isoformat(),
            'clone_url': clone_url,
            'tags': galaxy_info["galaxy_tags"],
            'commit': github_commit,
            'github_user': real_github_user,
            'github_repo': real_github_repo,
            'github_branch': github_reference,
            'github_reference': github_reference,
            'import_branch': github_reference,
            'commit': github_commit,
            'commit_message': github_commit_message,
            'issue_tracker_url': galaxy_info["issue_tracker_url"] or clone_url + "/issues",
            'dependencies': result["metadata"]["dependencies"],
            'versions': [],
            'description': galaxy_info["description"] or "",
            'license': galaxy_info["license"] or "",
            'min_ansible_version': galaxy_info["min_ansible_version"] or "",
            'min_ansible_container_version': galaxy_info["min_ansible_container_version"] or "",
            'platforms': galaxy_info["platforms"],
            'readme': result["readme_file"],
            'readme_html': result["readme_html"]
        }

        # Make or get the object
        if real_role:
            this_role = real_role
        else:
            this_role, _ = LegacyRole.objects.get_or_create(
                namespace=namespace,
                name=role_name
            )

        # set the enumerated versions ...
        new_full_metadata['versions'] = compute_all_versions(this_role, gitrepo)

        # Save the new metadata
        this_role.full_metadata = new_full_metadata

        # Set the correct name ...
        if this_role.name != role_name:
            this_role.name = role_name

        this_role.save()

    logger.debug('STOP LEGACY ROLE IMPORT')
    return True


def legacy_sync_from_upstream(
    baseurl=None,
    github_user=None,
    role_name=None,
    role_version=None,
    limit=None,
    start_page=None,
):
    """
    Sync legacy roles from a remote v1 api.

    :param baseurl:
        Allow the client to override the upstream v1 url this task will sync from.
    :param github_user:
        Allow the client to reduce the set of synced roles by the username.
    :param role_name:
        Allow the client to reduce the set of synced roles by the role name.
    :param limit:
        Allow the client to reduce the total number of synced roles.

    This is conceptually similar to the pulp_ansible/app/tasks/roles.py:synchronize
    function but has more robust handling and better schema matching. Although
    not considered something we'd be normally running on a production hosted
    galaxy instance, it is necessary for mirroring the roles into that future
    system until it is ready to deprecate the old instance.
    """

    logger.debug(
        'STARTING LEGACY SYNC!'
        + f' {baseurl} {github_user} {role_name} {role_version} {limit}'
    )

    logger.debug('SYNC INDEX EXISTING NAMESPACES')
    nsmap = {}

    # allow the user to specify how many roles to sync
    if limit is not None:
        limit = int(limit)

    # index of all roles
    rmap = {}

    iterator_kwargs = {
        'baseurl': baseurl,
        'github_user': github_user,
        'role_name': role_name,
        'limit': limit,
        'start_page': start_page,
    }
    for ns_data, rdata, rversions in upstream_role_iterator(**iterator_kwargs):

        # processing a namespace should make owners and set rbac as needed ...
        if ns_data['name'] not in nsmap:
            namespace, v3_namespace = process_namespace(ns_data['name'], ns_data)
            nsmap[ns_data['name']] = (namespace, v3_namespace)
        else:
            namespace, v3_namespace = nsmap[ns_data['name']]

        github_user = rdata.get('github_user')
        role_name = rdata.get('name')

        logger.info(f'POPULATE {github_user}.{role_name}')

        rkey = (github_user, role_name)
        remote_id = rdata['id']
        role_versions = rversions[:]
        # github_user = rdata['github_user']
        github_repo = rdata['github_repo']
        github_branch = rdata['github_branch']
        clone_url = f'https://github.com/{github_user}/{github_repo}'
        sfields = rdata.get('summary_fields', {})
        role_tags = sfields.get('tags', [])
        commit_hash = rdata.get('commit')
        commit_msg = rdata.get('commit_message')
        commit_url = rdata.get('commit_url')
        issue_tracker = rdata.get('issue_tracker_url', clone_url + '/issues')
        # role_versions = sfields.get('versions', [])
        role_description = rdata.get('description')
        role_license = rdata.get('license')
        role_readme = rdata.get('readme')
        role_html = rdata.get('readme_html')
        role_dependencies = sfields.get('dependencies', [])
        role_min_ansible = rdata.get('min_ansible_version')
        role_company = rdata.get('company')
        role_imported = rdata.get('imported', datetime.datetime.now().isoformat())
        role_created = rdata.get('created', datetime.datetime.now().isoformat())
        role_modified = rdata.get('modified', datetime.datetime.now().isoformat())
        role_type = rdata.get('role_type', 'ANS')
        role_download_count = rdata.get('download_count', 0)

        if rkey not in rmap:
            logger.debug(f'SYNC create initial role for {rkey}')
            this_role, _ = LegacyRole.objects.get_or_create(
                namespace=namespace,
                name=role_name
            )
            rmap[rkey] = this_role
        else:
            this_role = rmap[rkey]

        new_full_metadata = {
            'upstream_id': remote_id,
            'role_type': role_type,
            'imported': role_imported,
            'created': role_created,
            'modified': role_modified,
            'clone_url': clone_url,
            'tags': role_tags,
            'commit': commit_hash,
            'commit_message': commit_msg,
            'commit_url': commit_url,
            'github_user': github_user,
            'github_repo': github_repo,
            'github_branch': github_branch,
            # 'github_reference': github_reference,
            'issue_tracker_url': issue_tracker,
            'dependencies': role_dependencies,
            'versions': role_versions,
            'description': role_description,
            'license': role_license,
            'readme': role_readme,
            'readme_html': role_html,
            'min_ansible_version': role_min_ansible,
            'company': role_company,
        }

        if dict(this_role.full_metadata) != new_full_metadata:
            with transaction.atomic():
                this_role.full_metadata = new_full_metadata
                this_role.save()

        with transaction.atomic():
            counter, _ = LegacyRoleDownloadCount.objects.get_or_create(legacyrole=this_role)
            counter.count = role_download_count
            counter.save()

    logger.debug('STOP LEGACY SYNC!')
