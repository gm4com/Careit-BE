# Generated by Django 2.2.7 on 2020-03-11 16:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0003_auto_20200311_1451'),
    ]

    operations = [
        migrations.AddField(
            model_name='writing',
            name='subtitle',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='부제목'),
        ),
    ]