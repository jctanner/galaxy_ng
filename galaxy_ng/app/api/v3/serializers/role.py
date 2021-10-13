import logging
import mimetypes


from rest_framework import serializers
from rest_framework.exceptions import ValidationError, _get_error_details
from rest_framework.reverse import reverse

from galaxy_ng.app.api.ui.serializers.base import Serializer

from pulp_ansible.app.serializers import (
    GitRemoteSerializer
)

log = logging.getLogger(__name__)



class NGRoleSerializer(GitRemoteSerializer):

    class Meta:
        ref_name = "NGRoleSerializer"
        fields = ('meta')
