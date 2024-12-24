# Generated by Django 2.2.7 on 2020-06-15 15:34

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0033_remove_helper_rejected_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='recommended_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='추천인'),
        ),
    ]