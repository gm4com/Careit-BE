# Generated by Django 2.2.7 on 2020-03-03 09:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0012_auto_20200302_1745'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reward',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reward_type', models.CharField(choices=[('helper_created_review', '[헬퍼] 리뷰작성'), ('customer_created_review', '[고객] 리뷰작성'), ('customer_finished_mission', '[고객] 미션완료')], max_length=30, verbose_name='리워드 종류')),
                ('amount_or_rate', models.PositiveSmallIntegerField(help_text='100 미만으로 입력시 비율(%)로 계산합니다.', verbose_name='금액 또는 비율')),
                ('start_date', models.DateField(blank=True, null=True, verbose_name='시작일')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='종료일')),
                ('created_datetime', models.DateTimeField(auto_now_add=True, verbose_name='작성일시')),
            ],
            options={
                'verbose_name': '리워드',
                'verbose_name_plural': '리워드',
            },
        ),
    ]
