import json

from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.query import QuerySet
from django.utils.safestring import mark_safe
from django.template import Library


from common.utils import add_comma


register = Library()


@register.filter
def to_json(objects):
    if isinstance(objects, QuerySet):
        return mark_safe(serialize('json', objects))
    return mark_safe(json.dumps(objects, cls=DjangoJSONEncoder))


@register.filter(name='add_comma')
def _add_comma(value):
    try:
        value = int(value)
    except:
        return value
    return add_comma(value)


@register.filter
def add_prop(value, prop):
    prop = prop.split('=')
    value.field.widget.attrs[prop[0]] = prop[1]
    return str(value)
