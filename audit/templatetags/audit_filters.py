from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """Return value from a dictionary by key."""
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
