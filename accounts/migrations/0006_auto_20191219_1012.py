# Generated by Django 2.2.7 on 2019-12-19 01:12

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_auto_20191219_0948'),
    ]

    operations = [
        migrations.AlterField(
            model_name='regular',
            name='rejected_fields',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=30), blank=True, default=list, size=None, verbose_name='거부 필드'),
        ),
    ]
