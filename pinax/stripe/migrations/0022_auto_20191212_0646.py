# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-12-12 06:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pinax_stripe', '0021_usagerecord'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscriptionitem',
            name='quantity',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]