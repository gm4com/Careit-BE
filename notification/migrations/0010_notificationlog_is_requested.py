# Generated by Django 2.2.7 on 2021-03-04 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0009_notificationlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationlog',
            name='is_requested',
            field=models.BooleanField(blank=True, default=False, verbose_name='실제 푸시요청 여부'),
        ),
    ]
