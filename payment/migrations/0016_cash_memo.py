# Generated by Django 2.2.7 on 2020-07-20 13:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0015_auto_20200426_1959'),
    ]

    operations = [
        migrations.AddField(
            model_name='cash',
            name='memo',
            field=models.TextField(blank=True, default='', verbose_name='메모'),
        ),
    ]