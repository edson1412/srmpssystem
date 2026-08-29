from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from prison.models import Visitor, Notification, Prisoner, MedicalRecord, ConvictedPrisoner

def log_activity(user, action, model, object_id, details):
    # Example logging logic (adjust to match your activity model)
    print(f"LOG: {user} {action} {model} {object_id} - {details}")


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
            
            # Add medical staff users (you can customize this based on your user roles)
            medical_staff = User.objects.filter(is_staff=True)  # Adjust based on your role system
            notification.target_users.set(medical_staff)
            
            notifications_created += 1
    
    return notifications_created


def create_near_release_notifications():
    """
    Create notifications for prisoners nearing release.
    Creates notifications for prisoners due to be released within the next 30 days.
    """
    today = timezone.now().date()
    next_month = today + timedelta(days=30)
    
    # Get convicted prisoners nearing release
    near_release_prisoners = ConvictedPrisoner.objects.filter(
        date_of_release__gte=today,
        date_of_release__lte=next_month,
        prisoner__is_active=True
    ).select_related('prisoner').prefetch_related('prisoner__prison_station')
    
    notifications_created = 0
    
    for convicted in near_release_prisoners:
        # Check if notification already exists for this release
        existing_notification = Notification.objects.filter(
            notification_type='near_release',
            prisoner=convicted.prisoner,
            due_date=convicted.date_of_release,
            created_at__date=today
        ).exists()
        
        if not existing_notification:
            days_until = (convicted.date_of_release - today).days
            urgency = 'urgent' if days_until <= 7 else 'high' if days_until <= 14 else 'medium'
            
            notification = Notification.objects.create(
                title=f"Prisoner Near Release - {convicted.prisoner.full_name}",
                message=f"Prisoner {convicted.prisoner.prisoner_number} ({convicted.prisoner.full_name}) is due for release on {convicted.date_of_release}. "
                       f"Offense: {convicted.offense if convicted.offense else 'N/A'}. "
                       f"Court: {convicted.court}. Days until release: {days_until}",
                notification_type='near_release',
                priority=urgency,
                prisoner=convicted.prisoner,
                action_required=True,
                action_url=f'/prisoner/{convicted.prisoner.id}/',
                due_date=convicted.date_of_release,
                expires_at=convicted.date_of_release + timedelta(days=7)
            )
            
            # Add administrative staff users
            admin_staff = User.objects.filter(is_staff=True)  # Adjust based on your role system
            notification.target_users.set(admin_staff)
            
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
            action_url=f'/prisoner/{prisoner.id}/',
            due_date=prisoner.date_admitted + timedelta(days=3),
            expires_at=prisoner.date_admitted + timedelta(days=7)
        )
        
        # Add administrative staff users
        admin_staff = User.objects.filter(is_staff=True)  # Adjust based on your role system
        notification.target_users.set(admin_staff)
        
        return notification
    
    return None


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