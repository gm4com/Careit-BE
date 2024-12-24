import dateutil.parser
import statistics
import re
from random import randrange

import requests
import short_url

from django.db import models
from django.db.models.functions import Concat, Substr
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import ArrayField, JSONField
from django.utils import timezone
from django.apps import apps
from django.utils.safestring import mark_safe
from django.conf import settings

from django_summernote.fields import SummernoteTextField

from common.admin import log_with_reason
from common.utils import UploadFileHandler, stars, add_comma, list_to_concat_string
from common.validators import MobileNumberOnlyValidators
from common.exceptions import Errors, ValidationError
from base.models import anyman
from base.constants import MISSION_STATUS, MISSION_STATE_CLASSES
from accounts.models import Partnership, State, User, Helper, Area, MobileVerification
from notification.models import Notification, Tasker
from notification.utils import FirebaseFirestoreChatHandler
from .utils import KeywordWarning, KCTSafetyNumber


anytalk = FirebaseFirestoreChatHandler()

kct = KCTSafetyNumber()



"""
querysets & managers
"""


class SafetyNumberQuerySet(models.QuerySet):
    """
    안심번호 쿼리셋
    """
    number_prefix = '0508489'
    range_prefix = {
        'customer': '6',
        'helper': '7',
        'normal': '8'
    }

    @classmethod
    def get_random_4_number(cls):
        return str(randrange(0, 9999)).zfill(4)

    def get_available_random_4_number(self, range_name):
        prefix = self.number_prefix + self.range_prefix[range_name]
        current_using_list = self.current_using().filter(assigned_number__startswith=prefix)\
            .values_list('assigned_number', flat=True)
        while True:
            suffix = self.get_random_4_number()
            if prefix + suffix not in current_using_list:
                break
        return suffix

    def get_available_random_number(self, range_name):
        return self.number_prefix + self.range_prefix[range_name] + self.get_available_random_4_number(range_name)

    def current_using(self, **kwargs):
        qs = self.filter(assigned_datetime__isnull=False, unassigned_datetime__isnull=True)
        if kwargs:
            qs = qs.filter(**kwargs)
        return qs

    def assign(self, user, safety_number='', range_name='normal'):
        # 휴대폰 번호 정상여부 체크
        if not user.mobile or not user.mobile.isnumeric():
            return None

        # 번호 지정이 없으면 랜덤 생성
        if not safety_number:
            safety_number = self.get_available_random_number(range_name)

        if len(safety_number) is 4:
            safety_number = self.number_prefix + self.range_prefix[range_name] + safety_number

        obj = self.create(assigned_number=safety_number, number=user.mobile, user=user)  # 중복 생성을 방지하기 위해 일단 할당 전에 레코드 생성
        obj.assign()
        return obj if obj and obj.is_active else None

    def assign_pair_from_bid(self, bid):
        try:
            relay_url = getattr(settings, 'KCT_RELAY_URL')
            if relay_url:
                requests.get(relay_url + str(bid.id) + '/')
            else:
                suffix = self.get_available_random_4_number('customer')
                bid.customer_safety_number = self.assign(bid._mission.user, suffix, 'customer')
                bid.helper_safety_number = self.assign(bid.helper.user, suffix, 'helper')
                bid.save()
        except:
            pass

    def unassign_pair_from_bid(self, bid):
        try:
            relay_url = getattr(settings, 'KCT_RELAY_URL')
            if relay_url:
                requests.delete(relay_url + str(bid.id) + '/')
            else:
                if bid.customer_safety_number:
                    bid.customer_safety_number.unassign()
                if bid.helper_safety_number:
                    bid.helper_safety_number.unassign()
        except:
            pass

    def unassign_by_user(self, user):
        for safety_number in self.current_using(user=user):
            safety_number.unassign()


class AddressManager(models.Manager):
    """
    미션용 주소 매니져
    """
    def get_deleted(self):
        return super(AddressManager, self).get_queryset().filter(is_active=False)

    def get_queryset(self):
        return super(AddressManager, self).get_queryset().filter(is_active=True)


class MultiMissionQuerySet(models.QuerySet):
    """
    다중 미션 쿼리셋
    """
    def requested(self):
        return self.filter(requested_datetime__isnull=False)

    def activated(self):
        return self.filter(is_active=True)

    def draft(self):
        return self.filter(requested_datetime__isnull=True)

    def deactivated(self):
        return self.filter(is_active=False)

    def done(self):
        return self.requested().activated().filter(
            children__bids___done_datetime__isnull=False,
            children__bid_closed_datetime__isnull=False
        )

    def in_action(self):
        return self.requested().activated().filter(
            children__bids___done_datetime__isnull=True
        )

    def in_bidding(self):
        return self.requested().activated().filter(
            children__bid_closed_datetime__isnull=True
        )

    def available(self, user, area_ids=[]):
        area_ids = area_ids or user.helper.accept_area_ids
        return self.requested().in_bidding().filter(
            models.Q(request_helpers=user.helper)
            | models.Q(request_helpers__isnull=True, children__area__in=area_ids)
            | models.Q(request_helpers__isnull=True, children__area__parent__in=area_ids)
        )


class MissionQuerySet(models.QuerySet):
    """
    미션 쿼리셋
    """
    def all_view_only(self):
        return self.filter(
            requested_datetime__isnull=False,
            canceled_datetime__isnull=True,
            bid_closed_datetime__isnull=True,
        ).exclude(bid_limit_datetime__lte=timezone.now())

    def available(self, helper_user, area_ids=[]):
        area_ids = area_ids or helper_user.helper.accept_area_ids
        query = models.Q(stopovers__area__id__in=area_ids) \
            | models.Q(stopovers__area__parent__id__in=area_ids) \
            | models.Q(final_address__area__parent__id__in=area_ids) \
            | models.Q(final_address__area__id__in=area_ids)
        if helper_user.helper.is_online_acceptable:
            query = query | models.Q(final_address=None, request_areas=None)
        qs = self.filter(saved_state='bidding').filter(query)  # 요청 지역이 없는 미션이거나, 내 지역 및 인근지역 미션만 필터링
        qs = qs.exclude(bid_limit_datetime__lte=timezone.now())  # 타임아웃 미션 제외
        qs = qs.exclude(user_id__in=helper_user.blocked_ids)  # 블럭한 유져의 미션 제외
        qs = qs.exclude(user_id=helper_user.id)  # 내 미션 제외
        qs = qs.exclude(reports__created_user_id=helper_user.id)  # 신고한 미션 제외
        qs = qs.exclude(id__in=Bid.objects.applied(helper_user.id).values_list('mission_id', flat=True))  # 내가 입찰한 미션 제외
        return qs.distinct('id')

    def assigned(self, helper_user):
        return self.filter(
            saved_state='waiting_assignee',
            id__in=Bid.objects.assigned(helper_user).values_list('mission_id', flat=True),
        ).exclude(bid_limit_datetime__lte=timezone.now()).distinct('id')

    def canceled(self):
        return self.filter(
            requested_datetime__isnull=False
        ).filter(
            models.Q(canceled_datetime__isnull=False)
            | models.Q(bid_closed_datetime__isnull=True, bid_limit_datetime__lte=timezone.now())
            | models.Q(bids___canceled_datetime__isnull=False, bids__won_datetime__isnull=False)
        )

    def canceled_saved(self):
        canceled_status = [s for s in dict(MISSION_STATUS).keys() if 'canceled' in s]
        return self.filter(saved_state__in=canceled_status)

    def done(self):
        return self.filter(saved_state='done')

    def recent(self, days=None):
        qs = self.done() | self.canceled()
        if days:
            qs = qs.filter(requested_datetime__gte=(timezone.now() - timezone.timedelta(days=days)))
        return qs.distinct('id')

    def active(self, user_id=None):
        return (
            self.filter(user_id=user_id).in_action()
            | self._in_bidding(user_id=user_id)
        ).distinct('id')

    def _in_bidding(self, user_id=None):
        qs = self
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs.filter(saved_state__in=['bidding', 'waiting_assignee']).filter(
            models.Q(bid_limit_datetime__isnull=True)
            | models.Q(bid_limit_datetime__gte=timezone.now())
        )

    def in_bidding(self, user_id=None):
        return self._in_bidding(user_id).distinct('id')

    def in_action(self):
        return self.filter(id__in=Bid.objects.in_action().values_list('mission_id', flat=True))

    def check_user_bidding(self, user_id):
        return self.filter(user_id=user_id, saved_state__code__in=('bidding', 'waiting_assignee')).exists()

    def search(self, query, fields=['code', 'user__mobile', 'user__username']):
        qs = self.none()
        for field in fields:
            qs = qs | self.filter(**{field + '__icontains': query})
        return qs.distinct('id')


class MissionManager(models.Manager):
    def get_queryset(self):
        return MissionQuerySet(self.model, using=self._db).select_related('user', 'mission_type', 'final_address')


class BidQuerySet(models.QuerySet):
    """
    미션 입찰 쿼리셋
    """
    def in_bidding(self, user_id=None):
        qs = self
        if user_id:
            qs = qs.filter(mission__user_id=user_id)
        return qs.filter(saved_state='applied')

    def applied(self, helper_user_id=None):
        qs = self
        if helper_user_id:
            qs = qs.filter(helper__user_id=helper_user_id)
        return qs.filter(saved_state='applied')

    def in_action(self):
        return self.filter(saved_state='in_action')

    def canceled(self, days=None):
        qs = self.filter(applied_datetime__isnull=False, saved_state__in=[
                             'done_and_canceled', 'admin_canceled', 'user_canceled',
                             'timeout_canceled', 'won_and_canceled', 'bid_and_canceled'
                         ])
        if days:
            before_days = timezone.now() - timezone.timedelta(days=days)
            qs = qs.exclude(mission__canceled_datetime__lt=before_days)\
                .exclude(mission__bid_limit_datetime__lt=before_days)\
                .exclude(_canceled_datetime__lt=before_days)
        return qs

    def canceled_saved(self):
        return self.canceled()

    def failed(self):
        return self.filter(saved_state='failed')

    def done(self, days=None):
        qs = self.filter(saved_state='done')
        if days:
            before_days = timezone.now() - timezone.timedelta(days=days)
            qs = qs.filter(_done_datetime__gt=before_days)
        return qs

    def assigned(self, helper_user):
        return self.filter(
            helper__user_id=helper_user.id,
            is_assigned=True,
            won_datetime__isnull=True,
            applied_datetime__isnull=True
        )

    def waiting_assignee(self):
        return self.filter(saved_state='waiting_assignee')


