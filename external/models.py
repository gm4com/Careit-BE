import dateutil.parser

import short_url

from django.db import models
from django.contrib.postgres.fields import JSONField
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse_lazy
from django.utils import timezone

from common.admin import log_with_reason
from base.models import Area
from base.exceptions import ExternalErrors
from accounts.models import User, MobileVerification
from missions.models import MissionType, MultiMission, Mission, Address


class ExternalMissionProduct(models.Model):
    """
    외부 미션요청 제품
    """
    mission_type = models.ForeignKey(MissionType, verbose_name='미션 타입', related_name='products',
                                     on_delete=models.CASCADE, default=1)
    identifier = models.CharField('제품 식별자', max_length=100)
    items = JSONField('제품정보')

    class Meta:
        verbose_name = '외부 미션요청 제품'
        verbose_name_plural = '외부 미션요청 제품'

    def __str__(self):
        return '%s-%s' % (self.mission_type.code, self.identifier)


class ExternalMission(models.Model):
    """
    외부 미션요청
    """
    user = models.ForeignKey('accounts.User', verbose_name='회원', on_delete=models.CASCADE, null=True, blank=True,
                             related_name='external_missions')
    login_code = models.SlugField('코드', max_length=32, blank=True, default='')
    mission_type = models.ForeignKey(MissionType, verbose_name='미션 타입', related_name='externals',
                                     on_delete=models.CASCADE, default=1)
    mission = models.OneToOneField(Mission, verbose_name='미션', related_name='external',
                                   null=True, blank=True, on_delete=models.SET_NULL)
    multi_mission = models.OneToOneField(MultiMission, verbose_name='다중 미션', related_name='external',
                                         null=True, blank=True, on_delete=models.SET_NULL)
    data = JSONField('요청내용', blank=True, default=dict)
    reference_code = models.CharField('참조 미션코드', max_length=15, blank=True, default='')
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)

    class Meta:
        verbose_name = '외부 미션요청'
        verbose_name_plural = '외부 미션요청'

    def __str__(self):
        return 'E%s%s' % (self.mission_type.code, self.id)

    @property
    def _mission(self):
        return self.mission or self.multi_mission

    @property
    def url(self):
        return '%s?code=%s' % (settings.EXTERNAL_MISSION_SMS_URLS[self.mission_type.code], self.login_code)

    @property
    def shortened_url(self):
        return 'https://%s/e/%s/' % (settings.SHORTEN_HOST, short_url.encode_url(self.id))

    def has_required_data(self, *args):
        for arg in args:
            if arg not in self.data:
                return False
        return True

    def request_mission(self):
        handler = getattr(self, '_request_%s' % self.mission_type.code, None) or None
        if handler and callable(handler):
            return handler()
        return ExternalErrors.WRONG_REQUEST

    def _request_IK(self):
        """이케아 데이터 처리기"""
        # validation
        if not self.has_required_data('request', 'verification_id', 'address', 'address_detail', 'due_datetime',
                                      'items', 'expected_max_cost', 'expected_min_cost'):
            return ExternalErrors.NO_FIELD

        # 미션일시 확인
        due_datetime = dateutil.parser.parse(self.data['due_datetime'])
        if due_datetime < timezone.now():
            return ExternalErrors.DUE_DATETIME_OVER

        # 표시내용 조합
        content = '[이케아 조립미션]\n요청사항 : %s' % self.data['request']

        # 회원 변환
        try:
            verification = MobileVerification.objects.get(id=self.data['verification_id'])
        except:
            return ExternalErrors.VERIFICATION_NOT_FOUND
        self.user, is_created = User.objects.get_or_create(mobile=verification.number)
        if is_created:
            self.user._recommended_by = 'IKEA'
            self.user.save()
        if not verification.user:
            verification.user = self.user
            verification.save()

        # 주소 변환
        area_id, detail_1 = Area.objects.search(self.data['address'])
        if area_id:
            address = Address.objects.create(user_id=self.user.id, area_id=area_id,
                                             detail_1=detail_1, detail_2=self.data['address_detail'])
        else:
            log_with_reason(self.user.id, self, 'changed', '[미션 자동변환 실패] 주소 검색 불가')
            return ExternalErrors.ADDRESS_TRANSFORM_FAILED

        # 미션 변환
        try:
            mission = Mission.objects.create(
                user_id=self.user.id,
                login_code=self.login_code,
                mission_type=self.mission_type,
                content=content,
                due_datetime=due_datetime,
                final_address=address,
                product=self.data['items'],
                amount_high=self.data['expected_max_cost'],
                amount_low=self.data['expected_min_cost'],
            )
        except:
            log_with_reason(self.user.id, self, 'changed', '[미션 자동변환 실패] 미션 추가 실패')
            return ExternalErrors.MISSION_TRANSFORM_FAILED
        self.mission = mission

        # 미션 요청
        self.reference_code = mission.code
        self.save()
        requested = mission.request()
        if requested:
            return requested
        return ExternalErrors.MISSION_REQUEST_FAILED
