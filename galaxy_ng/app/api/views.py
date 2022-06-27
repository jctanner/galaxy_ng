import copy
import os

import galaxy_importer

from django.apps import apps
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from pulp_ansible.app.models import AnsibleDistribution

from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse

from galaxy_ng.app.api import base as api_base
from pulp_ansible.app.galaxy.views import RoleList


# define the version matrix at the module level to avoid the redefinition on every API call.
VERSIONS = {
    "available_versions": {
        "v1": "v1/",
        "v3": "v3/"
    },
    "server_version": apps.get_app_config("galaxy").version,
    "galaxy_ng_version": apps.get_app_config("galaxy").version,
    "galaxy_ng_commit": os.environ.get("GIT_COMMIT", ""),
    "galaxy_importer_version": galaxy_importer.__version__,
    "pulp_core_version": apps.get_app_config('core').version,
    "pulp_ansible_version": apps.get_app_config('ansible').version,
    "pulp_container_version": apps.get_app_config('container').version,
}


class ApiRootView(api_base.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        Returns the version matrix for the API + the current distro.
        """
        data = {**VERSIONS}

        if kwargs.get("path"):
            distro = get_object_or_404(
                AnsibleDistribution,
                base_path=self.kwargs["path"]
            )
            data["distro_base_path"] = distro.base_path

        return Response(data)


class ApiRedirectView(api_base.APIView):
    permission_classes = [IsAuthenticated]

    """Redirect requests to /api/automation-hub/api/ to /api/automation-hub/

    This is a workaround for https://github.com/ansible/ansible/issues/62073.
    This can be removed when ansible-galaxy stops appending '/api' to the url."""

    def get(self, request, *args, **kwargs):
        reverse_url_name = kwargs.get("reverse_url_name")

        reverse_kwargs = {}
        if "path" in kwargs:
            reverse_kwargs["path"] = kwargs["path"]

        return HttpResponseRedirect(reverse(reverse_url_name,
                                            kwargs=reverse_kwargs), status=307)

class LegacyRolesApiRedirectView(api_base.APIView):
    permission_classes = [AllowAny]

    """Redirect requests to /api/v1/roles to /api/pulp_ansible/galaxy/legacy/api/v1/roles
    """

    def get(self, request, *args, **kwargs):

        print(f'ARGS: {args}')
        print(f'KWARGS: {kwargs}')
        print(f'request: {dir(request)}')
        print(f'request.query_params: {request.query_params}')

        '''
        rargs = args[:]
        rkwargs = copy.deepcopy(kwargs)
        rkwargs['status'] = 307
        return HttpResponseRedirect('/pulp_ansible/galaxy/legacy/api/v1/roles/', *rargs, **rkwargs)
        '''

        #url = reverse(RoleList.as_view(), kwargs=kwargs)
        #url = reverse('RoleList', kwargs=kwargs)
        #url = reverse('pulp_ansible.app.galaxy.views.RoleList', kwargs=kwargs)

        url = '/pulp_ansible/galaxy/legacy/api/v1/roles/'
        if request.query_params:
            kwarg_items = []
            for k, v in request.query_params.items():
                kwarg_items.append(f'{k}={v}')
            url += '?' + '&'.join(kwarg_items)

        #url = '/pulp_ansible/galaxy/legacy/api/v1/roles/'
        #url = reverse(url, kwargs=request.query_params)

        print(f'REDIRECT URL: {url}')

        return HttpResponseRedirect(url, status=307)


class LegacyRoleVersionsApiRedirectView(api_base.APIView):
    permission_classes = [AllowAny]

    """Redirect requests to /api/v1/roles/{pk}/versions to /api/pulp_ansible/galaxy/legacy/api/v1/roles/{pk}/versions
    """

    def get(self, request, *args, **kwargs):

        print(f'ARGS: {args}')
        print(f'KWARGS: {kwargs}')
        print(f'request: {dir(request)}')
        print(f'request.query_params: {request.query_params}')

        '''
        rargs = args[:]
        rkwargs = copy.deepcopy(kwargs)
        rkwargs['status'] = 307
        return HttpResponseRedirect('/pulp_ansible/galaxy/legacy/api/v1/roles/', *rargs, **rkwargs)
        '''

        #url = reverse(RoleList.as_view(), kwargs=kwargs)
        #url = reverse('RoleList', kwargs=kwargs)
        #url = reverse('pulp_ansible.app.galaxy.views.RoleList', kwargs=kwargs)

        pk = kwargs.get('pk')
        url = f'/pulp_ansible/galaxy/legacy/api/v1/roles/{pk}/versions/'
        if request.query_params:
            kwarg_items = []
            for k, v in request.query_params.items():
                kwarg_items.append(f'{k}={v}')
            url += '?' + '&'.join(kwarg_items)

        #url = '/pulp_ansible/galaxy/legacy/api/v1/roles/'
        #url = reverse(url, kwargs=request.query_params)

        print(f'REDIRECT URL: {url}')

        return HttpResponseRedirect(url, status=307)


class LegacyImportsApiRedirectView(api_base.APIView):
    permission_classes = [AllowAny]

    """Redirect requests to /api/v1/imports to /api/pulp_ansible/galaxy/legacy/api/v1/roles
    """

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect('/pulp_ansible/galaxy/legacy/api/v1/imports/', status=307)

    def post(self, request, *args, **kwargs):
        return HttpResponseRedirect('/pulp_ansible/galaxy/legacy/api/v1/imports/', status=307)
