from django import template
from django.utils.safestring import mark_safe
import json

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


@register.filter(name='to_json')
def to_json(value):
    """Convert value to JSON string."""
    try:
        return mark_safe(json.dumps(value))
    except (TypeError, ValueError):
        return '{}'


@register.filter(name='get_type')
def get_type(value):
    """Get the type of a value."""
    if value is None:
        return 'None'
    return type(value).__name__


@register.filter(name='is_list')
def is_list(value):
    """Check if value is a list."""
    return isinstance(value, list)


@register.filter(name='is_dict')
def is_dict(value):
    """Check if value is a dictionary."""
    return isinstance(value, dict)


@register.filter(name='get_list_item')
def get_list_item(lst, index):
    """Get item from list by index."""
    if not lst:
        return ''
    try:
        return lst[int(index)]
    except (ValueError, IndexError, TypeError):
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


@register.filter(name='add_class')
def add_class(field, css_class):
    """Add CSS class to a form field."""
    if not field:
        return field
    try:
        existing = field.field.widget.attrs.get('class', '')
        field.field.widget.attrs['class'] = f"{existing} {css_class}".strip()
    except (AttributeError, KeyError):
        pass
    return field


@register.filter(name='get_display')
def get_display(obj, field_name):
    """Get display value for a model field."""
    if not obj:
        return ''
    try:
        if hasattr(obj, f'get_{field_name}_display'):
            return getattr(obj, f'get_{field_name}_display')()
        elif hasattr(obj, field_name):
            return getattr(obj, field_name)
        return ''
    except (AttributeError, TypeError):
        return ''


@register.filter(name='default_if_none')
def default_if_none(value, default=''):
    """Return default if value is None or empty."""
    if value is None or value == '':
        return default
    return value


# ============ NEW FILTERS ============

@register.filter(name='split')
def split(value, separator=','):
    """
    Split a string by the given separator.

    Usage:
    {% for item in "a,b,c"|split:"," %}
        {{ item }}
    {% endfor %}

    Or with default comma separator:
    {% for item in "a,b,c"|split %}
        {{ item }}
    {% endfor %}
    """
    if value is None:
        return []
    try:
        if isinstance(value, (list, tuple)):
            return value
        return str(value).split(separator)
    except (AttributeError, TypeError):
        return []


@register.filter(name='join')
def join(value, separator=', '):
    """
    Join a list with the given separator.

    Usage:
    {{ my_list|join:", " }}
    """
    if value is None:
        return ''
    try:
        if isinstance(value, (list, tuple)):
            return separator.join(str(item) for item in value)
        return str(value)
    except (AttributeError, TypeError):
        return ''


@register.filter(name='add')
def add(value, arg):
    """
    Add a value to a number.

    Usage:
    {{ 5|add:3 }}  # Returns 8
    """
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        try:
            return float(value) + float(arg)
        except (ValueError, TypeError):
            return value


@register.filter(name='subtract')
def subtract(value, arg):
    """
    Subtract a value from a number.

    Usage:
    {{ 10|subtract:3 }}  # Returns 7
    """
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        try:
            return float(value) - float(arg)
        except (ValueError, TypeError):
            return value


@register.filter(name='mul')
def mul(value, arg):
    """
    Multiply a number by a value.

    Usage:
    {{ 5|mul:3 }}  # Returns 15
    """
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        try:
            return float(value) * float(arg)
        except (ValueError, TypeError):
            return value


@register.filter(name='div')
def div(value, arg):
    """
    Divide a number by a value.

    Usage:
    {{ 10|div:2 }}  # Returns 5
    """
    try:
        return int(value) / int(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        try:
            return float(value) / float(arg)
        except (ValueError, TypeError, ZeroDivisionError):
            return ''