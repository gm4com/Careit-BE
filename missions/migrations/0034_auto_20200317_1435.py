# Generated by Django 2.2.7 on 2020-03-17 14:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0006_auto_20200313_1826'),
        ('missions', '0033_auto_20200307_1724'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='push_result',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='mission', to='notification.Notification', verbose_name='푸쉬 결과'),
        ),
        migrations.AddField(
            model_name='multiareamission',
            name='push_result',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='area_mission', to='notification.Notification', verbose_name='푸쉬 결과'),
        ),
    ]
