# Generated by Django 2.2.7 on 2020-11-02 15:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0019_auto_20201101_1613'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reward',
            name='reward_type',
            field=models.CharField(choices=[('helper_created_review', '[헬퍼] 리뷰작성'), ('customer_created_review', '[고객] 리뷰작성'), ('customer_finished_mission', '[고객] 미션완료'), ('customer_joined_by_recommend', '[고객] 가입시 추천인 입력'), ('helper_recommend_done_first', '[헬퍼] 추천에 의해 가입한 회원이 첫 미션완료'), ('customer_recommend_done_first', '[고객] 추천에 의해 가입한 회원이 첫 미션완료'), ('helper_recommend_done', '[헬퍼] 추천에 의해 가입한 회원이 미션완료'), ('customer_recommend_done', '[고객] 추천에 의해 가입한 회원이 미션완료')], max_length=30, verbose_name='리워드 종류'),
        ),
    ]
