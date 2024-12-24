from copy import deepcopy

from django.core.management.base import BaseCommand

from missions.models import MultiMission, MultiAreaMission, Mission, Bid


class Command(BaseCommand):
    """
    미션 관련 데이터 초기화 커맨드
    """

    def handle(self, *args, **options):
        # 입찰
        for bid in Bid.objects.filter(saved_state_id='user_canceled', won_datetime__isnull=False):
            state = deepcopy(bid.state)
            bid.set_state()
            if state != bid.state:
                print(bid.id, 'has changed state.')


