# Generated by Django 2.2.7 on 2019-12-31 00:22

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0002_auto_20191231_0922'),
    ]

    operations = [
        migrations.AlterField(
            model_name='missiontype',
            name='product_fields',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, verbose_name='상품 필드'),
        ),
    ]
