# Generated by Django 2.2.7 on 2021-08-03 12:30

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Partnership',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30, verbose_name='협력사명')),
                ('code', models.CharField(db_index=True, max_length=5, unique=True, verbose_name='협력사코드')),
                ('reward_when_joined', models.PositiveIntegerField(blank=True, default=0, verbose_name='가입 리워드')),
                ('reward_when_mission_done', models.PositiveIntegerField(blank=True, default=0, verbose_name='미션완료 리워드')),
                ('reward_when_mission_done_count', models.PositiveSmallIntegerField(blank=True, default=0, help_text='0인 경우 계속 지급', verbose_name='미션완료 리워드 회수')),
                ('active', models.BooleanField(default=True, verbose_name='파트너쉽 상태')),
                ('biz_code', models.CharField(max_length=10, verbose_name='사업자번호')),
                ('biz_tell', models.CharField(max_length=16, verbose_name='대표 전화번호')),
                ('biz_address_detail_1', models.CharField(blank=True, max_length=100, null=True, verbose_name='주소 상세 1')),
                ('biz_address_detail_2', models.CharField(blank=True, max_length=100, null=True, verbose_name='주소 상세 2')),
            ],
            options={
                'verbose_name': '협력사',
                'verbose_name_plural': '협력사',
            },
        ),
        migrations.CreateModel(
            name='PartnershipUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.IntegerField(choices=[(0, '매니저')], default=0)),
                ('partner_ship', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='partner_ship_user', to='biz.Partnership', verbose_name='파트너쉽')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='biz_partnershipUser', to=settings.AUTH_USER_MODEL, verbose_name='사용자')),
            ],
            options={
                'verbose_name': '협력사 유저',
                'verbose_name_plural': '협력사 유저',
            },
        ),
    ]
