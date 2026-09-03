from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.db.models import Q, Count
import io
import csv
import json
from datetime import datetime, date

from prison.models import PrisonStation
from accounts.models import CustomUser
from .models import (
    ReturnTemplate, ReturnSubmission, ReturnData, 
    RegionalReturnSummary, StationReturnStatus,
    MonthlySubmissionTracker, ReturnTypeStatus
)
from .forms import (
    ReturnSubmissionForm, ReturnTemplateForm, 
    ReturnsFilterForm, PeriodSelectionForm,
    MonthlyTrackingForm
)
from .services import (
    ReturnProcessingService, DefaultTemplateService, 
    ReturnReportService, MonthlySubmissionService
)
from .pdf_service import ReturnPDFService


# ============ HELPER FUNCTIONS ============

def _get_user_station(user):
    """Get user's assigned station or None."""
    if hasattr(user, 'prison_station') and user.prison_station:
        return user.prison_station
    return None


def _is_station_user(user):
    """Check if user is assigned to a station."""
    return _get_user_station(user) is not None


def _is_region_user(user):
    """Check if user has region permissions."""
    return hasattr(user, 'region') and user.region is not None


def _get_return_categories():
    """Get return category choices."""
    return ReturnTemplate.CATEGORY_CHOICES


def _parse_period(period_str):
    """Parse period string to year and month."""
    try:
        parts = period_str.split('-')
        year = int(parts[0])
        month = int(parts[1])
        return year, month
    except (ValueError, IndexError):
        return timezone.now().year, timezone.now().month


def _get_period_from_request(request):
    """Get period from request GET/POST parameters."""
    period = request.GET.get('period') or request.POST.get('period')
    if period:
        return period
    return timezone.now().strftime('%Y-%m')


# ============ DASHBOARD VIEW ============

@login_required
def returns_dashboard(request):
    """Returns dashboard showing overview of submissions and status."""
    user = request.user
    
    # Get current period
    today = timezone.now()
    period = today.strftime('%Y-%m')
    year = today.year
    month = today.month

    # Get counts
    total_templates = ReturnTemplate.objects.filter(is_active=True).count()

    # Filter submissions based on user
    submissions = ReturnSubmission.objects.all()
    if not user.is_superuser:
        if _is_station_user(user):
            submissions = submissions.filter(prison_station=user.prison_station)
        elif _is_region_user(user):
            submissions = submissions.filter(prison_station__region=user.region)

    total_submissions = submissions.count()
    pending_submissions = submissions.filter(status='pending').count()
    approved_submissions = submissions.filter(status='approved').count()
    rejected_submissions = submissions.filter(status='rejected').count()

    # Current month submissions
    current_month_submissions = submissions.filter(year=year, month=month).count()
    
    # Recent submissions
    recent_submissions = submissions.select_related(
        'template', 'prison_station', 'submitted_by'
    ).order_by('-submitted_at')[:10]

    # Station status for current period
    station_statuses = StationReturnStatus.objects.filter(
        year=year,
        month=month
    ).select_related('prison_station', 'template')

    # Get monthly tracker if exists
    monthly_tracker = MonthlySubmissionTracker.objects.filter(
        year=year,
        month=month
    ).select_related('prison_station')

    # Get missing stations
    missing_stations = StationReturnStatus.objects.filter(
        year=year,
        month=month,
        status='not_submitted'
    ).select_related('prison_station', 'template')[:10]

    # Get year months for navigation
    months = []
    for m in range(1, 13):
        month_count = submissions.filter(year=year, month=m).count()
        months.append({
            'month': m,
            'name': date(year, m, 1).strftime('%B'),
            'count': month_count,
            'is_current': m == month,
        })

    context = {
        'total_templates': total_templates,
        'total_submissions': total_submissions,
        'pending_submissions': pending_submissions,
        'approved_submissions': approved_submissions,
        'rejected_submissions': rejected_submissions,
        'current_month_submissions': current_month_submissions,
        'recent_submissions': recent_submissions,
        'station_statuses': station_statuses[:10],
        'monthly_tracker': monthly_tracker[:5],
        'missing_stations': missing_stations,
        'months': months,
        'year': year,
        'month': month,
        'period': period,
        'page_title': 'Returns Dashboard',
    }
    return render(request, 'returns/dashboard.html', context)


