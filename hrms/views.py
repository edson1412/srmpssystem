# hrms/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum, F, Count, Avg, Max
from django.db.models.functions import ExtractYear, ExtractMonth
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from dateutil.relativedelta import relativedelta
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
import csv
import io
import pandas as pd
from django.core.files.uploadedfile import InMemoryUploadedFile
from datetime import datetime
from audit.models import AuditLog, AuditLogSummary


from .models import (
    Officer, Education, PromotionHistory, TransferHistory, LeaveType, LeaveRequest, OfficerDocument,
    OfficerPerformance, OfficeAssignment, Rank, Attendance, DisciplinaryCase, AnnualLeaveBalance,
    PerformanceMetric, Notification, TrainingIntake, TrainingCourse, Recruit, RecruitMark,
    GraduationBatch, AttendanceSummary
)
from .forms import (
    OfficerForm, EducationFormSet, PromotionHistoryForm, TransferHistoryForm,
    LeaveRequestForm, LeaveApprovalForm, OfficerDocumentForm, OfficerFileResponseForm,
    OfficerPerformanceForm, AttendanceForm, DisciplinaryCaseForm, OfficeAssignmentForm,
    TrainingCourseForm, TrainingIntakeForm,
    IntakeGraduationForm, RecruitForm, RecruitMarkForm
)
from accounts.models import CustomUser, Region, PrisonStation
from accounts.forms import RegionForm, PrisonStationForm
from .email_utils import send_leave_approval_email, send_leave_rejection_email


# --- System Error View ---

def system_error_view(request, error_message=None, error_code=None):
    """
    Display a system error page with contact information for administrators.
    """
    context = {
        'error_message': error_message,
        'error_code': error_code,
    }
    return render(request, 'system_error.html', context)


# --- Helper Functions for Permissions ---

def is_national_level(user):
    """Checks if the user has a national-level role."""
    return user.is_authenticated and user.role in ['national_commissioner', 'national_hr']

def is_regional_level(user):
    """Checks if the user has a regional-level role."""
    return user.is_authenticated and user.role in ['regional_commanding_officer', 'regional_headquarters_officer', 'regional_hr']

def is_station_level(user):
    """Checks if the user has a station-level role."""
    return user.is_authenticated and user.role in ['officer_in_charge', 'station_officer', 'station_hr']

def is_training_wing_officer(user):
    """Checks if the user has a training wing role."""
    return user.is_authenticated and user.role in ['training_wing_officer', 'commissioner_training_school']

def can_access_training(user):
    """Training school pages: training wing staff, national level and superusers."""
    return user.is_authenticated and (
        user.is_superuser or is_training_wing_officer(user) or is_national_level(user)
    )

def is_ict_personnel(user):
    """Checks if the user has ICT personnel role."""
    return user.is_authenticated and (user.is_superuser or user.role == 'ict_personnel')

def can_manage_officer_data(user, officer_station=None, officer_region=None):
    """
    Checks if the user has permission to manage officer data based on their role and assigned location.
    - National level: Can manage all officers.
    - Regional level: Can manage officers in their assigned region.
    - Station level: Can manage officers in their assigned station.
    - ICT Personnel: Can manage all officers and users.
    """
    if user.is_superuser or is_national_level(user) or is_ict_personnel(user):
        return True
    # For regional level, check if the user's region matches the officer's region
    if is_regional_level(user) and user.region and officer_region and user.region == officer_region:
        return True
    # For station level, check if the user's station matches the officer's station
    if is_station_level(user) and user.prison_station and officer_station and user.prison_station == officer_station:
        return True
    return False

def can_manage_regions(user):
    """
    Checks if the user has permission to manage regions (only national level, ICT personnel, or superuser).
    """
    return user.is_superuser or is_national_level(user) or is_ict_personnel(user)

def can_manage_prison_stations(user, station_region=None):
    """
    Checks if the user has permission to manage prison stations.
    - National level: Can manage all stations.
    - Regional level: Can manage stations within their assigned region.
    - ICT Personnel: Can manage all stations.
    """
    if user.is_superuser or is_national_level(user) or is_ict_personnel(user):
        return True
    if is_regional_level(user) and user.region and station_region and user.region == station_region:
        return True
    return False


def get_filtered_officers_queryset(user):
    """
    Returns a queryset of officers visible to the current user based on their role.
    """
    if user.is_superuser or is_national_level(user) or is_ict_personnel(user):
        return Officer.objects.all()
    elif is_regional_level(user) and user.region:
        # Regional users see all officers in their assigned region, across all stations in that region
        return Officer.objects.filter(region=user.region)
    elif is_station_level(user) and user.prison_station:
        return Officer.objects.filter(prison_station=user.prison_station)
    return Officer.objects.none() # No officers visible if no matching role/location

def get_recent_files_queryset(user):
    """
    Returns officer documents visible to the user ordered by recency.
    """
    if user.is_superuser or is_national_level(user) or is_ict_personnel(user):
        return OfficerDocument.objects.order_by('-uploaded_at')
    if is_regional_level(user) and user.region:
        return OfficerDocument.objects.filter(officer__region=user.region).order_by('-uploaded_at')
    if is_station_level(user) and user.prison_station:
        return OfficerDocument.objects.filter(officer__prison_station=user.prison_station).order_by('-uploaded_at')
    return OfficerDocument.objects.none()

def get_pending_leave_requests_queryset(user):
    """
    Returns pending leave requests visible to the user ordered by newest request first.
    """
    if user.is_superuser or is_national_level(user) or is_ict_personnel(user):
        return LeaveRequest.objects.filter(status='pending').order_by('-requested_at')
    if is_regional_level(user) and user.region:
        return LeaveRequest.objects.filter(
            status='pending',
            officer__region=user.region
        ).order_by('-requested_at')
    if is_station_level(user) and user.prison_station:
        return LeaveRequest.objects.filter(
            status='pending',
            officer__prison_station=user.prison_station
        ).order_by('-requested_at')
    return LeaveRequest.objects.none()

def get_retirement_alerts(officers_queryset, months_ahead, retirement_age=60):
    """
    Builds a list of officers approaching retirement within the provided window.
    Returns dictionaries friendly for templates and APIs.
    """
    today = date.today()
    cutoff_date = today + relativedelta(months=+months_ahead)
    alerts = []

    for officer in officers_queryset.exclude(date_of_birth__isnull=True):
        if not officer.date_of_birth:
            continue
        retirement_date = officer.date_of_birth + relativedelta(years=retirement_age)
        if today <= retirement_date <= cutoff_date:
            alerts.append({
                'full_name': officer.full_name,
                'service_number': officer.service_number,
                'station_name': officer.prison_station.name if officer.prison_station else 'Unassigned',
                'retirement_date': retirement_date,
                'detail_url': reverse('hrms:officer_detail', kwargs={'service_number': officer.service_number})
            })

    alerts.sort(key=lambda item: item['retirement_date'])
    return alerts

def sync_officer_leave_statuses():
    """
    Ensures officer.status reflects whether they are currently on an approved leave.
    - Officers with an active approved leave window move to 'on_leave'.
    - Officers whose approved leave window has passed move back to 'active'.
    """
    today = date.today()

    officers_with_current_leave_ids = list(
        Officer.objects.filter(
            leave_requests__status='approved',
            leave_requests__start_date__lte=today,
            leave_requests__end_date__gte=today,
            status='active'
        ).values_list('id', flat=True)
    )
    if officers_with_current_leave_ids:
        Officer.objects.filter(id__in=officers_with_current_leave_ids).update(status='on_leave')

    officers_ready_for_activation_ids = list(
        Officer.objects.filter(
            status='on_leave',
            leave_requests__status='approved',
            leave_requests__end_date__lt=today
        ).exclude(
            leave_requests__status='approved',
            leave_requests__start_date__lte=today,
            leave_requests__end_date__gte=today
        ).values_list('id', flat=True)
    )
    if officers_ready_for_activation_ids:
        Officer.objects.filter(id__in=officers_ready_for_activation_ids).update(status='active')


# --- Notification Helper Function ---
def create_notification(recipient, sender, message, notification_type, content_object=None):
    """
    Creates a new notification.
    recipient: The CustomUser who receives the notification.
    sender: The CustomUser who initiated the action (can be None for system alerts).
    message: The notification message.
    notification_type: One of the NOTIFICATION_TYPE_CHOICES from Notification model.
    content_object: The related Django model instance (e.g., LeaveRequest, OfficerDocument).
    """
    content_type = None
    object_id = None
    if content_object:
        content_type = ContentType.objects.get_for_model(content_object)
        object_id = content_object.pk

    Notification.objects.create(
        recipient=recipient,
        sender=sender,
        message=message,
        notification_type=notification_type,
        content_type=content_type,
        object_id=object_id
    )



# --- Dashboard View ---

@login_required
def dashboard_view(request):
    """
    Displays the HRMS dashboard with key metrics and recent activities
    filtered by the user's permissions.
    """
    sync_officer_leave_statuses()
    user = request.user
    officers_queryset = get_filtered_officers_queryset(user)

    # Use aggregate to get counts more efficiently
    total_officers = officers_queryset.count()
    status_counts = officers_queryset.values('status').annotate(count=Count('status'))
    active_officers = 0
    on_leave_officers = 0
    retired_officers = 0
    for item in status_counts:
        if item['status'] == 'active':
            active_officers = item['count']
        elif item['status'] == 'on_leave':
            on_leave_officers = item['count']
        elif item['status'] == 'retired':
            retired_officers = item['count']

    retirement_alerts_12 = get_retirement_alerts(officers_queryset, months_ahead=12)
    retirement_alerts_4 = get_retirement_alerts(officers_queryset, months_ahead=4)

    recent_files_queryset = get_recent_files_queryset(user)
    recent_files = recent_files_queryset[:5]
    recent_files_total = recent_files_queryset.count()

    pending_leave_queryset = get_pending_leave_requests_queryset(user)
    pending_leave_requests = pending_leave_queryset[:5]
    pending_leave_requests_total = pending_leave_queryset.count()

    def calculate_percentage(part):
        return round((part / total_officers) * 100, 2) if total_officers else 0

    active_percentage = calculate_percentage(active_officers)
    on_leave_percentage = calculate_percentage(on_leave_officers)
    retired_percentage = calculate_percentage(retired_officers)

    # Fetch unread notifications for the current user (for initial page load)
    unread_notifications = Notification.objects.filter(recipient=user, is_read=False).order_by('-created_at')[:5]

    context = {
        'total_officers': total_officers,
        'active_officers': active_officers,
        'on_leave_officers': on_leave_officers,
        'retired_officers': retired_officers,
        'status_distribution': {
            'active': active_officers,
            'on_leave': on_leave_officers,
            'retired': retired_officers,
        },
        'retirement_alerts_12': retirement_alerts_12,
        'retirement_alerts_4': retirement_alerts_4,
        'recent_files': recent_files,
        'recent_files_total': recent_files_total,
        'pending_leave_requests': pending_leave_requests,
        'pending_leave_requests_total': pending_leave_requests_total,
        'user_role': user.get_role_display(),
        'unread_notifications': unread_notifications,
        'user': user,
        'is_national_level': is_national_level(user),
        'is_regional_level': is_regional_level(user),
        'is_station_level': is_station_level(user),
        'is_ict_personnel': is_ict_personnel(user),
        'title': 'Dashboard',
        'last_refreshed': timezone.now(),
        'active_percentage': active_percentage,
        'on_leave_percentage': on_leave_percentage,
        'retired_percentage': retired_percentage,
        'initial_metrics': {
            'total_officers': total_officers,
            'active_officers': active_officers,
            'on_leave_officers': on_leave_officers,
            'retired_officers': retired_officers,
        }
    }

    return render(request, 'hrms/dashboard.html', context)


@login_required
@user_passes_test(is_ict_personnel)
def ict_dashboard_view(request):
    """ICT dashboard: user/officer counts plus audit trail metrics."""
    
    # User Management Stats
    total_users = CustomUser.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()
    
    # Officer Stats
    total_officers = Officer.objects.count()
    active_officers = Officer.objects.filter(status='active').count()
    on_leave_officers = Officer.objects.filter(status='on_leave').count()
    pending_leave_requests = LeaveRequest.objects.filter(status='pending').count()
    
    # Location Stats
    total_regions = Region.objects.count()
    total_stations = PrisonStation.objects.count()
    
    # User Role Distribution
    user_role_stats = CustomUser.objects.values('role').annotate(count=Count('id')).order_by('-count')
    
    # Recent Users (last 30 days)
    recent_users = CustomUser.objects.order_by('-date_joined')[:5]
    
    # Recent Files
    recent_files = OfficerDocument.objects.select_related('officer', 'uploaded_by').order_by('-uploaded_at')[:5]
    
    # AUDIT TRAIL STATS
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    # Audit summary counts
    total_audit_logs = AuditLog.objects.count()
    audit_logs_today = AuditLog.objects.filter(timestamp__date=today).count()
    audit_logs_week = AuditLog.objects.filter(timestamp__date__gte=last_7_days).count()
    audit_logs_month = AuditLog.objects.filter(timestamp__date__gte=last_30_days).count()
    
    # Action breakdown (last 30 days)
    action_breakdown = AuditLog.objects.filter(
        timestamp__date__gte=last_30_days
    ).values('action').annotate(count=Count('id')).order_by('-count')[:5]
    
    # Top active users (by audit events)
    top_audit_users = AuditLog.objects.filter(
        timestamp__date__gte=last_30_days
    ).values('user__username').annotate(
        count=Count('id')
    ).exclude(user__isnull=True).order_by('-count')[:5]
    
    # Most modified models
    top_models = AuditLog.objects.filter(
        timestamp__date__gte=last_30_days
    ).values('model_name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Suspicious activity detection (high frequency changes in last hour)
    one_hour_ago = timezone.now() - timedelta(hours=1)
    high_volume_activity = AuditLog.objects.filter(
        timestamp__gte=one_hour_ago
    ).values('user__username').annotate(
        count=Count('id')
    ).filter(count__gt=20)
    
    # Recent audit logs (last 10 for display)
    recent_audit_logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:10]
    
    # Daily audit trend (last 7 days for chart)
    audit_trend = []
    for i in range(7):
        date = today - timedelta(days=i)
        count = AuditLog.objects.filter(timestamp__date=date).count()
        audit_trend.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    context = {
        # Existing stats
        'total_users': total_users,
        'active_users': active_users,
        'total_officers': total_officers,
        'active_officers': active_officers,
        'on_leave_officers': on_leave_officers,
        'pending_leave_requests': pending_leave_requests,
        'total_regions': total_regions,
        'total_stations': total_stations,
        'user_role_stats': user_role_stats,
        'recent_users': recent_users,
        'recent_files': recent_files,
        
        # Audit Trail Stats
        'total_audit_logs': total_audit_logs,
        'audit_logs_today': audit_logs_today,
        'audit_logs_week': audit_logs_week,
        'audit_logs_month': audit_logs_month,
        'action_breakdown': action_breakdown,
        'top_audit_users': top_audit_users,
        'top_models': top_models,
        'high_volume_activity': high_volume_activity,
        'recent_audit_logs': recent_audit_logs,
        'audit_trend': audit_trend,
    }
    
    return render(request, 'hrms/ict_dashboard.html', context)


@login_required
def dashboard_data_api_view(request):
    """
    Lightweight JSON endpoint consumed by the dashboard front-end for live updates.
    """
    sync_officer_leave_statuses()
    user = request.user
    officers_queryset = get_filtered_officers_queryset(user)

    total_officers = officers_queryset.count()
    status_counts = officers_queryset.values('status').annotate(count=Count('status'))
    status_map = {'active': 0, 'on_leave': 0, 'retired': 0}
    for item in status_counts:
        status_map[item['status']] = item['count']

    retirement_alerts_4 = get_retirement_alerts(officers_queryset, months_ahead=4)
    retirement_alerts_12 = get_retirement_alerts(officers_queryset, months_ahead=12)

    recent_files = get_recent_files_queryset(user)[:5]
    pending_leaves = get_pending_leave_requests_queryset(user)[:5]
    unread_notifications = Notification.objects.filter(recipient=user, is_read=False).order_by('-created_at')[:5]

    data = {
        'timestamp': timezone.now().isoformat(),
        'metrics': {
            'total_officers': total_officers,
            'active_officers': status_map['active'],
            'on_leave_officers': status_map['on_leave'],
            'retired_officers': status_map['retired'],
        },
        'retirement_alerts': {
            'next_four_months': [
                {
                    'full_name': alert['full_name'],
                    'service_number': alert['service_number'],
                    'station_name': alert['station_name'],
                    'retirement_date': alert['retirement_date'].isoformat(),
                    'detail_url': alert['detail_url'],
                } for alert in retirement_alerts_4
            ],
            'next_twelve_months': [
                {
                    'full_name': alert['full_name'],
                    'service_number': alert['service_number'],
                    'station_name': alert['station_name'],
                    'retirement_date': alert['retirement_date'].isoformat(),
                    'detail_url': alert['detail_url'],
                } for alert in retirement_alerts_12
            ],
        },
        'recent_files': [
            {
                'file_name': officer_file.file_name,
                'uploader': officer_file.officer.full_name if officer_file.officer else 'Unknown Officer',
                'uploaded_at': officer_file.uploaded_at.isoformat() if officer_file.uploaded_at else None,
                'status_display': officer_file.get_status_display(),
                'status': officer_file.status,
                'detail_url': reverse('hrms:officer_file_detail', kwargs={'pk': officer_file.pk})
            } for officer_file in recent_files
        ],
        'pending_leave_requests': [
            {
                'officer_name': leave.officer.full_name if leave.officer else 'Unknown Officer',
                'leave_type': leave.leave_type.name if leave.leave_type else 'N/A',
                'start_date': leave.start_date.isoformat() if leave.start_date else None,
                'end_date': leave.end_date.isoformat() if leave.end_date else None,
                'requested_at': leave.requested_at.isoformat() if leave.requested_at else None,
                'detail_url': reverse('hrms:leave_request_detail', kwargs={'pk': leave.pk})
            } for leave in pending_leaves
        ],
        'notifications': [
            {
                'message': notification.message,
                'created_at': notification.created_at.isoformat() if notification.created_at else None,
                'sender': notification.sender.get_full_name() if notification.sender else 'System',
                'detail_url': notification.get_absolute_url()
            } for notification in unread_notifications
        ]
    }

    return JsonResponse(data)

