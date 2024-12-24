import statistics
import itertools
import json
import os

from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField, JSONField
from django.utils import timezone
from django.apps import apps
from django.utils.functional import cached_property
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

from common.utils import stars
from common.models import DefaultEmailUserModel, BaseUserLoginAttemptModel
from common.validators import MobileNumberOnlyValidators
from common.admin import log_with_reason
from base.models import Area, BannedWord
from base.constants import *


from biz.models import Partnership


"""
querysets
"""


class LoggedInDeviceQuerySet(models.QuerySet):
    """
    로그인 기기 쿼리셋
    """
    def get_logged_in(self):
        return self.filter(logged_out_datetime__isnull=True)

    def get_helpers(self):
        return self.filter(user__helper__accepted_datetime__isnull=False, user__helper__is_active=True)

    def get_by_areas(self, *area_ids):
        parent_ids = list(Area.objects.filter(
            id__in=area_ids,
            parent__isnull=False
        ).distinct('parent').values_list('parent', flat=True))
        qs = self.get_logged_in().get_helpers()
        qs = qs.filter(
            models.Q(user__helper__accept_area__in=set(list(area_ids) + parent_ids))
            | models.Q(user__helper__accept_area__nearby__in=area_ids, user__helper__is_nearby_push_allowed=True)
        )
        return qs

    def get_by_tokens(self, tokens):
        return self.filter(push_token__in=tokens)

    def get_mission_push_allowed_helpers(self):
        now_time = timezone.now().time()
        qs = self.exclude(user__is_push_allowed=False)
        qs = qs.exclude(user__helper__is_mission_request_push_allowed=False)
        qs = qs.exclude(
            models.Q(
                models.Q(user__helper__push_allowed_from__lt=models.F('user__helper__push_allowed_to'))
                & ~models.Q(
                    models.Q(user__helper__push_allowed_from__lt=now_time)
                    & models.Q(user__helper__push_allowed_to__gt=now_time)
                )
            )
            | models.Q(
                models.Q(user__helper__push_allowed_from__gt=models.F('user__helper__push_allowed_to'))
                & models.Q(user__helper__push_allowed_from__gt=now_time)
                & models.Q(user__helper__push_allowed_to__lt=now_time)
            )
        )
        return qs

    def get_online_available(self):
        return self.filter(user__helper__is_online_acceptable=True)


class ServiceBlockQuerySet(models.QuerySet):
    """
    서비스 블록 쿼리셋
    """
    def get_current_blocked(self):
        return self.exclude(end_datetime__lt=timezone.now())

    def get_mobiles(self):
        return self.values_list('user__mobile', flat=True)


"""
managers
"""


class UserManager(models.Manager):
    """사용자 매니져"""
    def get_queryset(self):
        return super(UserManager, self).get_queryset().select_related('helper')

    def get_active_helper_users(self):
        return self.get_queryset().filter(
            is_active=True, _is_service_blocked=False, withdrew_datetime__isnull=True,
            helper__accepted_datetime__isnull=False, helper__is_active=True
        )


