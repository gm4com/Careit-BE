from django.core.management.base import BaseCommand

from common.utils import ServerScript


class Command(BaseCommand):
    """
    Update Server
    """

    def handle(self, *args, **options):
        script = ServerScript()
        script.deploy(view_on_console=True)
        self.stdout.write(self.style.NOTICE('Server Update Done!!'))
