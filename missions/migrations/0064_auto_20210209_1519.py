# Generated by Django 2.2.7 on 2021-02-09 15:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0063_auto_20210119_2259'),
    ]

    operations = [
        migrations.AlterField(
            model_name='templatequestion',
            name='options',
            field=models.TextField(blank=True, help_text='줄바꿈(엔터)으로 각 항목을 구분하세요. 각 항목에 대한 설명이 필요한 경우 ":"를 붙여서 작성하세요.', verbose_name='선택 항목'),
        ),
    ]