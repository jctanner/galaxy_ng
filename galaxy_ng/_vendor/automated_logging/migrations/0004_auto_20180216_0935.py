# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2018-02-16 09:35
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('automated_logging', '0003_auto_20180216_0900'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modelobject',
            name='type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='atl_modelobject_application', to='contenttypes.ContentType'),
        ),
    ]
