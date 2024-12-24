from harupy.text import String

from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelectMultiple
from django import forms
from django.db.models import Count, Q, F, Avg, Sum, When, Case, Value, IntegerField, FloatField , ManyToManyField
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.shortcuts import redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.admin.models import ContentType

from common.admin import (
    RelatedAdminMixin, ChangeFormSplitMixin, AdditionalAdminUrlsMixin, ImageWidgetMixin,
    log_with_reason
)
from common.views import ModelExportBaseView, FilteredExcelDownloadMixin
from common.utils import BaseExcelImportConverter, add_comma
from common.admin import AdminFilter
from base.models import Area
from base.constants import MISSION_STATUS
from base.admin import BaseAdmin
from accounts.models import LoggedInDevice
from accounts.admin import UserCodeSearchMixin
from notification.models import Notification
from payment.models import Payment
from .models import (
    Address, MissionType, MultiMission, MultiAreaMission, Mission, MissionFile, Bid, Interaction, Review, Report,
    UserBlock, PenaltyPoint, MissionWarningNotice, DangerousKeyword, CustomerService, SafetyNumber,
    TemplateCategory, TemplateTag, TemplateQuestion, MissionTemplate
)
from .serializers import CustomerHomeMissionSerializer
from missions.templatetags.missions_admin import multi_mission_state_menu, multi_area_mission_state_menu, bid_state_menu


"""
Forms and Inlines
"""


class DangerousKeywordInline(admin.TabularInline):
    """
    위험미션 키워드 인라인
    """
    model = DangerousKeyword
    extra = 1


class MultiAreaMissionInline(RelatedAdminMixin, admin.TabularInline):
    """
    다중지역 미션 인라인
    """
    model = MultiAreaMission
    remove_add_fields = ('area',)
    remove_change_fields = ('area',)
    autocomplete_fields = ('area',)
    fields = ('area', 'detail_1', 'detail_2', 'amount', 'customer_mobile', 'get_state_functions')
    readonly_fields = ('get_state_functions',)
    extra = 1

    def get_state_functions(self, obj):
        return multi_area_mission_state_menu(obj, size='sm') if obj else ''
    get_state_functions.short_description = '상태'


class MissionFileInline(admin.TabularInline):
    """
    미션 파일 인라인
    """
    model = MissionFile
    extra = 0
    fields = ('get_attach_display', 'attach',)
    readonly_fields = ('get_attach_display',)

    def has_add_permission(self, request, obj=None):
        return not bool(obj and obj.mission_type_id in (1, 2))

    def has_change_permission(self, request, obj=None):
        return not bool(obj and obj.mission_type_id == (1, 2))

    def get_attach_display(self, obj):
        ext = obj.attach.url.split('.')[-1].lower()
        if ext in ('jpeg', 'jpg', 'gif', 'bmp', 'png'):
            img = '<img src="%s" class="crop-100-100 circle">' % obj.attach.url
        else:
            img = '%s 파일' % ext
        return mark_safe('<a href="%s">%s</a>' % (obj.attach.url, img))
    get_attach_display.short_description = '미리보기'


class BidsInline(RelatedAdminMixin, admin.StackedInline):
    """
    입찰 인라인
    """
    model = Bid
    extra = 0
    template = 'admin/missions/mission/inline_bid.html'
    autocomplete_fields = ('helper',)
    fields = ('helper', 'amount')
    remove_add_fields = ('helper',)
    remove_change_fields = ('helper',)

    def has_add_permission(self, request, obj=None):
        # return not bool(obj and obj.mission_type_id in (1, 2))
        return bool(obj is None)


class InteractionInline(admin.TabularInline):
    """
    미션수행 인터랙션 인라인
    """
    model = Interaction
    extra = 0
    fields = ('created_user', 'interaction_type', 'detail', 'requested_datetime', 'accepted_datetime',
              'canceled_datetime')
    readonly_fields = ('requested_datetime', 'accepted_datetime', 'canceled_datetime')

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


"""
Filters
"""


class BaseStateFilter(admin.SimpleListFilter):
    """
    상태 기본 필터
    """
    title = '상태'
    parameter_name = 'state'
    state_query_names = (
        ('canceled', '취소됨'),
        ('in_bidding', '입찰중'),
        ('in_action', '수행중'),
        ('done', '수행완료'),
    )

    def lookups(self, request, model_admin):
        return self.state_query_names

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            query = getattr(queryset, val)
            if query:
                queryset = query()
        return queryset


class MissionStateFilter(BaseStateFilter):
    """
    미션 상태 필터
    """
    state_query_names = MISSION_STATUS

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            if val == 'canceled':
                queryset = queryset.canceled_saved()
            else:
                queryset = queryset.filter(saved_state=val)
        return queryset


