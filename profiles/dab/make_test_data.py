#!/usr/bin/env python

import requests
import warnings


warnings.filterwarnings("ignore")


HUB_API_ROOT = "https://localhost/api/galaxy/"
GW_ROOT_URL = "https://localhost"
ADMIN_AUTH = ('admin', 'redhat1234')

NAMESPACES = ("autohubtest2", "autohubtest3", "signing")
USERS = ("notifications_admin", "iqe_normal_user", "jdoe", "org-admin")

# FIXME - this seems to be dependant on not having a gateway
GROUP = "ns_group_for_tests"


# MAP OUT THE ROLES ..
rr = requests.get(
    GW_ROOT_URL + '/api/galaxy/_ui/v2/role_definitions/',
    verify=False,
    auth=ADMIN_AUTH
)
ROLEDEFS = dict((x['name'], x) for x in rr.json()['results'])


# MAKE AND MAP THE USERS ...
umap = {}
for USERNAME in USERS:

    payload = {'username': USERNAME, 'password': 'redhat'}
    if USERNAME == "notifications_admin":
        payload['is_superuser'] = True

    rr = requests.get(
        GW_ROOT_URL + f'/api/gateway/v1/users/?username={USERNAME}',
        verify=False,
        auth=ADMIN_AUTH
    )
    if rr.json()['count'] > 0:
        udata = rr.json()['results'][0]
    else:
        rr = requests.post(
            GW_ROOT_URL + '/api/gateway/v1/users/',
            verify=False,
            auth=ADMIN_AUTH,
            json=payload
        )
        udata = rr.json()

    umap[USERNAME] = udata

    # get the galaxy data ...
    rr = requests.get(
        GW_ROOT_URL + f'/api/galaxy/_ui/v2/users/?username={USERNAME}',
        verify=False,
        auth=ADMIN_AUTH
    )
    umap[USERNAME]['galaxy'] = rr.json()['results'][0]


# MAKE THE NAMESPACES ...
for NAMESPACE in NAMESPACES:
    rr = requests.get(
        GW_ROOT_URL + f'/api/galaxy/_ui/v1/namespaces/{NAMESPACE}/',
        verify=False,
        auth=ADMIN_AUTH
    )
    if rr.status_code == 404:
        prr = requests.post(
            GW_ROOT_URL + '/api/galaxy/_ui/v1/namespaces/',
            verify=False,
            auth=ADMIN_AUTH,
            json={"name": NAMESPACE, "groups": [], "users": []}
        )
        nsdata = prr.json()
    else:
        nsdata = rr.json()

    # add owner role for each user ..
    for USERNAME, udata in umap.items():
        payload = {
            # "role_definition": ROLEDEFS["galaxy.collection_namespace_owner"]["id"],
            "role_definition": ROLEDEFS["galaxy.content_admin"]["id"],
            # "object_id": nsdata['id'],
            "user": udata["galaxy"]["id"]
        }
        prr = requests.post(
            GW_ROOT_URL + '/api/galaxy/_ui/v2/role_user_assignments/',
            verify=False,
            auth=ADMIN_AUTH,
            json=payload
        )

        # galaxy.execution_environment_admin
        payload['role_definition'] = ROLEDEFS["galaxy.execution_environment_admin"]["id"]
        prr = requests.post(
            GW_ROOT_URL + '/api/galaxy/_ui/v2/role_user_assignments/',
            verify=False,
            auth=ADMIN_AUTH,
            json=payload
        )
