import random
from audioop import reverse

from django.apps import apps
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib.auth.hashers import (
    check_password, is_password_usable, make_password,
)

from base.constants import USER_CODE_STRINGS
from common.utils import UploadFileHandler, get_md5_hash
from common.exceptions import Errors
from accounts.models import Area


"""
CONSTANTS
"""


HELPER_HOME = 1
CUSTOMER_HOME = 2
WEB_HOME = 3

LOCATIONS = (
    (HELPER_HOME, '[APP] 헬퍼홈'),
    (CUSTOMER_HOME, '[APP] 고객홈'),
    (WEB_HOME, '[WEB] 메인홈'),
)

LOCATION_IMAGE_SIZES = (
    (HELPER_HOME, (984, 246)),
    (CUSTOMER_HOME, (1080, 540)),
    (WEB_HOME, (1280, 300)),
)

REQUEST_ACCEPT_STATUS = (
    ('requested', '신청됨'),
    ('activated', '활성화'),
    ('deactivated', '비활성화'),
    ('rejected', '반려됨'),
)

REQUEST_ACCEPT_STATUS_FILTERS = {
    'requested': {'is_active': True, 'accepted_datetime__isnull': True, 'rejected_datetime__isnull': True},
    'activated': {'is_active': True, 'accepted_datetime__isnull': False, 'rejected_datetime__isnull': True},
    'rejected': {'is_active': True, 'rejected_datetime__isnull': False},
    'deactivated': {'is_active': False}
}

CAMPAIGN_TYPES = [
    (1, '설문조사'),
    (2, 'CPA'),
]


"""
Querysets
"""


class PartnershipQuerySet(models.QuerySet):
    """
    협력사 쿼리셋
    """

    def get_activated(self):
        return self.filter(is_active=True, accepted_datetime__isnull=False)

    def get_rejected(self):
        return self.filter(is_active=True, accepted_datetime__isnull=True, rejected_datetime__isnull=False)

    def get_requested(self):
        return self.filter(is_active=True, accepted_datetime__isnull=True, rejected_datetime__isnull=True)

    def get_deactivated(self):
        return self.filter(is_active=False)

    def get_by_user(self, user):
        return self.filter(user_relations__user=user)


class CampaignQuerySet(PartnershipQuerySet):
    """
    캠페인 쿼리셋
    """
    def get_by_user(self, user, code=None):
        qs = self.filter(partnership__user_relations__user=user)
        if code:
            qs = qs.filter(partnership__code=code)
        return qs

    def current(self):
        now = timezone.now()
        return self.get_activated().filter(
            models.Q(start_datetime__lt=now, end_datetime__gt=now)
            | models.Q(start_datetime__lt=now, end_datetime__isnull=True)
        ).distinct('id')


class CampaignBannerQuerySet(CampaignQuerySet):
    """
    캠페인 배너 쿼리셋
    """
    locations = {
        'user': CUSTOMER_HOME,
        'helper': HELPER_HOME,
        'cs': None
    }

    def current(self, location=''):
        now = timezone.now()
        qs = self.get_activated()
        if location and location in self.locations:
            qs = qs.filter(location=self.locations[location])
        return qs.filter(campaign__in=Campaign.objects.current())


class CampaignUserLogQuerySet(models.QuerySet):
    """
    캠페인 유져 로그 쿼리셋
    """


class CampaignUserAnswerQuerySet(models.QuerySet):
    """
    캠페인 유져 답변 데이터 쿼리셋
    """


"""
Models
"""


class DatetimeModel(models.Model):
    created_datetime = models.DateTimeField('생성일시', auto_now_add=True)
    updated_datetime = models.DateTimeField('수정일시', auto_now=True)

    class Meta:
        abstract = True


class RequestAcceptModel(DatetimeModel):
    accepted_datetime = models.DateTimeField('승인일시', null=True, blank=True)
    rejected_datetime = models.DateTimeField('반려일시', null=True, blank=True)
    is_active = models.BooleanField('활성화 여부', default=True)

    class Meta:
        abstract = True

    @property
    def state(self):
        if not self.is_active:
            return 'deactivated'
        if self.rejected_datetime:
            return 'rejected'
        elif self.accepted_datetime:
            return 'activated'
        else:
            return 'requested'

    def accept(self):
        self.is_active = True
        self.accepted_datetime = timezone.now()
        self.rejected_datetime = None
        self.save()

    def reject(self):
        self.is_active = True
        self.rejected_datetime = timezone.now()
        self.save()

    def deactivate(self):
        self.is_active = False
        self.save()

    def activate(self):
        self.is_active = True
        self.save()


