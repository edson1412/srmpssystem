"""
Django signals for automatic audit logging.
Captures all changes to critical models automatically.
"""
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from accounts.models import CustomUser
from prison.models import PrisonStation, Region
from hrms.models import (
    Officer, Attendance, AttendanceSummary, Rank, OfficeAssignment,
    DisciplinaryCase, Recruit, LeaveType, LeaveRequest, AnnualLeaveBalance,
    OfficerDocument, OfficerPerformance, PromotionHistory, TransferHistory,
    TrainingIntake, TrainingCourse, CourseEnrollment, GraduationBatch,
    AttendancePattern, Notification
)
from audit.models import AuditLog
from audit.utils import get_current_request, serialize_audit_data


# Models to track (all critical models)
TRACKED_MODELS = (
    Officer, CustomUser, Attendance, AttendanceSummary,
    Rank, OfficeAssignment, DisciplinaryCase, Recruit, LeaveType,
    LeaveRequest, AnnualLeaveBalance, OfficerDocument, OfficerPerformance,
    PromotionHistory, TransferHistory, TrainingIntake, TrainingCourse,
    CourseEnrollment, GraduationBatch, AttendancePattern, Notification,
    Region, PrisonStation
)


def get_field_value(obj, field_name):
    """Safely get field value, handling relationships and special types."""
    try:
        field = obj._meta.get_field(field_name)
        value = getattr(obj, field_name)
        
        # Handle foreign key references
        if field.many_to_one or field.one_to_one:
            return str(value) if value else None
        # Handle date/datetime fields
        elif hasattr(value, 'isoformat'):
            return value.isoformat()
        else:
            return str(value) if value is not None else None
    except Exception as e:
        return None


def get_model_changes(instance, excluded_fields=None):
    """
    Compare original vs current values to detect changes.
    Returns dict of {field_name: (old_value, new_value)}
    """
    if excluded_fields is None:
        excluded_fields = {'created_at', 'updated_at', 'password', 'last_login'}
    
    changes = {}
    
    if not hasattr(instance, '_state') or not hasattr(instance._state, 'adding'):
        return changes
    
    # Get all fields
    for field in instance._meta.get_fields():
        # Skip excluded fields and many-to-many
        if field.name in excluded_fields or field.many_to_many:
            continue
        
        try:
            current_value = getattr(instance, field.name)
            
            # Handle foreign key references
            if hasattr(field, 'many_to_one') and field.many_to_one:
                current_value = str(current_value) if current_value else None
            elif hasattr(current_value, 'isoformat'):
                current_value = current_value.isoformat()
            else:
                current_value = str(current_value) if current_value is not None else None
            
            # Get original value if it exists
            if hasattr(instance, '_original_' + field.name):
                original_value = getattr(instance, '_original_' + field.name)
                if hasattr(original_value, 'isoformat'):
                    original_value = original_value.isoformat()
                else:
                    original_value = str(original_value) if original_value is not None else None
                
                if original_value != current_value:
                    changes[field.name] = (original_value, current_value)
        except Exception:
            pass
    
    return changes


def extract_audit_fields(instance, excluded_fields=None):
    """Extract all relevant fields from a model instance."""
    if excluded_fields is None:
        excluded_fields = {'created_at', 'updated_at', 'password', 'last_login'}
    
    data = {}
    for field in instance._meta.get_fields():
        if field.name in excluded_fields or field.many_to_many or field.one_to_many:
            continue
        
        try:
            value = getattr(instance, field.name)
            
            # Handle foreign keys
            if hasattr(field, 'many_to_one') and field.many_to_one:
                data[field.name] = {
                    'value': str(value) if value else None,
                    'id': value.pk if value else None
                }
            else:
                data[field.name] = serialize_audit_data(value)
        except Exception:
            pass
    
    return data


@receiver(pre_save, dispatch_uid="audit_pre_save")
def audit_pre_save(sender, instance, **kwargs):
    """Capture the original state before save."""
    # Only track if it's one of our monitored models
    if sender not in TRACKED_MODELS:
        return
    
    # Store original values before update
    if instance.pk:  # Only if it's an update
        try:
            original = sender.objects.get(pk=instance.pk)
            for field in sender._meta.get_fields():
                if not field.many_to_many and not field.one_to_many:
                    try:
                        original_value = getattr(original, field.name)
                        setattr(instance, '_original_' + field.name, original_value)
                    except Exception:
                        pass
        except sender.DoesNotExist:
            pass


@receiver(post_save, dispatch_uid="audit_post_save")
def audit_post_save(sender, instance, created, **kwargs):
    """Log create and update actions."""
    # Only track if it's one of our monitored models
    if sender not in TRACKED_MODELS:
        return
    
    # Skip if already created an audit log in this request
    if hasattr(instance, '_audit_logged'):
        return
    
    action = 'CREATE' if created else 'UPDATE'
    user = None
    
    # Try to get the user from the instance
    if hasattr(instance, 'user'):
        user = instance.user
    elif hasattr(instance, 'created_by'):
        user = instance.created_by
    elif hasattr(instance, 'marked_by'):
        user = instance.marked_by
    
    # Extract field changes for updates
    changed_fields = []
    old_values = {}
    new_values = {}
    
    if not created:
        # For updates, track what changed
        try:
            original = sender.objects.get(pk=instance.pk)
            excluded = {'created_at', 'updated_at', 'password', 'last_login'}
            
            for field in sender._meta.get_fields():
                if field.name in excluded or field.many_to_many:
                    continue
                
                try:
                    old_val = getattr(original, field.name)
                    new_val = getattr(instance, field.name)
                    
                    # Handle foreign keys
                    if hasattr(field, 'many_to_one') and field.many_to_one:
                        old_val = str(old_val) if old_val else None
                        new_val = str(new_val) if new_val else None
                    else:
                        old_val = serialize_audit_data(old_val)
                        new_val = serialize_audit_data(new_val)
                    
                    if old_val != new_val:
                        changed_fields.append(field.name)
                        old_values[field.name] = old_val
                        new_values[field.name] = new_val
                except Exception:
                    pass
        except sender.DoesNotExist:
            new_values = extract_audit_fields(instance)
    else:
        # For creates, log all values
        new_values = extract_audit_fields(instance)
    
    # Only log if there are actual changes or if it's a create
    if created or changed_fields:
        AuditLog.log_action(
            action=action,
            user=user,
            content_object=instance,
            old_values=serialize_audit_data(old_values),
            new_values=serialize_audit_data(new_values),
            changed_fields=changed_fields,
            request=get_current_request(),
            description=f"{action} {sender.__name__}: {instance}"
        )
        
        instance._audit_logged = True


@receiver(pre_delete, dispatch_uid="audit_pre_delete")
def audit_pre_delete(sender, instance, **kwargs):
    """Log delete actions."""
    # Only track if it's one of our monitored models
    if sender not in TRACKED_MODELS:
        return
    
    user = None
    
    # Try to get the user from the instance
    if hasattr(instance, 'user'):
        user = instance.user
    elif hasattr(instance, 'created_by'):
        user = instance.created_by
    
    # Capture current values
    old_values = extract_audit_fields(instance)
    
    AuditLog.log_action(
        action='DELETE',
        user=user,
        content_object=instance,
        old_values=serialize_audit_data(old_values),
        new_values={},
        request=get_current_request(),
        description=f"DELETED {sender.__name__}: {instance}"
    )
