#!/usr/bin/env python3

import random
import pytest
from jsonschema import validate as validate_json

from ..constants import DEFAULT_DISTROS
from ..utils import UIClient
from ..schemas import (
    schema_objectlist,
    schema_user,
    schema_me,
    schema_settings,
    schema_featureflags,
    schema_distro,
    schema_distro_repository,
    schema_remote,
    schema_group,
    schema_collectionversion,
    schema_collectionversion_metadata
)


# /api/automation-hub/_ui/v1/auth/login/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_login(ansible_config):

    cfg = ansible_config('ansible_partner')

    # an authenticated session has a csrftoken and a sessionid
    with UIClient(config=cfg) as uclient:
        assert uclient.cookies['csrftoken'] is not None
        assert uclient.cookies['sessionid'] is not None


# /api/automation-hub/_ui/v1/auth/logout/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_logout(ansible_config):

    cfg = ansible_config('ansible_partner')
    uclient = UIClient(config=cfg)

    # check the auth first
    uclient.login()
    assert uclient.cookies['csrftoken'] is not None
    assert uclient.cookies['sessionid'] is not None

    # logout should clear the sessionid but not the csrftoken
    uclient.logout(expected_code=204)
    assert uclient.cookies['csrftoken'] is not None
    assert 'sessionid' not in uclient.cookies


