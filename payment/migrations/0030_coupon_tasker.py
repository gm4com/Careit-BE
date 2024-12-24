# Generated by Django 2.2.7 on 2021-04-23 00:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0016_auto_20210423_0003'),
        ('payment', '0029_payment_coupon'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='tasker',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coupons', to='notification.MarketingTasker', verbose_name='태스커'),
        ),
    ]
