# Generated by Django 2.2.7 on 2020-11-26 15:44

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('payment', '0021_auto_20201120_1251'),
    ]

    operations = [
        migrations.CreateModel(
            name='Billing',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('billkey', models.CharField(blank=True, default='', max_length=20, verbose_name='빌키')),
                ('ref_no', models.CharField(blank=True, default='', max_length=20, verbose_name='거래번호')),
                ('card_company_no', models.CharField(blank=True, default='', max_length=2, verbose_name='카드사코드')),
                ('card_name', models.CharField(blank=True, default='', max_length=20, verbose_name='카드명')),
                ('card_no', models.CharField(blank=True, default='', max_length=20, verbose_name='카드번호')),
                ('customer_name', models.CharField(blank=True, default='', max_length=16, verbose_name='고객명')),
                ('customer_tel_no', models.CharField(blank=True, default='', max_length=13, verbose_name='고객 연락처')),
                ('created_datetime', models.DateTimeField(auto_now_add=True, verbose_name='작성일시')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='billings', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
            options={
                'verbose_name': '빌링',
                'verbose_name_plural': '빌링',
            },
        ),
    ]
