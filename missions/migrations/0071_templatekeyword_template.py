# Generated by Django 2.2.7 on 2021-04-05 15:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0070_auto_20210401_1350'),
    ]

    operations = [
        migrations.AddField(
            model_name='templatekeyword',
            name='template',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='searched_keywords', to='missions.MissionTemplate', verbose_name='선택 템플릿'),
        ),
    ]
