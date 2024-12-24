from django import template
from django.utils import timezone


register = template.Library()


@register.filter(name='range')
def _range(start, end):
	try:
		step = -1 if end < start else 1
	except:
		return []
	return list(range(int(start), int(end), step))


@register.filter(name='str')
def _str(text):
	return str(text)


@register.filter(name='startswith')
def _startswith(text, prefix):
	return text.startswith(prefix)


@register.filter(name='endswith')
def _endswith(text, suffix):
	return text.endswith(suffix)


@register.filter(name='lstrip')
def _lstrip(text, chars=None):
	return str(text).lstrip(chars)


@register.filter(name='print')
def _print(value):
	print(value)
	return value


@register.filter(name='dir')
def _dir(value):
	print(dir(value))
	return value


@register.filter(name='getattr')
def _getattr(value, attr):
	if value:
		if isinstance(value, dict):
			return value[attr] if attr in value else ''
		return getattr(value, attr, '')
	return ''

@register.filter(name='localtime')
def _localtime(dt):
	return timezone.localtime(dt)
