# Generated by Django 2.2.7 on 2020-04-22 09:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0027_helper_is_at_home'),
    ]

    operations = [
        migrations.AddField(
            model_name='helper',
            name='is_online_acceptable',
            field=models.BooleanField(blank=True, default=True, verbose_name='온라인 미션 수행여부'),
        ),
    ]
