import django_filters
from .models import UserResourcesView


class UserResourcesViewFilter(django_filters.FilterSet):
    resource__ansible_id = django_filters.CharFilter(field_name='resource__ansible_id', lookup_expr='exact')

    class Meta:
        model = UserResourcesView
        fields = ['resource__ansible_id']
