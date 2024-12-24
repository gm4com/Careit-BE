# Generated by Django 2.2.7 on 2021-10-05 14:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0058_auto_20210902_1807'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='recommended_partner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recommended_users', to='biz.Partnership', verbose_name='추천 협력사'),
        ),
        migrations.DeleteModel(
            name='Partnership',
        ),
    ]