# ============ TEMPLATE MANAGEMENT VIEWS ============

@login_required
def template_list(request):
    """List available return templates."""
    user = request.user

    # Determine allowed templates based on user role
    templates = ReturnTemplate.objects.filter(is_active=True).order_by('category', 'name')

    context = {
        'templates': templates,
        'page_title': 'Return Templates',
    }
    return render(request, 'returns/template_list.html', context)


@login_required
def template_create(request):
    """Create a new return template."""
    if not (request.user.is_superuser or hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()):
        raise PermissionDenied("You do not have permission to create templates.")

    if request.method == 'POST':
        form = ReturnTemplateForm(request.POST, request.FILES)

        if form.is_valid():
            template = form.save()
            messages.success(request, f"Template '{template.name}' created successfully.")
            return redirect('returns:template_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ReturnTemplateForm()

    context = {
        'form': form,
        'page_title': 'Create Return Template',
    }
    return render(request, 'returns/template_form.html', context)


@login_required
def template_edit(request, pk):
    """Edit an existing return template."""
    if not (request.user.is_superuser or hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()):
        raise PermissionDenied("You do not have permission to edit templates.")

    template = get_object_or_404(ReturnTemplate, pk=pk)

    if request.method == 'POST':
        form = ReturnTemplateForm(request.POST, request.FILES, instance=template)

        if form.is_valid():
            template = form.save()
            messages.success(request, f"Template '{template.name}' updated successfully.")
            return redirect('returns:template_list')
    else:
        form = ReturnTemplateForm(instance=template)

    context = {
        'form': form,
        'template': template,
        'page_title': f'Edit Template: {template.name}',
    }
    return render(request, 'returns/template_form.html', context)


@login_required
def template_delete(request, pk):
    """Delete a return template."""
    if not (request.user.is_superuser or hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()):
        raise PermissionDenied("You do not have permission to delete templates.")

    template = get_object_or_404(ReturnTemplate, pk=pk)

    if request.method == 'POST':
        template_name = template.name
        template.delete()
        messages.success(request, f"Template '{template_name}' deleted successfully.")
        return redirect('returns:template_list')

    context = {
        'template': template,
    }
    return render(request, 'returns/template_delete_confirm.html', context)


@login_required
def download_template(request, category):
    """Download a pre-configured CSV template for a given category."""
    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))

    # Generate template content
    try:
        csv_content = DefaultTemplateService.generate_template_csv(category, period)
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect('returns:template_list')

    # Create response
    response = HttpResponse(content_type='text/csv')
    filename = f"return_template_{category}_{period}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff' + csv_content)  # Add BOM for Excel compatibility

    return response


@login_required
def download_template_xlsx(request, category):
    """Download a pre-configured Excel template for a given category."""
    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))

    try:
        template = DefaultTemplateService.get_template_by_category(category)
        if not template:
            raise ValidationError(f"No template found for category: {category}")

        wb = DefaultTemplateService.generate_template_xlsx(category, period)

        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"return_template_{category}_{period}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        wb.save(response)
        return response

    except Exception as e:
        messages.error(request, f"Error generating template: {str(e)}")
        return redirect('returns:template_list')


# ============ SUBMISSION VIEWS ============

