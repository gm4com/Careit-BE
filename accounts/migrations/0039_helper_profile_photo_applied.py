# Generated by Django 2.2.7 on 2020-08-18 10:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0038_auto_20200716_1543'),
    ]

    operations = [
        migrations.AddField(
            model_name='helper',
            name='profile_photo_applied',
            field=models.ImageField(blank=True, null=True, upload_to='', verbose_name='신청된 프로필 사진'),
        ),
    ]
