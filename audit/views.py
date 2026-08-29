"""
Views for audit trail access and reporting.
Only accessible by super admins and IT/Compliance staff.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
import csv
import json

from audit.models import AuditLog, AuditLogSummary
from accounts.models import CustomUser


def is_audit_admin(user):
    """Check if user is superuser or IT/Compliance staff."""
    return user.is_superuser or user.is_staff


@login_required
@user_passes_test(is_audit_admin)
def audit_log_list(request):
    """Display audit log entries with filters."""
    logs = AuditLog.objects.all()
    
    # Apply filters
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    model_filter = request.GET.get('model', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    if user_filter:
        logs = logs.filter(user_id=user_filter)
    
    if model_filter:
        logs = logs.filter(model_name=model_filter)
    
    if date_from:
        try:
            date_from_dt = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__gte=date_from_dt)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_dt = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__lte=date_to_dt)
        except ValueError:
            pass
    
    if search_query:
        logs = logs.filter(
            Q(object_str__icontains=search_query) |
            Q(model_name__icontains=search_query) |
            Q(ip_address__icontains=search_query)
        )
    
    # Get unique values for filter dropdowns
    actions = AuditLog.ACTION_CHOICES
    users = CustomUser.objects.filter(audit_logs__isnull=False).distinct()
    models_list = AuditLog.objects.values_list('model_name', flat=True).distinct()
    
    # Pagination
    page_num = request.GET.get('page', 1)
    per_page = 50
    total = logs.count()
    
    try:
        page_num = int(page_num)
    except ValueError:
        page_num = 1
    
    start = (page_num - 1) * per_page
    end = start + per_page
    
    logs_page = logs[start:end]
    
    context = {
        'logs': logs_page,
        'total_logs': total,
        'actions': actions,
        'users': users,
        'models': models_list,
        'current_page': page_num,
        'total_pages': (total + per_page - 1) // per_page,
        'per_page': per_page,
        'title': 'Audit Trail Logs'
    }
    
    return render(request, 'audit/audit_log_list.html', context)


@login_required
@user_passes_test(is_audit_admin)
def audit_log_detail(request, pk):
    """Display detailed audit log entry."""
    log = AuditLog.objects.get(pk=pk)
    
    context = {
        'log': log,
        'title': f'Audit Log Detail - {log.id}'
    }
    
    return render(request, 'audit/audit_log_detail.html', context)


@login_required
@user_passes_test(is_audit_admin)
def audit_summary(request):
    """Display audit summary dashboard."""
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    
    # Get summary stats
    total_logs = AuditLog.objects.count()
    logs_today = AuditLog.objects.filter(timestamp__date=today).count()
    logs_this_month = AuditLog.objects.filter(
        timestamp__date__gte=today.replace(day=1)
    ).count()
    logs_last_30 = AuditLog.objects.filter(
        timestamp__date__gte=last_30_days
    ).count()
    
    # Action breakdown
    action_stats = AuditLog.objects.values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # User activity
    user_stats = AuditLog.objects.filter(
        timestamp__date__gte=last_30_days
    ).values('user__username').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Model changes
    model_stats = AuditLog.objects.filter(
        timestamp__date__gte=last_30_days
    ).values('model_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Recent changes
    recent_logs = AuditLog.objects.all()[:20]
    
    # Suspicious activity (multiple failed actions, high frequency changes)
    high_volume_users = AuditLog.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=1)
    ).values('user').annotate(count=Count('id')).filter(count__gt=50)
    
    context = {
        'total_logs': total_logs,
        'logs_today': logs_today,
        'logs_this_month': logs_this_month,
        'logs_last_30': logs_last_30,
        'action_stats': action_stats,
        'user_stats': user_stats,
        'model_stats': model_stats,
        'recent_logs': recent_logs,
        'high_volume_users': high_volume_users,
        'title': 'Audit Summary Dashboard'
    }
    
    return render(request, 'audit/audit_summary.html', context)


@login_required
@user_passes_test(is_audit_admin)
def audit_log_export(request):
    """Export audit logs as CSV."""
    today = timezone.now().date()
    # Get filters from request
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    action_filter = request.GET.get('action', '')
    model_filter = request.GET.get('model', '')
    
    logs = AuditLog.objects.all()
    
    # Apply filters
    if date_from:
        try:
            date_from_dt = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__gte=date_from_dt)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_dt = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__lte=date_to_dt)
        except ValueError:
            pass
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    if model_filter:
        logs = logs.filter(model_name=model_filter)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="audit_logs_{today.isoformat()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'Action', 'User', 'Model', 'Object ID', 'Object',
        'IP Address', 'Request Method', 'Request Path', 'Changed Fields',
        'Old Values', 'New Values'
    ])
    
    for log in logs:
        writer.writerow([
            log.timestamp.isoformat(),
            log.action,
            log.user.username if log.user else 'System',
            log.model_name,
            log.object_id or '',
            log.object_str,
            log.ip_address or '',
            log.request_method,
            log.request_path,
            ','.join(log.changed_fields) if log.changed_fields else '',
            json.dumps(log.old_values) if log.old_values else '',
            json.dumps(log.new_values) if log.new_values else ''
        ])
    
    return response


@login_required
@user_passes_test(is_audit_admin)
def audit_log_by_user(request, user_id):
    """Display all audit logs for a specific user."""
    user = CustomUser.objects.get(id=user_id)
    logs = AuditLog.objects.filter(user=user)
    
    # Apply date filters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        try:
            date_from_dt = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__gte=date_from_dt)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_dt = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__lte=date_to_dt)
        except ValueError:
            pass
    
    # Summary for this user
    action_stats = logs.values('action').annotate(count=Count('id')).order_by('-count')
    model_stats = logs.values('model_name').annotate(count=Count('id')).order_by('-count')
    
    context = {
        'user_obj': user,
        'logs': logs[:100],  # Show latest 100
        'total_logs': logs.count(),
        'action_stats': action_stats,
        'model_stats': model_stats,
        'title': f'Audit Logs - {user.get_full_name()}'
    }
    
    return render(request, 'audit/audit_log_by_user.html', context)
