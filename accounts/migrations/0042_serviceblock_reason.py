# Generated by Django 2.2.7 on 2020-08-21 00:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0041_auto_20200818_1506'),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceblock',
            name='reason',
            field=models.TextField(blank=True, default='', verbose_name='사유'),
        ),
    ]
