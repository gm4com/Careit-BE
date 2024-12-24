# Generated by Django 2.2.7 on 2020-02-04 00:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0014_mission_bid_limit_datetime'),
    ]

    operations = [
        migrations.RenameField(
            model_name='bid',
            old_name='_due_datetime',
            new_name='due_datetime',
        ),
        migrations.AddField(
            model_name='bid',
            name='adjusted_due_datetime',
            field=models.DateTimeField(blank=True, null=True, verbose_name='미션 일시'),
        ),
        migrations.AddField(
            model_name='bid',
            name='content',
            field=models.TextField(blank=True, default='', verbose_name='고객에게 한마디'),
        ),
        migrations.AddField(
            model_name='report',
            name='mission',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='missions.Mission', verbose_name='미션'),
        ),
        migrations.AlterField(
            model_name='report',
            name='bid',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='missions.Bid', verbose_name='입찰'),
        ),
    ]
