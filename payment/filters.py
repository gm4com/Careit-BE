from django.contrib import admin

from common.admin import NullFilter


class PointDetailTypeFilter(admin.SimpleListFilter):
    """포인트 내역 종류 필터"""
    parameter_name = 'detail_type'
    title = '내역 종류'

    def lookups(self, request, model_admin):
        return (
            ('voucher', '상품권 사용'),
            ('payment', '결제 차감'),
            ('k_voucher_all', '비대면바우쳐 고객의 전체내역'),
            ('k_voucher_use', '비대면바우쳐 고객의 결제 차감'),
            ('none', '내역 없음'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == 'voucher':
            return queryset.filter(voucher__isnull=False)
        if val == 'payment':
            return queryset.filter(payment__isnull=False)
        if val == 'k_voucher_all':
            user_ids = queryset.filter(added_type__gt=10).values_list('user', flat=True)
            return queryset.filter(user__in=user_ids)
        if val == 'k_voucher_use':
            user_ids = queryset.filter(added_type__gt=10).values_list('user', flat=True)
            return queryset.filter(payment__isnull=False, user__in=user_ids)
        if val == 'none':
            return queryset.filter(_detail='', memo='', bid__isnull=True, payment__isnull=True, voucher__isnull=True,
                                   review__isnull=True)


class CashDetailTypeFilter(admin.SimpleListFilter):
    """캐쉬 내역 종류 필터"""
    parameter_name = 'detail_type'
    title = '내역 종류'

    def lookups(self, request, model_admin):
        return (
            ('bid', '미션 수행'),
            ('review', '리뷰 작성'),
            ('withdraw', '출금'),
            ('none', '내역 없음'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == 'bid':
            return queryset.filter(bid__isnull=False)
        if val == 'withdraw':
            return queryset.filter(withdraw__isnull=False)
        if val == 'review':
            return queryset.filter(review__isnull=False)
        if val == 'none':
            return queryset.filter(_detail='', memo='', bid__isnull=True, withdraw__isnull=True, review__isnull=True)



class WithdrawStateFilter(admin.SimpleListFilter):
    """인출신청 내역 상태 필터"""
    parameter_name = 'state_type'
    title = '상태'

    def lookups(self, request, model_admin):
        return (
            ('requested', '요청됨'),
            ('done', '인출 완료'),
            ('failed', '인출 실패'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == 'requested':
            return queryset.filter(done_datetime__isnull=True, failed_datetime__isnull=True)
        if val == 'done':
            return queryset.filter(done_datetime__isnull=False, failed_datetime__isnull=True)
        if val == 'failed':
            return queryset.filter(done_datetime__isnull=False, failed_datetime__isnull=False)


class PointNullFilter(NullFilter):
    title = '포인트 사용'
    parameter_name = 'point'


class ActiveRewardFilter(admin.SimpleListFilter):
    """현재 적용중인 리워드 필터"""
    parameter_name = 'active_reward'
    title = '적용'

    def lookups(self, request, model_admin):
        self.active_ids = [obj.id for obj in model_admin.actives.values() if obj]
        return (
            (1, '현재 적용중'),
            (0, '적용되지 않음'),
        )

    def queryset(self, request, queryset):
        if self.value() is '1':
            return queryset.filter(id__in=self.active_ids)
        elif self.value() is '0':
            return queryset.exclude(id__in=self.active_ids)
        return queryset