@login_required
def submission_list(request):
    """List return submissions with filtering."""
    user = request.user
    filter_form = ReturnsFilterForm(request.GET or None, user=user)

    submissions = ReturnSubmission.objects.select_related(
        'template', 'prison_station', 'submitted_by'
    ).order_by('-submitted_at')

    # Filter by user permissions
    if not user.is_superuser:
        if _is_station_user(user):
            submissions = submissions.filter(prison_station=user.prison_station)
        elif _is_region_user(user):
            submissions = submissions.filter(prison_station__region=user.region)
        else:
            submissions = submissions.none()
            messages.warning(request, "You are not assigned to a station or region.")

    # Apply filters
    if filter_form.is_valid():
        period = filter_form.cleaned_data.get('period')
        category = filter_form.cleaned_data.get('category')
        prison_station = filter_form.cleaned_data.get('prison_station')
        status = filter_form.cleaned_data.get('status')
        year = filter_form.cleaned_data.get('year')
        month = filter_form.cleaned_data.get('month')

        if period:
            submissions = submissions.filter(period=period)
        if category:
            submissions = submissions.filter(template__category=category)
        if prison_station:
            submissions = submissions.filter(prison_station=prison_station)
        if status:
            submissions = submissions.filter(status=status)
        if year:
            submissions = submissions.filter(year=year)
        if month:
            submissions = submissions.filter(month=month)

    # Pagination
    paginator = Paginator(submissions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'submissions': page_obj,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'page_title': 'Return Submissions',
    }
    return render(request, 'returns/submission_list.html', context)


