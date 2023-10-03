import argparse
import re

from django.contrib.auth import get_user_model

from galaxy_ng.app.models import Namespace
from galaxy_ng.app.api.v1.models import LegacyNamespace
from galaxy_ng.app.utils import rbac

from pulp_ansible.app.models import CollectionVersion


User = get_user_model()


def strip_number_from_string(input_string):
    match = re.search(r'(\D+)(\d+)$', input_string)
    if match:
        prefix = match.group(1)
        number = match.group(2)
        return prefix, int(number)
    else:
        return input_string, None


def do_cleanup():
    # make a list of all namespace names
    ns_names = []
    for ns_name in Namespace.objects.values_list('name', flat=True):
        ns_names.append(ns_name)

    # map out names with a common prefix and a numbered suffix
    ns_map = {}
    for ns_name in ns_names:
        prefix, number = strip_number_from_string(ns_name)
        #print(f'{prefix} {number}')
        if number is None:
            continue
        if prefix not in ns_map:
            ns_map[prefix] = []
        ns_map[prefix].append(ns_name)

    # check each ns for content ...
    ns_keys = sorted(list(ns_map.keys()))
    for ns_key in ns_keys:

        if len(ns_map[ns_key]) <= 1:
            continue

        print(ns_key)
        # is there a user for this namespace ...?
        found_user = User.objects.filter(username=ns_key).first()

        for dupe_name in ns_map[ns_key]:
            ns = Namespace.objects.filter(name=dupe_name).first()
            collection_count = CollectionVersion.objects.filter(namespace=dupe_name).count()
            dupe_owners = rbac.get_v3_namespace_owners(ns)
            print(f'\t{dupe_name} collections:{collection_count} owners:{dupe_owners}')

    #import epdb; epdb.st()


do_cleanup()
