from django.conf import settings
from django.urls import include, path
from rest_framework import routers

from galaxy_ng.app import constants


from ansible_base.rbac.urls import (
    api_version_urls as dab_rbac_urls,
)

print(dab_rbac_urls)

urlpatterns = [
]
# urlpatterns.append(include(dab_rbac_urls))
urlpatterns.extend(dab_rbac_urls)
