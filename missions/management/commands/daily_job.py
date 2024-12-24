from django.core.management.base import BaseCommand
from django.utils import timezone

from common.admin import log_with_reason
from notification.models import Notification, Tasker
from missions.models import Mission, Bid, Interaction, SafetyNumber
from accounts.models import User
from payment.models import Coupon


#todo: jobs.py 라이브 적용 후 삭제할 것.


class Command(BaseCommand):
    """
    24시간 지난 미션완료요청 자동완료 처리, 시간 초과된 상태값들 재계산 저장 커맨드
    """

    def handle(self, *args, **options):
        # 가입 72시간 이내에 미션요청 없음
        recent_users = User.objects.get_joined_before(days=3).get_active_users()
        for u in recent_users.filter(missions__requested_datetime__isnull=True).distinct('id'):
            Tasker.objects.task('joined_remind_72', user=u)

        today = timezone.now().date()

        # 쿠폰 만료 5일 전
        not_used_coupons = Coupon.objects.filter(used_datetime__isnull=True)
        for c in not_used_coupons.filter(expire_date=today + timezone.timedelta(days=5)):
            kwargs = {'coupon_name': c.name, 'coupon_expire': c.expire_date}
            Tasker.objects.task('coupon_expire_remind_5d', user=c.user, kwargs=kwargs)

        # 쿠폰 만료 10일 전
        not_used_coupons = Coupon.objects.filter(used_datetime__isnull=True)
        for c in not_used_coupons.filter(expire_date=today + timezone.timedelta(days=10)):
            kwargs = {'coupon_name': c.name, 'coupon_expire': c.expire_date}
            Tasker.objects.task('coupon_expire_remind_10d', user=c.user, kwargs=kwargs)

        # 한달 이상 만료되지 않은 안심번호 만료처리
        before_30_days = timezone.now() - timezone.timedelta(days=30)
        for activated in SafetyNumber.objects.filter(assigned_datetime__lt=before_30_days, unassigned_datetime__isnull=True):
            activated.unassign()
