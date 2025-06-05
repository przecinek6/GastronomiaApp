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

@register.filter
def sub(value, arg):
    """Odejmowanie dwóch wartości"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def abs_value(value):
    """Wartość bezwzględna"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return 0

@register.filter
def progress_percentage(points, level):
    """Oblicza procent postępu do następnego poziomu"""
    try:
        points = int(points)
        if level == 'bronze':
            return min((points / 500) * 100, 100)
        elif level == 'silver':
            return min(((points - 500) / 500) * 100, 100) if points >= 500 else 0
        elif level == 'gold':
            return min(((points - 1000) / 1000) * 100, 100) if points >= 1000 else 0
        elif level == 'platinum':
            return 100
        return 0
    except (ValueError, TypeError):
        return 0

@register.filter
def points_to_next_level(points, level):
    """Oblicza ile punktów potrzeba do następnego poziomu"""
    try:
        points = int(points)
        if level == 'bronze':
            return max(500 - points, 0)
        elif level == 'silver':
            return max(1000 - points, 0)
        elif level == 'gold':
            return max(2000 - points, 0)
        else:
            return 0
    except (ValueError, TypeError):
        return 0