import logging

from rest_framework.viewsets import ViewSetMixin

from pulp_ansible.app.galaxy.v3 import views as pulp_ansible_views
from pulp_ansible.app.viewsets import GitRemoteViewSet

from galaxy_ng.app import models
# from galaxy_ng.app.access_control import access_policy
from galaxy_ng.app.api import base as api_base
from galaxy_ng.app.api.v3.models.role import NGRole
from galaxy_ng.app.api.v3.serializers import (
    NGRoleSerializer
)

log = logging.getLogger(__name__)


class NGRoleViewSet(GitRemoteViewSet):

    model = NGRole

    # permission_classes = [access_policy.CollectionAccessPolicy]
    serializer_class = NGRoleSerializer

    '''
    # does this come from a mixin?
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view.cls = cls
        view.initkwargs = initkwargs
        return view
    '''

    '''
    @staticmethod
    def dispatch(request, *args, **kwargs):
        pass

    @staticmethod
    def list(*args, **kwargs):
        print('LIST')
        return []

    @staticmethod
    def get(*args, **kwargs):
        print('GET')
        return []
    '''
