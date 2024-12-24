# Generated by Django 2.2.7 on 2020-12-08 11:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0044_auto_20201207_1459'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnership',
            name='reward_when_joined',
            field=models.PositiveIntegerField(blank=True, default=0, verbose_name='가입 리워드'),
        ),
        migrations.AddField(
            model_name='partnership',
            name='reward_when_mission_done',
            field=models.PositiveIntegerField(blank=True, default=0, verbose_name='미션완료 리워드'),
        ),
        migrations.AddField(
            model_name='partnership',
            name='reward_when_mission_done_count',
            field=models.PositiveSmallIntegerField(blank=True, default=0, help_text='0인 경우 계속 지급', verbose_name='미션완료 리워드 회수'),
        ),
    ]
