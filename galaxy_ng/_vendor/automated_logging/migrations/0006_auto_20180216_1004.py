# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2018-02-16 10:04
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('automated_logging', '0005_auto_20180216_0941'),
    ]

    operations = [
        migrations.AlterField(
            model_name='model',
            name='application',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='atl_model_application', to='automated_logging.Application'),
        ),
    ]
