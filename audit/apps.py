"""
Audit app configuration.
Registers signal handlers for automatic audit logging.
"""
from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = 'Audit Trail'
    
    def ready(self):
        """
        Import signal handlers when the app is ready.
        This ensures audit logging is active for all model changes.
        """
        import audit.signals  # noqa
