from django import template

register = template.Library()

@register.filter
def split(value, arg):
    if value:
        return value.split(arg)
    return []

@register.filter
def trim(value):
    if value:
        return value.strip()
    return value

@register.filter
def lookup(dictionary, key):
    """Pozwala na lookup w dictionary używając zmiennej"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def div(value, arg):
    """Dzielenie dwóch wartości"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def multiply(value, arg):
    """Mnożenie dwóch wartości"""
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0

@register.filter
def percentage(value, total):
    """Oblicza procent z dwóch wartości"""
    try:
        if float(total) == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except ValueError:
        return 0