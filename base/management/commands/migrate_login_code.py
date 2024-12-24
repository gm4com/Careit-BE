from django.core.management.base import BaseCommand

from external.models import ExternalMission


class Command(BaseCommand):
    """
    이케아미션 로그인 코드 마이그레이션 커맨드
    """

    def handle(self, *args, **options):
        ikea_missions = ExternalMission.objects.exclude(login_code='').filter(mission__isnull=False)
        for ikea in ikea_missions:
            if not ikea.mission.login_code:
                ikea.mission.login_code = ikea.login_code
                ikea.mission.save()
                print(ikea.id)