class Partnership(RequestAcceptModel):
    """
    협력사 모델
    """
    ABAILABLE_SERVICES = (
        ('campaigns', '캠페인'),
        ('missions', '다중미션'),
        ('apis', '미션 API'),
    )

    name = models.CharField('협력사명', max_length=30)
    code = models.SlugField('협력사코드', max_length=20, db_index=True, unique=True)
    secret = models.CharField('api secret', max_length=128, blank=True, default='')
    services = ArrayField(models.CharField(max_length=20, choices=ABAILABLE_SERVICES), verbose_name='사용 서비스', blank=True, default=list)
    business_number = models.CharField('사업자번호', max_length=10, unique=True, null=True, blank=True)
    tel = models.CharField('대표 전화번호', max_length=16, null=True, blank=True)
    address_area = models.ForeignKey(Area, verbose_name='주소 지역', null=True, blank=True,
                                     related_name='partnerships', on_delete=models.SET_NULL)
    address_detail = models.CharField('주소 상세', max_length=100, null=True, blank=True)
    business_registration_photo = models.ImageField('사업자 등록증 사진', null=True, blank=True)
    reward_when_joined = models.PositiveIntegerField('가입 리워드', blank=True, default=0)
    reward_when_mission_done = models.PositiveIntegerField('미션완료 리워드', blank=True, default=0)
    reward_when_mission_done_count = models.PositiveSmallIntegerField('미션완료 리워드 회수', blank=True, default=0,
                                                                      help_text='0인 경우 계속 지급')

    objects = PartnershipQuerySet.as_manager()

    class Meta:
        verbose_name = '협력사'
        verbose_name_plural = '협력사'

    def __str__(self):
        return f'[{self.code}] {self.name}'

    def save(self, *args, **kwargs):
        if not self.secret:
            self.set_unusable_secret()
        return super(Partnership, self).save(*args, **kwargs)

    @property
    def cash_balance(self):
        return 0

    @property
    def service_info(self):
        rtn = {}
        for s in self.ABAILABLE_SERVICES:
            rtn.update({s[0]: {
                'title': s[1], 
                'state': self.get_service_state(s[0]),
                'count': self.get_using_service_count(s[0])
            }})
        return rtn

    def get_service_state(self, service):
        # todo: 결제 기능 추가를 통해 사용가능 여부 체크 추가
        state = True if service in self.services else None
        if service != 'apis' and state and self.cash_balance <= 0:
            state = False
        return state

    def get_using_service_count(self, service):
        if service == 'campaigns':
            return self.campaigns.count()
        if service == 'apis':
            return self.templates.count()
        return 0

    def make_secret(self):
        secret = get_md5_hash(str(timezone.now().timestamp()))
        self.secret = make_password(secret)
        self.save()
        return secret

    def set_unusable_secret(self):
        self.secret = make_password(None)

    def check_secret(self, secret):
        return check_password(secret, self.secret)

    def handle_business_registration_photo(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_timestamp()
        return file.save(to='business_registration_photo')

    def get_business_registration_photo_display(self):
        return mark_safe(
            '<img src="%s" />' % self.business_registration_photo.url) if self.business_registration_photo else ''

    get_business_registration_photo_display.short_description = '협력사 사업자 등록증'
    get_business_registration_photo_display.admin_order_field = 'image'

    def get_state_display(self):
        return dict(REQUEST_ACCEPT_STATUS)[self.state]
    get_state_display.short_description = '파트너쉽 상태'


class PartnershipUserRelation(DatetimeModel):
    """
    협력사 유저 관계 모델
    """
    ROLES = [
        (1, '매니저'),
    ]
    partnership = models.ForeignKey(Partnership, verbose_name='파트너쉽', null=True, blank=True,
                                    related_name='user_relations', on_delete=models.SET_NULL)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='사용자', null=True, blank=True,
                             related_name='partnership_relations', on_delete=models.SET_NULL)
    role = models.IntegerField(choices=ROLES, default=1)

    class Meta:
        verbose_name = '협력사 유저 관계'
        verbose_name_plural = '협력사 유저 관계'

    def __str__(self):
        return f'{self.partnership} {self.user} {self.role}'

    def save(self, *args, **kwargs):
        return super(PartnershipUserRelation, self).save(*args, **kwargs)


