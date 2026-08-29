"""
Comprehensive Audit Trail System
Captures and preserves all changes to critical system data
"""
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import json


class AuditLog(models.Model):
    """
    Immutable audit log that tracks all changes to critical models.
    This table is append-only - records are never updated or deleted.
    """
    
    ACTION_CHOICES = [
        ('CREATE', _('Create')),
        ('UPDATE', _('Update')),
        ('DELETE', _('Delete')),
        ('LOGIN', _('Login')),
        ('LOGOUT', _('Logout')),
        ('PERMISSION_CHANGE', _('Permission Change')),
        ('ROLE_CHANGE', _('Role Change')),
        ('EXPORT', _('Export/Download')),
        ('PRINT', _('Print')),
        ('REPORT_GENERATE', _('Report Generated')),
    ]
    
    # Basic tracking info
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    
    # User info
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,  # Prevent deletion of user if audit logs exist
        related_name='audit_logs',
        null=True,
        blank=True
    )
    
    # Content tracking (generic foreign key to any model)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_index=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Model name (human readable)
    model_name = models.CharField(max_length=100, db_index=True)
    object_str = models.CharField(
        max_length=500,
        help_text="String representation of the object at time of change"
    )
    
    # Change tracking
    old_values = models.JSONField(default=dict, blank=True)  # Previous values
    new_values = models.JSONField(default=dict, blank=True)  # New values
    changed_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="List of field names that were changed"
    )
    
    # Request info
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    # Additional context
    description = models.TextField(blank=True)
    reason = models.TextField(
        blank=True,
        help_text="User-provided reason for the change (if applicable)"
    )
    
    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['model_name', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['content_type', 'object_id']),
        ]
        # Set permissions - these are mapped to roles
        permissions = [
            ('view_audit_log', 'Can view audit logs'),
            ('export_audit_log', 'Can export audit logs'),
        ]
        # Note: We'll prevent updates/deletes via application logic and DB constraints
    
    def __str__(self):
        return f"{self.action} - {self.model_name} ({self.object_id}) by {self.user} at {self.timestamp}"

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise RuntimeError("Audit logs are immutable and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit logs are immutable and cannot be deleted.")
    
    @classmethod
    def log_action(cls, action, user=None, content_object=None, old_values=None,
                   new_values=None, changed_fields=None, request=None,
                   description="", reason=""):
        """
        Create an audit log entry.
        
        Args:
            action: Type of action (CREATE, UPDATE, DELETE, etc.)
            user: User performing the action
            content_object: The object being modified
            old_values: Dict of previous field values
            new_values: Dict of new field values
            changed_fields: List of field names that changed
            request: HTTP request object (for IP, user agent, etc.)
            description: Description of the action
            reason: User-provided reason for change
        """
        from audit.utils import get_current_request, serialize_audit_data

        # If request is not explicitly provided, use the current request stored in middleware
        if request is None:
            request = get_current_request()

        # Use authenticated request user if no explicit user was supplied
        if user is None and request is not None and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
        # Extract request info
        ip_address = None
        user_agent = ""
        request_method = ""
        request_path = ""
        
        if request:
            ip_address = cls.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            request_method = request.method
            request_path = request.path[:500]
        
        # Determine content type and object ID
        content_type = None
        object_id = None
        model_name = "Unknown"
        object_str = ""
        
        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = content_object.pk
            model_name = content_object.__class__.__name__
            object_str = str(content_object)[:500]
        
        # Serialize values for JSONField storage
        old_values = serialize_audit_data(old_values or {})
        new_values = serialize_audit_data(new_values or {})

        # Create the log entry
        log_entry = cls.objects.create(
            action=action,
            user=user,
            content_type=content_type,
            object_id=object_id,
            model_name=model_name,
            object_str=object_str,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields or [],
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            description=description,
            reason=reason
        )
        
        return log_entry
    
    @staticmethod
    def get_client_ip(request):
        """
        Extract client IP address from request,
        accounting for proxies and load balancers.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def can_be_deleted(self):
        """Audit logs should never be deleted."""
        return False
    
    def can_be_edited(self):
        """Audit logs should never be edited."""
        return False


class AuditLogField(models.Model):
    """
    Stores detailed field-level changes for audit logs.
    Useful for tracking complex changes at the field level.
    """
    audit_log = models.ForeignKey(
        AuditLog,
        on_delete=models.CASCADE,
        related_name='field_changes'
    )
    field_name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=50)  # CharField, IntegerField, etc.
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = _("Audit Log Field")
        verbose_name_plural = _("Audit Log Fields")
    
    def __str__(self):
        return f"{self.field_name}: {self.old_value} → {self.new_value}"


class AuditLogSummary(models.Model):
    """
    Daily summary of audit activities for quick overview.
    Generated automatically, append-only.
    """
    date = models.DateField(auto_now_add=True, unique=True, db_index=True)
    total_actions = models.IntegerField(default=0)
    creates = models.IntegerField(default=0)
    updates = models.IntegerField(default=0)
    deletes = models.IntegerField(default=0)
    logins = models.IntegerField(default=0)
    unique_users = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _("Audit Log Summary")
        verbose_name_plural = _("Audit Log Summaries")
        ordering = ['-date']
    
    def __str__(self):
        return f"Audit Summary - {self.date}"
