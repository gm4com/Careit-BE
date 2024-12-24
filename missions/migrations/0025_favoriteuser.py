# Generated by Django 2.2.7 on 2020-02-21 06:37

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('missions', '0024_remove_mission_warning'),
    ]

    operations = [
        migrations.CreateModel(
            name='FavoriteUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_datetime', models.DateTimeField(auto_now_add=True, verbose_name='찜 일시')),
                ('created_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='likes', to=settings.AUTH_USER_MODEL, verbose_name='작성자')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='liked_bys', to=settings.AUTH_USER_MODEL, verbose_name='찜된 회원')),
            ],
            options={
                'verbose_name': '사용자 찜',
                'verbose_name_plural': '사용자 찜',
            },
        ),
    ]