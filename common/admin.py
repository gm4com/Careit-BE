import json

from harupy.text import String

from django.core import serializers
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION, ContentType
from django.contrib.admin.widgets import AdminFileWidget
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponse
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.shortcuts import redirect, get_object_or_404, reverse, NoReverseMatch
from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView
from django.urls import path, reverse
from django.utils.translation import ugettext_lazy as _
from django.template import loader, Context
from django.utils import timezone

from common.utils import add_comma


admin.site.empty_value_display = '-'
admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_HEADER

# 삭제 액션 기본적으로 삭제
if not getattr(settings, 'ADMIN_DELETE_ACTION_DEFAULT', True):
    admin.site.disable_action('delete_selected')


"""
Mixins
"""


class RelatedAdminMixin:
    """
    related admin에서 버튼 삭제
    """
    remove_add_fields = []
    remove_change_fields = []
    remove_delete_fields = []

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super(RelatedAdminMixin, self).formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in self.remove_add_fields:
            formfield.widget.can_add_related = False
        if db_field.name in self.remove_change_fields:
            formfield.widget.can_change_related = False
        if db_field.name in self.remove_delete_fields:
            formfield.widget.can_delete_related = False
        return formfield


class AdditionalAdminUrlsMixin:
    def get_urls(self):
        urls = []
        for view_name, url in self.get_additional_urls().items():
            view = getattr(self, 'view_%s' % view_name)
            name = self.model._meta.label_lower.replace('.', '_') + '_' + view_name
            urls.append(path(url, view, name=name))
        return urls + super(AdditionalAdminUrlsMixin, self).get_urls()

    def get_additional_urls(self):
        return {}

    def redirect_referer(self, request):
        return redirect(self._get_referer_or_fail(request))

    def _get_referer_or_fail(self, request):
        referer = request.META.get('HTTP_REFERER', None)
        if not referer:
            raise PermissionDenied
        return referer

    def _get_object_or_fail(self, kwargs):
        return get_object_or_404(self.model, **kwargs)


class ChangeFormSplitMixin:
    change_form_template = 'admin/change_form_split.html'
    change_form_split = [6, 6]

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({'change_form_split': self.change_form_split})
        return super(ChangeFormSplitMixin, self).changeform_view(request, object_id, form_url, extra_context)


class AdminImageWidget(AdminFileWidget):
    def render(self, name, value, attrs=None, renderer=None):
        output = []
        if value and getattr(value, "url", None):
            image_url = value.url
            file_name = str(value)
            output.append('<a href="%s"><img src="%s" class="img-thumbnail d-block" alt="%s" /></a> ' % \
                          (image_url, image_url, file_name))
        output.append(super(AdminFileWidget, self).render(name, value, attrs, renderer))
        return mark_safe(''.join(output))


class ImageWidgetMixin:
    image_fields = []

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.image_fields:
            kwargs['widget'] = AdminImageWidget
            return db_field.formfield(**kwargs)
        return super(ImageWidgetMixin, self).formfield_for_dbfield(db_field, request, **kwargs)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if change:
            context.update({'image_fields': self.image_fields})
        return super(ImageWidgetMixin, self).render_change_form(request, context, add, change, form_url, obj)


"""
기본 필터
"""


class NullFilter(admin.SimpleListFilter):
    """
    기본 Null 필터
    """
    check_field = ''

    def lookups(self, request, model_admin):
        return (
            (True, _('Yes')),
            (False, _('No')),
        )

    def queryset(self, request, queryset):
        values = {'True': False, 'False': True}
        if self.value() in values:
            query = {(self.check_field or self.parameter_name) + '__isnull': values[self.value()]}
            queryset = queryset.filter(**query)
        return queryset


class AdminFilter(admin.SimpleListFilter):
    """
    관리자 필터
    """
    title = '관리자'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        admins = get_user_model().objects.filter(is_staff=True)
        return ((a.id, a.username) for a in admins)

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(**{'%s_id' % self.parameter_name: self.value()})
        return queryset


"""
기본 어드민
"""


class AdminWithFormRequest(admin.ModelAdmin):
    """
    request 오브젝트를 어드민 폼에 포함하도록 하는 ModelAdmin
    """

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(AdminWithFormRequest, self).get_form(request, obj=obj, change=change, **kwargs)

        class AdminForm(form):
            def __new__(cls, *args, **kwargs):
                kwargs['request'] = request
                return form(*args, **kwargs)

        return AdminForm


class TabularInlineWithFormRequest(admin.TabularInline):
    """
    request 오브젝트를 어드민 폼에 포함하도록 하는 ModelAdmin
    """

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(TabularInlineWithFormRequest, self).get_formset(request, obj, **kwargs)

        class InlineFormSet(formset):
            def __init__(self, *args, **kwargs):
                form_kwargs = kwargs.pop('form_kwargs', {})
                form_kwargs['request'] = request
                super(InlineFormSet, self).__init__(*args, form_kwargs=form_kwargs, **kwargs)

        return InlineFormSet