class RequestPlatformFilter(admin.SimpleListFilter):
    """
    미션 요청 플랫폼 필터
    """
    title = '요청 플랫폼'
    parameter_name = 'platform'

    def lookups(self, request, model_admin):
        return (
            ('app', '앱 요청'),
            ('web', '웹 요청'),
            ('api', '외부 api 웹 요청'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == 'app':
            queryset = queryset.filter(login_code='')
        if val == 'web':
            queryset = queryset.exclude(login_code='').filter(template__partnership__isnull=True)
        if val == 'api':
            queryset = queryset.exclude(login_code='').filter(template__partnership__isnull=False)
        return queryset


class BidStateFilter(MissionStateFilter):
    """
    입찰 상태 필터
    """


class AdminUserFilter(AdminFilter):
    """
    작성 관리자 필터
    """
    title = '담당 직원'
    parameter_name = 'user'


class CreatedAdminUserFilter(AdminFilter):
    """
    작성 관리자 필터
    """
    title = '작성 직원'
    parameter_name = 'created_user'


class IsMultiMissionFilter(admin.SimpleListFilter):
    """
    다중미션 여부 필터
    """
    title = '미션 종류'
    parameter_name = 'is_multi_mission'

    def lookups(self, request, model_admin):
        return (
            (True, '다중미션'),
            (False, '일반미션'),
        )

    def queryset(self, request, queryset):
        values = {'True': 'area_mission', 'False': 'mission'}
        if self.value() in values:
            query = {values[self.value()] + '__isnull': False}
            queryset = queryset.filter(**query)
        return queryset


class SafetyNumberStateFilter(admin.SimpleListFilter):
    """
    안심번호 상태 필터
    """
    title = '할당 상태'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return (
            ('using', '사용중'),
            ('failed', '번호할당 실패'),
            ('unassigned', '사용 완료(할당 해제)'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            if value == 'using':
                queryset = queryset.filter(assigned_datetime__isnull=False, unassigned_datetime__isnull=True)
            elif value == 'failed':
                queryset = queryset.filter(assigned_datetime__isnull=True, unassigned_datetime__isnull=True)
            elif value == 'unassigned':
                queryset = queryset.filter(assigned_datetime__isnull=False, unassigned_datetime__isnull=False)
        return queryset


class CategoryDepthFilter(admin.SimpleListFilter):
    """
    카테고리 계층 필터
    """
    title = '카테고리 계층'
    parameter_name = 'depth'

    def lookups(self, request, model_admin):
        return (
            (1, '최상위'),
            (2, '2차'),
            (3, '3차'),
        )

    def queryset(self, request, queryset):
        val = int(self.value() or 0)
        if val:
            if val == 1:
                query = {'parent__isnull': True}
            else:
                query = {'parent__' * (val - 1) + 'isnull': False, 'parent__' * val + 'isnull': True}
            queryset = queryset.filter(**query)
        return queryset


class MissionAreaFilter(admin.SimpleListFilter):
    """
    미션 발생지역 필터
    """
    title = '미션 발생지역 (목적지)'
    parameter_name = 'mission_area'

    def lookups(self, request, model_admin):
        return [(a.id, a) for a in Area.objects.filter(parent__isnull=True)]

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            queryset = queryset.filter(Q(final_address__area__parent=v) | Q(final_address__area=v))
        return queryset
        

"""
Admins
"""


@admin.register(SafetyNumber)
class SafetyNumberAdmin(UserCodeSearchMixin, BaseAdmin):
    """
    안심번호 어드민
    """
    list_display = ('user', 'number', 'assigned_number', 'assigned_datetime', 'unassigned_datetime')
    list_display_links = None
    list_filter = (SafetyNumberStateFilter,)
    autocomplete_fields = ('user',)
    fields = ('user', 'number', 'assigned_number')
    search_fields = ('user__code', 'user__username', 'number', 'assigned_number')

    def has_add_permission(self, request):
        return False


@admin.register(MissionWarningNotice)
class MissionWarningNoticeAdmin(ChangeFormSplitMixin, BaseAdmin):
    """
    위험미션 키워드 어드민
    """
    list_display = ('description', 'get_keywords_display')
    inlines = (DangerousKeywordInline,)
    change_form_split = [7, 5]
    search_fields = ('description', 'keywords__text')

    def get_keywords_display(self, obj):
        return ', '.join(obj.keywords.values_list('text', flat=True))
    get_keywords_display.short_description = '키워드'


@admin.register(MissionType)
class MissionTypeAdmin(BaseAdmin):
    """
    미션 타입 어드민
    """
    list_display = ('title', 'description', 'code', 'class_name', 'user_in_charge',
                    'minimum_amount', 'bidding_limit', 'push_before_finish', 'product_fields')
    search_fields = ('title', 'description', 'code')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user_in_charge':
            kwargs['queryset'] = get_user_model().objects.filter(is_staff=True)
        return super(MissionTypeAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Address)
class AddressAdmin(RelatedAdminMixin, BaseAdmin):
    """
    주소 어드민
    """
    list_display = ('area', 'get_detail_display', 'name', 'user')
    search_fields = ('area__name', 'area__parent__name', 'detail_1', 'detail_2', 'name')
    autocomplete_fields = ('area',)
    exclude = ('user', )
    remove_add_fields = ('area',)
    remove_change_fields = ('area',)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
            obj.detail_1 = obj.detail_1.strip()
            obj.detail_2 = obj.detail_2.strip()
            exist_obj = Address.objects.filter(user=obj.user, area=obj.area, detail_1=obj.detail_1,
                                               detail_2=obj.detail_2).last()
            if exist_obj:
                if exist_obj.name != obj.name:
                    exist_obj.name = obj.name or exist_obj.name
                    exist_obj.save()
                return exist_obj
        return super(AddressAdmin, self).save_model(request, obj, form, change)

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super(AddressAdmin, self).get_search_results(request, queryset, search_term)
        queryset = queryset.filter(user=request.user)
        return queryset, use_distinct

    def get_detail_display(self, obj):
        return obj.detail
    get_detail_display.short_description = '상세주소'
    get_detail_display.admin_order_field = 'detail_1'


class MultiMissionExcelFormDownloadView(ModelExportBaseView):
    """
    다중미션 엑셀 양식 다운로드 뷰
    """
    model = MultiAreaMission
    columns = (
        ('empty', '시도'),
        ('empty', '구군'),
        ('empty', '미션주소'),
        ('empty', '상세주소'),
        ('empty', '지급캐쉬'),
        ('empty', '고객 연락처'),
    )

    def get_filename(self):
        return '다중지역미션_요청샘플.%s' % self.file_type


class MultiMissionExcelConverter(BaseExcelImportConverter):
    """
    다중미션 엑셀 가져오기
    """
    model = MultiAreaMission
    columns = (
        (
            'area_1',
            'area_2',
            'detail_1',
            'detail_2',
            'amount',
            'customer_mobile',
        ),
    )

    def convert_sheet_0_fields(self, row):
        area_1 = row.pop('area_1')
        area_2 = row.pop('area_2')
        row['amount'] = int(row['amount'])
        row['customer_mobile'] = (str(row['customer_mobile']).split('.')[0]).replace('-', '')
        row['area_id'], detail_0 = Area.objects.search(area_1 + ' ' + area_2)
        if detail_0:
            row['detail_1'] = detail_0 + ' ' + row['detail_1']
        return row


class MultiMissionAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    다중 미션 추가 어드민
    """
    def get_additional_urls(self):
        return {
            'upload_excel': '<id>/upload/excel/',
            'download_excel': 'download/excel/form/',
            'request': '<id>/request/',
            'activate': '<id>/activate/',
            'deactivate': '<id>/deactivate/',
            'push': '<id>/push/',
        }

    def view_download_excel(self, request, *args, **kwargs):
        return MultiMissionExcelFormDownloadView.as_view()(request, *args, **kwargs)

    def view_upload_excel(self, request, *args, **kwargs):
        if request.method == 'POST':
            referer = self._get_referer_or_fail(request)
            obj = self._get_object_or_fail(kwargs)
            if 'excel' in request.FILES:
                try:
                    excel = MultiMissionExcelConverter(request.FILES['excel'])
                except:
                    messages.error(request, '엑셀 파일이 아니거나, 잘못된 형식의 파일입니다.')
                else:
                    try:
                        data = excel.get_data_from_sheet()
                    except:
                        messages.error(request, '데이터 변환에 실패했습니다. 엑셀 파일이 형식에 맞게 작성되었는지 다시 한 번 확인 바랍니다.')
                    else:
                        for row in data:
                            obj.children.create(**row)
                        messages.success(request, '다중 미션 요청지역이 추가되었습니다.')
            else:
                messages.error(request, '엑셀 파일을 선택해서 업로드해주세요.')
            return redirect(referer)

    def view_request(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        if obj.request():
            messages.success(request, '미션을 요청했습니다. 이제부터 모바일 앱에 해당 미션이 노출됩니다.')
            return self.view_push(request, *args, **kwargs)
        else:
            messages.error(request, '미션이 요청할 수 없는 상태입니다.')
            return redirect(referer)

    def view_activate(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.is_active = True
        obj.save()
        messages.success(request, '미션을 활성화했습니다.')
        return redirect(referer)

    def view_deactivate(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.is_active = False
        obj.save()
        messages.success(request, '미션을 비활성화했습니다.')
        return redirect(referer)

    def view_push(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        if obj.request_helpers.exists():
            receivers = list(LoggedInDevice.objects.get_logged_in().filter(user__helper__in=obj.request_helpers.all())\
                .values_list('push_token', flat=True))
        else:
            receivers = [area.id for area in obj.request_areas]
        if receivers:
            obj.push_result = Notification.objects.push_preset(receivers, 'mission_requested',
                                                               title='애니맨 미션 알림',
                                                               args=['<%s>' % obj.summary, ''], request=request)
            obj.save()
        else:
            messages.error(request, '푸쉬 알림을 보낼 수 있는 대상이 없습니다.')
        return redirect(referer)


@admin.register(MultiMission)
class MultiMissionAdmin(MultiMissionAdditionalAdmin, RelatedAdminMixin, ImageWidgetMixin, UserCodeSearchMixin,
                        BaseAdmin):
    """
    다중 미션 어드민
    """
    list_display = ('code', 'title', 'get_banner_display', 'user', 'mission_type', 'get_request_areas_display',
                    'get_bids_count_display', 'get_state_functions')
    autocomplete_fields = ('request_helpers',)
    search_fields = ('code', 'user__code', 'user__username', 'title', 'summary', 'content')
    remove_add_fields = ('mission_type', 'user')
    remove_change_fields = ('mission_type', 'user')
    inlines = (MultiAreaMissionInline,)
    change_form_split = (5, 7)
    change_form_template = 'admin/multimission/change_form.html'
    list_filter = (MissionStateFilter, 'mission_type', AdminUserFilter)
    image_fields = ('banner',)

    def save_model(self, request, obj, form, change):
        if request.FILES and request.FILES['banner']:
            if not change:
                obj.save()
            obj.handle_banner(request.FILES['banner'])
        super(MultiMissionAdmin, self).save_model(request, obj, form, change)
        super(MultiMissionAdmin, self).save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return bool(obj.state in ('draft',)) if obj else True

    def get_fields(self, request, obj=None):
        fields = ['mission_type', 'user', 'title', 'banner', 'summary', 'content', 'request_helpers']
        if obj:
            fields.append('requested_datetime')
        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ['requested_datetime']
        if obj:
            readonly_fields += ['mission_type']
        return readonly_fields

    def get_changeform_initial_data(self, request):
        initial = super(MultiMissionAdmin, self).get_changeform_initial_data(request)
        initial['user'] = request.user
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'mission_type':
            kwargs['queryset'] = MissionType.objects.exclude(title='일반미션').exclude(title='원격미션').order_by('id')
        if db_field.name == 'user':
            kwargs['queryset'] = get_user_model().objects.filter(is_staff=True)
        return super(MultiMissionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super(MultiMissionAdmin, self).get_queryset(request)
        qs = qs.annotate(bids_count=Count('children__bids'))
        return qs

    def get_bids_count_display(self, obj):
        return obj.bids_count
    get_bids_count_display.short_description = '입찰'
    get_bids_count_display.admin_order_field = 'bids_count'

    def get_request_areas_display(self, obj):
        helpers = obj.request_helpers.all()
        if helpers:
            elements = ['<span class="btn btn-sm btn-outline-info mb-1 mt-1">%s</span>' % str(helper)
                        for helper in obj.request_helpers.all()]
        else:
            elements = ['<span class="btn btn-sm btn-outline-dark mb-1 mt-1">[지역] %s</span>' % str(area)
                        for area in obj.request_areas]
        return mark_safe(' '.join(elements))
    get_request_areas_display.short_description = '요청 및 알림발송 대상'

    def get_state_functions(self, obj):
        return multi_mission_state_menu(obj, size='sm')
    get_state_functions.short_description = '상태'
    get_state_functions.admin_order_field = 'saved_state'


class MissionExcelDownloadView(ModelExportBaseView):
    """
    미션 엑셀 다운로드 뷰
    """
    model = Mission
    columns = (
        ('code', '미션코드'),
        ('user', '회원'),
        ('user__mobile', '회원 휴대폰'),
        ('requested_datetime', '요청일시'),
        ('due_datetime', '미션일시'),
        ('mission_type', '미션타입'),
        ('final', '주소'),
        # ('area_1', '시/도'),
        # ('area_2', '구/군'),
        ('template', '템플릿'),
        ('content', '요청내용'),
        ('get_state_display', '상태'),
        ('bidded_count', '입찰수'),
        ('helper', '매칭 헬퍼'),
        ('budget', '고객 예산'),
        ('average_amount', '평균 입찰가'),
        ('won_amount', '낙찰가'),
        ('card_paid', '카드 결제액'),
        ('point_paid', '포인트 결제액'),
    )

    def dispatch(self, request, *args, **kwargs):
        rtn = super(MissionExcelDownloadView, self).dispatch(request, *args, **kwargs)
        reason = self.get_filename()
        if rtn.status_code != 200:
            reason += ' (실패)'
        log_with_reason(request.user, ContentType.objects.get_for_model(self.model), 'downloaded', changes=reason)
        return rtn

    def get_queryset(self):
        qs = super(MissionExcelDownloadView, self).get_queryset()
        qs = qs.prefetch_related('bids', 'bids__payment').select_related('final_address')
        qs = qs.annotate(average_amount=Avg('bids__amount'))
        qs = qs.annotate(card_paid=Sum(Case(When(bids__payment__is_succeeded=True, bids__payment__pay_method__in=['Card', 'CARD', 'POINT'], then='bids__payment__amount'))))
        qs = qs.annotate(point_paid=Sum(Case(When(bids__payment__is_succeeded=True, bids__payment__pay_method__in=['Card', 'CARD', 'POINT'], then=F('bids__payment__point__amount') * -1))))
        return qs

    def get_field_final(self, obj):
        return str(obj.final_address)

    # def get_field_area_1(self, obj):
    #     if not obj.final_address:
    #         return ''
    #     if not obj.final_address.area.parent:
    #         return str(obj.final_address.area)
    #     return str(obj.final_address.area.parent)
    #
    # def get_field_area_2(self, obj):
    #     if not obj.final_address or not obj.final_address.area.parent:
    #         return ''
    #     return str(obj.final_address.area.name)


class MissionAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    미션 추가 어드민
    """
    def get_additional_urls(self):
        return {
            'cancel': '<id>/cancel/',
            'download_excel': 'download/excel/',
        }

    def view_download_excel(self, request, *args, **kwargs):
        return MissionExcelDownloadView.as_view()(request, *args, **kwargs)

    def view_cancel(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        if obj.cancel():
            log_with_reason(request.user, obj, 'changed', {'미션 상태': '관리자 취소'})
            messages.success(request, '미션이 취소되었습니다.')
        else:
            messages.error(request, '미션이 취소할 수 없는 상태입니다.')
        return redirect(referer)


@admin.register(Mission)
class MissionAdmin(FilteredExcelDownloadMixin, MissionAdditionalAdmin, UserCodeSearchMixin, RelatedAdminMixin,
                   BaseAdmin):
    """
    미션 어드민
    """
    list_display = ('code', 'user', 'mission_type', 'get_final_area_display', 'get_content_short_display',
                    'requested_datetime', 'due_datetime', 'get_bids_count_display',
                    'get_matching_info_display', 'get_state_display')
    autocomplete_fields = ('stopovers', 'final_address', 'request_areas')
    search_fields = ('code', 'user__code', 'user__mobile', 'content')
    remove_add_fields = ('mission_type',)
    remove_change_fields = ('mission_type', 'final_address')
    inlines = (BidsInline, MissionFileInline)
    change_form_template = 'admin/missions/mission/change_form.html'
    list_filter = (MissionStateFilter, RequestPlatformFilter, 'template', MissionAreaFilter, 'is_at_home')
    actions = ('action_set_at_home_on', 'action_set_at_home_off')
    date_hierarchy = 'created_datetime'
    excel_download_view = MissionExcelDownloadView

    def action_set_at_home_on(self, request, queryset):
        cnt = queryset.filter(is_at_home=False).update(is_at_home=True)
        messages.success(request, '%s개의 미션을 고객홈에 설정했습니다.' % cnt)
        CustomerHomeMissionSerializer.cache()
    action_set_at_home_on.short_description = '선택한 미션을 고객홈에 설정'

    def action_set_at_home_off(self, request, queryset):
        cnt = queryset.filter(is_at_home=True).update(is_at_home=False)
        messages.success(request, '%s개의 미션을 고객홈에서 설정해제했습니다.' % cnt)
        CustomerHomeMissionSerializer.cache()
    action_set_at_home_off.short_description = '선택한 미션을 고객홈에서 설정해제'

    def get_fields(self, request, obj=None):
        fields = ['user', 'content', 'get_product_display', 'due_datetime', 'is_due_date_modifiable', 'is_due_time_modifiable',
                  'stopovers', 'final_address', 'amount_high', 'amount_low', 'charge_rate',
                  'is_point_reward']
        if obj:
            fields += ['requested_datetime', 'canceled_datetime', 'bid_closed_datetime', 'bid_limit_datetime',
                       'get_payment_display', 'get_safety_numbers_display', 'get_push_result_display',
                       'is_at_home', 'image_at_home']
        else:
            fields.insert(0, 'mission_type')
        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ['code', 'created_datetime', 'requested_datetime', 'canceled_datetime',
                           'bid_closed_datetime', 'bid_limit_datetime', 'user']
        if obj:
            readonly_fields += ['mission_type', 'stopovers', 'final_address', 'is_point_reward',
                                'amount_high', 'amount_low', 'get_payment_display', 'get_safety_numbers_display',
                                'get_product_display', 'get_push_result_display']
            if obj.mission_type_id in (1, 2):
                readonly_fields += ['content', 'due_datetime', 'is_due_date_modifiable', 'is_due_time_modifiable']
        return readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        if 'image_at_home' in request.FILES and request.FILES['image_at_home']:
            obj.handle_image_at_home(form.cleaned_data['image_at_home'])
        super(MissionAdmin, self).save_model(request, obj, form, change)
        if not change:
            obj.request()

    def get_changeform_initial_data(self, request):
        initial = super(MissionAdmin, self).get_changeform_initial_data(request)
        initial['user'] = request.user
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'mission_type':
            kwargs['queryset'] = MissionType.objects.exclude(id=1).order_by('id')
        if db_field.name == 'user':
            kwargs['queryset'] = get_user_model().objects.filter(is_staff=True)
        return super(MissionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def save_formset(self, request, form, formset, change):
        if formset.model is MissionFile:
            for f in formset.forms:
                if 'attach' in f.changed_data:
                    obj = f.save()
                    obj.handle_attach(f.cleaned_data['attach'])
        if formset.model is Bid:
            for f in formset.forms:
                if 'helper' in f.changed_data:
                    obj = f.save()
                    obj.is_assigned = True
                    obj.save()
        return super(MissionAdmin, self).save_formset(request, form, formset, change)

    def get_queryset(self, request):
        qs = super(MissionAdmin, self).get_queryset(request)
        return qs.prefetch_related('bids')

    def get_product_display(self, obj):
        rtn = []
        for item in obj.product:
            rtn.append('<h6><small>[%s]</small><br/>%s</h5><p class="pull-right">수량 : %s</p><p>제품 가격 : %s</p>' % (
                item['itemId'], item['title'], add_comma(item['quantity']), add_comma(item['price'])
            ))
        return mark_safe('<hr>'.join(rtn))
    get_product_display.short_description = '제품 정보'

    def get_payment_display(self, obj):
        paid = Payment.objects.filter(bid__mission=obj, is_succeeded=True)
        return mark_safe('<hr/>'.join([p.summary for p in paid]))
    get_payment_display.short_description = '결제 정보'

    def get_safety_numbers_display(self, obj):
        rtn = ''
        bid = obj.won.last()
        if bid:
            if bid.customer_safety_number:
                if bid.customer_safety_number.is_active:
                    prefix = suffix = ''
                else:
                    prefix = '<del>'
                    suffix = '</del>'
                rtn += '<p> 고객 : %s%s%s</p>' % (prefix, bid.customer_safety_number, suffix)
            if bid.helper_safety_number:
                if bid.helper_safety_number.is_active:
                    prefix = suffix = ''
                else:
                    prefix = '<del>'
                    suffix = '</del>'
                rtn += '<p> 헬퍼 : %s%s%s</p>' % (prefix, bid.helper_safety_number, suffix)
        return mark_safe(rtn)
    get_safety_numbers_display.short_description = '안심번호 할당'

    def get_push_result_display(self, obj):
        if obj.push_result:
            return mark_safe('<a href="/admin/notification/notification/%s/change/">%s</a>' % (
                obj.push_result.id,
                ('발송성공 %s 건' % obj.push_result.result['success_count']) if obj.push_result.result and 'success_count' in obj.push_result.result else '미발송'
            ))
        return obj.push_result.result if obj.push_result else '-'
    get_push_result_display.short_description = '푸시 결과'

    # def get_request_areas_display(self, obj):
    #     return [o.name for o in obj.request_areas.all()]
    # get_request_areas_display.short_description = '요청지역'
    # get_request_areas_display.admin_order_field = 'request_areas__name'

    def get_final_area_display(self, obj):
        return str(obj.final_address.area) if obj.final_address else '-'
    get_final_area_display.short_description = '수행지역'
    get_final_area_display.admin_order_field = 'final_address__area__id'

    def get_content_short_display(self, obj):
        return obj.get_content_shorten(20)
    get_content_short_display.short_description = '미션내용'
    get_content_short_display.admin_order_field = 'content'

    def get_bids_count_display(self, obj):
        return obj.bids.count()
    get_bids_count_display.short_description = '입찰'
    get_bids_count_display.admin_order_field = 'bids_count'

    def get_matching_info_display(self, obj):
        bid = obj.won.last()
        if bid:
            return mark_safe('<a class="btn btn-sm btn-helper" href="/admin/accounts/helper/%s/change/">%s</a> ￦%s' % (
                bid.helper_id, bid.helper, add_comma(bid.amount)
            ))
        return '-'
    get_matching_info_display.short_description = '낙찰정보'
    get_matching_info_display.admin_order_field = 'bids_count'


class BidAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    미션 입찰 추가 어드민
    """
    def get_additional_urls(self):
        return {
            'cancel': '<id>/cancel/',
            'force_finish': '<id>/force_finish/',
            'force_close_anytalk': '<id>/force_close_anytalk/',
            'done_request_accept': '<id>/done_request/accept/',
            'done_request_reject': '<id>/done_request/reject/',
        }

    def view_cancel(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        if obj.admin_cancel():
            log_with_reason(request.user, obj, 'changed', {'미션 상태': '관리자 취소'})
            messages.success(request, '미션입찰이 취소되었습니다.')
        else:
            messages.error(request, '미션입찰이 취소할 수 없는 상태입니다.')
        return redirect(referer)

    def view_force_finish(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        if obj.finish():
            log_with_reason(request.user, obj, 'changed', {'미션 상태': '관리자 강제 완료처리'})
            messages.success(request, '미션이 강제 완료처리되었습니다.')
        else:
            messages.error(request, '미션이 강제 완료처리할 수 없는 상태입니다.')
        return redirect(referer)

    def view_force_close_anytalk(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.close_anytalk()
        log_with_reason(request.user, obj, 'changed', {'미션 상태': '애니톡 강제 종료'})
        messages.success(request, '미션의 애니톡이 강제 종료 처리되었습니다.')
        return redirect(referer)

    def view_done_request_accept(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        if obj.done_requested and obj.done_requested.accept():
            log_with_reason(request.user, obj, 'changed', {'미션 상태': '수행완료 승인'})
            messages.success(request, '미션의 수행완료 요청이 승인되었습니다.')
        else:
            messages.error(request, '미션의 수행완료 요청을 승인할 수 없는 상태입니다.')
        return redirect(referer)

    def view_done_request_reject(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        if obj.done_requested and obj.done_requested.reject():
            log_with_reason(request.user, obj, 'changed', {'미션 상태': '수행완료 거부'})
            messages.success(request, '미션의 수행완료 요청이 거부되었습니다.')
        else:
            messages.error(request, '미션의 수행완료 요청을 거부할 수 없는 상태입니다.')
        return redirect(referer)


@admin.register(Bid)
class BidAdmin(BidAdditionalAdmin, UserCodeSearchMixin, BaseAdmin):
    """
    미션 입찰 어드민
    """
    list_display = ('get_mission_display', 'get_helper_display', 'amount', 'is_assigned', 'get_state_functions')
    readonly_fields = ('get_helper_display',)
    # fields = ('get_helper_display', )
    inlines = (InteractionInline, )
    change_form_template = 'admin/bid/change_form.html'
    fields = ['get_mission_display', 'helper', 'amount', 'is_assigned', 'content', 'get_location_display', 'due_datetime',
              'get_active_due_display', 'applied_datetime', 'won_datetime', '_canceled_datetime', '_done_datetime',
              '_anytalk_closed_datetime', 'get_helper_display']
    search_fields = ('mission__code', 'mission__user__username', 'helper__user__code', 'helper__user__username',
                     'helper__user__mobile', 'content',)
    list_filter = (IsMultiMissionFilter, BidStateFilter, 'is_assigned',)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_mission_display(self, obj):
        prefix = '<i class="fa fa-lg fa-user%s text-secondary"></i> ' % ('s' if obj.area_mission else '')
        return mark_safe(prefix + str(obj._mission))
    get_mission_display.short_description = '미션'

    def get_active_due_display(self, obj):
        return obj.active_due
    get_active_due_display.short_description = '실제적용 미션 일시'

    def get_helper_display(self, obj):
        return obj.helper.user.username
    get_helper_display.short_description = '헬퍼'
    get_helper_display.admin_order_field = 'helper__user__username'

    def get_state_functions(self, obj):
        return bid_state_menu(obj, size='sm')
    get_state_functions.short_description = '상태'
    get_state_functions.admin_order_field = 'saved_state'


class TargetUserTypeFilter(admin.SimpleListFilter):
    """
    대상 유져타입 필터
    """
    title = '대상 유져타입'
    parameter_name = 'target_user_type'

    def lookups(self, request, model_admin):
        return (
            ('customer', '고객'),
            ('helper', '헬퍼'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == 'helper':
            queryset = queryset.filter(bid__isnull=False)
        elif val == 'customer':
            queryset = queryset.filter(mission__isnull=False)
        return queryset


class TargetCustomerFilter(admin.SimpleListFilter):
    """
    대상 고객유져 필터
    """
    title = '대상 고객유져'
    parameter_name = 'target_customer_id'

    def lookups(self, request, model_admin):
        return ((None, '-- 직접선택할 수 없음 --'),)

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            queryset = queryset.get_customer_received(val)
        return queryset


class TargetHelperFilter(admin.SimpleListFilter):
    """
    대상 고객유져 필터
    """
    title = '대상 헬퍼유져'
    parameter_name = 'target_helper_user_id'

    def lookups(self, request, model_admin):
        return ((None, '-- 직접선택할 수 없음 --'),)

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            queryset = queryset.get_helper_received(val)
        return queryset


# class ReviewAdminForm(forms.ModelForm):
#     _created_datetime = forms.DateTimeField(label='작성일시', required=False)
#
#     def save(self, commit=True):
#         obj = super(ReviewAdminForm, self).save(commit)
#         if commit and self._created_datetime:
#             obj.created_datetime = self._created_datetime
#             self._created_datetime = None
#             obj.save()q
#         return obj
#
#     class Meta:
#         model = Review
#         fields = ('created_user', '_is_created_user_helper', '_received_user', 'stars', 'content', '_created_datetime')


@admin.register(Review)
class ReviewAdmin(UserCodeSearchMixin, RelatedAdminMixin, BaseAdmin):
    """
    리뷰 어드민
    """
    list_display = ('get_mission_display', 'get_created_user_display', 'get_received_user_display',
                    'get_stars_display', 'content', 'created_datetime', 'is_active')
    search_fields = ('bid__mission__user__username', 'bid__mission__user__code',
                     'bid__helper__user__username', 'bid__helper__user__code',
                     'created_user__username', 'created_user__code',
                     '_received_user__username', '_received_user__code')
    list_display_links = None
    list_filter = (TargetCustomerFilter, TargetHelperFilter)
    actions = ('action_activate', 'action_deactivate')
    fields = ('created_user', '_is_created_user_helper', '_received_user', 'stars', 'content')
    # form = ReviewAdminForm
    change_form_template = 'admin/change_form_split.html'
    autocomplete_fields = ('created_user', '_received_user')
    remove_add_fields = ('created_user', '_received_user')
    remove_change_fields = ('created_user', '_received_user')
    remove_delete_fields = ('created_user', '_received_user')

    # def has_add_permission(self, request):
    #     return False

    def has_change_permission(self, request, obj=None):
        return False

    def action_activate(self, request, queryset):
        queryset.update(is_active=True)
    action_activate.short_description = '선택한 리뷰를 활성화'
    action_activate.allowed_permissions = ('delete',)

    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)
    action_deactivate.short_description = '선택한 리뷰를 비활성화'
    action_deactivate.allowed_permissions = ('delete',)

    def get_mission_display(self, obj):
        if not obj.bid_id:
            return ''
        return mark_safe('<a class="%s" href="/admin/missions/mission/%s/change/">%s</a>' % (
            'btn btn-sm btn-info', obj.bid.mission.id, obj.bid.mission
        ))
    get_mission_display.short_description = '미션'
    get_mission_display.admin_order_field = 'bid__mission'

    def get_created_user_display(self, obj):
        klass = 'btn btn-sm btn-helper' if obj.is_created_user_helper else 'btn btn-sm btn-customer'
        return mark_safe('<a class="%s" href="/admin/accounts/user/%s/change/">%s</a>' % (
            klass, obj.created_user.id, obj.created_user
        ))
    get_created_user_display.short_description = '작성자'
    get_created_user_display.admin_order_field = '_created_user'

    def get_received_user_display(self, obj):
        klass = 'btn btn-sm btn-customer' if obj.is_created_user_helper else 'btn btn-sm btn-helper'
        return mark_safe('<a class="%s" href="/admin/accounts/user/%s/change/">%s</a>' % (
            klass, obj.received_user.id, obj.received_user
        ))
    get_received_user_display.short_description = '리뷰 대상'
    get_received_user_display.admin_order_field = '_received_user'


@admin.register(Report)
class ReportAdmin(UserCodeSearchMixin, BaseAdmin):
    """
    신고 어드민
    """
    list_display = ('get_reported_user', 'get_content_display', 'get_reported_info', 'created_user', 'created_datetime')
    list_display_links = None
    search_fields = ('mission__code', 'mission__user__username', 'bid__mission__user__username',
                     'bid__mission__user__code', 'bid__helper__user__username', 'bid__helper__user__code')
    list_filter = (TargetUserTypeFilter, TargetCustomerFilter, TargetHelperFilter)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_reported_info(self, obj):
        try:
            object_id = obj.mission_id or obj.bid.mission_id
        except:
            return ''
        if not object_id:
            return ''
        content = '<a class="btn btn-sm btn-info" href="%s">관련 미션</a>' % reverse(
            'admin:missions_mission_change',
            kwargs={'object_id': object_id}
        )
        if obj.bid:
            content += ' <a class="btn btn-sm btn-info" href="%s">관련 입찰</a>' % reverse(
                'admin:missions_bid_change',
                kwargs={'object_id': obj.bid.id}
            )
        return mark_safe(content)
    get_reported_info.short_description = '관련 내용'

    def get_reported_user(self, obj):
        if obj.mission:
            return mark_safe('<a class="btn btn-sm btn-info" href="%s">[고객] %s</a>' % (reverse(
                'admin:accounts_user_change',
                kwargs={'object_id': obj.mission.user_id}), obj.mission.user
            ))
        if obj.bid:
            return mark_safe('<a class="btn btn-sm btn-info" href="%s">%s</a>' % (reverse(
                'admin:accounts_user_change',
                kwargs={'object_id': obj.bid.helper.user_id}), obj.bid.helper
            ))
    get_reported_user.short_description = '신고대상'

    def get_content_display(self, obj):
        return mark_safe(obj.content.replace('\n', '<br/>'))
    get_content_display.short_description = '상세 사유'


@admin.register(PenaltyPoint)
class PenaltyPointAdmin(RelatedAdminMixin, UserCodeSearchMixin, BaseAdmin):
    """
    벌점 어드민
    """
    list_display = ('user', 'point', 'mission', 'reason', 'get_detail_display', 'created_datetime')
    list_display_links = None
    list_filter = ('reason', 'point')
    search_fields = ('user__code', 'user__username', 'mission__code', 'detail')
    autocomplete_fields = ('user', 'mission')
    remove_add_fields = ('user', 'mission')
    remove_change_fields = ('user', 'mission')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_detail_display(self, obj):
        return mark_safe(obj.detail.replace('\n', '<br/>'))
    get_detail_display.short_description = '상세 사유'


@admin.register(CustomerService)
class CustomerServiceAdmin(RelatedAdminMixin, UserCodeSearchMixin, BaseAdmin):
    """
    상담 내역 어드민
    """
    list_display = ('user', 'mission', 'content', 'created_user')
    autocomplete_fields = ('user', 'mission')
    remove_add_fields = ('user', 'mission')
    remove_change_fields = ('user', 'mission')
    remove_delete_fields = ('user', 'mission')
    fields = ('user', 'mission', 'content')
    search_fields = ('content', 'user__code', 'user__username')
    list_filter = (CreatedAdminUserFilter,)

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_form(self, request, form, change):
        obj = super(CustomerServiceAdmin, self).save_form(request, form, change)
        if not obj.created_user:
            obj.created_user = request.user
            obj.save()
        return obj

    def save_model(self, request, obj, form, change):
        return super(CustomerServiceAdmin, self).save_model(request, obj, form, change)


@admin.register(TemplateCategory)
class TemplateCategoryAdmin(BaseAdmin):
    """
    미션 템플릿 카테고리 어드민
    """
    list_display = ('get_category_display', 'get_depth_display')
    search_fields = ('name', 'parent__name', 'parent__parent__name')
    autocomplete_fields = ('parent',)
    list_filter = (CategoryDepthFilter,)

    def get_category_display(self, obj):
        return str(obj)
    get_category_display.short_description = '카테고리'
    get_category_display.admin_order_field = 'order_name'

    def get_depth_display(self, obj):
        return obj.depth
    get_depth_display.short_description = '카테고리 계층'
    # get_depth_display.admin_order_field = '-parent__id'

    def get_queryset(self, request):
        qs = super(TemplateCategoryAdmin, self).get_queryset(request)
        return qs.orderable('order_name')


@admin.register(TemplateTag)
class TemplateTagAdmin(BaseAdmin):
    """
    템플릿 태그 어드민
    """
    list_display = ('name', 'get_template_count_display')
    fields = ('name', 'synonyms', 'image', 'weight', 'get_templates_display')
    search_fields = ('name',)

    def has_add_permission(self, request):
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('name', 'get_templates_display')
        else:
            return ('get_templates_display',)

    def get_queryset(self, request):
        qs = super(TemplateTagAdmin, self).get_queryset(request)
        qs = qs.annotate(template_count=Count('templates__id'))
        return qs

    def get_template_count_display(self, obj):
        return obj.template_count
    get_template_count_display.short_description = '템플릿수'
    get_template_count_display.admin_order_field = 'template_count'

    def get_templates_display(self, obj):
        return mark_safe(''.join([
            '<p><a href="/admin/missions/missiontemplate/%s/change/" class="btn btn-info">%s</a></p>'
            % (t.id, t) for t in obj.templates.all()
        ]))
    get_templates_display.short_description = '템플릿'
    get_templates_display.admin_order_field = 'templates'


class TemplateQuestionInline(admin.TabularInline):
    """
    템플릿 질문 인라인
    """
    model = TemplateQuestion
    extra = 1
    min = 1
    ordering = ('order_no', 'id')
    template = 'admin/missions/mission/inline_template.html'

    def has_change_permission(self, request, obj=None):
        if obj and obj.requested_count > 0:
            return False
        return True

    def has_add_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(MissionTemplate)
class MissionTemplateAdmin(ImageWidgetMixin, BaseAdmin):
    """
    미션 템플릿 어드민
    """
    list_display = ('get_name_display', 'get_image_display', 'get_tags_display', 'get_mission_count_display',
                    'get_mission_done_count_display', 'get_mission_done_rate_display', 'get_average_amount',
                    'get_link_to_web', 'get_link_to_missions', 'is_active')
    autocomplete_fields = ('category', 'auto_stopover_address')
    inlines = (TemplateQuestionInline,)
    image_fields = ('image',)
    filter_horizontal = ('tags',)
    # formfield_overrides = {
    #     ManyToManyField: {
    #         'widget': forms.SelectMultiple(),
    #     }
    # }

    def get_queryset(self, request):
        qs = super(MissionTemplateAdmin, self).get_queryset(request)
        qs = qs.annotate(requested_count=Count('missions__id', distinct=True))
        qs = qs.annotate(done_count=Sum(Case(When(missions__bids__saved_state='done', then=1), output_field=IntegerField(), default=0)))
        qs = qs.annotate(done_avg=Avg(Case(When(missions__bids__saved_state='done', then='missions__bids__amount'))))
        qs = qs.annotate(done_rate=Case(When(requested_count__gt=0, then=F('done_count') * 100 / F('requested_count')), output_field=FloatField()))
        return qs

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ['템플릿 기본정보', {'fields': (
                'category', 'tags', 'name', 'description', 'image', 'mission_type', 'is_active', 'content_display'
            )}],
        ]
        if request.user.is_superuser:
            fieldsets.insert(0, ['협력사 정보', {'fields': (
                'partnership', 'auto_stopover_address', 'matching_success_url'
            )}]),
        return fieldsets

    def has_delete_permission(self, request, obj=None):
        if obj and obj.requested_count > 0:
            return False
        return True

    def get_name_display(self, obj):
        return mark_safe('[%s]<br/>%s' % (obj.category, obj.name))
    get_name_display.short_description = '템플릿명'
    get_name_display.admin_order_field = 'name'

    def get_questions_display(self, obj):
        return ', '.join([q.name for q in obj.questions.all().order_by('order_no', 'id')])
    get_questions_display.short_description = '질문 항목'

    def get_tags_display(self, obj):
        return ' '.join(['#' + t.name for t in obj.tags.all()])
    get_tags_display.short_description = '태그'

    def get_mission_count_display(self, obj):
        return obj.requested_count
    get_mission_count_display.short_description = '미션수'
    get_mission_count_display.admin_order_field = 'requested_count'

    def get_mission_done_count_display(self, obj):
        return obj.done_count
    get_mission_done_count_display.short_description = '완료 미션수'
    get_mission_done_count_display.admin_order_field = 'done_count'

    def get_mission_done_rate_display(self, obj):
        return ('%.1f%%' % obj.done_rate) if obj.done_rate is not None else '-'
    get_mission_done_rate_display.short_description = '완료율'
    get_mission_done_rate_display.admin_order_field = 'done_rate'

    def get_average_amount(self, obj):
        return add_comma(int(obj.done_avg)) if obj.done_avg else '-'
    get_average_amount.short_description = '평균 수행비'
    get_average_amount.admin_order_field = 'done_avg'

    def get_link_to_web(self, obj):
        return mark_safe('<a href="/template/%s/%s/" class="btn btn-sm btn-secondary"><i class="fa fa-web"></i> 웹 템플릿</a>' % (obj.id, obj.slug))
    get_link_to_web.short_description = '웹 바로가기'

    def get_link_to_missions(self, obj):
        return mark_safe('<a href="/admin/missions/mission/?template__id__exact=%s" class="btn btn-sm btn-secondary"><i class="fa fa-list"></i> 미션 목록</a>' % obj.id)
    get_link_to_missions.short_description = '미션 바로가기'
