# Generated by Django 2.2.7 on 2020-01-29 21:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0013_missiontype_bidding_limit'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='bid_limit_datetime',
            field=models.DateTimeField(blank=True, null=True, verbose_name='입찰제한일시'),
        ),
    ]
