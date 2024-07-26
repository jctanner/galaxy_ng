# from django.contrib.auth.models import User
from rest_framework import serializers
from django.contrib.auth import get_user_model
from ansible_base.resource_registry.models import Resource


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):

    ansible_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'ansible_id',
            'username',
        ]

    def get_ansible_id(self, obj):
        try:
            return Resource.objects.get(object_id=obj.id).ansible_id
        except:
            return None
