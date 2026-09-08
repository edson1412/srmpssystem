# prison/utils.py

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from prison.models import (
    Visitor, Notification, Prisoner, MedicalRecord,
    ConvictedPrisoner, PrisonerReleaseReview, AuditTrail
)

# Get the custom user model
User = get_user_model()


def _prisoner_action_url(prisoner):
    """Return the canonical detail URL used by prisoner notifications."""
    return reverse('prisoner_detail', args=[prisoner.id])


def log_activity(user, action, model, object_id, details):
    """Log activity to console (for development)"""
    print(f"LOG: {user} {action} {model} {object_id} - {details}")


def _get_notification_target_users(role=None):
    """Get users by role for notifications"""
    if role:
        return User.objects.filter(role=role, is_active=True)
    return User.objects.filter(is_active=True)


def _get_all_relevant_users():
    """Get all users that should receive notifications"""
    return User.objects.filter(
        role__in=[
            'reception', 'officer_in_charge', 'station_officer',
            'admin', 'superuser', 'warden', 'medical', 'visitor_attendant',
            'ict_personnel'
        ],
        is_active=True
    )


def create_medical_checkup_notifications():
    """
    Create notifications for prisoners with upcoming medical checkups.
    Creates notifications for checkups due within the next 7 days.
    """
    today = timezone.now().date()
    next_week = today + timedelta(days=7)

    # Get medical records with checkups due in the next 7 days
    upcoming_checkups = MedicalRecord.objects.filter(
        next_checkup__gte=today,
        next_checkup__lte=next_week,
        prisoner__is_active=True
    ).select_related('prisoner').prefetch_related('prisoner__prison_station')

    notifications_created = 0

    for medical_record in upcoming_checkups:
        # Check if notification already exists for this checkup
        existing_notification = Notification.objects.filter(
            notification_type='medical_checkup',
            medical_record=medical_record,
            created_at__date=today
        ).exists()

        if not existing_notification:
            days_until = (medical_record.next_checkup - today).days
            urgency = 'urgent' if days_until <= 1 else 'high' if days_until <= 3 else 'medium'

            notification = Notification.objects.create(
                title=f"Medical Checkup Due - {medical_record.prisoner.full_name}",
                message=f"Prisoner {medical_record.prisoner.prisoner_number} ({medical_record.prisoner.full_name}) has a medical checkup due on {medical_record.next_checkup}. "
                       f"Diagnosis: {medical_record.diagnosis}. Days until checkup: {days_until}",
                notification_type='medical_checkup',
                priority=urgency,
                prisoner=medical_record.prisoner,
                medical_record=medical_record,
                action_required=True,
                action_url=f'/medical/{medical_record.id}/',
                due_date=medical_record.next_checkup,
                expires_at=medical_record.next_checkup + timedelta(days=1)
            )

            # Add medical staff and admin users
            medical_staff = _get_notification_target_users('medical')
            admin_users = _get_notification_target_users('admin')
            superusers = _get_notification_target_users('superuser')
            wardens = _get_notification_target_users('warden')
            notification.target_users.set(medical_staff | admin_users | superusers | wardens)

            notifications_created += 1

    return notifications_created


