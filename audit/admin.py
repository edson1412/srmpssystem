"""
Admin configuration for audit models.
Provides read-only access with comprehensive display options.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import AuditLog, AuditLogField, AuditLogSummary


class AuditLogFieldInline(admin.TabularInline):
    """Inline display of field-level changes."""
    model = AuditLogField
    readonly_fields = ('field_name', 'field_type', 'old_value', 'new_value')
    can_delete = False
    
    def has_add_permission(self, request):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin interface for audit logs.
    Read-only to maintain immutability.
    """
    list_display = (
        'id', 'timestamp', 'action_badge', 'user_display',
        'model_name', 'object_id', 'ip_address_display'
    )
    list_filter = (
        'action', 'model_name', 'timestamp', 'user',
        ('ip_address', admin.RelatedFieldListFilter),
    )
    search_fields = (
        'object_str', 'model_name', 'user__username',
        'ip_address', 'user_agent'
    )
    readonly_fields = (
        'timestamp', 'action', 'user', 'content_type', 'object_id',
        'model_name', 'object_str', 'old_values_display', 'new_values_display',
        'changed_fields', 'ip_address', 'user_agent', 'request_method',
        'request_path', 'description', 'reason'
    )
    inlines = [AuditLogFieldInline]
    
    # Sorting
    ordering = ['-timestamp']
    
    # Pagination
    list_per_page = 50
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'timestamp', 'action', 'user', 'model_name',
                'object_id', 'object_str'
            )
        }),
        ('Change Details', {
            'fields': (
                'changed_fields', 'old_values_display',
                'new_values_display', 'description', 'reason'
            )
        }),
        ('Request Information', {
            'fields': (
                'ip_address', 'user_agent', 'request_method',
                'request_path'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Allow viewing but not editing."""
        return request.method in ('GET', 'HEAD', 'OPTIONS')
    
    def action_badge(self, obj):
        """Display action with color coding."""
        colors = {
            'CREATE': '#28a745',
            'UPDATE': '#ffc107',
            'DELETE': '#dc3545',
            'LOGIN': '#007bff',
            'LOGOUT': '#6c757d',
            'PERMISSION_CHANGE': '#e83e8c',
            'ROLE_CHANGE': '#e83e8c',
            'EXPORT': '#17a2b8',
            'PRINT': '#17a2b8',
            'REPORT_GENERATE': '#007bff',
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_badge.short_description = 'Action'
    
    def user_display(self, obj):
        """Display user with link if available."""
        if obj.user:
            return format_html(
                '<a href="/admin/accounts/customuser/{}/change/">{}</a>',
                obj.user.id,
                obj.user.get_full_name()
            )
        return 'System'
    user_display.short_description = 'User'
    
    def ip_address_display(self, obj):
        """Display IP address with color if suspicious."""
        if not obj.ip_address:
            return '-'
        
        # Check if this IP appears frequently (potential attack)
        from django.db.models import Count
        count = AuditLog.objects.filter(ip_address=obj.ip_address).count()
        
        if count > 100:
            color = '#dc3545'  # Red
        elif count > 50:
            color = '#ffc107'  # Yellow
        else:
            color = '#28a745'  # Green
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.ip_address
        )
    ip_address_display.short_description = 'IP Address'
    
    def old_values_display(self, obj):
        """Pretty display of old values."""
        import json
        if not obj.old_values:
            return '-'
        return format_html(
            '<pre style="background: #f5f5f5; padding: 10px; border-radius: 3px;">{}</pre>',
            json.dumps(obj.old_values, indent=2, ensure_ascii=False)
        )
    old_values_display.short_description = 'Previous Values'
    
    def new_values_display(self, obj):
        """Pretty display of new values."""
        import json
        if not obj.new_values:
            return '-'
        return format_html(
            '<pre style="background: #f5f5f5; padding: 10px; border-radius: 3px;">{}</pre>',
            json.dumps(obj.new_values, indent=2, ensure_ascii=False)
        )
    new_values_display.short_description = 'New Values'


@admin.register(AuditLogSummary)
class AuditLogSummaryAdmin(admin.ModelAdmin):
    """Admin interface for audit summary."""
    list_display = (
        'date', 'total_actions', 'creates', 'updates',
        'deletes', 'logins', 'unique_users'
    )
    list_filter = ('date',)
    ordering = ['-date']
    readonly_fields = (
        'date', 'total_actions', 'creates', 'updates',
        'deletes', 'logins', 'unique_users'
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return request.method in ('GET', 'HEAD', 'OPTIONS')
