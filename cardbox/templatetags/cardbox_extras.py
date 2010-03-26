from django import template

register = template.Library()

@register.filter
def timedelta(value):
    "Formats a timedelta object"
    minutes = value.seconds/60.0
    return "%d hours, %d minutes"%(minutes//60, minutes%60)
