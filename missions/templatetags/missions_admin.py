from django.template import Library
from django.utils.safestring import mark_safe
from django.urls import reverse

from common.templatetags.bootstrap import btn_dropdown_menu

# from notification.utils import FirebaseRealtimeChatHandler
from notification.utils import FirebaseFirestoreChatHandler


register = Library()


@register.simple_tag
def multi_mission_state_menu(obj, size='', prepend_text=''):
    menu_reqeust = '<a href="%s" class="dropdown-item">미션 요청</a>' % reverse('admin:missions_multimission_request', kwargs={'id': obj.id})
    menu_activate = '<a href="%s" class="dropdown-item">활성화</a>' % reverse('admin:missions_multimission_activate', kwargs={'id': obj.id})
    menu_deactivate = '<a href="%s" class="dropdown-item">비활성화</a>' % reverse('admin:missions_multimission_deactivate', kwargs={'id': obj.id})
    menu_push = '<a href="%s" class="dropdown-item">푸쉬 재전송</a>' % reverse('admin:missions_multimission_push', kwargs={'id': obj.id})

    menu_list = {
        'done': {
            'btn_style_class':'btn-success',
            'menus': [],
        },
        'draft': {
            'btn_style_class': 'btn-dark',
            'menus': [menu_reqeust, menu_deactivate],
        },
        'mission_deactivated': {
            'btn_style_class': 'btn-secondary',
            'menus': [menu_activate],
        },
        'bidding': {
            'btn_style_class': 'btn-warning',
            'menus': [menu_push, menu_deactivate],
        },
        'in_action': {
            'btn_style_class': 'btn-info',
            'menus': [menu_deactivate],
        },
    }

    btn_size_class = 'btn-%s' % size if size else ''
    menu = menu_list[obj.state]
    btn_prepend_class = menu['btn_style_class'].replace('-', '-outline-')
    prepend = '<span class="btn %s %s">%s</span>' % (btn_size_class, btn_prepend_class, prepend_text) if prepend_text else ''

    btn_class = btn_size_class + ' ' + menu['btn_style_class']
    element = btn_dropdown_menu(obj.get_state_display(), menu['menus'], btn_class=btn_class, prepend=prepend)
    return mark_safe(element)


@register.simple_tag
def multi_area_mission_state_menu(obj, size='', prepend_text=''):
    menu_cancel = '<a href="%s" class="dropdown-item">직권 취소</a>' % reverse('admin:missions_bid_cancel', kwargs={'id': obj.active_bid.id})  if obj.active_bid else ''
    menu_done_accept = '<a href="%s" class="dropdown-item">완료요청 승인</a>' % reverse('admin:missions_bid_done_request_accept', kwargs={'id': obj.active_bid.id})  if obj.active_bid else ''
    menu_done_reject = '<a href="%s" class="dropdown-item">완료요청 거부</a>' % reverse('admin:missions_bid_done_request_reject', kwargs={'id': obj.active_bid.id})  if obj.active_bid else ''
    menu_bid_info = '<a href="%s" class="dropdown-item">상세보기</a>' % reverse('admin:missions_bid_change', kwargs={'object_id': obj.active_bid.id})  if obj.active_bid else ''
    menu_divider = '<li href="%s" class="dropdown-divider"></li>'

    menu_list = {
        'draft': {
            'btn_style_class': 'btn-dark',
            'menus': [],
        },
        'mission_deactivated': {
            'btn_style_class': 'btn-secondary',
            'menus': [],
        },
        'done': {
            'btn_style_class':'btn-success',
            'menus': [],
        },
        'done_requested': {
            'btn_style_class':'btn-primary',
            'menus': [menu_done_accept, menu_done_reject, menu_divider, menu_bid_info],
        },
        'admin_canceled': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'won_and_canceled': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'bidding': {
            'btn_style_class': 'btn-warning',
            'menus': [],
        },
        'in_action': {
            'btn_style_class': 'btn-primary',
            'menus': [menu_cancel],
        },
    }

    btn_size_class = 'btn-%s' % size if size else ''
    menu = menu_list[obj.state]
    btn_prepend_class = menu['btn_style_class'].replace('-', '-outline-')
    prepend = '<span class="btn %s %s">%s</span>' % (btn_size_class, btn_prepend_class, prepend_text) if prepend_text else ''

    btn_class = btn_size_class + ' ' + menu['btn_style_class']
    element = btn_dropdown_menu(obj.get_state_display(), menu['menus'], btn_class=btn_class, prepend=prepend)
    return mark_safe(element)


@register.simple_tag
def bid_state_menu(obj, size='', prepend_text=''):
    menu_cancel = '<a href="%s" class="dropdown-item">직권 취소</a>' % reverse('admin:missions_bid_cancel', kwargs={'id': obj.id})

    menu_list = {
        'done': {
            'btn_style_class':'btn-success',
            'menus': [menu_cancel],
        },
        'bidding': {
            'btn_style_class': 'btn-dark',
            'menus': [],
        },
        'applied': {
            'btn_style_class': 'btn-warning',
            'menus': [],
        },
        'not_applied': {
            'btn_style_class': 'btn-secondary',
            'menus': [],
        },
        'waiting_assignee': {
            'btn_style_class': 'btn-secondary',
            'menus': [],
        },
        'failed': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'admin_canceled': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'timeout_canceled': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'user_canceled': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'won_and_canceled': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'done_and_canceled': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'bid_and_canceled': {
            'btn_style_class': 'btn-danger',
            'menus': [],
        },
        'in_action': {
            'btn_style_class': 'btn-primary',
            'menus': [menu_cancel],
        },
    }

    btn_size_class = 'btn-%s' % size if size else ''
    menu = menu_list[obj.state]
    btn_prepend_class = menu['btn_style_class'].replace('-', '-outline-')
    prepend = '<span class="btn %s %s">%s</span>' % (btn_size_class, btn_prepend_class, prepend_text) if prepend_text else ''

    btn_class = btn_size_class + ' ' + menu['btn_style_class']
    element = btn_dropdown_menu(obj.get_state_display(), menu['menus'], btn_class=btn_class, prepend=prepend)
    return mark_safe(element)


@register.inclusion_tag('admin/bid/anytalk.html')
def view_anytalk(bid):
    """애니톡 표시"""
    # anytalk = FirebaseRealtimeChatHandler()
    anytalk = FirebaseFirestoreChatHandler().get(bid.id)
    if anytalk:
        return {
            'bid': bid,
            'talks': anytalk['chat'],
            'is_end': anytalk['info']['is_end'] if 'info' in anytalk and anytalk['info'] and 'is_end' in anytalk['info'] else True,
        }
    return {'is_end': True}