@login_required
def submission_create(request):
    """Submit a new return."""
    user = request.user

    # Check permissions
    if not _is_station_user(user) and not user.is_superuser:
        messages.error(request, "You must be assigned to a prison station to submit returns.")
        return redirect('returns:submission_list')

    # Pre-select template if provided via query param
    initial = {}
    template_id = request.GET.get('template')
    if template_id:
        try:
            template = ReturnTemplate.objects.get(id=template_id)
            initial['template'] = template
        except ReturnTemplate.DoesNotExist:
            pass

    if request.method == 'POST':
        form = ReturnSubmissionForm(request.POST, request.FILES, user=user)

        if form.is_valid():
            submission = form.save(commit=False)
            submission.submitted_by = user

            # Auto-set station for non-superusers
            if not user.is_superuser:
                submission.prison_station = user.prison_station

            # Parse year and month from period field
            period = form.cleaned_data.get('period', datetime.now().strftime('%Y-%m'))
            year, month = _parse_period(period)
            submission.year = year
            submission.month = month
            submission.period = period

            submission.save()

            # Process the file
            result = ReturnProcessingService.process_file(submission)

            if result['success']:
                messages.success(
                    request,
                    f"Return submitted successfully! Processed {result['valid_rows']} records."
                )
            else:
                messages.warning(
                    request,
                    f"File uploaded but had issues: {result.get('errors', ['Unknown error'])[:3]}"
                )

            # Update station return status
            MonthlySubmissionService.update_station_status(submission)

            return redirect('returns:submission_detail', pk=submission.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ReturnSubmissionForm(user=user, initial=initial)

    context = {
        'form': form,
        'page_title': 'Submit Return',
    }
    return render(request, 'returns/submission_form.html', context)


@login_required
def submission_detail(request, pk):
    """View details of a return submission."""
    submission = get_object_or_404(
        ReturnSubmission.objects.select_related('template', 'prison_station', 'submitted_by'),
        pk=pk
    )

    # Check permissions
    user = request.user
    if not user.is_superuser:
        if _is_station_user(user) and submission.prison_station != user.prison_station:
            raise PermissionDenied("You do not have permission to view this submission.")
        if _is_region_user(user) and submission.prison_station.region != user.region:
            raise PermissionDenied("You do not have permission to view this submission.")

    # Get data rows - ordered by row_number ascending
    data_rows = submission.data_rows.all().order_by('row_number', 'id')

    # Pagination
    paginator = Paginator(data_rows, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'submission': submission,
        'data_rows': page_obj,
        'page_obj': page_obj,
        'page_title': f'Submission Details - {submission.template.name}',
    }
    return render(request, 'returns/submission_detail.html', context)


@login_required
def submission_approve(request, pk):
    """Approve a return submission."""
    submission = get_object_or_404(ReturnSubmission, pk=pk)

    # Check permissions
    user = request.user
    if not (user.is_superuser or hasattr(user, 'is_prison_admin') and user.is_prison_admin()):
        raise PermissionDenied("You do not have permission to approve submissions.")

    if request.method == 'POST':
        submission.status = 'approved'
        submission.processed_at = timezone.now()
        submission.processed_by = user
        submission.save()

        # Update station return status
        MonthlySubmissionService.approve_station_status(submission)

        messages.success(request, "Submission approved successfully.")
        return redirect('returns:submission_detail', pk=submission.pk)

    context = {
        'submission': submission,
    }
    return render(request, 'returns/submission_approve_confirm.html', context)


@login_required
def submission_reject(request, pk):
    """Reject a return submission."""
    submission = get_object_or_404(ReturnSubmission, pk=pk)

    # Check permissions
    user = request.user
    if not (user.is_superuser or hasattr(user, 'is_prison_admin') and user.is_prison_admin()):
        raise PermissionDenied("You do not have permission to reject submissions.")

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        submission.status = 'rejected'
        submission.processed_at = timezone.now()
        submission.processed_by = user
        submission.error_log = f"Rejected: {reason}\n{submission.error_log}"
        submission.save()

        # Update station return status
        MonthlySubmissionService.reject_station_status(submission, reason)

        messages.warning(request, f"Submission rejected: {reason}")
        return redirect('returns:submission_detail', pk=submission.pk)

    context = {
        'submission': submission,
    }
    return render(request, 'returns/submission_reject_confirm.html', context)


@login_required
def submission_download(request, pk):
    """Download submission data as CSV."""
    submission = get_object_or_404(ReturnSubmission, pk=pk)

    # Check permissions
    user = request.user
    if not user.is_superuser:
        if _is_station_user(user) and submission.prison_station != user.prison_station:
            raise PermissionDenied("You do not have permission to download this submission.")
        if _is_region_user(user) and submission.prison_station.region != user.region:
            raise PermissionDenied("You do not have permission to download this submission.")

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f"return_{submission.template.category}_{submission.prison_station.code}_{submission.period}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Get all data rows
    data_rows = submission.data_rows.all().order_by('row_number')

    # Write headers
    if data_rows.exists():
        headers = list(data_rows.first().row_data.keys())
        writer.writerow(headers)

        # Write data rows
        for row in data_rows:
            writer.writerow([row.row_data.get(header, '') for header in headers])

    return response


# ============ PDF EXPORT VIEWS ============

@login_required
def export_submission_pdf(request, pk):
    """Export a single submission as PDF."""
    submission = get_object_or_404(ReturnSubmission, pk=pk)
    
    # Check permissions
    user = request.user
    if not user.is_superuser:
        if _is_station_user(user) and submission.prison_station != user.prison_station:
            raise PermissionDenied("You do not have permission to export this submission.")
        if _is_region_user(user) and submission.prison_station.region != user.region:
            raise PermissionDenied("You do not have permission to export this submission.")
    
    return ReturnPDFService.generate_return_pdf(submission, request.user)


@login_required
def export_station_returns_pdf(request, station_id, template_id):
    """Export returns for a specific station and template as PDF."""
    station = get_object_or_404(PrisonStation, pk=station_id)
    template = get_object_or_404(ReturnTemplate, pk=template_id)
    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))
    
    # Check permissions
    user = request.user
    if not user.is_superuser:
        if _is_station_user(user) and station != user.prison_station:
            raise PermissionDenied("You do not have permission to export returns for this station.")
        if _is_region_user(user) and station.region != user.region:
            raise PermissionDenied("You do not have permission to export returns for this station.")
    
    return ReturnPDFService.generate_station_returns_pdf(station, template, period, request.user)


