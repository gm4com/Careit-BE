# Generated by Django 2.2.7 on 2021-08-27 17:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0080_auto_20210827_1729'),
    ]

    operations = [
        migrations.AlterField(
            model_name='missiontemplate',
            name='partnership',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='biz.Partnership', verbose_name='협력사 전용'),
        ),
    ]
