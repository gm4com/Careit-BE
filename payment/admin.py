from django.contrib import admin, messages
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.formats import localize
from django.urls import path, reverse
from django import forms
from django.db.models import Q, Count, Sum, Case, When, F
from django.conf import settings

from harupy.text import String

from common.admin import RelatedAdminMixin, ChangeFormSplitMixin, AdditionalAdminUrlsMixin, log_with_reason
from common.views import ModelExportBaseView
from common.utils import RSACrypt, add_comma
from base.admin import BaseAdmin
from accounts.admin import UserCodeSearchMixin
from .models import (
    Billing, Payment, Cash, Point, Withdraw, PointVoucherTemplate, PointVoucher, Reward, CouponTemplate, Coupon
)
from .filters import (
    PointDetailTypeFilter, CashDetailTypeFilter, WithdrawStateFilter, PointNullFilter, ActiveRewardFilter
)


@admin.register(Point)
class PointAdmin(RelatedAdminMixin, UserCodeSearchMixin, BaseAdmin):
    """
    포인트 내역 어드민
    """
    list_display = ('user', 'get_detail_display', 'get_amount_display', 'get_balance_display', 'created_datetime')
    list_display_links = None
    fields = ('user', 'amount', 'memo', 'added_type')
    search_fields = ('user__code', 'user__username', 'user__mobile', 'amount', 'voucher__template__name',
                     'payment__bid__mission__code', 'memo')
    autocomplete_fields = ('user',)
    remove_add_fields = ('user',)
    remove_change_fields = ('user',)
    list_filter = (PointDetailTypeFilter, 'voucher__template', 'added_type')
    change_form_template = 'admin/point/change_form.html'

    def has_change_permission(self, request, obj=None):
        return bool(obj is None)

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        rtn = super(PointAdmin, self).formfield_for_choice_field(db_field, request, **kwargs)
        del rtn.choices[1]
        return rtn

    def save_model(self, request, obj, form, change):
        if not form.cleaned_data['added_type']:
            raise forms.ValidationError('추가유형을 입력해주세요.', code='added_type')
        return super(PointAdmin, self).save_model(request, obj, form, change)

    def get_amount_display(self, obj):
        return add_comma(obj.amount)
    get_amount_display.short_description = '금액'
    get_amount_display.admin_order_field = 'amount'

    def get_balance_display(self, obj):
        return add_comma(obj.balance)
    get_balance_display.short_description = '잔액'
    get_balance_display.admin_order_field = 'balance'

    def get_detail_display(self, obj):
        return obj.detail_memo or '- 내역 없음 -'
    get_detail_display.short_description = '내역'


@admin.register(Cash)
class CashAdmin(RelatedAdminMixin, UserCodeSearchMixin, BaseAdmin):
    """
    캐쉬 내역 어드민
    """
    list_display = ('id', 'helper', 'get_detail_display', 'get_amount_display', 'get_balance_display', 'created_datetime')
    list_display_links = None
    fields = ('helper', 'amount', 'memo')
    search_fields = ('helper__user__code', 'helper__user__username', 'helper__user__mobile', 'amount',
                     'bid__mission__code', 'memo')
    autocomplete_fields = ('helper',)
    remove_add_fields = ('helper',)
    remove_change_fields = ('helper',)
    list_filter = (CashDetailTypeFilter, )
    change_form_template = 'admin/cash/change_form.html'

    def has_change_permission(self, request, obj=None):
        return bool(obj is None)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_amount_display(self, obj):
        return add_comma(obj.amount)
    get_amount_display.short_description = '금액'
    get_amount_display.admin_order_field = 'amount'

    def get_balance_display(self, obj):
        return add_comma(obj.balance)
    get_balance_display.short_description = '잔액'
    get_balance_display.admin_order_field = 'balance'

    def get_detail_display(self, obj):
        return obj.detail_memo or '- 내역 없음 -'
    get_detail_display.short_description = '내역'


