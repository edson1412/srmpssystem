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