@login_required
def export_regional_returns_pdf(request, template_id, region):
    """Export returns for a specific region and template as PDF."""
    template = get_object_or_404(ReturnTemplate, pk=template_id)
    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))
    
    # Check permissions
    user = request.user
    if not user.is_superuser:
        if _is_region_user(user) and user.region != region:
            raise PermissionDenied("You do not have permission to export returns for this region.")
    
    return ReturnPDFService.generate_regional_returns_pdf(region, template, period, request.user)


@login_required
def export_all_returns_pdf(request, template_id):
    """Export all returns for a specific template as PDF."""
    template = get_object_or_404(ReturnTemplate, pk=template_id)
    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))
    
    # Check permissions
    user = request.user
    if not user.is_superuser:
        raise PermissionDenied("You do not have permission to export all returns.")
    
    return ReturnPDFService.generate_all_returns_pdf(template, period, request.user)


# ============ STATION RETURN STATUS VIEWS ============

@login_required
def station_status(request):
    """View return submission status for stations."""
    user = request.user
    filter_form = ReturnsFilterForm(request.GET or None, user=user)

    # Get selected period
    period = request.GET.get('period', timezone.now().strftime('%Y-%m'))
    year, month = _parse_period(period)

    statuses = StationReturnStatus.objects.select_related(
        'prison_station', 'template', 'submission'
    ).order_by('prison_station__name', 'template__category')

    # Filter by user permissions
    if not user.is_superuser:
        if _is_station_user(user):
            statuses = statuses.filter(prison_station=user.prison_station)
        elif _is_region_user(user):
            statuses = statuses.filter(prison_station__region=user.region)
        else:
            statuses = statuses.none()
            messages.warning(request, "You are not assigned to a station or region.")

    # Filter by period
    statuses = statuses.filter(year=year, month=month)

    # Apply additional filters
    if filter_form.is_valid():
        category = filter_form.cleaned_data.get('category')
        prison_station = filter_form.cleaned_data.get('prison_station')
        status = filter_form.cleaned_data.get('status')

        if category:
            statuses = statuses.filter(template__category=category)
        if prison_station:
            statuses = statuses.filter(prison_station=prison_station)
        if status:
            statuses = statuses.filter(status=status)

    # Group by station
    grouped = {}
    for status in statuses:
        station_name = status.prison_station.name
        if station_name not in grouped:
            grouped[station_name] = {
                'station': status.prison_station,
                'statuses': []
            }
        grouped[station_name]['statuses'].append(status)

    context = {
        'grouped_statuses': grouped,
        'filter_form': filter_form,
        'period': period,
        'year': year,
        'month': month,
        'page_title': 'Station Return Status',
    }
    return render(request, 'returns/station_status.html', context)


@login_required
def initialize_monthly_tracking(request):
    """Initialize monthly tracking for a period."""
    user = request.user
    
    if not (user.is_superuser or hasattr(user, 'is_prison_admin') and user.is_prison_admin()):
        raise PermissionDenied("You do not have permission to initialize monthly tracking.")

    if request.method == 'POST':
        form = MonthlyTrackingForm(request.POST)
        if form.is_valid():
            year = int(form.cleaned_data['year'])
            month = int(form.cleaned_data['month'])

            result = MonthlySubmissionService.initialize_monthly_tracking(year, month)

            messages.success(
                request,
                f"Monthly tracking initialized for {result['period']}. Created {result['created_count']} status records."
            )
            return redirect('returns:station_status')
    else:
        form = MonthlyTrackingForm()

    context = {
        'form': form,
        'page_title': 'Initialize Monthly Tracking',
    }
    return render(request, 'returns/initialize_tracking.html', context)


# ============ REGIONAL SUMMARY VIEWS ============

