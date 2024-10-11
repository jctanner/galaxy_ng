import copy
import datetime
import logging
import os
import subprocess
import traceback
import tempfile
import uuid

from ansible.module_utils.compat.version import LooseVersion

from galaxy_importer.config import Config
from galaxy_importer.legacy_role import import_legacy_role

from galaxy_ng.app.models.auth import User
from galaxy_ng.app.models import Namespace
from galaxy_ng.app.utils.namespaces import generate_v3_namespace_from_attributes
from galaxy_ng.app.utils.rbac import get_v3_namespace_owners

from galaxy_ng.app.api.v1.models import LegacyNamespace
from galaxy_ng.app.api.v1.models import LegacyRole
from galaxy_ng.app.api.v1.models import LegacyRoleImport
from galaxy_ng.app.api.v1.utils import sort_versions
from galaxy_ng.app.api.v1.utils import parse_version_tag

from pulpcore.plugin.models import Task

from git import Repo

from galaxy_ng.app.utils.galaxy import (
    uuid_to_int,
)


logger = logging.getLogger("galaxy_ng.app.api.v1.tasks.legacy_role_import")


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
    ).order_by('created')
    if candidates.count() > 0:
        real_role = candidates.first()
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
    logger.info(f'cloning {clone_url} ...')

    # pygit didn't have an obvious way to prevent interactive clones ...
    cmd_args = ['git', 'clone', '--recurse-submodules', clone_url, checkout_path]
    pid = subprocess.run(
        cmd_args,
        shell=False,
        env={'GIT_TERMINAL_PROMPT': '0'},
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
                logger.error(f'{cmd} failed: {error}')
                raise Exception(f'{cmd} failed')

        last_commit = [x for x in gitrepo.iter_commits()][0]

    else:
        # use the default branch ...
        github_reference = gitrepo.active_branch.name

        # use latest commit on HEAD
        last_commit = gitrepo.head.commit

    return gitrepo, github_reference, last_commit


def normalize_versions(versions):

    # convert old integer based IDs to uuid
    for vix, version in enumerate(versions):
        if isinstance(version.get('id', ''), int):
            versions[vix]['upstream_id'] = version['id']
            versions[vix]['id'] = str(uuid.uuid4())

    # Normalize keys
    for vix, version in enumerate(versions):
        if not version.get('tag'):
            if version.get('name'):
                versions[vix]['tag'] = version['name']
            else:
                versions[vix]['tag'] = version['version']

    # if looseversion can't make a numeric version from this tag
    # it's not going to work later. This also should cover the case
    # where previous galaxy_ng import code mistakenly thought
    # the branch+commit should be a version instead of only tags.
    for version in versions[:]:
        if not version.get('tag'):
            versions.remove(version)
            continue
        lver = LooseVersion(version['tag'].lower())
        if not any(isinstance(x, int) for x in lver.version):
            versions.remove(version)

    return versions


def compute_all_versions(this_role, gitrepo):
    """
    Build a reconciled list of old versions and new versions.
    """

    # Combine old versions with new ...
    old_metadata = copy.deepcopy(this_role.full_metadata)
    versions = old_metadata.get('versions', [])

    # fix keys from synced versions ...
    versions = normalize_versions(versions)

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

        if str(tag.name) in current_tags:
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
        if tag.name not in current_tags:
            logger.info(f'adding new version from tag: {tag.name}')
        versions.append(vdata)

    # remove old tag versions if they no longer exist in the repo
    git_tags = [x.name for x in gitrepo.tags]
    for version in versions[:]:
        vname = version.get('tag')
        if not vname:
            vname = version.get('name')
        if vname not in git_tags:
            logger.info(f"removing {vname} because it no longer has a tag")
            versions.remove(version)

    versions = sort_versions(versions)
    for version in versions:
        logger.info(f'tag: {version["tag"]} version: {version["version"]}')

    return versions


def legacy_role_import(
    request_username=None,
    github_user=None,
    github_repo=None,
    github_reference=None,
    alternate_namespace_name=None,
    alternate_role_name=None,
    alternate_clone_url=None,
    superuser_can_create_namespaces=False,
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
    :param alternate_namespace_name:
        NO-OP ... future for UI
    :param alternate_role_name:
        NO-OP ... future for UI
    :param alternate_clone_url:
        Override the enumerated clone url for the repo.
        Only used for testing right now.
    :param superuser_can_create_namespaces:
        If the function is called by a superuser, it still
        won't be allowed to create namespaces on the fly
        without this being set to True

    This function attempts to clone the github repository to a
    temporary directory and uses galaxy-importer functions to
    enumerate the metadata and doc strings. If the role already
    exists in the database, the code will attempt to add a new
    version to the full_metadata. Roles can be versionless so
    there will not be any duplicate key errors. However,
    the "commit" field should always reflect the latest import.
    """

    task = None
    v1_task_id = None
    task_id = None
    import_model = None
    try:
        task = Task.current()
    except Exception:
        pass
    if task:
        v1_task_id = uuid_to_int(str(task.pulp_id))
        task_id = task.pulp_id
        import_model, _ = LegacyRoleImport.objects.get_or_create(task_id=task_id)

    logger.info(f'Starting import: task_id={v1_task_id}, pulp_id={task_id}')
    logger.info('')

    # find the request user
    request_user = User.objects.filter(username=request_username).first()
    request_user_id = request_user.id if request_user else None

    logger.info('==== PARAMETERS ====')
    logger.info(f'importer username: {request_username}')
    logger.info(f'matched user: {request_user} id:{request_user_id}')
    logger.info(f'github_user: {github_user}')
    logger.info(f'github_repo: {github_repo}')
    logger.info(f'github_reference: {github_reference}')
    logger.info(f'alternate_clone_url: {alternate_clone_url}')
    logger.info(f'alternate_namespace_name: {alternate_namespace_name}')
    logger.info(f'alternate_role_name: {alternate_role_name}')
    logger.info('')

    if not request_user:
        logger.error(f'username {request_username} does not exist in galaxy')

    # prevent empty strings?
    if not github_reference:
        github_reference = None

    # some roles have their github_user set differently from their namespace name ...
    logger.info('==== CHECK FOR MATCHING ROLE(S) ====')
    real_role, real_namespace_name, real_github_user, real_github_repo, clone_url = \
        find_real_role(github_user, github_repo)
    if real_role:
        logger.info(
            f'user:{github_user} repo:{github_repo}'
            + f' matched existing role {real_role} id:{real_role.id}'
        )
    else:
        logger.info(
            f'user:{github_user} repo:{github_repo}'
            + ' did not match any existing roles'
        )
    logger.info('')

    if alternate_clone_url:
        clone_url = alternate_clone_url

    # the user should have a legacy and v3 namespace if they logged in ...
    namespace = LegacyNamespace.objects.filter(name=real_namespace_name).first()
    if not namespace:

        if not request_user.is_superuser or \
                (request_user.is_superuser and not superuser_can_create_namespaces):
            logger.error(f'No standalone namespace exists for {github_user}')
            raise Exception(f'No standalone namespace exists for {github_user}')

        logger.info(f'create standalone namespace {real_namespace_name}')
        namespace, _ = LegacyNamespace.objects.get_or_create(name=real_namespace_name)

    # we have to have a v3 namespace because of the rbac based ownership ...
    v3_namespace = namespace.namespace
    if not v3_namespace:

        if not request_user.is_superuser or \
                (request_user.is_superuser and not superuser_can_create_namespaces):
            logger.error(f'no v3 namespace exists for {github_user}')
            raise Exception(f'no v3 namespace exists for {github_user}')

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
        logger.info('===== CLONING REPO =====')
        gitrepo, github_reference, last_commit = \
            do_git_checkout(clone_url, checkout_path, github_reference)
        logger.info('')

        # relevant data for this new role version ...
        logger.info('===== GIT ATTRIBUTES =====')
        github_commit = last_commit.hexsha
        github_commit_message = last_commit.message
        github_commit_date = last_commit.committed_datetime.isoformat()
        logger.info(f'github_reference(branch): {github_reference}')
        logger.info(f'github_commit: {github_commit}')
        logger.info(f'github_commit_message: {github_commit_message}')
        logger.info(f'github_commit_date: {github_commit_date}')
        logger.info('')

        # Parse legacy role with galaxy-importer.
        logger.info('===== LOADING ROLE =====')
        try:
            importer_config = Config()
            result = import_legacy_role(checkout_path, namespace.name, importer_config, logger)
        except Exception as e:
            logger.info('')
            logger.error(f'Role loading failed! {str(e)}')
            logger.info('')
            tb_str = traceback.format_exc()
            logger.error(tb_str)
            raise e
        logger.info('')

        logger.info('===== PROCESSING LOADER RESULTS ====')

        # Allow the meta/main.yml to define the destination namespace ...
        new_namespace_name = namespace.name
        if alternate_namespace_name:
            new_namespace_name = alternate_namespace_name
            logger.info(f'overriding namespace name via parameter: {alternate_namespace_name}')
        elif result['metadata']['galaxy_info'].get('namespace'):
            new_namespace_name = result['metadata']['galaxy_info'].get('namespace')
            logger.info(f'overriding namespace name via metadata: {new_namespace_name}')

        if namespace.name != new_namespace_name:

            # does it exist and is the user an owner?
            found = LegacyNamespace.objects.filter(name=new_namespace_name).first()
            if found:
                provider = found.namespace
                if provider:
                    owners = get_v3_namespace_owners(provider)
                else:
                    owners = []

                if not provider and not request_user.is_superuser:
                    logger.error(
                        f'legacy namespace {found} has no provider namespace to define owners'
                    )
                    raise Exception('permission denied')

                if request_user not in owners and not request_user.is_superuser:
                    logger.error(
                        f'{request_user.username} is not an owner'
                        f' of provider namespace {provider.name}'
                    )
                    raise Exception('permission denied')

            else:
                # we need to create the namespace but only if allowed ...
                if not request_user.is_superuser or not superuser_can_create_namespaces:
                    logger.error(
                        f'legacy namespace {new_namespace_name} does not exist'
                    )
                    raise Exception('permission denied')

                logger.info('creating legacy namespace {new_namespace_name}')
                namespace, _ = LegacyNamespace.objects.get_or_create(name=new_namespace_name)

            namespace, _ = LegacyNamespace.objects.get_or_create(name=new_namespace_name)
            real_role = None

        # munge the role name via an order of precedence
        if alternate_role_name:
            role_name = alternate_role_name
        elif result["metadata"]["galaxy_info"].get("role_name"):
            role_name = result["metadata"]["galaxy_info"]["role_name"]
        else:
            role_name = github_repo.replace("ansible-role-", "")

        logger.info(f'enumerated role name {role_name}')
        if real_role and real_role.name != role_name:
            real_role = None

        galaxy_info = result["metadata"]["galaxy_info"]
        new_full_metadata = {
            'imported': datetime.datetime.now().isoformat(),
            'clone_url': clone_url,
            'tags': galaxy_info.get("galaxy_tags", []),
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
            logger.info(f'created new role id:{this_role.id} {this_role}')

        # set the enumerated versions ...
        logger.info('')
        logger.info('===== COMPUTING ROLE VERSIONS ====')
        new_versions = compute_all_versions(this_role, gitrepo)
        new_full_metadata['versions'] = new_versions
        logger.info('')

        # Save the new metadata
        this_role.full_metadata = new_full_metadata

        # Set the correct name ...
        if this_role.name != role_name:
            logger.info('==== CHECK NEW ROLE NAME ====')
            logger.info(f'changing role name from {this_role.name} to {role_name}')
            this_role.name = role_name
            logger.info('')

        logger.info('==== SAVING ROLE ====')
        this_role.save()

    # bind the role to the import log model
    if import_model:
        import_model.refresh_from_db()
        import_model.role = this_role
        import_model.save()

    logger.info('')
    logger.info('Import completed')
    return this_role
