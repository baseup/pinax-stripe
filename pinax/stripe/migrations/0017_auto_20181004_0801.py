# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-10-04 08:01
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pinax_stripe', '0016_auto_20181004_0758'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plan',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plan_products', related_query_name='plan_product', to='pinax_stripe.Product'),
        ),
    ]
