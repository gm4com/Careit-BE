from django import template
from django.contrib import admin
from admin_reorder.middleware import ModelAdminReorder

from common.admin import get_change_message


register = template.Library()


@register.simple_tag(takes_context=True)
def get_app_list(context, **kwargs):
    # app_list = admin.site.get_app_list(context['request'])
    # admin_reorder = ModelAdminReorder(context['request'], admin.site.get_app_list(context['request']))
    admin_reorder = ModelAdminReorder()
    admin_reorder.init_config(context['request'], admin.site.get_app_list(context['request']))
    app_list = admin_reorder.get_app_list()
    return app_list


@register.simple_tag(name='get_change_message')
def _get_change_message(obj, with_reason=True):
    return get_change_message(obj, with_reason)
