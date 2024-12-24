import dateutil.parser

from django.contrib import admin
from django.contrib import messages
from django.utils import timezone

from common.admin import RelatedAdminMixin, ImageWidgetMixin, AdminPageBaseView
from .models import Area, Popup


"""
기본 어드민
"""


class BaseAdmin(admin.ModelAdmin):
    """
    사이트 글로벌 어드민
    """
    list_per_page = 20
    actions_on_top = False
    actions_on_bottom = True
    ordering = ('-id',)


class ParentAreaFilter(admin.SimpleListFilter):
    """
    상위 지역 필터
    """
    title = '상위 지역'
    parameter_name = 'parent_area'

    def lookups(self, request, model_admin):
        parents = Area.objects.filter(parent__isnull=True)
        return ((p.id, p.name) for p in parents)

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(parent_id=self.value())
        return queryset


@admin.register(Area)
class AreaAdmin(RelatedAdminMixin, BaseAdmin):
    """
    지역 어드민
    """
    list_display = ('__str__', 'nearby_string')
    autocomplete_fields = ('parent', 'nearby')
    search_fields = ('name', )
    remove_add_fields = ('parent', 'nearby')
    remove_change_fields = ('parent', 'nearby')
    list_filter = (ParentAreaFilter, )

    def get_queryset(self, request):
        return super(AreaAdmin, self).get_queryset(request).filter(parent__isnull=False)


@admin.register(Popup)
class PopupAdmin(ImageWidgetMixin, BaseAdmin):
    """
    팝업 어드민
    """
    list_display = ('title', 'get_location_display', 'get_target_type_display', 'get_end_state')
    actions = ('action_activate', 'action_deactivate')
    list_filter = ('location', 'target_type', 'is_active')
    search_fields = ('title', 'content', 'target_id', 'location')
    exclude = ('is_active',)
    image_fields = ('image',)

    def has_delete_permission(self, request, obj=None):
        return False

    def action_activate(self, request, queryset):
        cnt = queryset.filter(is_active=False).update(is_active=True)
        messages.success(request, '%s개의 팝업을 활성화 했습니다.' % cnt)
    action_activate.short_description = '선택한 팝업을 활성화'
    # action_activate.allowed_permissions = ('delete',)
    # todo: 권한 추후 조정

    def action_deactivate(self, request, queryset):
        cnt = queryset.filter(is_active=True).update(is_active=False)
        messages.success(request, '%s개의 팝업을 비활성화 했습니다.' % cnt)
    action_deactivate.short_description = '선택한 팝업을 비활성화'
    # action_deactivate.allowed_permissions = ('delete',)
    # todo: 권한 추후 조정

    def get_end_state(self, obj):
        if not obj.is_active:
            return '비활성화'
        state = '진행중' if obj.is_live else '종료'
        return '%s (~%s)' % (state, obj.end_datetime.strftime('%Y년 %m월 %d일 %H시 %M분'))
    get_end_state.short_description = '라이브'


"""
추가 어드민 페이지
"""


def get_preset_dates(preset=None):
    current_date = timezone.now().date()
    if preset in ('today', None):
        end_date = current_date
        start_date = current_date
    if preset == 'yesterday':
        end_date = current_date - timezone.timedelta(days=1)
        start_date = end_date
    if preset == 'month':
        end_date = current_date
        start_date = end_date - timezone.timedelta(days=30)
    if preset == 'week':
        end_date = current_date
        start_date = end_date - timezone.timedelta(days=7)
    if preset == '3month':
        end_date = current_date
        start_date = end_date - timezone.timedelta(days=90)
    if preset == 'thismonth':
        end_date = current_date
        start_date = timezone.datetime(year=end_date.year, month=end_date.month, day=1).date()
    if preset == 'prevmonth':
        end_date = timezone.datetime(
            year=current_date.year, month=current_date.month, day=1
        ).date() - timezone.timedelta(days=1)
        start_date = timezone.datetime(year=end_date.year, month=end_date.month, day=1).date()
    if preset == 'ppmonth':
        end_date = timezone.datetime(
            year=current_date.year, month=current_date.month, day=1
        ).date() - timezone.timedelta(days=1)
        end_date = timezone.datetime(
            year=end_date.year, month=end_date.month, day=1
        ).date() - timezone.timedelta(days=1)
        start_date = timezone.datetime(year=end_date.year, month=end_date.month, day=1).date()
    return (current_date, start_date, end_date)


class StatisticsView(AdminPageBaseView):
    """
    통계 분석 뷰
    """
    slugs = {
        'user': '회원',
        'mission': '미션',
        'payment': '결제',
        'recommend': '추천 시스템',
        'finance': '비용과 수익',
    }
    slug = ''
    current_date = None
    start_date = None
    end_date = None

    def dispatch(self, request, *args, **kwargs):
        self.slug = kwargs.get('slug', '')
        preset = request.GET.get('preset', None) or None
        start_date = request.GET.get('start') or None
        end_date = request.GET.get('end') or None
        if preset or (not start_date and not end_date):
            self.set_preset_dates(preset)
        else:
            if start_date:
                self.start_date = dateutil.parser.parse(start_date).date()
            else:
                self.set_preset_dates()
            if end_date:
                self.end_date = dateutil.parser.parse(end_date).date()
            else:
                self.end_date = self.current_date
        return super(StatisticsView, self).dispatch(request, *args, **kwargs)

    def set_preset_dates(self, preset=None):
        self.current_date, self.start_date, self.end_date = get_preset_dates(preset)

    def get_template_names(self):
        return ['admin/statistics/%s.html' % self.slug]

    def get_context_data(self, **kwargs):
        context = super(StatisticsView, self).get_context_data(**kwargs)
        context['slug'] = self.slug
        context['title'] = self.slugs[self.slug]
        context['current_date'] = self.current_date
        context['start_date'] = self.start_date
        context['end_date'] = self.end_date
        return context


_admin_site_get_urls = admin.site.get_urls

def add_custom_urls():
    from django.urls import path
    urls = _admin_site_get_urls()
    urls += [
        path('statistics/<slug:slug>/', admin.site.admin_view(StatisticsView.as_view()), name='statistics'),
    ]
    return urls

admin.site.get_urls = add_custom_urls