class Campaign(RequestAcceptModel):

    """
    캠페인 모델
    """
    partnership = models.ForeignKey(Partnership, verbose_name='파트너쉽', null=True, blank=True,
                                    related_name='campaigns', on_delete=models.SET_NULL)
    campaign_type = models.IntegerField('캠페인 종류', choices=CAMPAIGN_TYPES)
    title = models.CharField('제목', max_length=100)
    start_datetime = models.DateTimeField('게시 시작 일시', blank=True, null=True)
    end_datetime = models.DateTimeField('게시 종료 일시', blank=True, null=True)
    campaign_code = models.CharField('캠페인 코드', max_length=5, unique=True, db_index=True)

    objects = CampaignQuerySet.as_manager()

    class Meta:
        verbose_name = '캠페인'
        verbose_name_plural = '캠페인'

    def __str__(self):
        return self.title

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
    def data_count(self):
        CampaignUserData = apps.get_model('biz', 'CampaignUserData')
        return CampaignUserData.objects.filter(banner__campaign_id=self.id).count()

    def accept(self):
        super(Campaign, self).accept()
        CampaignBanner.objects.select_related('campaign').filter(
            Q(campaign__campaign_code=self.campaign_code) & Q(accepted_datetime=None) & Q(is_active=True)
        ).update(
            accepted_datetime=timezone.now()
        )

    def get_state_display(self):
        return dict(REQUEST_ACCEPT_STATUS)[self.state]
    get_state_display.short_description = '캠페인 상태'

    def to_user_data(self, values, **kwargs):
        if len(values) != len(self.fields):
            return Errors.fields_invalid

        answer_data = []
        object_data = {}
        for field, val in zip(self.fields, values):
            if field['is_required'] and not val:
                return Errors.missing_required_field(field['name'])

            data = {
                'id': field['id'],
                'name': field['name'],
            }
            if field['question_type'] == 'files':
                data.update({'val': val or 0, 'is_file': True})
            elif field['question_type'] == 'address':
                # 주소에 대해 포맷팅 추가
                if type(val) == str:
                    area_id, detail_1 = Area.objects.search(val)
                    val = {'area': area_id, 'detail_1': detail_1, 'readable': val}
                data.update({'val': val})
            elif field['question_type'] == 'area':
                # 지역에 대해 포맷팅 추가
                if type(val) == int:
                    area = Area.objects.filter(id=val).last()
                    if not area:
                        return Errors.fields_invalid
                    val = {'id': val, 'readable': str(area)}
                elif type(val) == str:
                    area_id, _ = Area.objects.search(val)
                    val = {'id': area_id, 'readable': val}
                data.update({'val': val})
            else:
                data.update({'val': val or ''})
            answer_data.append(data)
        object_data.update({
            'answer': answer_data,
        })
        object_data.update(kwargs)
        return object_data


