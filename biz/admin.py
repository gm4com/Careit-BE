from django.contrib import admin, messages
from django.db.models import Count, Q
from django import forms
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import localize
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.shortcuts import redirect

from common.admin import RelatedAdminMixin, AdditionalAdminUrlsMixin, ChangeFormSplitMixin
from missions.models import MissionTemplate
from .models import (
    Partnership, PartnershipUserRelation, Campaign, CampaignBanner,
    REQUEST_ACCEPT_STATUS, REQUEST_ACCEPT_STATUS_FILTERS, CAMPAIGN_TYPES
)
from .templatetags.biz_admin import request_accept_status_menu


"""
Forms and Inlines
"""


class PartnershipUserInline(RelatedAdminMixin, admin.TabularInline):
    """
    협력사 유져 인라인
    """
    model = PartnershipUserRelation
    verbose_name = verbose_name_plural = '협력사 관리 유져'
    extra = 0
    fields = ('user', 'role')
    autocomplete_fields = ('user',)
    remove_add_fields = ('user',)
    remove_change_fields = ('user',)
    remove_delete_fields = ('user',)


class CampaignInline(admin.TabularInline):
    """
    캠페인 인라인
    """
    model = Campaign
    extra = 0
    fields = ('title_link', 'campaign_type', 'get_state_display')
    readonly_fields = ('title_link', 'campaign_type', 'get_state_display')

    def get_queryset(self, request):
        return self.model.objects.select_related('partnership')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def title_link(self, instance):
        url = reverse(f'admin:{instance._meta.app_label}_{instance._meta.model_name}_change', args=(instance.id,))
        return format_html(f'<a href="{url}">{instance.title}</a>')

    title_link.short_description = '제목'


class MissionTemplateInline(admin.TabularInline):
    """
    캠페인 인라인
    """
    model = MissionTemplate
    verbose_name = verbose_name_plural = '미션 API 이용 템플릿'
    extra = 0
    fields = readonly_fields = ('title_link', 'tags', 'mission_count')

    def get_queryset(self, request):
        return self.model.objects.select_related('partnership')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def title_link(self, obj):
        url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=(obj.id,))
        return format_html(f'<a href="{url}">{obj.name}</a>')
    title_link.short_description = '템플릿'

    def mission_count(self, obj):
        url = reverse(f'admin:missions_mission_changelist') + '?template__id__exact=%s' % obj.id
        return format_html(f'<a href="{url}">{obj.missions.count()}</a>')
        return 
    mission_count.short_description = '미션수'



class CampaignBannerInline(admin.TabularInline):
    """
    캠페인 이미지 인라인
    """
    model = CampaignBanner
    extra = 0
    fields = ('get_image_display', 'location', 'get_state_display', 'get_state_functions',)
    readonly_fields = ('get_image_display', 'location', 'get_state_display', 'get_state_functions',)

    def get_queryset(self, request):
        return self.model.objects.select_related('campaign').filter(is_active=True).order_by('-id')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_image_display(self, obj):
        ext = obj.image.url.split('.')[-1].lower()
        if ext in ('jpeg', 'jpg', 'gif', 'bmp', 'png'):
            img = '<img src="%s" class="crop-100-100">' % obj.image.url
        else:
            img = '%s 파일' % ext
        return mark_safe('<a href="%s" target="_blank">%s</a>' % (obj.image.url, img))

    get_image_display.short_description = '미리보기'

    def get_state_functions(self, obj):
        return request_accept_status_menu(obj, size='sm', url_model_name='campaignbanner') if obj else ''
    get_state_functions.short_description = '상태'


"""
Filters
"""


class PartnershipStateFilter(admin.SimpleListFilter):
    """
    파트너쉽 상태 필터
    """
    title = '파트너쉽 상태'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return REQUEST_ACCEPT_STATUS

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            queryset = queryset.filter(**REQUEST_ACCEPT_STATUS_FILTERS[value])
        return queryset


class CampaignStateFilter(admin.SimpleListFilter):
    """
    캠페인 상태 필터
    """
    title = '캠페인 상태'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return REQUEST_ACCEPT_STATUS

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            queryset = queryset.filter(**REQUEST_ACCEPT_STATUS_FILTERS[value])
        return queryset


class CampaignBannerStateFilter(admin.SimpleListFilter):
    """
    캠페인 배너 이미지 상태 필터
    """
    title = '배너 이미지 상태'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return REQUEST_ACCEPT_STATUS

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            queryset = queryset.filter(**REQUEST_ACCEPT_STATUS_FILTERS[value])
        return queryset


