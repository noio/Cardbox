from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def timedelta(value):
    "Formats a timedelta object"
    minutes = value.seconds/60.0
    return "%d hours, %d minutes"%(minutes//60, minutes%60)

@register.filter
def from_datastore(value, arg):
    c = value.__class__
    return getattr(c,arg).get_value_for_datastore(value)

@register.filter
@stringfilter
def page_name(value, arg=False):
    prefix = bool(arg)
    if not prefix:
        value = value.split(':')[1]
    else:
        value = value.replace(':',': ')
    return ' '.join([w.capitalize() for w in value.split('_')])