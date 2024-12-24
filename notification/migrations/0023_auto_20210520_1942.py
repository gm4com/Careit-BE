# Generated by Django 2.2.7 on 2021-05-20 19:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0022_auto_20210504_1919'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marketingtasker',
            name='email_content',
            field=models.TextField(blank=True, help_text='다음 항목을 사용할 수 있습니다: {code}, {mobile}, {email}, {username}, {state}, {coupon_name} (쿠폰 만료 조건시), {coupon_expire} (쿠폰 만료 조건시)', verbose_name='이메일 내용'),
        ),
        migrations.AlterField(
            model_name='marketingtasker',
            name='email_title',
            field=models.CharField(blank=True, help_text='다음 항목을 사용할 수 있습니다: {code}, {mobile}, {email}, {username}, {state}, {coupon_name} (쿠폰 만료 조건시), {coupon_expire} (쿠폰 만료 조건시)', max_length=100, verbose_name='이메일 제목'),
        ),
        migrations.AlterField(
            model_name='marketingtasker',
            name='push_content',
            field=models.TextField(blank=True, help_text='다음 항목을 사용할 수 있습니다: {code}, {mobile}, {email}, {username}, {state}, {coupon_name} (쿠폰 만료 조건시), {coupon_expire} (쿠폰 만료 조건시)', verbose_name='푸시 내용'),
        ),
        migrations.AlterField(
            model_name='marketingtasker',
            name='push_title',
            field=models.CharField(blank=True, help_text='다음 항목을 사용할 수 있습니다: {code}, {mobile}, {email}, {username}, {state}, {coupon_name} (쿠폰 만료 조건시), {coupon_expire} (쿠폰 만료 조건시)', max_length=100, verbose_name='푸시 제목'),
        ),
        migrations.AlterField(
            model_name='marketingtasker',
            name='sms_content',
            field=models.TextField(blank=True, help_text='다음 항목을 사용할 수 있습니다: {code}, {mobile}, {email}, {username}, {state}, {coupon_name} (쿠폰 만료 조건시), {coupon_expire} (쿠폰 만료 조건시)', verbose_name='SMS 내용'),
        ),
    ]
