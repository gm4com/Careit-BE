# Generated by Django 2.2.7 on 2020-12-14 18:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0023_billing_canceled_datetime'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='billing',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paid', to='payment.Billing', verbose_name='빌링'),
        ),
    ]
