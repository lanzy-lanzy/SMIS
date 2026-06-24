from django import template

register = template.Library()


@register.filter(name='getitem')
def getitem(dictionary, key):
    try:
        return dictionary[key]
    except (KeyError, TypeError):
        return None