class UserQuerySet(models.QuerySet):
    """사용자 쿼리셋"""

    def get_active_users(self):
        return self.filter(is_active=True, _is_service_blocked=False, withdrew_datetime__isnull=True)

    def get_active_helpers(self):
        return self.get_active_users().filter(helper__is_active=True, helper__accepted_datetime__isnull=False)

    def get_push_tokens(self, only_if_allowed=True):
        users = self
        if only_if_allowed:
            users = users.filter(is_push_allowed=True)
        Device = apps.get_model('accounts', 'LoggedInDevice')
        devices = Device.objects.get_logged_in().filter(user_id__in=users.values_list('id', flat=True)).exclude(push_token='')
        return [device.push_token for device in devices]

    def get_code_and_push_tokens(self, only_if_allowed=True, is_mission_request=False, return_count=False):
        users = self
        if only_if_allowed:
            users = users.filter(is_push_allowed=True)
        Device = apps.get_model('accounts', 'LoggedInDevice')
        devices = Device.objects.get_logged_in().filter(user_id__in=users.values_list('id', flat=True)).exclude(push_token='')
        if is_mission_request:
            devices = devices.get_mission_push_allowed_helpers()
        if return_count:
            return devices.count()
        return [(device.user.code, device.push_token) for device in devices.distinct('push_token')]

    def get_by_helper_areas(self, *area_ids):
        parent_ids = list(Area.objects.filter(
            id__in=area_ids,
            parent__isnull=False
        ).distinct('parent').values_list('parent', flat=True))
        return self.get_active_helpers().filter(
            models.Q(helper__accept_area__in=set(list(area_ids) + parent_ids))
            | models.Q(helper__accept_area__nearby__in=area_ids, helper__is_nearby_push_allowed=True)
        ).distinct('id')

    def get_push_allowed(self):
        return self.filter(is_push_allowed=True)

    def get_recent_not_using(self, dt):
        return self.filter(
            created_datetime__lt=dt
        ).filter(
            models.Q(last_login__isnull=True)
            | models.Q(last_login__lt=dt)
        ).exclude(
            password=''
        )  # 이케아 자동가입 제외

    def get_recent_joined(self, days=3):
        return self.filter(created_datetime__gte=timezone.now() - timezone.timedelta(days=days))

    def get_joined_before(self, days=3):
        d = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_datetime__year=d.year, created_datetime__month=d.month, created_datetime__day=d.day)

    def get_not_used(self):
        return self.exclude(missions__saved_state='done')

    def get_online_helpers(self):
        return self.filter(helper__is_active=True).filter(helper__is_online_acceptable=True) \
            .filter(helper__accepted_datetime__isnull=False).distinct('id')

    def get_used(self):
        return self.filter(missions__saved_state='done').distinct('id')

    def get_external_mission_user(self, mobile, external_code='WEB', username='', partnership=None):
        user = self.filter(mobile=mobile).last()
        if not user:
            user = self.create(mobile=mobile, _recommended_by=external_code, username=username)
            if partnership:
                user.recommended_partner = partnership
                user.save()
        return user

    def get_in_action_users(self):
        return self.filter(
            models.Q(missions__saved_state='in_action')
            | models.Q(helper__bids__saved_state='in_action')
        ).distinct('id')

    def get_in_action_customers(self):
        return self.filter(missions__saved_state='in_action').distinct('id')

    def get_in_action_helpers(self):
        return self.filter(helper__bids__saved_state='in_action').distinct('id')


class HelperManager(models.Manager):
    """헬퍼 매니져"""
    def get_queryset(self):
        return super(HelperManager, self).get_queryset().select_related('user').prefetch_related('accept_area')

    def get_active_helpers(self):
        return self.get_queryset().filter(
            accepted_datetime__isnull=False, is_active=True,
            user__is_active=True, user___is_service_blocked=False, user__withdrew_datetime__isnull=True
        )

    # def get_by_areas(self, *area_ids):
    #     qs = self.get_queryset().filter(
    #         models.Q(accept_area__in=area_ids)
    #         | models.Q(accept_area__nearby__in=area_ids, is_nearby_push_allowed=True)
    #     )
    #     return qs


"""
models
"""


class State(models.Model):
    """
    상태 모델
    """
    STATE_TYPES = (
        ('user', '회원'),
        ('mission', '미션'),
    )
    code = models.CharField('상태코드', max_length=20, unique=True)
    state_type = models.CharField('상태타입', max_length=10, choices=STATE_TYPES)
    name = models.CharField('상태 표시명', max_length=20)

    class Meta:
        verbose_name = '상태'
        verbose_name_plural = '상태'

    def __str__(self):
        return self.code


class Agreement(models.Model):
    """
    약관 모델
    """
    title = models.CharField('제목', max_length=200)
    page_code = models.CharField('페이지코드', max_length=20, default='')
    content = models.TextField('내용')
    is_required = models.BooleanField('필수여부', blank=True, default=False)

    class Meta:
        verbose_name = '약관'
        verbose_name_plural = '약관'

    def __str__(self):
        return self.title


class UserLoginAttempt(BaseUserLoginAttemptModel):
    """
    로그인 시도
    """
    pass


class MobileVerificationQuerySet(models.QuerySet):
    """
    휴대폰 인증 모델 쿼리셋
    """
    def get_verified_recently(self, id, mobile='', minutes=30):
        qs = self.filter(id=id, verified_datetime__gte=timezone.now() - timezone.timedelta(minutes=minutes))
        if mobile:
            qs = qs.filter(number=mobile)
        if qs.exists():
            return qs.last()
        return None

    def create_by_nice(self, data):
        number = data.pop('MOBILE_NO')
        if not number:
            return None
        if 'CI' not in data or not data['CI']:
            return False

        user = User.objects.get_active_users().filter(ci=data['CI']).last()

        now = timezone.now()
        return self.create(number=number, code='', verified_datetime=now, nice_data=data), user