"""
추가 어드민 페이지
"""


class AdminPageBaseView(TemplateView):
    """
    추가 어드민 페이지 베이스 뷰
    """
    def get_context_data(self, **kwargs):
        context = super(AdminPageBaseView, self).get_context_data(**kwargs)
        context['site_title'] = admin.site.site_title
        context['site_header'] = admin.site.site_header
        context['site_url'] = '/'
        context['user'] = self.request.user
        context['has_permission'] = self.has_permission()
        return context

    def has_permission(self):
        return self.request.user.is_staff


"""
통계 차트
"""


class ChartDataBase:
    """
    차트 데이터 베이스
    """
    model = None
    type = None
    _data = None
    _sub_chart_data = None
    unit_prefix = ''
    unit_suffix = ''
    labels = []
    datasets = []
    base_term_field = 'created_datetime'

    def __init__(self, start, end, term_field=''):
        self.term_field = term_field or self.base_term_field
        self.start = start
        self.end = end

    def get_queryset(self, model=None, term_field=None):
        model = model or self.model
        term_field = term_field or self.term_field
        return model.objects.filter(**{
            '%s__range' % term_field: (self.start, self.end + timezone.timedelta(days=1))
        })

    def get_id(self):
        return self.type + str(timezone.now().timestamp()).replace('.', '')

    def get_date_labels(self):
        return [(self.start + timezone.timedelta(days=d)).strftime('%m-%d') for d in range(0, (self.end - self.start).days + 1)]

    def get_initialized_data(self, cnt):
        return [0]*cnt

    def get_initialized_data_dict(self, cnt, *args):
        return {key: self.get_initialized_data(cnt) for key in args}


class ChartDashboard(ChartDataBase):
    """
    차트 대시보드
    """
    template_name = 'admin/charts/dashboard.html'
    item_layout_class = 'col-3'
    options = None

    def get_entries(self):
        raise NotImplementedError

    def get_context(self):
        context = {
            'data': self.get_entries(),
            'item_layout_class': self.item_layout_class,
        }
        if self.options is not None:
            context.update({'options': self.options})
        return context

    def render(self):
        template = loader.get_template(self.template_name)
        return template.render(self.get_context())


class MultiLineChart(ChartDataBase):
    """
    멀티 선형 차트
    """
    template_name = 'admin/charts/multi_line_chart.html'
    type = 'bar'
    chart_class = ''
    table_class = ''
    sub_chart_class = ''
    sub_table_class = ''
    description_class = ''
    options = None

    def get_entries(self):
        raise NotImplementedError

    def handle_labels(self):
        self.labels = self.get_date_labels()

    def handle_data(self):
        """
        get_entries를 통해서 데이터 정보를 구현하는 경우 자동 계산
        그외의 경우에는 데이터를 직접 가공
        즉, 데이터를 직접 컨트롤할 때는 handle_data
        그 외에는 get_entries를
        둘 중에 하나만 구현하면 됨.
        """
        label_cnt = len(self.labels)
        base_type = 'bar' if label_cnt == 1 and self.type == 'bar' else 'line'

        self.datasets = []
        for key, entry in self.get_entries().items():
            # 데이터 채워넣기
            data = self.get_initialized_data(label_cnt)

            # 쿼리 데이터 업데이트
            for r in entry.pop('query'):
                i = self.labels.index(r[0].strftime('%m-%d'))
                data[i] = r[1]

            # 데이터셋에 추가
            kwargs = {
                'label': entry.pop('label'),
                'data': data,
                'type': base_type,
                'one_color': entry.pop('color')
            }
            kwargs.update(entry)
            self.datasets.append(self.make_dataset(**kwargs))

    @property
    def data(self):
        if not self.labels:
            self.handle_labels()
        if not self._data:
            self.handle_data()
            self._data = {
                'labels': self.labels,
                'datasets': self.datasets
            }
        return self._data

    def get_sub_chart_data(self):
        if not self._sub_chart_data:
            self._sub_chart_data = {
                'labels': [],
                'datasets': [{'data': [], 'backgroundColor': []}]
            }
            for dataset in self.data['datasets']:
                self._sub_chart_data['labels'].append(dataset['label'])
                self._sub_chart_data['datasets'][0]['data'].append(sum(dataset['data']))
                if 'backgroundColor' in dataset:
                    self._sub_chart_data['datasets'][0]['backgroundColor'].append(dataset['backgroundColor'])
        return self._sub_chart_data

    def get_sub_table_data(self):
        total = 0
        i = 0
        data = []
        sub_data = self.get_sub_chart_data()
        for label in sub_data['labels']:
            data.append((label, add_comma(sub_data['datasets'][0]['data'][i])))
            total += sub_data['datasets'][0]['data'][i]
            i += 1
        return {
            'title': add_comma(total),
            'data': data
        }

    def get_description(self):
        return ''

    def make_dataset(self, **kwargs):
        dataset = {
            'fill': False,
            'borderCapStyle': 'butt',
            'borderDash': [],
            'borderJoinStyle': 'miter',
            # 'lineTension': 0.1,
            'pointBackgroundColor': "#fff",
            'pointBorderWidth': 6,
            'pointHoverRadius': 10,
            'pointHoverBorderWidth': 2,
            'pointRadius': 1,
            'pointHitRadius': 10,
            'spanGaps': False,
            'borderWidth': 2,
        }
        one_color = kwargs.pop('one_color') if 'one_color' in kwargs else ''
        if one_color:
            dataset.update({
                'backgroundColor': one_color,
                'borderColor': one_color,
                'pointHoverBackgroundColor': one_color,
                'pointHoverBorderColor': one_color,
            })
        dataset.update(kwargs)
        return dataset

    def get_context(self):
        context = {
            'id': self.get_id(),
            'type': self.type,
            'chart_class': self.chart_class,
            'table_class': self.table_class,
            'sub_chart_class': self.sub_chart_class,
            'sub_table_class': self.sub_table_class,
            'description_class': self.description_class,
            'data': mark_safe(json.dumps(self.data, ensure_ascii=False)),
            # 'data': self.data,
            'sub_chart_data': self.get_sub_chart_data(),
            'sub_table_data': self.get_sub_table_data(),
            'description': mark_safe(self.get_description()),
            'unit_prefix': self.unit_prefix,
            'unit_suffix': self.unit_suffix,
        }
        if self.options is not None:
            context.update({'options': self.options})
        return context

    def render(self):
        template = loader.get_template(self.template_name)
        return template.render(self.get_context())