# --- Officer Management Views ---

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def officer_list_view(request):
    """
    Displays a list of all officers with filtering options.
    """
    sync_officer_leave_statuses()
    # Get all available filter options to pass to the template
    ranks = Rank.objects.all().order_by('name')
    stations = PrisonStation.objects.all().order_by('name')
    regions = Region.objects.all().order_by('name')

    # Start from the officers this user is allowed to see (region/station scoped)
    officers = get_filtered_officers_queryset(request.user)

    if is_regional_level(request.user) and request.user.region:
        stations = stations.filter(region=request.user.region)
        regions = regions.filter(pk=request.user.region.pk)
    elif is_station_level(request.user) and request.user.prison_station:
        stations = stations.filter(pk=request.user.prison_station.pk)
        regions = regions.filter(pk=request.user.prison_station.region_id)

    # Get filter parameters from the request
    current_rank_filter = request.GET.get('rank', 'all')
    current_station_filter = request.GET.get('station', 'all')
    current_region_filter = request.GET.get('region', 'all')
    current_status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')

    # Apply filters based on request parameters
    filter_kwargs = {}
    if current_rank_filter and current_rank_filter != 'all':
        filter_kwargs['rank__name'] = current_rank_filter

    if current_station_filter and current_station_filter != 'all':
        filter_kwargs['prison_station__name'] = current_station_filter

    if current_status_filter and current_status_filter != 'all':
        filter_kwargs['status'] = current_status_filter

    # Apply the regional filter only for national level users
    if is_national_level(request.user) and current_region_filter and current_region_filter != 'all':
        filter_kwargs['region__name'] = current_region_filter

    # Filter the queryset
    if filter_kwargs:
        officers = officers.filter(**filter_kwargs)

    # Apply search query
    if search_query:
        officers = officers.filter(
            Q(service_number__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(surname__icontains=search_query) |
            Q(rank__name__icontains=search_query)
        )

    context = {
        'title': 'Officers',
        'officers': officers,
        'ranks': ranks,
        'stations': stations,
        'regions': regions,
        'current_rank_filter': current_rank_filter,
        'current_station_filter': current_station_filter,
        'current_region_filter': current_region_filter,
        'current_status_filter': current_status_filter,
        'search_query': search_query,
        'is_national_level_user': is_national_level(request.user)
    }
    return render(request, 'hrms/officer_list.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def officer_create_view(request):
    """
    Allows authorized users to add new officer records.
    Station HR can only add officers to their station.
    Regional HR can only add officers to stations within their region.
    National HR/Commissioner can add officers to any station/region.
    """
    user = request.user
    if not (user.is_superuser or is_national_level(user) or is_regional_level(user) or is_station_level(user)):
        messages.error(request, "You do not have permission to add officers.")
        return redirect('hrms:dashboard')

    if request.method == 'POST':
        officer_form = OfficerForm(request.POST, request.FILES, user=user)
        education_formset = EducationFormSet(request.POST, request.FILES, prefix='education')

        if officer_form.is_valid() and education_formset.is_valid():
            officer = officer_form.save(commit=False)

            # Enforce location constraints based on user role
            if is_station_level(user) and user.prison_station:
                officer.prison_station = user.prison_station
                officer.region = officer.prison_station.region # Ensure region is set from station
            elif is_regional_level(user) and user.region:
                # If a regional user, ensure the selected region for the officer matches their own
                if officer.region and officer.region != user.region: # Check if officer.region is set before comparing
                    messages.error(request, "You can only add officers to stations within your assigned region.")
                    return render(request, 'hrms/officer_form.html', {
                        'officer_form': officer_form,
                        'education_formset': education_formset,
                        'title': 'Add New Officer'
                    })
                # Ensure the selected prison_station is within the user's region
                if officer.prison_station and officer.prison_station.region != user.region:
                     messages.error(request, "The selected prison station is not within your assigned region.")
                     return render(request, 'hrms/officer_form.html', {
                        'officer_form': officer_form,
                        'education_formset': education_formset,
                        'title': 'Add New Officer'
                    })

            officer.save()

            education_formset.instance = officer
            education_formset.save()

            messages.success(request, f"Officer {officer.full_name} added successfully.")

            # Create notification for relevant users (e.g., National HR, Regional HR)
            hr_users = CustomUser.objects.filter(
                Q(is_superuser=True) |
                Q(role='national_commissioner') | # National Commissioner
                Q(role='national_hr') |           # National HR
                Q(role='regional_commanding_officer', region=officer.region) | # RCO in officer's region
                Q(role='regional_headquarters_officer', region=officer.region) | # RHO in officer's region
                Q(role='regional_hr', region=officer.region) # Regional HR in officer's region
            ).distinct()
            for hr_user in hr_users:
                if hr_user != user: # Don't notify the user who just created the officer
                    create_notification(
                        recipient=hr_user,
                        sender=user,
                        message=f"New officer {officer.full_name} ({officer.service_number}) added to {officer.prison_station.name if officer.prison_station else 'an unassigned station'} in {officer.region.name if officer.region else 'an unassigned region'}.",
                        notification_type='new_officer',
                        content_object=officer
                    )

            return redirect('hrms:officer_detail', service_number=officer.service_number)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        officer_form = OfficerForm(user=user)
        education_formset = EducationFormSet(prefix='education')

    context = {
        'officer_form': officer_form,
        'education_formset': education_formset,
        'title': 'Add New Officer'
    }
    return render(request, 'hrms/officer_form.html', context)

@login_required
def officer_detail_view(request, service_number):
    """
    Displays detailed information about a single officer.
    Permissions:
    - National level: View all.
    - Regional level: View officers in their region.
    - Station level: View officers in their station.
    """
    officer = get_object_or_404(Officer.objects.select_related('rank', 'prison_station', 'region', 'current_office_assignment'), service_number=service_number)
    user = request.user

    # Check permission to view this officer
    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to view this officer's details.")
        return redirect('hrms:dashboard')

    # Fetching limited records for display on detail page
    education_qualifications = officer.education.all().order_by('-year_obtained')[:5]
    promotion_history = officer.promotions.all().order_by('-promotion_date')[:5]
    transfer_history = officer.transfers.all().order_by('-transfer_date')[:5]
    leave_requests = officer.leave_requests.all().order_by('-requested_at')[:5]
    officer_documents = officer.documents.all().order_by('-uploaded_at')[:5]
    performance_records = officer.performance_records.all().order_by('-date')[:5]
    attendance_records = officer.attendance_records.all().order_by('-date')[:5]
    disciplinary_cases = officer.disciplinary_cases.all().order_by('-case_date')[:5]


    # Calculate current annual leave balance
    annual_leave_balance_obj = AnnualLeaveBalance.objects.filter(officer=officer, year=date.today().year).first()
    annual_leave_balance = annual_leave_balance_obj.remaining_days if annual_leave_balance_obj else 0
    total_entitled_days = annual_leave_balance_obj.total_days_entitled if annual_leave_balance_obj else 0

    # Check for forfeited leave (if previous year's annual leave wasn't fully taken)
    previous_year_start = date(date.today().year - 1, 4, 1) # Assuming leave year starts April 1st

    previous_year_balance_obj = AnnualLeaveBalance.objects.filter(officer=officer, year=previous_year_start.year).first()
    forfeited_leave = 0
    if previous_year_balance_obj:
        forfeited_leave = max(0, previous_year_balance_obj.total_days_entitled - previous_year_balance_obj.days_taken)


    context = {
        'officer': officer,
        'education_qualifications': education_qualifications,
        'promotion_history': promotion_history,
        'transfer_history': transfer_history,
        'leave_requests': leave_requests,
        'officer_documents': officer_documents,
        'performance_records': performance_records,
        'attendance_records': attendance_records,
        'disciplinary_cases': disciplinary_cases,
        'annual_leave_balance': annual_leave_balance,
        'total_entitled_days': total_entitled_days,
        'forfeited_leave': forfeited_leave,
    }
    return render(request, 'hrms/officer_detail.html', context)

@login_required
def officer_update_view(request, service_number):
    """
    Allows authorized users to update existing officer records.
    Permissions are checked by `can_manage_officer_data`.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to edit this officer's details.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        officer_form = OfficerForm(request.POST, request.FILES, instance=officer, user=user)
        education_formset = EducationFormSet(request.POST, request.FILES, prefix='education', instance=officer) # Pass instance to formset

        if officer_form.is_valid() and education_formset.is_valid():
            officer = officer_form.save(commit=False)

            # Enforce location constraints based on user role (similar to create view)
            if is_station_level(user) and user.prison_station:
                officer.prison_station = user.prison_station
                officer.region = officer.prison_station.region # Ensure region is set from station
            elif is_regional_level(user) and user.region:
                if officer.region and officer.region != user.region: # Check if officer.region is set before comparing
                    messages.error(request, "You can only update officers within your assigned region.")
                    return render(request, 'hrms/officer_form.html', {
                        'officer_form': officer_form,
                        'education_formset': education_formset,
                        'title': f'Edit Officer: {officer.service_number}'
                    })
                if officer.prison_station and officer.prison_station.region != user.region:
                     messages.error(request, "The selected prison station is not within your assigned region.")
                     return render(request, 'hrms/officer_form.html', {
                        'officer_form': officer_form,
                        'education_formset': education_formset,
                        'title': f'Edit Officer: {officer.service_number}'
                    })

            officer.save()
            education_formset.instance = officer
            education_formset.save()

            messages.success(request, f"Officer {officer.full_name} updated successfully.")
            return redirect('hrms:officer_detail', service_number=officer.service_number)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        officer_form = OfficerForm(instance=officer, user=user)
        education_formset = EducationFormSet(instance=officer, prefix='education')

    context = {
        'officer_form': officer_form,
        'education_formset': education_formset,
        'title': f'Edit Officer: {officer.full_name}'
    }
    return render(request, 'hrms/officer_form.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u))
def officer_delete_view(request, service_number):
    """
    Deletes an officer record. Restricted to national/superuser.
    Regional users can delete officers in their region.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to delete this officer.")
        return redirect('hrms:officer_detail', service_number=service_number)

    if request.method == 'POST':
        officer_full_name = officer.full_name
        officer.delete()
        messages.success(request, f"Officer {officer_full_name} deleted successfully.")
        return redirect('hrms:officer_list')

    context = {
        'officer': officer
    }
    return render(request, 'hrms/officer_confirm_delete.html', context)

# --- Service History Views (Promotions & Transfers) ---

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def service_history_create_view(request, service_number):
    """
    Allows adding new promotion or transfer history for an officer.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to add service history for this officer.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    promotion_form = PromotionHistoryForm(prefix='promotion')
    transfer_form = TransferHistoryForm(prefix='transfer')

    if request.method == 'POST':
        if 'promotion_submit' in request.POST:
            promotion_form = PromotionHistoryForm(request.POST, prefix='promotion')
            if promotion_form.is_valid():
                promotion = promotion_form.save(commit=False)
                promotion.officer = officer
                promotion.recorded_by = user
                promotion.save()
                # Update officer's current rank if promoted
                officer.rank = promotion.new_rank
                officer.save()
                messages.success(request, "Promotion history added successfully.")

                # Create notification for the officer
                if officer.user:
                    create_notification(
                        recipient=officer.user,
                        sender=user,
                        message=f"Congratulations! You have been promoted to {promotion.new_rank.get_name_display()} on {promotion.promotion_date.strftime('%Y-%m-%d')}.",
                        notification_type='promotion',
                        content_object=promotion
                    )
                # Also notify relevant HR (e.g., National HR, Regional HR)
                hr_users = CustomUser.objects.filter(
                    Q(is_superuser=True) |
                    Q(role='national_commissioner') |
                    Q(role='national_hr') |
                    Q(role='regional_commanding_officer', region=officer.region) |
                    Q(role='regional_headquarters_officer', region=officer.region) |
                    Q(role='regional_hr', region=officer.region)
                ).distinct()
                for hr_user in hr_users:
                    if hr_user != user:
                        create_notification(
                            recipient=hr_user,
                            sender=user,
                            message=f"Officer {officer.full_name} promoted to {promotion.new_rank.get_name_display()}.",
                            notification_type='promotion',
                            content_object=promotion
                        )


                return redirect('hrms:officer_detail', service_number=officer.service_number)
            else:
                messages.error(request, "Error adding promotion history. Please correct the errors.")
        elif 'transfer_submit' in request.POST:
            transfer_form = TransferHistoryForm(request.POST, prefix='transfer')
            if transfer_form.is_valid():
                transfer = transfer_form.save(commit=False)
                transfer.officer = officer
                transfer.recorded_by = user
                transfer.save()
                # Update officer's current prison station and region if transferred
                officer.prison_station = transfer.new_station
                officer.region = transfer.new_station.region
                officer.save()
                messages.success(request, "Transfer history added successfully.")

                # Create notification for the officer
                if officer.user:
                    create_notification(
                        recipient=officer.user,
                        sender=user,
                        message=f"You have been transferred to {transfer.new_station.name} on {transfer.transfer_date.strftime('%Y-%m-%d')}.",
                        notification_type='transfer',
                        content_object=transfer
                    )
                # Also notify relevant HR
                hr_users = CustomUser.objects.filter(
                    Q(is_superuser=True) |
                    Q(role='national_commissioner') |
                    Q(role='national_hr') |
                    Q(role='regional_commanding_officer', region=officer.region) |
                    Q(role='regional_headquarters_officer', region=officer.region) |
                    Q(role='regional_hr', region=officer.region)
                ).distinct()
                for hr_user in hr_users:
                    if hr_user != user:
                        create_notification(
                            recipient=hr_user,
                            sender=user,
                            message=f"Officer {officer.full_name} transferred to {transfer.new_station.name}.",
                            notification_type='transfer',
                            content_object=transfer
                        )

                return redirect('hrms:officer_detail', service_number=officer.service_number)
            else:
                messages.error(request, "Error adding transfer history. Please correct the errors.")

    context = {
        'officer': officer,
        'promotion_form': promotion_form,
        'transfer_form': transfer_form,
        'title': f'Add Service History for {officer.full_name}'
    }
    return render(request, 'hrms/service_history_form.html', context)

@login_required
def service_history_list_view(request):
    """
    Lists promotion and transfer records relevant to the user's role.
    Can be filtered by officer service_number and type (promotion/transfer).
    """
    user = request.user
    officer_service_number = request.GET.get('officer_service_number')
    history_type = request.GET.get('type') # 'promotion' or 'transfer'

    officer_filter = None
    if officer_service_number:
        officer_filter = get_object_or_404(Officer, service_number=officer_service_number)

    promotions = PromotionHistory.objects.none()
    transfers = TransferHistory.objects.none()

    if history_type == 'promotion' or not history_type:
        promotions = PromotionHistory.objects.all().select_related('officer', 'previous_rank', 'new_rank', 'recorded_by')
        if officer_filter:
            promotions = promotions.filter(officer=officer_filter)
        if is_station_level(user) and user.prison_station:
            promotions = promotions.filter(officer__prison_station=user.prison_station)
        elif is_regional_level(user) and user.region:
            promotions = promotions.filter(officer__region=user.region)
        promotions = promotions.order_by('-promotion_date')

    if history_type == 'transfer' or not history_type:
        transfers = TransferHistory.objects.all().select_related('officer', 'previous_station', 'new_station', 'recorded_by')
        if officer_filter:
            transfers = transfers.filter(officer=officer_filter)
        if is_station_level(user) and user.prison_station:
            transfers = transfers.filter(officer__prison_station=user.prison_station)
        elif is_regional_level(user) and user.region:
            transfers = transfers.filter(officer__region=user.region)
        transfers = transfers.order_by('-transfer_date')

    title = "Service History"
    if officer_filter:
        title = f"Service History for {officer_filter.full_name}"
    if history_type == 'promotion':
        title = f"Promotion History for {officer_filter.full_name if officer_filter else 'All Officers'}"
    elif history_type == 'transfer':
        title = f"Transfer History for {officer_filter.full_name if officer_filter else 'All Officers'}"


    context = {
        'promotions': promotions,
        'transfers': transfers,
        'officer_filter': officer_filter,
        'history_type': history_type,
        'title': title,
    }
    return render(request, 'hrms/service_history_list.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def service_history_update_view(request, pk):
    """
    Allows updating an existing promotion or transfer history record.
    """
    promotion_history = PromotionHistory.objects.filter(pk=pk).first()
    transfer_history = TransferHistory.objects.filter(pk=pk).first()

    if promotion_history:
        instance = promotion_history
        form_class = PromotionHistoryForm
        history_type = 'Promotion'
        officer = instance.officer
    elif transfer_history:
        instance = transfer_history
        form_class = TransferHistoryForm
        history_type = 'Transfer'
        officer = instance.officer
    else:
        messages.error(request, "Service history record not found.")
        return redirect('hrms:dashboard')

    user = request.user
    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to edit this service history record.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"{history_type} history updated successfully.")
            return redirect('hrms:officer_detail', service_number=officer.service_number)
        else:
            messages.error(request, f"Error updating {history_type} history. Please correct the errors.")
    else:
        form = form_class(instance=instance)

    context = {
        'form': form,
        'officer': officer,
        'history_type': history_type,
        'title': f'Edit {history_type} History for {officer.full_name}'
    }
    return render(request, 'hrms/service_history_form.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u))
def service_history_delete_view(request, pk):
    """
    Allows deleting a promotion or transfer history record.
    """
    promotion_history = PromotionHistory.objects.filter(pk=pk).first()
    transfer_history = TransferHistory.objects.filter(pk=pk).first()

    if promotion_history:
        instance = promotion_history
        history_type = 'Promotion'
        officer = instance.officer
    elif transfer_history:
        instance = transfer_history
        history_type = 'Transfer'
        officer = instance.officer
    else:
        messages.error(request, "Service history record not found.")
        return redirect('hrms:dashboard')

    user = request.user
    if not (is_national_level(user) or user.is_superuser):
        messages.error(request, "You do not have permission to delete service history records.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        instance.delete()
        messages.success(request, f"{history_type} history deleted successfully.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    context = {
        'officer': officer,
        'history_type': history_type,
        'instance': instance,
    }
    return render(request, 'hrms/service_history_confirm_delete.html', context)

# --- Leave Requests Views ---

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def leave_request_create_view(request, service_number):
    """
    Allows an officer or HR to request leave for an officer.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to request leave for this officer.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, request.FILES)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.officer = officer
            leave_request.save()
            messages.success(request, "Leave request submitted successfully.")

            # Notify relevant HR users about the new leave request
            hr_users_to_notify = CustomUser.objects.filter(
                Q(is_superuser=True) |
                Q(role='national_commissioner') |
                Q(role='national_hr') |
                Q(role='regional_commanding_officer', region=officer.region) |
                Q(role='regional_headquarters_officer', region=officer.region) |
                Q(role='regional_hr', region=officer.region) |
                Q(role='officer_in_charge', prison_station=officer.prison_station) |
                Q(role='station_hr', prison_station=officer.prison_station)
            ).distinct()

            for hr_user in hr_users_to_notify:
                if hr_user != user:
                    create_notification(
                        recipient=hr_user,
                        sender=user,
                        message=f"New leave request from {officer.full_name} for {leave_request.leave_type.name} ({leave_request.start_date.strftime('%Y-%m-%d')}).",
                        notification_type='leave_request',
                        content_object=leave_request
                    )

            return redirect('hrms:leave_request_detail', pk=leave_request.pk)
        else:
            messages.error(request, "Error submitting leave request. Please correct the errors.")
    else:
        form = LeaveRequestForm()

    context = {
        'form': form,
        'officer': officer,
        'title': f'Request Leave for {officer.full_name}'
    }
    return render(request, 'hrms/leave_request_form.html', context)

@login_required
def leave_request_list_view(request):
    """
    Lists leave requests relevant to the user's role.
    Can be filtered by officer service_number.
    """
    user = request.user
    leave_requests = LeaveRequest.objects.all().select_related('officer', 'leave_type')

    if is_station_level(user) and user.prison_station:
        leave_requests = leave_requests.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        leave_requests = leave_requests.filter(officer__region=user.region)
    # National level/superuser sees all

    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        leave_requests = leave_requests.filter(status=status_filter)

    officer_service_number = request.GET.get('officer_service_number')
    officer_filter = None
    if officer_service_number:
        officer_filter = get_object_or_404(Officer, service_number=officer_service_number)
        leave_requests = leave_requests.filter(officer=officer_filter)

    context = {
        'leave_requests': leave_requests.order_by('-requested_at'),
        'title': 'Leave Requests',
        'current_status_filter': status_filter,
        'officer_filter': officer_filter,
    }
    return render(request, 'hrms/leave_request_list.html', context)

@login_required
def leave_request_detail_view(request, pk):
    """
    Displays details of a single leave request.
    """
    leave_request = get_object_or_404(LeaveRequest.objects.select_related('officer', 'leave_type', 'approved_by'), pk=pk)
    user = request.user

    if not can_manage_officer_data(user, leave_request.officer.prison_station, leave_request.officer.region):
        messages.error(request, "You do not have permission to view this leave request.")
        return redirect('hrms:leave_request_list')

    context = {
        'leave_request': leave_request,
        'title': f'Leave Request: {leave_request.officer.full_name} ({leave_request.leave_type.name})'
    }
    return render(request, 'hrms/leave_request_detail.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def leave_request_approve_view(request, pk):
    """
    Allows authorized users to approve a leave request.
    """
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    user = request.user

    if not can_manage_officer_data(user, leave_request.officer.prison_station, leave_request.officer.region):
        messages.error(request, "You do not have permission to approve this leave request.")
        return redirect('hrms:leave_request_detail', pk=pk)

    if leave_request.status != 'pending':
        messages.warning(request, "This leave request has already been processed.")
        return redirect('hrms:leave_request_detail', pk=pk)

    if request.method == 'POST':
        form = LeaveApprovalForm(request.POST, instance=leave_request)
        if form.is_valid():
            leave_request.status = 'approved'
            leave_request.approved_by = user
            leave_request.approved_at = timezone.now()
            leave_request.save()

            if leave_request.start_date <= date.today() <= leave_request.end_date:
                officer = leave_request.officer
                officer.status = 'on_leave'
                officer.save()

            if leave_request.leave_type.name == 'Annual Leave':
                current_year = date.today().year
                annual_balance, created = AnnualLeaveBalance.objects.get_or_create(
                    officer=leave_request.officer,
                    year=current_year,
                    defaults={'total_days_entitled': leave_request.officer.rank.leave_days_annual if leave_request.officer.rank else 0}
                )
                annual_balance.days_taken += leave_request.number_of_days
                annual_balance.save()

            messages.success(request, "Leave request approved successfully.")

            # Send email notification to officer
            try:
                email_sent = send_leave_approval_email(leave_request)
                if email_sent:
                    messages.info(request, "Email notification sent to the officer.")
                else:
                    messages.warning(request, "Leave approved but email notification could not be sent. Officer may not have a valid email address.")
            except Exception as e:
                messages.warning(request, f"Leave approved but there was an issue sending email notification: {str(e)}")

            if leave_request.officer.user:
                create_notification(
                    recipient=leave_request.officer.user,
                    sender=user,
                    message=f"Your leave request for {leave_request.leave_type.name} from {leave_request.start_date.strftime('%Y-%m-%d')} has been APPROVED.",
                    notification_type='leave_request',
                    content_object=leave_request
                )

            return redirect('hrms:leave_request_detail', pk=pk)
        else:
            messages.error(request, "Error approving leave request. Please correct the errors.")
    else:
        form = LeaveApprovalForm(instance=leave_request)

    context = {
        'form': form,
        'leave_request': leave_request,
        'title': f'Approve Leave for {leave_request.officer.full_name}'
    }
    return render(request, 'hrms/leave_approval_form.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def leave_request_reject_view(request, pk):
    """
    Allows authorized users to reject a leave request.
    """
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    user = request.user

    if not can_manage_officer_data(user, leave_request.officer.prison_station, leave_request.officer.region):
        messages.error(request, "You do not have permission to reject this leave request.")
        return redirect('hrms:leave_request_detail', pk=pk)

    if leave_request.status != 'pending':
        messages.warning(request, "This leave request has already been processed.")
        return redirect('hrms:leave_request_detail', pk=pk)

    if request.method == 'POST':
        form = LeaveApprovalForm(request.POST, instance=leave_request)
        if form.is_valid():
            leave_request.status = 'rejected'
            leave_request.approved_by = user
            leave_request.approved_at = timezone.now()
            leave_request.save()
            messages.success(request, "Leave request rejected successfully.")

            # Send email notification to officer
            try:
                email_sent = send_leave_rejection_email(leave_request)
                if email_sent:
                    messages.info(request, "Email notification sent to the officer.")
                else:
                    messages.warning(request, "Leave rejected but email notification could not be sent. Officer may not have a valid email address.")
            except Exception as e:
                messages.warning(request, f"Leave rejected but there was an issue sending email notification: {str(e)}")

            if leave_request.officer.user:
                create_notification(
                    recipient=leave_request.officer.user,
                    sender=user,
                    message=f"Your leave request for {leave_request.leave_type.name} from {leave_request.start_date.strftime('%Y-%m-%d')} has been REJECTED. Reason: {leave_request.rejection_notes or 'N/A'}",
                    notification_type='leave_request',
                    content_object=leave_request
                )

            return redirect('hrms:leave_request_detail', pk=pk)
        else:
            messages.error(request, "Error rejecting leave request. Please provide rejection notes.")
    else:
        form = LeaveApprovalForm(instance=leave_request)

    context = {
        'form': form,
        'leave_request': leave_request,
        'title': f'Reject Leave for {leave_request.officer.full_name}'
    }
    return render(request, 'hrms/leave_approval_form.html', context)

# --- Officer Files Views ---

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def officer_file_upload_view(request, service_number):
    """
    Allows uploading a new file for an officer.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to upload files for this officer.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        form = OfficerDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            officer_file = form.save(commit=False)
            officer_file.officer = officer
            officer_file.uploaded_by = user

            # Determine the specific user to whom the action is directed
            action_to_role = officer_file.action_to
            action_recipient_user = None

            if action_to_role:
                # Start with a base queryset for CustomUser
                recipient_qs = CustomUser.objects.all()

                # Filter by role
                recipient_qs = recipient_qs.filter(role=action_to_role)

                # Apply regional filtering if the role is regional
                if action_to_role in ['regional_commanding_officer', 'regional_headquarters_officer', 'regional_hr']:
                    if officer.region:
                        recipient_qs = recipient_qs.filter(region=officer.region)
                    else:
                        messages.warning(request, f"Cannot send notification to {action_to_role} as officer's region is not set.")
                        action_recipient_user = None # No specific recipient found
                # Apply station filtering if the role is station-level
                elif action_to_role in ['officer_in_charge', 'station_officer', 'station_hr']:
                    if officer.prison_station:
                        recipient_qs = recipient_qs.filter(prison_station=officer.prison_station)
                    else:
                        messages.warning(request, f"Cannot send notification to {action_to_role} as officer's prison station is not set.")
                        action_recipient_user = None # No specific recipient found

                # Try to get one recipient. If multiple, pick the first one, or handle as needed.
                action_recipient_user = recipient_qs.first()

            officer_file.action_to_user = action_recipient_user # Assign the determined user object
            officer_file.save()
            messages.success(request, "File uploaded successfully.")

            # Notify the officer who the document is about
            if officer.user:
                create_notification(
                    recipient=officer.user,
                    sender=user,
                    message=f"A new document '{officer_file.file_name}' has been uploaded to your file.",
                    notification_type='file_action',
                    content_object=officer_file
                )

            # Notify the specific user/role for whom action is required
            if officer_file.action_to_user and officer_file.action_to_user != user: # Ensure not notifying self if action_to_user is the uploader
                create_notification(
                    recipient=officer_file.action_to_user,
                    sender=user,
                    message=f"Action required: New document '{officer_file.file_name}' for {officer.full_name} needs your review.",
                    notification_type='file_action',
                    content_object=officer_file
                )
            elif officer_file.action_to_user is None and action_to_role and action_to_role != 'officer_self' and action_to_role != 'all':
                # This means a specific role was selected but no user was found for that role/location
                messages.warning(request, f"No specific user found for the selected 'Action Required By Role': {action_to_role}. Notification could not be sent to that role.")


            return redirect('hrms:officer_file_detail', pk=officer_file.pk)
        else:
            messages.error(request, "Error uploading file. Please correct the errors.")
    else:
        form = OfficerDocumentForm()

    context = {
        'form': form,
        'officer': officer,
        'title': f'Upload File for {officer.full_name}'
    }
    return render(request, 'hrms/officer_file_form.html', context)

@login_required
def officer_file_list_view(request):
    """
    Lists officer files relevant to the user's role.
    Can be filtered by officer service_number and status.
    """
    user = request.user
    officer_files = OfficerDocument.objects.all().select_related('officer', 'uploaded_by')

    if is_station_level(user) and user.prison_station:
        officer_files = officer_files.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        officer_files = officer_files.filter(officer__region=user.region)
    # National level/superuser sees all

    officer_service_number = request.GET.get('officer_service_number')
    officer_filter = None
    if officer_service_number:
        officer_filter = get_object_or_404(Officer, service_number=officer_service_number)
        officer_files = officer_files.filter(officer=officer_filter)

    search_query = request.GET.get('search', '')
    if search_query:
        officer_files = officer_files.filter(
            Q(file_name__icontains=search_query) |
            Q(officer__service_number__icontains=search_query) |
            Q(officer__first_name__icontains=search_query) |
            Q(officer__surname__icontains=search_query)
        )

    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        officer_files = officer_files.filter(status=status_filter)


    context = {
        'officer_files': officer_files.order_by('-uploaded_at'),
        'title': 'Officer Files',
        'current_status_filter': status_filter,
        'search_query': search_query,
        'officer_filter': officer_filter,
    }
    return render(request, 'hrms/officer_file_list.html', context)

@login_required
def officer_file_detail_view(request, pk):
    """
    Displays details of a single officer file.
    """
    officer_file = get_object_or_404(OfficerDocument.objects.select_related('officer', 'uploaded_by', 'reviewed_by'), pk=pk)
    user = request.user

    if not can_manage_officer_data(user, officer_file.officer.prison_station, officer_file.officer.region):
        messages.error(request, "You do not have permission to view this file.")
        return redirect('hrms:officer_file_list')

    context = {
        'officer_file': officer_file,
        'title': f'File: {officer_file.file_name}'
    }
    return render(request, 'hrms/officer_file_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def officer_file_respond_view(request, pk):
    """
    Allows authorized users to respond to an officer file (approve/reject).
    """
    officer_file = get_object_or_404(OfficerDocument, pk=pk)
    user = request.user

    if not can_manage_officer_data(user, officer_file.officer.prison_station, officer_file.officer.region):
        messages.error(request, "You do not have permission to respond to this file.")
        return redirect('hrms:officer_file_detail', pk=pk)

    if officer_file.status != 'pending':
        messages.warning(request, "This file has already been responded to.")
        return redirect('hrms:officer_file_detail', pk=pk)

    if request.method == 'POST':
        form = OfficerFileResponseForm(request.POST, instance=officer_file)
        if form.is_valid():
            file_response = form.save(commit=False)
            file_response.reviewed_by = user
            file_response.reviewed_at = timezone.now()
            file_response.save()
            messages.success(request, "File response recorded successfully.")

            # Notify the user who uploaded the document about the response
            if officer_file.uploaded_by:
                create_notification(
                    recipient=officer_file.uploaded_by,
                    sender=user,
                    message=f"Your uploaded document '{officer_file.file_name}' for {officer_file.officer.full_name} has been {file_response.get_status_display().lower()}. Notes: {file_response.response_notes or 'N/A'}",
                    notification_type='file_action',
                    content_object=officer_file
                )
            # Notify the officer themselves if they have a user account
            if officer_file.officer.user and officer_file.officer.user != officer_file.uploaded_by:
                create_notification(
                    recipient=officer_file.officer.user,
                    sender=user,
                    message=f"Your document '{officer_file.file_name}' has been reviewed and {file_response.get_status_display().lower()}. Notes: {file_response.response_notes or 'N/A'}",
                    notification_type='file_action',
                    content_object=officer_file
                )


            return redirect('hrms:officer_file_detail', pk=pk)
        else:
            messages.error(request, "Error responding to file. Please correct the errors.")
    else:
        form = OfficerFileResponseForm(instance=officer_file)

    context = {
        'form': form,
        'officer_file': officer_file,
        'title': f'Respond to File: {officer_file.file_name}'
    }
    return render(request, 'hrms/officer_file_response_form.html', context)

# --- Performance Views ---

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def performance_record_create_view(request, service_number):
    """
    Allows adding a new performance record for an officer.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to add performance records for this officer.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        form = OfficerPerformanceForm(request.POST)
        if form.is_valid():
            performance_record = form.save(commit=False)
            performance_record.officer = officer
            performance_record.recorded_by = user
            performance_record.save()
            messages.success(request, "Performance record added successfully.")
            return redirect('hrms:officer_detail', service_number=officer.service_number)
        else:
            messages.error(request, "Error adding performance record. Please correct the errors.")
    else:
        form = OfficerPerformanceForm()

    context = {
        'form': form,
        'officer': officer,
        'title': f'Add Performance Record for {officer.full_name}'
    }
    return render(request, 'hrms/performance_record_form.html', context)

@login_required
def performance_record_list_view(request):
    """
    Lists performance records relevant to the user's role.
    Can be filtered by officer service_number.
    """
    user = request.user
    performance_records = OfficerPerformance.objects.all().select_related('officer', 'metric', 'recorded_by')

    if is_station_level(user) and user.prison_station:
        performance_records = performance_records.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        performance_records = performance_records.filter(officer__region=user.region)
    # National level/superuser sees all

    officer_service_number = request.GET.get('officer_service_number')
    officer_filter = None
    if officer_service_number:
        officer_filter = get_object_or_404(Officer, service_number=officer_service_number)
        performance_records = performance_records.filter(officer=officer_filter)

    search_query = request.GET.get('search', '')
    if search_query:
        performance_records = performance_records.filter(
            Q(officer__service_number__icontains=search_query) |
            Q(officer__first_name__icontains=search_query) |
            Q(officer__surname__icontains=search_query) |
            Q(metric__name__icontains=search_query)
        )

    context = {
        'performance_records': performance_records.order_by('-date', 'officer__surname'),
        'title': 'Officer Performance Records',
        'search_query': search_query,
        'officer_filter': officer_filter,
    }
    return render(request, 'hrms/performance_record_list.html', context)

# --- Office Assignments Views ---

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def office_assignment_create_view(request, service_number):
    """
    Allows assigning an officer to a new office.
    This updates the 'current_office_assignment' field on the Officer model.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to assign offices for this officer.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        form = OfficeAssignmentForm(request.POST, instance=officer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Officer {officer.full_name} assigned to new office successfully.")
            return redirect('hrms:officer_detail', service_number=officer.service_number)
        else:
            messages.error(request, "Error assigning office. Please correct the errors.")
    else:
        form = OfficeAssignmentForm(instance=officer)

    context = {
        'form': form,
        'officer': officer,
        'title': f'Assign Office to {officer.full_name}'
    }
    return render(request, 'hrms/office_assignment_form.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def office_assignment_update_view(request, pk):
    """
    Allows updating an officer's current office assignment.
    """
    officer = get_object_or_404(Officer, pk=pk)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to update this officer's assignment.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        form = OfficeAssignmentForm(request.POST, instance=officer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Officer {officer.full_name}'s office assignment updated successfully.")
            return redirect('hrms:officer_detail', service_number=officer.service_number)
        else:
            messages.error(request, "Error updating office assignment. Please correct the errors.")
    else:
        form = OfficeAssignmentForm(instance=officer)

    context = {
        'form': form,
        'officer': officer,
        'title': f'Update Office Assignment for {officer.full_name}'
    }
    return render(request, 'hrms/office_assignment_form.html', context)


# --- Region Management Views ---

@login_required
@user_passes_test(can_manage_regions)
def region_list_view(request):
    """
    Lists all regions. Only accessible by national-level users or superusers.
    """
    regions = Region.objects.all().order_by('name')
    search_query = request.GET.get('search', '')
    if search_query:
        regions = regions.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))

    context = {
        'regions': regions,
        'title': 'Manage Regions',
        'search_query': search_query,
    }
    return render(request, 'hrms/region_list.html', context)

@login_required
@user_passes_test(can_manage_regions)
def region_create_view(request):
    """
    Allows creating a new region. Only accessible by national-level users or superusers.
    """
    if request.method == 'POST':
        form = RegionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Region added successfully.")
            return redirect('hrms:region_list')
        else:
            messages.error(request, "Error adding region. Please correct the errors.")
    else:
        form = RegionForm()

    context = {
        'form': form,
        'title': 'Add New Region'
    }
    return render(request, 'hrms/region_form.html', context)

@login_required
@user_passes_test(can_manage_regions)
def region_update_view(request, pk):
    """
    Allows updating an existing region. Only accessible by national-level users or superusers.
    """
    region = get_object_or_404(Region, pk=pk)
    if request.method == 'POST':
        form = RegionForm(request.POST, instance=region)
        if form.is_valid():
            form.save()
            messages.success(request, f"Region '{region.name}' updated successfully.")
            return redirect('hrms:region_list')
        else:
            messages.error(request, "Error updating region. Please correct the errors.")
    else:
        form = RegionForm(instance=region)

    context = {
        'form': form,
        'title': f'Edit Region: {region.name}'
    }
    return render(request, 'hrms/region_form.html', context)

@login_required
@user_passes_test(can_manage_regions)
def region_delete_view(request, pk):
    """
    Allows deleting a region. Only accessible by national-level users or superusers.
    """
    region = get_object_or_404(Region, pk=pk)
    if request.method == 'POST':
        region_name = region.name
        region.delete()
        messages.success(request, f"Region '{region_name}' deleted successfully.")
        return redirect('hrms:region_list')

    context = {
        'region': region,
        'title': f'Delete Region: {region.name}'
    }
    return render(request, 'hrms/region_confirm_delete.html', context)

# --- Prison Station Management Views ---

@login_required
@user_passes_test(lambda u: can_manage_prison_stations(u))
def prison_station_list_view(request):
    """
    Lists all prison stations. National level sees all, regional level sees stations in their region.
    """
    user = request.user
    prison_stations = PrisonStation.objects.all().select_related('region').order_by('name')

    if is_regional_level(user) and user.region:
        prison_stations = prison_stations.filter(region=user.region)

    search_query = request.GET.get('search', '')
    if search_query:
        prison_stations = prison_stations.filter(
            Q(name__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(region__name__icontains=search_query)
        )

    context = {
        'prison_stations': prison_stations,
        'title': 'Manage Prison Stations',
        'search_query': search_query,
    }
    return render(request, 'hrms/prison_station_list.html', context)

@login_required
@user_passes_test(lambda u: can_manage_prison_stations(u))
def prison_station_create_view(request):
    """
    Allows creating a new prison station. National level can create anywhere,
    regional level can create only in their region.
    """
    user = request.user
    if request.method == 'POST':
        form = PrisonStationForm(request.POST)
        if form.is_valid():
            prison_station = form.save(commit=False)
            if is_regional_level(user) and user.region:
                if prison_station.region and prison_station.region != user.region: # Check if prison_station.region is set before comparing
                    messages.error(request, "You can only add prison stations within your assigned region.")
                    return render(request, 'hrms/prison_station_form.html', {'form': form, 'title': 'Add New Prison Station'})
            prison_station.save()
            messages.success(request, "Prison Station added successfully.")
            return redirect('hrms:prison_station_list')
        else:
            messages.error(request, "Error adding prison station. Please correct the errors.")
    else:
        form = PrisonStationForm()
        if is_regional_level(user) and user.region:
            form.fields['region'].queryset = Region.objects.filter(pk=user.region.pk)
            form.fields['region'].initial = user.region
            form.fields['region'].widget.attrs['readonly'] = True

    context = {
        'form': form,
        'title': 'Add New Prison Station'
    }
    return render(request, 'hrms/prison_station_form.html', context)

@login_required
@user_passes_test(lambda u: can_manage_prison_stations(u))
def prison_station_update_view(request, pk):
    """
    Allows updating an existing prison station. National level can update anywhere,
    regional level can update only in their region.
    """
    prison_station = get_object_or_404(PrisonStation, pk=pk)
    user = request.user

    if not can_manage_prison_stations(user, prison_station.region):
        messages.error(request, "You do not have permission to edit this prison station.")
        return redirect('hrms:prison_station_list')

    if request.method == 'POST':
        form = PrisonStationForm(request.POST, instance=prison_station)
        if form.is_valid():
            updated_station = form.save(commit=False)
            if is_regional_level(user) and user.region:
                if updated_station.region and updated_station.region != user.region: # Check if updated_station.region is set before comparing
                    messages.error(request, "You can only update prison stations within your assigned region.")
                    return render(request, 'hrms/prison_station_form.html', {'form': form, 'title': f'Edit Prison Station: {prison_station.name}'})
            updated_station.save()
            messages.success(request, f"Prison Station '{prison_station.name}' updated successfully.")
            return redirect('hrms:prison_station_list')
        else:
            messages.error(request, "Error updating prison station. Please correct the errors.")
    else:
        form = PrisonStationForm(instance=prison_station)
        if is_regional_level(user) and user.region:
            form.fields['region'].queryset = Region.objects.filter(pk=user.region.pk)
            form.fields['region'].initial = user.region
            form.fields['region'].widget.attrs['readonly'] = True

    context = {
        'form': form,
        'title': f'Edit Prison Station: {prison_station.name}'
    }
    return render(request, 'hrms/prison_station_form.html', context)

@login_required
@user_passes_test(lambda u: can_manage_prison_stations(u))
def prison_station_delete_view(request, pk):
    """
    Allows deleting a prison station. National level can delete anywhere,
    regional level can delete only in their region.
    """
    prison_station = get_object_or_404(PrisonStation, pk=pk)
    user = request.user

    if not can_manage_prison_stations(user, prison_station.region):
        messages.error(request, "You do not have permission to delete this prison station.")
        return redirect('hrms:prison_station_list')

    if request.method == 'POST':
        station_name = prison_station.name
        prison_station.delete()
        messages.success(request, f"Prison Station '{station_name}' deleted successfully.")
        return redirect('hrms:prison_station_list')

    context = {
        'prison_station': prison_station,
        'title': f'Delete Prison Station: {prison_station.name}'
    }
    return render(request, 'hrms/prison_station_confirm_delete.html', context)

# --- Attendance Views ---

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def attendance_record_create_view(request, service_number):
    """
    Allows adding a new attendance record for an officer.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to add attendance records for this officer.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            attendance_record = form.save(commit=False)
            attendance_record.officer = officer
            attendance_record.recorded_by = user
            attendance_record.save()
            messages.success(request, "Attendance record added successfully.")
            return redirect('hrms:officer_detail', service_number=officer.service_number)
        else:
            messages.error(request, "Error adding attendance record. Please correct the errors.")
    else:
        form = AttendanceForm()

    context = {
        'form': form,
        'officer': officer,
        'title': f'Add Attendance Record for {officer.full_name}'
    }
    return render(request, 'hrms/attendance_form.html', context)

@login_required
def attendance_record_list_view(request):
    """
    Lists attendance records relevant to the user's role.
    """
    user = request.user
    attendance_records = Attendance.objects.all().select_related('officer', 'marked_by')

    if is_station_level(user) and user.prison_station:
        attendance_records = attendance_records.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        attendance_records = attendance_records.filter(officer__region=user.region)
    # National level/superuser sees all

    search_query = request.GET.get('search', '')
    if search_query:
        attendance_records = attendance_records.filter(
            Q(officer__service_number__icontains=search_query) |
            Q(officer__first_name__icontains=search_query) |
            Q(officer__surname__icontains=search_query) |
            Q(notes__icontains=search_query)
        )

    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        attendance_records = attendance_records.filter(status=status_filter)

    officer_service_number = request.GET.get('officer_service_number')
    officer_filter = None
    if officer_service_number:
        officer_filter = get_object_or_404(Officer, service_number=officer_service_number)
        attendance_records = attendance_records.filter(officer=officer_filter)


    context = {
        'attendance_records': attendance_records.order_by('-date', 'officer__surname'),
        'title': 'Officer Attendance Records',
        'search_query': search_query,
        'current_status_filter': status_filter,
        'officer_filter': officer_filter,
    }
    return render(request, 'hrms/attendance_list.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def attendance_record_update_view(request, pk):
    """
    Allows updating an existing attendance record.
    """
    attendance_record = get_object_or_404(Attendance, pk=pk)
    user = request.user

    if not can_manage_officer_data(user, attendance_record.officer.prison_station, attendance_record.officer.region):
        messages.error(request, "You do not have permission to edit this attendance record.")
        return redirect('hrms:attendance_record_list')

    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance_record)
        if form.is_valid():
            form.save()
            messages.success(request, "Attendance record updated successfully.")
            return redirect('hrms:officer_detail', service_number=attendance_record.officer.service_number)
        else:
            messages.error(request, "Error updating attendance record. Please correct the errors.")
    else:
        form = AttendanceForm(instance=attendance_record)

    context = {
        'form': form,
        'officer': attendance_record.officer,
        'title': f'Edit Attendance for {attendance_record.officer.full_name}'
    }
    return render(request, 'hrms/attendance_form.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u))
def attendance_record_delete_view(request, pk):
    """
    Deletes an attendance record. Restricted to national/regional/superuser.
    """
    attendance_record = get_object_or_404(Attendance, pk=pk)
    user = request.user

    if not can_manage_officer_data(user, attendance_record.officer.prison_station, attendance_record.officer.region):
        messages.error(request, "You do not have permission to delete this attendance record.")
        return redirect('hrms:attendance_record_list')

    if request.method == 'POST':
        officer_name = attendance_record.officer.full_name
        attendance_record.delete()
        messages.success(request, f"Attendance record for {officer_name} on {attendance_record.date} deleted successfully.")
        return redirect('hrms:attendance_record_list')

    context = {
        'attendance_record': attendance_record,
        'title': f'Delete Attendance for {attendance_record.officer.full_name}'
    }
    return render(request, 'hrms/attendance_confirm_delete.html', context)


# --- Disciplinary Cases Views ---

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def disciplinary_case_create_view(request, service_number):
    """
    Allows adding a new disciplinary case for an officer.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    user = request.user

    if not can_manage_officer_data(user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to add disciplinary cases for this officer.")
        return redirect('hrms:officer_detail', service_number=officer.service_number)

    if request.method == 'POST':
        form = DisciplinaryCaseForm(request.POST)
        file_formset = DisciplinaryCaseFileFormSet(request.POST, request.FILES, prefix='files')
        
        if form.is_valid() and file_formset.is_valid():
            disciplinary_case = form.save(commit=False)
            disciplinary_case.officer = officer
            disciplinary_case.recorded_by = user
            disciplinary_case.save()
            
            # Save file attachments
            for file_form in file_formset:
                if file_form.cleaned_data and not file_form.cleaned_data.get('DELETE'):
                    file_instance = file_form.save(commit=False)
                    file_instance.disciplinary_case = disciplinary_case
                    file_instance.uploaded_by = user
                    file_instance.save()
            
            messages.success(request, "Disciplinary case added successfully.")

            if officer.user:
                create_notification(
                    recipient=officer.user,
                    sender=user,
                    message=f"A new disciplinary case has been recorded against you for '{disciplinary_case.offense}' on {disciplinary_case.case_date.strftime('%Y-%m-%d')}.",
                    notification_type='disciplinary_action',
                    content_object=disciplinary_case
                )
            hr_users = CustomUser.objects.filter(
                Q(is_superuser=True) |
                Q(role='national_commissioner') |
                Q(role='national_hr') |
                Q(role='regional_commanding_officer', region=officer.region) |
                Q(role='regional_headquarters_officer', region=officer.region) |
                Q(role='regional_hr', region=officer.region)
            ).distinct()
            for hr_user in hr_users:
                if hr_user != user:
                    create_notification(
                        recipient=hr_user,
                        sender=user,
                        message=f"New disciplinary case for {officer.full_name}: '{disciplinary_case.offense}'.",
                        notification_type='disciplinary_action',
                        content_object=disciplinary_case
                    )

            return redirect('hrms:officer_detail', service_number=officer.service_number)
        else:
            messages.error(request, "Error adding disciplinary case. Please correct the errors.")
    else:
        form = DisciplinaryCaseForm()
        file_formset = DisciplinaryCaseFileFormSet(prefix='files')

    context = {
        'form': form,
        'file_formset': file_formset,
        'officer': officer,
        'title': f'Add Disciplinary Case for {officer.full_name}'
    }
    return render(request, 'hrms/disciplinary_case_form.html', context)

@login_required
def disciplinary_case_list_view(request):
    """
    Lists disciplinary cases relevant to the user's role.
    Can be filtered by officer service_number.
    """
    user = request.user
    disciplinary_cases = DisciplinaryCase.objects.all().select_related('officer', 'recorded_by')

    if is_station_level(user) and user.prison_station:
        disciplinary_cases = disciplinary_cases.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        disciplinary_cases = disciplinary_cases.filter(officer__region=user.region)
    # National level/superuser sees all

    officer_service_number = request.GET.get('officer_service_number')
    officer_filter = None
    if officer_service_number:
        officer_filter = get_object_or_404(Officer, service_number=officer_service_number)
        disciplinary_cases = disciplinary_cases.filter(officer=officer_filter)

    search_query = request.GET.get('search', '')
    if search_query:
        disciplinary_cases = disciplinary_cases.filter(
            Q(offense__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(officer__service_number__icontains=search_query) |
            Q(officer__first_name__icontains=search_query) |
            Q(officer__surname__icontains=search_query)
        )

    action_taken_filter = request.GET.get('action_taken')
    if action_taken_filter and action_taken_filter != 'all':
        disciplinary_cases = disciplinary_cases.filter(action_taken=action_taken_filter)


    context = {
        'disciplinary_cases': disciplinary_cases.order_by('-case_date', 'officer__surname'),
        'title': 'Officer Disciplinary Cases',
        'search_query': search_query,
        'action_taken_filter': action_taken_filter,
        'officer_filter': officer_filter,
    }
    return render(request, 'hrms/disciplinary_case_list.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def disciplinary_case_update_view(request, pk):
    """
    Allows updating an existing disciplinary case.
    """
    disciplinary_case = get_object_or_404(DisciplinaryCase, pk=pk)
    user = request.user

    if not can_manage_officer_data(user, disciplinary_case.officer.prison_station, disciplinary_case.officer.region):
        messages.error(request, "You do not have permission to edit this disciplinary case.")
        return redirect('hrms:disciplinary_case_list')

    if request.method == 'POST':
        form = DisciplinaryCaseForm(request.POST, instance=disciplinary_case)
        if form.is_valid():
            form.save()
            messages.success(request, "Disciplinary case updated successfully.")
            return redirect('hrms:officer_detail', service_number=disciplinary_case.officer.service_number)
        else:
            messages.error(request, "Error updating disciplinary case. Please correct the errors.")
    else:
        form = DisciplinaryCaseForm(instance=disciplinary_case)

    context = {
        'form': form,
        'officer': disciplinary_case.officer,
        'title': f'Edit Disciplinary Case for {disciplinary_case.officer.full_name}'
    }
    return render(request, 'hrms/disciplinary_case_form.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u))
def disciplinary_case_delete_view(request, pk):
    """
    Deletes a disciplinary case record. Restricted to national/regional/superuser.
    """
    disciplinary_case = get_object_or_404(DisciplinaryCase, pk=pk)
    user = request.user

    if not can_manage_officer_data(user, disciplinary_case.officer.prison_station, disciplinary_case.officer.region):
        messages.error(request, "You do not have permission to delete this disciplinary case.")
        return redirect('hrms:disciplinary_case_list')

    if request.method == 'POST':
        officer_name = disciplinary_case.officer.full_name
        case_date = disciplinary_case.case_date
        disciplinary_case.delete()
        messages.success(request, f"Disciplinary case for {officer_name} on {case_date} deleted successfully.")
        return redirect('hrms:disciplinary_case_list')

    context = {
        'disciplinary_case': disciplinary_case,
        'title': f'Delete Disciplinary Case for {disciplinary_case.officer.full_name}'
    }
    return render(request, 'hrms/disciplinary_case_confirm_delete.html', context)


# Initial data setup views (for superuser only)
@login_required
def setup_initial_data(request):
    """
    A view to populate initial Ranks, OfficeAssignments, and LeaveTypes.
    Accessible only to superusers.
    """
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('hrms:dashboard')

    if request.method == 'POST':
        # Populate Ranks
        ranks_to_create = [
            {'name': 'watchman', 'leave_days_annual': 21},
            {'name': 'messenger', 'leave_days_annual': 21},
            {'name': 'warder', 'leave_days_annual': 24},
            {'name': 'sergeant', 'leave_days_annual': 24},
            {'name': 'gaoler', 'leave_days_annual': 24},
            {'name': 'inspector', 'leave_days_annual': 24},
            {'name': 'assistant_superintendent', 'leave_days_annual': 30},
            {'name': 'superintendent', 'leave_days_annual': 30},
            {'name': 'senior_superintendent', 'leave_days_annual': 30},
            {'name': 'assistant_commissioner', 'leave_days_annual': 36},
            {'name': 'deputy_commissioner', 'leave_days_annual': 36},
            {'name': 'commissioner', 'leave_days_annual': 36},
            {'name': 'commissioner_general', 'leave_days_annual': 36},
        ]
        for rank_data in ranks_to_create:
            Rank.objects.get_or_create(name=rank_data['name'], defaults=rank_data)
        messages.info(request, "Ranks populated.")

        # Populate Office Assignments
        office_assignments_to_create = [
            {'name': 'general_duties'}, {'name': 'hospital'}, {'name': 'female_in_charge'},
            {'name': 'administration'}, {'name': 'accounts_office'}, {'name': 'research_office'},
            {'name': 'gender'}, {'name': 'rehabilitation'}, {'name': 'public_relations_office'},
            {'name': 'chaplaincy'}, {'name': 'secretary'}, {'name': 'protocol'},
            {'name': 'restorative_justice'}, {'name': 'radio_communication'}, {'name': 'registry'},
            {'name': 'ict'}, {'name': 'education'}, {'name': 'driver'},
        ]
        for office_data in office_assignments_to_create:
            OfficeAssignment.objects.get_or_create(name=office_data['name'], defaults=office_data)
        messages.info(request, "Office Assignments populated.")

        # Populate Leave Types
        leave_types_to_create = [
            {'name': 'Annual Leave', 'is_maternity': False, 'is_study': False, 'default_days': None},
            {'name': 'Maternity Leave', 'is_maternity': True, 'is_study': False, 'default_days': 90},
            {'name': 'Study Leave', 'is_maternity': False, 'is_study': True, 'default_days': None},
            {'name': 'Sick Leave', 'is_maternity': False, 'is_study': False, 'default_days': None},
            {'name': 'Compassionate Leave', 'is_maternity': False, 'is_study': False, 'default_days': None},
        ]
        for leave_type_data in leave_types_to_create:
            LeaveType.objects.get_or_create(name=leave_type_data['name'], defaults=leave_type_data)
        messages.info(request, "Leave Types populated.")

        # Populate Performance Metrics
        performance_metrics_to_create = [
            {'name': 'Punctuality', 'description': 'Adherence to schedules and deadlines.'},
            {'name': 'Teamwork', 'description': 'Ability to collaborate effectively with colleagues.'},
            {'name': 'Communication Skills', 'description': 'Clarity and effectiveness in conveying information.'},
            {'name': 'Report Writing Skills', 'description': 'Accuracy, clarity, and conciseness in written reports.'},
            {'name': 'Problem Identification', 'description': 'Ability to accurately identify and define problems.'},
            {'name': 'Solution Generation', 'description': 'Capacity to develop creative and effective solutions.'},
            {'name': 'Decision Making', 'description': 'Skill in making sound and timely decisions based on available information.'},
            {'name': 'Implementation Effectiveness', 'description': 'Proficiency in putting solutions into practice and evaluating their success.'},
        ]
        for metric_data in performance_metrics_to_create:
            PerformanceMetric.objects.get_or_create(name=metric_data['name'], defaults=metric_data)
        messages.info(request, "Performance Metrics populated.")

        messages.success(request, "Initial data setup complete!")
        return redirect('hrms:dashboard')

    return render(request, 'hrms/setup_initial_data.html')


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u))
def annual_leave_reset_view(request):
    """
    A view to manually trigger the annual leave reset for all officers.
    This should typically be a scheduled task, but a manual trigger is useful for testing/admin.
    """
    if request.method == 'POST':
        current_year = date.today().year
        reset_count = 0

        officers = Officer.objects.filter(status='active')

        for officer in officers:
            entitled_days = officer.rank.leave_days_annual if officer.rank else 0

            annual_balance, created = AnnualLeaveBalance.objects.get_or_create(
                officer=officer,
                year=current_year,
                defaults={
                    'total_days_entitled': entitled_days,
                    'days_taken': 0,
                    'last_reset_date': date.today()
                }
            )

            if not created:
                if annual_balance.last_reset_date != date.today():
                    annual_balance.total_days_entitled = entitled_days
                    annual_balance.days_taken = 0
                    annual_balance.last_reset_date = date.today()
                    annual_balance.save()
                    reset_count += 1
                else:
                    messages.info(request, f"Leave for {officer.full_name} already reset today.")
            else:
                reset_count += 1

        messages.success(request, f"Annual leave reset process completed. {reset_count} officer(s) had their leave balance reset/created for {current_year}.")
        return redirect('hrms:dashboard')

    context = {
        'title': 'Annual Leave Reset',
        'current_year': date.today().year,
        'next_reset_date_info': 'This action will reset annual leave balances for all active officers for the current year. It should typically be run once at the start of your leave year (e.g., April 1st).',
    }
    return render(request, 'hrms/annual_leave_reset_confirm.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def attendance_report_view(request):
    """
    Generates an attendance report with filtering options.
    Users can filter by year, month, region, and prison station.
    """
    user = request.user

    selected_year = request.GET.get('year', str(date.today().year))
    selected_month = request.GET.get('month', '')
    selected_region_id = request.GET.get('region', '')
    selected_station_id = request.GET.get('station', '')

    attendance_records = Attendance.objects.all().select_related('officer__region', 'officer__prison_station')

    if is_station_level(user) and user.prison_station:
        attendance_records = attendance_records.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        attendance_records = attendance_records.filter(officer__region=user.region)

    if selected_year:
        attendance_records = attendance_records.filter(date__year=selected_year)
    if selected_month:
        attendance_records = attendance_records.filter(date__month=selected_month)
    if selected_region_id:
        attendance_records = attendance_records.filter(officer__region_id=selected_region_id)
    if selected_station_id:
        attendance_records = attendance_records.filter(officer__prison_station_id=selected_station_id)
        if not selected_region_id:
            try:
                station = PrisonStation.objects.get(pk=selected_station_id)
                selected_region_id = str(station.region_id)
            except PrisonStation.DoesNotExist:
                pass

    attendance_summary = attendance_records.values('status').annotate(count=Count('status'))
    summary_dict = {item['status']: item['count'] for item in attendance_summary}

    available_years = Attendance.objects.annotate(year=ExtractYear('date')).values_list('year', flat=True).distinct().order_by('-year')
    if not available_years:
        available_years = [date.today().year]

    regions = Region.objects.all().order_by('name')
    stations = PrisonStation.objects.all().order_by('name')

    if is_regional_level(user) and user.region:
        regions = regions.filter(pk=user.region.pk)
        stations = stations.filter(region=user.region)
    elif is_station_level(user) and user.prison_station:
        regions = regions.filter(pk=user.prison_station.region.pk)
        stations = stations.filter(pk=user.prison_station.pk)

    if selected_region_id:
        stations = stations.filter(region_id=selected_region_id)

    context = {
        'title': 'Attendance Report',
        'summary_data': summary_dict,
        'total_records': attendance_records.count(),
        'available_years': available_years,
        'months': [
            {'value': 1, 'name': 'January'}, {'value': 2, 'name': 'February'},
            {'value': 3, 'name': 'March'}, {'value': 4, 'name': 'April'},
            {'value': 5, 'name': 'May'}, {'value': 6, 'name': 'June'},
            {'value': 7, 'name': 'July'}, {'value': 8, 'name': 'August'},
            {'value': 9, 'name': 'September'}, {'value': 10, 'name': 'October'},
            {'value': 11, 'name': 'November'}, {'value': 12, 'name': 'December'},
        ],
        'regions': regions,
        'stations': stations,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_region_id': selected_region_id,
        'selected_station_id': selected_station_id,
    }
    return render(request, 'hrms/attendance_report.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def performance_report_view(request):
    """
    Generates a performance report with filtering options.
    Users can filter by year, month, specific metric, region, and prison station.
    """
    user = request.user

    selected_year = request.GET.get('year', str(date.today().year))
    selected_month = request.GET.get('month', '')
    selected_metric_id = request.GET.get('metric', '')
    selected_region_id = request.GET.get('region', '')
    selected_station_id = request.GET.get('station', '')

    performance_records = OfficerPerformance.objects.all().select_related('officer__region', 'officer__prison_station', 'metric')

    if is_station_level(user) and user.prison_station:
        performance_records = performance_records.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        performance_records = performance_records.filter(officer__region=user.region)

    if selected_year:
        performance_records = performance_records.filter(date__year=selected_year)
    if selected_month:
        performance_records = performance_records.filter(date__month=selected_month)
    if selected_metric_id:
        performance_records = performance_records.filter(metric_id=selected_metric_id)
    if selected_region_id:
        performance_records = performance_records.filter(officer__region_id=selected_region_id)
    if selected_station_id:
        performance_records = performance_records.filter(officer__prison_station_id=selected_station_id)

    overall_average_score = performance_records.aggregate(Avg('score'))['score__avg']

    average_scores_by_metric = []
    if not selected_metric_id:
        average_scores_by_metric = performance_records.values('metric__name').annotate(avg_score=Avg('score')).order_by('metric__name')

    officer_performance_summary = performance_records.values(
        'officer__service_number',
        'officer__first_name',
        'officer__surname'
    ).annotate(
        avg_score=Avg('score'),
        record_count=Count('pk')
    ).order_by('-avg_score')

    available_years = OfficerPerformance.objects.annotate(year=ExtractYear('date')).values_list('year', flat=True).distinct().order_by('-year')
    if not available_years:
        available_years = [date.today().year]

    all_metrics = PerformanceMetric.objects.all().order_by('name')

    regions = Region.objects.all().order_by('name')
    stations = PrisonStation.objects.all().order_by('name')

    if is_regional_level(user) and user.region:
        regions = regions.filter(pk=user.region.pk)
        stations = stations.filter(region=user.region)
    elif is_station_level(user) and user.prison_station:
        regions = regions.filter(pk=user.prison_station.region.pk)
        stations = stations.filter(pk=user.prison_station.pk)

    context = {
        'title': 'Performance Report',
        'overall_average_score': round(overall_average_score, 2) if overall_average_score else 'N/A',
        'average_scores_by_metric': average_scores_by_metric,
        'officer_performance_summary': officer_performance_summary,
        'total_records': performance_records.count(),
        'available_years': available_years,
        'months': [
            {'value': 1, 'name': 'January'}, {'value': 2, 'name': 'February'},
            {'value': 3, 'name': 'March'}, {'value': 4, 'name': 'April'},
            {'value': 5, 'name': 'May'}, {'value': 6, 'name': 'June'},
            {'value': 7, 'name': 'July'}, {'value': 8, 'name': 'August'},
            {'value': 9, 'name': 'September'}, {'value': 10, 'name': 'October'},
            {'value': 11, 'name': 'November'}, {'value': 12, 'name': 'December'},
        ],
        'all_metrics': all_metrics,
        'regions': regions,
        'stations': stations,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_metric_id': selected_metric_id,
        'selected_region_id': selected_region_id,
        'selected_station_id': selected_station_id,
    }
    return render(request, 'hrms/performance_report.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def disciplinary_report_view(request):
    """
    Generates a disciplinary cases report with filtering options.
    Users can filter by year, month, action taken, region, and prison station.
    """
    user = request.user

    selected_year = request.GET.get('year', str(date.today().year))
    selected_month = request.GET.get('month', '')
    selected_action_taken = request.GET.get('action_taken', '')
    selected_region_id = request.GET.get('region', '')
    selected_station_id = request.GET.get('station', '')

    disciplinary_cases = DisciplinaryCase.objects.all().select_related('officer__region', 'officer__prison_station')

    if is_station_level(user) and user.prison_station:
        disciplinary_cases = disciplinary_cases.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        disciplinary_cases = disciplinary_cases.filter(officer__region=user.region)

    if selected_year:
        disciplinary_cases = disciplinary_cases.filter(case_date__year=selected_year)
    if selected_month:
        disciplinary_cases = disciplinary_cases.filter(case_date__month=selected_month)
    if selected_action_taken:
        disciplinary_cases = disciplinary_cases.filter(action_taken=selected_action_taken)
    if selected_region_id:
        disciplinary_cases = disciplinary_cases.filter(officer__region_id=selected_region_id)
    if selected_station_id:
        disciplinary_cases = disciplinary_cases.filter(officer__prison_station_id=selected_station_id)

    total_cases = disciplinary_cases.count()

    cases_by_offense = disciplinary_cases.values('offense').annotate(count=Count('offense')).order_by('-count')

    cases_by_action = disciplinary_cases.values('action_taken').annotate(count=Count('action_taken')).order_by('-count')

    available_years = DisciplinaryCase.objects.annotate(year=ExtractYear('case_date')).values_list('year', flat=True).distinct().order_by('-year')
    if not available_years:
        available_years = [date.today().year]

    action_taken_choices = DisciplinaryCase.ACTION_TAKEN_CHOICES

    regions = Region.objects.all().order_by('name')
    stations = PrisonStation.objects.all().order_by('name')

    if is_regional_level(user) and user.region:
        regions = regions.filter(pk=user.region.pk)
        stations = stations.filter(region=user.region)
    elif is_station_level(user) and user.prison_station:
        regions = regions.filter(pk=user.prison_station.region.pk)
        stations = stations.filter(pk=user.prison_station.pk)

    context = {
        'title': 'Disciplinary Cases Report',
        'total_cases': total_cases,
        'cases_by_offense': cases_by_offense,
        'cases_by_action': cases_by_action,
        'available_years': available_years,
        'months': [
            {'value': 1, 'name': 'January'}, {'value': 2, 'name': 'February'},
            {'value': 3, 'name': 'March'}, {'value': 4, 'name': 'April'},
            {'value': 5, 'name': 'May'}, {'value': 6, 'name': 'June'},
            {'value': 7, 'name': 'July'}, {'value': 8, 'name': 'August'},
            {'value': 9, 'name': 'September'}, {'value': 10, 'name': 'October'},
            {'value': 11, 'name': 'November'}, {'value': 12, 'name': 'December'},
        ],
        'action_taken_choices': action_taken_choices,
        'regions': regions,
        'stations': stations,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_action_taken': selected_action_taken,
        'selected_region_id': selected_region_id,
        'selected_station_id': selected_station_id,
    }
    return render(request, 'hrms/disciplinary_report.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def leave_report_view(request):
    """
    Generates a leave report with filtering options.
    Users can filter by year, month, leave type, status, region, and prison station.
    """
    user = request.user

    selected_year = request.GET.get('year', str(date.today().year))
    selected_month = request.GET.get('month', '')
    selected_leave_type_id = request.GET.get('leave_type', '')
    selected_status = request.GET.get('status', '')
    selected_region_id = request.GET.get('region', '')
    selected_station_id = request.GET.get('station', '')

    leave_requests = LeaveRequest.objects.all().select_related('officer__region', 'officer__prison_station', 'leave_type')

    if is_station_level(user) and user.prison_station:
        leave_requests = leave_requests.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        leave_requests = leave_requests.filter(officer__region=user.region)

    if selected_year:
        leave_requests = leave_requests.filter(start_date__year=selected_year)
    if selected_month:
        leave_requests = leave_requests.filter(start_date__month=selected_month)
    if selected_leave_type_id:
        leave_requests = leave_requests.filter(leave_type_id=selected_leave_type_id)
    if selected_status:
        leave_requests = leave_requests.filter(status=selected_status)
    if selected_region_id:
        leave_requests = leave_requests.filter(officer__region_id=selected_region_id)
    if selected_station_id:
        leave_requests = leave_requests.filter(officer__prison_station_id=selected_station_id)

    total_leave_requests = leave_requests.count()
    total_days_requested = leave_requests.aggregate(Sum('number_of_days'))['number_of_days__sum'] or 0

    requests_by_status = leave_requests.values('status').annotate(count=Count('status')).order_by('status')

    requests_by_type = leave_requests.values('leave_type__name').annotate(count=Count('leave_type__name'), total_days=Sum('number_of_days')).order_by('leave_type__name')

    available_years = LeaveRequest.objects.annotate(year=ExtractYear('start_date')).values_list('year', flat=True).distinct().order_by('-year')
    if not available_years:
        available_years = [date.today().year]

    all_leave_types = LeaveType.objects.all().order_by('name')

    leave_status_choices = LeaveRequest.STATUS_CHOICES

    regions = Region.objects.all().order_by('name')
    stations = PrisonStation.objects.all().order_by('name')

    if is_regional_level(user) and user.region:
        regions = regions.filter(pk=user.region.pk)
        stations = stations.filter(region=user.region)
    elif is_station_level(user) and user.prison_station:
        regions = regions.filter(pk=user.prison_station.region.pk)
        stations = stations.filter(pk=user.prison_station.pk)

    context = {
        'title': 'Leave Report',
        'total_leave_requests': total_leave_requests,
        'total_days_requested': total_days_requested,
        'requests_by_status': requests_by_status,
        'requests_by_type': requests_by_type,
        'available_years': available_years,
        'months': [
            {'value': 1, 'name': 'January'}, {'value': 2, 'name': 'February'},
            {'value': 3, 'name': 'March'}, {'value': 4, 'name': 'April'},
            {'value': 5, 'name': 'May'}, {'value': 6, 'name': 'June'},
            {'value': 7, 'name': 'July'}, {'value': 8, 'name': 'August'},
            {'value': 9, 'name': 'September'}, {'value': 10, 'name': 'October'},
            {'value': 11, 'name': 'November'}, {'value': 12, 'name': 'December'},
        ],
        'all_leave_types': all_leave_types,
        'leave_status_choices': leave_status_choices,
        'regions': regions,
        'stations': stations,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_leave_type_id': selected_leave_type_id,
        'selected_status': selected_status,
        'selected_region_id': selected_region_id,
        'selected_station_id': selected_station_id,
    }
    return render(request, 'hrms/leave_report.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def demographics_report_view(request):
    """
    Generates a demographics report with filtering options.
    Users can filter by region and prison station.
    The report provides breakdowns by gender, marital status, and rank.
    """
    user = request.user

    selected_region_id = request.GET.get('region', '')
    selected_station_id = request.GET.get('station', '')
    selected_status = request.GET.get('status', '')

    officers = Officer.objects.all().select_related('region', 'prison_station', 'rank')

    if is_station_level(user) and user.prison_station:
        officers = officers.filter(prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        officers = officers.filter(region=user.region)

    if selected_region_id:
        officers = officers.filter(region_id=selected_region_id)
    if selected_station_id:
        officers = officers.filter(prison_station_id=selected_station_id)
    if selected_status:
        officers = officers.filter(status=selected_status)

    total_officers = officers.count()

    gender_breakdown = officers.values('gender').annotate(count=Count('gender')).order_by('gender')
    gender_display_map = dict(Officer.GENDER_CHOICES)
    gender_breakdown_display = [{'gender': gender_display_map.get(item['gender'], item['gender']), 'count': item['count']} for item in gender_breakdown]


    marital_status_breakdown = officers.values('marital_status').annotate(count=Count('marital_status')).order_by('marital_status')
    marital_status_display_map = dict(Officer.MARITAL_STATUS_CHOICES)
    marital_status_breakdown_display = [{'marital_status': marital_status_display_map.get(item['marital_status'], item['marital_status']), 'count': item['count']} for item in marital_status_breakdown]


    rank_breakdown = officers.values('rank__name').annotate(count=Count('rank__name')).order_by('rank__name')
    rank_display_map = dict(Rank.RANK_CHOICES)
    rank_breakdown_display = [{'rank': rank_display_map.get(item['rank__name'], item['rank__name']), 'count': item['count']} for item in rank_breakdown]


    age_groups = {
        'Under 30': 0,
        '30-39': 0,
        '40-49': 0,
        '50-59': 0,
        '60+': 0,
    }
    today = date.today()
    for officer in officers:
        if officer.date_of_birth:
            age = today.year - officer.date_of_birth.year - ((today.month, today.day) < (officer.date_of_birth.month, officer.date_of_birth.day))
            if age < 30:
                age_groups['Under 30'] += 1
            elif 30 <= age <= 39:
                age_groups['30-39'] += 1
            elif 40 <= age <= 49:
                age_groups['40-49'] += 1
            elif 50 <= age <= 59:
                age_groups['50-59'] += 1
            else:
                age_groups['60+'] += 1
    age_group_breakdown = [{'age_group': k, 'count': v} for k, v in age_groups.items()]


    regions = Region.objects.all().order_by('name')
    stations = PrisonStation.objects.all().order_by('name')

    if is_regional_level(user) and user.region:
        regions = regions.filter(pk=user.region.pk)
        stations = stations.filter(region=user.region)
    elif is_station_level(user) and user.prison_station:
        regions = regions.filter(pk=user.prison_station.region.pk)
        stations = stations.filter(pk=user.prison_station.pk)

    context = {
        'title': 'Demographics Report',
        'total_officers': total_officers,
        'gender_breakdown': gender_breakdown_display,
        'marital_status_breakdown': marital_status_breakdown_display,
        'rank_breakdown': rank_breakdown_display,
        'age_group_breakdown': age_group_breakdown,
        'officer_status_choices': Officer.STATUS_CHOICES,
        'regions': regions,
        'stations': stations,
        'selected_region_id': selected_region_id,
        'selected_station_id': selected_station_id,
        'selected_status': selected_status,
    }
    return render(request, 'hrms/demographics_report.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def service_history_report_view(request):
    """
    Generates a service history report (promotions and transfers) with filtering options.
    Users can filter by year, month, type (promotion/transfer), rank, region, and prison station.
    """
    user = request.user

    selected_year = request.GET.get('year', str(date.today().year))
    selected_month = request.GET.get('month', '')
    selected_history_type = request.GET.get('history_type', '')
    selected_rank_id = request.GET.get('rank', '')
    selected_region_id = request.GET.get('region', '')
    selected_station_id = request.GET.get('station', '')

    promotions_queryset = PromotionHistory.objects.all().select_related('officer__region', 'officer__prison_station', 'previous_rank', 'new_rank')
    transfers_queryset = TransferHistory.objects.all().select_related('officer__region', 'officer__prison_station', 'previous_station', 'new_station')

    if is_station_level(user) and user.prison_station:
        promotions_queryset = promotions_queryset.filter(officer__prison_station=user.prison_station)
        transfers_queryset = transfers_queryset.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        promotions_queryset = promotions_queryset.filter(officer__region=user.region)
        transfers_queryset = transfers_queryset.filter(officer__region=user.region)

    if selected_year:
        promotions_queryset = promotions_queryset.filter(promotion_date__year=selected_year)
        transfers_queryset = transfers_queryset.filter(transfer_date__year=selected_year)
    if selected_month:
        promotions_queryset = promotions_queryset.filter(promotion_date__month=selected_month)
        transfers_queryset = transfers_queryset.filter(transfer_date__month=selected_month)
    if selected_region_id:
        promotions_queryset = promotions_queryset.filter(officer__region_id=selected_region_id)
        transfers_queryset = transfers_queryset.filter(officer__region_id=selected_region_id)
    if selected_station_id:
        promotions_queryset = promotions_queryset.filter(officer__prison_station_id=selected_station_id)
        transfers_queryset = transfers_queryset.filter(officer__prison_station_id=selected_station_id)
    if selected_rank_id:
        promotions_queryset = promotions_queryset.filter(new_rank_id=selected_rank_id)


    total_records = 0
    promotions_summary = []
    transfers_summary = []

    if selected_history_type == 'promotion' or not selected_history_type:
        total_promotions = promotions_queryset.count()
        promotions_by_new_rank = promotions_queryset.values('new_rank__name').annotate(count=Count('new_rank__name')).order_by('-count')
        promotions_summary = [{'type': 'Promotion', 'detail': item['new_rank__name'], 'count': item['count']} for item in promotions_by_new_rank]
        total_records += total_promotions

    if selected_history_type == 'transfer' or not selected_history_type:
        total_transfers = transfers_queryset.count()
        transfers_by_new_station = transfers_queryset.values('new_station__name', 'new_station__region__name').annotate(count=Count('new_station__name')).order_by('-count')
        transfers_summary = [{'type': 'Transfer', 'detail': f"{item['new_station__name']} ({item['new_station__region__name']})", 'count': item['count']} for item in transfers_by_new_station]
        total_records += total_transfers


    available_years_promo = PromotionHistory.objects.annotate(year=ExtractYear('promotion_date')).values_list('year', flat=True)
    available_years_transfer = TransferHistory.objects.annotate(year=ExtractYear('transfer_date')).values_list('year', flat=True)
    available_years = sorted(list(set(list(available_years_promo) + list(available_years_transfer))), reverse=True)
    if not available_years:
        available_years = [date.today().year]

    all_ranks = Rank.objects.all().order_by('name')
    regions = Region.objects.all().order_by('name')
    stations = PrisonStation.objects.all().order_by('name')

    if is_regional_level(user) and user.region:
        regions = regions.filter(pk=user.region.pk)
        stations = stations.filter(region=user.region)
    elif is_station_level(user) and user.prison_station:
        regions = regions.filter(pk=user.prison_station.region.pk)
        stations = stations.filter(pk=user.prison_station.pk)


    context = {
        'title': 'Service History Report',
        'total_records': total_records,
        'promotions_summary': promotions_summary,
        'transfers_summary': transfers_summary,
        'available_years': available_years,
        'months': [
            {'value': 1, 'name': 'January'}, {'value': 2, 'name': 'February'},
            {'value': 3, 'name': 'March'}, {'value': 4, 'name': 'April'},
            {'value': 5, 'name': 'May'}, {'value': 6, 'name': 'June'},
            {'value': 7, 'name': 'July'}, {'value': 8, 'name': 'August'},
            {'value': 9, 'name': 'September'}, {'value': 10, 'name': 'October'},
            {'value': 11, 'name': 'November'}, {'value': 12, 'name': 'December'},
        ],
        'all_ranks': all_ranks,
        'regions': regions,
        'stations': stations,
        'history_type_choices': [
            {'value': 'promotion', 'label': 'Promotion'},
            {'value': 'transfer', 'label': 'Transfer'},
        ],
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_history_type': selected_history_type,
        'selected_rank_id': selected_rank_id,
        'selected_region_id': selected_region_id,
        'selected_station_id': selected_station_id,
    }
    return render(request, 'hrms/service_history_report.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def report_list_view(request):
    """
    Displays a list of all available reports.
    """
    context = {
        'title': 'Reports Overview',
    }
    return render(request, 'hrms/report_list.html', context)


# --- Notification Views ---

@login_required
def notification_list_view(request):
    """
    Lists all notifications for the current user.
    """
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    context = {
        'notifications': notifications,
        'title': 'Your Notifications'
    }
    return render(request, 'hrms/notification_list.html', context)

@login_required
def notification_detail_view(request, pk):
    """
    Displays a single notification and marks it as read.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save()
    context = {
        'notification': notification,
        'title': 'Notification Details'
    }
    return render(request, 'hrms/notification_detail.html', context)

@login_required
def mark_notification_read(request, pk):
    """
    Marks a single notification as read via POST request.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save()
        messages.success(request, "Notification marked as read.")
    return redirect('hrms:notification_list')

@login_required
def mark_all_notifications_read(request):
    """
    Marks all notifications for the current user as read via POST request.
    """
    notifications = Notification.objects.filter(recipient=request.user, is_read=False)
    count = notifications.update(is_read=True)
    messages.success(request, f"{count} notifications marked as read.")
    return redirect('hrms:notification_list')

# View to get unread notification count for AJAX
@login_required
def get_unread_notification_count_view(request):
    """
    Returns the count of unread notifications for the current user as JSON.
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return JsonResponse({'unread_count': unread_count})


# --- Attendance Views ---

@login_required
def daily_attendance_view(request):
    """
    Displays the daily attendance page with all officers for marking attendance.
    """
    today = timezone.now().date()
    attendance_date = request.GET.get('date', today)
    
    # Get all active officers
    officers = Officer.objects.filter(status='active').order_by('surname', 'first_name')
    
    # Get existing attendance for the selected date
    existing_attendance = Attendance.objects.filter(date=attendance_date)
    attendance_dict = {att.officer.id: att for att in existing_attendance}
    
    # Get stations for filtering
    stations = PrisonStation.objects.all()
    
    context = {
        'officers': officers,
        'attendance_dict': attendance_dict,
        'today': today,
        'selected_date': attendance_date,
        'stations': stations,
        'title': 'Daily Attendance'
    }
    return render(request, 'hrms/daily_attendance.html', context)


@login_required
def save_daily_attendance_view(request):
    """
    Saves daily attendance records via AJAX.
    """
    if request.method == 'POST':
        attendance_date = request.POST.get('attendance_date', timezone.now().date())
        marked_by = request.user
        
        try:
            attendance_date = timezone.datetime.strptime(attendance_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format'})
        
        saved_count = 0
        error_count = 0
        
        # Process each officer's attendance
        for key, value in request.POST.items():
            if key.startswith('attendance_') and value == 'on':
                officer_id = key.split('_')[1]
                try:
                    officer = Officer.objects.get(id=officer_id)
                    shift = request.POST.get(f'shift_{officer_id}', 'morning')
                    remarks = request.POST.get(f'remarks_{officer_id}', '')
                    
                    # Create or update attendance record
                    attendance, created = Attendance.objects.update_or_create(
                        officer=officer,
                        date=attendance_date,
                        shift=shift,
                        defaults={
                            'status': 'present',
                            'remarks': remarks,
                            'marked_by': marked_by
                        }
                    )
                    saved_count += 1
                    
                except Officer.DoesNotExist:
                    error_count += 1
                    continue
            elif key.startswith('attendance_') and value == 'off':
                # Handle unchecked boxes (mark as absent)
                officer_id = key.split('_')[1]
                try:
                    officer = Officer.objects.get(id=officer_id)
                    shift = request.POST.get(f'shift_{officer_id}', 'morning')
                    remarks = request.POST.get(f'remarks_{officer_id}', '')
                    
                    # Create or update attendance record as absent
                    attendance, created = Attendance.objects.update_or_create(
                        officer=officer,
                        date=attendance_date,
                        shift=shift,
                        defaults={
                            'status': 'absent',
                            'remarks': remarks,
                            'marked_by': marked_by
                        }
                    )
                    saved_count += 1
                    
                except Officer.DoesNotExist:
                    error_count += 1
                    continue
        
        if error_count > 0:
            message = f'Attendance saved with {error_count} errors. {saved_count} records processed.'
        else:
            message = f'Attendance saved successfully! {saved_count} records processed.'
        
        return JsonResponse({'success': True, 'message': message})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def get_attendance_for_date_view(request, date_str):
    """
    Returns attendance data for a specific date as JSON.
    """
    try:
        attendance_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid date format'})
    
    attendances = Attendance.objects.filter(date=attendance_date)
    attendance_data = []
    
    for attendance in attendances:
        attendance_data.append({
            'officer_id': attendance.officer.id,
            'present': attendance.status == 'present',
            'status': attendance.status,
            'shift': attendance.shift,
            'remarks': attendance.remarks
        })
    
    return JsonResponse({'success': True, 'attendance': attendance_data})


@login_required
def attendance_summary_report_view(request):
    """
    Displays monthly attendance reports with graphs and statistics.
    """
    # Get current month and year
    today = timezone.now().date()
    year = request.GET.get('year', today.year)
    month = request.GET.get('month', today.month)
    
    try:
        year = int(year)
        month = int(month)
    except ValueError:
        year = today.year
        month = today.month
    
    # Get attendance summaries for the selected month
    summaries = AttendanceSummary.objects.filter(year=year, month=month)
    
    # Calculate overall statistics
    total_officers = summaries.count()
    avg_attendance = summaries.aggregate(avg_attendance=Avg('attendance_percentage'))['avg_attendance'] or 0
    
    # Calculate aggregated values for charts
    attendance_stats = summaries.aggregate(
        total_present=Sum('present_days'),
        total_absent=Sum('absent_days'),
        total_leave=Sum('leave_days'),
        total_sick=Sum('sick_days'),
        total_duty=Sum('duty_days')
    )
    
    # Get top performers and low performers
    top_performers = summaries.filter(attendance_percentage__gte=95).order_by('-attendance_percentage')[:10]
    low_performers = summaries.filter(attendance_percentage__lt=80).order_by('attendance_percentage')[:10]
    good_performers = summaries.filter(attendance_percentage__gte=80, attendance_percentage__lt=95).count()
    
    context = {
        'summaries': summaries,
        'year': year,
        'month': month,
        'total_officers': total_officers,
        'avg_attendance': avg_attendance,
        'attendance_stats': attendance_stats,
        'top_performers': top_performers,
        'low_performers': low_performers,
        'good_performers': good_performers,
        'title': f'Attendance Report - {year}/{month:02d}'
    }
    return render(request, 'hrms/attendance_report.html', context)


def generate_attendance_summary_pdf(attendance_records, year, month):
    """
    Generate PDF from actual attendance records with summary statistics.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=18,
    )
    styles = getSampleStyleSheet()
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        alignment=TA_LEFT,
        wordWrap='CJK',
    )
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
        wordWrap='CJK',
    )
    elements = []

    month_str = f'{int(month):02d}' if month else 'All Months'
    title_text = f'Attendance Report - {year}/{month_str}'
    elements.append(Paragraph(title_text, styles['Title']))
    elements.append(Spacer(1, 12))

    # Prepare table data
    table_data = [
        [
            Paragraph('Officer Name', header_style),
            Paragraph('Service Number', header_style),
            Paragraph('Region', header_style),
            Paragraph('Station', header_style),
            Paragraph('Date', header_style),
            Paragraph('Status', header_style),
            Paragraph('Shift', header_style),
            Paragraph('Check In', header_style),
            Paragraph('Check Out', header_style),
            Paragraph('Remarks', header_style),
        ]
    ]

    if attendance_records.exists():
        for record in attendance_records.select_related(
            'officer__region', 'officer__prison_station', 'marked_by'
        ).order_by('officer__surname', 'officer__first_name', '-date'):
            table_data.append([
                Paragraph(record.officer.full_name, table_cell_style),
                Paragraph(record.officer.service_number, table_cell_style),
                Paragraph(record.officer.region.name if record.officer.region else 'N/A', table_cell_style),
                Paragraph(record.officer.prison_station.name if record.officer.prison_station else 'N/A', table_cell_style),
                Paragraph(record.date.strftime('%Y-%m-%d'), table_cell_style),
                Paragraph(record.get_status_display(), table_cell_style),
                Paragraph(record.get_shift_display(), table_cell_style),
                Paragraph(str(record.check_in_time) if record.check_in_time else '', table_cell_style),
                Paragraph(str(record.check_out_time) if record.check_out_time else '', table_cell_style),
                Paragraph(record.remarks or '', table_cell_style),
            ])
    else:
        table_data.append([
            Paragraph('No attendance records found for the selected filters.', table_cell_style)
        ] + [Paragraph('', table_cell_style)] * 9)

    # Create table with proper column widths
    col_widths = [80, 50, 70, 75, 60, 55, 70, 55, 55, 90]
    table = Table(table_data, repeatRows=1, hAlign='LEFT', colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('LEFTPADDING', (0, 1), (-1, -1), 4),
        ('RIGHTPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer


@login_required
@user_passes_test(lambda u: u.is_superuser or is_national_level(u) or is_regional_level(u) or is_station_level(u))
def attendance_report_pdf_export_view(request):
    """
    Export attendance report as PDF with all applied filters.
    """
    user = request.user
    today = timezone.now().date()
    
    selected_year = request.GET.get('year', str(today.year))
    selected_month = request.GET.get('month', '')
    selected_region_id = request.GET.get('region', '')
    selected_station_id = request.GET.get('station', '')

    # Start with all attendance records
    attendance_records = Attendance.objects.all().select_related(
        'officer__region', 'officer__prison_station', 'marked_by'
    )

    # Apply user role filters
    if is_station_level(user) and user.prison_station:
        attendance_records = attendance_records.filter(officer__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        attendance_records = attendance_records.filter(officer__region=user.region)

    # Apply selected filters
    if selected_year:
        try:
            selected_year = int(selected_year)
            attendance_records = attendance_records.filter(date__year=selected_year)
        except (ValueError, TypeError):
            selected_year = today.year
            attendance_records = attendance_records.filter(date__year=selected_year)
    
    if selected_month:
        try:
            selected_month_int = int(selected_month)
            attendance_records = attendance_records.filter(date__month=selected_month_int)
        except (ValueError, TypeError):
            selected_month = ''
    
    if selected_region_id:
        attendance_records = attendance_records.filter(officer__region_id=selected_region_id)
    
    if selected_station_id:
        attendance_records = attendance_records.filter(officer__prison_station_id=selected_station_id)

    # Generate PDF
    pdf_buffer = generate_attendance_summary_pdf(attendance_records, selected_year, selected_month)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    
    month_str = selected_month if selected_month else 'all'
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{selected_year}_{month_str}.pdf"'
    return response


@login_required
def office_assignment_list_view(request):
    """
    Displays all office assignments with assigned officers, their stations, and ranks.
    """
    user = request.user
    office_assignments = OfficeAssignment.objects.all().prefetch_related('assigned_officers')
    
    # Filter based on user role
    if is_station_level(user) and user.prison_station:
        office_assignments = office_assignments.filter(assigned_officers__prison_station=user.prison_station)
    elif is_regional_level(user) and user.region:
        office_assignments = office_assignments.filter(assigned_officers__region=user.region)
    
    context = {
        'office_assignments': office_assignments,
        'title': 'Office Assignments'
    }
    return render(request, 'hrms/office_assignment_list.html', context)

@login_required
def export_attendance_view(request, date_str):
    """
    Exports attendance data for a specific date as CSV.
    """
    try:
        attendance_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid date format'})
    
    attendances = Attendance.objects.filter(date=attendance_date).select_related('officer', 'officer__prison_station', 'officer__rank')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_{date_str}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Officer Name', 'Service Number', 'Rank', 'Station', 'Status', 
        'Shift', 'Check In', 'Check Out', 'Remarks', 'Marked By'
    ])
    
    for attendance in attendances:
        writer.writerow([
            attendance.officer.full_name,
            attendance.officer.service_number,
            attendance.officer.rank.get_name_display() if attendance.officer.rank else 'N/A',
            attendance.officer.prison_station.name if attendance.officer.prison_station else 'N/A',
            attendance.get_status_display(),
            attendance.get_shift_display(),
            attendance.check_in_time or '',
            attendance.check_out_time or '',
            attendance.remarks,
            attendance.marked_by.username if attendance.marked_by else ''
        ])
    
    return response


@login_required
def export_officer_attendance_view(request, service_number):
    """
    Exports all attendance records for a specific officer as CSV.
    """
    officer = get_object_or_404(Officer, service_number=service_number)
    
    # Check permissions
    if not can_manage_officer_data(request.user, officer.prison_station, officer.region):
        messages.error(request, "You do not have permission to export this officer's attendance records.")
        return redirect('hrms:attendance_record_list')
    
    attendances = Attendance.objects.filter(officer=officer).select_related(
        'officer', 'officer__prison_station', 'officer__rank', 'marked_by'
    ).order_by('-date')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_{officer.service_number}_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Officer Name', 'Service Number', 'Date', 'Status', 'Shift',
        'Check In', 'Check Out', 'Remarks', 'Marked By', 'Created At'
    ])
    
    for attendance in attendances:
        writer.writerow([
            officer.full_name,
            officer.service_number,
            attendance.date,
            attendance.get_status_display(),
            attendance.get_shift_display(),
            attendance.check_in_time or '',
            attendance.check_out_time or '',
            attendance.remarks or '',
            attendance.marked_by.username if attendance.marked_by else 'N/A',
            attendance.created_at.strftime('%Y-%m-%d %H:%M:%S') if attendance.created_at else ''
        ])
    
    return response


# --- Training Wing Views ---

@login_required
@user_passes_test(can_access_training)
def training_dashboard(request):
    """Main dashboard for training wing."""
    context = {
        'total_intakes': TrainingIntake.objects.count(),
        'active_intakes': TrainingIntake.objects.filter(is_active=True).count(),
        'total_recruits': Recruit.objects.count(),
        'active_recruits': Recruit.objects.filter(status__in=['enrolled', 'in_training']).count(),
        'completed_recruits': Recruit.objects.filter(status='graduated').count(),
        'failed_recruits': Recruit.objects.filter(status__in=['dismissed', 'withdrawn']).count(),
        'recent_intakes': TrainingIntake.objects.order_by('-created_at')[:5],
        'recent_recruits': Recruit.objects.order_by('-created_at')[:10],
        'courses': TrainingCourse.objects.filter(is_active=True),
    }
    return render(request, 'hrms/training_dashboard.html', context)

@login_required
@user_passes_test(can_access_training)
def intake_list(request):
    """List all training intakes."""
    intakes = TrainingIntake.objects.all().order_by('-year', 'intake_number')
    
    # Get unique years for filtering
    years = TrainingIntake.objects.values_list('year', flat=True).distinct().order_by('-year')
    
    # Apply filters
    year_filter = request.GET.get('year')
    status_filter = request.GET.get('status')
    search_filter = request.GET.get('search')
    
    if year_filter:
        intakes = intakes.filter(year=year_filter)
    
    if status_filter:
        if status_filter == 'active':
            intakes = intakes.filter(is_active=True)
        elif status_filter == 'inactive':
            intakes = intakes.filter(is_active=False)
    
    if search_filter:
        intakes = intakes.filter(
            Q(description__icontains=search_filter) |
            Q(intake_number__icontains=search_filter)
        )
    
    return render(request, 'hrms/intake_list.html', {
        'intakes': intakes,
        'years': years,
        'selected_year': year_filter,
        'selected_status': status_filter,
        'search_query': search_filter
    })

@login_required
@user_passes_test(can_access_training)
def intake_create(request):
    """Create a new training intake."""
    if request.method == 'POST':
        form = TrainingIntakeForm(request.POST)
        if form.is_valid():
            intake = form.save(commit=False)
            intake.created_by = request.user
            intake.save()
            messages.success(
                request,
                f'Training Intake {intake.get_display_name()} created successfully!'
            )
            return redirect('hrms:intake_detail', pk=intake.pk)

        messages.error(request, 'Please correct the errors below.')
        return render(request, 'hrms/intake_form.html', {
            'now': timezone.now(),
            'form': form,
            'form_data': request.POST,
        })

    return render(request, 'hrms/intake_form.html', {
        'now': timezone.now(),
        'form': TrainingIntakeForm(),
    })

@login_required
@user_passes_test(can_access_training)
def intake_detail(request, pk):
    """View details of a specific intake."""
    intake = get_object_or_404(TrainingIntake, pk=pk)
    recruits = intake.recruits.all().order_by('surname', 'first_name')
    
    # Calculate statistics
    total_recruits = recruits.count()
    enrolled_count = recruits.filter(status='enrolled').count()
    in_training_count = recruits.filter(status='in_training').count()
    graduated_count = recruits.filter(status='graduated').count()
    dismissed_count = recruits.filter(status='dismissed').count()
    withdrawn_count = recruits.filter(status='withdrawn').count()
    
    # Calculate average score
    recruits_with_scores = recruits.exclude(overall_score__isnull=True)
    avg_score = recruits_with_scores.aggregate(Avg('overall_score'))['overall_score__avg'] or 0
    
    # Get top performers
    top_performers = recruits_with_scores.order_by('-overall_score')[:5]
    
    # Get courses for this intake
    courses = TrainingCourse.objects.filter(is_active=True).order_by('category', 'display_order')
    
    context = {
        'intake': intake,
        'recruits': recruits,
        'total_recruits': total_recruits,
        'enrolled_count': enrolled_count,
        'in_training_count': in_training_count,
        'graduated_count': graduated_count,
        'dismissed_count': dismissed_count,
        'withdrawn_count': withdrawn_count,
        'avg_score': round(avg_score, 2),
        'top_performers': top_performers,
        'courses': courses,
    }
    return render(request, 'hrms/intake_detail.html', context)

@login_required
@user_passes_test(can_access_training)
def course_list(request):
    """List all training courses."""
    courses = TrainingCourse.objects.all().order_by('category', 'display_order', 'name')
    
    # Group courses by category
    categories = {}
    for course in courses:
        category_name = course.get_category_display()
        if category_name not in categories:
            categories[category_name] = []
        categories[category_name].append(course)
    
    # Get course statistics
    total_courses = courses.count()
    active_courses = courses.filter(is_active=True).count()
    required_courses = courses.filter(is_required=True).count()
    
    return render(request, 'hrms/course_list.html', {
        'courses': courses,
        'categories': categories,
        'total_courses': total_courses,
        'active_courses': active_courses,
        'required_courses': required_courses,
    })

@login_required
@user_passes_test(can_access_training)
def course_create(request):
    """Create a new training course."""
    if request.method == 'POST':
        form = TrainingCourseForm(request.POST)
        if form.is_valid():
            course = form.save()
            messages.success(request, f'Course "{course.name}" created successfully!')
            return redirect('hrms:course_detail', pk=course.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TrainingCourseForm()
    
    return render(request, 'hrms/course_form.html', {'form': form})


@login_required
@user_passes_test(can_access_training)
def course_update(request, pk):
    """Update an existing training course."""
    course = get_object_or_404(TrainingCourse, pk=pk)
    
    if request.method == 'POST':
        form = TrainingCourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Course "{course.name}" updated successfully!')
            return redirect('hrms:course_detail', pk=course.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TrainingCourseForm(instance=course)
    
    return render(request, 'hrms/course_update.html', {
        'form': form,
        'course': course,
        'available_courses': TrainingCourse.objects.filter(is_active=True).order_by('course_code'),
        'selected_courses': [course.pk for course in TrainingCourse.objects.filter(is_active=True)]
    })

@login_required
@user_passes_test(can_access_training)
def course_detail(request, pk):
    """View details of a specific course."""
    course = get_object_or_404(TrainingCourse, pk=pk)
    
    # Get recruits who have taken this course through marks
    recruit_marks = RecruitMark.objects.filter(course=course).select_related('recruit').order_by('-obtained_marks', 'recruit__intake', 'recruit__surname')
    
    # Calculate statistics
    total_enrollments = recruit_marks.count()
    passed_count = recruit_marks.filter(obtained_marks__gte=F('course__passing_mark')).count()
    failed_count = total_enrollments - passed_count
    avg_score = recruit_marks.aggregate(Avg('obtained_marks'))['obtained_marks__avg'] or 0
    highest_score = recruit_marks.aggregate(Max('obtained_marks'))['obtained_marks__max'] or 0
    
    return render(request, 'hrms/course_detail.html', {
        'course': course,
        'recruit_marks': recruit_marks,
        'total_enrollments': total_enrollments,
        'passed_count': passed_count,
        'failed_count': failed_count,
        'avg_score': round(avg_score, 2),
        'highest_score': highest_score,
    })

@login_required
@user_passes_test(can_access_training)
def recruit_list(request):
    """List all recruits."""
    recruits = Recruit.objects.all().order_by('intake', 'surname', 'first_name')
    intake_filter = request.GET.get('intake')
    status_filter = request.GET.get('status')
    
    if intake_filter:
        recruits = recruits.filter(intake_id=intake_filter)
    if status_filter:
        recruits = recruits.filter(status=status_filter)
    
    intakes = TrainingIntake.objects.all().order_by('-year', 'intake_number')
    return render(request, 'hrms/recruit_list.html', {
        'recruits': recruits,
        'intakes': intakes,
        'selected_intake': intake_filter,
        'selected_status': status_filter
    })

@login_required
@user_passes_test(can_access_training)
def recruit_create(request, intake_pk):
    """Create a new recruit in a specific intake."""
    intake = get_object_or_404(TrainingIntake, pk=intake_pk)
    
    if request.method == 'POST':
        form = RecruitForm(request.POST, intake_pk=intake.pk)
        form.fields['intake'].required = False
        if form.is_valid():
            # Courses are auto-created via Recruit.save()
            recruit = form.save(commit=False)
            recruit.intake = intake
            recruit.created_by = request.user
            recruit.save()
            messages.success(
                request,
                f'Recruit {recruit.full_name} added successfully! Training ID: {recruit.training_id}'
            )
            return redirect('hrms:recruit_detail', pk=recruit.pk)

        messages.error(request, 'Please correct the errors below.')
        return render(request, 'hrms/recruit_form.html', {
            'intake': intake,
            'recruit_types': Recruit.RECRUIT_TYPE_CHOICES,
            'genders': Officer.GENDER_CHOICES,
            'form': form,
            'recruit': form.instance,
        })

    return render(request, 'hrms/recruit_form.html', {
        'intake': intake,
        'recruit_types': Recruit.RECRUIT_TYPE_CHOICES,
        'genders': Officer.GENDER_CHOICES,
        'form': RecruitForm(intake_pk=intake.pk),
    })

@login_required
@user_passes_test(can_access_training)
def recruit_update(request, pk):
    """Edit an existing recruit."""
    recruit = get_object_or_404(Recruit, pk=pk)
    intake = recruit.intake

    if request.method == 'POST':
        form = RecruitForm(request.POST, instance=recruit, intake_pk=intake.pk)
        form.fields['intake'].required = False
        if form.is_valid():
            updated = form.save(commit=False)
            updated.intake = intake
            updated.save()
            messages.success(request, f'Recruit {updated.full_name} updated successfully!')
            return redirect('hrms:recruit_detail', pk=updated.pk)

        messages.error(request, 'Please correct the errors below.')
        return render(request, 'hrms/recruit_form.html', {
            'intake': intake,
            'recruit_types': Recruit.RECRUIT_TYPE_CHOICES,
            'genders': Officer.GENDER_CHOICES,
            'form': form,
            'recruit': recruit,
            'edit_mode': True,
        })

    return render(request, 'hrms/recruit_form.html', {
        'intake': intake,
        'recruit_types': Recruit.RECRUIT_TYPE_CHOICES,
        'genders': Officer.GENDER_CHOICES,
        'form': RecruitForm(instance=recruit, intake_pk=intake.pk),
        'recruit': recruit,
        'edit_mode': True,
    })

@login_required
@user_passes_test(can_access_training)
def recruit_detail(request, pk):
    """View details of a specific recruit."""
    recruit = get_object_or_404(Recruit, pk=pk)
    marks = recruit.marks.all().order_by('course__category', 'course__display_order')
    
    # Calculate summary statistics
    total_courses = marks.count()
    passed_courses = marks.filter(obtained_marks__gte=F('course__passing_mark')).count()
    failed_courses = total_courses - passed_courses
    
    # Get all active courses for progress calculation
    all_courses = TrainingCourse.objects.filter(is_active=True)
    
    # Get ranking info
    ranking_info = recruit.get_current_ranking()
    rank, total_recruits = ranking_info if ranking_info else (None, None)
    
    # Get courses by category
    courses_by_category = {}
    for mark in marks:
        category = mark.course.get_category_display()
        if category not in courses_by_category:
            courses_by_category[category] = []
        courses_by_category[category].append(mark)
    
    context = {
        'recruit': recruit,
        'marks': marks,
        'total_courses': total_courses,
        'passed_courses': passed_courses,
        'failed_courses': failed_courses,
        'rank': rank,
        'total_recruits': total_recruits,
        'all_courses': all_courses,
        'courses_by_category': courses_by_category,
        'progress_percentage': round((recruit.overall_score or 0) / 100 * 100, 1) if recruit.overall_score else 0,
    }
    return render(request, 'hrms/recruit_detail.html', context)

@login_required
@user_passes_test(can_access_training)
def add_mark(request, recruit_pk):
    """Add or update marks for a recruit."""
    recruit = get_object_or_404(Recruit, pk=recruit_pk)
    
    if request.method == 'POST':
        course = get_object_or_404(TrainingCourse, pk=request.POST.get('course'))
        form = RecruitMarkForm(request.POST, course=course)
        if form.is_valid():
            mark, created = RecruitMark.objects.update_or_create(
                recruit=recruit,
                course=course,
                defaults={
                    'obtained_marks': form.cleaned_data['obtained_marks'],
                    'exam_date': form.cleaned_data['exam_date'],
                    'remarks': form.cleaned_data.get('remarks', ''),
                    'recorded_by': request.user
                }
            )

            action = 'created' if created else 'updated'
            messages.success(request, f'Mark for {course.name} {action} successfully!')
            return redirect('hrms:recruit_detail', pk=recruit.pk)

        for field in form:
            for error in field.errors:
                messages.error(request, f'{field.label}: {error}')
    
    # Get all active courses
    all_courses = TrainingCourse.objects.filter(is_active=True).order_by('category', 'display_order')
    
    # Get courses grouped by category
    courses_by_category = {}
    for course in all_courses:
        category = course.get_category_display()
        if category not in courses_by_category:
            courses_by_category[category] = []
        courses_by_category[category].append(course)
    
    return render(request, 'hrms/mark_form.html', {
        'recruit': recruit,
        'courses_by_category': courses_by_category,
        'all_courses': all_courses,
        'today': date.today(),
    })

@login_required
@user_passes_test(can_access_training)
def edit_mark(request, pk):
    """Edit existing marks."""
    mark = get_object_or_404(RecruitMark, pk=pk)
    
    if request.method == 'POST':
        form = RecruitMarkForm(request.POST, instance=mark, course=mark.course)
        if form.is_valid():
            updated_mark = form.save(commit=False)
            updated_mark.recorded_by = request.user
            updated_mark.save()

            messages.success(request, f'Mark for {mark.course.name} updated successfully!')
            return redirect('hrms:recruit_detail', pk=mark.recruit.pk)

        for field in form:
            for error in field.errors:
                messages.error(request, f'{field.label}: {error}')
    else:
        form = RecruitMarkForm(instance=mark, course=mark.course)

    return render(request, 'hrms/mark_edit.html', {
        'mark': mark,
        'recruit': mark.recruit,
        'course': mark.course,
        'form': form,
        'today': date.today(),
    })


# ========== ADDITIONAL TRAINING WING VIEWS ==========

@login_required
@user_passes_test(can_access_training)
def intake_graduation_view(request, pk):
    """View for graduating an intake and assigning service numbers"""
    intake = get_object_or_404(TrainingIntake, pk=pk)
    graduates = intake.recruits.filter(status__in=['enrolled', 'in_training'])

    if request.method == 'POST':
        graduation_form = IntakeGraduationForm(request.POST)
        if not graduation_form.is_valid():
            messages.error(request, 'Please correct the graduation details below.')
            return render(request, 'hrms/intake_graduation.html', {
                'intake': intake,
                'graduates': graduates,
                'total_graduates': graduates.count(),
                'form': graduation_form,
                'title': f'Graduate Intake - {intake.get_display_name()}',
            })

        graduation_date = graduation_form.cleaned_data['graduation_date']
        ceremony_location = graduation_form.cleaned_data['ceremony_location']

        # Freeze the list before updating, otherwise the queryset no longer
        # matches the recruits once their status becomes "graduated".
        graduates_list = list(graduates.order_by('-overall_score', 'surname', 'first_name'))

        if not graduates_list:
            messages.error(request, 'This intake has no recruits ready to graduate.')
            return redirect('hrms:intake_detail', pk=intake.pk)

        for recruit in graduates_list:
            recruit.status = 'graduated'
            recruit.graduated_at = timezone.now()

        # Get starting number
        previous_intake = TrainingIntake.objects.filter(
            year__lt=intake.year
        ).order_by('-year', '-intake_number').first()

        if previous_intake and previous_intake.last_pass_out_number:
            start_number = previous_intake.last_pass_out_number + 1
        else:
            last_officer = Officer.objects.filter(service_number__regex=r'^\d+$').order_by('-service_number').first()
            start_number = (
                int(last_officer.service_number) + 1 if last_officer
                else Recruit.DEFAULT_SERVICE_NUMBER_START
            )
        
        # Assign numbers and calculate rank
        total = len(graduates_list)
        best_recruit = None
        
        for idx, recruit in enumerate(graduates_list, 1):
            recruit.service_number = str(start_number + idx - 1)
            recruit.rank_in_class = idx
            recruit.total_recruits_in_class = total
            recruit.save()
            
            if idx == 1:
                best_recruit = recruit
        
        # Create officer records from graduates
        junior_rank = Rank.objects.filter(name='warder').first()
        officer_count = 0
        for recruit in graduates_list:
            # Check if officer already exists
            if not Officer.objects.filter(service_number=recruit.service_number).exists():
                Officer.objects.create(
                    service_number=recruit.service_number,
                    first_name=recruit.first_name,
                    middle_name=recruit.middle_name,
                    surname=recruit.surname,
                    date_of_birth=recruit.date_of_birth,
                    date_joined_service=graduation_date,
                    gender=recruit.gender,
                    status='active',
                    # Default rank for new recruits (most junior rank)
                    rank=junior_rank,
                    district=recruit.home_district,
                    contact_number=recruit.contact_number,
                    email=recruit.email or None,
                    next_of_kin_name=recruit.next_of_kin,
                    next_of_kin_relationship=recruit.next_of_kin_relationship,
                    next_of_kin_contact=recruit.next_of_kin_contact,
                )
                officer_count += 1
        
        # Update intake
        intake.last_pass_out_number = start_number + total - 1
        intake.is_active = False
        intake.save()

        passed = sum(1 for recruit in graduates_list if recruit.final_grade and recruit.final_grade != 'F')

        # Create graduation batch record
        GraduationBatch.objects.update_or_create(
            intake=intake,
            defaults={
                'graduation_date': graduation_date,
                'ceremony_location': ceremony_location,
                'total_graduates': total,
                'total_passed': passed,
                'total_failed': total - passed,
                'best_performing_recruit': best_recruit,
                'service_number_start': start_number,
                'service_number_end': start_number + total - 1,
            },
        )
        
        messages.success(request, f"Successfully graduated {total} recruits! Created {officer_count} officer records.")
        return redirect('hrms:intake_detail', pk=intake.pk)
    
    context = {
        'intake': intake,
        'graduates': graduates,
        'total_graduates': graduates.count(),
        'form': IntakeGraduationForm(),
        'title': f'Graduate Intake - {intake.get_display_name()}'
    }
    return render(request, 'hrms/intake_graduation.html', context)


@login_required
@user_passes_test(can_access_training)
def class_ranking_view(request, pk):
    """View showing class ranking/order of merit"""
    intake = get_object_or_404(TrainingIntake, pk=pk)
    
    # Get all recruits with marks, ordered by score
    recruits = intake.recruits.filter(
        overall_score__isnull=False
    ).order_by('-overall_score', 'surname', 'first_name')
    
    # Add rank to each
    ranked_recruits = []
    for idx, recruit in enumerate(recruits, 1):
        ranked_recruits.append({
            'rank': idx,
            'recruit': recruit,
            'score': recruit.overall_score,
            'grade': recruit.final_grade,
        })
    
    context = {
        'intake': intake,
        'ranked_recruits': ranked_recruits,
        'title': f'Class Ranking - {intake.get_display_name()}'
    }
    return render(request, 'hrms/class_ranking.html', context)


@login_required
@user_passes_test(can_access_training)
def export_graduation_list_view(request, pk):
    """Export graduation list as CSV"""
    intake = get_object_or_404(TrainingIntake, pk=pk)
    graduates = intake.recruits.filter(status='graduated').order_by('-overall_score', 'surname')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="graduation_list_{intake.get_display_name()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Rank', 'Service Number', 'Full Name', 'Overall Score (%)', 'Grade',
        'Date of Birth', 'Gender', 'Home District', 'Contact Number'
    ])
    
    for idx, recruit in enumerate(graduates, 1):
        writer.writerow([
            idx,
            recruit.service_number or '',
            recruit.full_name,
            recruit.overall_score or '',
            recruit.final_grade or '',
            recruit.date_of_birth,
            recruit.get_gender_display(),
            recruit.home_district,
            recruit.contact_number
        ])
    
    return response


@login_required
@user_passes_test(can_access_training)
def bulk_add_marks_view(request, module_pk=None):
    """
    Enhanced bulk add marks with both manual entry and CSV import options.
    """
    # Get intake from GET parameter or POST data
    intake_pk = request.GET.get('intake_pk') or request.POST.get('intake_pk')
    if not intake_pk:
        # Redirect to intake selection page if intake_pk is not provided
        intakes = TrainingIntake.objects.filter(is_active=True).order_by('-start_date')
        if not intakes.exists():
            messages.error(request, "No active training intakes found.")
            return redirect('hrms:training')
        if intakes.count() == 1:
            return redirect(f'{request.path}?intake_pk={intakes.first().pk}')
        # Show intake selection page
        return render(request, 'hrms/intake_selection.html', {
            'intakes': intakes,
            'action': 'bulk_add_marks',
            'title': 'Select Training Intake - Bulk Add Marks'
        })
    intake = get_object_or_404(TrainingIntake, pk=intake_pk)
    recruits = intake.recruits.filter(status__in=['enrolled', 'in_training'])
    
    if recruits.exists():
        courses = TrainingCourse.objects.filter(is_active=True).order_by('course_code')
    else:
        courses = TrainingCourse.objects.none()
    
    selected_course = None
    if module_pk:
        selected_course = get_object_or_404(TrainingCourse, pk=module_pk)
    
    # For CSV preview
    preview_data = None
    if request.method == 'POST' and 'preview_csv' in request.POST:
        csv_file = request.FILES.get('csv_file')
        if csv_file:
            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                preview_data = list(reader)[:10]  # Preview first 10 rows
            except Exception as e:
                messages.error(request, f"Error previewing CSV: {str(e)}")
    
    if request.method == 'POST' and 'submit_marks' in request.POST:
        course_id = request.POST.get('module')
        exam_date = request.POST.get('exam_date')
        selected_course = get_object_or_404(TrainingCourse, pk=course_id)
        
        success_count = 0
        for recruit in recruits:
            obtained_marks = request.POST.get(f'marks_{recruit.id}')
            if obtained_marks is not None and obtained_marks != '':
                try:
                    marks_value = float(obtained_marks)
                    # Validate marks range
                    if 0 <= marks_value <= selected_course.total_marks:
                        RecruitMark.objects.update_or_create(
                            recruit=recruit,
                            course=selected_course,
                            defaults={
                                'obtained_marks': marks_value,
                                'exam_date': exam_date,
                                'recorded_by': request.user
                            }
                        )
                        success_count += 1
                except ValueError:
                    pass
        
        # Recalculate overall scores
        for recruit in recruits:
            recruit.calculate_final_results()
        
        messages.success(request, f"Successfully saved marks for {success_count} recruits in course '{selected_course.name}'.")
        return redirect('hrms:intake_detail', pk=intake.pk)
    
    from datetime import date
    
    context = {
        'intake': intake,
        'recruits': recruits,
        'modules': courses,  # Changed to courses for template compatibility
        'selected_module': selected_course,  # Keep as selected_module for template compatibility
        'preview_data': preview_data,
        'title': f'Bulk Add Marks - {intake.get_display_name()}',
        'today': date.today(),
        'csv_help': """
            CSV Format:
            - recruit_training_id: The training ID of the recruit (e.g., R-2024-001)
            - course_code: Course code (MPS101, MPS102, MPR103, MPC104, MPH105, MPW106)
            - obtained_marks: Score obtained (0-100)
            - exam_date: Date of exam in YYYY-MM-DD format
        """
    }
    return render(request, 'hrms/bulk_marks_form.html', context)


# ========== CSV/EXCEL IMPORT VIEWS ==========

@login_required
@user_passes_test(can_access_training)
def bulk_marks_import_csv_view(request):
    """
    Import marks for all recruits in an intake via CSV upload.
    CSV Format: recruit_training_id,course_code,obtained_marks,exam_date
    """
    # Get intake from GET parameter or POST data
    intake_pk = request.GET.get('intake_pk') or request.POST.get('intake_pk')
    if not intake_pk:
        # Redirect to intake selection page if intake_pk is not provided
        intakes = TrainingIntake.objects.filter(is_active=True).order_by('-start_date')
        if not intakes.exists():
            messages.error(request, "No active training intakes found.")
            return redirect('hrms:training')
        if intakes.count() == 1:
            return redirect(f'{request.path}?intake_pk={intakes.first().pk}')
        # Show intake selection page
        return render(request, 'hrms/intake_selection.html', {
            'intakes': intakes,
            'action': 'bulk_marks_import_csv',
            'title': 'Select Training Intake - Bulk Import Marks via CSV'
        })
    
    intake = get_object_or_404(TrainingIntake, pk=intake_pk)
    recruits = intake.recruits.filter(status__in=['enrolled', 'in_training'])
    
    # Get courses for the intake
    if recruits.exists():
        courses = {c.course_code: c for c in TrainingCourse.objects.filter(is_active=True)}
    else:
        courses = {}
    
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Please select a CSV file to upload.")
            return redirect(f'{reverse("hrms:bulk_marks_import_csv")}?intake_pk={intake_pk}')
        
        # Validate file type
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a valid CSV file.")
            return redirect(f'{reverse("hrms:bulk_marks_import_csv")}?intake_pk={intake_pk}')
        
        # Process CSV
        try:
            # Read CSV file
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            # Statistics for feedback
            total_records = 0
            successful_records = 0
            failed_records = []
            marks_created = 0
            marks_updated = 0
            unknown_recruits = []
            unknown_modules = []
            
            # Process each row
            for row_num, row in enumerate(reader, start=2):  # Start at 2 for row numbers (header is row 1)
                total_records += 1
                
                # Extract data
                training_id = row.get('recruit_training_id') or row.get('training_id') or row.get('recruit_id')
                course_code = row.get('course_code') or row.get('module_code') or row.get('module')
                obtained_marks = row.get('obtained_marks') or row.get('marks') or row.get('score')
                exam_date = row.get('exam_date') or row.get('date')
                
                # Validate required fields
                if not training_id:
                    failed_records.append({'row': row_num, 'error': 'Missing recruit identifier'})
                    continue
                
                if not course_code:
                    failed_records.append({'row': row_num, 'error': 'Missing course code'})
                    continue
                
                if not obtained_marks:
                    failed_records.append({'row': row_num, 'error': 'Missing marks'})
                    continue
                
                # Find recruit
                recruit = None
                # Try multiple field types for recruit lookup
                recruit = recruits.filter(training_id=training_id).first()
                if not recruit:
                    recruit = recruits.filter(service_number=training_id).first()
                if not recruit:
                    recruit = recruits.filter(
                        Q(first_name__icontains=training_id) | 
                        Q(surname__icontains=training_id)
                    ).first()
                
                if not recruit:
                    unknown_recruits.append({'row': row_num, 'training_id': training_id})
                    failed_records.append({'row': row_num, 'error': f'Recruit not found: {training_id}'})
                    continue
                
                # Find course
                course = courses.get(course_code)
                if not course:
                    # Try case-insensitive search
                    course = next((c for c in courses.values() if c.course_code.lower() == course_code.lower()), None)
                
                if not course:
                    unknown_modules.append({'row': row_num, 'module_code': course_code})
                    failed_records.append({'row': row_num, 'error': f'Course not found: {course_code}'})
                    continue
                
                # Parse exam date
                try:
                    # Try different date formats
                    exam_date_parsed = None
                    if exam_date:
                        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                            try:
                                exam_date_parsed = datetime.strptime(str(exam_date).strip(), fmt).date()
                                break
                            except ValueError:
                                continue
                except Exception:
                    exam_date_parsed = date.today()
                
                if not exam_date_parsed:
                    exam_date_parsed = date.today()
                
                # Parse marks
                try:
                    marks_value = float(obtained_marks)
                    if marks_value < 0 or marks_value > course.total_marks:
                        failed_records.append({'row': row_num, 'error': f'Marks must be between 0 and {course.total_marks}'})
                        continue
                except ValueError:
                    failed_records.append({'row': row_num, 'error': f'Invalid marks value: {obtained_marks}'})
                    continue
                
                # Create or update mark
                mark, created = RecruitMark.objects.update_or_create(
                    recruit=recruit,
                    course=course,
                    defaults={
                        'obtained_marks': marks_value,
                        'exam_date': exam_date_parsed,
                        'remarks': f"Imported from CSV on {date.today()}",
                        'recorded_by': request.user
                    }
                )
                
                if created:
                    marks_created += 1
                else:
                    marks_updated += 1
                
                successful_records += 1
            
            # Recalculate overall scores for all recruits after import
            recalculated_count = 0
            for recruit in recruits:
                recruit.calculate_final_results()
                recalculated_count += 1
            
            # Prepare success message
            message = f"""
            CSV Import Complete!
            - Total records processed: {total_records}
            - Successful: {successful_records}
            - Marks created: {marks_created}
            - Marks updated: {marks_updated}
            - Recruits recalculated: {recalculated_count}
            """
            
            if failed_records:
                message += f"\n- Failed: {len(failed_records)} records"
                messages.warning(request, message)
                # Store failed records in session for detailed download
                request.session['import_failures'] = failed_records
                request.session['unknown_recruits'] = unknown_recruits
                request.session['unknown_modules'] = unknown_modules
            else:
                messages.success(request, message)
            
            return redirect('hrms:intake_detail', pk=intake.pk)
            
        except Exception as e:
            messages.error(request, f"Error processing CSV file: {str(e)}")
            return redirect(f'{reverse("hrms:bulk_marks_import_csv")}?intake_pk={intake_pk}')
    
    # GET request - show form
    # Generate template CSV
    sample_data = []
    for recruit in recruits[:5]:  # Show first 5 as sample
        for course_code in courses.keys():
            sample_data.append({
                'recruit_training_id': recruit.training_id,
                'recruit_name': recruit.full_name,
                'course_code': course_code,
                'obtained_marks': '',
                'exam_date': date.today().strftime('%Y-%m-%d')
            })
    
    modules = list(courses.values())

    context = {
        'intake': intake,
        'recruits': recruits,
        'modules': modules,
        'sample_data': sample_data,
        'total_recruits': recruits.count(),
        'total_modules': len(modules),
        'expected_rows': recruits.count() * len(modules),
        'title': f'Bulk Import Marks via CSV - {intake.get_display_name()}'
    }
    return render(request, 'hrms/bulk_marks_import_csv.html', context)

@login_required
@user_passes_test(can_access_training)
def download_csv_template_view(request):
    """
    Download a CSV template for marks import.
    """
    # Get intake from GET parameter
    intake_pk = request.GET.get('intake_pk')
    if not intake_pk:
        return JsonResponse({'error': 'Intake ID is required'}, status=400)
    intake = get_object_or_404(TrainingIntake, pk=intake_pk)
    recruits = intake.recruits.filter(status__in=['enrolled', 'in_training'])
    
    if recruits.exists():
        courses = TrainingCourse.objects.filter(is_active=True).order_by('course_code')
    else:
        courses = TrainingCourse.objects.none()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="marks_template_{intake.get_display_name()}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'recruit_training_id', 'recruit_name', 'course_code', 'course_name', 
        'obtained_marks', 'exam_date', 'remarks'
    ])
    
    # Write sample data for each recruit and course
    for recruit in recruits:
        for course in courses:
            writer.writerow([
                recruit.training_id,
                recruit.full_name,
                course.course_code,
                course.name,
                '',  # obtained_marks - to be filled
                date.today().strftime('%Y-%m-%d'),
                'Enter marks here (0-{})'.format(course.total_marks)
            ])
    
    return response


@login_required
@user_passes_test(can_access_training)
def download_import_failures_view(request):
    """
    Download a CSV file containing failed import records for correction.
    """
    failed_records = request.session.get('import_failures', [])
    unknown_recruits = request.session.get('unknown_recruits', [])
    unknown_modules = request.session.get('unknown_modules', [])
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="import_failures.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Row Number', 'Error Type', 'Details', 'Suggested Correction'])
    
    for failure in failed_records:
        writer.writerow([
            failure.get('row', ''),
            'Validation Error',
            failure.get('error', ''),
            'Please check the data format'
        ])
    
    for unknown in unknown_recruits:
        writer.writerow([
            unknown.get('row', ''),
            'Unknown Recruit',
            f"Training ID: {unknown.get('training_id', '')}",
            'Verify training ID exists in the system'
        ])
    
    for unknown in unknown_modules:
        writer.writerow([
            unknown.get('row', ''),
            'Unknown Course',
            f"Course Code: {unknown.get('module_code', '')}",
            f'Valid course codes: MPS101, MPS102, MPR103, MPC104, MPH105, MPW106'
        ])
    
    # Clear session after download
    request.session.pop('import_failures', None)
    request.session.pop('unknown_recruits', None)
    request.session.pop('unknown_modules', None)
    
    return response


@login_required
@user_passes_test(can_access_training)
def bulk_marks_import_excel_view(request):
    """
    Import marks from Excel file (.xlsx) for better handling of large datasets.
    """
    # Get intake from GET parameter or POST data
    intake_pk = request.GET.get('intake_pk') or request.POST.get('intake_pk')
    if not intake_pk:
        # Redirect to intake selection page if intake_pk is not provided
        intakes = TrainingIntake.objects.filter(is_active=True).order_by('-start_date')
        if not intakes.exists():
            messages.error(request, "No active training intakes found.")
            return redirect('hrms:training')
        if intakes.count() == 1:
            return redirect(f'{request.path}?intake_pk={intakes.first().pk}')
        # Show intake selection page
        return render(request, 'hrms/intake_selection.html', {
            'intakes': intakes,
            'action': 'bulk_marks_import_excel',
            'title': 'Select Training Intake - Bulk Import Marks via Excel'
        })
    intake = get_object_or_404(TrainingIntake, pk=intake_pk)
    recruits = intake.recruits.filter(status__in=['enrolled', 'in_training'])
    
    if recruits.exists():
        courses = {c.course_code: c for c in TrainingCourse.objects.filter(is_active=True)}
    else:
        courses = {}
    
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select an Excel file to upload.")
            return redirect(f'{reverse("hrms:bulk_marks_import_excel")}?intake_pk={intake_pk}')
        
        if not (excel_file.name.endswith('.xlsx') or excel_file.name.endswith('.xls')):
            messages.error(request, "Please upload a valid Excel file (.xlsx or .xls).")
            return redirect(f'{reverse("hrms:bulk_marks_import_excel")}?intake_pk={intake_pk}')
        
        try:
            # Read Excel file using pandas
            df = pd.read_excel(excel_file)
            
            # Standardize column names
            df.columns = df.columns.str.lower()
            
            total_records = len(df)
            successful_records = 0
            marks_created = 0
            marks_updated = 0
            failed_records = []
            
            for idx, row in df.iterrows():
                # Get values with flexible column mapping
                training_id = row.get('recruit_training_id') or row.get('training_id') or row.get('recruit_id')
                course_code = row.get('course_code') or row.get('module_code') or row.get('module')
                obtained_marks = row.get('obtained_marks') or row.get('marks') or row.get('score')
                exam_date = row.get('exam_date') or row.get('date')
                
                if pd.isna(training_id):
                    failed_records.append({'row': idx + 2, 'error': 'Missing recruit identifier'})
                    continue
                
                if pd.isna(course_code):
                    failed_records.append({'row': idx + 2, 'error': 'Missing course code'})
                    continue
                
                if pd.isna(obtained_marks):
                    failed_records.append({'row': idx + 2, 'error': 'Missing marks'})
                    continue
                
                # Find recruit
                recruit = recruits.filter(training_id=str(training_id).strip()).first()
                if not recruit:
                    recruit = recruits.filter(service_number=str(training_id).strip()).first()
                
                if not recruit:
                    failed_records.append({'row': idx + 2, 'error': f'Recruit not found: {training_id}'})
                    continue
                
                # Find course
                course = courses.get(str(course_code).strip())
                if not course:
                    course = next((c for c in courses.values() if c.course_code.lower() == str(course_code).lower()), None)
                
                if not course:
                    failed_records.append({'row': idx + 2, 'error': f'Course not found: {course_code}'})
                    continue
                
                # Parse exam date
                try:
                    if pd.notna(exam_date):
                        if isinstance(exam_date, str):
                            exam_date_parsed = datetime.strptime(exam_date, '%Y-%m-%d').date()
                        else:
                            exam_date_parsed = exam_date.date() if hasattr(exam_date, 'date') else exam_date
                    else:
                        exam_date_parsed = date.today()
                except Exception:
                    exam_date_parsed = date.today()
                
                # Parse marks
                try:
                    marks_value = float(obtained_marks)
                except (ValueError, TypeError):
                    failed_records.append({'row': idx + 2, 'error': f'Invalid marks: {obtained_marks}'})
                    continue
                
                # Create or update mark
                mark, created = RecruitMark.objects.update_or_create(
                    recruit=recruit,
                    course=course,
                    defaults={
                        'obtained_marks': marks_value,
                        'exam_date': exam_date_parsed,
                        'remarks': f"Imported from Excel on {date.today()}",
                        'recorded_by': request.user
                    }
                )
                
                if created:
                    marks_created += 1
                else:
                    marks_updated += 1
                
                successful_records += 1
            
            # Recalculate overall scores
            recalculated_count = 0
            for recruit in recruits:
                recruit.calculate_final_results()
                recalculated_count += 1
            
            # Prepare success message
            message = f"""
            Excel Import Complete!
            - Total records processed: {total_records}
            - Successful: {successful_records}
            - Marks created: {marks_created}
            - Marks updated: {marks_updated}
            - Recruits recalculated: {recalculated_count}
            """
            
            if failed_records:
                message += f"\n- Failed: {len(failed_records)} records. Check the failures CSV for details."
                # Store failed records in session
                request.session['excel_failures'] = failed_records
                messages.warning(request, message)
            else:
                messages.success(request, message)
            
            return redirect('hrms:intake_detail', pk=intake.pk)
            
        except Exception as e:
            messages.error(request, f"Error processing Excel file: {str(e)}")
            return redirect(f'{reverse("hrms:bulk_marks_import_excel")}?intake_pk={intake_pk}')
    
    context = {
        'intake': intake,
        'recruits': recruits,
        'modules': courses,  # Keep as modules for template compatibility
        'total_recruits': recruits.count(),
        'total_modules': len(courses),
        'title': f'Bulk Import Marks via Excel - {intake.get_display_name()}'
    }
    return render(request, 'hrms/bulk_marks_import_excel.html', context)


@login_required
@user_passes_test(can_access_training)
def marks_import_status_view(request):
    """
    View to check the status of a marks import job.
    """
    from django.core.cache import cache
    
    import_status = cache.get('marks_import_status', {
        'status': 'idle',
        'progress': 0,
        'total': 0,
        'completed': 0,
        'message': ''
    })
    
    return JsonResponse(import_status)


# --- ICT Personnel User Management Views ---

@login_required
@user_passes_test(is_ict_personnel)
def ict_user_list_view(request):
    """
    Displays list of all users in the system for ICT Personnel management.
    """
    users = CustomUser.objects.all().order_by('username')
    
    # Filter by role if specified
    role_filter = request.GET.get('role')
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Filter by region if specified
    region_filter = request.GET.get('region')
    if region_filter:
        users = users.filter(region_id=region_filter)
    
    # Filter by station if specified
    station_filter = request.GET.get('station')
    if station_filter:
        users = users.filter(prison_station_id=station_filter)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    regions = Region.objects.all()
    stations = PrisonStation.objects.all()
    
    context = {
        'users': users,
        'regions': regions,
        'stations': stations,
        'role_filter': role_filter,
        'region_filter': region_filter,
        'station_filter': station_filter,
        'search_query': search_query,
        'title': 'User Management - ICT Personnel',
    }
    
    return render(request, 'hrms/ict_user_list.html', context)


@login_required
@user_passes_test(is_ict_personnel)
def ict_user_create_view(request):
    """
    Allows ICT Personnel to create new user accounts.
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role')
        region_id = request.POST.get('region')
        station_id = request.POST.get('station')
        password = request.POST.get('password')
        
        try:
            # Check if username already exists
            if CustomUser.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return redirect('hrms:ict_user_create')
            
            # Create new user
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
            )
            
            # Assign region and station if provided
            if region_id:
                user.region = Region.objects.get(id=region_id)
            if station_id:
                user.prison_station = PrisonStation.objects.get(id=station_id)
            
            user.save()
            messages.success(request, f'User {username} created successfully.')
            return redirect('hrms:ict_user_list')
            
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
    
    regions = Region.objects.all()
    stations = PrisonStation.objects.all()
    
    context = {
        'regions': regions,
        'stations': stations,
        'title': 'Create User - ICT Personnel',
    }
    
    return render(request, 'hrms/ict_user_create.html', context)


@login_required
@user_passes_test(is_ict_personnel)
def ict_user_update_view(request, user_id):
    """
    Allows ICT Personnel to update user accounts.
    """
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        user.email = request.POST.get('email', user.email)
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.role = request.POST.get('role', user.role)
        
        region_id = request.POST.get('region')
        if region_id:
            user.region = Region.objects.get(id=region_id)
        else:
            user.region = None
        
        station_id = request.POST.get('station')
        if station_id:
            user.prison_station = PrisonStation.objects.get(id=station_id)
        else:
            user.prison_station = None
        
        # Update password if provided
        password = request.POST.get('password')
        if password:
            user.set_password(password)
        
        # Handle active/inactive status
        is_active = request.POST.get('is_active')
        user.is_active = (is_active == 'on')
        
        user.save()
        messages.success(request, f'User {user.username} updated successfully.')
        return redirect('hrms:ict_user_list')
    
    regions = Region.objects.all()
    stations = PrisonStation.objects.all()
    
    context = {
        'user_to_edit': user,
        'regions': regions,
        'stations': stations,
        'title': f'Update User - {user.username}',
    }
    
    return render(request, 'hrms/ict_user_update.html', context)


@login_required
@user_passes_test(is_ict_personnel)
def ict_user_delete_view(request, user_id):
    """
    Allows ICT Personnel to delete user accounts.
    """
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User {username} deleted successfully.')
        return redirect('hrms:ict_user_list')
    
    context = {
        'user_to_delete': user,
        'title': f'Delete User - {user.username}',
    }
    
    return render(request, 'hrms/ict_user_delete.html', context)


@login_required
@user_passes_test(is_ict_personnel)
def ict_user_detail_view(request, user_id):
    """
    Displays detailed information about a user for ICT Personnel.
    """
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Get user's officer profile if exists
    officer_profile = None
    try:
        officer_profile = user.officer_profile
    except:
        pass
    
    # Get user's recent activities
    recent_files = OfficerDocument.objects.filter(uploaded_by=user)[:5]
    recent_promotions = PromotionHistory.objects.filter(recorded_by=user)[:5]
    recent_transfers = TransferHistory.objects.filter(recorded_by=user)[:5]
    
    context = {
        'user': user,
        'officer_profile': officer_profile,
        'recent_files': recent_files,
        'recent_promotions': recent_promotions,
        'recent_transfers': recent_transfers,
        'title': f'User Details - {user.username}',
    }
    
    return render(request, 'hrms/ict_user_detail.html', context)


@login_required
@user_passes_test(is_ict_personnel)
def ict_system_logs_view(request):
    """
    Displays system logs and activities for ICT Personnel monitoring.
    """
    # Get recent activities across the system
    recent_officer_creations = Officer.objects.order_by('-created_at')[:20]
    recent_leave_requests = LeaveRequest.objects.order_by('-requested_at')[:20]
    recent_file_uploads = OfficerDocument.objects.order_by('-uploaded_at')[:20]
    recent_promotions = PromotionHistory.objects.order_by('-promotion_date')[:20]
    recent_transfers = TransferHistory.objects.order_by('-transfer_date')[:20]
    
    context = {
        'recent_officer_creations': recent_officer_creations,
        'recent_leave_requests': recent_leave_requests,
        'recent_file_uploads': recent_file_uploads,
        'recent_promotions': recent_promotions,
        'recent_transfers': recent_transfers,
        'title': 'System Logs - ICT Personnel',
    }
    
    return render(request, 'hrms/ict_system_logs.html', context)

