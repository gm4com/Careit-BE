# Generated by Django 2.2.7 on 2021-04-22 21:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0029_payment_coupon'),
        ('notification', '0013_auto_20210311_0037'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketingTasker',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('condition', models.CharField(choices=[('joined', '회원가입시'), ('timeout_canceled', '미션 시간초과 취소시')], max_length=100, verbose_name='조건')),
                ('send_method', models.CharField(choices=[('push', 'Push'), ('sms', 'SMS'), ('email', 'Email')], max_length=5, verbose_name='메세지 타입')),
                ('content', models.TextField(verbose_name='메세지 내용')),
                ('is_active', models.BooleanField(blank=True, default=True, null=True, verbose_name='활성화')),
                ('auto_issue_coupon', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='taskers', to='payment.CouponTemplate', verbose_name='자동발급 쿠폰')),
            ],
            options={
                'verbose_name': '알림',
                'verbose_name_plural': '알림',
            },
        ),
    ]