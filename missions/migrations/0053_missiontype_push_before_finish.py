# Generated by Django 2.2.7 on 2020-08-21 19:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0052_auto_20200722_1113'),
    ]

    operations = [
        migrations.AddField(
            model_name='missiontype',
            name='push_before_finish',
            field=models.PositiveSmallIntegerField(blank=True, default=0, verbose_name='마감 전 푸시알림 (분)'),
        ),
    ]
