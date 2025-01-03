# Generated by Django 2.2.7 on 2021-06-08 17:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0026_auto_20210525_2005'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketingtasker',
            name='kakao_content',
            field=models.TextField(blank=True, help_text='다음 항목을 사용할 수 있습니다: {code}, {mobile}, {email}, {username}, {state}, {coupon_name} (쿠폰 만료 조건시), {coupon_expire} (쿠폰 만료 조건시)', verbose_name='카카오 알림톡 내용'),
        ),
        migrations.AddField(
            model_name='marketingtasker',
            name='kakao_template_code',
            field=models.CharField(blank=True, max_length=30, verbose_name='카카오 알림톡 템플릿 코드'),
        ),
    ]
