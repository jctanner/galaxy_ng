import gzip
import json
import os

from pprint import pprint

from galaxy_ng.app.api.v1.models import LegacyRole


def do_check():

    checkmode = True
    if os.environ.get('CHECK_MODE') == "0":
        checkmode = False

    # compressed for size ...
    fn = 'old_mismatched_namespaces.json.gz'
    with gzip.open(fn, 'rb') as gz_file:
        raw = gz_file.read()
    rows = json.loads(raw)

    for idr,row in enumerate(rows):

        '''
        print('-' * 100)
        print(f'{len(rows)} | {idr}')
        pprint(row)
        '''

        expected_github_user = row['provider_namespace__name']

        # can we find it by the upstream ID? ...
        role = LegacyRole.objects.filter(full_metadata__upstream_id=int(row['role_id'])).first()
        if not role:
            continue

        if role.full_metadata.get('github_user') != expected_github_user:
            print(f'FIX - ({len(rows)} | {idr}) set {role} github_user={expected_github_user}')
            if not checkmode:
                role.full_metadata['github_user'] = expected_github_user
                role.save()


do_check()
