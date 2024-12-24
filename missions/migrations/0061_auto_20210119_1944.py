# Generated by Django 2.2.7 on 2021-01-19 19:44

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0060_auto_20210111_1738'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='template',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='missions', to='missions.MissionTemplate', verbose_name='템플릿'),
        ),
        migrations.AddField(
            model_name='mission',
            name='template_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=list, verbose_name='템플릿 데이터'),
        ),
    ]