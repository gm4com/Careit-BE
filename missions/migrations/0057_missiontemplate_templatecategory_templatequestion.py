# Generated by Django 2.2.7 on 2020-12-21 18:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0056_auto_20201204_1330'),
    ]

    operations = [
        migrations.CreateModel(
            name='TemplateQuestion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_type', models.CharField(choices=[('radio', '라디오 (1개 선택)'), ('checkbox', '체크박스 (다중 선택)'), ('number', '숫자 입력'), ('text', '단답형 문자'), ('textarea', '장문'), ('area', '지역'), ('address', '주소'), ('datetime', '날짜와 시간'), ('date', '날짜'), ('time', '시간'), ('customer_mobile', '고객 연락처'), ('', '')], max_length=20, verbose_name='유형')),
                ('name', models.CharField(max_length=250, verbose_name='항목 이름')),
                ('title', models.CharField(max_length=250, verbose_name='질문 제목')),
                ('description', models.TextField(verbose_name='질문 설명')),
                ('options', models.TextField(help_text='줄바꿈(엔터)으로 각 항목을 구분하세요. 각 항목에 대한 설명이 필요한 경우 ":"를 붙여서 작성하세요.', verbose_name='선택 항목')),
                ('has_etc_input', models.BooleanField(blank=True, default=False, verbose_name='직접입력(기타)')),
                ('is_required', models.BooleanField(blank=True, default=False, verbose_name='필수 입력 여부')),
            ],
            options={
                'verbose_name': '템플릿 질문',
                'verbose_name_plural': '템플릿 질문',
            },
        ),
        migrations.CreateModel(
            name='TemplateCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=250, verbose_name='카테고리명')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='missions.TemplateCategory', verbose_name='상위 카테고리')),
            ],
            options={
                'verbose_name': '템플릿 카테고리',
                'verbose_name_plural': '템플릿 카테고리',
            },
        ),
        migrations.CreateModel(
            name='MissionTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=250, verbose_name='템플릿 이름')),
                ('image', models.ImageField(blank=True, null=True, upload_to='', verbose_name='템플릿 이미지')),
                ('is_active', models.BooleanField(blank=True, default=True, verbose_name='활성화')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='templates', to='missions.TemplateCategory', verbose_name='템플릿 카테고리')),
                ('questions', models.ManyToManyField(to='missions.TemplateQuestion', verbose_name='질문')),
            ],
            options={
                'verbose_name': '템플릿',
                'verbose_name_plural': '템플릿',
            },
        ),
    ]
