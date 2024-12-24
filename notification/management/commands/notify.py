from logging import getLogger
from django.core.management.base import BaseCommand

from missions.models import Notification


logger = getLogger('django')


class Command(BaseCommand):
    """
    알림 처리 커맨트
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'send_method', type=str,
            help='Notification type',
        )
        parser.add_argument(
            'notification_ids', nargs='*', type=int, default=[],
            help='Notification object id to send notification.',
        )

    def handle(self, *args, **options):
        qs = self.get_queryset(options['send_method'].lower())
        if options['notification_ids']:
            qs = qs.filter(id__in=options['notification_ids'])
        for obj in qs:
            obj.send()
            logger.info('[push sent] {success_count}/{request_count}'.format(**obj.result))

    def get_queryset(self, send_method):
        return Notification.objects.not_requested(send_method)
