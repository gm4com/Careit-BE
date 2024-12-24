# Generated by Django 2.2.7 on 2020-02-18 02:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0006_auto_20200218_1100'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='payment',
            name='failed_datetime',
        ),
        migrations.AddField(
            model_name='payment',
            name='is_succeeded',
            field=models.BooleanField(blank=True, default=True, verbose_name='성공여부'),
        ),
    ]