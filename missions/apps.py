from django.apps import AppConfig


class MissionsConfig(AppConfig):
    name = 'missions'
    verbose_name = '미션'

    def ready(self):
        import missions.signals
