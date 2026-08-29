from django import template

register = template.Library()

@register.filter
def grade_color(grade):
    """Return Bootstrap color class based on grade."""
    grade_colors = {
        'A': 'success',
        'B': 'info', 
        'C': 'warning',
        'D': 'secondary',
        'F': 'danger'
    }
    return grade_colors.get(grade, 'secondary')

@register.filter
def filter(queryset, field, value):
    """Filter queryset by field value."""
    if not queryset:
        return queryset
    return queryset.filter(**{field: value})

@register.filter
def percent_of(value, total):
    """Calculate percentage of value from total."""
    if not value or not total:
        return 0
    return round((float(value) / float(total)) * 100, 1)

@register.filter
def length_completed(recruits):
    """Count completed/graduated recruits."""
    if not recruits:
        return 0
    return recruits.filter(status__in=['completed', 'graduated']).count()

@register.filter
def length_training(recruits):
    """Count recruits in training."""
    if not recruits:
        return 0
    return recruits.filter(status='in_training').count()

@register.filter
def length_finished(recruits):
    """Alias for length_completed."""
    return length_completed(recruits)

@register.filter
def length_enrolled(recruits):
    """Count enrolled recruits."""
    if not recruits:
        return 0
    return recruits.filter(status='enrolled').count()

@register.filter
def length_failed(recruits):
    """Count failed recruits."""
    if not recruits:
        return 0
    return recruits.filter(status='failed').count()

@register.filter
def has_scores(recruits):
    """Check if any recruits have overall scores."""
    if not recruits:
        return False
    return recruits.filter(overall_score__isnull=False).exists()

@register.filter
def count_excellent(recruits):
    """Count recruits with excellent scores (80%+)."""
    if not recruits:
        return 0
    return recruits.filter(overall_score__gte=80).count()

@register.filter
def count_good(recruits):
    """Count recruits with good scores (60-79%)."""
    if not recruits:
        return 0
    return recruits.filter(overall_score__gte=60, overall_score__lt=80).count()

@register.filter
def count_needs_improvement(recruits):
    """Count recruits who need improvement (<60%)."""
    if not recruits:
        return 0
    return recruits.filter(overall_score__lt=60).count()

@register.filter
def lookup(dictionary, key):
    """Lookup a key in a dictionary."""
    try:
        return dictionary.get(key, '')
    except (AttributeError, TypeError):
        return ''

@register.filter
def mul(value, multiplier):
    """Multiply two values."""
    try:
        return float(value) * float(multiplier)
    except (ValueError, TypeError):
        return 0

@register.filter
def dict_get(dictionary, key):
    """Get a value from a dictionary by key, similar to dictionary.get()"""
    try:
        return dictionary.get(key, '')
    except (AttributeError, TypeError):
        return ''

@register.filter
def split(value, delimiter=','):
    """Split a string by the given delimiter and return a list."""
    if value is None:
        return []
    try:
        return str(value).split(delimiter)
    except Exception:
        return []
