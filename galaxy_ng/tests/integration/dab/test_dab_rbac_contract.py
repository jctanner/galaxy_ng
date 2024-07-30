import pytest


# This tests the basic DAB RBAC contract using custom roles to do things

def test_list_namespace_permissions(galaxy_client):
    gc = galaxy_client('admin')
    r = gc.get('/api/galaxy/_ui/v2/role_metadata/')
    assert 'galaxy.namespace' in r['allowed_permissions']
    allowed_perms = r['allowed_permissions']['galaxy.namespace']
    assert set(allowed_perms) == {
        'galaxy.change_namespace',
        'galaxy.delete_namespace',
        'galaxy.add_collectionimport',
        'galaxy.change_collectionimport',
        'galaxy.delete_collectionimport',
        'galaxy.upload_to_namespace',
        'galaxy.view_collectionimport',
        'galaxy.view_namespace',
    }


@pytest.fixture(scope='module')
def custom_ns_role(galaxy_client):
    gc = galaxy_client('admin')
    list_r = gc.get('/api/galaxy/_ui/v2/role_definitions/?name=My own Namespace admin role')
    if list_r['count'] == 1:
        return list_r['results'][0]
    elif list_r['count'] > 1:
        raise RuntimeError('Found too many role_definitions with expected name')
    r = gc.post('/api/galaxy/_ui/v2/role_definitions/', body={
        "name": "My own Namespace admin role",
        "permissions": [
            'galaxy.change_namespace',
            'galaxy.delete_namespace',
            'galaxy.view_namespace',
            'galaxy.view_collectionimport'
        ],
        "content_type": None
    })
    return r    


def test_create_custom_namespace_admin_role(custom_ns_role):
    assert custom_ns_role['name'] == "My own Namespace admin role"


def test_give_custom_role(galaxy_client, custom_ns_role):
    gc = galaxy_client('admin')
    user_r = gc.get('/api/galaxy/_ui/v2/users/')
    assert user_r['count'] > 0
    user = user_r['results'][0]
    assignment = gc.post('/api/galaxy/_ui/v2/role_user_assignments/', body={
        'role_definition': custom_ns_role['id'],
        'user': user['id']
    })
    # TODO: make a request as the user and see that it works
