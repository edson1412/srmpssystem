from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()

@register.filter
def timesince(value, arg=None):
    """
    Returns a string representing the time since that datetime
    (e.g., "2 days, 3 hours").
    """
    if not value:
        return ""

    now = timezone.now()
    if value > now:
        # If the value is in the future, return time until
        diff = value - now
        tense = "from now"
    else:
        # If the value is in the past, return time since
        diff = now - value
        tense = "ago"

    seconds = int(diff.total_seconds())

    if seconds < 60:
        return f"{seconds} seconds {tense}"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} {tense}"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} {tense}"
    elif seconds < 2592000: # 30 days
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} {tense}"
    elif seconds < 31536000: # 365 days
        months = seconds // 2592000 # Approximation
        return f"{months} month{'s' if months != 1 else ''} {tense}"
    else:
        years = seconds // 31536000 # Approximation
        return f"{years} year{'s' if years != 1 else ''} {tense}"

@register.filter
def get_item(dictionary, key):
    """
    Returns the value for a given key from a dictionary.
    Useful for accessing dictionary items with variable keys in templates.
    """
    return dictionary.get(key)
