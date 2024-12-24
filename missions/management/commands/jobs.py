from django.core.management.base import BaseCommand

from django.utils import timezone

from common.utils import add_comma
from accounts.models import User
from payment.models import Point
from missions.models import Tasker
from payment.models import Coupon
from missions.models import SafetyNumber


class Command(BaseCommand):
    """
    일괄처리 커맨트
    """
    help = '일괄처리 스크립트'
    commands = {
        'monthly': (
            'send_point_balance',
        ),
        'daily': (
            'joined_remind_72',
            'coupon_expire_in_5_days',
            'coupon_expire_in_10_days',
            'unassign_safety_number_passed_a_month'
        )
    }

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            'run_cycle', type=str, nargs='?',
            help='run cycle options: %s' % ', '.join(self.commands),
        )
        parser.add_argument(
            '--list', '-l', action="store_true", dest="list_jobs",
            help="List all jobs with their description")

    def list_jobs(self):
        for run_cycle in self.commands:
            print('\nrun_cycle [%s]:' % run_cycle)
            for job_name, job in self.get_jobs(run_cycle):
                print('\t%s' % job_name.rjust(40), ':', job.__doc__)

    def get_jobs(self, run_cycle):
        jobs = list()
        for job_name in self.commands[run_cycle]:
            obj = getattr(self, job_name, None)
            if obj and callable(obj):
                jobs.append((job_name, obj))
        return jobs

    def handle(self, *args, **options):
        if options.get('list_jobs'):
            self.list_jobs()
            return 0

        run_cycle = options.get('run_cycle')
        if not run_cycle:
            return 1
        self.today = timezone.now().date()
        for job_name, job in self.get_jobs(run_cycle):
            # print('%s...' % job.__doc__, end='')
            job()

    def send_point_balance(self):
        """한달 이상 접속기록 없는 사용자 미사용 포인트 잔액 안내"""
        one_month_ago = timezone.now() - timezone.timedelta(days=30)
        latest_points = Point.objects.filter(
            user__is_active=True, user___is_service_blocked=False, user__withdrew_datetime__isnull=True,
            user__helper__isnull=True, user__last_login__lt=one_month_ago
        ).order_by('user_id', '-id').distinct('user_id')
        for p in latest_points:
            if p.balance >= 1000:
                Tasker.objects.task('regular_point_balance', user=p.user, kwargs={'balance': add_comma(p.balance)})

    def joined_remind_72(self):
        """가입 72시간 이내에 미션요청 없음 알림"""
        recent_users = User.objects.get_joined_before(days=3).get_active_users()
        for u in recent_users.filter(missions__requested_datetime__isnull=True).distinct('id'):
            Tasker.objects.task('joined_remind_72', user=u)

    def coupon_expire_in_5_days(self):
        """쿠폰 만료 5일 전 알림"""
        not_used_coupons = Coupon.objects.filter(used_datetime__isnull=True)
        for c in not_used_coupons.filter(expire_date=self.today + timezone.timedelta(days=5)):
            kwargs = {'coupon_name': c.name, 'coupon_expire': c.expire_date}
            Tasker.objects.task('coupon_expire_remind_5d', user=c.user, kwargs=kwargs)

    def coupon_expire_in_10_days(self):
        """쿠폰 만료 10일 전 알림"""
        not_used_coupons = Coupon.objects.filter(used_datetime__isnull=True)
        for c in not_used_coupons.filter(expire_date=self.today + timezone.timedelta(days=10)):
            kwargs = {'coupon_name': c.name, 'coupon_expire': c.expire_date}
            Tasker.objects.task('coupon_expire_remind_10d', user=c.user, kwargs=kwargs)

    def unassign_safety_number_passed_a_month(self):
        """한달 이상 만료되지 않은 안심번호 만료처리"""
        before_30_days = timezone.now() - timezone.timedelta(days=30)
        for activated in SafetyNumber.objects.filter(assigned_datetime__lt=before_30_days, unassigned_datetime__isnull=True):
            activated.unassign()
