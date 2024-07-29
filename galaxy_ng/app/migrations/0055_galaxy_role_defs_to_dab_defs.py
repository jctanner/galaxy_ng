from django.db import migrations

from awx.main.migrations._dab_rbac import migrate_to_new_rbac, create_permissions_as_operation, setup_managed_role_definitions


def copy_permissions_to_role_definitions(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    RoleDefinition = apps.get_model('dab_rbac', 'RoleDefinition')

    # TODO: migrate from pulp role model or something like that
    permissions = Permission.objects.all().filter(name__icontains='namespace')
    rd = RoleDefinition.objects.get_or_create(
        name='Namespace Admin',
        defaults=dict(
            content_type=permissions[0].content_type,
            managed=True
        )
    )
    for perm in permissions:
        rd.permissions.add(perm)



class Migration(migrations.Migration):

    dependencies = [
        ('galaxy', '0054_dab_resource_views'),
        ('dab_rbac', '__first__'),
    ]

    operations = [
        migrations.RunPython(create_permissions_as_operation, migrations.RunPython.noop),
        migrations.RunPython(copy_permissions_to_role_definitions),
    ]
