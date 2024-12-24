from django.core.management.base import BaseCommand

from missions.models import Bid
from notification.utils import FirebaseFirestoreChatHandler


class Command(BaseCommand):
    """
    종료 후 24시간 지난 미션 애니톡 일괄 닫기
    """

    def handle(self, *args, **options):
        anytlak = FirebaseFirestoreChatHandler()
        for bid in Bid.objects.done(days=1):
            if bid.close_anytalk():
                print(bid.id, 'closed')
            else:
                print(bid.id, 'not found')

        for bid in Bid.objects.filter(saved_state__code__contains='cancel').exclude(saved_state__code='timeout_canceled').exclude(saved_state__code='user_canceled'):
            if bid.close_anytalk():
                print(bid.id, 'closed')
            else:
                print(bid.id, 'not found')
