from django.core.management.base import BaseCommand
from django.utils import timezone

from common.admin import log_with_reason
from notification.models import Notification, Tasker
from missions.models import Mission, Bid, Interaction
from missions.models import SafetyNumber


class Command(BaseCommand):
    """
    24시간 지난 미션완료요청 자동완료 처리, 시간 초과된 상태값들 재계산 저장 커맨드
    """

    def handle(self, *args, **options):
        six_hours_before = timezone.now() - timezone.timedelta(hours=6)
        no_responses = Interaction.objects.filter(
            interaction_type=9, requested_datetime__lte=six_hours_before, bid__saved_state='in_action',
            accepted_datetime__isnull=True, rejected_datetime__isnull=True, canceled_datetime__isnull=True
        )
        for obj in no_responses:
            obj.accept()
            log_with_reason(obj.receiver, obj, 'changed', '미션 완료요청 응답시간 초과로 자동완료 처리')

        for mission in Mission.objects.filter(saved_state__code='in_action'):
            mission.set_state()

        # 시간초과 취소 미션 푸쉬 발송
        # memo: 1분 스크립트로 이동
        # for mission in Mission.objects.filter(saved_state__code='bidding'):
        #     mission.set_state()
        #     if mission.is_timeout:
        #         if mission.is_web:
        #             if mission.is_bidded:
        #                 # Notification.objects.sms_preset(mission.user, 'mission_timeout_canceled_with_bidding')
        #                 Tasker.objects.task('web_mission_timeout_canceled_with_bidding', user=mission.user)
        #             else:
        #                 # Notification.objects.sms_preset(mission.user, 'mission_timeout_canceled')
        #                 Tasker.objects.task('web_mission_timeout_canceled', user=mission.user)
        #         else:
        #             if mission.is_bidded:
        #                 # Notification.objects.push_preset(mission.user, 'mission_timeout_canceled_with_bidding',
        #                 #                                  kwargs={'obj_id': mission.id})
        #                 Tasker.objects.task('mission_timeout_canceled_with_bidding', user=mission.user,
        #                                     data={'obj_id': mission.id})
        #             else:
        #                 # Notification.objects.push_preset(mission.user, 'mission_timeout_canceled',
        #                 #                                  kwargs={'obj_id': mission.id})
        #                 Tasker.objects.task('mission_timeout_canceled', user=mission.user,
        #                                     data={'obj_id': mission.id})

        # 미션완료 24시간 후에 애니톡 닫음
        before_one_day = timezone.now() - timezone.timedelta(days=1)
        for bid in Bid.objects.filter(saved_state='done', _done_datetime__lte=before_one_day, _anytalk_closed_datetime__isnull=True):
            bid.close_anytalk()
            SafetyNumber.objects.unassign_pair_from_bid(bid)