class MobileVerification(models.Model):
    """
    회원 휴대폰 인증 모델
    """
    number = models.CharField('휴대폰 번호', validators=MobileNumberOnlyValidators, max_length=11, blank=True, default='')
    code = models.CharField('인증코드', max_length=6)
    created_datetime = models.DateTimeField('생성일시', auto_now_add=True)
    verified_datetime = models.DateTimeField('휴대폰 인증 일시', null=True, blank=True)
    user = models.ForeignKey('accounts.User', verbose_name='회원', related_name='verifications',
                             on_delete=models.CASCADE, null=True, blank=True)
    nice_data = JSONField('나이스 본인인증 정보', blank=True, default=dict)
    objects = MobileVerificationQuerySet.as_manager()

    class Meta:
        verbose_name = '휴대폰 인증'
        verbose_name_plural = '휴대폰 인증'

    def __str__(self):
        return self.number

    def verify(self, code):
        if self.created_datetime < timezone.now() - timezone.timedelta(minutes=30):
            return None  # 시간초과
        if self.code == code:
            self.verified_datetime = timezone.now()
            self.save()
            return True
        return False

    def verifiy_user_ci(self, user, deactivate_same_number=False):
        try:
            # 인증 정보를 회원 모델에 저장
            self.user = user
            self.user.mobile = self.number
            self.user.ci = self.nice_data.pop('CI')
            self.user.date_of_birth = timezone.datetime.strptime(self.nice_data.pop('BIRTHDATE'), '%Y%m%d').date()
            self.user.gender = bool(self.nice_data.pop('GENDER') == '0')
            self.user.save()
            self.save()

            # 같은 휴대폰 번호를 가진 기존 회원 무력화
            if deactivate_same_number:
                others = User.objects.filter(mobile=self.user.mobile).exclude(id=self.user.id)
                others.update(mobile=':%s:' % self.number)
        except:
            return False

        return True


