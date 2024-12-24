from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'
    verbose_name = '계정'

    def ready(self):
        import accounts.signals
