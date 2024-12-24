from django.core.management.base import BaseCommand

from missions.models import Review


class Command(BaseCommand):
    """
    리뷰 수신자 필드 채우기 커맨드
    """

    def handle(self, *args, **options):
        for review in Review.objects.filter(_received_user__isnull=True):
            review._received_user_id = review.received_user.id
            review._is_created_user_helper = bool(review.created_user_id == review.bid.helper.user_id)
            review.save()
