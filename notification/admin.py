from django.contrib import admin
from django import forms
from django.contrib import messages
from django.db.models import Q, Count, Sum, Case, When, F, IntegerField

from common.admin import RelatedAdminMixin, NullFilter, AdditionalAdminUrlsMixin
from base.admin import BaseAdmin
from .models import ReceiverGroup, Notification, Tasker


class NotificationAdminForm(forms.ModelForm):
    """
    알림 어드민 폼
    """
    receiver_groups = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=ReceiverGroup.objects.all(),
        label= "수신그룹 조건 :",
        required=False,
        help_text="체크된 모든 조건에 해당하는 회원이 수신그룹이 됩니다. (AND)"
    )

    class Meta:
        model = Notification
        fields = '__all__'

    def clean(self):
        cleaned_data = super(NotificationAdminForm, self).clean()
        if 'send_method' not in cleaned_data:
            raise forms.ValidationError('메세지 타입을 선택해주세요.', 'send_method')

        if cleaned_data['send_method'] == 'sms':
            if cleaned_data['receiver_user']:
                if not str(cleaned_data['receiver_user'].mobile):
                    self.add_error('receiver_user', '해당 회원은 인증된 휴대폰 번호가 없습니다.')
            elif not cleaned_data['receiver_groups']:
                raise forms.ValidationError('수신그룹 또는 수신회원을 선택하세요. 또는, 수신 식별자에 푸쉬 토큰을 직접 입력하세요.', 'receiver_groups')

        elif cleaned_data['send_method'] == 'push':
            if not cleaned_data['subject']:
                self.add_error('subject', '푸쉬 알림에는 제목을 반드시 입력해야 합니다.')
            if cleaned_data['receiver_user']:
                if not str(cleaned_data['receiver_user'].push_tokens):
                    self.add_error('receiver_user', '해당 회원은 푸쉬 토큰 정보가 없습니다.')
            elif not cleaned_data['receiver_groups']:
                raise forms.ValidationError('수신그룹 또는 수신회원을 선택하세요. 또는, 수신 식별자에 푸쉬 토큰을 직접 입력하세요.', 'receiver_groups')

        return cleaned_data


class UserSentMessageFilter(NullFilter):
    """유져 발송 메세지 필터"""
    title = '사용자 직접 발송'
    parameter_name = 'user_sent'
    check_field = 'created_user'


@admin.register(ReceiverGroup)
class ReceiverGroupAdmin(BaseAdmin):
    """
    수신그룹 어드민
    """


class NotificationAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    알림 추가 어드민
    """
    def get_additional_urls(self):
        return {
            'send': '<id>/send/',
        }

    def view_send(self, request, *args, **kwargs):
        obj = self._get_object_or_fail(kwargs)
        obj.send()
        messages.success(request, '발송요청이 완료 되었습니다.')
        return self.redirect_referer(request)


@admin.register(Notification)
class NotificationAdmin(NotificationAdditionalAdmin, RelatedAdminMixin, BaseAdmin):
    """
    알림 어드민
    """
    remove_add_fields = ('receiver_user',)
    remove_change_fields = ('receiver_user',)
    list_display = ('get_receiver_display', 'subject', 'get_content_display', 'get_sender_display', 'get_state_with_datetime')
    autocomplete_fields = ('receiver_user', )
    form = NotificationAdminForm
    search_fields = ('receiver_user__code', 'receiver_user__username', 'receiver_user__mobile',
                     'receiver_identifier', 'created_user__code', 'created_user__username', 'created_user__mobile')
    list_filter = ('send_method', 'tasker', UserSentMessageFilter)
    date_hierarchy = 'requested_datetime'

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_list_display_links(self, request, list_display):
        return list_display[0] if request.user.is_superuser else None

    def get_fields(self, request, obj=None):
        if obj:
            return super(NotificationAdmin, self).get_fields(request, obj)
        else:
            return ('receiver_groups', 'receiver_user', 'send_method', 'subject', 'content')

    def save_model(self, request, obj, form, change):
        if not obj.created_user:
            obj.created_user = request.user
        super(NotificationAdmin, self).save_model(request, obj, form, change)
        # receiver = form.cleaned_data['receiver_groups'] \
        #            or form.cleaned_data['receiver_user'] \
        #            or form.cleaned_data['receiver_identifier']
        # if form.cleaned_data['send_method'] == 'sms':
        #     self.model.objects.sms(receiver, form.cleaned_data['content'], request.user)
        # elif form.cleaned_data['send_method'] == 'push':
        #     self.model.objects.push(receiver, form.cleaned_data['subject'], form.cleaned_data['content'],
        #                             sender=request.user)

    def get_content_display(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
    get_content_display.short_description = '내용'
    get_content_display.admin_order_field = 'content'

    def get_receiver_display(self, obj):
        return str(obj)
    get_receiver_display.short_description = '수신자'
    get_receiver_display.admin_order_field = 'receiver_identifier'

    def get_state_with_datetime(self, obj):
        if obj.send_method == 'push' and obj.result and 'success_count' in obj.result and 'failure_count' in obj.result:
            return '[발송성공] %s건 / [발송실패] %s건' % (obj.result['success_count'], obj.result['failure_count'])
        return obj.state_with_datetime
    get_state_with_datetime.short_description = '상태'


@admin.register(Tasker)
class TaskerAdmin(BaseAdmin):
    """
    마케팅 태스커 어드민
    """
    list_display = ('condition', 'get_send_methods_display', 'auto_issue_coupon',
                    'get_requested_push_count', 'get_requested_email_count', 'get_requested_sms_count',
                    'get_requested_kakao_count',
                    #'get_issued_coupon_count', 'get_used_coupon_count',
                    'get_last_task', 'is_active')
    autocomplete_fields = ('auto_issue_coupon',)
    ordering = ('-is_active', '-id')
    list_per_page = 100

    def get_queryset(self, request):
        qs = super(TaskerAdmin, self).get_queryset(request)
        return qs.annotate(requested_push_count=Count(Case(When(notifications__send_method='push', then=F('notifications__id'))), distinct=True)) \
                 .annotate(requested_email_count=Count(Case(When(notifications__send_method='email', then=F('notifications__id'))), distinct=True)) \
                 .annotate(requested_sms_count=Count(Case(When(notifications__send_method='sms', then=F('notifications__id'))), distinct=True)) \
                 .annotate(requested_kakao_count=Count(Case(When(notifications__send_method='kakao', then=F('notifications__id'))), distinct=True))
                 #.annotate(issued_coupon_count=Count('coupons__id', distinct=True)) \
                 #.annotate(used_coupon_count=Count(Case(When(coupons__used_datetime__isnull=False, then=F('coupons__id'))), distinct=True))

    def get_exclude(self, request, obj=None):
        if request.user.is_superuser:
            return []
        return ['is_lazy']

    def get_send_methods_display(self, obj):
        return obj.send_methods
    get_send_methods_display.short_description = '전송방법'

    def get_requested_push_count(self, obj):
        return obj.requested_push_count
    get_requested_push_count.short_description = '푸시 발송요청'
    get_requested_push_count.admin_order_field = 'requested_push_count'

    def get_requested_email_count(self, obj):
        return obj.requested_email_count
    get_requested_email_count.short_description = '이메일 발송요청'
    get_requested_email_count.admin_order_field = 'requested_email_count'

    def get_requested_sms_count(self, obj):
        return obj.requested_sms_count
    get_requested_sms_count.short_description = 'SMS 발송요청'
    get_requested_sms_count.admin_order_field = 'requested_sms_count'

    def get_requested_kakao_count(self, obj):
        return obj.requested_kakao_count
    get_requested_kakao_count.short_description = '알림톡 발송요청'
    get_requested_kakao_count.admin_order_field = 'requested_kakao_count'

    def get_issued_coupon_count(self, obj):
        return obj.issued_coupon_count
    get_issued_coupon_count.short_description = '발급된 쿠폰'
    get_issued_coupon_count.admin_order_field = 'issued_coupon_count'

    def get_used_coupon_count(self, obj):
        return obj.used_coupon_count
    get_used_coupon_count.short_description = '사용된 쿠폰'
    get_used_coupon_count.admin_order_field = 'used_coupon_count'

    def get_last_task(self, obj):
        return obj.last_notification.created_datetime if obj.last_notification else '-'
    get_last_task.short_description = '마지막 전송 작업'
