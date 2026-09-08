"""
Audit trail service for tracking all system actions.
"""
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count
from .models import AuditTrail, PrisonerAuditHistory, ReleaseAuditLog, SentryAlert

User = get_user_model()


class AuditService:
    """Service for creating audit trails and detecting anomalies"""

    @staticmethod
    def log_action(user, action, model_name, object_id=None, object_repr="",
                   changes=None, old_values=None, new_values=None,
                   request=None, severity='info', description="",
                   prison_station=None):
        """
        Create an audit trail entry

        Args:
            user: The user performing the action
            action: The action being performed (CREATE, UPDATE, DELETE, etc.)
            model_name: The name of the model being acted upon
            object_id: The ID of the object being acted upon
            object_repr: String representation of the object
            changes: Dictionary of changes made
            old_values: Dictionary of old values
            new_values: Dictionary of new values
            request: The HTTP request object for metadata
            severity: Severity level (info, warning, critical)
            description: Human-readable description of the action
            prison_station: The prison station context
        """
        # Get request metadata
        ip_address = None
        user_agent = ""
        request_path = ""
        session_id = ""

        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')

            user_agent = request.META.get('HTTP_USER_AGENT', '')
            request_path = request.path
            session_id = request.session.session_key or ""

        # Create audit trail
        audit = AuditTrail.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=str(object_id) if object_id else "",
            object_repr=object_repr,
            changes=changes or {},
            old_values=old_values or {},
            new_values=new_values or {},
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=timezone.now(),
            severity=severity,
            prison_station=prison_station,
            description=description,
            request_path=request_path,
            session_id=session_id,
        )

        # Check for sensitive actions
        if action in ['DATE_CHANGE', 'SENTENCE_CHANGE', 'RELEASE', 'DELETE', 'PERMISSION_CHANGE']:
            AuditService._check_for_anomalies(audit)

        return audit

    @staticmethod
    def log_prisoner_change(prisoner, user, field_name, old_value, new_value,
                            request=None, change_reason=""):
        """
        Log a specific field change on a prisoner

        Args:
            prisoner: The prisoner being changed
            user: The user making the change
            field_name: The name of the field being changed
            old_value: The old value
            new_value: The new value
            request: The HTTP request object
            change_reason: Reason for the change
        """
        # Get IP
        ip_address = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')

        # Create prisoner audit history
        history = PrisonerAuditHistory.objects.create(
            prisoner=prisoner,
            changed_by=user,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else "",
            new_value=str(new_value) if new_value is not None else "",
            change_reason=change_reason,
            ip_address=ip_address,
        )

        # Also create general audit trail
        AuditService.log_action(
            user=user,
            action='UPDATE',
            model_name='Prisoner',
            object_id=prisoner.id,
            object_repr=f"{prisoner.prisoner_number} - {prisoner.full_name}",
            changes={field_name: {'old': str(old_value) if old_value is not None else 'None',
                                  'new': str(new_value) if new_value is not None else 'None'}},
            old_values={field_name: str(old_value) if old_value is not None else 'None'},
            new_values={field_name: str(new_value) if new_value is not None else 'None'},
            request=request,
            severity='warning',
            description=f"Field '{field_name}' changed on prisoner {prisoner.prisoner_number}: {change_reason}"
        )

        # Check for sensitive changes
        if field_name in ['date_of_release', 'date_of_release_on_remission', 'sentence', 'offense']:
            AuditService._check_sensitive_change(prisoner, field_name, old_value, new_value, user)

        return history

    @staticmethod
    def log_release_action(prisoner, action, performed_by, request=None,
                           original_release_date=None, modified_release_date=None,
                           original_sentence=None, modified_sentence=None,
                           review_role="", approval_status="", change_reason=""):
        """
        Log release-related actions

        Args:
            prisoner: The prisoner being released
            action: The action (APPROVE, REJECT, FORWARD, RELEASE, SENTENCE_CHANGE)
            performed_by: The user performing the action
            request: The HTTP request object
            original_release_date: Original release date before change
            modified_release_date: Modified release date after change
            original_sentence: Original sentence before change
            modified_sentence: Modified sentence after change
            review_role: The role of the reviewer
            approval_status: The approval status
            change_reason: Reason for the change
        """
        # Get IP
        ip_address = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')

        # Create release audit log
        release_log = ReleaseAuditLog.objects.create(
            prisoner=prisoner,
            action=action,
            performed_by=performed_by,
            original_release_date=original_release_date,
            modified_release_date=modified_release_date,
            original_sentence=original_sentence,
            modified_sentence=modified_sentence,
            review_role=review_role,
            approval_status=approval_status,
            change_reason=change_reason,
            ip_address=ip_address,
        )

        # Determine severity based on action
        severity = 'info'
        if action in ['APPROVE', 'RELEASE']:
            severity = 'critical'
        elif action in ['REJECT', 'SENTENCE_CHANGE']:
            severity = 'warning'
        elif action in ['FORWARD']:
            severity = 'info'

        # Also create general audit trail
        changes = {}
        if original_release_date or modified_release_date:
            changes['release_date'] = {
                'old': str(original_release_date) if original_release_date else None,
                'new': str(modified_release_date) if modified_release_date else None
            }
        if original_sentence or modified_sentence:
            changes['sentence'] = {
                'old': original_sentence,
                'new': modified_sentence
            }

        AuditService.log_action(
            user=performed_by,
            action=action,
            model_name='Release',
            object_id=prisoner.id,
            object_repr=f"{prisoner.prisoner_number} - {prisoner.full_name}",
            changes=changes,
            request=request,
            severity=severity,
            description=f"Release action '{action}' for prisoner {prisoner.prisoner_number}: {change_reason}"
        )

        # Check for release anomalies
        AuditService._check_release_anomaly(prisoner, action, original_release_date, modified_release_date, performed_by)

        return release_log

    @staticmethod
    def log_security_event(alert_type, severity, title, description,
                           prisoner=None, user=None, ip_address=None,
                           audit_trail=None, request=None):
        """
        Log a security event / sentry alert

        Args:
            alert_type: The type of alert
            severity: Severity level
            title: Alert title
            description: Alert description
            prisoner: Related prisoner (optional)
            user: Related user (optional)
            ip_address: IP address (optional)
            audit_trail: Related audit trail (optional)
            request: HTTP request (optional)
        """
        # Get IP from request if not provided
        if request and not ip_address:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')

        # Check if similar alert already exists (prevent duplicates)
        existing_alert = SentryAlert.objects.filter(
            alert_type=alert_type,
            is_resolved=False,
            user=user,
            prisoner=prisoner,
            detected_at__gte=timezone.now() - timedelta(minutes=30)
        ).first()

        if existing_alert:
            # Update existing alert with new count
            existing_alert.title = f"{title} (x{existing_alert.detected_at_count + 1})"
            existing_alert.description = description
            existing_alert.save()
            return existing_alert

        # Create new alert
        alert = SentryAlert.objects.create(
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            prisoner=prisoner,
            user=user,
            ip_address=ip_address,
            audit_trail=audit_trail,
        )
        return alert

    @staticmethod
    def _check_for_anomalies(audit):
        """Check audit trail for suspicious patterns"""

        # Skip if no user
        if not audit.user:
            return

        # Check for multiple changes in short period
        recent_changes = AuditTrail.objects.filter(
            user=audit.user,
            object_id=audit.object_id,
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).count()

        if recent_changes > 5:
            AuditService.log_security_event(
                alert_type='multiple_changes',
                severity='high',
                title=f"Multiple Changes by {audit.user.username}",
                description=f"User {audit.user.username} made {recent_changes} changes in the last hour. Object: {audit.object_repr}",
                user=audit.user,
                ip_address=audit.ip_address,
                audit_trail=audit,
            )

        # Check for off-hours access (between 10 PM and 6 AM)
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 22:
            AuditService.log_security_event(
                alert_type='off_hours_access',
                severity='medium',
                title=f"Off-hours Access by {audit.user.username}",
                description=f"User {audit.user.username} performed {audit.action} at {timezone.now().strftime('%H:%M')}",
                user=audit.user,
                ip_address=audit.ip_address,
                audit_trail=audit,
            )

        # Check for foreign IP addresses (non-local)
        if audit.ip_address and not audit.ip_address.startswith(('127.', '192.168.', '10.')):
            # Check if the IP is from a known foreign country (simplified check)
            AuditService.log_security_event(
                alert_type='foreign_ip',
                severity='medium',
                title=f"Foreign IP Access by {audit.user.username}",
                description=f"User {audit.user.username} accessed from IP {audit.ip_address}",
                user=audit.user,
                ip_address=audit.ip_address,
                audit_trail=audit,
            )

    @staticmethod
    def _check_sensitive_change(prisoner, field_name, old_value, new_value, user):
        """Check for sensitive changes that might indicate corruption"""

        # Check if release date was moved EARLIER significantly
        if field_name in ['date_of_release', 'date_of_release_on_remission']:
            if old_value and new_value:
                try:
                    # Handle both string and date objects
                    old_date = None
                    new_date = None

                    if isinstance(old_value, (datetime, date)):
                        old_date = old_value
                    elif isinstance(old_value, str):
                        old_date = datetime.strptime(str(old_value)[:10], '%Y-%m-%d').date()

                    if isinstance(new_value, (datetime, date)):
                        new_date = new_value
                    elif isinstance(new_value, str):
                        new_date = datetime.strptime(str(new_value)[:10], '%Y-%m-%d').date()

                    if old_date and new_date:
                        days_earlier = (old_date - new_date).days
                        if days_earlier > 30:
                            AuditService.log_security_event(
                                alert_type='early_release',
                                severity='critical',
                                title=f"Early Release Detected - {prisoner.prisoner_number}",
                                description=f"Release date moved earlier by {days_earlier} days. Old: {old_date}, New: {new_date}",
                                prisoner=prisoner,
                                user=user,
                            )
                        elif days_earlier > 7:
                            AuditService.log_security_event(
                                alert_type='date_manipulation',
                                severity='high',
                                title=f"Release Date Change - {prisoner.prisoner_number}",
                                description=f"Release date moved earlier by {days_earlier} days. Old: {old_date}, New: {new_date}",
                                prisoner=prisoner,
                                user=user,
                            )
                except (ValueError, TypeError):
                    pass

        # Check if sentence was reduced significantly
        if field_name == 'sentence':
            if old_value and new_value:
                try:
                    old_sentence = float(old_value)
                    new_sentence = float(new_value)
                    reduction = old_sentence - new_sentence

                    if reduction > 12:  # More than 12 months reduction
                        AuditService.log_security_event(
                            alert_type='sentence_reduction',
                            severity='high',
                            title=f"Large Sentence Reduction - {prisoner.prisoner_number}",
                            description=f"Sentence reduced by {reduction} months. Old: {old_sentence}, New: {new_sentence}",
                            prisoner=prisoner,
                            user=user,
                        )
                    elif reduction > 6:
                        AuditService.log_security_event(
                            alert_type='sentence_reduction',
                            severity='medium',
                            title=f"Sentence Reduction - {prisoner.prisoner_number}",
                            description=f"Sentence reduced by {reduction} months. Old: {old_sentence}, New: {new_sentence}",
                            prisoner=prisoner,
                            user=user,
                        )
                except (ValueError, TypeError):
                    pass

        # Check for offense change
        if field_name == 'offense':
            if old_value and new_value and old_value != new_value:
                AuditService.log_security_event(
                    alert_type='date_manipulation',
                    severity='warning',
                    title=f"Offense Changed - {prisoner.prisoner_number}",
                    description=f"Offense changed from '{old_value}' to '{new_value}'",
                    prisoner=prisoner,
                    user=user,
                )

    @staticmethod
    def _check_release_anomaly(prisoner, action, original_date, modified_date, user):
        """Check release actions for anomalies"""

        if action in ['APPROVE', 'RELEASE']:
            # Check if release date is significantly earlier than expected
            if original_date and modified_date:
                try:
                    days_earlier = (original_date - modified_date).days
                    if days_earlier > 30:
                        AuditService.log_security_event(
                            alert_type='date_manipulation',
                            severity='critical',
                            title=f"Release Date Manipulation Detected - {prisoner.prisoner_number}",
                            description=f"Release date moved earlier by {days_earlier} days. Original: {original_date}, Modified: {modified_date}",
                            prisoner=prisoner,
                            user=user,
                        )
                    elif days_earlier > 7:
                        AuditService.log_security_event(
                            alert_type='date_manipulation',
                            severity='high',
                            title=f"Release Date Modified - {prisoner.prisoner_number}",
                            description=f"Release date moved earlier by {days_earlier} days. Original: {original_date}, Modified: {modified_date}",
                            prisoner=prisoner,
                            user=user,
                        )
                except (ValueError, TypeError):
                    pass


