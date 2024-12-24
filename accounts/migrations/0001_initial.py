# Generated by Django 2.2.7 on 2019-12-10 02:01

from django.conf import settings
import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0011_update_proxy_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('created_datetime', models.DateTimeField(auto_now_add=True, verbose_name='Joined Datetime')),
                ('is_staff', models.BooleanField(default=False, verbose_name='Is Staff')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('code', models.CharField(max_length=5, unique=True, verbose_name='회원코드')),
                ('email', models.EmailField(blank=True, default='', max_length=100, verbose_name='이메일')),
                ('username', models.CharField(blank=True, default='', max_length=20, verbose_name='닉네임')),
                ('kakao_id', models.CharField(blank=True, default='', max_length=100, verbose_name='카카오 식별자')),
                ('naver_id', models.CharField(blank=True, default='', max_length=100, verbose_name='네이버 식별자')),
                ('date_of_birth', models.DateField(blank=True, null=True, verbose_name='생년월일')),
                ('gender', models.NullBooleanField(choices=[(False, '남자'), (True, '여자')], verbose_name='성별')),
                ('is_push_allowed', models.BooleanField(blank=True, default=True, null=True, verbose_name='푸시 허용')),
                ('push_token', models.CharField(blank=True, default='', max_length=200, verbose_name='Push 토큰')),
                ('push_allowed_level', models.PositiveSmallIntegerField(blank=True, default=1, verbose_name='푸시 허용 단계')),
                ('push_ringtone', models.CharField(blank=True, default='', max_length=20, verbose_name='푸시 알림음')),
                ('withdrew_datetime', models.DateTimeField(blank=True, null=True, verbose_name='탈퇴일시')),
                ('_is_blocked', models.BooleanField(blank=True, default=False, null=True, verbose_name='블록')),
            ],
            options={
                'verbose_name': 'User',
                'verbose_name_plural': 'Users',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Agreement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='제목')),
                ('content', models.TextField(verbose_name='내용')),
                ('is_required', models.BooleanField(blank=True, default=False, verbose_name='필수여부')),
            ],
            options={
                'verbose_name': '약관',
                'verbose_name_plural': '약관',
            },
        ),
        migrations.CreateModel(
            name='Area',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=10, verbose_name='지역명')),
                ('nearby', models.ManyToManyField(blank=True, related_name='_area_nearby_+', to='accounts.Area', verbose_name='인근 지역')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='accounts.Area', verbose_name='상위 지역')),
            ],
            options={
                'verbose_name': '지역',
                'verbose_name_plural': '지역',
            },
        ),
        migrations.CreateModel(
            name='Helper',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('profile_photo', models.ImageField(blank=True, null=True, upload_to='', verbose_name='프로필 사진')),
                ('introduction', models.TextField(blank=True, null=True, verbose_name='소개글')),
                ('services', models.TextField(blank=True, null=True, verbose_name='제공 서비스')),
                ('level', models.PositiveSmallIntegerField(blank=True, default=5, verbose_name='헬퍼 등급')),
                ('details', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, verbose_name='추가질문')),
                ('has_crime_report', models.BooleanField(blank=True, default=False, null=True, verbose_name='범죄기록유무')),
                ('requested_datetime', models.DateTimeField(auto_now_add=True, verbose_name='헬퍼 신청일시')),
                ('is_regular', models.NullBooleanField(default=None, verbose_name='정식헬퍼')),
                ('accept_area', models.ManyToManyField(related_name='helpers', to='accounts.Area', verbose_name='수행지역')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='helper', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
            options={
                'verbose_name': '헬퍼',
                'verbose_name_plural': '헬퍼',
            },
        ),
        migrations.CreateModel(
            name='MobilePhone',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, default='', max_length=11, validators=[django.core.validators.RegexValidator('^01([0|1|6|7|8|9]?)([0-9]{3,4})([0-9]{4})$')], verbose_name='휴대폰 번호')),
                ('verified_datetime', models.DateTimeField(blank=True, null=True, verbose_name='휴대폰 인증/인증해제 일시')),
                ('is_active', models.BooleanField(blank=True, default=True, verbose_name='유효성')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mobiles', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
            options={
                'verbose_name': '휴대폰',
                'verbose_name_plural': '휴대폰',
            },
        ),
        migrations.CreateModel(
            name='UserLoginAttempt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.CharField(blank=True, default='', max_length=100, verbose_name='User ID')),
                ('device_info', django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name='Device Info')),
                ('app_info', django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name='App Info')),
                ('result', models.SmallIntegerField(choices=[(0, 'Success'), (1, 'Not exist'), (2, 'Not match'), (9, 'Attempt count exceeded'), (-1, 'Attempt count reset')], verbose_name='Result')),
                ('attempted_datetime', models.DateTimeField(auto_now_add=True, verbose_name='Attempted Datetime')),
            ],
            options={
                'verbose_name': 'User Login Attempt',
                'verbose_name_plural': 'User Login Attempts',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Regular',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_photo', models.ImageField(blank=True, null=True, upload_to='', verbose_name='신분증 사진')),
                ('id_person_photo', models.ImageField(blank=True, null=True, upload_to='', verbose_name='신분증과 함께 찍은 사진')),
                ('name', models.CharField(max_length=20, verbose_name='이름')),
                ('address_detail', models.CharField(blank=True, max_length=100, null=True, verbose_name='주소 상세')),
                ('requested_datetime', models.DateTimeField(auto_now_add=True, verbose_name='정식헬퍼 신청일시')),
                ('accepted_datetime', models.DateTimeField(blank=True, null=True, verbose_name='정식헬퍼 승인일시')),
                ('rejected_datetime', models.DateTimeField(blank=True, null=True, verbose_name='정식헬퍼 거부일시')),
                ('rejected_fields', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=30), blank=True, size=None, verbose_name='거부 필드')),
                ('rejected_reason', models.TextField(blank=True, verbose_name='거부 이유')),
                ('address_area', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='address_helpers', to='accounts.Area', verbose_name='주소 지역')),
                ('helper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regular_requests', to='accounts.Helper', verbose_name='정식헬퍼 신청')),
            ],
            options={
                'verbose_name': '정식헬퍼 신청',
                'verbose_name_plural': '정식헬퍼 신청',
            },
        ),
        migrations.CreateModel(
            name='MobilePhoneVerification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=6, verbose_name='인증코드')),
                ('created_datetime', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('mobile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='verifications', to='accounts.MobilePhone', verbose_name='휴대폰')),
            ],
            options={
                'verbose_name': '휴대폰 인증',
                'verbose_name_plural': '휴대폰 인증',
            },
        ),
        migrations.CreateModel(
            name='Block',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(verbose_name='블록사유')),
                ('block_start_datetime', models.DateTimeField(auto_now_add=True, verbose_name='블록 시작일시')),
                ('block_end_datetime', models.DateTimeField(blank=True, null=True, verbose_name='블록 종료일시')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
            options={
                'verbose_name': '블록',
                'verbose_name_plural': '블록',
            },
        ),
        migrations.CreateModel(
            name='BankAccount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.PositiveSmallIntegerField(blank=True, choices=[(2, 'KDB산업은행'), (3, 'IBK기업은행'), (4, '국민은행'), (5, '외환은행'), (7, '수협중앙회'), (11, '농협(중앙회)'), (12, '농협(단위농협)'), (20, '우리은행'), (23, 'SC제일은행'), (27, '한국씨티은행'), (31, '대구은행'), (32, '부산은행'), (34, '광주은행'), (35, '제주은행'), (37, '전북은행'), (39, '경남은행'), (81, 'KEB하나은행'), (88, '신한은행'), (45, '새마을금고'), (48, '신협중앙회'), (50, '상호저축은행'), (54, 'HSBC은행'), (55, '도이치은행'), (89, '케이뱅크'), (90, '카카오뱅크')], null=True, verbose_name='출금계좌 은행')),
                ('number', models.CharField(blank=True, max_length=15, null=True, verbose_name='출금계좌 번호')),
                ('name', models.CharField(blank=True, max_length=20, null=True, verbose_name='출금계좌 예금주')),
                ('created_datetime', models.DateTimeField(blank=True, null=True, verbose_name='등록일시')),
                ('helper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_accounts', to='accounts.Helper', verbose_name='헬퍼')),
            ],
            options={
                'verbose_name': '은행 계좌',
                'verbose_name_plural': '은행 계좌',
            },
        ),
        migrations.AddField(
            model_name='user',
            name='agreed_documents',
            field=models.ManyToManyField(blank=True, related_name='users', to='accounts.Agreement', verbose_name='동의문서'),
        ),
        migrations.AddField(
            model_name='user',
            name='groups',
            field=models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.Group', verbose_name='groups'),
        ),
        migrations.AddField(
            model_name='user',
            name='user_permissions',
            field=models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.Permission', verbose_name='user permissions'),
        ),
    ]