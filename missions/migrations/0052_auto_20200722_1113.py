# Generated by Django 2.2.7 on 2020-07-22 11:13

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0051_auto_20200718_1118'),
    ]

    operations = [
        migrations.AlterField(
            model_name='review',
            name='_received_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='received_all_reviews', to=settings.AUTH_USER_MODEL, verbose_name='수신자'),
        ),
        migrations.AlterField(
            model_name='review',
            name='created_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_all_reviews', to=settings.AUTH_USER_MODEL, verbose_name='작성자'),
        ),
    ]