def create_near_release_notifications():
    """
    Create notifications for prisoners nearing release.
    Creates notifications for prisoners due to be released within the next 5 days.
    """
    today = timezone.now().date()
    release_window_end = today + timedelta(days=5)

    # Get convicted prisoners due for release within 5 days
    near_release_prisoners = ConvictedPrisoner.objects.filter(
        Q(date_of_release_on_remission__gte=today) & Q(date_of_release_on_remission__lte=release_window_end) |
        Q(date_of_release__gte=today) & Q(date_of_release__lte=release_window_end),
        prisoner__is_active=True
    ).select_related('prisoner').prefetch_related('prisoner__prison_station')

    notifications_created = 0

    for convicted in near_release_prisoners:
        # Check if notification already exists for this release
        release_date = convicted.date_of_release_on_remission or convicted.date_of_release
        existing_notification = Notification.objects.filter(
            notification_type='near_release',
            prisoner=convicted.prisoner,
            due_date=release_date,
            created_at__date=today
        ).exists()

        if not existing_notification:
            days_until = (release_date - today).days
            urgency = 'urgent' if days_until <= 1 else 'high' if days_until <= 3 else 'medium'

            notification = Notification.objects.create(
                title=f"Prisoner Near Release - {convicted.prisoner.full_name}",
                message=f"Prisoner {convicted.prisoner.prisoner_number} ({convicted.prisoner.full_name}) is due for release on {release_date}. "
                       f"Offense: {convicted.offense if convicted.offense else 'N/A'}. "
                       f"Days until release: {days_until}",
                notification_type='near_release',
                priority=urgency,
                prisoner=convicted.prisoner,
                action_required=True,
                action_url='/release-hub/',
                due_date=release_date,
                expires_at=release_date + timedelta(days=2)
            )

            # Target all relevant roles
            reception_users = _get_notification_target_users('reception')
            oc_users = _get_notification_target_users('officer_in_charge')
            station_officers = _get_notification_target_users('station_officer')
            admin_users = _get_notification_target_users('admin')
            superusers = _get_notification_target_users('superuser')
            notification.target_users.set(
                reception_users | oc_users | station_officers | admin_users | superusers
            )

            notifications_created += 1

    return notifications_created


def create_new_admission_notification(prisoner):
    """
    Create notification for newly admitted prisoner.
    """
    today = timezone.now().date()

    # Check if notification already exists for this admission
    existing_notification = Notification.objects.filter(
        notification_type='new_admission',
        prisoner=prisoner,
        created_at__date=today
    ).exists()

    if not existing_notification:
        notification = Notification.objects.create(
            title=f"New Prisoner Admission - {prisoner.full_name}",
            message=f"New prisoner {prisoner.prisoner_number} ({prisoner.full_name}) has been admitted to {prisoner.prison_station.name}. "
                   f"Class: {prisoner.get_prisoner_class_display()}. "
                   f"Block: {prisoner.block_number}, Cell: {prisoner.cell_number}. "
                   f"Admission Date: {prisoner.date_admitted}",
            notification_type='new_admission',
            priority='high',
            prisoner=prisoner,
            action_required=True,
            action_url=_prisoner_action_url(prisoner),
            due_date=prisoner.date_admitted + timedelta(days=3),
            expires_at=prisoner.date_admitted + timedelta(days=7)
        )

        # Target all relevant roles
        reception_users = _get_notification_target_users('reception')
        admin_users = _get_notification_target_users('admin')
        superusers = _get_notification_target_users('superuser')
        wardens = _get_notification_target_users('warden')
        notification.target_users.set(reception_users | admin_users | superusers | wardens)

        return notification

    return None


def create_release_review_notification(review):
    """
    Create notification when a prisoner is forwarded for release review.
    """
    notification = Notification.objects.create(
        title=f"Release Review Required - {review.prisoner.full_name}",
        message=f"Prisoner {review.prisoner.prisoner_number} ({review.prisoner.full_name}) has been forwarded for {review.get_review_role_display()} review. "
               f"Release Date: {review.release_date}. "
               f"Requested by: {review.requested_by.get_full_name() if review.requested_by else 'Unknown'}",
        notification_type='general',
        priority='high',
        prisoner=review.prisoner,
        action_required=True,
        action_url='/release-hub/',
        due_date=review.release_date,
        expires_at=review.release_date + timedelta(days=2)
    )

    # Target the appropriate reviewer AND all relevant roles
    if review.review_role == 'officer_in_charge':
        oc_users = _get_notification_target_users('officer_in_charge')
        admin_users = _get_notification_target_users('admin')
        superusers = _get_notification_target_users('superuser')
        station_officers = _get_notification_target_users('station_officer')
        notification.target_users.set(oc_users | admin_users | superusers | station_officers)
    elif review.review_role == 'station_officer':
        station_officers = _get_notification_target_users('station_officer')
        admin_users = _get_notification_target_users('admin')
        superusers = _get_notification_target_users('superuser')
        oc_users = _get_notification_target_users('officer_in_charge')
        notification.target_users.set(station_officers | admin_users | superusers | oc_users)

    return notification


