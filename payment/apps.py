from django.apps import AppConfig


class PaymentConfig(AppConfig):
    name = 'payment'
    verbose_name = '결제'

    def ready(self):
        import payment.signals