class ReviewQuerySet(models.QuerySet):
    """
    리뷰 쿼리셋
    """
    # todo: 리뷰 수동추가에 따른 쿼리 추가됨. 추가된 필드값이 기존 데이터에도 들어가면 이 부분을 마저 변경해야 함.

    def get_customer_received(self, user):
        if type(user) is int:
            return self.filter(is_active=True, _is_created_user_helper=True, _received_user_id=user)
        return self.filter(is_active=True, _is_created_user_helper=True, _received_user=user)

    def get_helper_received(self, user=None):
        qs = self.filter(is_active=True, _is_created_user_helper=False)
        if user:
            if type(user) is int:
                return qs.filter(received_user_id=user)
            return qs.filter(_received_user=user)
        return qs

    def get_template_reviews(self):
        return self.filter(bid__mission__template__isnull=False)

    def mean(self, round_digit=1):
        # 이 부분의 로직은 항상 stars 배열의 길이가 같다는 전제하에 작성된 것이므로,
        # 길이가 일정하지 않을 가능성이 있는 경우 변화가 있어야 함.
        # 특히, 전체 평균은 길이가 일정하지 않은 경우 반드시 계산이 달라져야 할 것임.
        rtn = []
        for stars in zip(*self.values_list('stars', flat=True)):
            rtn.append(round(statistics.mean(stars), round_digit))
        if rtn:
            rtn.insert(0, round(statistics.mean(rtn), round_digit))
        return rtn or [0, 0, 0]


class ReportQuerySet(models.QuerySet):
    """
    신고 쿼리셋
    """
    def get_customer_received(self, user):
        if type(user) is int:
            return self.filter(mission__user_id=user).exclude(created_user_id=user)
        return self.filter(mission__user=user).exclude(created_user=user)

    def get_helper_received(self, user):
        return self.filter(bid__helper__user=user).exclude(created_user=user)


"""
models
"""


class SafetyNumber(models.Model):
    """
    안심번호
    """
    user = models.ForeignKey(User, verbose_name='회원', related_name='safety_numbers', on_delete=models.CASCADE)
    number = models.CharField('번호', max_length=12)
    assigned_number = models.CharField('안심번호', max_length=12)
    assigned_datetime = models.DateTimeField('할당 일시', null=True, blank=True, default=None)
    unassigned_datetime = models.DateTimeField('할당해제 일시', null=True, blank=True, default=None)

    objects = SafetyNumberQuerySet.as_manager()

    class Meta:
        verbose_name = '안심번호'
        verbose_name_plural = '안심번호'

    def __str__(self):
        return '%s (%s)' % (self.assigned_number, self.number)

    @property
    def is_active(self):
        return bool(self.assigned_datetime is not None and self.unassigned_datetime is None)

    def assign(self):
        if self.assigned_datetime:
            return False
        kct.login()
        response = kct.assign_number(self.assigned_number, self.user.mobile)
        if response:
            self.assigned_datetime = timezone.now()
            self.save()
            return True
        return False

    def unassign(self):
        if self.unassigned_datetime:
            return False
        self.unassigned_datetime = timezone.now()
        self.save()
        kct.login()
        kct.unassign_number(self.assigned_number)
        return True


class MissionWarningNotice(models.Model):
    """
    위험미션 키워드
    """
    description = models.TextField('안내 문구')

    class Meta:
        verbose_name = '위험미션 키워드'
        verbose_name_plural = '위험미션 키워드'

    def __str__(self):
        return self.description


class DangerousKeyword(models.Model):
    """
    위험 키워드
    """
    warning = models.ForeignKey(MissionWarningNotice, related_name='keywords', on_delete=models.CASCADE)
    text = models.CharField('키워드', max_length=20)

    class Meta:
        verbose_name = '경고 키워드'
        verbose_name_plural = '경고 키워드'

    def __str__(self):
        return self.text


class Address(models.Model):
    """
    미션용 주소 모델
    """
    user = models.ForeignKey(User, verbose_name='회원', related_name='address_books', on_delete=models.CASCADE)
    name = models.CharField('별칭', max_length=13, blank=True, default='')
    area = models.ForeignKey(Area, verbose_name='지역', on_delete=models.CASCADE)
    detail_1 = models.CharField('상세 주소', max_length=100)
    detail_2 = models.CharField('상세 주소', max_length=100, blank=True, default='')
    is_active = models.BooleanField('활성화', blank=True, default=True)

    objects = AddressManager()

    class Meta:
        verbose_name = '미션용 주소'
        verbose_name_plural = '미션용 주소'

    def __str__(self):
        return '%s [%s]' % (self.full, self.name) if self.name else self.full

    def delete(self, using=None, keep_parents=False):
        self.is_active = False
        return self.save()

    @property
    def detail(self):
        return '%s %s' % (self.detail_1, self.detail_2)

    @property
    def full(self):
        return '%s %s' % (str(self.area), self.detail)

    def readable(self):
        return str(self)


class MissionType(models.Model):
    """
    미션 타입 모델
    """
    title = models.CharField('타입명', max_length=20)
    description = models.CharField('타입 설명', max_length=250)
    code = models.CharField('타입 코드', max_length=2, blank=True, default='')
    class_name = models.CharField('클래스명', max_length=20, blank=True, default='')
    user_in_charge = models.ForeignKey(User, verbose_name='담당자', null=True, blank=True,
                                       related_name='charged_mission_types', on_delete=models.SET_NULL)
    minimum_amount = models.SmallIntegerField('입찰 하한가', blank=True, default=1000)
    charge_rate = models.SmallIntegerField('수수료율', blank=True, default=16)
    product_fields = JSONField('상품 필드', blank=True, default=dict)
    bidding_limit = models.PositiveSmallIntegerField('입찰 제한시간 (분)', null=True, blank=True)
    push_before_finish = models.PositiveSmallIntegerField('마감 전 푸시알림 (분)', blank=True, default=0)

    class Meta:
        verbose_name = '미션 타입'
        verbose_name_plural = '미션 타입'

    def __str__(self):
        return self.description


