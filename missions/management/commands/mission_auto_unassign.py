from django.core.management.base import BaseCommand
from django.utils import timezone

from common.admin import log_with_reason
from notification.models import Notification, Tasker
from missions.models import Mission, Bid, SafetyNumber


class Command(BaseCommand):
    """
    1분단위 자동처리 확인 커맨드
    """

    def handle(self, *args, **options):
        # 10분 지난 헬퍼지정미션 자동 일반미션 전환 처리
        ten_minutes_before = timezone.now() - timezone.timedelta(minutes=10)
        no_responses = Bid.objects.filter(
            is_assigned=True,
            amount=0,
            mission__requested_datetime__lte=ten_minutes_before
        )
        for obj in no_responses:
            obj.unassign()
            log_with_reason(obj.helper.user, obj, 'changed', '헬퍼지정미션 응답시간 초과로 일반미션 전환 처리')

        # lock 후 10분 지나면 unlock
        for obj in Bid.objects.filter(_locked_datetime__lte=ten_minutes_before):
            obj.unlock()

        # 타임아웃된 미션 처리
        for mission in Mission.objects.filter(saved_state__code='bidding'):
            mission.set_state()
            if mission.is_timeout:
                self.handle_timeout_missions(mission)

        # 입찰중 상태에 있는 미션들 상태 다시 계산
        bidded_mission_ids = set()
        for obj in Bid.objects.filter(saved_state__code__in=['applied', 'waiting_assignee']):
            obj.set_state()

            # 입찰중인(낙찰되지 않은) 미션 중 입찰이 있는 미션 목록에 추가
            if obj.saved_state.code == 'applied':
                bidded_mission_ids.add(obj.mission_id)
            else:
                obj._mission.set_state()

        # 안심번호 미할당인 수행중 미션에 번호 할당
        for bid in Bid.objects.filter(saved_state='in_action', customer_safety_number__isnull=True,
                                      won_datetime__gte=timezone.now() - timezone.timedelta(hours=1)):
            SafetyNumber.objects.assign_pair_from_bid(bid)

        # 낙찰자 선택 독려 푸쉬
        missions = Mission.objects.filter(id__in=bidded_mission_ids).exclude(mission_type__push_before_finish=0)
        for mission in missions:
            left = mission.bid_limit_datetime - timezone.now()
            if (left - timezone.timedelta(minutes=mission.mission_type.push_before_finish)).seconds <= 60 \
                    and mission.bidded_count > 0:
                if mission.is_web:
                    # Notification.objects.sms_preset(mission.user, 'select_helper_before_timeout',
                    #                                 args=[mission.bidded_count, mission.shortened_url])
                    Tasker.objects.task('web_select_helper_before_timeout', user=mission.user, kwargs={
                        'count': mission.bidded_count,
                        'url': mission.shortened_url
                    })
                else:
                    # Notification.objects.push_preset(mission.user, 'select_helper_before_timeout',
                    #                                  kwargs={'obj_id': mission.id})
                    Tasker.objects.task('select_helper_before_timeout', user=mission.user,
                                        kwargs={'count': mission.bidded_count}, data={'obj_id': mission.id})

        # lazy 푸시 알림
        notifications = Notification.objects.filter(
            send_method__in=['push', 'kakao'],
            requested_datetime__isnull=True,
            created_datetime__gt=timezone.now() - timezone.timedelta(minutes=5),
            created_datetime__lte=timezone.now() - timezone.timedelta(minutes=1)
        )
        for n in notifications:
            try:
                n.send()
            except ValueError:
                print('Notification', n.id, n, ': no target user')

    def handle_timeout_missions(self, mission):
        if mission.is_web:
            if mission.is_bidded:
                # Notification.objects.sms_preset(mission.user, 'mission_timeout_canceled_with_bidding')
                Tasker.objects.task('web_mission_timeout_canceled_with_bidding', user=mission.user)
            else:
                # Notification.objects.sms_preset(mission.user, 'mission_timeout_canceled')
                Tasker.objects.task('web_mission_timeout_canceled', user=mission.user)
        else:
            if mission.is_bidded:
                # Notification.objects.push_preset(mission.user, 'mission_timeout_canceled_with_bidding',
                #                                  kwargs={'obj_id': mission.id})
                Tasker.objects.task('mission_timeout_canceled_with_bidding', user=mission.user,
                                    data={'obj_id': mission.id})
            else:
                # Notification.objects.push_preset(mission.user, 'mission_timeout_canceled',
                #                                  kwargs={'obj_id': mission.id})
                Tasker.objects.task('mission_timeout_canceled', user=mission.user,
                                    data={'obj_id': mission.id})

