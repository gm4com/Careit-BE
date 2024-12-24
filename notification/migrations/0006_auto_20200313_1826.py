# Generated by Django 2.2.7 on 2020-03-13 18:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0005_auto_20200309_1459'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='send_method',
            field=models.CharField(choices=[('push', 'Push'), ('sms', 'SMS'), ('email', 'Email')], max_length=5, verbose_name='메세지 타입'),
        ),
    ]
