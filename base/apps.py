from django.apps import AppConfig
from django.conf import settings


class BaseConfig(AppConfig):
    name = 'base'
    verbose_name = '기본사항'

    def ready(self):
        from common.utils import CachedProperties, SlackWebhook
        from .views import CustomerHomeView
        from notification.models import Tasker

        anyman = CachedProperties()
        anyman.slack = SlackWebhook()
        anyman.server = 'Development' if settings.MAIN_HOST.startswith('test.') or settings.MAIN_HOST.startswith('dev.') else 'Production'
        CustomerHomeView.cache_all()
