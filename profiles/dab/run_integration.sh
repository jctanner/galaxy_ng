set -e

VENVPATH=/tmp/gng_testing
PIP=${VENVPATH}/bin/pip
if  [[ ! -d $VENVPATH ]]; then
    virtualenv --python=$(which python3.11) $VENVPATH
    $PIP install -r integration_requirements.txt
fi
source $VENVPATH/bin/activate
#if [[ -d ../galaxykit ]]; then
#    cd 
#    $PIP install -e ../galaxykit
#fi

#cd /src/galaxy_ng/
#django-admin shell < ./dev/common/setup_test_data.py
#cd galaxy_ng
#django-admin makemessages --all
# cd /src/galaxy_ng/

set -x

export HUB_API_ROOT=https://localhost/api/galaxy/
# export HUB_ADMIN_PASS=admin
export HUB_USE_MOVE_ENDPOINT=1
export HUB_LOCAL=1
export ENABLE_DAB_TESTS=1
export HUB_TEST_MARKS="(deployment_standalone or x_repo_search or all) and not package and not iqe_ldap and not skip_in_gw"
export JWT_PROXY=false
export AAP_GATEWAY=true
export GW_ROOT_URL=https://localhost


$VENVPATH/bin/python profiles/dab/make_test_data.py


$VENVPATH/bin/pytest -v -r sx --color=yes -m "$HUB_TEST_MARKS" "$@" galaxy_ng/tests/integration
RC=$?

exit $RC