class WithdrawExcelFormDownloadView(ModelExportBaseView):
    """
    인출내역 엑셀 양식 다운로드 뷰
    """
    model = Withdraw
    columns = [
        ('amount', '금액'),
        ('helper_code', '헬퍼코드'),
        ('helper__name', '이름'),
        ('bank_account_display', '은행계좌번호'),
    ]

    def dispatch(self, request, *args, **kwargs):
        self.xls_type = kwargs.pop('xls_type')
        if self.xls_type == 'all':
            self.title = '인출요청내역'
            self.query_field = 'requested_datetime'
            self.columns.insert(0, ('requested_datetime', '인출요청일시'))
            self.columns.append(('state_text', '처리상태'))
            self.columns.append(('handled_datetime', '처리일시'))
        elif self.xls_type == 'requested':
            self.title = '인출요청미처리내역'
            self.query_field = 'requested_datetime'
            self.columns.insert(0, ('requested_datetime', '인출요청일시'))
        elif self.xls_type == 'done_with_id':
            self.title = '인출완료내역'
            self.query_field = 'done_datetime'
            self.columns.insert(0, ('done_datetime', '인출처리일시'))
            self.rsa = kwargs.pop('rsa') if 'rsa' in kwargs else None
            if self.rsa:
                self.columns.append(('tin_number', '주민번호'))
        else:
            self.title = ''
        self.year = kwargs.pop('year')
        self.month = kwargs.pop('month')
        return super(WithdrawExcelFormDownloadView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_queryset(self):
        qs = self.model.objects.filter(**{
            '%s__year' % self.query_field: self.year,
            '%s__month' % self.query_field: self.month
        })
        if self.xls_type == 'requested':
            qs = qs.filter(done_datetime__isnull=True, failed_datetime__isnull=True)
        if qs.exists():
            log_with_reason(self.request.user, qs.first(), 'changed',
                            '%s년 %s월 캐쉬 %s 조회 (%s건)' % (self.year, self.month, self.title, qs.count()))
        return qs

    def get_filename(self):
        return '%s.%s.%s.%s' % (self.title, self.year, self.month, self.file_type)

    def get_field_bank_account_display(self, obj):
        return str(obj.bank_account or obj.helper.bank_account or '-')

    def get_field_helper_code(self, obj):
        return 'U%s' % obj.helper.user.code

    def get_field_tin_number(self, obj):
        try:
            return self.rsa.decrypt(obj.helper.tin.number.tobytes())
        except:
            return ''


class WithdrawAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    인출 추가 어드민
    """

    def get_additional_urls(self):
        return {
            'set_done': '<id>/done',
            'set_failed': '<id>/failed',
            'download_excel': 'download'
        }

    def view_set_done(self, request, *args, **kwargs):
        obj = self._get_object_or_fail(kwargs)
        if obj.helper.cash_balance >= obj.amount:
            obj.finish()
            log_with_reason(request.user, obj, 'changed', 'done_datetime')
            messages.success(request, '%s원 인출요청을 완료처리 했습니다.' % obj.amount)
        else:
            messages.error(request, '캐쉬 잔액이 부족하여 인출요청을 완료로 처리할 수 없습니다.')
        return self.redirect_referer(request)

    def view_set_failed(self, request, *args, **kwargs):
        obj = self._get_object_or_fail(kwargs)
        obj.fail()
        log_with_reason(request.user, obj, 'changed', 'failed_datetime')
        messages.success(request, '%s원 인출요청을 실패로 처리했습니다.' % obj.amount)
        return self.redirect_referer(request)

    def view_download_excel(self, request, *args, **kwargs):
        if request.method == 'POST':
            if request.POST['xls_type'] == 'done_with_id':
                if 'key' in request.FILES:
                    rsa = RSACrypt()
                    try:
                        rsa.set_key(request.FILES['key'].read())
                    except:
                        messages.error(request, '암호키 파일이 아닙니다.')
                        return self.redirect_referer(request)
                    else:
                        kwargs.update({'rsa': rsa})
                else:
                    messages.error(request, '암호키 파일을 선택해서 업로드해주세요.')
                    return self.redirect_referer(request)
            if 'year' not in request.POST or 'month' not in request.POST:
                messages.error(request, '년과 월을 입력해주세요.')
                return self.redirect_referer(request)
            kwargs.update({
                'year': request.POST['year'],
                'month': request.POST['month'],
                'xls_type': request.POST['xls_type'],
            })

            return WithdrawExcelFormDownloadView.as_view()(request, *args, **kwargs)


@admin.register(Withdraw)
class WithdrawAdmin(WithdrawAdditionalAdmin, UserCodeSearchMixin, BaseAdmin):
    """
    인출요청 어드민
    """
    list_display = ('helper', 'get_amount_display', 'requested_datetime', 'get_handle_buttons_display',
                    'get_bank_account_display', 'get_helper_name_display', 'get_cash_display')
    list_display_links = None
    search_fields = ('helper__user__code', 'helper__user__username', 'helper__user__mobile', 'helper__name', 'amount')
    list_filter = (WithdrawStateFilter, )
    date_hierarchy = 'done_datetime'
    change_list_template = 'admin/withdraw/change_list.html'

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_amount_display(self, obj):
        return add_comma(obj.amount)
    get_amount_display.short_description = '금액'
    get_amount_display.admin_order_field = 'amount'

    def get_cash_display(self, obj):
        return mark_safe('<a class="btn btn-sm btn-info" href="%s?helper=%s">캐쉬 내역보기</a>' % (
            reverse('admin:payment_cash_changelist'),
            obj.helper_id
        ))
    get_cash_display.short_description = '캐쉬 내역'

    def get_bank_account_display(self, obj):
        return obj.bank_account or obj.helper.bank_account
    get_bank_account_display.short_description = '은행 계좌'

    def get_helper_name_display(self, obj):
        return obj.helper.name
    get_helper_name_display.short_description = '헬퍼 이름'

    def get_handle_buttons_display(self, obj):
        buttons = '<a class="btn btn-sm btn-primary" href="%s">완료 처리</a> ' % reverse(
            'admin:payment_withdraw_set_done', kwargs={'id': obj.id}
        )
        buttons += '<a class="btn btn-sm btn-warning" href="%s">실패 처리</a>' % reverse(
            'admin:payment_withdraw_set_failed', kwargs={'id': obj.id}
        )
        if obj.state == 'requested':
            return mark_safe(buttons)
        return obj.get_state_display()
    get_handle_buttons_display.short_description = '상태'


class PointVoucherInline(RelatedAdminMixin, admin.TabularInline):
    """
    발급된 포인트 상품권 인라인
    """
    model = PointVoucher
    autocomplete_fields = ('user', )
    remove_add_fields = ('user',)
    remove_change_fields = ('user',)
    extra = 0

    def get_fields(self, request, obj=None):
        return ('user', 'code', 'expire_date', 'used_datetime')

    def get_readonly_fields(self, request, obj=None):
        if obj and (obj.is_repetitive_use or not obj.is_active):
            return ('user', 'code', 'expire_date', 'used_datetime')
        return ('code', 'expire_date', 'used_datetime')

    def has_add_permission(self, request, obj=None):
        return bool(obj and obj.is_active and not obj.is_repetitive_use)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PointVoucherTemplate)
class PointVoucherTemplateAdmin(UserCodeSearchMixin, ChangeFormSplitMixin, BaseAdmin):
    """
    포인트 상품권 템플릿 어드민
    """
    list_display = ('name', 'description', 'price', 'code', 'is_repetitive_use', 'active_days', 'is_active')
    inlines = (PointVoucherInline,)
    search_fields = ('name', 'description', 'price', 'code', 'vouchers__user__code', 'vouchers__user__username')
    change_form_split = [4, 8]
    list_filter = ('is_repetitive_use', 'is_active')

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.vouchers.count():
            return ['name', 'description', 'price', 'code', 'is_repetitive_use', 'active_days']
        return super(PointVoucherTemplateAdmin, self).get_readonly_fields(request, obj)

    def get_fields(self, request, obj=None):
        if obj and obj.vouchers.count():
            return ['name', 'description', 'price', 'code', 'is_repetitive_use', 'active_days', 'is_active']
        return super(PointVoucherTemplateAdmin, self).get_fields(request, obj)


class CouponInline(RelatedAdminMixin, admin.TabularInline):
    """
    발급된 쿠폰 인라인
    """
    model = Coupon
    autocomplete_fields = ('user', )
    remove_add_fields = ('user',)
    remove_change_fields = ('user',)
    extra = 0

    def get_fields(self, request, obj=None):
        return ('user', 'code', 'get_issued_by_display', 'expire_date', 'used_datetime')

    def get_readonly_fields(self, request, obj=None):
        if obj and not obj.is_active:
            return ('user', 'code', 'get_issued_by_display', 'expire_date', 'used_datetime')
        return ('code', 'get_issued_by_display', 'expire_date', 'used_datetime')

    def has_add_permission(self, request, obj=None):
        return bool(obj and obj.is_active)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_issued_by_display(self, obj):
        if not obj.expire_date:
            return '-'
        if not obj.issued_user:
            return '시스템 자동발급' + (' (%s)' % obj.tasker.get_condition_display() if obj.tasker else '')
        if obj.user == obj.issued_user:
            return '직접 등록'
        return '%s 발급' % String(obj.issued_user).josa('가')
    get_issued_by_display.short_description = '발급 경위'


@admin.register(CouponTemplate)
class CouponTemplateAdmin(UserCodeSearchMixin, ChangeFormSplitMixin, BaseAdmin):
    """
    쿠폰 템플릿 어드민
    """
    list_display = ('name', 'description', 'get_price_display', 'user_register_code', 'active_days',
                    'get_issued_count_display', 'get_used_count_display', 'is_active')
    inlines = (CouponInline,)
    search_fields = ('name', 'description', 'price', 'user_register_code', 'coupons__user__code', 'coupons__user__username')
    change_form_split = [4, 8]
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    fields = ('name', 'description', 'price', 'amount_condition', 'user_register_code', 'active_days', 'is_active')

    def get_queryset(self, request):
        qs = super(CouponTemplateAdmin, self).get_queryset(request)
        return qs.annotate(issued_count=Count('coupons__id')) \
                 .annotate(used_count=Count(Case(When(coupons__used_datetime__isnull=False, then=F('coupons__id'))), distinct=True))

    def save_formset(self, request, form, formset, change):
        for f in formset:
            if not f.instance.pk:
                f.instance.issued_user = request.user
        return super(CouponTemplateAdmin, self).save_formset(request, form, formset, change)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.issued_count:
            return ['name', 'description', 'price', 'amount_condition', 'user_register_code', 'active_days']
        return super(CouponTemplateAdmin, self).get_readonly_fields(request, obj)

    def get_price_display(self, obj):
        return '%s (%s)' % (obj.discount, obj.condition)
    get_price_display.short_description = '쿠폰가액'
    get_price_display.admin_field_order = 'price'

    def get_issued_count_display(self, obj):
        return obj.issued_count
    get_issued_count_display.short_description = '발급건수'
    get_issued_count_display.admin_field_order = 'issued_count'

    def get_used_count_display(self, obj):
        return obj.used_count
    get_used_count_display.short_description = '사용건수'
    get_used_count_display.admin_field_order = 'used_count'


@admin.register(Billing)
class BillingAdmin(UserCodeSearchMixin, BaseAdmin):
    """
    빌링 어드민
    """
    list_display = ('user', 'card_company_no', 'card_name', 'card_no', 'customer_name', 'customer_tel_no',
                    'created_datetime', 'canceled_datetime')
    search_fields = ('user__code', 'user__username', 'user__mobile', 'card_name', 'customer_name', 'customer_tel_no')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PaymentAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    결제 추가 어드민
    """

    def get_additional_urls(self):
        return {
            'cancel': '<id>/cancel/',
        }

    def view_cancel(self, request, *args, **kwargs):
        obj = self._get_object_or_fail(kwargs)
        if not obj.can_cancel:
            messages.error(request, '취소할 수 없는 결제입니다.')
            return self.redirect_referer(request)

        if obj.cancel():
            messages.success(request, '결제 취소처리가 완료되었습니다.')
            if obj.bid.unfinish():
                messages.success(request, '관리자 직권으로 미션이 취소되었습니다.')
                # todo: 이 부분이 미션으로 들어가야 할 것 같음
        else:
            messages.error(request, '취소시도 중에 오류가 발생했습니다. 이미 취소되었거나 일시적인 오류일 수 있습니다.')
        return self.redirect_referer(request)


@admin.register(Payment)
class PaymentAdmin(PaymentAdditionalAdmin, UserCodeSearchMixin, BaseAdmin):
    """
    결제 어드민
    """
    list_display = ('bid', 'get_total_display', 'get_summary_display', 'get_canceled_object_display',
                    'authenticated_no', 'created_datetime', 'is_succeeded',)
    list_display_links = None
    list_filter = ('pay_method', PointNullFilter, 'is_succeeded')
    search_fields = ('bid__mission__code', 'bid__mission__user__username', 'bid__mission__user__code',
                     'bid__mission__user__mobile',  'amount', 'payment_id', 'authenticated_no',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_canceled_object_display(self, obj):
        if 'canceled' in obj.result:
            # return mark_safe('<a href="%s"><i class="fa fa-lg fa-link"></i></a>' % reverse('admin:payment_payment_change', kwargs={'object_id': obj.result['canceled']}))
            return '취소됨'
        return ''
    get_canceled_object_display.short_description = '취소'

    def get_total_display(self, obj):
        return add_comma(obj.bid.amount)
    get_total_display.short_description = '수행비'

    def get_summary_display(self, obj):
        return obj.summary
    get_summary_display.short_description = '결제내용'


class RewardAdminForm(forms.ModelForm):
    """
    리워드 어드민 폼
    """
    class Meta:
        model = Reward
        fields = '__all__'

    def clean(self):
        cleaned_data = super(RewardAdminForm, self).clean()
        if bool(cleaned_data['start_date']) is not bool(cleaned_data['end_date']):
            self.add_error('start_date', '시작일과 종료일은 하나만 지정할 수 없습니다.')
            self.add_error('end_date', '시작일과 종료일은 하나만 지정할 수 없습니다.')
        return cleaned_data


@admin.register(Reward)
class RewardAdmin(BaseAdmin):
    """
    리워드 어드민
    """
    list_display = ('reward_type', 'get_amount_or_rate_display', 'start_date', 'end_date', 'get_is_active_display')
    form = RewardAdminForm
    list_filter = ('reward_type', ActiveRewardFilter)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        if obj:
            return ('reward_type', 'get_amount_or_rate_display', 'start_date', 'end_date',
                    'get_is_active_display', 'created_datetime')
        return super(RewardAdmin, self).get_fields(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('reward_type', 'get_amount_or_rate_display', 'get_is_active_display', 'created_datetime')
        return super(RewardAdmin, self).get_readonly_fields(request, obj)

    def get_queryset(self, request):
        self.actives = {}
        for reward_type, verbose_name in self.model.REWARD_TYPES:
            self.actives.update({reward_type: self.model.objects.get_active(reward_type)})
        return super(RewardAdmin, self).get_queryset(request)

    def get_is_active_display(self, obj):
        return '현재 적용중' if self.actives[obj.reward_type] == obj else '-'
    get_is_active_display.short_description = '적용'
