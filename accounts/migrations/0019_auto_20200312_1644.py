# Generated by Django 2.2.7 on 2020-03-12 16:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_tin'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='helper',
            name='is_helper_main',
        ),
        migrations.AddField(
            model_name='user',
            name='is_helper_main',
            field=models.BooleanField(blank=True, default=False, verbose_name='헬퍼 메인화면'),
        ),
    ]
