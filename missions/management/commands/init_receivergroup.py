from django.core.management.base import BaseCommand

from notification.models import ReceiverGroup


class Command(BaseCommand):
    """
    알림 수신그룹 데이터 초기화 커맨드
    """

    def handle(self, *args, **options):
        groups = [
            {'title': '광고허용', 'code': 'ad_allowed', 'query': {"is_ad_allowed": True}},
            {'title': '헬퍼만', 'code': 'helperonly', 'query': {"helper__accepted_datetime__isnull": False}},
            {'title': '헬퍼가 아닌 회원', 'code': 'not_helper', 'query': {"helper__accepted_datetime__isnull": True}},
            {'title': '이용실적 있는 회원', 'code': 'used', 'query': {"missions__saved_state": "done"}},
            {'title': '이용실적 없는 회원', 'code': 'not_used', 'query': {"test": None}},
            {'title': '최근 3개월간 앱 사용하지 않은 회원', 'code': 'nolog_3month', 'query': {"last_login__lt": "__timezone.now()__"}},
            {'title': '온라인미션 헬퍼', 'code': 'online_helper', 'query': {"helper__is_online_acceptable": True}},
        ]
        for group in groups:
            try:
                ReceiverGroup.objects.create(**group)
            except:
                print('%s (%s) already exists' % (group['title'], group['code']))
            else:
                print('%s (%s) created' % (group['title'], group['code']))
