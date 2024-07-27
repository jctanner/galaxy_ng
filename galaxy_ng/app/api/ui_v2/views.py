from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from ansible_base.resource_registry.models import Resource
from ansible_base.rest_pagination.default_paginator import DefaultPaginator

from .filters import UserResourcesViewFilter
from .filters import TeamResourcesViewFilter
from .models import UserResourcesView
from .models import TeamResourcesView
from .serializers import UserSerializer
from .serializers import TeamSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = UserResourcesView.objects.all().order_by('user__id')
    serializer_class = UserSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = UserResourcesViewFilter
    pagination_class = DefaultPaginator


class TeamViewSet(viewsets.ModelViewSet):
    queryset = TeamResourcesView.objects.all().order_by('team__id')
    serializer_class = TeamSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TeamResourcesViewFilter
    pagination_class = DefaultPaginator
