# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-10-04 07:58
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pinax_stripe', '0015_auto_20181004_0720'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='plan',
            name='name',
        ),
        migrations.RemoveField(
            model_name='plan',
            name='statement_descriptor',
        ),
        migrations.AddField(
            model_name='product',
            name='statement_descriptor',
            field=models.TextField(blank=True),
        ),
    ]