# Generated by Django 2.2.7 on 2021-09-23 17:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0085_auto_20210907_1449'),
    ]

    operations = [
        migrations.AddField(
            model_name='missiontemplate',
            name='matching_success_url',
            field=models.URLField(blank=True, default='', verbose_name='헬퍼 매칭 성공시 호출 URL'),
        ),
    ]