class CampaignBanner(RequestAcceptModel):
    """
    캠페인 배너 모델
    """
    campaign = models.ForeignKey(Campaign, verbose_name='캠페인', null=True, blank=True,
                                 related_name='banners', on_delete=models.SET_NULL)
    image = models.ImageField('광고 이미지', null=True, blank=True)
    location = models.IntegerField(choices=LOCATIONS)

    objects = CampaignBannerQuerySet.as_manager()

    class Meta:
        verbose_name = '캠페인 배너'
        verbose_name_plural = '캠페인 배너'

    def __str__(self):
        return f'{self.campaign} {self.get_location_display()} {self.id}'

    def save(self, *args, **kwargs):
        rtn = super(CampaignBanner, self).save(*args, **kwargs)
        # if self.is_active:
        #     CampaignBanner.objects.filter(campaign=self.campaign, location=self.location, is_active=True) \
        #         .exclude(id=self.id) \
        #         .update({'is_active': False})
        return rtn

    @property
    def pre_link(self):
        return '/l/%s/%%s/' % self.id

    def get_link_url(self, user_code):
        return reverse_lazy('biz:campaign-banner-link', kwargs={'id': self.id, 'code': user_code})

    def handle_image(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_timestamp()
        return file.save(to='image')

    def get_image_display(self):
        return mark_safe(
            '<img src="%s" />' % self.image.url) if self.image else ''

    get_image_display.short_description = '캠페인 이미지'
    get_image_display.admin_order_field = 'image'

    def get_state_display(self):
        return dict(REQUEST_ACCEPT_STATUS)[self.state]
    get_state_display.short_description = '캠페인 배너 이미지 상태'


class CampaignQuestion(models.Model):
    """
    캠페인 질문 모델
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
    )
    campaign = models.ForeignKey(Campaign, verbose_name='캠페인', null=True, blank=True,
                                 related_name='questions', on_delete=models.SET_NULL)
    order_no = models.PositiveSmallIntegerField('순번', blank=True, default=10)
    question_type = models.CharField('유형', choices=QUESTION_TYPES, max_length=20)
    name = models.CharField('항목 이름', max_length=250)
    title = models.CharField('질문 제목', max_length=250)
    description = models.TextField('질문 설명', blank=True)
    options = JSONField('선택 항목', blank=True, default=list)
    has_etc_input = models.BooleanField('직접입력(기타) 추가', blank=True, default=False)
    is_required = models.BooleanField('필수 입력 여부', blank=True, default=False)

    class Meta:
        verbose_name = '캠페인 질문'
        verbose_name_plural = '캠페인 질문'

    def __str__(self):
        return self.name

    @property
    def select_options(self):
        return [{o: ''} for o in self.options]


class CampaignUserData(models.Model):
    """
    캠페인 유져 데이터 모델
    """
    code = models.CharField('유져 데이터 코드', max_length=32, blank=True, default='')
    banner = models.ForeignKey(CampaignBanner, verbose_name='캠페인 배너', related_name='data', null=True,
                               on_delete=models.SET_NULL)
    created_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='사용자', null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='campaign_data')
    created_user_identifier = models.CharField('사용자 식별자', max_length=32, blank=True, default='')
    device_info = JSONField('기기정보', blank=True, default=dict)
    app_info = JSONField('앱정보', blank=True, default=dict)
    answer = JSONField('답변', blank=True, default=list)
    clicked_datetime = models.DateTimeField('클릭 일시', null=True, blank=True, default=None)
    answered_datetime = models.DateTimeField('전환 일시', null=True, blank=True, default=None)

    class Meta:
        verbose_name = '캠페인 유져 데이터'
        verbose_name_plural = '캠페인 유져 데이터'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = get_md5_hash('%s.%s.%s' % (self.banner_id, self.created_user_id, self.clicked_datetime))
        if not self.created_user_identifier:
            if self.created_user:
                self.created_user_identifier = self.created_user.code
        return super(CampaignUserData, self).save(*args, **kwargs)

    @property
    def user_display(self):
        if self.created_user:
            return str(self.created_user)
        return self.created_user_identifier[:10] + '**********'

    @property
    def answer_display(self):
        rtn = []
        for a in self.answer:
            if 'is_file' in a and a['is_file']:
                answer_files = self.files.filter(question_id=a['id'])
                a['val'] = []
                for file in answer_files:
                    a['val'].append(file.attach.url)
            rtn.append(a)
        return rtn


class CampaignUserDataFile(models.Model):
    """
    캠페인 유져 데이터 파일 모델
    """
    user_data = models.ForeignKey(CampaignUserData, verbose_name='유져 데이터', related_name='files',
                                  on_delete=models.CASCADE)
    question = models.ForeignKey(CampaignQuestion, verbose_name='캠페인 질문', related_name='files',
                                 on_delete=models.CASCADE)
    attach = models.FileField('파일')

    class Meta:
        verbose_name = '유져 데이터 파일'
        verbose_name_plural = '유져 데이터 파일'

    def __str__(self):
        return '%s.%s.%s' % (self.user_data_id, self.question_id, self.id)

    def handle_attach(self, file_obj):
        filename = ''
        if self.question.options:
            filename_template = '_'.join(self.question.options)
            filename = filename_template.format(
                code=self.user_data.created_user_identifier,
                user_id=self.user_data.created_user_id or 0
            )
        else:
            filename = '%s.%s' % (self.user_data.code, self.question_id)
        file = UploadFileHandler(self, file_obj, filename=filename)
        return file.save(to='attach')
