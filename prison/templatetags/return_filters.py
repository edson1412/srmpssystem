# prison/templatetags/return_filters.py
from django import template
from datetime import datetime

register = template.Library()

@register.filter
def getattr(obj, attr_name):
    """Get an attribute from an object"""
    if hasattr(obj, attr_name):
        value = getattr(obj, attr_name)
        if isinstance(value, datetime):
            return value.strftime('%d-%m-%Y')
        return value
    return None

    from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get item from dictionary by key."""
    if not dictionary:
        return ''
    try:
        if isinstance(dictionary, dict):
            # Try the exact key first
            if key in dictionary:
                return dictionary[key]
            # Try case-insensitive match
            for k, v in dictionary.items():
                if str(k).lower() == str(key).lower():
                    return v
            # Try with underscores instead of spaces/dots
            normalized_key = str(key).lower().replace(' ', '_').replace('.', '_').replace('/', '_')
            for k, v in dictionary.items():
                if str(k).lower().replace(' ', '_').replace('.', '_').replace('/', '_') == normalized_key:
                    return v
        elif hasattr(dictionary, key):
            # Handle object attributes
            return getattr(dictionary, key, '')
        return ''
    except (AttributeError, TypeError, KeyError):
        return ''


@register.filter(name='default_if_none')
def default_if_none(value, default=''):
    """Return default if value is None or empty."""
    if value is None or value == '':
        return default
    return value


@register.filter(name='get_nested')
def get_nested(dictionary, path):
    """Get value from nested dictionary using dot notation."""
    if not dictionary:
        return ''
    try:
        current = dictionary
        for key in path.split('.'):
            if isinstance(current, dict):
                current = current.get(key, '')
            elif hasattr(current, key):
                current = getattr(current, key, '')
            else:
                return ''
        return current
    except (AttributeError, TypeError):
        return ''


@register.filter(name='format_date')
def format_date(value, fmt='%d-%m-%Y'):
    """Format a date value."""
    if not value:
        return ''
    try:
        if hasattr(value, 'strftime'):
            return value.strftime(fmt)
        return str(value)
    except (ValueError, TypeError):
        return ''