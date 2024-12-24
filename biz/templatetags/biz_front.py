from django.template import Library
from ..models import REQUEST_ACCEPT_STATUS

"""
CONSTANTS
"""

REQUEST_ACCEPT_STATUS_CUSTOMER_STYLE_CLASS = {
    'requested': 'warning',
    'activated': 'success',
    'deactivated': 'secondary',
    'rejected': 'danger',
}


"""
REGISTER
"""

register = Library()


@register.filter
def get_request_accept_status_text(key):
    return dict(REQUEST_ACCEPT_STATUS).get(key)


@register.filter
def get_request_accept_status_style_class(key):
    return REQUEST_ACCEPT_STATUS_CUSTOMER_STYLE_CLASS.get(key)
