# Generated by Django 2.2.7 on 2020-02-18 04:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0021_auto_20200217_1033'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mission',
            name='code',
            field=models.CharField(blank=True, db_index=True, default='', max_length=8, verbose_name='미션코드'),
        ),
    ]
