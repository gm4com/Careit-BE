# Generated by Django 2.2.7 on 2020-04-29 14:37

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0031_auto_20200427_1553'),
    ]

    operations = [
        migrations.AddField(
            model_name='helper',
            name='licenses',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=50), blank=True, default=list, size=None, verbose_name='자격증'),
        ),
    ]
