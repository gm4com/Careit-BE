from django.apps import AppConfig


class BizConfig(AppConfig):
    name = 'biz'
    verbose_name = '애니비즈'

    def ready(self):
        import biz.signals