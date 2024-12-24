from django.conf import settings
from rest_framework.authentication import SessionAuthentication


def template_load_settings(request):
    """Load settings to template"""
    loaded = {}
    for setting in settings.TEMPLATE_LOAD_SETTINGS:
        loaded.update({setting: getattr(settings, setting, None)})
    return {'settings': loaded}


class CsrfExemptSessionAuthentication(SessionAuthentication):

    def enforce_csrf(self, request):
        return