class MultiMission(models.Model):
    """
    다중 미션 모델
    """
    code = models.CharField('미션코드', max_length=8, blank=True, default='', db_index=True)
    user = models.ForeignKey(User, verbose_name='담당자', related_name='multi_missions', on_delete=models.CASCADE)
    mission_type = models.ForeignKey(MissionType, verbose_name='미션 타입', related_name='multi_missions',
                                     on_delete=models.CASCADE, default=1)
    title = models.CharField('미션 제목', max_length=250)
    banner = models.ImageField('미션 배너', null=True, blank=True)
    summary = models.TextField('수행내용 요약')
    content = SummernoteTextField('수행내용')
    request_helpers = models.ManyToManyField(Helper, verbose_name='요청 헬퍼', blank=True,
                                             help_text='요청 헬퍼를 지정하는 경우, 해당 헬퍼에게만 노출됩니다.')
    created_datetime = models.DateTimeField('작성 일시', auto_now_add=True)
    requested_datetime = models.DateTimeField('요청 일시', blank=True, null=True)
    is_active = models.BooleanField('활성화', blank=True, default=True)
    saved_state = models.ForeignKey(State, verbose_name='상태', blank=True, default='draft', to_field='code',
                                    related_name='multi_missions', on_delete=models.SET_DEFAULT)

    objects = MultiMissionQuerySet.as_manager()

    class Meta:
        verbose_name = '다중 미션'
        verbose_name_plural = '다중 미션'

    def __str__(self):
        return '[%s] %s' % (str(self.mission_type), self.code)

    def save(self, *args, **kwargs):
        self.set_state(save=False)
        for child in self.children.all():
            child._save_single()
        return super(MultiMission, self).save(*args, **kwargs)

    @property
    def request_areas(self):
        return [child.area for child in self.children.distinct('area')]

    @property
    def state(self):
        """미션 상태"""
        return self.saved_state.code

    @property
    def parsed_content(self):
        try:
            return re.sub(r'src\=\"\/media\/django\-summernote\/',
                          'src="https://%s/media/django-summernote/' % settings.MAIN_HOST,
                          self.content)
        except:
            return self.content

    def set_state(self, save=True):
        try:
            self.saved_state_id = self.get_state_code()
        except:
            return False
        if save:
            self.save()

    def get_state_code(self):
        if not self.is_active:
            return 'mission_deactivated'  # 비활성화
        else:
            if not self.requested_datetime:
                return 'draft'  # 미션 작성이 완료되지 않음
            if self.children.filter(bid_closed_datetime__isnull=True).exists():
                return 'bidding'  # 입찰중
            else:
                if self.children.filter(bids___done_datetime__isnull=True).exists():
                    return 'in_action'  # 수행중
                else:
                    return 'done'  # 수행완료

    def request(self):
        if self.requested_datetime:
            return False
        if not self.children.exists():
            return False
        self.requested_datetime = timezone.now()
        self.save()
        return True

    def handle_banner(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_timestamp()
        return file.save(to='banner')

    def get_state_display(self):
        return dict(MISSION_STATUS)[self.state]
    get_state_display.short_description = '미션 상태'

    def get_banner_display(self):
        return mark_safe('<img src="%s" />' % self.banner.url) if self.banner else ''
    get_banner_display.short_description = '배너'
    get_banner_display.admin_order_field = 'banner'


class MultiAreaMission(models.Model):
    """
    다중지역 미션 모델
    """
    parent = models.ForeignKey(MultiMission, verbose_name='상위 미션', related_name='children', on_delete=models.CASCADE)
    area = models.ForeignKey(Area, verbose_name='지역', on_delete=models.CASCADE)
    detail_1 = models.CharField('상세 주소 1', max_length=100)
    detail_2 = models.CharField('상세 주소 2', max_length=100, blank=True, default='')
    amount = models.IntegerField('지급캐쉬', blank=True, default=0)
    customer_mobile = models.CharField('고객 연락처', max_length=11, blank=True, default='')
    canceled_datetime = models.DateTimeField('취소일시', blank=True, null=True)
    bid_closed_datetime = models.DateTimeField('입찰종료일시', blank=True, null=True)
    push_result = models.OneToOneField('notification.Notification', verbose_name='푸쉬 결과', null=True, blank=True,
                                       related_name='area_mission', on_delete=models.CASCADE)
    saved_state = models.ForeignKey(State, verbose_name='상태', blank=True, default='draft', to_field='code',
                                    related_name='area_missions', on_delete=models.SET_DEFAULT)

    class Meta:
        verbose_name = '다중지역 미션'
        verbose_name_plural = '다중지역 미션'

    def __str__(self):
        return '[%s] %s' % (str(self.mission_type), self.code)

    def save(self, *args, **kwargs):
        self.set_state(save=False)
        self.parent.set_state()
        return super(MultiAreaMission, self).save(*args, **kwargs)

    def _save_single(self):
        self.set_state(save=False)
        return super(MultiAreaMission, self).save()

    @property
    def code(self):
        return self.parent.code

    @property
    def user(self):
        return self.parent.user

    @property
    def mission_type(self):
        return self.parent.mission_type

    @property
    def mission_type_id(self):
        return self.parent.mission_type_id

    @property
    def requested_datetime(self):
        return self.parent.requested_datetime

    @property
    def final_address(self):
        return {
            'area': self.area_id,
            'detail_1': self.detail_1,
            'detail_2': self.detail_2,
            'readable': '%s %s' % (str(self.area), self.detail_1),
            'readable_bidded': '%s %s %s' % (str(self.area), self.detail_1,  self.detail_2),
        }

    @property
    def final_address_area_id(self):
        return self.area_id

    @property
    def title(self):
        return self.parent.title

    @property
    def banner(self):
        return self.parent.banner

    @property
    def content(self):
        return self.parent.content

    @property
    def parsed_content(self):
        return self.parent.parsed_content

    @property
    def summary(self):
        return self.parent.summary

    @property
    def content_short(self):
        return self.parent.summary.replace('\n', '')[:7] + '...'

    @property
    def charge_rate(self):
        return 0

    @property
    def is_web(self):
        return False

    @property
    def is_multi(self):
        return True

    @property
    def shortened_url(self):
        return ''

    @property
    def bidded_count(self):
        return self.bids.filter(_canceled_datetime__isnull=True, applied_datetime__isnull=False).count()

    @property
    def won(self):
        return self.bids.filter(won_datetime__isnull=False)

    @property
    def active_bid(self):
        return self.won.filter(_canceled_datetime__isnull=True).last()

    @property
    def active_bid_id(self):
        return self.active_bid.id if self.active_bid else None

    @property
    def helper(self):
        return self.active_bid.helper if self.active_bid else None

    @property
    def can_cancel(self):
        return bool(self.state == 'bidding')

    @property
    def active_due(self):
        return self.active_bid.active_due if self.active_bid else None

    @property
    def warnings(self):
        return []

    @property
    def customer_paid(self):
        return self.amount

    @property
    def customer_point_used(self):
        return 0

    @property
    def bid_canceled_datetime(self):
        return self.active_bid.canceled_datetime if self.won else self.canceled_datetime

    @property
    def bid_done_datetime(self):
        return self.active_bid.done_datetime if self.won else None

    @property
    def done_requested(self):
        if not self.active_bid:
            return None
        return self.active_bid.done_requested

    @property
    def state(self):
        """미션 상태"""
        return self.saved_state.code

    def set_state(self, save=True):
        try:
            self.saved_state_id = self.get_state_code()
        except:
            return False
        if save:
            self.save()

    def get_state_code(self):
        if not self.parent.requested_datetime:
            return 'draft'  # 미션 작성이 완료되지 않음
        if self.canceled_datetime:
            return 'user_canceled'  # 낙찰 전 취소
        if self.active_bid:
            if self.done_requested:
                return 'done_requested'
            return self.active_bid.state
        if self.parent.is_active:
            return 'bidding'  # 입찰중
        return 'mission_deactivated'  # 비활성화

    def get_state_display(self):
        status = dict(MISSION_STATUS)
        if type(self.state) is list:
            return [status[s] for s in self.state]
        return status[self.state]
    get_state_display.short_description = '미션 상태'

    def cancel(self):
        if not self.can_cancel:
            return False
        self.canceled_datetime = timezone.now()
        self.save()
        return True

    def close(self):
        if self.bid_closed_datetime:
            return False
        self.bid_closed_datetime = timezone.now()
        self.save()
        return True


class Mission(models.Model):
    """
    미션 모델
    """
    code = models.CharField('미션코드', max_length=8, blank=True, default='', db_index=True)
    user = models.ForeignKey(User, verbose_name='회원', related_name='missions', on_delete=models.CASCADE)
    login_code = models.SlugField('외부 로그인 코드', max_length=32, blank=True, default='')
    mission_type = models.ForeignKey(MissionType, verbose_name='미션 타입', related_name='missions',
                                     on_delete=models.CASCADE, default=1)
    content = models.TextField('수행내용')
    due_datetime = models.DateTimeField('미션 일시', blank=True, null=True)
    is_due_date_modifiable = models.BooleanField('미션일자 수정가능', blank=True, default=False)
    is_due_time_modifiable = models.BooleanField('미션시간 수정가능', blank=True, default=False)
    stopovers = models.ManyToManyField(Address, verbose_name='경유지', related_name='stopover_missions', blank=True)
    final_address = models.ForeignKey(Address, verbose_name='최종 목적지', related_name='final_address_missions',
                                      null=True, blank=True, on_delete=models.SET_NULL)
    request_areas = models.ManyToManyField(Area, verbose_name='요청 지역', blank=True)
    template = models.ForeignKey('MissionTemplate', verbose_name='템플릿', null=True, blank=True, related_name='missions',
                                 on_delete=models.SET_NULL)
    template_data = JSONField('템플릿 데이터', blank=True, default=list)
    product = JSONField('제품 정보', blank=True, default=list)
    budget = models.IntegerField('예산', blank=True, default=0)
    amount_high = models.IntegerField('최고가', null=True, default=0)
    amount_low = models.IntegerField('최저가', null=True, default=0)
    is_point_reward = models.BooleanField('포인트 보상', blank=True, default=False)
    charge_rate = models.SmallIntegerField('수수료율', blank=True, default=10)
    created_datetime = models.DateTimeField('작성 일시', auto_now_add=True)
    requested_datetime = models.DateTimeField('요청 일시', blank=True, null=True)
    canceled_datetime = models.DateTimeField('취소일시', blank=True, null=True)
    canceled_detail = models.TextField('취소 상세내용', blank=True, default='')
    bid_closed_datetime = models.DateTimeField('입찰종료일시', blank=True, null=True)
    bid_limit_datetime = models.DateTimeField('입찰제한일시', blank=True, null=True)
    is_at_home = models.BooleanField('홈 화면 노출여부', blank=True, default=False)
    image_at_home = models.ImageField('홈 화면 이미지', null=True, blank=True)
    # todo: 홈에 들어갈 내용은 별도 테이블로 분리하는 것이 여러모로 나을 것 같음. 어차피 기본적으로 캐싱을 해서 성능 이슈에서도 매우 자유롭기 때문에,
    # todo: 일단은 이렇게 적용해두고 별도로 분리 작업 할 것.
    # todo: 또는, 미션의 카테고리화가 추가될 경우 카테고리별로 이미지를 지정하는 것도 고려해볼 수 있을 것임.
    push_result = models.OneToOneField('notification.Notification', verbose_name='푸쉬 결과', null=True, blank=True,
                                       related_name='mission', on_delete=models.CASCADE)
    saved_state = models.ForeignKey(State, verbose_name='상태', blank=True, default='draft', to_field='code',
                                    related_name='missions', on_delete=models.SET_DEFAULT)

    objects = MissionQuerySet.as_manager()
    # objects = MissionManager()

    class Meta:
        verbose_name = '미션'
        verbose_name_plural = '미션'

    def __str__(self):
        return '[%s] %s' % (str(self.mission_type), self.code)

    def save(self, *args, **kwargs):
        self.set_state(save=False)
        return super(Mission, self).save(*args, **kwargs)

    def handle_image_at_home(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_timestamp()
        return file.save(to='image_at_home')

    def get_content_shorten(self, length):
        return self.content.replace('\n', '')[:length] + ('...' if len(self.content) > length else '')

    @property
    def is_web(self):
        return bool(self.login_code)

    @property
    def is_multi(self):
        return False

    @property
    def shortened_url(self):
        if self.is_web:
            return 'https://%s/t/%s/' % (settings.SHORTEN_HOST, short_url.encode_url(self.id))
        if hasattr(self, 'external'):
            return self.external.shortened_url
        return ''

    @property
    def url(self):
        if self.is_web:
            return '%s?code=%s' % (settings.WEB_MISSION_DETAIL_URL, self.login_code)
        return ''

    @property
    def content_short(self):
        if self.template:
            return self.template.name
        return self.get_content_shorten(7)

    @property
    def is_amount_fixed(self):
        return self.amount_high and self.amount_low and self.amount_high == self.amount_low

    @property
    def is_timeout(self):
        return bool(self.bid_limit_datetime and self.bid_limit_datetime < timezone.now())

    @property
    def external_bids(self):
        if self.state == 'bidding':
            return self.bids.filter(saved_state='applied')
        if self.state == 'in_action':
            return self.bids.filter(saved_state='in_action')
        return self.bids.all()

    @property
    def assigned_bids(self):
        return self.bids.filter(is_assigned=True)

    @property
    def assigned_bid_ids(self):
        return self.assigned_bids.values_list('id', flat=True)

    @property
    def is_bidded(self):
        return self.bids.filter(_canceled_datetime__isnull=True, applied_datetime__isnull=False).exists()

    @property
    def bidded_count(self):
        return self.bids.filter(_canceled_datetime__isnull=True, applied_datetime__isnull=False).count()

    @property
    def bidded_lowest(self):
        lowest = self.bids.filter(_canceled_datetime__isnull=True, applied_datetime__isnull=False)\
            .order_by('amount').first()
        return lowest.amount if lowest else 0

    @property
    def won(self):
        return self.bids.filter(won_datetime__isnull=False)

    @property
    def active_bid(self):
        return self.won.filter(_canceled_datetime__isnull=True).last()

    @property
    def active_bid_amount(self):
        return self.active_bid.amount if self.active_bid else 0

    @property
    def helper(self):
        return self.won.last().helper if self.won.exists() else None

    @property
    def mean_amount(self):
        return self.bids.aggregate(models.Avg('amount')).values()

    @property
    def won_amount(self):
        return self.won.last().amount if self.won.exists() else None

    @property
    def can_cancel(self):
        return bool(self.state in ('bidding', 'waiting_assignee'))

    @property
    def active_due(self):
        # todo: 일대다 설계 적용시 수정할 것.
        return self.won[0].active_due if self.won else self.due_datetime

    @property
    def final_address_area_id(self):
        return self.final_address.area_id if self.final_address else None

    @property
    def due_datetime_string(self):
        if not self.due_datetime:
            return ''
        today = timezone.now().date()
        if self.due_datetime.date() == today:
            due_date = '오늘'
        elif self.due_datetime.date() == today + timezone.timedelta(days=1):
            due_date = '내일'
        else:
            due_date = self.due_datetime.strftime('%m월 %d일')
        return due_date + self.due_datetime.strftime(' %H시 %M분까지')

    @property
    def bid_canceled_datetime(self):
        return self.won[0].canceled_datetime if self.won else self.canceled_datetime

    @property
    def bid_done_datetime(self):
        return self.won[0].done_datetime if self.won else None

    @property
    def template_data_answers(self):
        return [data['val'] for data in self.template_data]

    @property
    def warnings(self):
        return KeywordWarning().check(list_to_concat_string(self.template_data_answers) if self.template else self.content)

    @property
    def customer_coupon_used(self):
        return -sum([w.customer_coupon_used for w in self.won]) or 0

    @property
    def customer_paid(self):
        return sum([w.customer_paid for w in self.won])

    @property
    def customer_point_used(self):
        return -sum([w.customer_point_used for w in self.won])

    @property
    def all_request_area_ids(self):
        return list(set(
            list(self.stopovers.values_list('area_id', flat=True)) + \
            ([self.final_address.area_id] if self.final_address else [])
        ))

    @property
    def all_request_area_names(self):
        return Area.objects.filter(id__in=self.all_request_area_ids).values_list('name', flat=True)

    @property
    def timeline(self):
        events = []
        if self.created_datetime:
            events.append([self.created_datetime, self.user, '미션 작성'])
        if self.requested_datetime:
            events.append([self.requested_datetime, self.user, '미션 요청'])
        if self.canceled_datetime:
            canceled_msg = '미션 취소' + ((' (%s)' % self.canceled_detail) if self.canceled_detail else '')
            events.append([self.canceled_datetime, self.user, canceled_msg])
        if self.bid_closed_datetime:
            events.append([self.bid_closed_datetime, self.user, '미션 입찰종료'])
        if self.get_state_code() == 'timeout_canceled':
            events.append([self.bid_limit_datetime, self.user, '미션 시간초과'])
        for bid in self.bids.all():
            if bid.applied_datetime:
                events.append([bid.applied_datetime, bid.helper.user, '미션 입찰'])
            if bid.won_datetime:
                events.append([bid.won_datetime, bid.helper.user, '낙찰'])
            if bid._canceled_datetime:
                events.append([bid._canceled_datetime, bid.helper.user, '취소' + (' (관리자)' if bid._canceled_by_admin else '')])
            if bid._done_datetime:
                events.append([bid._done_datetime, bid.helper.user, '미션 완료'])
            if bid._anytalk_closed_datetime:
                events.append([bid._anytalk_closed_datetime, '-', '애니톡 종료'])
        #todo: 인터랙션 추가
        return sorted(events, key=lambda t: t[0])

    @property
    def state(self):
        """미션 상태"""
        return self.saved_state.code

    def set_state(self, save=True):
        try:
            self.saved_state_id = self.get_state_code()
        except:
            return False
        if save:
            self.save()

    def get_state_code(self):
        if not self.requested_datetime:
            return 'draft'  # 미션 작성이 완료되지 않음
        if not self.bid_closed_datetime:
            if self.canceled_datetime:
                return 'user_canceled'  # 낙찰 전 취소
            if self.is_timeout:
                return 'timeout_canceled'  # 시간제한 취소
            else:
                return 'bidding'  # 입찰중
        else:
            if self.active_bid:
                return self.active_bid.state
            elif self.won.exists():
                return self.won.last().state
            elif self.assigned_bid_ids:
                if self.is_timeout:
                    return 'timeout_canceled'  # 시간제한 취소
                if self.canceled_datetime:
                    return 'user_canceled'  # 낙찰 전 취소
                return 'waiting_assignee'  # 지정 헬퍼 입찰대기
        return 'unknown'

    def get_state_display(self):
        status = dict(MISSION_STATUS)
        if type(self.state) is list:
            return [status[s] for s in self.state]
        return status[self.state]
    get_state_display.short_description = '미션 상태'

    def request(self):
        if self.due_datetime and self.due_datetime < timezone.now():
            return False
        # if self.requested_datetime:
        #     return False
        self.requested_datetime = timezone.now()
        self.charge_rate = self.mission_type.charge_rate
        if self.mission_type.bidding_limit:
            self.bid_limit_datetime = self.requested_datetime \
                                      + timezone.timedelta(minutes=self.mission_type.bidding_limit)
        self.save()

        # 푸쉬 & 로그
        if self.assigned_bids.exists():
            for assigned_bid in self.assigned_bids:
                if assigned_bid.helper.is_mission_request_push_allowed_now:
                    self.push_result = self.push_request(assigned_bid)
                log_with_reason(self.user, self, 'changed',
                                '"%s" 미션 요청 (헬퍼 지정 : %s)' % (self.content_short, str(assigned_bid.helper)))
        else:
            self.push_result = self.push_request()
            log_with_reason(self.user, self, 'changed', '"%s" 미션 요청' % self.content_short)

        self.save()
        return True

    def push_request(self, assigned_bid=None):
        if assigned_bid:
            # return Notification.objects.push_preset(assigned_bid.helper.user, 'assigned_mission_requested',
            #                                         [self.user.username], kwargs={'obj_id': assigned_bid.mission.id})
            return Tasker.objects.task('assigned_mission_requested', user=assigned_bid.helper.user,
                                       kwargs={'sender': self.user.username}, data={'obj_id': assigned_bid.mission.id})
        if self.all_request_area_ids:
            return Notification.objects.push_preset(self.all_request_area_ids, 'mission_requested',
                                                    args=['/'.join(self.all_request_area_names), self.due_datetime_string],
                                                    title='애니맨 미션 알림', sender=self.user, lazy=True)
        else:
            return Notification.objects.push_preset('online_helper', 'mission_requested', title='애니맨 미션 알림',
                                                    args=['원격', self.due_datetime_string], sender=self.user, lazy=True)
            # LoggedInDevice = apps.get_model('accounts', 'LoggedInDevice')
            # tokens = list(LoggedInDevice.objects.get_logged_in().get_online_available().exclude(user_id=self.user_id)
            #               .get_push_allowed().values_list('push_token', flat=True).distinct('push_token'))
            # return Notification.objects.push_preset(tokens, 'mission_requested', args=['원격', self.due_datetime_string],
            #                                         sender=self.user, lazy=True)

    def cancel(self, detail=''):
        if not self.can_cancel:
            return False
        self.canceled_datetime = timezone.now()
        self.canceled_detail = detail
        self.save()
        for bid in self.bids.all():
            bid.set_state()
        return True

    def close(self):
        self.bid_closed_datetime = timezone.now()
        self.save()
        for bid in self.bids.all():
            bid.set_state()
        return True


class MissionFile(models.Model):
    """
    미션 수행 관련 파일 모델
    """
    mission = models.ForeignKey(Mission, verbose_name='미션', related_name='files', on_delete=models.CASCADE)
    attach = models.FileField('파일')

    class Meta:
        verbose_name = '미션 수행 관련 파일'
        verbose_name_plural = '미션 수행 관련 파일'

    def __str__(self):
        return '%s.%s' % (self.mission_id, self.id)

    def handle_attach(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_parent('mission_id').with_timestamp()
        return file.save(to='attach')


class Bid(models.Model):
    """
    미션 입찰 모델
    """
    mission = models.ForeignKey(Mission, verbose_name='미션', related_name='bids', null=True, blank=True,
                                on_delete=models.CASCADE)
    area_mission = models.ForeignKey(MultiAreaMission, verbose_name='지역미션', related_name='bids',
                                     null=True, blank=True, on_delete=models.CASCADE)
    helper = models.ForeignKey(Helper, verbose_name='헬퍼', related_name='bids', on_delete=models.CASCADE)
    amount = models.IntegerField('입찰가', blank=True, default=0)
    is_assigned = models.BooleanField('지정 미션 여부', blank=True, default=False)
    content = models.TextField('고객에게 한마디', blank=True, default='')
    latitude = models.FloatField('위도', null=True, blank=True)
    longitude = models.FloatField('경도', null=True, blank=True)
    location = models.CharField('입찰시 위치 행정동', blank=True, default='', max_length=100)
    cash = models.OneToOneField('payment.Cash', verbose_name='캐쉬', null=True, blank=True, related_name='bid',
                                on_delete=models.PROTECT)
    point = models.OneToOneField('payment.Point', verbose_name='포인트', null=True, blank=True, related_name='bid',
                                 on_delete=models.PROTECT)
    reward = models.ForeignKey('payment.Reward', verbose_name='리워드', null=True, blank=True, related_name='bids',
                                 on_delete=models.PROTECT)
    due_datetime = models.DateTimeField('미션 일시', blank=True, null=True)
    adjusted_due_datetime = models.DateTimeField('적용 미션 일시', blank=True, null=True)
    applied_datetime = models.DateTimeField('입찰일시', blank=True, null=True)
    customer_checked_datetime = models.DateTimeField('입찰 확인 일시', blank=True, null=True)
    won_datetime = models.DateTimeField('낙찰일시', blank=True, null=True)
    _canceled_datetime = models.DateTimeField('취소일시', blank=True, null=True)
    _canceled_by_admin = models.BooleanField('직권취소여부', blank=True, default=False)
    _done_datetime = models.DateTimeField('완료일시', blank=True, null=True)
    _anytalk_closed_datetime = models.DateTimeField('애니톡 종료일시', blank=True, null=True)
    _locked_datetime = models.DateTimeField('잠금일시', blank=True, null=True)
    saved_state = models.ForeignKey(State, verbose_name='상태', blank=True, default='not_applied', to_field='code',
                                    related_name='bids', on_delete=models.SET_DEFAULT)
    customer_safety_number = models.OneToOneField(SafetyNumber, verbose_name='고객 안심번호', null=True, blank=True,
                                                  on_delete=models.SET_NULL, related_name='customer_safety_number')
    helper_safety_number = models.OneToOneField(SafetyNumber, verbose_name='헬퍼 안심번호', null=True, blank=True,
                                                on_delete=models.SET_NULL, related_name='helper_safety_number')

    objects = BidQuerySet.as_manager()

    class Meta:
        verbose_name = '미션 입찰'
        verbose_name_plural = '미션 입찰'

    def __str__(self):
        return '[입찰] %s' % self._mission

    def save(self, *args, **kwargs):
        self.set_state(save=False)
        rtn = super(Bid, self).save(*args, **kwargs)
        self._mission.set_state()
        return rtn

    @property
    def _mission(self):
        return self.mission or self.area_mission

    @property
    def is_external(self):
        return self._mission.is_web or hasattr(self._mission, 'external')

    @property
    def active_due(self):
        if self.mission:
            return self.adjusted_due_datetime or self.due_datetime or self.mission.due_datetime
        else:
            return self.won_datetime  # todo: MultiAreaMission에 수행일시 추가할 때까지 임시조치

    @property
    def is_paid(self):
        return self.payment.get_paid_amount() >= self.amount  # 방어적으로 결제액이 큰 경우도 결제된 것으로 봄

    @property
    def is_canceled(self):
        """미션취소(낙찰 전 취소)나 입찰취소(낙찰 후 취소) 둘 중에 하나라도 있으면 취소된 것으로 판단"""
        return bool(self._mission.canceled_datetime or self._canceled_datetime)

    @property
    def canceled_datetime(self):
        return self._canceled_datetime or self._mission.canceled_datetime

    @property
    def done_datetime(self):
        return self._done_datetime

    @property
    def is_in_action(self):
        """수행중 여부"""
        return self.won_datetime and not self._done_datetime and not self.is_canceled

    @property
    def customer_coupon_used(self):
        return sum([p.coupon.calculate_discount(self) for p in self.payment.get_succeeded()])

    @property
    def customer_paid(self):
        if self.mission:
            return sum(self.payment.get_succeeded().values_list('amount', flat=True))
        else:
            return self.amount

    @property
    def customer_point_used(self):
        if self.mission:
            return sum([p for p in self.payment.get_succeeded().values_list('point__amount', flat=True) if p])
        else:
            return 0

    @property
    def customer_mobile(self):
        if self.customer_safety_number and self.customer_safety_number.is_active:
            return self.customer_safety_number.assigned_number
        return self.mission.user.mobile

    @property
    def helper_mobile(self):
        if self.helper_safety_number and self.helper_safety_number.is_active:
            return self.helper_safety_number.assigned_number
        return self.helper.user.mobile

    @property
    def done_requested(self):
        return self.interactions.filter(
            interaction_type=9,
            accepted_datetime__isnull=True,
            rejected_datetime__isnull=True,
            canceled_datetime__isnull=True,
        ).last()

    @property
    def state(self):
        """입찰 미션 상태"""
        return self.saved_state.code

    @property
    def state_class(self):
        return dict(MISSION_STATE_CLASSES)[self.state]

    def set_state(self, save=True):
        try:
            self.saved_state_id = self.get_state_code()
        except:
            return False
        if save:
            self.save()
        self._mission.set_state(save=save)

    def get_state_code(self):
        if self._locked_datetime:
            return 'applied'
        if self.done_datetime:
            if self.canceled_datetime:
                return 'done_and_canceled'  # 완료 후 취소
            else:
                return 'done'  # 완료
        if self.canceled_datetime:
            if self._canceled_by_admin:
                if self.applied_datetime:
                    return 'admin_canceled'  # 관리자 취소
                else:
                    return 'not_applied'  # 지정헬퍼 미입찰
            if self.won_datetime:
                return 'won_and_canceled'  # 낙찰 후 취소
            else:
                if self._mission.canceled_datetime:
                    return 'user_canceled'  # 낙찰 전 취소
                else:
                    return 'bid_and_canceled'  # 입찰 취소
        if self.won_datetime:
            return 'in_action'  # 수행중
        if self.applied_datetime:
            if self._mission.bid_closed_datetime and not self.is_assigned:
                return 'failed'  # 패찰
            if self.mission and self.mission.is_timeout:
                return 'timeout_canceled'
            return 'applied'  # 입찰중
        elif self.is_assigned:
            return 'waiting_assignee'  # 지정 헬퍼 입찰대기
        return 'unknown'

    @property
    def is_locked(self):
        return bool(self._locked_datetime)

    def lock(self):
        if self.get_state_code() == 'applied' and not self._mission.is_timeout:
            self._locked_datetime = timezone.now()
            self.save()
            return True
        return False

    def unlock(self):
        if self._locked_datetime:
            self._locked_datetime = None
            self.save()
            return True
        return False

    def get_state_display(self):
        return dict(MISSION_STATUS)[self.state]

    def get_location_display(self):
        location_array = self.location.split(' ')
        return ' '.join(location_array[-2:]) if len(location_array) > 1 else ''
    get_location_display.short_description = '입찰시 위치'
    get_location_display.admin_order_field = 'location'

    def cancel_bidding(self):
        """입찰 취소"""
        if (self.mission and self.state == 'applied') or (self.area_mission and self.state == 'in_action'):
            self._canceled_datetime = timezone.now()
            if self.area_mission and self.area_mission.bid_closed_datetime:
                self.area_mission.bid_closed_datetime = None
                self.area_mission.save()
            elif self.mission and self.is_assigned:
                self.unassign()
            self.save()
            return True
        return False

    def admin_cancel(self):
        """관리자 직권취소"""
        self.close_anytalk()

        if self._locked_datetime:
            return False

        if self._canceled_datetime:
            return False

        # 결제도 취소해야 하는 경우
        if self.state in ('in_action', 'done'):
            if not self.cancel_payment():
                return False
            if self.state == 'done' and not self.unfinish():
                return False
        self._canceled_datetime = timezone.now()
        self._canceled_by_admin = True
        if self.area_mission:
            self.area_mission.bid_closed_datetime = None
            self.area_mission.save()
        self.save()
        SafetyNumber.objects.unassign_pair_from_bid(self)
        return True

    def win(self):
        # if self.state != 'applied' or self.mission.is_timeout:
        #     return False

        self.won_datetime = timezone.now()
        self.save()

        # 애니톡 오픈
        self.open_anytalk()

        if self.mission:

            # 안심번호 할당
            SafetyNumber.objects.assign_pair_from_bid(self)

            # 패찰 알림
            failed_helper_users = list(User.objects.filter(helper__bids__mission=self.mission).exclude(helper=self.helper))
            if failed_helper_users:
                Notification.objects.push_preset(failed_helper_users, 'bidded_mission_failed',
                                                 args=[self.mission.content_short], lazy=True)
                # log_with_reason(bid.helper.user, bid, 'changed', '"%s" 미션 패찰' % self.mission.content_short)

            # logging
            msg = ['"%s" 미션 입찰 종료' % self.mission.content_short, '%s 낙찰' % str(self.helper)]
            for failed in failed_helper_users:
                msg.append('[헬퍼] %s 패찰' % failed)
            log_with_reason(self.mission.user, self, 'changed', msg)

            # 제휴사 템플릿 미션 매칭성공 url이 있는 경우 호출
            if self.mission.template and self.mission.template.partnership and self.mission.template.matching_success_url:
                try:
                    data = {'code': self.mission.code}
                    requests.get(self.mission.template.matching_success_url, params=data, timeout=1)
                except:
                    pass

        # Notification.objects.push_preset(self.helper.user, 'bidded_mission_matched',
        #                                  args=[self._mission.content_short],
        #                                  kwargs={'obj_id': self.id})
        Tasker.objects.task('bidded_mission_matched', user=self.helper.user,
                            kwargs={'mission': self._mission.content_short}, data={'obj_id': self.id})

        return True

    def win_single(self):
        if self.win():
            return self._mission.close()
        return False

    def finish(self, done_datetime=None):
        if self.cash or self._done_datetime:
            return False
        self._done_datetime = done_datetime or timezone.now()

        # 헬퍼 캐쉬 처리
        Cash = apps.get_model('payment', 'Cash')
        fee_rate = self.helper.fee_rate.fee if self.helper.fee_rate else self._mission.charge_rate
        cash_amount = int(self.amount * (100 - fee_rate) / 100) if self.mission else self.amount
        self.cash = Cash.objects.create(helper=self.helper, amount=cash_amount)

        if self.mission and not self.point:
            # 고객 미션완료 리워드 처리
            Reward = apps.get_model('payment', 'Reward')
            Point = apps.get_model('payment', 'Point')
            self.reward = Reward.objects.get_active('customer_finished_mission')
            if self.reward:
                point_amount = self.reward.calculate_reward(self.customer_paid)
                self.point = Point.objects.create(user=self.mission.user, amount=point_amount)

            # 협력사 추천 회원 추가 미션완료 리워드
            if self.mission.user.recommended_partner:
                reward_amount = self.mission.user.recommended_partner.reward_when_mission_done
                if reward_amount:
                    reward_count = self.mission.user.recommended_partner.reward_when_mission_done_count
                    query = {
                        'user': self.mission.user,
                        'memo': '[%s] 미션완료 추가 리워드' % self.mission.user.recommended_partner.name
                    }
                    # 리워드 회수 제한이 있는 경우에는 리워드 회수를 체크해서 리워드 여부 판단
                    if not reward_count or Point.objects.filter(**query).count() < reward_count:
                        Point.objects.create(**query, amount=reward_amount)

        if self.area_mission:
            # 미션 상태값 변경
            self.area_mission.save()

        # self.close_anytalk()
        # SafetyNumber.objects.unassign_pair_from_bid(self)
        self.save()

        if self.mission:
            done_count = self.mission.user.missions.done().count()
            # 추천인 미션 완료 리워드
            if self.mission.user.recommended_user:
                msg = '미션완료'
                if self.mission.user.recommended_user.is_helper:
                    reward_type = 'helper_recommend_done'
                    RewardTargetModel = apps.get_model('payment', 'Cash')
                    query = {'helper': self.mission.user.recommended_user.helper}
                else:
                    reward_type = 'customer_recommend_done'
                    RewardTargetModel = apps.get_model('payment', 'Point')
                    query = {'user': self.mission.user.recommended_user}
                if done_count == 1:
                    reward_type += '_first'
                    msg = '첫 미션완료'
                Reward = apps.get_model('payment', 'Reward')
                reward = Reward.objects.get_active(reward_type)
                if reward:
                    reward_amount = reward.calculate_reward(self.amount)

                    if reward_amount:
                        # 추천인 리워드 처리
                        query.update({'amount': reward_amount, 'memo':'[친구초대] %s (%s)' % (msg, self.mission.code)})
                        if not RewardTargetModel.objects.filter(**query).exists():
                            RewardTargetModel.objects.create(**query)
                            # 리워드 푸쉬 처리
                            # Notification.objects.push_preset(self.mission.user.recommended_user, 'rewarded_' + reward_type,
                            #                              args=[add_comma(reward_amount)])
                            Tasker.objects.task('rewarded_' + reward_type, user=self.mission.user.recommended_user,
                                                kwargs={'amount': add_comma(reward_amount)})

            # 첫 미션 완료
            if done_count == 1:
                Tasker.objects.task('first_mission_done', user=self.mission.user)
            else:
                # 기간 내에 2회 완료했는지 조건검사후 태스크 수행
                Tasker.objects.check_and_run_peoriod_task('2nd_mission_done_in_peoriod', user=self.mission.user)

        return True

    def unfinish(self, by_admin=True):
        """완료된 미션의 기지급된 캐쉬와 포인트를 환수하고 미션 상태를 취소로 변경"""
        if self.state != 'done':
            return False

        # 헬퍼에게 이미 캐쉬가 지급된 경우 캐쉬 회수
        if self.cash:
            Cash = apps.get_model('payment', 'Cash')
            cash = Cash.objects.create(helper=self.helper, amount=-self.cash.amount, _detail=self._mission.code)

        # 결제시 사용된 포인트가 있는 경우 포인트 환불
        if self.point:
            Point = apps.get_model('payment', 'Point')
            point = Point.objects.create(user=self.mission.user, amount=-self.point.amount, _detail=self._mission.code)

        # 추천인 완료 리워드 회수
        if self.mission and self.mission.user.recommended_user:
            if self.mission.user.recommended_user.is_helper:
                RewardTargetModel = apps.get_model('payment', 'Cash')
                user_query = {'helper': self.mission.user.recommended_user.helper}
            else:
                RewardTargetModel = apps.get_model('payment', 'Point')
                user_query = {'user': self.mission.user.recommended_user}
            rewarded = RewardTargetModel.objects.filter(**user_query, memo__icontains='미션완료 (%s)' % self.mission.code).last()
            if rewarded:
                RewardTargetModel.objects.create(**user_query, amount=rewarded.amount,
                                                 memo='[친구초대] 미션취소 (%s)' % self.mission.code)

        # 미션 취소 처리
        self._canceled_datetime = timezone.now()
        self._canceled_by_admin = by_admin
        self.reopen_anytalk()
        try:
            SafetyNumber.objects.assign_pair_from_bid(self)
        except:
            print('안심번호 할당 오류')
        self.save()
        return True

    def cancel_payment(self):
        """결제내역 취소"""
        # 카드 결제 취소 (카드 결제가 있는 경우 결제취소가 안 되면 미션 취소도 안 됨)
        result = True
        for paid in self.payment.get_paid():
            if not paid.cancel():
                result = False
        return result

    def unassign(self):
        """지정미션 지정 취소 : 일반 미션으로 전환"""
        if not self.mission or not self.is_assigned:
            return None
        self.is_assigned = False
        if not self._canceled_datetime:
            self._canceled_datetime = timezone.now()
            self._canceled_by_admin = True
        self.save()
        self.mission.bid_closed_datetime = None
        self.mission.push_result = self.mission.push_request()
        self.mission.save()
        log_with_reason(self.mission.user, self.mission, 'changed',
                        '"%s" 미션 헬퍼지정 취소에 의한 전체요청' % self.mission.content_short)

    def open_anytalk(self):
        anytalk.open(self)

    def reopen_anytalk(self):
        anytalk.reopen(self.id)

    def close_anytalk(self):
        anytalk.close(self.id)
        self._anytalk_closed_datetime = timezone.now()
        self.save()


class BidFile(models.Model):
    """
    미션 수행중 애니톡 교환 파일 모델
    """
    bid = models.ForeignKey(Bid, verbose_name='입찰', related_name='files', on_delete=models.CASCADE)
    attach = models.FileField('파일')
    created_user = models.ForeignKey(User, verbose_name='작성자', related_name='bid_files', on_delete=models.CASCADE)
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)

    class Meta:
        verbose_name = '미션 수행중 애니톡 교환 파일'
        verbose_name_plural = '미션 수행중 애니톡 교환 파일'

    def __str__(self):
        return self.attach.file.name

    def handle_attach(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_parent('bid_id').with_timestamp()
        return file.save(to='attach')


class Interaction(models.Model):
    """
    미션 인터랙션 모델
    """
    INTERACTION_TYPES = (
        (1, '취소'),
        # (3, '지정입찰'),
        (5, '일시변경'),
        (9, '완료'),
    )

    bid = models.ForeignKey(Bid, verbose_name='입찰', related_name='interactions', on_delete=models.CASCADE)
    created_user = models.ForeignKey(User, verbose_name='작성자', related_name='interactions', on_delete=models.CASCADE)
    interaction_type = models.PositiveSmallIntegerField('미션 인터랙션', choices=INTERACTION_TYPES)
    detail = models.TextField('상세 내용', blank=True)
    requested_datetime = models.DateTimeField('요청 일시', auto_now_add=True)
    accepted_datetime = models.DateTimeField('수락 일시', blank=True, null=True)
    rejected_datetime = models.DateTimeField('거절 일시', blank=True, null=True)
    canceled_datetime = models.DateTimeField('취소 일시', blank=True, null=True)

    class Meta:
        verbose_name = '미션 인터랙션'
        verbose_name_plural = '미션 인터랙션'

    def __str__(self):
        return '[%s] %s' % (dict(self.INTERACTION_TYPES)[self.interaction_type], self.bid)

    def save(self, *args, **kwargs):
        if self.state == 'accepted':
            # 취소 확정시
            if self.interaction_type == 1:
                # 결제 취소
                # - 카드 결제가 있는 경우 결제취소가 안 되면 미션 취소도 안 됨
                if self.bid.cancel_payment():
                    self.bid._canceled_datetime = self.accepted_datetime
                    self.bid.save()
                    SafetyNumber.objects.unassign_pair_from_bid(self.bid)
                else:
                    self.accepted_datetime = None
                    self.save()
                self.bid.close_anytalk()

            # 일시변경 확정시
            if self.interaction_type == 5:
                self.bid.adjusted_due_datetime = dateutil.parser.parse(self.detail)
                self.bid.save()

            # 완료 확정시
            if self.interaction_type == 9:
                if self.bid.saved_state.code == 'in_action':
                    if self.bid.finish(self.accepted_datetime):
                        self.bid.save()
                    else:
                        self.accepted_datetime = None
                        self.save()
                else:
                    self.accepted_datetime = None
                    self.save()
        return super(Interaction, self).save(*args, **kwargs)

    @property
    def is_created_user_helper(self):
        return self.created_user_id == self.bid.helper.user_id

    @property
    def receiver(self):
        if self.is_created_user_helper:
            return self.bid._mission.user
        return self.bid.helper.user

    @property
    def state(self):
        if self.canceled_datetime:
            return 'canceled'
        if self.accepted_datetime:
            return 'accepted'
        if self.rejected_datetime:
            return 'rejected'
        return 'requested'

    def get_interaction_type_display(self):
        return dict(self.INTERACTION_TYPES)[self.interaction_type]

    def accept(self):
        if self.state == 'requested':
            self.accepted_datetime = timezone.now()
            self.save()
            return bool(self.accepted_datetime is not None)
        return False

    def cancel(self):
        if self.state == 'requested':
            self.canceled_datetime = timezone.now()
            self.save()
            return True
        return False

    def reject(self):
        if self.state == 'requested':
            self.rejected_datetime = timezone.now()
            self.save()
            return True
        return False


class Review(models.Model):
    """
    리뷰 모델
    """
    bid = models.ForeignKey(Bid, verbose_name='입찰', related_name='reviews', null=True, blank=True,
                            on_delete=models.CASCADE)
    _received_user = models.ForeignKey(User, verbose_name='수신자', related_name='received_all_reviews', null=True,
                                      blank=True, on_delete=models.SET_NULL)
    stars = ArrayField(
        models.PositiveSmallIntegerField(validators=[MaxValueValidator(5), MinValueValidator(1)]),
        verbose_name='별점',
        size=2,
    )
    content = models.TextField('내용', blank=True)
    cash = models.OneToOneField('payment.Cash', verbose_name='캐쉬', null=True, blank=True, related_name='review',
                                on_delete=models.PROTECT)
    point = models.OneToOneField('payment.Point', verbose_name='포인트', null=True, blank=True, related_name='review',
                                 on_delete=models.PROTECT)
    reward = models.ForeignKey('payment.Reward', verbose_name='리워드', null=True, blank=True, related_name='reviews',
                                 on_delete=models.PROTECT)
    created_datetime = models.DateTimeField('작성 일시', auto_now_add=True)
    created_user = models.ForeignKey(User, verbose_name='작성자', related_name='created_all_reviews',
                                     on_delete=models.CASCADE)
    _is_created_user_helper = models.NullBooleanField('작성자 헬퍼여부', null=True, blank=True, default=None)
    is_active = models.BooleanField('활성화', null=True, blank=True, default=True)

    objects = ReviewQuerySet.as_manager()

    class Meta:
        verbose_name = '리뷰'
        verbose_name_plural = '리뷰'

    def __str__(self):
        return self.get_stars_display()

    @property
    def star_avg(self):
        return '%.1f' % statistics.mean(self.stars) if self.stars else 0

    @property
    def star_avg_int(self):
        return int(self.star_avg)

    @property
    def star_text(self):
        return (
            '친절도 %s' % stars(self.stars[0]),
            '수행완성도 %s' % stars(self.stars[1]),
        )

    def get_stars_display(self):
        return ' / '.join([stars(s) for s in self.stars])
    get_stars_display.short_description = '별점'

    @property
    def is_created_user_helper(self):
        if self._is_created_user_helper is not None:
            return self._is_created_user_helper
        return self.created_user_id == self.bid.helper.user_id

    @property
    def received_user(self):
        if self._received_user:
            return self._received_user
        if self.is_created_user_helper:
            return self.bid._mission.user
        return self.bid.helper.user


class Report(models.Model):
    """
    신고 모델
    """
    mission = models.ForeignKey(Mission, verbose_name='미션', related_name='reports',
                                null=True, blank=True, on_delete=models.CASCADE)
    bid = models.ForeignKey(Bid, verbose_name='입찰', related_name='reports',
                            null=True, blank=True, on_delete=models.CASCADE)
    content = models.TextField('내용', blank=True)
    created_datetime = models.DateTimeField('작성 일시', auto_now_add=True)
    created_user = models.ForeignKey(User, verbose_name='작성자', related_name='created_reports',
                                     on_delete=models.CASCADE)

    objects = ReportQuerySet.as_manager()

    class Meta:
        verbose_name = '신고'
        verbose_name_plural = '신고'

    def __str__(self):
        # return dict(self.CATEGORIES)[self.category]
        return str(self.received_user)

    def save(self, *args, **kwargs):
        rtn = super(Report, self).save(*args, **kwargs)
        if self.mission and self.mission.reports.distinct('created_user').count() >= 5:
            reason = '신고 누적에 따른 자동 이용정지 (%s)' % self.mission.code
            if not self.mission.user.service_blocks.filter(reason=reason).exists():
                in_action = Bid.objects.filter(saved_state='in_action').filter(
                    models.Q(mission__user=self.mission.user)
                    | models.Q(helper__user=self.mission.user)
                )
                if in_action.exists():
                    # 진행중인 미션이 있는 경우에는 블럭 대신 알림만 발송
                    codes = list(in_action.distinct('mission_id').values_list('mission__code', flat=True))
                    anyman.slack.channel('anyman__17-1').script_msg(
                        '이용정지 유예 알림',
                        '%s 회원이 신고 누적으로 이용정지가 되어야 하나, 진행중인 미션(%s)이 있어서 유예됨.' % (self.mission.user, ', '.join(codes))
                    )
                else:
                    self.mission.user.block(days=7, reason=reason)
            if not self.mission.canceled_datetime and not self.mission.cancel():
                anyman.slack.channel('anyman__80dev').script_msg(
                    '신고누적 미션취소 오류 알림',
                    '미션 "%s"이 자동으로 취소되지 않음' % self.mission.code
                )
        return rtn

    @property
    def received_user(self):
        if self.bid:
            if self.created_user == self.bid.helper.user:
                return self.bid.mission.user
            return self.bid.helper.user
        return self.mission.user


class UserBlock(models.Model):
    """
    사용자 차단 모델
    """
    user = models.ForeignKey(User, verbose_name='차단된 회원', related_name='blocked_bys', on_delete=models.CASCADE)
    related_mission = models.ForeignKey(Mission, verbose_name='미션', related_name='related_blocks',
                                        null=True, blank=True, on_delete=models.SET_NULL)
    created_datetime = models.DateTimeField('차단 일시', auto_now_add=True)
    created_user = models.ForeignKey(User, verbose_name='작성자', related_name='blocks', on_delete=models.CASCADE)

    class Meta:
        verbose_name = '사용자 차단'
        verbose_name_plural = '사용자 차단'

    def __str__(self):
        return str(self.user)


class FavoriteUser(models.Model):
    """
    사용자 찜 모델
    """
    user = models.ForeignKey(User, verbose_name='찜된 회원', related_name='liked_bys', on_delete=models.CASCADE)
    created_datetime = models.DateTimeField('찜 일시', auto_now_add=True)
    created_user = models.ForeignKey(User, verbose_name='작성자', related_name='likes', on_delete=models.CASCADE)

    class Meta:
        verbose_name = '사용자 찜'
        verbose_name_plural = '사용자 찜'

    def __str__(self):
        return str(self.user)

    @property
    def helper(self):
        return self.user.helper


class PenaltyPoint(models.Model):
    """
    벌점 모델
    """
    REASONS = (
        (1, '욕설, 비난, 혐오성 발언'),
        (2, '개인적 연락 (만남시도)'),
        (3, '개인거래 유도'),
        (4, '추가비용 요구 (허위입찰)'),
        (5, '잠수 / No Show'),
        (6, '불성실 미션수행'),
        (7, '고객센터에 욕설, 비난, 혐오, 비방성 발언'),
        (8, '홍보, 광고용으로 사용'),
        (9, '불법/위험 미션 요청'),
        (99, '기타'),
    )
    user = models.ForeignKey(User, verbose_name='회원', related_name='penalty_points', on_delete=models.CASCADE)
    reason = models.SmallIntegerField('사유', choices=REASONS)
    point = models.SmallIntegerField('점수', default=0, validators=[MinValueValidator(-8), MaxValueValidator(8)])
    mission = models.ForeignKey(Mission, verbose_name='관련 미션', null=True, blank=True,
                                related_name='penalty_points', on_delete=models.CASCADE)
    detail = models.TextField('상세 사유')
    created_datetime = models.DateTimeField('부여 일시', auto_now_add=True)

    class Meta:
        verbose_name = '벌점'
        verbose_name_plural = '벌점'

    def __str__(self):
        return str(self.point)


class CustomerService(models.Model):
    """
    상담 내역
    """
    user = models.ForeignKey(User, verbose_name='회원', null=True, blank=True, related_name='customer_services',
                             on_delete=models.CASCADE)
    mission = models.ForeignKey(Mission, verbose_name='관련 미션', null=True, blank=True, on_delete=models.SET_NULL)
    content = models.TextField('내용')
    created_user = models.ForeignKey(User, verbose_name='작성자', related_name='created_cs', null=True,
                                     on_delete=models.SET_NULL)
    created_datetime = models.DateTimeField('상담 일시', auto_now_add=True)

    class Meta:
        verbose_name = '상담 내역'
        verbose_name_plural = '상담 내역'



"""
미션 템플릿
"""


class TemplateTagQuerySet(models.QuerySet):
    """
    탬플릿 태그 쿼리셋
    """
    def get_personalized(self, user):
        return self.order_by('-weight')[:12]


class TemplateCategoryQuerySet(models.QuerySet):
    """
    미션 템플릿 카테고리 쿼리셋
    """
    def orderable(self, *args):
        # todo: 정렬을 위한 임시조치. 수동 sql 추가할 것. (order by 에 collate “C” 추가)
        return self.annotate(order_name=Substr(Concat('parent__parent__name', 'parent__name', 'name'), 1, 2))\
            .order_by(*args, 'id')

    def root(self, *args, **kwargs):
        return self.filter(parent__isnull=True)

    def get_children(self, id=None, recursively=False):
        if not id:
            return self.root()
        if recursively:
            return self.filter(models.Q(parent_id=id) | models.Q(parent__parent_id=id) | models.Q(parent__parent__parent_id=id))
        else:
            return self.filter(parent_id=id)


import random  # 임시


class MissionTemplateQuerySet(models.QuerySet):
    """
    미션 템플릿 쿼리셋
    """
    def get_by_category(self, category_id):
        return self.filter(category_id=category_id, is_active=True)

    def get_active(self):
        return self.filter(is_active=True)

    def get_recent(self, limit=10):
        return self.get_active()[:10]

    def get_recommended(self, user, limit=10):
        # todo: 추천 알고리즘으로 변경할 것.
        ids = list(self.get_active().values_list('id', flat=True))
        # 간병인 임시 작업
        # return self.filter(id__in=random.sample(ids, limit))
        priority = list(self.filter(id__in=[83]))
        return priority + list(self.filter(id__in=random.sample(ids, limit-1)).order_by('-id'))

    def search(self, query):
        keywords = query.split(' ')
        templates_by_name = self.get_active()
        templates_by_tags = self.get_active()
        for keyword in keywords:
            templates_by_name = templates_by_name.filter(name__icontains=keyword)
            templates_by_tags = templates_by_tags.filter(tags__name__icontains=keyword)

        templates = (templates_by_name | templates_by_tags).distinct('id')
        return templates


class TemplateCategory(models.Model):
    """
    미션 템플릿 카테고리 모델
    """
    name = models.CharField('카테고리명', max_length=250)
    parent = models.ForeignKey('self', verbose_name='상위 카테고리', null=True, blank=True, related_name='children',
                               on_delete=models.CASCADE)

    objects = TemplateCategoryQuerySet.as_manager()

    class Meta:
        verbose_name = '템플릿 카테고리'
        verbose_name_plural = '템플릿 카테고리'

    def __str__(self):
        if self.parent:
            return '%s > %s' % (self.parent, self.name)
        return self.name

    @property
    def fullname(self):
        return self.__str__()

    @property
    def depth(self):
        rtn = 1
        p = self.parent
        while p:
            rtn += 1
            p  = p.parent
        return rtn


class TemplateTag(models.Model):
    """
    미션 템플릿 태그 모델
    """
    name = models.CharField('태그명', max_length=20, unique=True)
    synonyms = ArrayField(models.CharField(max_length=20), verbose_name='동의어', blank=True,
                          help_text='쉽표로 구분합니다.')
    image = models.ImageField('태그 이미지', null=True, blank=True)
    weight = models.SmallIntegerField('가중치', blank=True, default=0)

    objects = TemplateTagQuerySet.as_manager()

    class Meta:
        verbose_name = '태그'
        verbose_name_plural = '태그'

    def __str__(self):
        return '#%s' % self.name

    @property
    def strings(self):
        return self.synonyms + [self.name]

    def save(self, *args, **kwargs):
        return super(TemplateTag, self).save(*args, **kwargs)

    def handle_image(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_timestamp()
        return file.save(to='image')

    def get_image_display(self):
        return mark_safe('<img src="%s" />' % self.image.url) if self.image else ''
    get_image_display.short_description = '템플릿 이미지'
    get_image_display.admin_order_field = 'image'


class MissionTemplate(models.Model):
    """
    미션 템플릿 모델
    """
    category = models.ForeignKey(TemplateCategory, verbose_name='템플릿 카테고리', related_name='templates',
                                 on_delete=models.CASCADE)
    tags = models.ManyToManyField(TemplateTag, verbose_name='태그', blank=True, related_name='templates')
    partnership = models.ForeignKey('biz.Partnership', verbose_name='협력사 전용', null=True, blank=True, 
                                    on_delete=models.SET_NULL, related_name='templates')
    auto_stopover_address = models.ForeignKey(Address, verbose_name='자동입력 경유지', null=True, blank=True, on_delete=models.SET_NULL)
    matching_success_url = models.URLField('헬퍼 매칭 성공시 호출 URL', blank=True, default='')
    name = models.CharField('템플릿 이름', max_length=250)
    description = models.TextField('템플릿 설명')
    image = models.ImageField('템플릿 이미지', null=True, blank=True)
    mission_type = models.ForeignKey(MissionType, verbose_name='미션 타입', related_name='templates',
                                     on_delete=models.CASCADE, default=1)
    is_active = models.BooleanField('활성화', blank=True, default=True)
    content_display = models.TextField('미션내용 표시', blank=True, default='', help_text='질문에 들어가는 항목 이름으로 미션을 자유롭게 표시할 수 있습니다.')

    objects = MissionTemplateQuerySet.as_manager()

    class Meta:
        verbose_name = '템플릿'
        verbose_name_plural = '템플릿'

    def __str__(self):
        return '[%s] %s' % (self.category, self.name)

    def clean_fields(self, exclude=None):
        super(MissionTemplate, self).clean_fields(exclude=exclude)
        if self.content_display:
            test_data = {f:'t' for f in self.field_names}
            try:
                self.content_display.format(**test_data)
            except:
                raise ValidationError('입력한 항목 이름이 올바른지 확인하세요. 항목 이름에는 띄어쓰기도 구분합니다.')

    @property
    def ordered_questions(self):
        return self.questions.order_by('order_no', 'id')

    @property
    def fields(self):
        return self.ordered_questions.values('id', 'question_type', 'name', 'is_required')

    @property
    def field_names(self):
        return list(self.ordered_questions.values_list('name', flat=True))

    @property
    def fields_for_api(self):
        rtn = []
        trans = {
            'due_datetime': 'datetime',
            'final_address': 'text',
            'product': 'array',
            'stopovers': 'array',
            '': '',
        }
        for field in self.fields:
            if field['question_type'] in trans:
                field['question_type'] = trans[field['question_type']]
            rtn.append(field)
        return rtn

    @property
    def tag_list(self):
        tags = []
        for tag in self.tags.all():
            tags += tag.strings
        return tags

    @property
    def slug(self):
        return re.sub('[^A-Za-z0-9가-힣]', '-', self.name)

    @property
    def content_display_html(self):
        return mark_safe(self.content_display.replace('{', '<span style="color: red; font-style: italic;">{').replace('}', '}</span>'))

    def get_content_display_rendered(self, template_data):
        if self.content_display:
            data = {}
            for item in template_data:
                data.update({item['name']: item['val']})
            try:
                return self.content_display.format(**data)
            except:
                pass
        return '[' + self.name + ']\r\n\r\n' + '\r\n'.join(['{name} : {val}'.format(**t) for t in template_data])

    def to_mission_data(self, values, **kwargs):
        if len(values) != len(self.fields):
            return Errors.fields_invalid

        template_data = []
        object_data = {}
        for field, val in zip(self.fields, values):
            if field['is_required'] and not val:
                return Errors.missing_required_field(field['name'])

            if hasattr(Mission, field['question_type']):
                if val:
                    # 경유지 주소에 대해 포맷팅 추가
                    if field['question_type'] == 'stopovers' and type(val) in (list, tuple) and type(val[0]) == str:
                        new_val = []
                        for address in val:
                            area_id, detail_1 = Area.objects.search(address)
                            new_val.append({'area': area_id, 'detail_1': detail_1})
                        val = new_val

                    # 최종 목적지 주소에 대해 포맷팅 추가
                    if field['question_type'] == 'final_address' and type(val) == str:
                        area_id, detail_1 = Area.objects.search(val)
                        val = {'area': area_id, 'detail_1': detail_1}

                    object_data.update({
                        field['question_type']: val
                    })
            else:
                data = {
                    'id': field['id'],
                    'name': field['name'],
                }
                if field['question_type'] == 'files':
                    data.update({'val': (val + '개') if val else '없음'})
                elif type(val) is dict:
                    data.update({'origin': val, 'val': self._get_object_display(val)})
                elif type(val) is list:
                    data.update({'origin': val, 'val': ', '.join(val)})
                else:
                    data.update({'val': val or ''})
                template_data.append(data)
        object_data.update({
            'mission_type': self.mission_type_id,
            'template_data': template_data,
            'content': self.get_content_display_rendered(template_data),
        })
        object_data.update(kwargs)
        return object_data

    def _get_object_display(self, val):
        if 'area' in val and 'detail_1' in val:
            # 주소
            return ' '.join((str(Area.objects.get(id=val['area'])), val['detail_1'], val['detail_2'])).strip()
        if 'id' in val and 'nearby' in val and 'parent' in val:
            # 지역
            return str(Area.objects.get(id=val['id']))
        return val

    def handle_image(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_timestamp()
        return file.save(to='image')

    def get_image_display(self):
        return mark_safe('<img src="%s" />' % self.image.url) if self.image else ''
    get_image_display.short_description = '템플릿 이미지'
    get_image_display.admin_order_field = 'image'


class TemplateQuestion(models.Model):
    """
    미션 템플릿 질문 모델
    """
    QUESTION_TYPES = (
        ('radio', '라디오 (1개 선택)'),
        ('checkbox', '체크박스 (다중 선택)'),
        ('number', '숫자 입력'),
        ('text', '단답형 문자'),
        ('textarea', '장문'),
        ('area', '지역'),
        ('address', '주소'),
        ('datetime', '날짜와 시간'),
        ('date', '날짜'),
        ('time', '시간'),
        ('files', '파일 첨부'),

        ('due_datetime', '미션 일시'),
        ('stopovers', '경유지'),
        ('final_address', '최종 목적지'),

        ('product', '제품 정보'),
        # ('budget', '고객 예산'),  # memo: 템플릿에 적용 필요
    )
    template = models.ForeignKey(MissionTemplate, verbose_name='템플릿', related_name='questions', on_delete=models.CASCADE)
    order_no = models.PositiveSmallIntegerField('순번', blank=True, default=10)
    question_type = models.CharField('유형', choices=QUESTION_TYPES, max_length=20)
    name = models.CharField('항목 이름', max_length=250)
    title = models.CharField('질문 제목', max_length=250)
    description = models.TextField('질문 설명')
    options = models.TextField('선택 항목', blank=True, help_text='줄바꿈(엔터)으로 각 항목을 구분하세요. 각 항목에 대한 설명이 필요한 경우 ":"를 붙여서 작성하세요.')
    has_etc_input = models.BooleanField('직접입력(기타) 추가', blank=True, default=False)
    is_required = models.BooleanField('필수 입력 여부', blank=True, default=False)

    class Meta:
        verbose_name = '템플릿 질문'
        verbose_name_plural = '템플릿 질문'

    def __str__(self):
        return '[%s] %s' % (self.question_type, self.name)

    @property
    def select_options(self):
        option_list_to_dict = lambda o: {o[0]: o[1] if len(o) > 1 else ''}
        return [option_list_to_dict(o.split(':')) for o in self.options.split('\r\n') if o]


class TemplateKeywordQuerySet(models.QuerySet):
    """
    템플릿 키워드 쿼리셋
    """
    def search(self, user, query):
        user_id = user.id if user.is_authenticated else None
        self.create(name=query, user_id=user_id)
        return MissionTemplate.objects.search(query)

    def save_result(self, user, keywords, selected_id=None):
        obj = None
        user_id = user.id if user.is_authenticated else None
        for keyword in keywords:
            obj = self.create(name=keyword, user_id=user_id)
        if obj and selected_id:
            try:
                obj.template_id = selected_id
                obj.save()
            except: pass
        return obj


class TemplateKeyword(models.Model):
    """
    템플릿 검색 키워드 모델
    """
    name = models.CharField('키워드', max_length=20)
    template = models.ForeignKey(MissionTemplate, verbose_name='선택 템플릿', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='searched_keywords')
    user = models.ForeignKey(User, verbose_name='회원', null=True, blank=True, related_name='keywords',
                             on_delete=models.SET_NULL)
    created_datetime = models.DateTimeField('검색일시', auto_now_add=True)

    objects = TemplateKeywordQuerySet.as_manager()

    class Meta:
        verbose_name = '키워드'
        verbose_name_plural = '키워드'

    def __str__(self):
        return self.name

