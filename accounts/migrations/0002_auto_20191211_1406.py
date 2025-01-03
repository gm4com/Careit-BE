# Generated by Django 2.2.7 on 2019-12-11 05:06

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='문제')),
                ('answers', django.contrib.postgres.fields.jsonb.JSONField(verbose_name='답안')),
            ],
        ),
        migrations.RemoveField(
            model_name='user',
            name='push_allowed_level',
        ),
        migrations.AddField(
            model_name='helper',
            name='is_helper_main',
            field=models.BooleanField(blank=True, default=True, verbose_name='헬퍼 메인화면'),
        ),
        migrations.AddField(
            model_name='helper',
            name='is_nearby_push_allowed',
            field=models.BooleanField(blank=True, default=False, verbose_name='인근지역 푸시 허용'),
        ),
        migrations.AddField(
            model_name='helper',
            name='push_not_allowed_from',
            field=models.TimeField(blank=True, null=True, verbose_name='알람금지 시작'),
        ),
        migrations.AddField(
            model_name='helper',
            name='push_not_allowed_to',
            field=models.TimeField(blank=True, null=True, verbose_name='알람금지 종료'),
        ),
        migrations.AlterField(
            model_name='regular',
            name='helper',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regular_requests', to='accounts.Helper', verbose_name='헬퍼'),
        ),
    ]
