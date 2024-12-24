import inspect

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
from django.test.client import Client

from base.admin import get_preset_dates, StatisticsView
from base.templatetags import dashboard
from accounts.models import User


class Command(BaseCommand):
    """
    통계 캐시 리셋 커맨드
    """

    def handle(self, *args, **options):

        client = Client()
        user = User.objects.first()
        client.force_login(user)

        cache.clear()
        for stat in ('user', 'mission', 'payment', 'recommend', 'finance'):
            for preset in ('month', 'week', '3month', 'thismonth', 'prevmonth', 'ppmonth'):
                response = client.get('/admin/statistics/%s/?preset=%s' % (stat, preset))

