# Generated by Django 2.2.7 on 2020-10-13 17:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0054_safetynumber'),
    ]

    operations = [
        migrations.AddField(
            model_name='bid',
            name='customer_safety_number',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customer_safety_number', to='missions.SafetyNumber', verbose_name='고객 안심번호'),
        ),
        migrations.AddField(
            model_name='bid',
            name='helper_safety_number',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='helper_safety_number', to='missions.SafetyNumber', verbose_name='헬퍼 안심번호'),
        ),
        migrations.AlterField(
            model_name='safetynumber',
            name='assigned_datetime',
            field=models.DateTimeField(blank=True, default=None, null=True, verbose_name='할당 일시'),
        ),
    ]
