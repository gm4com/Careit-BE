# Generated by Django 2.2.7 on 2021-10-14 11:58

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('biz', '0011_auto_20211005_1430'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampaignUserData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, default='', max_length=32, verbose_name='유져 데이터 코드')),
                ('created_user_identifier', models.CharField(blank=True, default='', max_length=32, verbose_name='사용자 식별자')),
                ('device_info', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, verbose_name='기기정보')),
                ('app_info', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, verbose_name='앱정보')),
                ('answer', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, verbose_name='답변')),
                ('clicked_datetime', models.DateTimeField(blank=True, default=None, null=True, verbose_name='클릭 일시')),
                ('answered_datetime', models.DateTimeField(blank=True, default=None, null=True, verbose_name='전환 일시')),
                ('banner', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='data', to='biz.CampaignBanner', verbose_name='캠페인 배너')),
                ('created_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campaign_data', to=settings.AUTH_USER_MODEL, verbose_name='사용자')),
            ],
            options={
                'verbose_name': '캠페인 유져 데이터',
                'verbose_name_plural': '캠페인 유져 데이터',
            },
        ),
        migrations.CreateModel(
            name='CampaignUserDataFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attach', models.FileField(upload_to='', verbose_name='파일')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='biz.CampaignQuestion', verbose_name='캠페인 질문')),
                ('user_data', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='biz.CampaignUserData', verbose_name='유져 데이터')),
            ],
            options={
                'verbose_name': '유져 데이터 파일',
                'verbose_name_plural': '유져 데이터 파일',
            },
        ),
        migrations.RemoveField(
            model_name='campaignuserlog',
            name='banner',
        ),
        migrations.RemoveField(
            model_name='campaignuserlog',
            name='created_user',
        ),
        migrations.DeleteModel(
            name='CampaignUserAnswer',
        ),
        migrations.DeleteModel(
            name='CampaignUserLog',
        ),
    ]
