from django.template import Library
from django.utils.safestring import mark_safe
from django.urls import reverse

from common.templatetags.bootstrap import btn_dropdown_menu

# from notification.utils import FirebaseRealtimeChatHandler
from notification.utils import FirebaseFirestoreChatHandler


register = Library()


@register.simple_tag
def request_accept_status_menu(obj, size='', url_model_name='', prepend_text=''):
    menu_activate = '<a href="%s" class="dropdown-item">활성화</a>' % reverse(f'admin:biz_{url_model_name}_activate',
                                                                           kwargs={'id': obj.id})
    menu_deactivate = '<a href="%s" class="dropdown-item">비활성화</a>' % reverse(f'admin:biz_{url_model_name}_deactivate',
                                                                              kwargs={'id': obj.id})
    menu_reject = '<a href="%s" class="dropdown-item">승인 반려</a>' % reverse(f'admin:biz_{url_model_name}_reject',
                                                                           kwargs={'id': obj.id})

    menu_list = {
        'activated': {
            'btn_style_class': 'btn-success',
            'menus': [menu_deactivate],
        },
        'deactivated': {
            'btn_style_class': 'btn-dark',
            'menus': [menu_activate],
        },
        'requested': {
            'btn_style_class': 'btn-secondary',
            'menus': [menu_activate, menu_reject],
        },
        'rejected': {
            'btn_style_class': 'btn-warning',
            'menus': [menu_activate],
        }
    }
    btn_size_class = f'btn-{size}' if size else ''
    menu = menu_list[obj.state]
    btn_prepend_class = menu['btn_style_class'].replace('-', '-outline-')
    prepend = '<span class="btn %s %s">%s</span>' % (btn_size_class, btn_prepend_class, prepend_text) if prepend_text else ''
    btn_class = btn_size_class + ' ' + menu['btn_style_class']
    element = btn_dropdown_menu(obj.get_state_display(), menu['menus'], btn_class=btn_class, prepend=prepend)
    return mark_safe(element)