# Generated by Django 2.2.7 on 2020-05-07 17:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0043_mission_budget'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='image_at_home',
            field=models.ImageField(blank=True, null=True, upload_to='', verbose_name='홈 화면 이미지'),
        ),
    ]
