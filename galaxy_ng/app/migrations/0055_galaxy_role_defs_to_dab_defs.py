from django.db import migrations


def copy_permissions_to_role_definitions(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    RoleDefinition = apps.get_model('ansible_base.rbac', 'RoleDefinition')

    permissions = Permission.objects.all().filter(name__icontains='namespace')
    for perm in permissions:
        RoleDefinition.objects.create(
            name=perm.name,
            permissions=[perm.codename],
            content_type=perm.content_type
        )


class Migration(migrations.Migration):

    dependencies = [
        ('galaxy', '0054_dab_resource_views'),
    ]

    operations = [
        # migrations.RunPython(copy_permissions_to_role_definitions),
    ]
