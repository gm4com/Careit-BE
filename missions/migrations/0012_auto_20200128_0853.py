# Generated by Django 2.2.7 on 2020-01-27 23:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0011_auto_20200122_1436'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='code',
            field=models.CharField(blank=True, default='', max_length=8, verbose_name='미션코드'),
        ),
        migrations.AddField(
            model_name='missiontype',
            name='code',
            field=models.CharField(blank=True, default='', max_length=2, verbose_name='타입 코드'),
        ),
    ]