class CampaignTypeFilter(admin.SimpleListFilter):
    """
    캠페인 종류 필터
    """
    title = '캠페인 종류'
    parameter_name = 'campaign_type'

    def lookups(self, request, model_admin):
        return CAMPAIGN_TYPES

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            queryset = queryset.filter(campaign_type=value)
        return queryset


"""
Admins
"""


class RequestAcceptStaTusMixin:
    """애니비즈 요청 수락 여부 상태 조회시"""
    def get_state_with_datetime_display(self, obj):
        datetime_display = None
        if obj.state == 'requested':
            datetime_display = obj.created_datetime
        elif obj.state == 'activated':
            datetime_display = obj.accepted_datetime
        elif obj.state == 'rejected':
            datetime_display = obj.rejected_datetime
        if datetime_display:
            return '%s (%s)' % (obj.get_state_display(), localize(datetime_display))
        return obj.get_state_display()

    get_state_with_datetime_display.short_description = ''


class RequestAcceptStaTusAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    파트너쉽 어드민
    """

    def get_additional_urls(self):
        return {
            'activate': '<id>/activate/',
            'deactivate': '<id>/deactivate/',
            'reject': '<id>/reject/',
        }

    def view_activate(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.accept()
        messages.success(request, '활성화했습니다.')
        return redirect(referer)

    def view_deactivate(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.is_active = False
        obj.save()
        messages.success(request, '비활성화했습니다.')
        return redirect(referer)

    def view_reject(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.reject()
        messages.success(request, '승인 반려했습니다.')
        return redirect(referer)


class PartnershipAdditionalAdmin(RequestAcceptStaTusAdditionalAdmin):
    """
    
    """
    def get_additional_urls(self):
        urls = super(PartnershipAdditionalAdmin, self).get_additional_urls()
        urls.update({
            'resetsecret': '<id>/resetsecret/',
        })
        return urls

    def view_resetsecret(self, request, *args, **kwargs):
        referer = self._get_referer_or_fail(request)
        obj = self._get_object_or_fail(kwargs)
        obj.make_secret()
        messages.success(request, 'API 인증 시크릿을 설정했습니다.')
        return redirect(referer)


class PartnershipAdminForm(forms.ModelForm):
    """
    파트너쉽 어드민 폼
    """
    services = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=Partnership.ABAILABLE_SERVICES,
        label= "이용 서비스 :",
        required=False,
    )

    class Meta:
        model = Partnership
        fields = '__all__'


@admin.register(Partnership)
class PartnershipAdmin(PartnershipAdditionalAdmin, RequestAcceptStaTusMixin, ChangeFormSplitMixin,
                       admin.ModelAdmin):
    """
    파트너쉽 어드민
    """
    readonly_fields = ('created_datetime', 'updated_datetime', 'accepted_datetime', 'rejected_datetime', 'get_secret_display')
    remove_add_fields = ('address_area',)
    remove_change_fields = ('address_area',)
    autocomplete_fields = ('address_area',)
    list_filter = (PartnershipStateFilter,)
    list_display = ('name', 'code', 'get_request_state_with_datetime_display', 'get_users_count_display', 
                    'get_state_menu_function', 'get_user_mode_display')
    inlines = (PartnershipUserInline, CampaignInline, MissionTemplateInline)
    search_fields = ('name', 'code', 'business_number',)
    form = PartnershipAdminForm
    fieldsets = (
        (
            '기본정보', 
            {'fields': (
                'name', 'code', 'business_number', 'tel', 'address_area', 'address_detail', 'business_registration_photo',
                'created_datetime', 'updated_datetime', 'accepted_datetime', 'rejected_datetime'
            )}
        ),
        (
            '서비스',
            {'fields': ('services', 'get_secret_display', )}
        ),
        (
            '추천가입 리워드',
            {'fields': ('reward_when_joined', 'reward_when_mission_done', 'reward_when_mission_done_count')}
        )
    )

    def save_model(self, request, obj, form, change):
        print(request.POST)
        return super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super(PartnershipAdmin, self).get_queryset(request)
        return qs.annotate(users_count=Count('recommended_users__id'))

    def get_users_count_display(self, obj):
        return obj.users_count
    get_users_count_display.short_description = '회원수'
    get_users_count_display.admin_order_field = 'users_count'


    def get_secret_display(self, obj):
        url = reverse('admin:biz_partnership_resetsecret', kwargs={'id': obj.id})
        if obj.secret.startswith('pbkdf2_'):
            return '설정됨'
        return mark_safe('설정되지 않음 <a class="btn btn-danger btn-sm" href="%s">설정</a>' % url)
    get_secret_display.short_description = 'API 이용 시크릿'

    def get_request_state_with_datetime_display(self, obj):
        return super(PartnershipAdmin, self).get_state_with_datetime_display(obj)

    get_request_state_with_datetime_display.short_description = '파트너쉽 상태'

    def get_state_menu_function(self, obj):
        return request_accept_status_menu(obj, size='sm', url_model_name='partnership')

    get_state_menu_function.short_description = '상태'
    get_state_menu_function.admin_order_field = 'saved_state'

    def get_user_mode_display(self, obj):
        return mark_safe(
            '<a class="btn btn-sm btn-secondary" href="%s" target="_blank">사용자 화면</a> ' %
            reverse('biz:dashboard', kwargs={'code': obj.code})
        )
    get_user_mode_display.short_description = '사용자 링크'


@admin.register(PartnershipUserRelation)
class PartnershipUserAdmin(admin.ModelAdmin):
    """
    파트너쉽 유저 어드민
    """
    autocomplete_fields = ('user',)
    remove_add_fields = ('user',)
    remove_change_fields = ('user',)
    remove_delete_fields = ('user',)

    def get_queryset(self, request):
        qs = super(PartnershipUserAdmin, self).get_queryset(request)
        return qs.select_related('partnership', 'user')


@admin.register(Campaign)
class CampaignAdmin(RequestAcceptStaTusAdditionalAdmin, RequestAcceptStaTusMixin, ChangeFormSplitMixin,
                    admin.ModelAdmin):
    """
    캠페인 어드민
    """
    readonly_fields = ('campaign_code', 'partnership', 'accepted_datetime', 'rejected_datetime')
    inlines = (CampaignBannerInline,)
    list_filter = (CampaignStateFilter, CampaignTypeFilter)
    list_display = ('campaign_type', 'partnership', 'title', 'get_period_campaign',
                    'get_request_state_with_datetime_display', 'get_requested_banner_count', 'get_user_mode_display',)
    change_form_template = 'admin/biz/change_form.html'

    def get_queryset(self, request):
        return super(CampaignAdmin, self).get_queryset(request).select_related('partnership').prefetch_related('banners')

    def get_request_state_with_datetime_display(self, obj):
        return super(CampaignAdmin, self).get_state_with_datetime_display(obj)

    get_request_state_with_datetime_display.short_description = '캠페인 상태'

    def get_user_mode_display(self, obj):
        return mark_safe(
            '<a class="btn btn-sm btn-secondary" href="%s" target="_blank">사용자 화면</a> ' %
            reverse('biz:campaign-update', kwargs={'code': obj.partnership.code,
                                                   'campaign_code': obj.campaign_code, })
        )

    get_user_mode_display.short_description = '사용자 링크'

    def get_period_campaign(self, obj):
        start_datetime = obj.start_datetime.strftime('%Y-%m-%d')
        end_datetime = obj.end_datetime.strftime('%Y-%m-%d') if obj.end_datetime else ''
        return mark_safe(
            f'<span>{start_datetime} ~ {end_datetime}</span> '
        )

    get_period_campaign.short_description = '게시 요청 기간'

    def get_requested_banner_count(self, obj):
        count = [z.state for z in obj.banners.all() if z.state == 'requested']
        count = len(count) if count else ''
        return mark_safe(
            f'<div align="center">{count}</div> '
        )

    get_requested_banner_count.short_description = '승인대기 이미지'


@admin.register(CampaignBanner)
class CampaignBannerAdmin(RequestAcceptStaTusAdditionalAdmin, RequestAcceptStaTusMixin, admin.ModelAdmin):
    """
    캠페인 배너 이미지 어드민
    """
    list_display = ('campaign', 'location', 'is_active', 'accepted_datetime', 'rejected_datetime',
                    'get_request_state_with_datetime_display')
    list_filter = (CampaignBannerStateFilter,)

    def get_queryset(self, request):
        qs = super(CampaignBannerAdmin, self).get_queryset(request)
        return qs.select_related('campaign')

    def get_request_state_with_datetime_display(self, obj):
        return super(CampaignBannerAdmin, self).get_state_with_datetime_display(obj)

    get_request_state_with_datetime_display.short_description = '배너 이미지 상태'
