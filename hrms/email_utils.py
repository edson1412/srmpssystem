from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import date, timedelta
from .models import LeaveRequest
import logging

logger = logging.getLogger(__name__)

def send_leave_approval_email(leave_request):
    """
    Send email notification to officer when leave request is approved.
    
    Args:
        leave_request (LeaveRequest): The approved leave request instance
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        officer = leave_request.officer
        
        # Check if officer has email
        if not officer.email:
            logger.warning(f"Officer {officer.full_name} has no email address configured")
            return False
            
        subject = f"Leave Request Approved - {leave_request.leave_type.name}"
        
        context = {
            'officer': officer,
            'leave_request': leave_request,
            'start_date': leave_request.start_date.strftime('%d %B %Y'),
            'end_date': leave_request.end_date.strftime('%d %B %Y') if leave_request.end_date else 'N/A',
            'number_of_days': leave_request.number_of_days,
            'leave_type': leave_request.leave_type.name,
            'approved_date': leave_request.approved_at.strftime('%d %B %Y') if leave_request.approved_at else date.today().strftime('%d %B %Y'),
        }
        
        message = render_to_string('hrms/emails/leave_approval_email.txt', context)
        html_message = render_to_string('hrms/emails/leave_approval_email.html', context)
        
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [officer.email]
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Leave approval email sent to {officer.email} for {officer.full_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send leave approval email to {officer.email}: {str(e)}")
        return False


def send_leave_reminder_email():
    """
    Send reminder emails to officers whose leave ends in 3 days.
    This function is intended to be called by a scheduled task (e.g., cron job).
    
    Returns:
        dict: Dictionary with counts of successful and failed email sends
    """
    today = timezone.now().date()
    reminder_date = today + timedelta(days=3)
    
    # Find approved leave requests that end in 3 days
    upcoming_leaves = LeaveRequest.objects.filter(
        status='approved',
        end_date=reminder_date
    ).select_related('officer', 'leave_type')
    
    success_count = 0
    failure_count = 0
    
    for leave_request in upcoming_leaves:
        officer = leave_request.officer
        
        # Check if officer has email
        if not officer.email:
            logger.warning(f"Officer {officer.full_name} has no email address configured for reminder")
            failure_count += 1
            continue
            
        try:
            subject = f"Leave Ending Reminder - Return to Duty on {leave_request.end_date.strftime('%d %B %Y')}"
            
            context = {
                'officer': officer,
                'leave_request': leave_request,
                'end_date': leave_request.end_date.strftime('%d %B %Y'),
                'leave_type': leave_request.leave_type.name,
                'days_remaining': 3,
                'return_date': (leave_request.end_date + timedelta(days=1)).strftime('%d %B %Y'),
            }
            
            message = render_to_string('hrms/emails/leave_reminder_email.txt', context)
            html_message = render_to_string('hrms/emails/leave_reminder_email.html', context)
            
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [officer.email]
            
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Leave reminder email sent to {officer.email} for {officer.full_name}")
            success_count += 1
            
        except Exception as e:
            logger.error(f"Failed to send leave reminder email to {officer.email}: {str(e)}")
            failure_count += 1
    
    return {
        'success_count': success_count,
        'failure_count': failure_count,
        'total_processed': success_count + failure_count
    }


def send_leave_rejection_email(leave_request):
    """
    Send email notification to officer when leave request is rejected.
    
    Args:
        leave_request (LeaveRequest): The rejected leave request instance
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        officer = leave_request.officer
        
        # Check if officer has email
        if not officer.email:
            logger.warning(f"Officer {officer.full_name} has no email address configured")
            return False
            
        subject = f"Leave Request Rejected - {leave_request.leave_type.name}"
        
        context = {
            'officer': officer,
            'leave_request': leave_request,
            'leave_type': leave_request.leave_type.name,
            'rejection_notes': leave_request.rejection_notes,
            'rejected_date': leave_request.approved_at.strftime('%d %B %Y') if leave_request.approved_at else date.today().strftime('%d %B %Y'),
        }
        
        message = render_to_string('hrms/emails/leave_rejection_email.txt', context)
        html_message = render_to_string('hrms/emails/leave_rejection_email.html', context)
        
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [officer.email]
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Leave rejection email sent to {officer.email} for {officer.full_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send leave rejection email to {officer.email}: {str(e)}")
        return False
