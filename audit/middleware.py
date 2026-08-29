from .utils import set_current_request


class AuditRequestMiddleware:
    """Middleware to preserve the current request for audit logging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        try:
            response = self.get_response(request)
        finally:
            set_current_request(None)
        return response