"""
액션
"""


def export_as_json(modeladmin, request, queryset):
    """json 출력 어드민 액션"""
    response = HttpResponse(content_type="application/json")
    response['X-SendFile-Encoding'] = 'url'
    response['Content-Disposition'] = 'attachment; filename="%s.json"' % str(modeladmin.model._meta).replace('.', '-')
    serializers.serialize("json", queryset, stream=response)
    return response

export_as_json.short_description = 'JSON으로 출력하기'


"""
로그 엔트리
"""


action_names = {
    ADDITION: '추가',
    DELETION: '삭제',
    CHANGE: '수정',
    4: '조회',
    5: '다운로드',
}


class ActionListFilter(admin.SimpleListFilter):
    """
    액션(추가/삭제/수정) 필터
    """
    title = '액션'
    parameter_name = 'action_flag'

    def lookups(self, request, model_admin):
        return action_names.items()

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(action_flag=self.value())
        return queryset


class UserListFilter(admin.SimpleListFilter):
    """
    액션 실행 유져 필터
    """
    title = '회원'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        staff = get_user_model().objects.filter(is_staff=True)
        return (
            (s.id, force_text(s))
            for s in staff
        )

    def queryset(self, request, queryset):
        if self.value():
            condition = {self.parameter_name + '_id': self.value(), self.parameter_name + '__is_staff': True}
            queryset = queryset.filter(**condition)
        return queryset


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = 'action_time'
    readonly_fields = ([f.name for f in LogEntry._meta.fields] + ['object_link', 'user_link'])
    fieldsets = (
        ('로그 정보', {
            'fields': (
                'action_time',
                'user_link',
                'action_description',
                'object_link',
                'change_message',
                'content_type',
                'object_id',
                'object_repr',
            )
        }),
    )
    list_filter = [UserListFilter, 'content_type', ActionListFilter]
    search_fields = ['object_repr', 'change_message']
    list_display_links = None
    list_display = ['action_time', 'user_link', 'content_type', 'object_link', 'action_flag',
                    'change_message_with_reason_display']
    actions = []
    list_per_page = 50

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context['show_save'] = False
        context['show_save_and_continue'] = False
        return super(LogEntryAdmin, self).render_change_form(request, context, add=add, change=change,
                                                             form_url=form_url, obj=obj)

    def get_queryset(self, request):
        self.request = request
        return super(LogEntryAdmin, self).get_queryset(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return request.user.is_superuser or request.user.has_perm('admin.change_logentry')

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request) and request.method != 'POST'

    def object_link(self, obj):
        object_link = escape(obj.object_repr)
        content_type = obj.content_type

        if obj.action_flag != DELETION and content_type is not None:
            try:
                url = reverse(
                    'admin:{}_{}_change'.format(content_type.app_label, content_type.model),
                    args=[obj.object_id]
                )
                object_link = '<a href="{}">{}</a>'.format(url, object_link)
            except NoReverseMatch:
                pass
        return mark_safe(object_link)

    object_link.allow_tags = True
    object_link.admin_order_field = 'object_repr'
    object_link.short_description = '오브젝트'

    def user_link(self, obj):
        content_type = ContentType.objects.get_for_model(type(obj.user))
        user_link = escape(force_text(obj.user))
        try:
            url = reverse(
                'admin:{}_{}_change'.format(content_type.app_label, content_type.model),
                args=[obj.user.pk]
            )
            user_link = '<a href="{}">{}</a>'.format(url, user_link)
        except NoReverseMatch:
            pass
        return mark_safe(user_link)

    user_link.allow_tags = True
    user_link.admin_order_field = 'user'
    user_link.short_description = '회원'

    def change_message_with_reason_display(self, obj):
        return get_change_message(obj, True)

    change_message_with_reason_display.short_description = '내용'
    change_message_with_reason_display.admin_order_field = 'change_message'

    def change_message_display(self, obj):
        model = obj.content_type.model_class()
        html = ''
        if obj.change_message:
            try:
                for c in eval(obj.change_message):
                    for k, v in c.items():
                        fields = ''
                        if type(v) is dict and 'fields' in v:
                            fields = ', '.join([model._meta.get_field(f).verbose_name for f in v['fields']])
                        html += fields
            except:
                html += obj.change_message
        return mark_safe(html)

    change_message_display.short_description = '내용'
    change_message_display.admin_order_field = 'action_flag'


