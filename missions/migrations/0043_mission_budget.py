# Generated by Django 2.2.7 on 2020-04-30 18:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0042_auto_20200427_0942'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='budget',
            field=models.IntegerField(blank=True, default=0, verbose_name='예산'),
        ),
    ]
