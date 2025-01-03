# Generated by Django 2.2.7 on 2020-03-25 18:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_auto_20200325_1810'),
    ]

    operations = [
        migrations.AlterField(
            model_name='popup',
            name='location',
            field=models.CharField(choices=[('user', '고객 메인'), ('helper', '헬퍼 메인'), ('cs', '고객센터')], max_length=10, verbose_name='위치'),
        ),
        migrations.AlterField(
            model_name='popup',
            name='target_type',
            field=models.CharField(choices=[('view', '뷰'), ('link', '외부링크'), ('contact', '[게시물] 1:1문의'), ('partnership', '[게시물] 제휴/제안'), ('customer_notice', '[게시물] 공지(고객)'), ('helper_notice', '[게시물] 공지(헬퍼)'), ('customer_event', '[게시물] 이벤트(고객)'), ('helper_event', '[게시물] 이벤트(헬퍼)'), ('magazine', '[게시물] 매거진'), ('webtoon', '[게시물] 웹툰'), ('faq', '[게시물] FAQ')], max_length=15, verbose_name='타겟 타입'),
        ),
    ]