def log_with_reason(user, obj, action, changes=None, reason=''):
    user_id = None
    if isinstance(user, int):
        user_id = user
    elif isinstance(user, get_user_model()):
        user_id = user.id
    if not user_id or action not in action_flags:
        raise PermissionDenied
    content_type = ContentType.objects.get_for_model(obj._meta.model)
    if type(changes) is dict:
        message = [{
            action: {
                'fields': list(changes.keys()),
                'values': list(changes.values()),
            }
        }]
    elif type(changes) in (list, tuple):
        message = [{
            action: {
                'fields': list(changes),
            }
        }]
    else:
        message = [{
            action: {
                'fields': [str(changes)],
            }
        }] if changes else ''
    if message and reason:
        message[0][action].update({'reason': reason})
    LogEntry.objects.log_action(
        user_id=user_id,
        content_type_id=content_type.id,
        object_id=obj.id,
        object_repr=str(obj),
        action_flag=action_flags[action],
        change_message=message
    )


action_flags = {
    'changed': CHANGE,
    'added': ADDITION,
    'deleted': DELETION,
    'viewed': 4,
    'downloaded': 5,
}

action_keys = {
    'changed': '변경됨',
    'added': '추가됨',
    'deleted': '삭제됨',
    'viewed': '조회함',
    'downloaded': '다운로드',
}

action_classes = {
    'changed': 'warning',
    'added': 'primary',
    'deleted': 'danger',
    'viewed': 'info',
    'downloaded': 'success',
}

action_messages = {
    CHANGE: '변경되었습니다.',
    ADDITION: '추가되었습니다.',
    DELETION: '삭제되었습니다.',
    4: '조회되었습니다.',
    5: '다운로드 되었습니다.',
}


def get_change_message(obj, with_reason=False):
    model = obj.content_type.model_class()
    html = ''
    try:
        messages = json.loads(obj.change_message)
    except:
        return ''
    action_message = action_messages[obj.action_flag]

    if type(messages) is not list:
        return messages

    for c in messages:
        for k, v in c.items():
            fields = []
            suffix = ''
            if type(v) is dict:
                if 'fields' in v:
                    for field in v['fields']:
                        try:
                            fields.append(str(model._meta.get_field(field).verbose_name))
                        except:
                            fields.append(field)

                if 'values' in v:
                    i = 0
                    for field in fields:
                        val = String(v['values'][i])
                        fields[i] = ' %s "%s"%s %s' % (
                            String(field).josa('이'),
                            val,
                            val.josa('로')[len(val):],
                            action_message
                        )
                        i += 1

                if with_reason and 'reason' in v and v['reason']:
                    suffix = """
                        <div class="card bg-light mt-1">
                            <div class="card-header">사유</div>
                            <div class="card-body">
                                <p class="card-text">%s</p>
                            </div>
                        </div>""" % v['reason'].replace('\n', '<br>')
            prefix = '<span class="badge badge-%s mt-1 mb-1">%s</span> ' % (action_classes[k], action_keys[k])
            html += '<br />'.join([prefix + f for f in fields]) + suffix

    return mark_safe(html)

