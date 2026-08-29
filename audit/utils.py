import threading
from datetime import date, datetime, time
from django.db import models

_request_local = threading.local()


def set_current_request(request):
    """Store the current request in thread-local storage."""
    _request_local.request = request


def get_current_request():
    """Return the current request stored in thread-local storage."""
    return getattr(_request_local, 'request', None)


def serialize_audit_value(value):
    """Convert values to JSON-safe primitives for audit logging."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): serialize_audit_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serialize_audit_value(v) for v in value]
    if isinstance(value, models.Model):
        return str(value)
    try:
        return str(value)
    except Exception:
        return None


def serialize_audit_data(data):
    """Recursively serialize a dict or list for JSON storage."""
    if isinstance(data, dict):
        return {str(k): serialize_audit_value(v) for k, v in data.items()}
    if isinstance(data, (list, tuple, set)):
        return [serialize_audit_value(v) for v in data]
    return serialize_audit_value(data)
