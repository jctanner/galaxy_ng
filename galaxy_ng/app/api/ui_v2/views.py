from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from ansible_base.resource_registry.models import Resource

from .filters import UserResourcesViewFilter
from .models import UserResourcesView
from .serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = UserResourcesView.objects.all()
    serializer_class = UserSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = UserResourcesViewFilter