@login_required
def regional_summary(request):
    """View regional return summary."""
    user = request.user

    # Check permissions
    if not (user.is_superuser or _is_region_user(user)):
        messages.error(request, "You do not have permission to view regional summaries.")
        return redirect('returns:submission_list')

    period_form = PeriodSelectionForm(request.GET or None)

    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))
    category = request.GET.get('category', '')

    # Generate summary
    summary = ReturnReportService.generate_regional_summary(period, user)

    context = {
        'summary': summary,
        'period_form': period_form,
        'period': period,
        'selected_category': category,
        'page_title': 'Regional Return Summary',
    }
    return render(request, 'returns/regional_summary.html', context)


@login_required
def regional_summary_export(request):
    """Export regional summary as CSV."""
    user = request.user

    if not (user.is_superuser or _is_region_user(user)):
        raise PermissionDenied("You do not have permission to export regional summaries.")

    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))

    # Generate summary
    summary = ReturnReportService.generate_regional_summary(period, user)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f"regional_summary_{period}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Write headers
    writer.writerow(['Region', 'Stations', 'Submissions', 'Records', 'Male', 'Female'])

    # Write region data
    for region, data in summary['by_region'].items():
        writer.writerow([region, data['stations'], data['submissions'], data['records'], data['male'], data['female']])

    # Write category breakdown
    writer.writerow([])
    writer.writerow(['Category Breakdown'])
    writer.writerow(['Category', 'Submissions', 'Records', 'Stations', 'Male', 'Female'])

    for category, data in summary['by_category'].items():
        writer.writerow([category, data['count'], data['records'], len(data['stations']), data['male'], data['female']])

    return response


# ============ MONTHLY STATUS REPORT VIEW ============

@login_required
def monthly_status_report(request):
    """View monthly status report for all stations."""
    user = request.user

    if not (user.is_superuser or _is_region_user(user)):
        messages.error(request, "You do not have permission to view monthly status reports.")
        return redirect('returns:submission_list')

    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))
    year, month = _parse_period(period)

    # Generate report
    report = ReturnReportService.generate_monthly_status_report(year, month)

    context = {
        'report': report,
        'period': period,
        'year': year,
        'month': month,
        'page_title': f'Monthly Status Report - {date(year, month, 1).strftime("%B %Y")}',
    }
    return render(request, 'returns/monthly_status_report.html', context)


# ============ API VIEWS ============

@login_required
def api_returns_summary(request):
    """API endpoint for returns summary data."""
    user = request.user
    period = request.GET.get('period', datetime.now().strftime('%Y-%m'))
    year, month = _parse_period(period)

    # Filter submissions
    submissions = ReturnSubmission.objects.filter(
        year=year,
        month=month
    )

    if not user.is_superuser:
        if _is_station_user(user):
            submissions = submissions.filter(prison_station=user.prison_station)
        elif _is_region_user(user):
            submissions = submissions.filter(prison_station__region=user.region)
        else:
            submissions = submissions.none()

    # Build response data
    data = {
        'period': period,
        'total_submissions': submissions.count(),
        'total_records': sum(s.row_count for s in submissions),
        'total_male': sum(s.total_male for s in submissions),
        'total_female': sum(s.total_female for s in submissions),
        'by_status': {},
        'by_category': {},
        'by_station': {},
    }

    for status in ['pending', 'validated', 'rejected', 'imported', 'approved']:
        data['by_status'][status] = submissions.filter(status=status).count()

    for submission in submissions:
        category = submission.template.category
        if category not in data['by_category']:
            data['by_category'][category] = {
                'submissions': 0,
                'records': 0
            }
        data['by_category'][category]['submissions'] += 1
        data['by_category'][category]['records'] += submission.row_count

        station_name = submission.prison_station.name
        if station_name not in data['by_station']:
            data['by_station'][station_name] = {
                'submissions': 0,
                'records': 0,
                'male': 0,
                'female': 0,
                'status': submission.status
            }
        data['by_station'][station_name]['submissions'] += 1
        data['by_station'][station_name]['records'] += submission.row_count
        data['by_station'][station_name]['male'] += submission.total_male
        data['by_station'][station_name]['female'] += submission.total_female

    return JsonResponse(data)