class User(DefaultEmailUserModel):
    """
    회원 모델
    """
    code = models.CharField('회원코드', max_length=5, unique=True, db_index=True)
    ci = models.CharField('CI', max_length=90, blank=True, default='')
    # mobile = models.CharField('휴대폰 번호', max_length=14, unique=True)
    mobile = models.CharField('휴대폰 번호', max_length=14, blank=True, default='')
    email = models.EmailField('이메일', max_length=100, blank=True, default='')
    username = models.CharField('닉네임', blank=True, default='', max_length=20)
    agreed_documents = models.ManyToManyField(Agreement, verbose_name='동의문서', related_name='users', blank=True)
    date_of_birth = models.DateField('생년월일', null=True, blank=True)
    gender = models.NullBooleanField('성별', choices=GENDERS, null=True, blank=True)
    _auth_center = models.CharField('인증센터', max_length=50, null=True, blank=True)
    recommended_user = models.ForeignKey('self', verbose_name='추천인', blank=True, null=True, on_delete=models.SET_NULL,
                                         related_name='recommended')
    recommended_partner = models.ForeignKey(Partnership, verbose_name='추천 협력사', blank=True, null=True,
                                            related_name='recommended_users', on_delete=models.SET_NULL)
    _recommended_by = models.CharField('추천인 코드', max_length=20, blank=True, default='')
    _legacy_recommended = models.CharField('구버젼 추천인 코드', max_length=5, blank=True, default='')
    is_helper_main = models.BooleanField('헬퍼 메인화면', blank=True, default=False)
    is_push_allowed = models.BooleanField('푸시 허용', null=True, blank=True, default=True)
    is_ad_allowed = models.BooleanField('마케팅 정보 허용', null=True, blank=True, default=True)
    withdrew_datetime = models.DateTimeField('탈퇴일시', null=True, blank=True)
    _is_service_blocked = models.BooleanField('서비스 블록', null=True, blank=True, default=False)
    level = models.PositiveSmallIntegerField('고객 등급', blank=True, default=1)

    USERNAME_FIELD = 'id'
    LOGIN_ATTEMPT_MODEL = UserLoginAttempt

    objects = UserQuerySet.as_manager()

    def __str__(self):
        return '[U%s] %s' % (self.code, self.username)

    def clean(self):
        if not BannedWord.objects.check_username(self.username):
            raise ValidationError('허용되지 않은 닉네임', 'username')
        return super(User, self).clean()

    def save(self, *args, **kwargs):
        self.clean()
        if not self.recommended_user and not self.recommended_partner and self._recommended_by:
            self.recommended_partner = Partnership.objects.filter(code=self._recommended_by.lower()).last()
            if not self.recommended_partner:
                try:
                    self.recommended_user = self._meta.model.objects.get(code=self._recommended_by.upper())
                except:
                    pass
        return super(User, self).save(*args, **kwargs)

    @property
    def nickname(self):
        return self.username

    @property
    def is_service_blocked(self):
        return bool(self.blocked_info is not None)

    @property
    def blocked_info(self):
        if not self._is_service_blocked:
            return None
        blocked = self.service_blocks.exclude(end_datetime__lt=timezone.now())
        if not blocked.count():
            self._is_service_blocked = False
            self.save()
            return None
        blocked = blocked.last()
        return {
            'reason': blocked.get_reason(),
            'end_date': blocked.end_datetime.strftime('%Y-%m-%d')
        }

    @property
    def is_helper(self):
        return hasattr(self, 'helper') and self.helper.accepted_datetime and self.helper.is_active

    @property
    def is_withdrawn(self):
        return self.withdrew_datetime is not None

    @property
    def is_ci(self):
        return bool(self.ci)

    @property
    def is_adult(self):
        if self.date_of_birth:
            return bool(timezone.now().date() - self.date_of_birth > timezone.timedelta(days=365 * 19))
        return None

    def get_gender_display(self):
        return dict(GENDERS)[self.gender]

    @property
    def state(self):
        if self.is_withdrawn:
            return 'withdrew'
        if self.is_service_blocked:
            return 'service_blocked'
        if not self.is_active:
            return 'deactivated'
        if hasattr(self, 'helper') and self.helper.is_active:
            if self.helper.accepted_datetime:
                return 'helper'
            if self.helper.rejected_datetime:
                return 'helper_rejected'
            return 'helper_requested'
        return 'customer'

    @property
    def recommended_by(self):
        return self.recommended_partner or self.recommended_user or self._recommended_by if self._recommended_by else '-'

    @property
    def mission_requested_count(self):
        return self.missions.filter(requested_datetime__isnull=False, canceled_datetime__isnull=True).count()

    @property
    def mission_canceled_count(self):
        # return self.missions.filter(canceled_datetime__isnull=False).count()
        return self.missions.canceled().count()

    @property
    def mission_done_count(self):
        return self.missions.filter(saved_state='done').count()

    @property
    def mission_in_action_count(self):
        return self.missions.filter(saved_state__in=['in_action', 'done_requested']).count()

    @property
    def mission_bidding_count(self):
        return self.missions.filter(saved_state='bidding').count()

    @property
    def received_reviews(self):
        Review = apps.get_model('missions', 'Review')
        return Review.objects.filter(bid__mission__user=self, is_active=True).exclude(created_user_id=self.id)

    @property
    def user_review_count(self):
        return self.received_reviews.count()

    @property
    def user_review_average(self):
        stars = self.received_reviews.values_list('stars', flat=True)
        return round(statistics.mean(itertools.chain(*stars)), 1) if stars else 0

    @property
    def user_review_average_float(self):
        return '%0.1f' % self.user_review_average

    @property
    def user_review_average_stars(self):
        return stars(round(self.user_review_average))

    @property
    def helper_review_average(self):
        if not hasattr(self, 'helper'):
            return 0
        return self.helper.review_average

    @property
    def reported(self):
        Report = apps.get_model('missions', 'Report')
        return Report.objects.filter(mission__user_id=self.id)

    @property
    def point_balance(self):
        return self.points.get_balance()

    @property
    def blocked_ids(self):
        return set(
            list(self.blocks.all().values_list('user_id', flat=True))
            + list(self.blocked_bys.all().values_list('created_user_id', flat=True))
        )

    @property
    def profile_photo(self):
        return self.helper.profile_photo if self.helper and self.helper.profile_photo else None

    def get_state_display(self):
        return dict(USER_STATUS)[self.state]
    get_state_display.short_description = '회원구분'

    @property
    def push_tokens(self):
        return [device.push_token for device in self.logged_in_devices.get_logged_in() if device.push_token]

    def get_mission_done_in_peoriod(self, start_date, end_date):
        Bid = apps.get_model('missions', 'Bid')
        return Bid.objects.filter(
            mission__user=self,
            _done_datetime__gte=start_date,
            _done_datetime__lt=end_date + timezone.timedelta(days=1)
        )

    def logout_all_by_token(self, push_token, exclude_id=None):
        logged_in = LoggedInDevice.objects.filter(
            # device_info__uuid=device_info['uuid'],
            push_token=push_token,
            logged_out_datetime__isnull=True
        )
        if exclude_id:
            logged_in = logged_in.exclude(id=exclude_id)
        if logged_in:
            logged_in.update(logged_out_datetime=timezone.now())

    def update_push_token(self, push_token, device_info, app_info):
        # 처음부터 푸쉬가 허용되고 os로부터 푸쉬토큰을 받아온 적이 없는 경우 해당 디바이스의 푸쉬토큰이 업데이트 되어야 할 상황이 있음.
        logged_in = self.logged_in_devices.get_logged_in().filter(device_info=device_info)
        if logged_in.exists():
            logged_in.update(device_info=device_info, app_info=app_info)
            obj = logged_in.last()
        else:
            obj  = self.logged_in_devices.create(
                push_token=push_token,
                device_info=device_info,
                app_info=app_info,
            )
        if obj.push_token:
            self.logout_all_by_token(obj.push_token, obj.id)
        return obj

    def device_login(self, push_token, device_info, app_info):
        # 같은 토큰으로 로그아웃 처리 되지 않은 것들은 모두 로그아웃 처리
        if push_token:
            self.logout_all_by_token(push_token)

        # 링톤 설정 이어받음
        last = self.logged_in_devices.filter(device_info__uuid=device_info['uuid']).last()
        ringtone = last.push_ringtone if last else ''

        obj = self.logged_in_devices.create(
            push_token=push_token,
            push_ringtone=ringtone,
            device_info=device_info,
            app_info=app_info,
        )
        return obj

    def device_logout(self, push_token=''):
        """기기 로그아웃 기록 : 실제 로그아웃을 하는 것은 아님에 주의할 것"""
        devices = self.logged_in_devices.get_logged_in()
        if push_token:
            devices = devices.filter(push_token=push_token)
        for device in devices:
            device.logout()
        return devices

    def block(self, days=None, reason=''):
        obj = self.service_blocks.create(reason=reason)
        if days:
            obj.end_datetime = obj.start_datetime + timedelta(days=days)
            obj.save()
        return obj


