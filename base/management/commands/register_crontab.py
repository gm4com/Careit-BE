import os
import subprocess

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    cron job 등록
    """

    def handle(self, *args, **options):
        crontabs = [
            '',
            'SHELL=/bin/bash',
            'MAILTO=anyman',
            'HOME=/home/anyman/www',
            '',
            '*/10 * * * * venv/bin/python ./manage.py mission_auto_finish',
            '* * * * * venv/bin/python ./manage.py mission_auto_unassign',
            '3 * * * * venv/bin/python ./manage.py cache_stats',
            '51 3 * * * venv/bin/python ./manage.py jobs daily',
            ''
        ]
        process = subprocess.run('crontab', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                                 preexec_fn=os.setsid, input='\n'.join(crontabs), encoding='ascii')

        if process.returncode:
            self.stdout.write(self.style.NOTICE(process.stdout))
            self.stdout.write(self.style.ERROR(process.stderr))
        else:
            self.stdout.write(self.style.SUCCESS('OK'))
