# Generated by Django 4.2.13 on 2024-06-06 19:13

from django.db import migrations


def create_system_auditor_role(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    Permission = apps.get_model("auth", "Permission")

    # Create the role
    role, created = Role.objects.get_or_create(
        name='galaxy.auditor',
        defaults={'description': 'Role with read-only permissions to all resources'}
    )

    for permission in Permission.objects.filter(codename__icontains='view'):
        role.permissions.add(permission)


def delete_system_auditor_role(apps, schema_editor):
    Role = apps.get_model("core", "Role")

    try:
        role = Role.objects.get(name='galaxy.auditor')
    except Role.DoesNotExist:
        return

    # Delete the role
    role.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("galaxy", "0052_alter_organization_created_by_and_more"),
    ]

    operations = [
        migrations.RunPython(create_system_auditor_role, delete_system_auditor_role),
    ]
