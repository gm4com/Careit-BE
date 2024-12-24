from django.core.management.base import BaseCommand

from accounts.models import State
from base.constants import USER_STATUS, MISSION_STATUS


class Command(BaseCommand):
    """
    상태 초기화 커맨드
    """

    def handle(self, *args, **options):
        self.create_user_status()
        self.create_mission_status()

    def create_user_status(self):
        self._create_status('user', USER_STATUS)

    def create_mission_status(self):
        self._create_status('mission', MISSION_STATUS)

    def _create_status(self, state_type, status):
        for code, name in status:
            State.objects.get_or_create(state_type=state_type, code=code, name=name)

