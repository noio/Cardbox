from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def timedelta(value):
    "Formats a timedelta object"
    minutes = value.seconds/60.0
    hours = value.days*24 + minutes//60
    if hours < 1:
        hour_text = ''
    elif hours == 1:
        hour_text = '1 hour, '
    else:
        hour_text = '%d hours, '%hours
    return "%s%d minute%s"%(hour_text, minutes%60, '' if minutes == 1 else 's')

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
    
@register.filter
def dictkey(d, k):
    return d.get(k, None)