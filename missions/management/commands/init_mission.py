from django.core.management.base import BaseCommand

from missions.models import MissionType
from payment.models import Reward


class Command(BaseCommand):
    """
    미션 관련 데이터 초기화 커맨드
    """

    def handle(self, *args, **options):

        # 미션타입
        MissionType.objects.create(id=1, title='일반미션', description='일반미션', bidding_limit=60)
        MissionType.objects.create(id=2, title='본사미션', description='본사미션', code='AN')
        MissionType.objects.create(id=3, title='기업미션', description='기업미션 (이케아)', code='IK')
        MissionType.objects.create(id=4, title='기업미션', description='기업미션 (이고진)', code='EG')

        # 리워드
        Reward.objects.create(id=1, reward_type='helper_created_review', amount_or_rate=100)
        Reward.objects.create(id=1, reward_type='customer_created_review', amount_or_rate=100)
        Reward.objects.create(id=1, reward_type='customer_finished_mission', amount_or_rate=1)
        