class LoggedInDevice(models.Model):
    """
    로그인 기기
    """
    user = models.ForeignKey(User, verbose_name='회원', related_name='logged_in_devices', on_delete=models.CASCADE)
    push_token = models.CharField('Push 토큰', max_length=200, blank=True, default='', db_index=True)
    push_ringtone = models.CharField('푸시 알림음', max_length=20, blank=True, default='')
    device_info = JSONField('기기 정보', default=dict)
    app_info = JSONField('앱 정보', default=dict)
    logged_in_datetime = models.DateTimeField('로그인 일시', auto_now_add=True)
    logged_out_datetime = models.DateTimeField('로그아웃 일시', null=True, blank=True)

    objects = LoggedInDeviceQuerySet.as_manager()

    class Meta:
        verbose_name = '로그인 기기'
        verbose_name_plural = '로그인 기기'

    def __str__(self):
        return self.get_device_info_display()

    def logout(self):
        self.logged_out_datetime = timezone.now()
        self.save()

    def get_device_info_display(self):
        try:
            return '%s - %s %s (%s %s)' % (self.app_info['versionNumber'], self.device_info['platform'],
                                           self.device_info['version'], self.device_info['manufacturer'],
                                           self.device_info['model'])
        except:
            return 'Device %s' % self.id


class ServiceBlock(models.Model):
    """
    회원 이용정지 내역 모델
    """
    user = models.ForeignKey(User, verbose_name='회원', related_name='service_blocks', on_delete=models.CASCADE)
    start_datetime = models.DateTimeField('시작일시', auto_now_add=True)
    end_datetime = models.DateTimeField('종료일시', null=True, blank=True)
    reason = models.TextField('사유', blank=True, default='')

    objects = ServiceBlockQuerySet.as_manager()

    class Meta:
        verbose_name = '회원 이용정지 내역'
        verbose_name_plural = '회원 이용정지 내역'

    def save(self, *args, **kwargs):
        if self.end_datetime and self.end_datetime <= timezone.now():
            self.user._is_service_blocked = False
        else:
            self.user._is_service_blocked = True
        self.user.save()
        return super(ServiceBlock, self).save(*args, **kwargs)

    def get_reason(self):
        if self.reason:
            return self.reason
        logs = LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(User),
            object_id=self.user.id,
            change_message__icontains='reason',
        )
        is_second = False
        while True:
            if logs.count() == 0:
                return ''
            if logs.count() == 1:
                try:
                    return json.loads(logs.last().change_message)[0]['changed']['reason']
                except:
                    return ''
            if is_second:
                break
            is_second = True
            logs = logs.filter(
                action_time__gte=self.start_datetime - timedelta(seconds=1),
                action_time__lte=self.start_datetime + timedelta(seconds=1),
            )
    get_reason.short_description = '사유'


