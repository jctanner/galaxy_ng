# from django.contrib.auth.models import User
from rest_framework import serializers
from django.contrib.auth import get_user_model
from ansible_base.resource_registry.models import Resource

from .models import UserResourcesView
from .models import TeamResourcesView


class UserSerializer(serializers.ModelSerializer):

    id = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    date_joined = serializers.SerializerMethodField()
    is_superuser = serializers.SerializerMethodField()
    auth_provider = serializers.SerializerMethodField()
    resource = serializers.SerializerMethodField()

    class Meta:
        model = UserResourcesView
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'groups',
            'date_joined',
            'is_superuser',
            'auth_provider',
            'resource',
        ]

    def get_id(self, obj):
        return obj.user.id

    def get_username(self, obj):
        return obj.user.id

    def get_first_name(self, obj):
        return obj.user.first_name

    def get_last_name(self, obj):
        return obj.user.last_name

    def get_email(self, obj):
        return obj.user.email

    def get_groups(self, obj):
        return []

    def get_date_joined(self, obj):
        return obj.user.date_joined

    def get_is_superuser(self, obj):
        return obj.user.is_superuser

    def get_auth_provider(self, obj):
        return []

    def get_resource(self, obj):
        return {
            'resource_type': obj.resource.content_type.name,
            'ansible_id': obj.resource.ansible_id,
        }


class TeamSerializer(serializers.ModelSerializer):

    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    group = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    resource = serializers.SerializerMethodField()

    class Meta:
        model = TeamResourcesView
        fields = [
            'id',
            'name',
            'group',
            'organization',
            'resource',
        ]

    def get_id(self, obj):
        return obj.team.id

    def get_name(self, obj):
        return obj.team.name

    def get_group(self, obj):
        return {
            'id': obj.group.id,
            'name': obj.group.name,
        }

    def get_organization(self, obj):
        return {
            'id': obj.organization.id,
            'name': obj.organization.name,
        }

    def get_resource(self, obj):
        return {
            'resource_type': obj.resource.content_type.name,
            'ansible_id': obj.resource.ansible_id,
        }
