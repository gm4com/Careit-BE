# Generated by Django 2.2.7 on 2020-05-20 13:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0044_mission_image_at_home'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='review',
            unique_together=set(),
        ),
    ]
