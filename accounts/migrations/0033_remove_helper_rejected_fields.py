# Generated by Django 2.2.7 on 2020-05-13 14:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0032_helper_licenses'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='helper',
            name='rejected_fields',
        ),
    ]