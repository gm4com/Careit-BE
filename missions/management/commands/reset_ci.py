from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    """
    ci 인증정보 리셋
    """

    def handle(self, *args, **options):
        User.objects.exclude(ci='').update(ci='')
