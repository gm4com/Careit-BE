from dateutil.relativedelta import relativedelta

from harupy.text import String

from django import forms
from django.apps import apps
from django.contrib import admin
from django.db.models import Sum, Subquery, OuterRef, Q, Count, Case, When, F, IntegerField
from django.utils.formats import localize
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.urls import path, reverse
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.admin.models import ContentType
from django.contrib.auth.forms import (
    UserCreationForm as UserCreationBaseForm,
    UserChangeForm
)


from common.admin import (
    RelatedAdminMixin, ChangeFormSplitMixin, AdditionalAdminUrlsMixin, ImageWidgetMixin, log_with_reason
)
from common.views import ModelExportBaseView, FilteredExcelDownloadMixin
from base.admin import BaseAdmin
from .models import User, Helper, FeeRate, BannedWord, Agreement, Quiz, QuizAnswer, ServiceTag, ServiceBlock
from .serializers import CustomerHomeHelperSerializer
from .filters import (
    UserStateFilter, RecommendFilter, AccountTypeFilter, GenderFilter, OSFilter, ManufacturerFilter,
    HelperStateFilter, HelperGenderFilter, AreaFilter, UserUsageFilter
)
from missions.models import CustomerService, Mission
from notification.models import Notification, Tasker


class UserCreationForm(UserCreationBaseForm):
    class Meta:
        model = User
        fields = ('email',)


