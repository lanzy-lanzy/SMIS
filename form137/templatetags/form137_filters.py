from django import template

register = template.Library()


@register.filter(name='getitem')
def getitem(dictionary, key):
    try:
        return dictionary[key]
    except (KeyError, TypeError):
        return None


@register.filter(name='next_grade')
def next_grade(level):
    """Return the next grade level after the given level.

    When level is 10, returns the string "11 (Senior High School)".
    Otherwise returns level + 1 as an integer.
    """
    if level == 10:
        return "11 (Senior High School)"
    return level + 1
