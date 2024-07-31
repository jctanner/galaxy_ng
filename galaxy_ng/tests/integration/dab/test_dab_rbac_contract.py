import pytest

import contextlib


# This tests the basic DAB RBAC contract using custom roles to do things


def test_list_namespace_permissions(galaxy_client):
    gc = galaxy_client("admin")
    r = gc.get("/api/galaxy/_ui/v2/role_metadata/")
    assert "galaxy.namespace" in r["allowed_permissions"]
    allowed_perms = r["allowed_permissions"]["galaxy.namespace"]
    assert set(allowed_perms) == {
        "galaxy.change_namespace",
        "galaxy.delete_namespace",
        "galaxy.add_collectionimport",
        "galaxy.change_collectionimport",
        "galaxy.delete_collectionimport",
        "galaxy.upload_to_namespace",
        "galaxy.view_collectionimport",
        "galaxy.view_namespace",
    }


# look for the content_type choices
def test_role_definition_options(galaxy_client):
    gc = galaxy_client("admin")
    # TODO: add support for options in GalaxyClient in galaxykit
    options_r = gc._http("options", "/api/galaxy/_ui/v2/role_definitions/")
    assert 'actions' in options_r
    assert 'POST' in options_r['actions']
    assert 'permissions' in options_r['actions']['POST']
    post_data = options_r['actions']['POST']
    assert 'permissions' in post_data
    field_data = post_data['permissions']
    assert 'child' in field_data
    assert 'choices' in field_data['child']
    assert set(item['value'] for item in field_data['child']['choices']) == {
        "galaxy.change_namespace",
        "galaxy.add_namespace",
        "galaxy.delete_namespace",
        "galaxy.add_collectionimport",
        "galaxy.change_collectionimport",
        "galaxy.delete_collectionimport",
        "galaxy.upload_to_namespace",
        "galaxy.view_collectionimport",
        "galaxy.view_namespace",
        'shared.add_team',
        'shared.change_team',
        'shared.delete_team',
        'shared.view_team',
    }

    assert 'content_type' in post_data
    field_data = post_data['content_type']
    assert 'choices' in field_data
    assert set(item['value'] for item in field_data['choices']) == {
        'galaxy.collectionimport',
        'galaxy.namespace',
        'shared.team',
    }


NS_FIXTURE_DATA = {
    "name": "My own Namespace admin role",
    "permissions": [
        "galaxy.change_namespace",
        "galaxy.delete_namespace",
        "galaxy.view_namespace",
        "galaxy.view_collectionimport",
    ],
    "content_type": None,
}


@pytest.fixture(scope="session")
def custom_role_creator(galaxy_client):
    @contextlib.contextmanager
    def _rf(data):
        gc = galaxy_client("admin")
        list_r = gc.get(f"/api/galaxy/_ui/v2/role_definitions/?name={data['name']}")
        if list_r["count"] == 1:
            r = list_r["results"][0]
            yield r
        elif list_r["count"] > 1:
            raise RuntimeError(f"Found too many role_definitions with expected name {data['name']}")
        else:
            r = gc.post("/api/galaxy/_ui/v2/role_definitions/", body=data)
            yield r
        with pytest.raises(ValueError):
            gc.delete(f'/api/galaxy/_ui/v2/role_definitions/{r["id"]}/')
    return _rf


@pytest.fixture(scope="module")
def custom_ns_role(galaxy_client, custom_role_creator):
    with custom_role_creator(NS_FIXTURE_DATA) as ns_role:
        yield ns_role


# these fixtures are function-scoped so they will be deleted
# deleting the role will delete all associated permissions
@pytest.fixture
def custom_obj_role(galaxy_client, custom_role_creator):
    data = NS_FIXTURE_DATA.copy()
    data['name'] = 'galaxy.namespace_custom_object_role'
    data['content_type'] = 'galaxy.namespace'
    with custom_role_creator(data) as ns_role:
        yield ns_role


@pytest.fixture
def namespace(galaxy_client):
    gc = galaxy_client("admin")
    payload = {'name': 'new_namespace'}
    ns = gc.post("_ui/v1/my-namespaces/", body=payload)
    yield ns
    with pytest.raises(ValueError):
        gc.delete(f"_ui/v1/my-namespaces/{ns['name']}/")


def test_create_custom_namespace_admin_role(custom_ns_role):
    assert custom_ns_role["name"] == NS_FIXTURE_DATA["name"]


def test_give_custom_role_system(galaxy_client, custom_ns_role):
    gc = galaxy_client("admin")
    user_r = gc.get("/api/galaxy/_ui/v2/users/")
    assert user_r["count"] > 0
    user = user_r["results"][0]
    assignment = gc.post(
        "/api/galaxy/_ui/v2/role_user_assignments/",
        body={"role_definition": custom_ns_role["id"], "user": user["id"]},
    )
    # TODO: make a request as the user and see that it works


@pytest.mark.parametrize('by_api', ['dab', 'pulp'])
def test_give_custom_role_object(galaxy_client, custom_obj_role, namespace, by_api):
    gc = galaxy_client("admin")
    user_r = gc.get("/api/galaxy/_ui/v2/users/")
    assert user_r["count"] > 0
    user = user_r["results"][0]

    # sanity - assignments should not exist at start of this test
    # Assure the assignment shows up in the pulp API
    r = gc.get(f"_ui/v1/my-namespaces/{namespace['name']}/")
    assert len(r['users']) == 0

    # Assure the assignment shows up in the DAB RBAC API
    r = gc.get(f"/api/galaxy/_ui/v2/role_user_assignments/?user={user['id']}&object_id={namespace['id']}")
    assert r['count'] == 0

    dab_assignment = None
    if by_api == 'dab':
        dab_assignment = gc.post(
            "/api/galaxy/_ui/v2/role_user_assignments/",
            body={"role_definition": custom_obj_role["id"], "user": user["id"], "object_id": str(namespace["id"])},
        )
    else:
        payload = {
            'name': namespace['name'],
            'users': [
                {
                    'id': user['id'],
                    'object_roles': [custom_obj_role['name']],
                }
            ]
        }
        gc.put(f"_ui/v1/my-namespaces/{namespace['name']}/", body=payload)

    # TODO: make a request as the user and see that it works

    # Assure the assignment shows up in the pulp API
    r = gc.get(f"_ui/v1/my-namespaces/{namespace['name']}/")
    assert len(r['users']) == 1

    # Assure the assignment shows up in the DAB RBAC API
    r = gc.get(f"/api/galaxy/_ui/v2/role_user_assignments/?user={user['id']}&object_id={namespace['id']}")
    assert r['count'] == 1
    if dab_assignment:
        assert r['results'][0]['id'] == dab_assignment['id']
