# Generated by Django 2.2.7 on 2020-10-08 18:57

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('missions', '0053_missiontype_push_before_finish'),
    ]

    operations = [
        migrations.CreateModel(
            name='SafetyNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(max_length=12, verbose_name='번호')),
                ('assigned_number', models.CharField(max_length=12, verbose_name='안심번호')),
                ('assigned_datetime', models.DateTimeField(auto_now_add=True, verbose_name='할당 일시')),
                ('unassigned_datetime', models.DateTimeField(blank=True, default=None, null=True, verbose_name='할당해제 일시')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='safety_numbers', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
            options={
                'verbose_name': '안심번호',
                'verbose_name_plural': '안심번호',
            },
        ),
    ]
