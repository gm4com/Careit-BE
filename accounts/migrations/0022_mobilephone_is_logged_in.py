# Generated by Django 2.2.7 on 2020-04-06 15:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0021_auto_20200325_1806'),
    ]

    operations = [
        migrations.AddField(
            model_name='mobilephone',
            name='is_logged_in',
            field=models.BooleanField(blank=True, default=True, verbose_name='로그인 상태에서 인증'),
        ),
    ]
