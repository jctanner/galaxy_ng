from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from ansible_base.resource_registry.models import Resource
from ansible_base.rest_pagination.default_paginator import DefaultPaginator

from .filters import UserResourcesViewFilter
from .models import UserResourcesView
from .serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = UserResourcesView.objects.all().order_by('user__id')
    serializer_class = UserSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = UserResourcesViewFilter
    pagination_class = DefaultPaginator
