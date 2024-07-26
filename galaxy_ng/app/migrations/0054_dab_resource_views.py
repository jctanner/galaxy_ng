from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('galaxy', '0053_wait_for_dab_rbac'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE VIEW galaxy_dab_user_resources_view AS
            SELECT
                u.id AS user_id,
                r.id AS resource_id
            FROM galaxy_user u
            LEFT JOIN dab_resource_registry_resource r ON r.object_id = u.id::text
            WHERE r.content_type_id = (SELECT id FROM django_content_type WHERE model = 'user');
            """,
            reverse_sql="DROP VIEW IF EXISTS galaxy_dab_user_resources_view;"
        ),
    ]
