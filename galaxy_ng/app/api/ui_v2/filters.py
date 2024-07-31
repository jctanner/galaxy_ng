import django_filters
from .models import UserResourcesView
from .models import OrganizationResourcesView
from .models import TeamResourcesView


class UserResourcesViewFilter(django_filters.FilterSet):
    resource__ansible_id = django_filters.CharFilter(
        field_name='resource__ansible_id',
        lookup_expr='exact'
    )

    class Meta:
        model = UserResourcesView
        fields = ['resource__ansible_id']


class OrganizationResourcesViewFilter(django_filters.FilterSet):
    resource__ansible_id = django_filters.CharFilter(
        field_name='resource__ansible_id',
        lookup_expr='exact'
    )

    class Meta:
        model = OrganizationResourcesView
        fields = ['resource__ansible_id']


class TeamResourcesViewFilter(django_filters.FilterSet):
    resource__ansible_id = django_filters.CharFilter(
        field_name='resource__ansible_id',
        lookup_expr='exact'
    )

    class Meta:
        model = TeamResourcesView
        fields = ['resource__ansible_id']
