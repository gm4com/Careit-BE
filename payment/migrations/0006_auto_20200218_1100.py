# Generated by Django 2.2.7 on 2020-02-18 02:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0005_coupontemplate_is_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='withdraw',
            name='cash',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='withdraw', to='payment.Cash', verbose_name='캐쉬'),
        ),
    ]
