from django.core.management.base import BaseCommand

from missions.models import MultiMission, MultiAreaMission, Mission, Bid


class Command(BaseCommand):
    """
    미션 관련 데이터 초기화 커맨드
    """

    def handle(self, *args, **options):
        # 입찰
        for bid in Bid.objects.filter(saved_state_id='not_applied'):
            bid.set_state()

        # 미션
        for mission in Mission.objects.filter(saved_state_id='draft'):
            mission.set_state()

        # 미션
        for area_mission in MultiAreaMission.objects.filter(saved_state_id='draft'):
            area_mission.set_state()

        # 미션
        for multi_mission in MultiMission.objects.filter(saved_state_id='draft'):
            multi_mission.set_state()
