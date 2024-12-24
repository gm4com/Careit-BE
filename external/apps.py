from django.apps import AppConfig


class ExternalConfig(AppConfig):
    name = 'external'
    verbose_name = '외부연동'

    def ready(self):
        import external.signals