class ServiceTag(models.Model):
    """
    제공 서비스 태그
    """
    title = models.CharField('서비스 이름', max_length=250)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = '제공서비스 태그'
        verbose_name_plural = '제공서비스 태그'


class Helper(models.Model):
    """
    헬퍼 모델
    """
    user = models.OneToOneField(User, verbose_name='회원', related_name='helper', on_delete=models.CASCADE)
    push_allowed_from = models.TimeField('알림허용 시작', null=True, blank=True)
    push_allowed_to = models.TimeField('알림허용 종료', null=True, blank=True)
    is_online_acceptable = models.BooleanField('온라인 미션 수행여부', blank=True, default=True)
    accept_area = models.ManyToManyField(Area, verbose_name='수행지역', blank=True, related_name='helpers')
    is_mission_request_push_allowed = models.BooleanField('미션요청 푸시 허용', null=True, blank=True, default=True)
    is_nearby_push_allowed = models.BooleanField('인근지역 푸시 허용', blank=True, default=False)
    profile_photo = models.ImageField('프로필 사진', null=True, blank=True,)
    profile_photo_applied = models.ImageField('신청중인 프로필 사진', null=True, blank=True,)
    is_profile_photo_accepted = models.NullBooleanField('프로필 변경 승인여부', null=True, blank=True, default=True)
    is_profile_public = models.BooleanField('프로필 사진 공개여부', null=True, blank=True, default=False)
    has_pet = models.NullBooleanField('펫 여부', null=True, blank=True)
    introduction = models.TextField('자기소개', null=True, blank=True,)
    best_moment = models.TextField('행복했던 순간', null=True, blank=True,)
    services = models.ManyToManyField(ServiceTag, verbose_name='제공 서비스', blank=True, related_name='helpers')
    experience = ArrayField(models.CharField(max_length=250), verbose_name='경력', blank=True, default=list)
    licenses = ArrayField(models.CharField(max_length=250), verbose_name='자격증', blank=True, default=list)
    means_of_transport = ArrayField(models.CharField(max_length=10), verbose_name='이동수단', blank=True, default=list)
    usable_tools = ArrayField(models.CharField(max_length=250), verbose_name='보유장비', blank=True, default=list)
    level = models.PositiveSmallIntegerField('헬퍼 등급', blank=True, default=1)
    has_crime_report = models.BooleanField('범죄기록유무', null=True, blank=True, default=False)
    requested_datetime = models.DateTimeField('헬퍼 신청일시', auto_now_add=True)
    id_photo = models.ImageField('신분증 사진', null=True, blank=True,)
    id_person_photo = models.ImageField('신분증과 함께 찍은 사진', null=True, blank=True,)
    name = models.CharField('이름', blank=True, default='', max_length=100)
    address_area = models.ForeignKey(Area, verbose_name='주소 지역', null=True, blank=True,
                                     related_name='address_helpers', on_delete=models.SET_NULL)
    address_detail_1 = models.CharField('주소 상세 1', max_length=100, null=True, blank=True)
    address_detail_2 = models.CharField('주소 상세 2', max_length=100, null=True, blank=True)
    accepted_datetime = models.DateTimeField('승인일시', null=True, blank=True)
    rejected_datetime = models.DateTimeField('거부일시', null=True, blank=True)
    # rejected_fields = ArrayField(models.CharField(max_length=30), verbose_name='거부 필드', blank=True, default=list)
    rejected_reason = models.TextField('거부 이유', blank=True)
    is_active = models.BooleanField('활성헬퍼여부', blank=True, default=True)
    is_at_home = models.BooleanField('홈 화면 노출여부', blank=True, default=False)
    _joined_from = models.CharField('가입경로', max_length=30, blank=True, default='')
    _job = models.CharField('직업', max_length=30, blank=True, default='')
    _additional_mission_done_count = models.PositiveSmallIntegerField('추가 미션 수행건수', blank=True, default=0)
    _additional_mission_canceled_count = models.PositiveSmallIntegerField('추가 미션 취소건수', blank=True, default=0)

    objects = HelperManager()

    class Meta:
        verbose_name = '헬퍼'
        verbose_name_plural = '헬퍼'

    def __str__(self):
        return '[헬퍼] %s' % str(self.user)

    def accept(self):
        if not self.accepted_datetime:
            self.accepted_datetime = timezone.now()
            self.is_active = True
        if self.profile_photo_applied:
            self.profile_photo = self.profile_photo_applied
            self.profile_photo_applied = None
            self.is_profile_photo_accepted = True
        self.delete_id_files()

    def reject(self, reason=''):
        if self.profile_photo_applied and self.is_profile_photo_accepted is None:
            self.is_profile_photo_accepted = False
        else:
            self.rejected_datetime = timezone.now()
            if reason:
                self.rejected_reason = reason
        self.delete_id_files()

    def request_again(self):
        if self.accepted_datetime:
            self.accepted_datetime = None
        self.requested_datetime = timezone.now()
        self.rejected_datetime = None
        self.rejected_reason = ''
        self.is_active = True
        self.save()

    def get_linked_images(self):
        images = []
        for field_name in ('profile_photo', 'profile_photo_applied', 'id_photo', 'id_person_photo'):
            field = getattr(self, field_name, None)
            if field and field.path:
                images.append(field.path)
        return images

    @property
    def request_state(self):
        if not self.is_active:
            return 'deactivated'
        if self.user.withdrew_datetime:
            return 'deactivated'
        if self.accepted_datetime:
            return 'accepted'
        if self.rejected_datetime:
            if self.requested_datetime > self.rejected_datetime:
                return 'requested_again'
            return 'rejected'
        return 'requested'

    def get_request_state_display(self):
        return dict(HELPER_REQUEST_STATUS)[self.request_state]

    get_request_state_display.short_description = '헬퍼신청 상태'

    @property
    def service_tags(self):
        return [service.title for service in self.services.all()]

    @service_tags.setter
    def service_tags(self, tags):
        if hasattr(tags, '__iter__'):
            self.services.clear()
            for tag in tags:
                obj = ServiceTag.objects.filter(title=tag.strip()).last()
                if not obj:
                    obj = ServiceTag.objects.create(title=tag.strip())
                self.services.add(obj)

    @cached_property
    def accept_area_ids(self):
        ids = []
        for area in self.accept_area.all():
            ids.append(area.id)
            if self.is_nearby_push_allowed:
                ids += list(area.nearby.all().values_list('id', flat=True))
        return set(ids)

    @property
    def bank_account(self):
        return self.bank_accounts.order_by('id').last()

    @property
    def address(self):
        return '%s %s %s' % (self.address_area.name, self.address_detail_1, self.address_detail_2)

    @property
    def mission_canceled_count(self):
        # return self.missions.filter(canceled_datetime__isnull=False).count()
        return self.bids.canceled().count()

    @property
    def mission_done_count(self):
        return self.bids.filter(saved_state='done').count()

    @property
    def mission_in_action_count(self):
        return self.bids.filter(saved_state__in=['in_action', 'done_requested']).count()

    @property
    def mission_bidding_count(self):
        return self.bids.filter(saved_state='bidding').count()

    @property
    def mission_waiting_count(self):
        return self.bids.waiting_assignee().count()

    @property
    def mission_failed_count(self):
        return self.bids.failed().count()

    @property
    def profile_image_url(self):
        return ('https://%s%s' % (settings.MAIN_HOST, self.profile_photo.url)) if self.profile_photo else ''

    # @property
    # def mission_done_count(self):
    #     return self.bids.filter(_done_datetime__isnull=False).count() + self._additional_mission_done_count

    @property
    def mission_done_in_30_days_count(self):
        in_30_days = timezone.now() - timezone.timedelta(days=30)
        return self.bids.filter(_done_datetime__gte=in_30_days).count()

    @property
    def received_reviews(self):
        return self.user.received_all_reviews.filter(is_active=True, _is_created_user_helper=False)

    @property
    def review_average(self):
        stars = self.received_reviews.values_list('stars', flat=True)
        return round(statistics.mean(itertools.chain(*stars)), 1) if stars else 0

    @property
    def review_average_float(self):
        return '%0.1f' % self.review_average

    @property
    def review_average_stars(self):
        return stars(round(self.review_average))

    @property
    def review_count(self):
        return self.received_reviews.count()

    @property
    def reported(self):
        Report = apps.get_model('missions', 'Report')
        return Report.objects.filter(bid__helper_id=self.id)

    @property
    def profit_mission_fee(self):
        return sum(self.cashes.filter(bid__isnull=False).values_list('amount', flat=True))

    @property
    def profit_etc(self):
        return sum(self.cashes.filter(bid__isnull=True, withdraw__isnull=True, amount__gte=0).values_list('amount', flat=True))

    @property
    def profit_total(self):
        return self.profit_mission_fee + self.profit_etc

    @property
    def cash_balance(self):
        return self.cashes.get_balance()

    @property
    def withdrawable_cash_balance(self):
        balance = self.cashes.get_balance()
        requested_before = sum(self.withdraws.filter(failed_datetime__isnull=True, done_datetime__isnull=True)
                               .values_list('amount', flat=True))
        withdrawable = balance - requested_before
        return withdrawable if withdrawable > 0 else 0

    @property
    def is_mission_request_push_allowed_now(self):
        now_time = timezone.now().time()

        # 푸쉬 허용 안 되어 있는 경우
        if not self.user.is_push_allowed or not self.is_mission_request_push_allowed:
            return False

        # 알림시간 지정 안 된 경우
        if not self.push_allowed_from or not self.push_allowed_to or (self.push_allowed_from == self.push_allowed_to):
            return True

        # 알림시간에 해당되는 경우
        if self.push_allowed_from < now_time < self.push_allowed_to:
            return True
        if self.push_allowed_from > self.push_allowed_to:
            if not (self.push_allowed_from < now_time < self.push_allowed_to):
                return True

        return False

    @property
    def fee_rate(self):
        today = timezone.now().date()
        return self.fee_rates.filter(start_date__lte=today, end_date__gte=today).order_by('-created_datetime').first()

    def delete_id_files(self):
        if self.id_photo:
            if os.path.isfile(self.id_photo.path):
                os.remove(self.id_photo.path)
            self.id_photo = None
        if self.id_person_photo:
            if os.path.isfile(self.id_person_photo.path):
                os.remove(self.id_person_photo.path)
            self.id_person_photo = None
        self.save()


