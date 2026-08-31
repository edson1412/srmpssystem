from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, "")

@register.filter
def percentage(value, total):
    """Calculate percentage of value relative to total"""
    try:
        if total and total > 0:
            return round((value / total) * 100, 1)
        return 0
    except (ValueError, TypeError):
        return 0

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if dictionary is None:
        return None
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    if hasattr(dictionary, '__getitem__'):
        try:
            return dictionary[key]
        except (KeyError, IndexError, TypeError):
            return None
    return None

@register.filter
def getattr(obj, attr):
    """Get attribute from object by name"""
    if obj is None or attr is None:
        return None
    if hasattr(obj, attr):
        return getattr(obj, attr)
    return None

@register.filter
def truncatechars(value, arg):
    """Truncate string to specified length"""
    if value is None:
        return ''
    if len(str(value)) > arg:
        return str(value)[:arg] + '...'
    return value