@login_required
def api_monthly_status(request):
    """API endpoint for monthly status data."""
    user = request.user
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))

    period = f"{year}-{month:02d}"

    # Get statuses
    statuses = StationReturnStatus.objects.filter(
        year=year,
        month=month
    ).select_related('prison_station', 'template')

    if not user.is_superuser:
        if _is_station_user(user):
            statuses = statuses.filter(prison_station=user.prison_station)
        elif _is_region_user(user):
            statuses = statuses.filter(prison_station__region=user.region)

    # Build response
    data = {
        'period': period,
        'total_records': statuses.count(),
        'by_status': {},
        'by_station': {},
    }

    for status in ['not_submitted', 'pending', 'submitted', 'approved', 'rejected']:
        data['by_status'][status] = statuses.filter(status=status).count()

    for status in statuses:
        station_name = status.prison_station.name
        if station_name not in data['by_station']:
            data['by_station'][station_name] = {}
        data['by_station'][station_name][status.template.category] = status.status

    return JsonResponse(data)


# ============ EXPORT OPTIONS VIEW ============

@login_required
def export_options(request):
    """View export options for returns."""
    user = request.user
    
    # Check permissions
    if not (user.is_superuser or _is_region_user(user) or _is_station_user(user)):
        messages.error(request, "You do not have permission to access export options.")
        return redirect('returns:submission_list')
    
    templates = ReturnTemplate.objects.filter(is_active=True).order_by('category', 'name')
    stations = PrisonStation.objects.all()
    
    # Filter stations based on user permissions
    if not user.is_superuser:
        if _is_station_user(user):
            stations = stations.filter(pk=user.prison_station.pk)
        elif _is_region_user(user):
            stations = stations.filter(region=user.region)
    
    period = request.GET.get('period', timezone.now().strftime('%Y-%m'))
    
    context = {
        'templates': templates,
        'stations': stations,
        'period': period,
        'regions': PrisonStation.REGION_CHOICES,
        'page_title': 'Export Returns',
    }
    return render(request, 'returns/export_options.html', context)

@login_required
def export_options(request):
    """View export options for returns."""
    user = request.user
    
    # Check permissions
    if not (user.is_superuser or _is_region_user(user) or _is_station_user(user)):
        messages.error(request, "You do not have permission to access export options.")
        return redirect('returns:submission_list')
    
    templates = ReturnTemplate.objects.filter(is_active=True).order_by('category', 'name')
    stations = PrisonStation.objects.all()
    
    # Filter stations based on user permissions
    if not user.is_superuser:
        if _is_station_user(user):
            stations = stations.filter(pk=user.prison_station.pk)
        elif _is_region_user(user):
            stations = stations.filter(region=user.region)
    
    period = request.GET.get('period', timezone.now().strftime('%Y-%m'))
    
    # Get recent submissions for the selected period
    recent_submissions = ReturnSubmission.objects.filter(
        period=period
    ).select_related('template', 'prison_station', 'submitted_by').order_by('-submitted_at')[:20]
    
    # Filter submissions based on user permissions
    if not user.is_superuser:
        if _is_station_user(user):
            recent_submissions = recent_submissions.filter(prison_station=user.prison_station)
        elif _is_region_user(user):
            recent_submissions = recent_submissions.filter(prison_station__region=user.region)
    
    context = {
        'templates': templates,
        'stations': stations,
        'period': period,
        'regions': PrisonStation.REGION_CHOICES,
        'recent_submissions': recent_submissions,
        'page_title': 'Export Returns',
    }
    return render(request, 'returns/export_options.html', context)