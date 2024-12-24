# Generated by Django 2.2.7 on 2020-03-26 03:30

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0035_auto_20200325_0912'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('anyman_migration', '0003_auto_20200326_0016'),
    ]

    operations = [
        migrations.CreateModel(
            name='MissionAsIs',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('anycode', models.CharField(max_length=10, verbose_name='AnyCode')),
                ('mission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mission_anycode', to='missions.Mission', verbose_name='미션')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mission_user_h_uid', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
        ),
    ]