from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    """
    Delete Cache
    """

    def handle(self, *args, **options):
        cache.clear()
        self.stdout.write(self.style.NOTICE('Cache has been empty.'))