def create_release_approved_notification(review):
    """
    Create notification when a release is approved.
    """
    notification = Notification.objects.create(
        title=f"Release Approved - {review.prisoner.full_name}",
        message=f"Release for prisoner {review.prisoner.prisoner_number} ({review.prisoner.full_name}) has been APPROVED by {review.reviewed_by.get_full_name() if review.reviewed_by else 'Unknown'}. "
               f"Release Date: {review.release_date}. "
               f"The prisoner will be released on this date.",
        notification_type='general',
        priority='urgent',
        prisoner=review.prisoner,
        action_required=True,
        action_url='/release-hub/',
        due_date=review.release_date,
        expires_at=review.release_date + timedelta(days=1)
    )

    # Target all relevant roles
    reception_users = _get_notification_target_users('reception')
    admin_users = _get_notification_target_users('admin')
    superusers = _get_notification_target_users('superuser')
    oc_users = _get_notification_target_users('officer_in_charge')
    station_officers = _get_notification_target_users('station_officer')
    notification.target_users.set(
        reception_users | admin_users | superusers | oc_users | station_officers
    )

    return notification


def create_release_rejected_notification(review):
    """
    Create notification when a release is rejected.
    """
    notification = Notification.objects.create(
        title=f"Release Rejected - {review.prisoner.full_name}",
        message=f"Release for prisoner {review.prisoner.prisoner_number} ({review.prisoner.full_name}) has been REJECTED by {review.reviewed_by.get_full_name() if review.reviewed_by else 'Unknown'}.",
        notification_type='general',
        priority='high',
        prisoner=review.prisoner,
        action_required=True,
        action_url='/release-hub/'
    )

    # Target all relevant roles
    reception_users = _get_notification_target_users('reception')
    admin_users = _get_notification_target_users('admin')
    superusers = _get_notification_target_users('superuser')
    oc_users = _get_notification_target_users('officer_in_charge')
    station_officers = _get_notification_target_users('station_officer')
    notification.target_users.set(
        reception_users | admin_users | superusers | oc_users | station_officers
    )

    return notification


def create_return_submission_notification(submission):
    """
    Create notification when a return is submitted.
    """
    notification = Notification.objects.create(
        title=f"Return Submitted - {submission.template.name}",
        message=f"Return {submission.template.name} has been submitted by {submission.prison_station.name}. "
               f"Period: {submission.period_display}. Records: {submission.row_count}.",
        notification_type='general',
        priority='medium',
        action_required=True,
        action_url='/returns/submissions/'
    )

    # Target admin, superuser, and ICT personnel
    admin_users = _get_notification_target_users('admin')
    superusers = _get_notification_target_users('superuser')
    ict_users = _get_notification_target_users('ict_personnel')
    notification.target_users.set(admin_users | superusers | ict_users)

    return notification


def create_return_approved_notification(submission):
    """
    Create notification when a return is approved.
    """
    notification = Notification.objects.create(
        title=f"Return Approved - {submission.template.name}",
        message=f"Return {submission.template.name} from {submission.prison_station.name} has been APPROVED. "
               f"Period: {submission.period_display}. Records: {submission.row_count}.",
        notification_type='general',
        priority='medium',
        action_required=False,
        action_url='/returns/submissions/'
    )

    # Target the station that submitted
    station_users = User.objects.filter(prison_station=submission.prison_station, is_active=True)
    notification.target_users.set(station_users)

    return notification


def create_return_rejected_notification(submission, reason=""):
    """
    Create notification when a return is rejected.
    """
    notification = Notification.objects.create(
        title=f"Return Rejected - {submission.template.name}",
        message=f"Return {submission.template.name} from {submission.prison_station.name} has been REJECTED. "
               f"Period: {submission.period_display}. Reason: {reason}",
        notification_type='general',
        priority='high',
        action_required=True,
        action_url='/returns/submissions/'
    )

    # Target the station that submitted
    station_users = User.objects.filter(prison_station=submission.prison_station, is_active=True)
    notification.target_users.set(station_users)

    return notification


