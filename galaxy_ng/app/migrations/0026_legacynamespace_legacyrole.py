# Generated by Django 3.2.12 on 2022-04-12 03:36

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('galaxy', '0025_add_content_guard_to_distributions'),
    ]

    operations = [
        migrations.CreateModel(
            name='LegacyNamespace',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=64, unique=True)),
                ('company', models.CharField(blank=True, max_length=64)),
                ('email', models.CharField(blank=True, max_length=256)),
                ('avatar_url', models.URLField(blank=True, max_length=256)),
                ('description', models.CharField(blank=True, max_length=256)),
                ('resources', models.TextField(blank=True)),
                ('owners', models.ManyToManyField(related_name='legacy_namespaces', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='LegacyRole',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=64)),
                ('full_metadata', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('metadata', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('namespace', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='roles', to='galaxy.legacynamespace')),
            ],
        ),
    ]