class Quiz(models.Model):
    """
    헬퍼 신청 퀴즈 모델
    """
    title = models.CharField('문제', max_length=200)

    class Meta:
        verbose_name = '퀴즈'
        verbose_name_plural = '퀴즈'

    def __str__(self):
        return self.title


class QuizAnswer(models.Model):
    """
    헬퍼 신청 퀴즈 답안 모델
    """
    quiz = models.ForeignKey(Quiz, verbose_name='문제', related_name='answers', on_delete=models.CASCADE)
    text = models.CharField('답안', max_length=200)
    is_correct = models.BooleanField('정답', blank=True, default=False)

    class Meta:
        verbose_name = '답안'
        verbose_name_plural = '답안'
        ordering = ('id',)

    def __str__(self):
        return self.text


class FeeRate(models.Model):
    """
    기간 수수료율 모델
    """
    helper = models.ForeignKey(Helper, verbose_name='헬퍼', related_name='fee_rates', on_delete=models.CASCADE)
    fee = models.PositiveSmallIntegerField('수수료율', blank=True, default=0)
    start_date = models.DateField('적용 시작일시')
    end_date = models.DateField('적용 종료일시')
    created_datetime = models.DateTimeField('등록일시', auto_now_add=True)

    class Meta:
        verbose_name = '기간 수수료율'
        verbose_name_plural = '기간 수수료율'

    def __str__(self):
        return '%s%% (%s~%s)' % (self.fee, self.start_date, self.end_date)


class BankAccount(models.Model):
    """
    은행 계좌 모델
    """
    helper = models.ForeignKey(Helper, verbose_name='헬퍼', related_name='bank_accounts', on_delete=models.CASCADE)
    bank_code = models.PositiveSmallIntegerField('은행', choices=BANK_CODES, null=True, blank=True,)
    number = models.CharField('계좌번호', max_length=20, null=True, blank=True,)
    name = models.CharField('예금주', max_length=20, null=True, blank=True,)
    created_datetime = models.DateTimeField('등록일시', null=True, blank=True)

    class Meta:
        verbose_name = '은행 계좌'
        verbose_name_plural = '은행 계좌'

    @property
    def bank_name(self):
        try:
            return dict(BANK_CODES)[self.bank_code]
        except:
            return self.bank_code

    def __str__(self):
        return '[%s] %s' % (self.bank_name, self.number)


class TIN(models.Model):
    """
    주민번호
    """
    helper = models.OneToOneField(Helper, verbose_name='헬퍼', related_name='tin', on_delete=models.CASCADE)
    number = models.BinaryField('번호')

    class Meta:
        verbose_name = '주민번호'
        verbose_name_plural = '주민번호'
