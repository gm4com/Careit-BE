# Generated by Django 2.2.7 on 2020-03-09 14:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0004_notification_receiver_areas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='receiver_identifier',
            field=models.TextField(blank=True, default='', verbose_name='수신 식별자'),
        ),
    ]