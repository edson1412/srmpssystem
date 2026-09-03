# prison/templatetags/custom_filters.py

from django import template
from django.utils.html import escape

register = template.Library()


@register.filter(name='percentage')
def percentage(value, total):
    """
    Calculate percentage of value relative to total.
    
    Usage: {{ value|percentage:total }}
    Example: {{ convicted_count|percentage:total_prisoners }}
    """
    try:
        # Convert to float and handle potential errors
        value = float(value)
        total = float(total)
        
        # Avoid division by zero
        if total == 0:
            return 0
        
        # Calculate percentage
        result = (value / total) * 100
        
        # Format to 1 decimal place (or integer if whole number)
        if result == int(result):
            return int(result)
        else:
            return round(result, 1)
            
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter(name='multiply')
def multiply(value, arg):
    """
    Multiply value by arg.
    
    Usage: {{ value|multiply:arg }}
    Example: {{ price|multiply:quantity }}
    """
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter(name='divide')
def divide(value, arg):
    """
    Divide value by arg.
    
    Usage: {{ value|divide:arg }}
    Example: {{ total|divide:count }}
    """
    try:
        arg = float(arg)
        if arg == 0:
            return 0
        return float(value) / arg
    except (TypeError, ValueError):
        return 0


@register.filter(name='subtract')
def subtract(value, arg):
    """
    Subtract arg from value.
    
    Usage: {{ value|subtract:arg }}
    """
    try:
        return float(value) - float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter(name='add')
def add(value, arg):
    """
    Add arg to value.
    
    Usage: {{ value|add:arg }}
    """
    try:
        return float(value) + float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter(name='months_to_years')
def months_to_years(months):
    """
    Convert months to years and months format.
    
    Usage: {{ months|months_to_years }}
    Example: 72 months -> "6 years"
             30 months -> "2 years 6 months"
    """
    try:
        months = int(months)
        years = months // 12
        remaining_months = months % 12
        
        if years == 0:
            return f"{remaining_months} months"
        elif remaining_months == 0:
            return f"{years} year{'s' if years != 1 else ''}"
        else:
            return f"{years} year{'s' if years != 1 else ''} {remaining_months} months"
    except (TypeError, ValueError):
        return "N/A"


@register.filter(name='date_format')
def date_format(date_value, format_str="%d-%m-%Y"):
    """
    Format a date with custom format.
    
    Usage: {{ date|date_format:"%d/%m/%Y" }}
    """
    if not date_value:
        return ""
    
    try:
        return date_value.strftime(format_str)
    except (AttributeError, ValueError):
        return str(date_value)


@register.filter(name='status_badge')
def status_badge(status):
    """
    Return appropriate CSS class for status badges.
    
    Usage: {{ status|status_badge }}
    """
    status_map = {
        'approved': 'success',
        'active': 'success',
        'completed': 'success',
        'pending': 'warning',
        'submitted': 'info',
        'imported': 'primary',
        'validated': 'info',
        'rejected': 'danger',
        'cancelled': 'danger',
        'inactive': 'secondary',
        'not_submitted': 'secondary',
    }
    return status_map.get(str(status).lower(), 'secondary')


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Get item from dictionary by key.
    
    Usage: {{ my_dict|get_item:key }}
    """
    try:
        return dictionary.get(key, "")
    except AttributeError:
        return ""


@register.filter(name='format_currency')
def format_currency(value):
    """
    Format a number as currency.
    
    Usage: {{ amount|format_currency }}
    """
    try:
        value = float(value)
        return f"MWK {value:,.2f}"
    except (TypeError, ValueError):
        return "MWK 0.00"