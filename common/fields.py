from django.conf import settings

from rest_framework.fields import URLField


class FullURLField(URLField):
    def to_representation(self, value):
        return 'https://%s%s' % (settings.MAIN_HOST, value.url) if value else ''

