# Generated by Django 2.2.7 on 2020-02-17 04:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0003_auto_20200217_1315'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='code',
            field=models.CharField(blank=True, default='', max_length=16, verbose_name='쿠폰 코드'),
        ),
    ]