class CustomerServiceInline(RelatedAdminMixin, admin.TabularInline):
    """
    상담 내역 인라인
    """
    model = CustomerService
    fields = ('user', 'get_created_user_display', 'mission', 'content', 'created_datetime')
    readonly_fields = ('created_datetime', 'get_created_user_display')
    fk_name = 'user'
    extra = 1
    template = 'admin/user/inline_cs.html'
    # autocomplete_fields = ('mission',)
    remove_add_fields = ('mission',)
    remove_change_fields = ('mission',)
    remove_delete_fields = ('mission',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'mission':
            user_id = request.resolver_match.kwargs['object_id']
            kwargs['queryset'] = Mission.objects.filter(
                Q(user_id=user_id)
                | Q(bids__helper__user_id=user_id)
            ).distinct('id').order_by('-id')
        return super(CustomerServiceInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_created_user_display(self, obj):
        return obj.created_user.username
    get_created_user_display.short_description = '상담자'


class UserExcelDownloadView(ModelExportBaseView):
    """
    회원 엑셀 다운로드 뷰
    """
    model = User
    columns = (
        ('state', '회원구분'),
        ('code', '회원코드'),
        ('username', '닉네임'),
        ('mobile', '휴대폰'),
        ('email', '이메일'),
        ('date_of_birth', '생년월일'),
        ('get_gender_display', '성별'),
        ('recommended_user', '추천 회원'),
        ('recommended_partner', '추천 기업'),
        ('created_datetime', '가입일시'),
        ('requested_count', '미션 요청'),
        ('done_count', '미션 완료'),
        ('user_canceled_count', '낙찰전취소'),
        ('timeout_canceled_count', '시간초과취소'),
        ('won_and_canceled_count', '수행중취소'),
        ('done_amount', '미션 완료 금액'),
        ('point_balance', '포인트 잔액'),
        ('device', '단말기 정보'),
        ('last_login', '마지막 로그인'),
    )

    def dispatch(self, request, *args, **kwargs):
        rtn = super(UserExcelDownloadView, self).dispatch(request, *args, **kwargs)
        reason = self.get_filename()
        if rtn.status_code != 200:
            reason += ' (실패)'
        log_with_reason(request.user, ContentType.objects.get_for_model(self.model), 'downloaded', changes=reason)
        return rtn

    def get_queryset(self):
        qs = super(UserExcelDownloadView, self).get_queryset()
        qs = qs.annotate(requested_count=Count('missions__id', distinct=True))
        qs = qs.annotate(done_count=Count(Case(When(missions__saved_state='done', then=1)), distinct=True))
        qs = qs.annotate(user_canceled_count=Count(Case(When(missions__saved_state='user_canceled', then=1)), distinct=True))
        qs = qs.annotate(timeout_canceled_count=Count(Case(When(missions__saved_state='timeout_canceled', then=1)), distinct=True))
        qs = qs.annotate(won_and_canceled_count=Count(Case(When(missions__bids__saved_state='won_and_canceled', then=1))))
        qs = qs.annotate(done_amount=Sum(Case(When(missions__bids__saved_state='done', then='missions__bids__amount'))))
        return qs

    def get_field_point_balance(self, obj):
        return obj.points.get_balance()

    def get_field_device(self, obj):
        return ', '.join([d.get_device_info_display() for d in obj.logged_in_devices.get_logged_in()])


class UserAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    회원 추가 어드민
    """
    def get_additional_urls(self):
        return {
            'activate': '<id>/activate/',
            'deactivate': '<id>/deactivate/',
            'block': '<id>/block/',
            'unblock': '<id>/unblock/',
            'change_level': '<id>/level/change/',
            'push_test': '<id>/push/test/',
            'download_excel': 'download/excel/',
        }

    def view_activate(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.is_active = True
        obj.save()
        messages.success(request, '사용자 %s 활성화 되었습니다.' % String(obj.username).josa('가'))
        return redirect(referer)

    def view_deactivate(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.is_active = False
        obj.save()
        messages.success(request, '사용자 %s 비활성화 되었습니다.' % String(obj.username).josa('가'))
        return redirect(referer)

    def view_block(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        days = int(request.POST.get('days')) or 1
        reason = request.POST.get('reason') or ''

        obj.service_blocks.create(user=obj, reason=reason, end_datetime=timezone.now() + timezone.timedelta(days=days))
        log_with_reason(request.user, obj, 'changed', {'_is_service_blocked': True, '차단일수': days}, reason)
        messages.success(request, '사용자 %s 서비스 차단했습니다.' % String(obj.username).josa('를'))
        return redirect(referer)

    def view_unblock(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        days = int(request.POST.get('days', 0)) or None
        reason = request.POST.get('reason') or ''
        now = timezone.now()
        for block in obj.service_blocks.filter(end_datetime__gt=now):
            block.end_datetime = (block.end_datetime - timezone.timedelta(days=days)) if days else now
            block.save()

        changes = {'_is_service_blocked': False, '차단해제일수': days if days else '즉시해제'}
        log_with_reason(request.user, obj, 'changed', changes, reason)
        messages.success(request, '사용자 %s 차단 해제했습니다.' % String(obj.username).josa('를'))
        return redirect(referer)

    def view_change_level(self, request, *args, **kwargs):
        if request.method != 'POST':
            raise PermissionDenied
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.level = request.POST.get('level') or 1
        obj.save()
        log_with_reason(request.user, obj, 'changed', {'level': obj.level}, request.POST.get('reason') or '')
        messages.success(request, '사용자 %s %s등급으로 변경했습니다.' % (String(obj.username).josa('를'), obj.level))
        return redirect(referer)

    def view_push_test(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        if obj.push_tokens:
            # Notification.objects.push_preset(obj, 'test', request=request)
            Tasker.objects.task('test', user=obj)
        else:
            messages.error(request, '회원 %s 푸쉬 토큰 정보가 없습니다.' % String(obj).josa('는'))
        return redirect(referer)

    def view_download_excel(self, request, *args, **kwargs):
        return UserExcelDownloadView.as_view()(request, *args, **kwargs)


class UserCodeSearchMixin:
    """유져코드 어드민에서 검색시"""
    def get_search_results(self, request, queryset, search_term):
        if search_term.startswith('u') or search_term.startswith('U'):
            search_term = search_term[1:]
        return super(UserCodeSearchMixin, self).get_search_results(request, queryset, search_term)


@admin.register(User)
class UserAdmin(FilteredExcelDownloadMixin, UserAdditionalAdmin, UserCodeSearchMixin, ChangeFormSplitMixin,
                BaseUserAdmin):
    """
    회원 어드민
    """
    form = UserChangeForm
    add_form = UserCreationForm
    change_form_template = 'admin/user/change_form.html'
    list_display = ('get_code_display', 'get_state_display', 'created_datetime', 'username', 'mobile', 'email',
                    'get_logged_in_device_info_display', 'get_function_display', 'get_penalty_display')
    list_filter = (UserStateFilter, UserUsageFilter, RecommendFilter, AccountTypeFilter, GenderFilter, 
                   AreaFilter, OSFilter,
                   ManufacturerFilter, 'is_staff')
    ordering = ('-id',)
    list_per_page = 20
    search_fields = ('code', 'username', 'email', 'mobile', 'helper__name')
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    date_hierarchy = 'created_datetime'
    autocomplete_fields = ('groups',)
    inlines = (CustomerServiceInline,)
    change_form_split = [6, 6]
    excel_download_view = UserExcelDownloadView

    def get_queryset(self, request):
        qs = super(UserAdmin, self).get_queryset(request).annotate(penalty=Sum('penalty_points__point'))
        return qs.prefetch_related('service_blocks', 'penalty_points').select_related('helper')

    def get_penalty_display(self, obj):
        return obj.penalty
    get_penalty_display.short_description = '벌점'
    get_penalty_display.admin_order_field = 'penalty'

    def save_formset(self, request, form, formset, change):
        for obj in formset.save():
            if hasattr(obj, 'created_user') and not obj.created_user:
                obj.created_user_id = request.user.id
                obj.save()

    def has_add_permission(self, request, obj=None):
        # return request.user.is_superuser
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
        # return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj):
        fields = ['last_login', 'created_datetime', 'withdrew_datetime', 'get_device_info_display',
                  'is_push_allowed', 'is_ad_allowed', '_auth_center', 'recommended_by', 'get_ci_display',
                  'get_uid_display', 'get_h_uid_display']
        if obj.ci:
            fields += ['date_of_birth', 'gender']
        if not request.user.is_superuser:
            fields.append('is_staff')
        return fields

    def get_fieldsets(self, request, obj):
        if request.path.endswith('/add/'):
            return self.add_fieldsets
        else:
            fieldsets = [
                ['기본정보', {'fields': (
                    'mobile', 'email', 'username', 'password', 'created_datetime', 'withdrew_datetime',
                    '_auth_center', 'recommended_by',
                )}],
                ['개인정보', {'fields': (
                    'get_ci_display', 'date_of_birth', 'gender',
                )}],
                ['기기정보', {'fields': (
                    'last_login', 'get_device_info_display', 'is_push_allowed', 'is_ad_allowed'
                )}],
                ['권한', {'fields': (
                    'groups', 'is_staff'
                )}],
            ]
            if request.user.is_superuser:
                fieldsets[3][1]['fields'] = ('groups', 'is_staff', 'is_superuser')
        return fieldsets

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if change:
            context.update({'title': str(obj)})
            context.update({'context_type_id': ContentType.objects.get_for_model(obj).id})
        return super(UserAdmin, self).render_change_form(request, context, add, change, form_url, obj)

    def get_code_display(self, obj):
        return mark_safe('U%s' % obj.code)
    get_code_display.short_description = '회원코드'
    get_code_display.admin_order_field = 'code'

    def get_function_display(self, obj):
        return mark_safe(
            # '<a class="btn btn-danger" href="">BLOCK</a> '
            '<a class="btn btn-sm btn-secondary" href="%s">푸시 테스트</a> ' % reverse('admin:accounts_user_push_test', kwargs={'id': obj.id})
            # + '<a class="btn btn-sm btn-info" href="">상담+</a>'
        )
    get_function_display.short_description = '기능'

    def get_ci_display(self, obj):
        if not obj.ci:
            return '미인증'
        return '인증완료'
    get_ci_display.short_description = '본인인증'

    def get_logged_in_device_info_display(self, obj):
        html = []
        for device in obj.logged_in_devices.get_logged_in().order_by('device_info__uuid', '-id').distinct('device_info__uuid'):
            device_info = device.get_device_info_display()
            if device_info:
                html.append(
                    '<span class="btn btn-sm btn-%s mb-1 bt-1">%s</span>' % (
                        'outline-secondary' if device.logged_out_datetime else 'outline-dark',
                        device_info
                    )
                )
        return mark_safe('<br/>'.join(html))
    get_logged_in_device_info_display.short_description = '로그인 기기정보'

    def get_device_info_display(self, obj):
        html = []
        for device in obj.logged_in_devices.order_by('device_info__uuid', '-id').distinct('device_info__uuid'):
            device_info = device.get_device_info_display()
            if device_info:
                html.append(
                    '<span class="btn btn-sm btn-%s mb-1 bt-1">%s</span>' % (
                        'outline-secondary' if device.logged_out_datetime else 'outline-dark',
                        device_info
                    )
                )
        return mark_safe('<br/>'.join(html))
    get_device_info_display.short_description = '기기정보'

    def get_uid_display(self, obj):
        return ', '.join(obj.user_uid.values_list('uid', flat=True))
    get_uid_display.short_description = '구 UID'

    def get_h_uid_display(self, obj):
        return ', '.join(obj.user_h_uid.values_list('h_uid', flat=True))
    get_h_uid_display.short_description = '구 헬퍼 UID'


class FeeRateInline(RelatedAdminMixin, admin.TabularInline):
    """
    기간 수수료율 인라인
    """
    model = FeeRate
    fields = ('fee', 'start_date', 'end_date')
    extra = 0
    ordering = ('-created_datetime',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class HelperAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    헬퍼 추가 어드민
    """
    def get_additional_urls(self):
        return {
            'change_helper_level': '<id>/level/change/',
            'accept': '<id>/accept/',
            'reject': '<id>/reject/',
            'accept_profile_photo': '<id>/accept_profile_photo/',
            'reject_profile_photo': '<id>/reject_profile_photo/',
        }

    def view_accept_profile_photo(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.accept()
        messages.success(request, '%s의 프로필 이미지 변경 신청을 승인했습니다.' % String(obj))
        return redirect(referer)

    def view_reject_profile_photo(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.reject()
        messages.success(request, '%s의 프로필 이미지 변경 신청을 거부했습니다.' % String(obj))
        return redirect(referer)

    def view_accept(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.accept()

        changes = {'헬퍼승인': True}
        log_with_reason(request.user, obj, 'changed', changes)
        messages.success(request, '%s의 헬퍼 신청을 승인했습니다.' % String(obj))

        # Notification.objects.push_preset(obj.user, 'helper_accepted', args=[obj.user.username], request=request)
        Tasker.objects.task('helper_accepted', user=obj.user)

        return redirect(referer)

    def view_reject(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        reason = request.POST.get('reason') or ''

        obj.reject(reason)

        changes = {'헬퍼승인': False}
        log_with_reason(request.user, obj, 'changed', changes, reason)
        messages.success(request, '%s의 헬퍼신청 승인을 거부했습니다.' % String(obj))

        # Notification.objects.push_preset(obj.user, 'helper_rejected', args=[obj.user.username], request=request)
        Tasker.objects.task('helper_rejected', user=obj.user, kwargs={'reason': reason})

        return redirect(referer)

    def view_change_helper_level(self, request, *args, **kwargs):
        if request.method != 'POST':
            raise PermissionDenied
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.level = request.POST.get('level') or 1
        obj.save()
        log_with_reason(request.user, obj, 'changed', {'level': obj.level}, request.POST.get('reason') or '')
        messages.success(request, '%s %s등급으로 변경했습니다.' % (String(obj).josa('를'), obj.level))
        return redirect(referer)


@admin.register(Helper)
class HelperAdmin(HelperAdditionalAdmin, ImageWidgetMixin, UserCodeSearchMixin, RelatedAdminMixin, BaseAdmin):
    """
    헬퍼 어드민
    """
    list_display = ('user', 'get_request_state_with_datetime_display', 'name', 'get_gender_display',
                    'get_date_of_birth_display', 'get_accept_area_display', 'is_at_home')
    change_form_template = 'admin/helper/change_form.html'
    list_filter = (HelperStateFilter, 'is_profile_photo_accepted', HelperGenderFilter, AreaFilter, 'is_at_home')
    list_per_page = 20
    search_fields = ('user__code', 'user__username', 'user__email', 'user__mobile', 'name')
    autocomplete_fields = ('accept_area',)
    remove_add_fields = ('accept_area',)
    image_fields = ('profile_photo', 'id_photo', 'id_person_photo', 'profile_photo_applied')
    fields = (
        'user', 'push_allowed_from', 'push_allowed_to', 'is_online_acceptable', 'accept_area',
        'is_mission_request_push_allowed', 'is_nearby_push_allowed', 'is_profile_public',
        'introduction', 'best_moment', 'get_services_display', 'experience', 'licenses',
        'means_of_transport', 'usable_tools', 'level',
        'has_crime_report', 'requested_datetime', 'name', 'address_area', 'address_detail_1', 'address_detail_2',
        'accepted_datetime', 'rejected_datetime', 'rejected_reason', 'is_active', 'is_at_home',
        '_joined_from', '_job', '_additional_mission_done_count', '_additional_mission_canceled_count'
    )
    date_hierarchy = 'requested_datetime'
    exclude = image_fields
    inlines = (FeeRateInline,)
    actions = ('action_set_at_home_on', 'action_set_at_home_off', 'action_is_active_on', 'action_is_active_off')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                'user', 'push_allowed_from', 'push_allowed_to', 'is_online_acceptable',
                'is_mission_request_push_allowed', 'is_nearby_push_allowed', 'is_profile_public',
                'introduction', 'best_moment', 'get_services_display', 'experience', 'licenses',
                'means_of_transport', 'usable_tools', 'level',
                'has_crime_report', 'requested_datetime', 'address_area', 'address_detail_1',
                'address_detail_2',
                'accepted_datetime', 'rejected_datetime', 'rejected_reason', 'is_active', 'is_at_home',
                '_joined_from', '_job'
            )
        return super(HelperAdmin, self).get_readonly_fields(request, obj)

    def action_set_at_home_on(self, request, queryset):
        cnt = queryset.filter(is_at_home=False).update(is_at_home=True)
        messages.success(request, '%s명의 헬퍼를 고객홈에 설정했습니다.' % cnt)
        CustomerHomeHelperSerializer.cache()
    action_set_at_home_on.short_description = '선택한 헬퍼를 고객홈에 설정'

    def action_set_at_home_off(self, request, queryset):
        cnt = queryset.filter(is_at_home=True).update(is_at_home=False)
        messages.success(request, '%s명의 헬퍼를 고객홈에서 설정해제했습니다.' % cnt)
        CustomerHomeHelperSerializer.cache()
    action_set_at_home_off.short_description = '선택한 헬퍼를 고객홈에서 설정해제'

    def action_is_active_on(self, request, queryset):
        if request.user.is_superuser:
            cnt = queryset.filter(is_active=False).update(is_active=True)
            messages.success(request, '%s명의 헬퍼를 활성화했습니다.' % cnt)
        else:
            messages.error(request, '최고 관리자만 변경할 수 있습니다.')
    action_is_active_on.short_description = '선택한 헬퍼를 활성화'

    def action_is_active_off(self, request, queryset):
        if request.user.is_superuser:
            cnt = queryset.filter(is_active=True).update(is_active=False)
            messages.success(request, '%s명의 헬퍼를 비활성화했습니다.' % cnt)
        else:
            messages.error(request, '최고 관리자만 변경할 수 있습니다.')
    action_is_active_off.short_description = '선택한 헬퍼를 비활성화'

    def has_add_permission(self, request, obj=None):
        return False

    # def has_change_permission(self, request, obj=None):
    #     return bool(obj is None)

    def has_delete_permission(self, request, obj=None):
        return False

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if change:
            context.update({'title': str(obj.user)})
            context.update({'context_type_id': ContentType.objects.get_for_model(obj).id})
            context.update({'labels_for_fields': {
                'profile_photo': '프로필 사진',
                'id_photo': '신분증 사진',
                'id_person_photo': '신분증과 함께 찍은 사진',
                'profile_photo_applied': '',
            }})
        return super(HelperAdmin, self).render_change_form(request, context, add, change, form_url, obj)

    def get_gender_display(self, obj):
        return obj.user.get_gender_display()

    get_gender_display.short_description = '성별'
    get_gender_display.admin_order_field = 'user__gender'

    def get_date_of_birth_display(self, obj):
        return obj.user.date_of_birth

    get_date_of_birth_display.short_description = '생년월일'
    get_date_of_birth_display.admin_order_field = 'user__date_of_birth'

    def get_request_state_with_datetime_display(self, obj):
        if obj.request_state == 'deactivated':
            return obj.get_request_state_display()
        elif obj.request_state == 'accepted':
            datetime_display = obj.accepted_datetime
        elif obj.request_state == 'rejected':
            datetime_display = obj.rejected_datetime
        else:
            datetime_display = obj.requested_datetime
        return '%s (%s)' % (obj.get_request_state_display(), localize(datetime_display))

    get_request_state_with_datetime_display.short_description = '헬퍼승인 상태'

    def get_accept_area_display(self, obj):
        return ', '.join([str(area) for area in  obj.accept_area.all()])

    get_accept_area_display.short_description = '수행지역'
    get_accept_area_display.admin_order_field = 'accept_area'

    def get_services_display(self, obj):
        html = ''
        for tag in obj.services.all():
            html += '<a class="btn btn-sm btn-info mb-1" href="%s">%s</a> ' % (
            reverse('admin:accounts_servicetag_change', kwargs={'object_id': tag.id}), str(tag))
        return mark_safe(html)
    get_services_display.short_description = '제공 서비스'


@admin.register(ServiceBlock)
class ServiceBlockAdmin(BaseAdmin):
    """
    회원 이용정지 어드민
    """
    list_display = ('get_user_link', 'start_datetime', 'end_datetime', 'get_reason', 'get_period_display')
    list_display_links = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super(ServiceBlockAdmin, self).get_queryset(request)
        return qs.annotate(period=F('end_datetime') - F('start_datetime'))

    def get_user_link(self, obj):
        return mark_safe('<a href="/admin/accounts/user/%s/change/" class="btn btn-info btn-sm mb-1">%s</a>' % (obj.user.id, obj.user))
    get_user_link.short_description = '회원'

    def get_period_display(self, obj):
        period = relativedelta(seconds=obj.period.total_seconds() + 1)
        rtn = []
        if period.days:
            rtn.append('%d일' % period.days)
        if period.hours:
            rtn.append('%d시간' % period.hours)
        if period.minutes:
            rtn.append('%d분' % period.minutes)
        return ' '.join(rtn)
    get_period_display.short_description = '기간'
    get_period_display.admin_order_field = 'period'


@admin.register(ServiceTag)
class ServiceTagAdmin(BaseAdmin):
    """
    제공 서비스 태그 어드민
    """
    list_display = ('title', 'get_helper_count_display')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super(ServiceTagAdmin, self).get_queryset(request)
        qs = qs.annotate(helper_count=Count('helpers__id'))
        return qs

    def get_helper_count_display(self, obj):
        return obj.helper_count
    get_helper_count_display.short_description = '헬퍼수'
    get_helper_count_display.admin_order_field = 'helper_count'

    def get_readonly_fields(self, request, obj=None):
        return ['get_helpers_display'] if request.user.is_superuser else ('title', 'get_helpers_display')

    def get_helpers_display(self, obj):
        html = '<p>총 %s명</p>' % obj.helper_count
        for helper in obj.helpers.all():
            html += '<a class="btn btn-info mb-1" href="%s">%s</a><br/>' % (reverse('admin:accounts_helper_change', kwargs={'object_id': helper.id}), str(helper))
        return mark_safe(html)
    get_helpers_display.short_description = '헬퍼'


@admin.register(BannedWord)
class BannedWordAdmin(BaseAdmin):
    """
    금지어 어드민
    """
    list_display = ('word', 'banned_username', 'banned_mission')
    search_fields = ('word',)
    list_filter = ('banned_username', 'banned_mission')


@admin.register(Agreement)
class AgreementAdmin(BaseAdmin):
    """
    동의 문서 어드민
    """
    list_display = ('title', 'is_required')
    search_fields = ('title', 'content', 'page_code')
    list_filter = ('page_code', 'is_required')


class QuizAnswerInline(admin.TabularInline):
    """
    헬퍼 퀴즈 답안 인라인
    """
    model = QuizAnswer
    extra = 0
    min_num = 2
    max_num = 5
    ordering = ('id',)


@admin.register(Quiz)
class QuizAdmin(BaseAdmin):
    """
    헬퍼 퀴즈 어드민
    """
    inlines = (QuizAnswerInline,)
    list_display = ('title', 'get_answer_display')
    search_fields = ('title', 'answers__text')

    CORRECT = '<li class="success"><b>%s</b></li>'
    WRONG = '<li>%s</li>'

    def get_answer_display(self, obj):
        objects = obj.answers.all().order_by('id')
        return mark_safe(
            '<ol>' + \
            ''.join([(self.CORRECT if o.is_correct else self.WRONG) % o.text for o in objects]) + \
            '</ol>'
        )
    get_answer_display.short_description = '답안'
