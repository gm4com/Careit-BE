# Generated by Django 2.2.7 on 2020-03-05 13:18

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_popup'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0018_tin'),
        ('missions', '0031_bidfile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bid',
            name='mission',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bids', to='missions.Mission', verbose_name='미션'),
        ),
        migrations.AlterField(
            model_name='mission',
            name='content',
            field=models.TextField(verbose_name='수행내용'),
        ),
        migrations.AlterField(
            model_name='mission',
            name='mission_type',
            field=models.ForeignKey(blank=True, default=1, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='missions', to='missions.MissionType', verbose_name='미션 타입'),
        ),
        migrations.CreateModel(
            name='MultiMission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, db_index=True, default='', max_length=8, verbose_name='미션코드')),
                ('title', models.CharField(max_length=250, verbose_name='미션 제목')),
                ('banner', models.ImageField(blank=True, null=True, upload_to='', verbose_name='미션 배너')),
                ('summary', models.TextField(verbose_name='수행내용 요약')),
                ('content', models.TextField(verbose_name='수행내용')),
                ('created_datetime', models.DateTimeField(auto_now_add=True, verbose_name='작성 일시')),
                ('requested_datetime', models.DateTimeField(blank=True, null=True, verbose_name='요청 일시')),
                ('is_active', models.BooleanField(blank=True, default=True, verbose_name='활성화')),
                ('mission_type', models.ForeignKey(blank=True, default=1, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='multi_missions', to='missions.MissionType', verbose_name='미션 타입')),
                ('request_helpers', models.ManyToManyField(blank=True, to='accounts.Helper', verbose_name='요청 헬퍼')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='multi_missions', to=settings.AUTH_USER_MODEL, verbose_name='담당자')),
            ],
            options={
                'verbose_name': '다중 미션',
                'verbose_name_plural': '다중 미션',
            },
        ),
        migrations.CreateModel(
            name='MultiAreaMission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('detail_1', models.CharField(max_length=100, verbose_name='상세 주소 1')),
                ('detail_2', models.CharField(blank=True, default='', max_length=100, verbose_name='상세 주소 2')),
                ('amount', models.IntegerField(blank=True, default=0, verbose_name='지급캐쉬')),
                ('customer_mobile', models.CharField(blank=True, default='', max_length=11, validators=[django.core.validators.RegexValidator('^01([0|1|6|7|8|9]?)([0-9]{3,4})([0-9]{4})$')], verbose_name='휴대폰 번호')),
                ('canceled_datetime', models.DateTimeField(blank=True, null=True, verbose_name='취소일시')),
                ('bid_closed_datetime', models.DateTimeField(blank=True, null=True, verbose_name='입찰종료일시')),
                ('area', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='base.Area', verbose_name='지역')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='children', to='missions.MultiMission', verbose_name='상위 미션')),
            ],
            options={
                'verbose_name': '다중지역 미션',
                'verbose_name_plural': '다중지역 미션',
            },
        ),
        migrations.AddField(
            model_name='bid',
            name='area_mission',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bids', to='missions.MultiAreaMission', verbose_name='지역미션'),
        ),
    ]