# /api/automation-hub/_ui/v1/collection-versions/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_collection_versions(ansible_config, uncertifiedv2):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:
        resp = uclient.get('_ui/v1/collection-versions/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        assert len(ds['data']) >= 1

        for cv in ds['data']:
            validate_json(instance=cv, schema=schema_collectionversion)
            validate_json(instance=cv['metadata'], schema=schema_collectionversion_metadata)

            # try to get the direct url for this version ...
            cv_url = f"_ui/v1/collection-versions/{cv['namespace']}/{cv['name']}/{cv['version']}/"
            cv_resp = uclient.get(cv_url)
            assert cv_resp.status_code == 200

            ds = cv_resp.json()
            validate_json(instance=ds, schema=schema_collectionversion)
            validate_json(instance=ds['metadata'], schema=schema_collectionversion_metadata)


# /api/automation-hub/_ui/v1/collection-versions/{version}/
# ^ tested by previous function


# /api/automation-hub/_ui/v1/collection_signing/
# /api/automation-hub/_ui/v1/collection_signing/{path}/
# /api/automation-hub/_ui/v1/collection_signing/{path}/{namespace}/
# /api/automation-hub/_ui/v1/collection_signing/{path}/{namespace}/{collection}/
# /api/automation-hub/_ui/v1/collection_signing/{path}/{namespace}/{collection}/{version}/
# /api/automation-hub/_ui/v1/controllers/


# /api/automation-hub/_ui/v1/distributions/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_distributions(ansible_config):
    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:
        resp = uclient.get('_ui/v1/distributions/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        for distro in ds['data']:
            validate_json(instance=distro, schema=schema_distro)
            validate_json(instance=distro['repository'], schema=schema_distro_repository)

        # make sure all default distros are in the list ...
        distro_tuples = [(x['name'], x['base_path']) for x in ds['data']]
        for k, v in DEFAULT_DISTROS.items():
            key = (k, v['basepath'])
            assert key in distro_tuples


# /api/automation-hub/_ui/v1/distributions/{pulp_id}/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_distributions_by_id(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/distributions/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        for distro in ds['data']:
            validate_json(instance=distro, schema=schema_distro)

        # check the endpoint for each distro by pulp id ...
        distro_ids = [x['pulp_id'] for x in ds['data']]
        for distro_id in distro_ids:
            resp = uclient.get(f'_ui/v1/distributions/{distro_id}')
            assert resp.status_code == 200
            _ds = resp.json()
            validate_json(instance=_ds, schema=schema_distro)
            validate_json(instance=_ds['repository'], schema=schema_distro_repository)
            assert _ds['pulp_id'] == distro_id


# /api/automation-hub/_ui/v1/execution-environments/namespaces/
# /api/automation-hub/_ui/v1/execution-environments/namespaces/{name}/
# /api/automation-hub/_ui/v1/execution-environments/registries/
# /api/automation-hub/_ui/v1/execution-environments/registries/{pulp_id}/
# /api/automation-hub/_ui/v1/execution-environments/registries/{id}/index/
# /api/automation-hub/_ui/v1/execution-environments/registries/{id}/sync/
# /api/automation-hub/_ui/v1/execution-environments/remotes/
# /api/automation-hub/_ui/v1/execution-environments/remotes/{pulp_id}/
# /api/automation-hub/_ui/v1/execution-environments/repositories/
# /api/automation-hub/_ui/v1/execution-environments/repositories/{base_path}/
# /api/automation-hub/_ui/v1/execution-environments/repositories/{base_path}/_content/history/
# /api/automation-hub/_ui/v1/execution-environments/repositories/{base_path}/_content/images/
# /api/automation-hub/_ui/v1/execution-environments/repositories/{base_path}/_content/images/{manifest_ref}/
# /api/automation-hub/_ui/v1/execution-environments/repositories/{base_path}/_content/readme/
# /api/automation-hub/_ui/v1/execution-environments/repositories/{base_path}/_content/sync/
# /api/automation-hub/_ui/v1/execution-environments/repositories/{base_path}/_content/tags/


# /api/automation-hub/_ui/v1/feature-flags/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_feature_flags(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/feature-flags/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_featureflags)


# /api/automation-hub/_ui/v1/groups/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_groups(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/groups/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        for grp in ds['data']:
            validate_json(instance=grp, schema=schema_group)

        # try to make a group
        suffix = random.choice(range(0, 1000))
        payload = {'name': f'foobar{suffix}'}
        resp = uclient.post('_ui/v1/groups/', payload=payload)
        assert resp.status_code == 201

        ds = resp.json()
        validate_json(instance=ds, schema=schema_group)
        assert ds['name'] == payload['name']
        assert ds['pulp_href'].endswith(f"/{ds['id']}/")


# /api/automation-hub/_ui/v1/groups/{group_pk}/model-permissions/
# /api/automation-hub/_ui/v1/groups/{group_pk}/model-permissions/{id}/
# /api/automation-hub/_ui/v1/groups/{group_pk}/users/
# /api/automation-hub/_ui/v1/groups/{group_pk}/users/{id}/


# /api/automation-hub/_ui/v1/groups/{id}/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_groups_by_id(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/groups/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        for grp in ds['data']:
            gid = grp['id']
            gresp = uclient.get(f'_ui/v1/groups/{gid}/')
            assert gresp.status_code == 200
            ds = gresp.json()
            validate_json(instance=ds, schema=schema_group)
            assert ds['id'] == gid


# /api/automation-hub/_ui/v1/imports/collections/
# /api/automation-hub/_ui/v1/imports/collections/{task_id}/


# /api/automation-hub/_ui/v1/landing-page/
# ^ tested in tests/integration/api/test_landing_page.py

# /api/automation-hub/_ui/v1/me/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_me(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/me')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_me)

        assert not ds['is_anonymous']
        assert ds['username'] == cfg.get('username')
        assert ds['email'] == 'admin@example.com'
        assert ds['auth_provider'] == ['django']
        assert ds['groups'] == [{'id': 1, 'name': 'system:partner-engineers'}]
        assert ds['id'] == 1


# /api/automation-hub/_ui/v1/my-distributions/
# /api/automation-hub/_ui/v1/my-distributions/{pulp_id}/
# /api/automation-hub/_ui/v1/my-namespaces/
# /api/automation-hub/_ui/v1/my-namespaces/{name}/
# /api/automation-hub/_ui/v1/my-synclists/
# /api/automation-hub/_ui/v1/my-synclists/{id}/
# /api/automation-hub/_ui/v1/my-synclists/{id}/curate/


# /api/automation-hub/_ui/v1/namespaces/
# ^ tested in tests/integration/api/test_namespace_management.py


# /api/automation-hub/_ui/v1/namespaces/{name}/
# ^ tested in tests/integration/api/test_namespace_management.py


# /api/automation-hub/_ui/v1/remotes/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_remotes(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/remotes/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        for remote in ds['data']:
            validate_json(instance=remote, schema=schema_remote)

        remote_names = [x['name'] for x in ds['data']]
        assert 'community' in remote_names
        assert 'rh-certified' in remote_names


# /api/automation-hub/_ui/v1/remotes/{pulp_id}/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_remotes_by_id(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/remotes/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        for remote in ds['data']:
            validate_json(instance=remote, schema=schema_remote)

        # FIXME - there is no suitable pulp_id for a remote?
        pulp_ids = [x['pk'] for x in ds['data']]
        for pulp_id in pulp_ids:
            resp = uclient.get('_ui/v1/remotes/{pulp_id}/')
            assert resp.status_code == 404


# /api/automation-hub/_ui/v1/repo/{distro_base_path}/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_repo_distro_by_basepath(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get each repo by basepath? or is it get a distro by basepath?
        for k, v in DEFAULT_DISTROS.items():
            bp = v['basepath']
            resp = uclient.get(f'_ui/v1/repo/{bp}')
            ds = resp.json()
            validate_json(instance=ds, schema=schema_objectlist)


# /api/automation-hub/_ui/v1/repo/{distro_base_path}/{namespace}/{name}/
# ^ FIXME - need some examples


# /api/automation-hub/_ui/v1/settings/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_settings(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/settings/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_settings)

        # FIXME - password length and token expiration are None?
        assert ds['GALAXY_ENABLE_UNAUTHENTICATED_COLLECTION_ACCESS'] is False
        assert ds['GALAXY_ENABLE_UNAUTHENTICATED_COLLECTION_DOWNLOAD'] is False
        assert ds['GALAXY_REQUIRE_CONTENT_APPROVAL'] is True

        ff = ds['GALAXY_FEATURE_FLAGS']
        validate_json(instance=ff, schema=schema_featureflags)


# /api/automation-hub/_ui/v1/synclists/
# /api/automation-hub/_ui/v1/synclists/{id}/


# /api/automation-hub/_ui/v1/tags/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_tags(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/tags/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        # FIXME - ui tags api does not support POST?


# /api/automation-hub/_ui/v1/users/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_users(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/users/')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_objectlist)

        assert len(ds['data']) >= 1
        for user in ds['data']:
            validate_json(instance=user, schema=schema_user)

        # try creating a user
        suffix = random.choice(range(0, 9999))
        payload = {
            'username': f'foobar{suffix}',
            'first_name': 'foobar',
            'last_name': f'{suffix}'
        }
        resp = uclient.post('_ui/v1/users/', payload=payload)
        assert resp.status_code == 201

        ds = resp.json()
        validate_json(instance=ds, schema=schema_user)

        # should NOT be superuser by default
        assert not ds['is_superuser']

        assert ds['username'] == payload['username']
        assert ds['first_name'] == payload['first_name']
        assert ds['last_name'] == payload['last_name']


# /api/automation-hub/_ui/v1/users/{id}/
@pytest.mark.standalone_only
@pytest.mark.api_ui
def test_api_ui_v1_users_by_id(ansible_config):

    cfg = ansible_config('ansible_partner')
    with UIClient(config=cfg) as uclient:

        # get the response
        resp = uclient.get('_ui/v1/users/1')
        assert resp.status_code == 200

        ds = resp.json()
        validate_json(instance=ds, schema=schema_user)

        assert ds['id'] == 1
        assert ds['username'] == cfg.get('username')
        assert ds['email'] == 'admin@example.com'
        assert ds['is_superuser'] is True
        assert ds['groups'] == [{'id': 1, 'name': 'system:partner-engineers'}]
