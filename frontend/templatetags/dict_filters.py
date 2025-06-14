from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Pobiera wartość ze słownika używając klucza"""
    if dictionary:
        return dictionary.get(key)
    return None