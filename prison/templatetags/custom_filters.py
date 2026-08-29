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