def create_prisoner_transfer_notification(transfer):
    """
    Create notification when a prisoner is transferred.
    """
    notification = Notification.objects.create(
        title=f"Prisoner Transferred - {transfer.prisoner.full_name}",
        message=f"Prisoner {transfer.prisoner.prisoner_number} ({transfer.prisoner.full_name}) has been transferred from {transfer.from_prison.name} to {transfer.to_prison.name}. "
               f"Transfer Date: {transfer.transfer_date}.",
        notification_type='general',
        priority='medium',
        prisoner=transfer.prisoner,
        action_required=False,
        action_url=_prisoner_action_url(transfer.prisoner)
    )

    # Target both stations' users and relevant roles
    from_station_users = User.objects.filter(prison_station=transfer.from_prison, is_active=True)
    to_station_users = User.objects.filter(prison_station=transfer.to_prison, is_active=True)
    admin_users = _get_notification_target_users('admin')
    superusers = _get_notification_target_users('superuser')
    ict_users = _get_notification_target_users('ict_personnel')
    notification.target_users.set(
        from_station_users | to_station_users | admin_users | superusers | ict_users
    )

    return notification


def create_incident_report_notification(incident):
    """
    Create notification when an incident is reported.
    """
    notification = Notification.objects.create(
        title=f"Incident Reported - {incident.title}",
        message=f"Incident: {incident.title}. Severity: {incident.get_severity_display()}. "
               f"Location: {incident.location}. Reported by: {incident.reported_by.get_full_name() if incident.reported_by else 'Unknown'}.",
        notification_type='general',
        priority='urgent' if incident.severity in ['high', 'critical'] else 'high',
        action_required=True,
        action_url=f'/incidents/{incident.id}/'
    )

    # Target admin, superuser, warden, ICT
    admin_users = _get_notification_target_users('admin')
    superusers = _get_notification_target_users('superuser')
    wardens = _get_notification_target_users('warden')
    ict_users = _get_notification_target_users('ict_personnel')
    notification.target_users.set(admin_users | superusers | wardens | ict_users)

    return notification


def create_visitor_notification(visitor):
    """
    Create notification when a visitor request is created.
    """
    notification = Notification.objects.create(
        title=f"New Visitor Request - {visitor.full_name}",
        message=f"New visitor {visitor.full_name} has requested to visit {visitor.prisoner.full_name} on {visitor.visit_date}. "
               f"Relationship: {visitor.get_relationship_display()}.",
        notification_type='general',
        priority='medium',
        prisoner=visitor.prisoner,
        action_required=True,
        action_url='/visitors/'
    )

    # Target reception and visitor attendant
    reception_users = _get_notification_target_users('reception')
    visitor_attendants = _get_notification_target_users('visitor_attendant')
    notification.target_users.set(reception_users | visitor_attendants)

    return notification


def create_system_alert_notification(alert):
    """
    Create notification when a sentry alert is triggered.
    """
    notification = Notification.objects.create(
        title=f"Security Alert - {alert.get_alert_type_display()}",
        message=f"Alert: {alert.title}. Severity: {alert.get_severity_display()}. "
               f"Description: {alert.description}",
        notification_type='general',
        priority='urgent' if alert.severity == 'critical' else 'high',
        prisoner=alert.prisoner,
        action_required=True,
        action_url='/audit-trail/sentry-alerts/'
    )

    # Target ICT personnel, admin, superuser
    ict_users = _get_notification_target_users('ict_personnel')
    admin_users = _get_notification_target_users('admin')
    superusers = _get_notification_target_users('superuser')
    notification.target_users.set(ict_users | admin_users | superusers)

    return notification


def generate_all_notifications():
    """
    Generate all types of notifications.
    This function can be called periodically (e.g., via cron job or scheduled task).
    """
    medical_count = create_medical_checkup_notifications()
    release_count = create_near_release_notifications()

    return {
        'medical_checkup_notifications': medical_count,
        'near_release_notifications': release_count,
        'total': medical_count + release_count
    }