class SecurityMonitoringService:
    """Service for monitoring security events"""

    @staticmethod
    def get_user_activity_report(user, days=30):
        """Generate activity report for a specific user"""
        start_date = timezone.now() - timedelta(days=days)

        activities = AuditTrail.objects.filter(
            user=user,
            timestamp__gte=start_date
        ).order_by('-timestamp')

        return {
            'user': user,
            'total_actions': activities.count(),
            'by_action': activities.values('action').annotate(count=Count('id')),
            'sensitive_actions': activities.filter(
                action__in=['DATE_CHANGE', 'SENTENCE_CHANGE', 'RELEASE', 'DELETE', 'PERMISSION_CHANGE']
            ).count(),
            'recent_activities': activities[:50],
            'period_days': days,
        }

    @staticmethod
    def get_prisoner_audit_report(prisoner):
        """Generate comprehensive audit report for a prisoner"""
        changes = PrisonerAuditHistory.objects.filter(
            prisoner=prisoner
        ).order_by('-changed_at')

        release_logs = ReleaseAuditLog.objects.filter(
            prisoner=prisoner
        ).order_by('-performed_at')

        alerts = SentryAlert.objects.filter(
            prisoner=prisoner
        ).order_by('-detected_at')

        return {
            'prisoner': prisoner,
            'total_changes': changes.count(),
            'sensitive_changes': changes.filter(
                field_name__in=['date_of_release', 'date_of_release_on_remission', 'sentence', 'offense']
            ).count(),
            'changes': changes,
            'release_logs': release_logs,
            'sentry_alerts': alerts,
            'total_alerts': alerts.count(),
            'active_alerts': alerts.filter(is_resolved=False).count(),
        }

    @staticmethod
    def get_suspicious_activities(days=7):
        """Get suspicious activities from the last N days"""
        start_date = timezone.now() - timedelta(days=days)

        alerts = SentryAlert.objects.filter(
            detected_at__gte=start_date,
            is_resolved=False
        ).order_by('-detected_at')

        return alerts

    @staticmethod
    def generate_audit_summary():
        """Generate summary of audit activities"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        return {
            'total_actions_today': AuditTrail.objects.filter(
                timestamp__date=today
            ).count(),
            'critical_actions_today': AuditTrail.objects.filter(
                timestamp__date=today,
                severity='critical'
            ).count(),
            'total_actions_week': AuditTrail.objects.filter(
                timestamp__date__gte=week_ago
            ).count(),
            'active_alerts': SentryAlert.objects.filter(is_resolved=False).count(),
            'critical_alerts': SentryAlert.objects.filter(is_resolved=False, severity='critical').count(),
            'recent_alerts': SentryAlert.objects.filter(is_resolved=False).order_by('-detected_at')[:10],
            'most_active_users': AuditTrail.objects.filter(
                timestamp__date__gte=week_ago
            ).values('user__username').annotate(
                count=Count('id')
            ).order_by('-count')[:5],
            'most_common_actions': AuditTrail.objects.filter(
                timestamp__date__gte=week_ago
            ).values('action').annotate(
                count=Count('id')
            ).order_by('-count')[:5],
        }

    @staticmethod
    def get_audit_trail_export(start_date=None, end_date=None, user=None, action=None, severity=None):
        """Get audit trail entries for export"""
        queryset = AuditTrail.objects.all().select_related('user').order_by('-timestamp')

        if start_date:
            queryset = queryset.filter(timestamp__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__date__lte=end_date)
        if user:
            queryset = queryset.filter(user=user)
        if action:
            queryset = queryset.filter(action=action)
        if severity:
            queryset = queryset.filter(severity=severity)

        return queryset

    @staticmethod
    def get_alert_statistics():
        """Get statistics about alerts"""
        total_alerts = SentryAlert.objects.count()
        active_alerts = SentryAlert.objects.filter(is_resolved=False).count()
        resolved_alerts = SentryAlert.objects.filter(is_resolved=True).count()

        return {
            'total': total_alerts,
            'active': active_alerts,
            'resolved': resolved_alerts,
            'by_severity': SentryAlert.objects.values('severity').annotate(
                count=Count('id')
            ).order_by('severity'),
            'by_type': SentryAlert.objects.values('alert_type').annotate(
                count=Count('id')
            ).order_by('-count')[:10],
            'recent_activity': SentryAlert.objects.filter(
                is_resolved=False,
                detected_at__gte=timezone.now() - timedelta(hours=24)
            ).count(),
        }