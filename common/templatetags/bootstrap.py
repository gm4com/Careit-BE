from django.template import Library


register = Library()


# todo: 클래스 구현 추가할 것.


@register.filter
def btn_dropdown_menu(title, menus=[], btn_class='btn-default', prepend=''):
    btn_class += ' dropdown-toggle' if menus else ''
    html = """
        <button class="btn %s" type="button" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
            %s
        </button>""" % (btn_class, title)
    if menus:
        html += """
        <div class="dropdown-menu dropdown-menu-right">
            %s
        </div>""" % ' '.join(menus)
    return '<div class="dropdown"><div class="btn-group">' + prepend + html + '</div></div>'
