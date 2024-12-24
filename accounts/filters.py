from django.contrib import admin
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils.encoding import force_text
from django.utils import timezone

from base.constants import USER_STATUS, GENDERS, HELPER_REQUEST_STATUS
from .models import Area


class UserStateFilter(admin.SimpleListFilter):
    """
    회원구분 필터
    """
    title = '회원구분'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return USER_STATUS

    def queryset(self, request, queryset):
        if self.value():
            # todo: 다음 회원구분 로직을 세밀하게 다시 확인할 것.
            query_dict = {
                'withdrew': {'withdrew_datetime__isnull': False},
                'service_blocked': {
                    'withdrew_datetime__isnull': True,
                    '_is_service_blocked': True,
                },
                'deactivated': {
                    'withdrew_datetime__isnull': True,
                    'is_active': False
                },
                'customer': {
                    'withdrew_datetime__isnull': True,
                    'helper__accepted_datetime__isnull': True
                },
                'regular_customer': {
                    'mobiles__number__isnull': False,
                    'mobiles__verified_datetime__isnull': False,
                    'helper__requested_datetime__isnull': True,
                },
                'helper_rejected': {
                    'helper__rejected_datetime__isnull': False,
                    'helper__accepted_datetime__isnull': True,
                },
                'helper_requested': {
                    'helper__requested_datetime__isnull': False,
                    'helper__rejected_datetime__isnull': True,
                    'helper__accepted_datetime__isnull': True,
                },
                'helper': {'helper__accepted_datetime__isnull': False},
            }
            queryset = queryset.filter(**query_dict[self.value()])
        return queryset


class UserUsageFilter(admin.SimpleListFilter):
    """
    앱 사용 필터
    """
    title = '앱 사용'
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        return (
            ('recent_1month', '최근 한달 이내'),
            ('recent_3month', '최근 3개월 이내'),
            ('not_recent_1month', '최근 한달 이내 미사용'),
            ('not_recent_3month', '최근 3개월 이내 미사용'),
            ('not_after_anyman_2_0', '2.0 업데이트 이후 미사용'),
        )

    def queryset(self, request, queryset):
        v = self.value()
        now = timezone.now()
        if v == 'recent_1month':
            queryset = queryset.filter(last_login__gte=now - timezone.timedelta(days=30))
        if v == 'recent_3month':
            queryset = queryset.filter(last_login__gte=now - timezone.timedelta(days=90))
        if v == 'not_recent_1month':
            queryset = queryset.get_recent_not_using(now - timezone.timedelta(days=30))
        if v == 'not_recent_3month':
            queryset = queryset.get_recent_not_using(now - timezone.timedelta(days=90))
        if v == 'not_after_anyman_2_0':
            queryset = queryset.get_recent_not_using(timezone.datetime(year=2020, month=7, day=13))
        return queryset


class RecommendFilter(admin.SimpleListFilter):
    """
    가입 경로 필터
    """
    title = '가입 경로'
    parameter_name = 'recommend'

    def lookups(self, request, model_admin):
        return (
            ('web', '웹 요청에 의한 자동가입'),
            ('user', '추천인에 의한 가입'),
            ('partner', '협력사에 의한 가입'),
            ('recommended', '가입을 추천한 회원'),
        )

    def queryset(self, request, queryset):
        v = self.value()
        if v == 'web':
            queryset = queryset.filter(_recommended_by__in=('WEB', 'IKEA'))
        if v == 'user':
            queryset = queryset.filter(recommended_user__isnull=False).exclude(_recommended_by='')
        if v == 'partner':
            queryset = queryset.filter(recommended_partner__isnull=False).exclude(_recommended_by='')
        if v == 'recommended':
            queryset = queryset.filter(recommended__id__isnull=False)
        return queryset


class AccountTypeFilter(admin.SimpleListFilter):
    """
    계정구분 필터
    """
    title = '계정구분'
    parameter_name = 'account_type'

    def lookups(self, request, model_admin):
        return (
            ('email', '이메일'),
            ('kakao', '카카오'),
            ('naver', '네이버'),
        )

    def queryset(self, request, queryset):
        if self.value():
            queries = {
                'email': queryset.filter(kakao_id='', naver_id=''),
                'kakao': queryset.exclude(kakao_id=''),
                'naver': queryset.exclude(naver_id=''),
            }
            queryset = queries[self.value()]
        return queryset


class GenderFilter(admin.SimpleListFilter):
    """
    성별 필터
    """
    title = '성별'
    parameter_name = 'gender'
    lookup_field = 'gender'

    def lookups(self, request, model_admin):
        return GENDERS[:2] + [(0, '미입력')]

    def queryset(self, request, queryset):
        if self.value() is not None:
            value = self.value()
            if value is '0':
                value = None
            queryset = queryset.filter(**{self.lookup_field: value})
        return queryset


class OSFilter(admin.SimpleListFilter):
    """
    OS 필터
    """
    title = 'OS'
    parameter_name = 'os'

    def lookups(self, request, model_admin):
        return (
            ('Android', 'Android'),
            ('ios', 'iOS')
        )

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(logged_in_devices__device_info__platform__icontains=self.value())
        return queryset


class ManufacturerFilter(admin.SimpleListFilter):
    """
    단말기 제조사 필터
    """
    title = '단말기 제조사'
    parameter_name = 'manufacturer'

    def lookups(self, request, model_admin):
        return (
            ('samsung', '삼성'),
            ('apple', '애플')
        )

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(logged_in_devices__device_info__manufacturer__icontains=self.value())
        return queryset


class HelperStateFilter(admin.SimpleListFilter):
    """
    헬퍼승인 필터
    """
    title = '헬퍼승인 상태'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return HELPER_REQUEST_STATUS[:-1]

    def queryset(self, request, queryset):
        if self.value():
            # todo: 다음 회원구분 로직을 세밀하게 다시 확인할 것.
            query_dict = {
                'accepted': {
                    'accepted_datetime__isnull': False,
                    'user__is_active': True,
                    'is_active': True,
                },
                'rejected': {
                    'accepted_datetime__isnull': True,
                    'rejected_datetime__isnull': False,
                    'user__is_active': True,
                },
                'requested': {
                    'accepted_datetime__isnull': True,
                    'rejected_datetime__isnull': True,
                    'user__is_active': True,
                },
                'deactivated': {'is_active': False},
            }
            queryset = queryset.filter(user__withdrew_datetime__isnull=True, **query_dict[self.value()])
        return queryset


class HelperGenderFilter(GenderFilter):
    """
    헬퍼 성별 필터
    """
    lookup_field = 'user__gender'


class AreaFilter(admin.SimpleListFilter):
    """
    헬퍼 수행지역 필터
    """
    title = '수행지역'
    parameter_name = 'area'

    def lookups(self, request, model_admin):
        return [(a.id, a) for a in Area.objects.filter(parent__isnull=True)]

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            queryset = queryset.filter(Q(accept_area__parent=v) | Q(accept_area=v))
        return queryset



