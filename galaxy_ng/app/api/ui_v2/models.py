from django.db import models
from django.contrib.auth import get_user_model
from ansible_base.resource_registry.models import Resource

User = get_user_model()


class UserResourcesView(models.Model):

    user = models.ForeignKey(User, to_field='id', db_column='user_id', on_delete=models.DO_NOTHING, primary_key=True)
    resource = models.ForeignKey(Resource, to_field='id', db_column='resource_id', on_delete=models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'galaxy_dab_user_resources_view'
