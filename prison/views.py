from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.urls import reverse_lazy
from django.utils import timezone
import os
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.core.exceptions import PermissionDenied
from collections import defaultdict
from django.core.exceptions import PermissionDenied, ValidationError
import json
import logging

from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View
import time
# Mixins for Class-Based Views
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from accounts.mixins import RoleRequiredMixin

# Database and Querying
from django.db.models import Count, Q, Sum, F

# PDF and CSV generation
from xhtml2pdf import pisa
import io
import csv

# Date and Time utilities
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# Models from your app
from .models import (
    Prisoner,
    ConvictedPrisoner,
    RemandPrisoner,
    RiskAssessment,
    PrisonerParticulars,
    PhysicalCharacteristics,
    RehabilitationProgram,
    PrisonerTransfer,
    ActivityLog,
    ReleaseOnRemission,
    PrisonStation,
    Visitor,
    MedicalRecord,
    IncidentReport,
    PrisonerItem,
    PrisonerItemTransaction,
    RationItem,
    RationConsumption,
    RationProcurement,
    Notification,
    FingerprintDevice,
    FingerprintMatch,
    FingerprintAuditLog,
    PrisonerReleaseReview,
)
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from .models import *
from .forms import *
from .forms import (
    PrisonerForm,
    ConvictedPrisonerForm,
    RemandPrisonerForm,
    PrisonerParticularsForm,
    PhysicalCharacteristicsForm,
    RehabilitationProgramForm,
    PrisonerTransferForm,
    SentenceReductionForm,
    SearchForm,
    PrisonStationForm,
    VisitorForm,
    MedicalRecordForm,
    IncidentReportForm,
    PrisonerItemForm,
    PrisonerItemTransactionForm,
    ExtendedSearchForm,
    RationItemForm,
    RationConsumptionForm,
    RationProcurementForm,
    RecidivismConfirmationForm,
    FingerprintCaptureForm,
    FingerprintSearchForm,
    FingerprintDeviceForm,
    FingerprintMatchConfirmForm,
    RiskAssessmentForm,
)
from .biometric_service import BiometricService, FingerprintProcessor, FingerprintDeviceManager
from accounts.models import CustomUser
from django.contrib.auth import get_user_model

User = get_user_model()

logger = logging.getLogger(__name__)


# ============ HELPER FUNCTIONS ============

def _get_prisoner_release_date(prisoner):
    try:
        convicted_details = prisoner.convicted_details
    except ObjectDoesNotExist:
        return None
    return convicted_details.date_of_release_on_remission or convicted_details.date_of_release


def _get_release_candidates(today):
    release_window_end = today + timedelta(days=5)
    return (
        Prisoner.objects.filter(is_active=True)
        .filter(
            Q(convicted_details__date_of_release_on_remission__gte=today)
            & Q(convicted_details__date_of_release_on_remission__lte=release_window_end)
            | Q(convicted_details__date_of_release__gte=today)
            & Q(convicted_details__date_of_release__lte=release_window_end)
        )
        .select_related('prison_station', 'convicted_details')
        .order_by('convicted_details__date_of_release_on_remission', 'convicted_details__date_of_release')
    )


NATIONALITY_TO_COUNTRY = {
    'mozambican': 'Mozambique',
    'zimbabwean': 'Zimbabwe',
    'congolese': 'Congo',
    'zambian': 'Zambia',
    'tanzanian': 'Tanzania',
    'chinese': 'China',
    'japanese': 'Japan',
    'korean': 'Korea',
    'indian': 'India',
    'british': 'United Kingdom',
    'south_african': 'South Africa',
    'burundi': 'Burundi',
    'rwandan': 'Rwanda',
    'botswana': 'Botswana',
    'other': 'Other',
}


def _get_lockup_summary_data(request_user):
    is_super_admin_user = hasattr(request_user, 'is_super_admin') and request_user.is_super_admin()
    has_region_permission = hasattr(request_user, 'has_region_permission') and request_user.has_region_permission()
    has_station_permission = hasattr(request_user, 'has_station_permission') and request_user.has_station_permission()

    prisoners_base_qs = Prisoner.objects.filter(is_active=True).select_related('prison_station').prefetch_related(
        'physical', 'particulars', 'convicted_details')

    if is_super_admin_user:
        return _get_regional_summary_data(prisoners_base_qs)
    elif has_region_permission and request_user.region:
        region_prisoners = prisoners_base_qs.filter(prison_station__region=request_user.region)
        regional_data = _get_regional_summary_data(region_prisoners, single_region=True)
        if regional_data:
            region_key = list(regional_data.keys())[0]
            regional_summary = regional_data[region_key]
            regional_summary['total_stations'] = len(regional_summary['stations'])
            return {
                'regional_summary': regional_summary,
                'overall_summary': _calculate_overall_summary(region_prisoners),
            }
        else:
            return _get_empty_summary()
    elif has_station_permission and request_user.prison_station:
        station_prisoners = prisoners_base_qs.filter(prison_station=request_user.prison_station)
        station_summary = _calculate_station_summary(request_user.prison_station, station_prisoners)
        return {
            'station_summary': station_summary,
        }
    else:
        return _get_empty_summary()


def _get_regional_summary_data(prisoners_qs, single_region=False):
    if single_region:
        stations = PrisonStation.objects.filter(
            id__in=prisoners_qs.values_list('prison_station_id', flat=True)
        ).distinct()
        if not stations.exists():
            return None
        region_name = stations.first().get_region_display()
        region_data = _calculate_region_data(stations, prisoners_qs)
        return {region_name: region_data}
    else:
        regions = PrisonStation.REGION_CHOICES
        regional_summary = {}
        for region_code, region_display in regions:
            region_stations = PrisonStation.objects.filter(region=region_code)
            if not region_stations.exists():
                continue
            region_prisoners = prisoners_qs.filter(prison_station__region=region_code)
            if not region_prisoners.exists():
                continue
            region_data = _calculate_region_data(region_stations, region_prisoners)
            regional_summary[region_display] = region_data
        return regional_summary


def _calculate_region_data(stations, prisoners_qs):
    stations_data = []
    region_totals = {
        'male_convicted': 0,
        'female_convicted': 0,
        'male_remand': 0,
        'female_remand': 0,
        'foreigner_convicted': 0,
        'foreigner_remand': 0,
        'children': 0,
        'total': 0,
    }
    for station in stations:
        station_prisoners = prisoners_qs.filter(prison_station=station)
        station_data = _calculate_station_summary(station, station_prisoners)
        stations_data.append(station_data)
        for key in region_totals:
            region_totals[key] += station_data.get(key, 0)
    return {
        'stations': stations_data,
        'total_stations': len(stations_data),
        **region_totals,
    }


def _calculate_station_summary(station, prisoners_qs):
    m_conv = prisoners_qs.filter(sex='male', prisoner_class='convicted').count()
    f_conv = prisoners_qs.filter(sex='female', prisoner_class='convicted').count()
    m_rem = prisoners_qs.filter(sex='male', prisoner_class='remand').count()
    f_rem = prisoners_qs.filter(sex='female', prisoner_class='remand').count()

    s_conv_foreigners = prisoners_qs.filter(
        prisoner_class='convicted',
        particulars__nationality__isnull=False
    ).exclude(particulars__nationality__iexact='malawian').count()

    s_rem_foreigners = prisoners_qs.filter(
        prisoner_class='remand',
        particulars__nationality__isnull=False
    ).exclude(particulars__nationality__iexact='malawian').count()

    station_children_count = sum(
        p.physical.children_count for p in prisoners_qs.filter(sex='female')
        if hasattr(p, 'physical') and p.physical and p.physical.children_count is not None
    )

    station_total = m_conv + f_conv + m_rem + f_rem + station_children_count + s_conv_foreigners + s_rem_foreigners

    return {
        'name': station.name,
        'male_convicted': m_conv,
        'female_convicted': f_conv,
        'male_remand': m_rem,
        'female_remand': f_rem,
        'foreigner_convicted': s_conv_foreigners,
        'foreigner_remand': s_rem_foreigners,
        'children': station_children_count,
        'total': station_total,
    }


def _calculate_overall_summary(prisoners_qs):
    male_convicted_total = prisoners_qs.filter(sex='male', prisoner_class='convicted').count()
    female_convicted_total = prisoners_qs.filter(sex='female', prisoner_class='convicted').count()
    male_remand_total = prisoners_qs.filter(sex='male', prisoner_class='remand').count()
    female_remand_total = prisoners_qs.filter(sex='female', prisoner_class='remand').count()

    female_prisoners_with_physical = prisoners_qs.filter(sex='female', physical__isnull=False)
    children_count_total = sum([p.physical.children_count for p in female_prisoners_with_physical if
                                p.physical.children_count is not None]) if female_prisoners_with_physical.exists() else 0

    all_foreign_prisoners_qs = prisoners_qs.filter(
        particulars__nationality__isnull=False
    ).exclude(particulars__nationality__iexact='malawian').select_related('particulars')

    country_counts = defaultdict(int)
    for prisoner in all_foreign_prisoners_qs:
        if hasattr(prisoner, 'particulars') and prisoner.particulars.nationality:
            nat = prisoner.particulars.nationality.lower()
            country = NATIONALITY_TO_COUNTRY.get(nat, nat.title())
            country_counts[country] += 1

    foreigners_by_country = [{'nationality': country, 'count': count}
                             for country, count in sorted(country_counts.items())]
    total_foreigners = sum(country_counts.values())

    total_foreigner_convicted = prisoners_qs.filter(
        prisoner_class='convicted',
        particulars__nationality__isnull=False
    ).exclude(particulars__nationality__iexact='malawian').count()

    total_foreigner_remand = prisoners_qs.filter(
        prisoner_class='remand',
        particulars__nationality__isnull=False
    ).exclude(particulars__nationality__iexact='malawian').count()

    grand_total = (
            male_convicted_total +
            female_convicted_total +
            male_remand_total +
            female_remand_total +
            children_count_total +
            total_foreigner_convicted +
            total_foreigner_remand
    )

    return {
        'male_convicted': male_convicted_total,
        'female_convicted': female_convicted_total,
        'male_remand': male_remand_total,
        'female_remand': female_remand_total,
        'children': children_count_total,
        'grand_total': grand_total,
        'total_foreigners': total_foreigners,
        'foreigners_by_country': foreigners_by_country,
        'foreigner_convicted': total_foreigner_convicted,
        'foreigner_remand': total_foreigner_remand,
    }


def _get_empty_summary():
    return {
        'regional_summary': None,
        'station_summary': None,
        'overall_summary': None,
    }


def get_total_people_for_ration(station=None):
    if station:
        active_prisoners_in_station = Prisoner.objects.filter(
            prison_station=station,
            is_active=True
        )
    else:
        active_prisoners_in_station = Prisoner.objects.filter(is_active=True)

    total_inmates = active_prisoners_in_station.count()
    children_count = sum(
        p.physical.children_count for p in active_prisoners_in_station.filter(sex='female')
        if hasattr(p, 'physical') and p.physical and p.physical.children_count is not None
    )
    return total_inmates + children_count


# ============ SUMMARY VIEWS ============

@login_required
def lockup_summary_view(request):
    summary_data = _get_lockup_summary_data(request.user)

    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()
    is_visitor_attendant_user = hasattr(request.user, 'is_visitor_attendant') and request.user.is_visitor_attendant()

    show_prisoner_stats = is_super_admin_user or is_prison_admin_user or is_reception_user or is_warden_user or is_visitor_attendant_user

    upcoming_releases = []
    if show_prisoner_stats:
        prisoners = Prisoner.objects.filter(is_active=True)
        if not is_super_admin_user and hasattr(request.user, 'prison_station') and request.user.prison_station:
            prisoners = prisoners.filter(prison_station=request.user.prison_station)
        elif not is_super_admin_user and (not hasattr(request.user, 'prison_station') or not request.user.prison_station):
            prisoners = Prisoner.objects.none()

        today = timezone.now().date()
        next_month = today + timedelta(days=30)
        upcoming_qs = ConvictedPrisoner.objects.filter(
            prisoner__in=prisoners,
            date_of_release_on_remission__gte=today,
            date_of_release_on_remission__lte=next_month
        ).select_related('prisoner', 'prisoner__prison_station')

        upcoming_releases = upcoming_qs.order_by('date_of_release_on_remission')[:10]

    context = {
        'today_date': timezone.localdate(),
        'upcoming_releases': upcoming_releases,
        **summary_data,
    }

    return render(request, 'prison/lockup_summary.html', context)


# ============ DASHBOARD VIEWS ============

@login_required
def release_hub(request):
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_officer_in_charge_user = hasattr(request.user, 'is_officer_in_charge') and request.user.is_officer_in_charge()
    is_station_officer_user = hasattr(request.user, 'is_station_officer') and request.user.is_station_officer()

    if not (is_reception_user or is_officer_in_charge_user or is_station_officer_user):
        raise PermissionDenied("You do not have permission to access the release hub.")

    today = timezone.now().date()
    release_candidates = _get_release_candidates(today)

    pending_reviews = []
    if is_officer_in_charge_user:
        pending_reviews = (
            PrisonerReleaseReview.objects.filter(
                station=request.user.prison_station,
                review_role='officer_in_charge',
                status='pending',
            )
            .select_related('prisoner', 'requested_by', 'station')
            .order_by('release_date', 'requested_at')
        )
    elif is_station_officer_user:
        pending_reviews = (
            PrisonerReleaseReview.objects.filter(
                station=request.user.prison_station,
                review_role='station_officer',
                status='pending',
            )
            .select_related('prisoner', 'requested_by', 'station')
            .order_by('release_date', 'requested_at')
        )

    context = {
        'release_candidates': release_candidates,
        'pending_reviews': pending_reviews,
        'today': today,
    }
    return render(request, 'prison/release_hub.html', context)


@login_required
@require_POST
def forward_release_for_review(request, prisoner_id):
    if not (hasattr(request.user, 'is_reception') and request.user.is_reception()):
        raise PermissionDenied("Only reception officers can forward prisoners for review.")

    prisoner = get_object_or_404(Prisoner, pk=prisoner_id, is_active=True)
    review_role = request.POST.get('review_role', 'officer_in_charge')
    if review_role not in dict(PrisonerReleaseReview.REVIEW_ROLE_CHOICES):
        review_role = 'officer_in_charge'

    release_date = _get_prisoner_release_date(prisoner) or timezone.now().date()
    review, created = PrisonerReleaseReview.objects.get_or_create(
        prisoner=prisoner,
        review_role=review_role,
        station=prisoner.prison_station,
        defaults={
            'requested_by': request.user,
            'release_date': release_date,
            'status': 'pending',
        },
    )
    if not created:
        review.requested_by = request.user
        review.release_date = release_date
        review.status = 'pending'
        review.notes = ''
        review.save(update_fields=['requested_by', 'release_date', 'status', 'notes'])

    messages.success(request, f"{prisoner.full_name} was forwarded for {review.get_review_role_display()} review.")
    return redirect('release_hub')


@login_required
@require_POST
def approve_release_review(request, review_id):
    review = get_object_or_404(PrisonerReleaseReview, pk=review_id)

    if review.station != request.user.prison_station:
        raise PermissionDenied("You can only review prisoners from your station.")

    if review.review_role == 'officer_in_charge' and not (
            hasattr(request.user, 'is_officer_in_charge') and request.user.is_officer_in_charge()):
        raise PermissionDenied("Only the officer in charge can approve this request.")

    if review.review_role == 'station_officer' and not (
            hasattr(request.user, 'is_station_officer') and request.user.is_station_officer()):
        raise PermissionDenied("Only the station officer can approve this request.")

    review.status = 'approved'
    review.reviewed_by = request.user
    review.reviewed_at = timezone.now()
    review.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    prisoner = review.prisoner
    prisoner.is_active = False
    prisoner.date_released = review.release_date or timezone.now().date()
    prisoner.save(update_fields=['is_active', 'date_released'])

    messages.success(request, f"{prisoner.full_name} was approved for discharge.")
    return redirect('release_hub')


@login_required
@require_POST
def reject_release_review(request, review_id):
    review = get_object_or_404(PrisonerReleaseReview, pk=review_id)

    if review.station != request.user.prison_station:
        raise PermissionDenied("You can only review prisoners from your station.")

    if review.review_role == 'officer_in_charge' and not (
            hasattr(request.user, 'is_officer_in_charge') and request.user.is_officer_in_charge()):
        raise PermissionDenied("Only the officer in charge can reject this request.")

    if review.review_role == 'station_officer' and not (
            hasattr(request.user, 'is_station_officer') and request.user.is_station_officer()):
        raise PermissionDenied("Only the station officer can reject this request.")

    review.status = 'rejected'
    review.reviewed_by = request.user
    review.reviewed_at = timezone.now()
    review.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    messages.info(request, f"{review.prisoner.full_name} was rejected for release.")
    return redirect('release_hub')


@login_required
def dashboard(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()
    is_visitor_attendant_user = hasattr(request.user, 'is_visitor_attendant') and request.user.is_visitor_attendant()
    is_medical_officer_user = hasattr(request.user, 'is_medical_officer') and request.user.is_medical_officer()

    show_prisoner_stats = is_super_admin_user or is_prison_admin_user or \
                          is_reception_user or is_warden_user or is_visitor_attendant_user

    prisoners = Prisoner.objects.filter(is_active=True) if show_prisoner_stats else Prisoner.objects.none()

    if not is_super_admin_user and hasattr(request.user, 'prison_station') and request.user.prison_station:
        prisoners = prisoners.filter(prison_station=request.user.prison_station)
    elif not is_super_admin_user and (not hasattr(request.user, 'prison_station') or not request.user.prison_station):
        prisoners = Prisoner.objects.none()

    total_prisoners = prisoners.count() if show_prisoner_stats else 0
    convicted_count = prisoners.filter(prisoner_class='convicted').count() if show_prisoner_stats else 0
    remand_count = prisoners.filter(prisoner_class='remand').count() if show_prisoner_stats else 0

    children_count = 0
    if show_prisoner_stats:
        female_prisoners = prisoners.filter(sex='female')
        children_count = sum([p.physical.children_count for p in female_prisoners if
                              hasattr(p, 'physical') and p.physical and p.physical.children_count is not None]) if female_prisoners.exists() else 0

    recidivism_rate = 0
    if show_prisoner_stats and total_prisoners > 0:
        risk_assessments = RiskAssessment.objects.filter(prisoner__in=prisoners)
        recidivism_count = risk_assessments.filter(previous_conviction=True).count()
        recidivism_rate = (recidivism_count / total_prisoners * 100)

    months = []
    prisoner_counts = []
    if show_prisoner_stats:
        today = datetime.now().date()
        for i in range(5, -1, -1):
            month_start = (today - relativedelta(months=i)).replace(day=1)
            month_end = (month_start + relativedelta(months=1) - relativedelta(days=1))
            month_name = month_start.strftime('%b %Y')
            count = prisoners.filter(
                date_admitted__lte=month_end
            ).filter(
                Q(date_released__isnull=True) | Q(date_released__gte=month_start)
            ).count()
            months.append(month_name)
            prisoner_counts.append(count)

    upcoming_releases = []
    if show_prisoner_stats:
        today = datetime.now().date()
        next_month = today + timedelta(days=30)
        convicted_prisoners_query = ConvictedPrisoner.objects.filter(
            prisoner__in=prisoners,
            date_of_release_on_remission__gte=today,
            date_of_release_on_remission__lte=next_month
        )
        upcoming_releases = convicted_prisoners_query.order_by('date_of_release_on_remission')[:10]

    recent_activities = None
    if is_super_admin_user:
        recent_activities = ActivityLog.objects.all().order_by('-timestamp')[:10]

    lockup_summary = {}
    if show_prisoner_stats:
        lockup_summary = {
            'male_convicted': prisoners.filter(sex='male', prisoner_class='convicted').count(),
            'female_convicted': prisoners.filter(sex='female', prisoner_class='convicted').count(),
            'male_remand': prisoners.filter(sex='male', prisoner_class='remand').count(),
            'female_remand': prisoners.filter(sex='female', prisoner_class='remand').count(),
            'male_murder_convicted': ConvictedPrisoner.objects.filter(
                prisoner__in=prisoners.filter(sex='male', prisoner_class='convicted'),
                offense__icontains='Murder contrary to section 209 of the Penal Code',
            ).count(),
            'female_murder_convicted': ConvictedPrisoner.objects.filter(
                prisoner__in=prisoners.filter(sex='female', prisoner_class='convicted'),
                offense__icontains='Murder contrary to section 209 of the Penal Code',
            ).count(),
            'male_foreigner_remand': prisoners.filter(
                sex='male', prisoner_class='remand',
                particulars__nationality__isnull=False
            ).exclude(particulars__nationality__iexact='malawian').count(),
            'female_foreigner_remand': prisoners.filter(
                sex='female', prisoner_class='remand',
                particulars__nationality__isnull=False
            ).exclude(particulars__nationality__iexact='malawian').count(),
            'children': children_count,
            'grand_total': total_prisoners,
        }

    show_medical_stats = is_medical_officer_user or is_super_admin_user or is_prison_admin_user

    medical_stats = {}
    if show_medical_stats:
        medical_records_query = MedicalRecord.objects.all()
        if not is_super_admin_user and hasattr(request.user, 'prison_station') and request.user.prison_station:
            medical_records_query = medical_records_query.filter(prisoner__prison_station=request.user.prison_station)
        elif not is_super_admin_user and (not hasattr(request.user, 'prison_station') or not request.user.prison_station):
            medical_records_query = MedicalRecord.objects.none()

        medical_stats['categories'] = dict(MedicalRecord.MEDICAL_CATEGORIES)
        medical_stats['count_by_category'] = medical_records_query.values('category').annotate(count=Count('id')).order_by(
            'category')
        medical_stats['recent_records'] = medical_records_query.order_by('-record_date')[:5]

        prisoners_with_medical_conditions_query = prisoners.filter(medical_records__isnull=False).distinct()
        medical_stats['prisoners_with_medical'] = prisoners_with_medical_conditions_query.count()
        medical_stats['urgent_cases'] = medical_records_query.filter(category='emergency').count()

        common_diagnosis = medical_records_query.values('diagnosis').annotate(
            count=Count('diagnosis')
        ).exclude(diagnosis__isnull=True).exclude(diagnosis__exact='').order_by('-count')[:5]
        medical_stats['common_diagnosis'] = common_diagnosis
        medical_stats['total_records_count'] = medical_records_query.count()

    show_ration_stats = is_super_admin_user or is_prison_admin_user or is_warden_user or is_reception_user
    ration_alerts = []
    daily_ration_needs = {}
    total_people_requiring_ration = 0

    if show_ration_stats and hasattr(request.user, 'prison_station') and request.user.prison_station:
        user_prison_station = request.user.prison_station

        active_prisoners_in_station = Prisoner.objects.filter(
            prison_station=user_prison_station,
            is_active=True
        )
        total_inmates = active_prisoners_in_station.count()
        children_count = sum(
            p.physical.children_count for p in active_prisoners_in_station.filter(sex='female')
            if hasattr(p, 'physical') and p.physical and p.physical.children_count is not None
        )
        total_people_requiring_ration = total_inmates + children_count

        ration_items_in_station = RationItem.objects.filter(
            prison_station=user_prison_station,
            is_active=True
        ).order_by('name')

        for item in ration_items_in_station:
            if item.is_low_stock:
                ration_alerts.append({
                    'type': 'warning',
                    'message': f"Low stock for {item.name}: {item.current_stock_kg:.3f} {item.unit} (Threshold: {item.low_stock_threshold_kg:.3f} {item.unit})"
                })

            required_daily_kg = Decimal(total_people_requiring_ration) * Decimal('0.680')

            days_of_coverage = 0
            if required_daily_kg > 0:
                days_of_coverage = item.current_stock_kg / required_daily_kg

            daily_ration_needs[item.name] = {
                'required_kg': required_daily_kg,
                'current_stock_kg': item.current_stock_kg,
                'unit': item.unit,
                'is_low_stock': item.is_low_stock,
                'percentage_remaining': (item.current_stock_kg / required_daily_kg * 100) if required_daily_kg > 0 else 0,
                'days_of_coverage': days_of_coverage
            }
            if item.current_stock_kg < required_daily_kg and required_daily_kg > 0:
                ration_alerts.append({
                    'type': 'danger',
                    'message': f"CRITICAL: {item.name} stock ({item.current_stock_kg:.3f} {item.unit}) is insufficient for today's estimated need ({required_daily_kg:.3f} {item.unit})."
                })

    elif show_ration_stats and (not hasattr(request.user, 'prison_station') or not request.user.prison_station):
        ration_alerts.append({
            'type': 'info',
            'message': "You are not assigned to a prison station. Ration management details are not available."
        })

    context = {
        'show_prisoner_stats': show_prisoner_stats,
        'total_prisoners': total_prisoners,
        'convicted_count': convicted_count,
        'remand_count': remand_count,
        'children_count': children_count,
        'recidivism_rate': round(recidivism_rate, 2) if show_prisoner_stats else 0,
        'months': months if show_prisoner_stats else [],
        'prisoner_counts': prisoner_counts if show_prisoner_stats else [],
        'upcoming_releases': upcoming_releases if show_prisoner_stats else [],
        'recent_activities': recent_activities,
        'lockup_summary': lockup_summary,
        'show_medical_stats': show_medical_stats,
        'medical_stats': medical_stats if show_medical_stats else None,
        'show_ration_stats': show_ration_stats,
        'ration_alerts': ration_alerts,
        'daily_ration_needs': daily_ration_needs,
        'total_people_requiring_ration': total_people_requiring_ration,
        'today_date': timezone.localdate(),
    }

    return render(request, 'prison/dashboard.html', context)


# ============ PRISONER MANAGEMENT VIEWS ============

@login_required
def prisoner_list(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_visitor_attendant_user = hasattr(request.user, 'is_visitor_attendant') and request.user.is_visitor_attendant()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()

    if not (is_super_admin_user or is_prison_admin_user or
            is_reception_user or is_visitor_attendant_user or is_warden_user):
        raise PermissionDenied("You do not have permission to view the prisoner list.")

    form = SearchForm(request.GET or None, user=request.user)

    prisoners_qs = Prisoner.objects.filter(is_active=True)

    if not is_super_admin_user:
        if hasattr(request.user, 'prison_station') and request.user.prison_station:
            prisoners_qs = prisoners_qs.filter(prison_station=request.user.prison_station)
        else:
            prisoners_qs = Prisoner.objects.none()

    if form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        prisoner_class = form.cleaned_data.get('prisoner_class')
        risk_level = form.cleaned_data.get('risk_level')

        if search_query:
            prisoners_qs = prisoners_qs.filter(
                Q(prisoner_number__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(middle_name__icontains=search_query) |
                Q(surname__icontains=search_query)
            )

        if prisoner_class:
            prisoners_qs = prisoners_qs.filter(prisoner_class=prisoner_class)

        if risk_level:
            prisoner_ids = RiskAssessment.objects.filter(
                risk_level=risk_level,
                prisoner__in=prisoners_qs
            ).values_list('prisoner_id', flat=True)
            prisoners_qs = prisoners_qs.filter(id__in=prisoner_ids)

    context = {
        'prisoners': prisoners_qs.order_by('-date_admitted'),
        'form': form,
    }
    return render(request, 'prison/prisoner_list.html', context)


@login_required
def add_prisoner(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user):
        raise PermissionDenied("You do not have permission to add prisoners.")

    if request.method == 'POST':
        prisoner_form = PrisonerForm(request.POST, request.FILES, user=request.user)

        if prisoner_form.is_valid():
            prisoner = prisoner_form.save(commit=False)
            prisoner.created_by = request.user

            if not prisoner.prison_station and hasattr(request.user, 'prison_station') and request.user.prison_station:
                prisoner.prison_station = request.user.prison_station
            elif not prisoner.prison_station and is_super_admin_user:
                messages.error(request, "Superuser must select a prison station for the new prisoner.")
                context = {'prisoner_form': prisoner_form}
                return render(request, 'prison/add_prisoner.html', context)

            prisoner.save()

            ActivityLog.objects.create(
                user=request.user,
                action='create',
                model='Prisoner',
                object_id=prisoner.id,
                details=f'Added prisoner {prisoner.prisoner_number} to station {prisoner.prison_station.name if prisoner.prison_station else "N/A"}'
            )

            from .utils import create_new_admission_notification
            create_new_admission_notification(prisoner)

            if prisoner.prisoner_class == 'convicted':
                return redirect('add_convicted_details', prisoner_id=prisoner.id)
            else:
                return redirect('add_remand_details', prisoner_id=prisoner.id)
        else:
            messages.error(request, "Please correct the errors below.")
            context = {
                'prisoner_form': prisoner_form,
            }
            return render(request, 'prison/add_prisoner.html', context)

    prisoner_form = PrisonerForm(user=request.user)

    context = {
        'prisoner_form': prisoner_form,
    }
    return render(request, 'prison/add_prisoner.html', context)


@login_required
def add_convicted_details(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user):
        raise PermissionDenied("You do not have permission to add convicted prisoner details.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id)
    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied("You do not have permission for this prisoner's station.")

    if request.method == 'POST':
        form = ConvictedPrisonerForm(request.POST)
        particulars_form = PrisonerParticularsForm(request.POST)
        physical_form = PhysicalCharacteristicsForm(request.POST)
        risk_form = RiskAssessmentForm(request.POST)
        rehab_form = RehabilitationProgramForm(request.POST)

        if all([
            form.is_valid(),
            particulars_form.is_valid(),
            physical_form.is_valid(),
            risk_form.is_valid(),
            rehab_form.is_valid()
        ]):
            convicted = form.save(commit=False)
            convicted.prisoner = prisoner
            convicted.save()

            particulars = particulars_form.save(commit=False)
            particulars.prisoner = prisoner
            particulars.save()

            physical = physical_form.save(commit=False)
            physical.prisoner = prisoner
            physical.save()

            risk = risk_form.save(commit=False)
            risk.prisoner = prisoner
            risk.save()

            rehab = rehab_form.save(commit=False)
            rehab.prisoner = prisoner
            rehab.save()

            ActivityLog.objects.create(
                user=request.user,
                action='create_details',
                model='ConvictedPrisoner',
                object_id=prisoner.id,
                details=f'Added full details for convicted prisoner {prisoner.prisoner_number}'
            )

            messages.success(request, 'Convicted prisoner details added successfully.')
            return redirect('prisoner_detail', prisoner_id=prisoner.id)
        else:
            logger.error(f"Convicted details form errors: {form.errors}")
            logger.error(f"Particulars form errors: {particulars_form.errors}")
            logger.error(f"Physical form errors: {physical_form.errors}")
            logger.error(f"Risk form errors: {risk_form.errors}")
            logger.error(f"Rehab form errors: {rehab_form.errors}")
            messages.error(request, 'Please correct the errors in the forms.')
    else:
        form = ConvictedPrisonerForm()
        particulars_form = PrisonerParticularsForm()
        physical_form = PhysicalCharacteristicsForm()
        risk_form = RiskAssessmentForm()
        rehab_form = RehabilitationProgramForm()

    context = {
        'prisoner': prisoner,
        'form': form,
        'particulars_form': particulars_form,
        'physical_form': physical_form,
        'risk_form': risk_form,
        'rehab_form': rehab_form,
    }
    return render(request, 'prison/add_convicted_details.html', context)


@login_required
def add_remand_details(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user):
        raise PermissionDenied("You do not have permission to add remand prisoner details.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id)
    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied("You do not have permission for this prisoner's station.")

    if request.method == 'POST':
        form = RemandPrisonerForm(request.POST)
        particulars_form = PrisonerParticularsForm(request.POST)
        physical_form = PhysicalCharacteristicsForm(request.POST)

        if all([
            form.is_valid(),
            particulars_form.is_valid(),
            physical_form.is_valid(),
        ]):
            remand = form.save(commit=False)
            remand.prisoner = prisoner
            remand.save()

            particulars = particulars_form.save(commit=False)
            particulars.prisoner = prisoner
            particulars.save()

            physical = physical_form.save(commit=False)
            physical.prisoner = prisoner
            physical.save()

            ActivityLog.objects.create(
                user=request.user,
                action='create_details',
                model='RemandPrisoner',
                object_id=prisoner.id,
                details=f'Added details for remand prisoner {prisoner.prisoner_number}'
            )

            messages.success(request, 'Remand prisoner details added successfully.')
            return redirect('prisoner_detail', prisoner_id=prisoner.id)
        else:
            logger.error(f"Remand form errors: {form.errors}")
            logger.error(f"Particulars form errors: {particulars_form.errors}")
            logger.error(f"Physical form errors: {physical_form.errors}")
            messages.error(request, 'Please correct the errors in the forms.')
    else:
        form = RemandPrisonerForm()
        particulars_form = PrisonerParticularsForm()
        physical_form = PhysicalCharacteristicsForm()

    context = {
        'prisoner': prisoner,
        'form': form,
        'particulars_form': particulars_form,
        'physical_form': physical_form,
    }
    return render(request, 'prison/add_remand_details.html', context)


@login_required
def prisoner_detail(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()
    is_medical_officer_user = hasattr(request.user, 'is_medical_officer') and request.user.is_medical_officer()

    if not (is_super_admin_user or is_prison_admin_user or
            is_reception_user or is_warden_user or is_medical_officer_user):
        raise PermissionDenied("You do not have permission to view prisoner details.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id)
    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied("You do not have permission to view this prisoner.")

    transfers = prisoner.transfers.all().order_by('-transfer_date')
    medical_records = prisoner.medical_records.all().order_by('-record_date')
    prisoner_items = prisoner.items.all().order_by('-date_received')

    context = {
        'prisoner': prisoner,
        'transfers': transfers,
        'medical_records': medical_records,
        'prisoner_items': prisoner_items,
    }

    try:
        context['physical'] = prisoner.physical
        context['particulars'] = prisoner.particulars
    except ObjectDoesNotExist:
        messages.warning(request, f"Essential details might be missing for prisoner {prisoner.prisoner_number}.")

    if prisoner.prisoner_class == 'convicted':
        try:
            context['convicted_details'] = prisoner.convicted_details
            context['risk_assessment'] = prisoner.risk_assessment
            context['rehabilitation'] = prisoner.rehabilitation
        except ObjectDoesNotExist:
            messages.warning(request, f"Convicted prisoner specific details are missing.")
    elif prisoner.prisoner_class == 'remand':
        try:
            context['remand_details'] = prisoner.remand_details
        except ObjectDoesNotExist:
            messages.warning(request, f"Remand prisoner specific details are missing.")

    return render(request, 'prison/prisoner_detail.html', context)


@login_required
def edit_prisoner(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user):
        raise PermissionDenied("You do not have permission to edit prisoner details.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id)

    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied('You do not have permission to edit this prisoner.')

    if request.method == 'POST':
        form = PrisonerForm(request.POST, request.FILES, instance=prisoner, user=request.user)

        if form.is_valid():
            original_class = prisoner.prisoner_class
            updated_prisoner = form.save()

            ActivityLog.objects.create(
                user=request.user,
                action='update_core',
                model='Prisoner',
                object_id=updated_prisoner.id,
                details=f'Updated core details for prisoner {updated_prisoner.prisoner_number}'
            )

            messages.success(request, 'Prisoner core details updated successfully.')

            if updated_prisoner.prisoner_class != original_class:
                messages.info(request,
                              f"Prisoner class changed from {original_class} to {updated_prisoner.prisoner_class}.")
                if updated_prisoner.prisoner_class == 'convicted':
                    return redirect('edit_convicted_details', prisoner_id=updated_prisoner.id)
                else:
                    return redirect('edit_remand_details', prisoner_id=updated_prisoner.id)

            return redirect('prisoner_detail', prisoner_id=updated_prisoner.id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PrisonerForm(instance=prisoner, user=request.user)

    context = {
        'form': form,
        'prisoner': prisoner,
    }
    return render(request, 'prison/edit_prisoner.html', context)


@login_required
def edit_convicted_details(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user):
        raise PermissionDenied("You do not have permission to edit convicted prisoner details.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id, prisoner_class='convicted')
    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied("You do not have permission for this prisoner's station.")

    convicted, _ = ConvictedPrisoner.objects.get_or_create(prisoner=prisoner)
    particulars, _ = PrisonerParticulars.objects.get_or_create(prisoner=prisoner)
    physical, _ = PhysicalCharacteristics.objects.get_or_create(prisoner=prisoner)
    risk, _ = RiskAssessment.objects.get_or_create(prisoner=prisoner)
    rehab, _ = RehabilitationProgram.objects.get_or_create(prisoner=prisoner)

    if request.method == 'POST':
        convicted_form = ConvictedPrisonerForm(request.POST, instance=convicted)
        particulars_form = PrisonerParticularsForm(request.POST, instance=particulars)
        physical_form = PhysicalCharacteristicsForm(request.POST, instance=physical)
        risk_form = RiskAssessmentForm(request.POST, instance=risk)
        rehab_form = RehabilitationProgramForm(request.POST, instance=rehab)

        if all([
            convicted_form.is_valid(),
            particulars_form.is_valid(),
            physical_form.is_valid(),
            risk_form.is_valid(),
            rehab_form.is_valid()
        ]):
            convicted_form.save()
            particulars_form.save()
            physical_form.save()
            risk_form.save()
            rehab_form.save()

            ActivityLog.objects.create(
                user=request.user,
                action='update_details',
                model='ConvictedPrisoner',
                object_id=prisoner.id,
                details=f'Updated details for convicted prisoner {prisoner.prisoner_number}'
            )

            messages.success(request, 'Convicted prisoner details updated successfully.')
            return redirect('prisoner_detail', prisoner_id=prisoner.id)
        else:
            messages.error(request, "Please correct the validation errors in the forms.")
    else:
        convicted_form = ConvictedPrisonerForm(instance=convicted)
        particulars_form = PrisonerParticularsForm(instance=particulars)
        physical_form = PhysicalCharacteristicsForm(instance=physical)
        risk_form = RiskAssessmentForm(instance=risk)
        rehab_form = RehabilitationProgramForm(instance=rehab)

    context = {
        'prisoner': prisoner,
        'convicted_form': convicted_form,
        'particulars_form': particulars_form,
        'physical_form': physical_form,
        'risk_form': risk_form,
        'rehab_form': rehab_form,
    }
    return render(request, 'prison/edit_convicted_details.html', context)


@login_required
def edit_remand_details(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user):
        raise PermissionDenied("You do not have permission to edit remand prisoner details.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id, prisoner_class='remand')
    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied("You do not have permission for this prisoner's station.")

    remand, _ = RemandPrisoner.objects.get_or_create(prisoner=prisoner)
    particulars, _ = PrisonerParticulars.objects.get_or_create(prisoner=prisoner)
    physical, _ = PhysicalCharacteristics.objects.get_or_create(prisoner=prisoner)

    if request.method == 'POST':
        remand_form = RemandPrisonerForm(request.POST, instance=remand)
        particulars_form = PrisonerParticularsForm(request.POST, instance=particulars)
        physical_form = PhysicalCharacteristicsForm(request.POST, instance=physical)

        if all([
            remand_form.is_valid(),
            particulars_form.is_valid(),
            physical_form.is_valid(),
        ]):
            remand_form.save()
            particulars_form.save()
            physical_form.save()

            ActivityLog.objects.create(
                user=request.user,
                action='update_details',
                model='RemandPrisoner',
                object_id=prisoner.id,
                details=f'Updated details for remand prisoner {prisoner.prisoner_number}'
            )

            messages.success(request, 'Remand prisoner details updated successfully.')
            return redirect('prisoner_detail', prisoner_id=prisoner.id)
        else:
            messages.error(request, "Please correct the validation errors in the forms.")
    else:
        remand_form = RemandPrisonerForm(instance=remand)
        particulars_form = PrisonerParticularsForm(instance=particulars)
        physical_form = PhysicalCharacteristicsForm(instance=physical)

    context = {
        'prisoner': prisoner,
        'remand_form': remand_form,
        'particulars_form': particulars_form,
        'physical_form': physical_form,
    }
    return render(request, 'prison/edit_remand_details.html', context)


@login_required
def delete_prisoner(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user):
        raise PermissionDenied("You do not have permission to delete prisoners.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id)

    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied('You do not have permission to delete this prisoner.')

    if request.method == 'POST':
        prisoner.is_active = False
        prisoner.date_released = timezone.now().date()
        prisoner.save()

        ActivityLog.objects.create(
            user=request.user,
            action='soft_delete',
            model='Prisoner',
            object_id=prisoner.id,
            details=f'Soft-deleted prisoner {prisoner.prisoner_number}'
        )

        messages.success(request, f'Prisoner {prisoner.prisoner_number} deactivated successfully.')
        return redirect('prisoner_list')

    return render(request, 'prison/delete_prisoner_confirm.html', {'prisoner': prisoner})


@login_required
def transfer_prisoner(request, prisoner_id):
    prisoner = get_object_or_404(Prisoner, id=prisoner_id)

    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()

    if not (is_super_admin_user or is_prison_admin_user):
        raise PermissionDenied('You do not have permission to transfer prisoners.')

    if prisoner.prison_station is None and not is_super_admin_user:
        raise PermissionDenied("This prisoner is not currently assigned to your station for transfer.")

    if request.method == 'POST':
        form = PrisonerTransferForm(request.POST, prisoner=prisoner, user=request.user)

        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.prisoner = prisoner
            transfer.from_prison = prisoner.prison_station
            transfer.transferred_by = request.user
            transfer.save()

            prisoner.prison_station = transfer.to_prison
            prisoner.save()

            ActivityLog.objects.create(
                user=request.user,
                action='transfer',
                model='Prisoner',
                object_id=prisoner.id,
                details=f'Transferred prisoner {prisoner.prisoner_number} from {transfer.from_prison.name if transfer.from_prison else "Unassigned"} to {transfer.to_prison.name}'
            )

            messages.success(request, 'Prisoner transferred successfully.')
            return redirect('prisoner_detail', prisoner_id=prisoner.id)
        else:
            messages.error(request, "Please correct the errors in the transfer form.")
    else:
        form = PrisonerTransferForm(prisoner=prisoner, user=request.user)

    context = {
        'form': form,
        'prisoner': prisoner,
    }
    return render(request, 'prison/transfer_prisoner.html', context)


@login_required
def apply_sentence_reduction(request, prisoner_id):
    prisoner = get_object_or_404(Prisoner, id=prisoner_id, prisoner_class='convicted')

    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()

    if not (is_super_admin_user or is_warden_user or is_prison_admin_user):
        raise PermissionDenied('You do not have permission to apply sentence reductions.')

    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied("You do not have permission for this prisoner's station.")

    try:
        convicted = prisoner.convicted_details
    except ConvictedPrisoner.DoesNotExist:
        messages.error(request, "Convicted prisoner details not found.")
        return redirect('prisoner_detail', prisoner_id=prisoner.id)

    if request.method == 'POST':
        form = SentenceReductionForm(request.POST, instance=convicted)

        if form.is_valid():
            updated_convicted_details = form.save()

            release_record, created = ReleaseOnRemission.objects.update_or_create(
                prisoner=prisoner,
                defaults={
                    'release_date': updated_convicted_details.date_of_release_on_remission,
                    'original_sentence': updated_convicted_details.sentence,
                    'remission_months': updated_convicted_details.sentence / 3,
                    'reduction_months': updated_convicted_details.reduction_months,
                    'reduction_reason': updated_convicted_details.reduction_notes,
                    'processed_by': request.user
                }
            )

            ActivityLog.objects.create(
                user=request.user,
                action='sentence_reduction',
                model='ConvictedPrisoner',
                object_id=prisoner.id,
                details=f'Applied sentence reduction for prisoner {prisoner.prisoner_number}. New release date: {updated_convicted_details.date_of_release_on_remission}'
            )

            messages.success(request, 'Sentence reduction applied successfully.')
            return redirect('prisoner_detail', prisoner_id=prisoner.id)
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = SentenceReductionForm(instance=convicted)

    context = {
        'form': form,
        'prisoner': prisoner,
        'convicted': convicted,
    }
    return render(request, 'prison/apply_sentence_reduction.html', context)


# ============ REPORT GENERATION VIEWS ============

@login_required
def generate_prisoner_report(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()

    if not (is_super_admin_user or is_prison_admin_user or
            is_reception_user or is_warden_user):
        raise PermissionDenied("You do not have permission to generate a report for this prisoner.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id)

    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied('You do not have permission to generate a report for this prisoner.')

    template_path = 'prison/prisoner_report_pdf.html'

    context = {
        'prisoner': prisoner,
        'today': datetime.now().date(),
        'physical': getattr(prisoner, 'physical', None),
        'particulars': getattr(prisoner, 'particulars', None),
        'medical_records': prisoner.medical_records.all().order_by('-record_date'),
        'transfers': prisoner.transfers.all().order_by('-transfer_date'),
    }

    if prisoner.prisoner_class == 'convicted':
        context.update({
            'convicted_details': getattr(prisoner, 'convicted_details', None),
            'risk_assessment': getattr(prisoner, 'risk_assessment', None),
            'rehabilitation': getattr(prisoner, 'rehabilitation', None),
        })
    elif prisoner.prisoner_class == 'remand':
        context['remand_details'] = getattr(prisoner, 'remand_details', None)

    html_string = render_to_string(template_path, context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="prisoner_{prisoner.prisoner_number}_report.pdf"'

    pisa_status = pisa.CreatePDF(
        html_string, dest=response, encoding='utf-8'
    )

    if pisa_status.err:
        logger.error(f"PDF generation error for prisoner {prisoner_id}: {pisa_status.err}")
        return HttpResponse(f'We had some errors generating the PDF: {pisa_status.err}')

    return response


@login_required
def upcoming_releases_report(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()

    if not (is_super_admin_user or is_prison_admin_user or
            is_warden_user or is_reception_user):
        raise PermissionDenied("You do not have permission to view this report.")

    today = datetime.now().date()
    next_30_days = today + timedelta(days=30)

    base_query = ConvictedPrisoner.objects.filter(
        prisoner__is_active=True,
        date_of_release_on_remission__gte=today,
        date_of_release_on_remission__lte=next_30_days
    )

    if not is_super_admin_user and hasattr(request.user, 'prison_station') and request.user.prison_station:
        base_query = base_query.filter(prisoner__prison_station=request.user.prison_station)

    upcoming_convicted_releases = base_query.order_by('date_of_release_on_remission')

    report_format = request.GET.get('format', 'html')

    if report_format == 'pdf':
        template_path = 'prison/upcoming_releases_report_pdf.html'
        context = {
            'releases': upcoming_convicted_releases,
            'reporting_period_start': today,
            'reporting_period_end': next_30_days,
            'user': request.user,
            'station_name': request.user.prison_station.name if hasattr(request.user,
                                                                        'prison_station') and request.user.prison_station and not is_super_admin_user else "All Stations"
        }
        html_string = render_to_string(template_path, context)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="upcoming_releases_report.pdf"'
        pisa_status = pisa.CreatePDF(html_string, dest=response, encoding='utf-8')
        if pisa_status.err:
            return HttpResponse(f'We had some errors generating the PDF: {pisa_status.err}')
        return response

    elif report_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="upcoming_releases_report.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Prisoner Number', 'Full Name', 'Prison Station',
            'Release Date', 'Sentence (Months)',
            'Calculated Remission (Months)', 'Additional Reduction (Months)', 'Offense', 'Date Admitted'
        ])
        for cp in upcoming_convicted_releases:
            writer.writerow([
                cp.prisoner.prisoner_number,
                cp.prisoner.full_name,
                cp.prisoner.prison_station.name if cp.prisoner.prison_station else 'N/A',
                cp.date_of_release_on_remission.strftime('%Y-%m-%d') if cp.date_of_release_on_remission else 'N/A',
                cp.sentence,
                cp.sentence / 3,
                cp.reduction_months if cp.reduction_months is not None else 0,
                cp.offense,
                cp.prisoner.date_admitted.strftime('%Y-%m-%d') if cp.prisoner.date_admitted else 'N/A',
            ])
        return response

    context = {
        'releases': upcoming_convicted_releases,
        'reporting_period_start': today,
        'reporting_period_end': next_30_days,
    }
    return render(request, 'prison/upcoming_releases_list.html', context)


# ============ PRISON STATION MANAGEMENT VIEWS ============

@login_required
def create_prison_station(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()

    if not is_super_admin_user:
        raise PermissionDenied("You do not have permission to create prison stations.")

    if request.method == 'POST':
        form = PrisonStationForm(request.POST)
        if form.is_valid():
            station = form.save(commit=False)
            if hasattr(request.user, 'id') and request.user.id is not None:
                station.created_by = request.user
            station.save()
            messages.success(request, f'Prison station "{station.name}" created successfully!')
            return redirect('manage_prison_stations')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PrisonStationForm()

    return render(request, 'prison/create_prison_station.html', {'form': form})


@login_required
def manage_prison_stations(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()

    if not is_super_admin_user:
        raise PermissionDenied('You do not have permission to access this page.')

    stations = PrisonStation.objects.all().order_by('name')

    if request.method == 'POST' and 'add_station' in request.POST:
        form = PrisonStationForm(request.POST)
        if form.is_valid():
            station = form.save(commit=False)
            if hasattr(request.user, 'id') and request.user.id is not None:
                station.created_by = request.user
            station.save()
            messages.success(request, 'Prison station added successfully.')
            return redirect('manage_prison_stations')
        else:
            messages.error(request, "Error adding station. Please check the form.")
    else:
        form = PrisonStationForm()

    context = {
        'stations': stations,
        'form': form,
    }
    return render(request, 'prison/manage_prison_stations.html', context)


@login_required
def edit_prison_station(request, station_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()

    if not is_super_admin_user:
        raise PermissionDenied('You do not have permission to access this page.')

    station = get_object_or_404(PrisonStation, id=station_id)

    if request.method == 'POST':
        form = PrisonStationForm(request.POST, instance=station)

        if form.is_valid():
            form.save()
            messages.success(request, 'Prison station updated successfully.')
            return redirect('manage_prison_stations')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PrisonStationForm(instance=station)

    context = {
        'form': form,
        'station': station,
    }
    return render(request, 'prison/edit_prison_station.html', context)


@login_required
def delete_prison_station(request, station_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()

    if not is_super_admin_user:
        raise PermissionDenied('You do not have permission to access this page.')

    station = get_object_or_404(PrisonStation, id=station_id)

    if request.method == 'POST':
        if Prisoner.objects.filter(prison_station=station, is_active=True).exists():
            messages.error(request,
                           f'Cannot delete prison station "{station.name}" as it has active prisoners assigned.')
            return redirect('manage_prison_stations')

        station_name = station.name
        station.delete()
        messages.success(request, f'Prison station "{station_name}" deleted successfully.')
        return redirect('manage_prison_stations')

    return render(request, 'prison/delete_prison_station_confirm.html', {'station': station})


# ============ API ENDPOINTS ============

@login_required
def prison_statistics_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()

    if not is_super_admin_user and not (hasattr(request.user, 'prison_station') and request.user.prison_station):
        raise PermissionDenied('Forbidden: No prison station assigned or insufficient permissions.')

    prisoners_qs_api = Prisoner.objects.filter(is_active=True)
    if not is_super_admin_user:
        prisoners_qs_api = prisoners_qs_api.filter(prison_station=request.user.prison_station)

    counts_by_class = list(prisoners_qs_api.values('prisoner_class').annotate(count=Count('id')).order_by(
        'prisoner_class'))

    counts_by_station = []
    if is_super_admin_user:
        counts_by_station = list(PrisonStation.objects.annotate(
            prisoner_count=Count('prisoner', filter=Q(prisoner__is_active=True))
        ).values('name', 'prisoner_count').order_by('name'))
    elif hasattr(request.user, 'prison_station') and request.user.prison_station:
        station_name = request.user.prison_station.name
        station_count = prisoners_qs_api.count()
        counts_by_station = [{'name': station_name, 'prisoner_count': station_count}]

    risk_distribution_qs_api = RiskAssessment.objects.filter(prisoner__in=prisoners_qs_api)
    risk_distribution = list(risk_distribution_qs_api.values('risk_level').annotate(count=Count('id')).order_by(
        'risk_level'))

    total_active_prisoners = prisoners_qs_api.count()
    recidivism_count_api = risk_distribution_qs_api.filter(previous_conviction=True).count()
    recidivism_rate_api = (recidivism_count_api / total_active_prisoners * 100) if total_active_prisoners > 0 else 0

    female_prisoners_qs_api = prisoners_qs_api.filter(sex='female')
    children_count_api = 0
    if female_prisoners_qs_api.exists():
        children_count_api = sum(
            p.physical.children_count
            for p in female_prisoners_qs_api
            if hasattr(p, 'physical') and p.physical and p.physical.children_count is not None
        )

    data = {
        'counts_by_class': counts_by_class,
        'counts_by_station': counts_by_station,
        'risk_distribution': risk_distribution,
        'recidivism_rate': round(recidivism_rate_api, 2),
        'total_prisoners': total_active_prisoners,
        'children_count': children_count_api,
    }
    return JsonResponse(data)


# ============ VISITOR MANAGEMENT VIEWS ============

class VisitorListView(LoginRequiredMixin, ListView):
    model = Visitor
    template_name = 'prison/visitor_list.html'
    context_object_name = 'visitors'
    paginate_by = 15

    def get_queryset(self):
        queryset = super().get_queryset().select_related('prisoner', 'approved_by', 'created_by')
        is_super_user_request = hasattr(self.request.user, 'is_superuser') and self.request.user.is_superuser

        if not is_super_user_request:
            if hasattr(self.request.user, 'prison_station') and self.request.user.prison_station:
                queryset = queryset.filter(prisoner__prison_station=self.request.user.prison_station)
            else:
                queryset = Visitor.objects.none()
                messages.warning(self.request, "You are not assigned to a prison station. Cannot display visitor records.")

        approval_filter = self.request.GET.get('approved', None)
        if approval_filter is not None:
            if approval_filter.lower() == 'true':
                queryset = queryset.filter(is_approved=True)
            elif approval_filter.lower() == 'false':
                queryset = queryset.filter(is_approved=False)
            elif approval_filter.lower() == 'pending':
                queryset = queryset.filter(is_approved=False, approved_by__isnull=True)

        start_date_str = self.request.GET.get('start_date', '')
        end_date_str = self.request.GET.get('end_date', '')

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(visit_date__gte=start_date)
            except ValueError:
                messages.error(self.request, "Invalid start date format. Please use YYYY-MM-DD.")
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(visit_date__lte=end_date)
            except ValueError:
                messages.error(self.request, "Invalid end date format. Please use YYYY-MM-DD.")

        search_query = self.request.GET.get('search_query', '')
        if search_query:
            queryset = queryset.filter(
                Q(full_name__icontains=search_query) |
                Q(prisoner__prisoner_number__icontains=search_query) |
                Q(prisoner__first_name__icontains=search_query) |
                Q(prisoner__surname__icontains=search_query)
            )

        return queryset.order_by('-visit_date', '-visit_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_approved_filter'] = self.request.GET.get('approved', '')
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        context['current_search_query'] = self.request.GET.get('search_query', '')
        return context


class VisitorCreateView(RoleRequiredMixin, CreateView):
    model = Visitor
    form_class = VisitorForm
    template_name = 'prison/visitor_form.html'
    success_url = reverse_lazy('visitor_list')
    roles_required = ['reception', 'visitor_attendant', 'warden', 'prison_admin', 'superuser']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        visitor = form.save(commit=False)
        visitor.created_by = self.request.user
        visitor.save()
        form.save_m2m()

        messages.success(self.request,
                         f"Visit request for {visitor.full_name} to see {visitor.prisoner.full_name} has been submitted and is pending approval.")
        ActivityLog.objects.create(
            user=self.request.user, action='create_visitor_request', model='Visitor',
            object_id=visitor.id,
            details=f'Created visitor request for {visitor.full_name} for prisoner {visitor.prisoner.prisoner_number}'
        )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "Request New Visit"
        return context


class VisitorUpdateView(RoleRequiredMixin, UpdateView):
    model = Visitor
    form_class = VisitorForm
    template_name = 'prison/visitor_form.html'
    success_url = reverse_lazy('visitor_list')
    roles_required = ['reception', 'visitor_attendant', 'warden', 'prison_admin', 'superuser']

    def get_queryset(self):
        queryset = super().get_queryset()
        is_super_user_request = hasattr(self.request.user, 'is_superuser') and self.request.user.is_superuser
        if not is_super_user_request:
            if hasattr(self.request.user, 'prison_station') and self.request.user.prison_station:
                return queryset.filter(prisoner__prison_station=self.request.user.prison_station)
            return queryset.none()
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        visitor = form.save(commit=False)
        visitor.save()
        form.save_m2m()

        messages.success(self.request, f"Visit request for {visitor.full_name} updated.")
        ActivityLog.objects.create(
            user=self.request.user, action='update_visitor_request', model='Visitor',
            object_id=visitor.id, details=f'Updated visitor request for {visitor.full_name}'
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = f"Update Visit Request for {self.object.full_name}"
        return context


class VisitorDetailView(LoginRequiredMixin, DetailView):
    model = Visitor
    template_name = 'prison/visitor_detail.html'
    context_object_name = 'visitor'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('prisoner', 'approved_by', 'created_by')
        is_super_user_request = hasattr(self.request.user, 'is_superuser') and self.request.user.is_superuser
        if not is_super_user_request:
            if hasattr(self.request.user, 'prison_station') and self.request.user.prison_station:
                return queryset.filter(prisoner__prison_station=self.request.user.prison_station)
            return queryset.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Visitor Details: {self.object.full_name}"
        return context


class VisitorApproveView(RoleRequiredMixin, UpdateView):
    model = Visitor
    fields = []
    template_name = 'prison/visitor_approve_confirm.html'
    success_url = reverse_lazy('visitor_list')
    roles_required = ['reception', 'warden', 'prison_admin', 'superuser']

    def get_queryset(self):
        queryset = super().get_queryset()
        is_super_user_request = hasattr(self.request.user, 'is_superuser') and self.request.user.is_superuser
        if not is_super_user_request:
            if hasattr(self.request.user, 'prison_station') and self.request.user.prison_station:
                return queryset.filter(prisoner__prison_station=self.request.user.prison_station)
            return queryset.none()
        return queryset

    def form_valid(self, form):
        visitor = self.get_object()
        if visitor.is_approved:
            messages.info(self.request, f"Visit for {visitor.full_name} is already approved.")
        else:
            visitor.is_approved = True
            visitor.approved_by = self.request.user
            visitor.save()
            messages.success(self.request,
                             f"Visit for {visitor.full_name} to see {visitor.prisoner.full_name} has been APPROVED.")
            ActivityLog.objects.create(
                user=self.request.user, action='approve_visitor_request', model='Visitor',
                object_id=visitor.id, details=f'Approved visitor request for {visitor.full_name}'
            )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['visitor_to_approve'] = self.get_object()
        return context


# ============ MEDICAL RECORD VIEWS ============

class MedicalRecordListView(RoleRequiredMixin, ListView):
    model = MedicalRecord
    template_name = 'prison/medical_record_list.html'
    context_object_name = 'medical_records'
    paginate_by = 15
    roles_required = ['medical_officer', 'prison_admin', 'superuser']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('prisoner', 'recorded_by')
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                queryset = queryset.filter(prisoner__prison_station=user.prison_station)
            else:
                queryset = MedicalRecord.objects.none()

        category = self.request.GET.get('category', '')
        if category:
            queryset = queryset.filter(category=category)

        start_date_str = self.request.GET.get('start_date', '')
        end_date_str = self.request.GET.get('end_date', '')
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(record_date__gte=start_date)
            except ValueError:
                messages.error(self.request, "Invalid start date format. Please use YYYY-MM-DD.")
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(record_date__lte=end_date)
            except ValueError:
                messages.error(self.request, "Invalid end date format. Please use YYYY-MM-DD.")

        search_query = self.request.GET.get('search_query', '')
        if search_query:
            queryset = queryset.filter(
                Q(prisoner__prisoner_number__icontains=search_query) |
                Q(prisoner__first_name__icontains=search_query) |
                Q(prisoner__surname__icontains=search_query) |
                Q(diagnosis__icontains=search_query) |
                Q(treatment__icontains=search_query)
            )
        return queryset.order_by('-record_date', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = MedicalRecord.MEDICAL_CATEGORIES
        context['current_category'] = self.request.GET.get('category', '')
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        context['current_search_query'] = self.request.GET.get('search_query', '')
        return context


class MedicalRecordCreateView(RoleRequiredMixin, CreateView):
    model = MedicalRecord
    form_class = MedicalRecordForm
    template_name = 'prison/medical_record_form.html'
    success_url = reverse_lazy('medical_record_list')
    roles_required = ['medical_officer', 'prison_admin', 'superuser']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        record = form.save(commit=False)
        record.recorded_by = self.request.user
        record.save()
        messages.success(self.request, f"Medical record for prisoner {record.prisoner.full_name} created successfully.")
        ActivityLog.objects.create(
            user=self.request.user, action='create_medical_record', model='MedicalRecord',
            object_id=record.id, details=f'Created medical record for {record.prisoner.prisoner_number}'
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "Add New Medical Record"
        return context


class MedicalRecordUpdateView(RoleRequiredMixin, UpdateView):
    model = MedicalRecord
    form_class = MedicalRecordForm
    template_name = 'prison/medical_record_form.html'
    success_url = reverse_lazy('medical_record_list')
    context_object_name = 'medical_record'
    roles_required = ['medical_officer', 'prison_admin', 'superuser']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                return queryset.filter(prisoner__prison_station=user.prison_station)
            return queryset.none()
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        record = form.save()
        messages.success(self.request, f"Medical record for prisoner {record.prisoner.full_name} updated successfully.")
        ActivityLog.objects.create(
            user=self.request.user, action='update_medical_record', model='MedicalRecord',
            object_id=record.id, details=f'Updated medical record for {record.prisoner.prisoner_number}'
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = f"Edit Medical Record for {self.object.prisoner.full_name}"
        return context


class MedicalRecordDetailView(RoleRequiredMixin, DetailView):
    model = MedicalRecord
    template_name = 'prison/medical_record_detail.html'
    context_object_name = 'medical_record'
    roles_required = ['medical_officer', 'prison_admin', 'superuser', 'warden']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('prisoner', 'recorded_by')
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                return queryset.filter(prisoner__prison_station=user.prison_station)
            return queryset.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Medical Record for {self.object.prisoner.full_name} on {self.object.record_date}"
        return context


class MedicalRecordDeleteView(RoleRequiredMixin, DeleteView):
    model = MedicalRecord
    template_name = 'prison/medical_record_confirm_delete.html'
    success_url = reverse_lazy('medical_record_list')
    context_object_name = 'medical_record'
    roles_required = ['medical_officer', 'prison_admin', 'superuser']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station and (
                    hasattr(user, 'is_medical_officer') and user.is_medical_officer() or hasattr(user,
                                                                                                 'is_prison_admin') and user.is_prison_admin()):
                return queryset.filter(prisoner__prison_station=user.prison_station)
            return queryset.none()
        return queryset

    def form_valid(self, form):
        record = self.get_object()
        prisoner_name = record.prisoner.full_name
        record_date = record.record_date
        record_id = record.id

        response = super().form_valid(form)

        messages.success(self.request,
                         f"Medical record for prisoner {prisoner_name} (dated {record_date}) deleted successfully.")
        ActivityLog.objects.create(
            user=self.request.user, action='delete_medical_record', model='MedicalRecord',
            object_id=str(record_id),
            details=f'Deleted medical record (ID: {record_id}) for prisoner {prisoner_name}'
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Confirm Delete Medical Record for {self.object.prisoner.full_name}"
        return context


# ============ INCIDENT REPORT VIEWS ============

class IncidentReportListView(LoginRequiredMixin, ListView):
    model = IncidentReport
    template_name = 'prison/incident_report_list.html'
    context_object_name = 'incidents'
    paginate_by = 15

    def get_queryset(self):
        queryset = super().get_queryset().select_related('reported_by').prefetch_related('involved_prisoners')
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                queryset = queryset.filter(
                    Q(involved_prisoners__prison_station=user.prison_station) |
                    Q(reported_by=user)
                ).distinct()
            else:
                queryset = queryset.filter(reported_by=user).distinct()
                messages.warning(self.request, "You are not assigned to a prison station; showing only incidents you reported.")

        severity = self.request.GET.get('severity', '')
        if severity:
            queryset = queryset.filter(severity=severity)

        follow_up_str = self.request.GET.get('follow_up', '')
        if follow_up_str:
            if follow_up_str.lower() == 'true':
                queryset = queryset.filter(follow_up_required=True)
            elif follow_up_str.lower() == 'false':
                queryset = queryset.filter(follow_up_required=False)

        start_date_str = self.request.GET.get('start_date', '')
        end_date_str = self.request.GET.get('end_date', '')
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(date_occurred__gte=start_date)
            except ValueError:
                messages.error(self.request, "Invalid start date.")
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(date_occurred__lte=end_date)
            except ValueError:
                messages.error(self.request, "Invalid end date.")

        return queryset.order_by('-date_occurred', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['severities'] = IncidentReport.SEVERITY_CHOICES
        context['current_severity'] = self.request.GET.get('severity', '')
        context['current_follow_up'] = self.request.GET.get('follow_up', '')
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        return context


class IncidentReportCreateView(LoginRequiredMixin, CreateView):
    model = IncidentReport
    form_class = IncidentReportForm
    template_name = 'prison/incident_report_form.html'
    success_url = reverse_lazy('incident_report_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        incident = form.save(commit=False)
        incident.reported_by = self.request.user
        incident.save()
        form.save_m2m()
        messages.success(self.request, f"Incident report '{incident.title}' created successfully.")
        ActivityLog.objects.create(
            user=self.request.user, action='create_incident_report', model='IncidentReport',
            object_id=incident.id, details=f'Created incident report: {incident.title}'
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "Report New Incident"
        return context


class IncidentReportDetailView(LoginRequiredMixin, DetailView):
    model = IncidentReport
    template_name = 'prison/incident_report_detail.html'
    context_object_name = 'incident'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('reported_by').prefetch_related('involved_prisoners__prison_station')
        return queryset

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            can_view_based_on_station = False
            if hasattr(user, 'prison_station') and user.prison_station:
                if obj.involved_prisoners.filter(prison_station=user.prison_station).exists():
                    can_view_based_on_station = True

            if not (obj.reported_by == user or can_view_based_on_station):
                raise PermissionDenied("You do not have permission to view this incident report.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Incident Report: {self.object.title}"
        return context


# ============ ACTIVITY LOG VIEWS ============

class ActivityLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ActivityLog
    template_name = 'prison/activity_log_list.html'
    context_object_name = 'activities'
    paginate_by = 30

    def test_func(self):
        is_super_user_request = hasattr(self.request.user, 'is_superuser') and self.request.user.is_superuser
        is_prison_admin_request = hasattr(self.request.user, 'is_prison_admin') and self.request.user.is_prison_admin()
        return is_super_user_request or is_prison_admin_request

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to view the activity log.")
        return redirect('dashboard')

    def get_queryset(self):
        queryset = ActivityLog.objects.all().select_related('user')

        user_filter = self.request.GET.get('user_id', '')
        action_filter = self.request.GET.get('action_type', '')
        model_filter = self.request.GET.get('model_type', '')
        start_date_str = self.request.GET.get('start_date', '')
        end_date_str = self.request.GET.get('end_date', '')

        if user_filter:
            queryset = queryset.filter(user_id=user_filter)
        if action_filter:
            queryset = queryset.filter(action__icontains=action_filter)
        if model_filter:
            queryset = queryset.filter(model=model_filter)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                queryset = queryset.filter(timestamp__gte=start_date)
            except ValueError:
                messages.error(self.request, "Invalid start date format.")
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date_inclusive = end_date + timedelta(days=1)
                queryset = queryset.filter(timestamp__lt=end_date_inclusive)
            except ValueError:
                messages.error(self.request, "Invalid end date format.")

        return queryset.order_by('-timestamp')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_users'] = User.objects.filter(activitylog__isnull=False).distinct().order_by('username')
        context['action_types'] = ActivityLog.objects.values_list('action', flat=True).distinct().order_by('action')
        context['model_types'] = ActivityLog.objects.values_list('model', flat=True).distinct().order_by('model')
        context['current_user_id'] = self.request.GET.get('user_id', '')
        context['current_action_type'] = self.request.GET.get('action_type', '')
        context['current_model_type'] = self.request.GET.get('model_type', '')
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        return context


# ============ PRISONER ITEM MANAGEMENT VIEWS ============

class PrisonerItemListView(LoginRequiredMixin, DetailView):
    model = Prisoner
    template_name = 'prison/prisoner_items_list.html'
    context_object_name = 'prisoner'
    pk_url_kwarg = 'prisoner_id'

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('items')
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()
        is_prison_admin_user = hasattr(user, 'is_prison_admin') and user.is_prison_admin()
        is_reception_user = hasattr(user, 'is_reception') and user.is_reception()
        is_warden_user = hasattr(user, 'is_warden') and user.is_warden()

        if not (is_super_admin_user or is_prison_admin_user or is_reception_user or is_warden_user):
            raise PermissionDenied("You do not have permission to view prisoner items.")

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                queryset = queryset.filter(prison_station=user.prison_station)
            else:
                queryset = Prisoner.objects.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prisoner = self.get_object()
        context['items'] = prisoner.items.all().order_by('-date_received')
        context['money_items'] = prisoner.items.filter(item_type='money').order_by('-date_received')
        context['total_money_balance'] = sum(item.current_amount for item in context['money_items'])
        return context


class AddPrisonerItemView(RoleRequiredMixin, CreateView):
    model = PrisonerItem
    form_class = PrisonerItemForm
    template_name = 'prison/add_prisoner_item.html'
    roles_required = ['reception', 'warden', 'prison_admin', 'superuser']

    def dispatch(self, request, *args, **kwargs):
        self.prisoner = get_object_or_404(Prisoner, id=self.kwargs['prisoner_id'])
        is_super_user_request = hasattr(request.user, 'is_superuser') and request.user.is_superuser
        if not is_super_user_request and (
                not self.prisoner.prison_station or self.prisoner.prison_station != request.user.prison_station):
            raise PermissionDenied("You do not have permission to add items for this prisoner's station.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('prisoner_item_list', kwargs={'prisoner_id': self.prisoner.id})

    def form_valid(self, form):
        item = form.save(commit=False)
        item.prisoner = self.prisoner
        item.received_by = self.request.user
        item.save()

        ActivityLog.objects.create(
            user=self.request.user, action='add_item', model='PrisonerItem',
            object_id=item.id,
            details=f'Added item "{item.description}" ({item.get_item_type_display()}) for prisoner {self.prisoner.prisoner_number}'
        )
        messages.success(self.request, f"Item '{item.description}' added successfully for {self.prisoner.full_name}.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['prisoner'] = self.prisoner
        context['form_title'] = f"Add New Item for {self.prisoner.full_name}"
        return context


class WithdrawPrisonerMoneyView(RoleRequiredMixin, CreateView):
    model = PrisonerItemTransaction
    form_class = PrisonerItemTransactionForm
    template_name = 'prison/withdraw_prisoner_money.html'
    roles_required = ['reception', 'warden', 'prison_admin', 'superuser']

    def dispatch(self, request, *args, **kwargs):
        self.money_item = get_object_or_404(PrisonerItem, id=self.kwargs['pk'], item_type='money')
        is_super_user_request = hasattr(request.user, 'is_superuser') and request.user.is_superuser
        if not is_super_user_request and (
                not self.money_item.prisoner.prison_station or self.money_item.prisoner.prison_station != request.user.prison_station):
            raise PermissionDenied("You do not have permission to manage items for this prisoner's station.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['item'] = self.money_item
        return kwargs

    def get_success_url(self):
        return reverse_lazy('prisoner_item_list', kwargs={'prisoner_id': self.money_item.prisoner.id})

    def form_valid(self, form):
        transaction = form.save(commit=False)
        transaction.item = self.money_item
        transaction.transaction_type = 'withdrawal'
        transaction.transacted_by = self.request.user

        try:
            transaction.save()
            ActivityLog.objects.create(
                user=self.request.user, action='withdraw_money', model='PrisonerItemTransaction',
                object_id=transaction.id,
                details=f'Withdrew {transaction.amount} {self.money_item.currency} from {self.money_item.prisoner.full_name}\'s money item {self.money_item.id}'
            )
            messages.success(self.request,
                             f"Successfully withdrew {transaction.amount} {self.money_item.currency} from {self.money_item.prisoner.full_name}'s account.")
            return super().form_valid(form)
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    form.add_error(field if field != '__all__' else None, error)
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['money_item'] = self.money_item
        context['prisoner'] = self.money_item.prisoner
        context['form_title'] = f"Withdraw Money for {self.money_item.prisoner.full_name}"
        return context


class PrisonerItemDetailView(LoginRequiredMixin, DetailView):
    model = PrisonerItem
    template_name = 'prison/prisoner_item_detail.html'
    context_object_name = 'item'
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('prisoner', 'received_by').prefetch_related('transactions')
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()
        is_prison_admin_user = hasattr(user, 'is_prison_admin') and user.is_prison_admin()
        is_reception_user = hasattr(user, 'is_reception') and user.is_reception()
        is_warden_user = hasattr(user, 'is_warden') and user.is_warden()

        if not (is_super_admin_user or is_prison_admin_user or is_reception_user or is_warden_user):
            raise PermissionDenied("You do not have permission to view this item.")

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                queryset = queryset.filter(prisoner__prison_station=user.prison_station)
            else:
                queryset = PrisonerItem.objects.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        context['transactions'] = item.transactions.all().order_by('-transaction_date')
        return context


class CollectPrisonerItemView(RoleRequiredMixin, View):
    roles_required = ['reception', 'warden', 'prison_admin', 'superuser']

    def post(self, request, *args, **kwargs):
        item = get_object_or_404(PrisonerItem, id=self.kwargs['pk'])

        is_super_user_request = hasattr(request.user, 'is_superuser') and request.user.is_superuser
        if not is_super_user_request and (
                not item.prisoner.prison_station or item.prisoner.prison_station != request.user.prison_station):
            raise PermissionDenied("You do not have permission to collect items for this prisoner's station.")

        if item.item_type == 'money':
            messages.error(request, "Money items cannot be 'collected' in this manner. Use the withdrawal function.")
            return redirect('prisoner_item_list', prisoner_id=item.prisoner.id)

        if item.is_collected:
            messages.info(request, f"Item '{item.description}' for {item.prisoner.full_name} is already marked as collected.")
        else:
            item.is_collected = True
            item.save()
            ActivityLog.objects.create(
                user=request.user, action='collect_item', model='PrisonerItem',
                object_id=item.id,
                details=f'Collected item "{item.description}" (ID: {item.id}) for prisoner {item.prisoner.prisoner_number}'
            )
            messages.success(request, f"Item '{item.description}' for {item.prisoner.full_name} has been marked as collected.")

        return redirect('prisoner_item_list', prisoner_id=item.prisoner.id)


# ============ EXTENDED SEARCH VIEW ============

@login_required
def extended_prisoner_search(request):
    form = ExtendedSearchForm(request.GET or None, user=request.user)
    prisoners = Prisoner.objects.filter(is_active=True).select_related('prison_station').prefetch_related(
        'convicted_details', 'risk_assessment')

    is_super_user_request = hasattr(request.user, 'is_superuser') and request.user.is_superuser

    if not is_super_user_request:
        if hasattr(request.user, 'prison_station') and request.user.prison_station:
            prisoners = prisoners.filter(prison_station=request.user.prison_station)
        else:
            prisoners = Prisoner.objects.none()
            messages.warning(request, "You haven't been assigned to a prison station. Cannot perform search.")
            return render(request, 'prison/extended_search.html', {'form': form, 'prisoners': Prisoner.objects.none()})

    if form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        gender = form.cleaned_data.get('gender')
        prisoner_class = form.cleaned_data.get('prisoner_class')
        previous_conviction = form.cleaned_data.get('previous_conviction')
        release_date_from = form.cleaned_data.get('release_date_from')
        release_date_to = form.cleaned_data.get('release_date_to')
        selected_prison_station = form.cleaned_data.get('prison_station')

        if search_query:
            prisoners = prisoners.filter(
                Q(prisoner_number__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(middle_name__icontains=search_query) |
                Q(surname__icontains=search_query)
            )

        if gender:
            prisoners = prisoners.filter(sex=gender)

        if prisoner_class:
            prisoners = prisoners.filter(prisoner_class=prisoner_class)

        if previous_conviction:
            if previous_conviction == 'yes':
                prisoners = prisoners.filter(risk_assessment__previous_conviction=True)
            elif previous_conviction == 'no':
                prisoners = prisoners.filter(risk_assessment__previous_conviction=False)

        if release_date_from:
            prisoners = prisoners.filter(
                prisoner_class='convicted',
                convicted_details__date_of_release_on_remission__gte=release_date_from
            )
        if release_date_to:
            prisoners = prisoners.filter(
                prisoner_class='convicted',
                convicted_details__date_of_release_on_remission__lte=release_date_to
            )

        if is_super_user_request and selected_prison_station:
            prisoners = prisoners.filter(prison_station=selected_prison_station)
        elif not is_super_user_request and hasattr(request.user, 'prison_station') and request.user.prison_station:
            if selected_prison_station and selected_prison_station != request.user.prison_station:
                prisoners = Prisoner.objects.none()

    prisoners = prisoners.distinct().order_by('prisoner_number')

    context = {
        'form': form,
        'prisoners': prisoners,
    }
    return render(request, 'prison/extended_search.html', context)


# ============ NOTIFICATION VIEWS ============

@login_required
def notification_list(request):
    user = request.user
    notifications = Notification.objects.filter(
        target_users=user
    ).exclude(
        expires_at__lt=timezone.now()
    ).order_by('-created_at')

    unread_notifications = notifications.filter(is_read=False)
    read_notifications = notifications.filter(is_read=True)

    notification_data = []

    for notification in unread_notifications:
        notification_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'priority': notification.priority,
            'is_read': notification.is_read,
            'action_required': notification.action_required,
            'action_url': notification.action_url,
            'due_date': notification.due_date.isoformat() if notification.due_date else None,
            'created_at': notification.created_at.isoformat(),
            'prisoner_name': notification.prisoner.full_name if notification.prisoner else None,
            'prisoner_number': notification.prisoner.prisoner_number if notification.prisoner else None,
        })

    for notification in read_notifications:
        notification_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'priority': notification.priority,
            'is_read': notification.is_read,
            'action_required': notification.action_required,
            'action_url': notification.action_url,
            'due_date': notification.due_date.isoformat() if notification.due_date else None,
            'created_at': notification.created_at.isoformat(),
            'prisoner_name': notification.prisoner.full_name if notification.prisoner else None,
            'prisoner_number': notification.prisoner.prisoner_number if notification.prisoner else None,
        })

    return JsonResponse({
        'notifications': notification_data,
        'unread_count': unread_notifications.count(),
        'total_count': notifications.count()
    })


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)

    if request.user in notification.target_users.all():
        notification.mark_as_read(request.user)
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(
        target_users=request.user,
        is_read=False
    ).update(
        is_read=True,
        read_at=timezone.now(),
        read_by=request.user
    )

    return JsonResponse({'success': True})


@login_required
def notification_count(request):
    count = Notification.objects.filter(
        target_users=request.user,
        is_read=False
    ).exclude(
        expires_at__lt=timezone.now()
    ).count()

    return JsonResponse({'unread_count': count})


# ============ RATION MANAGEMENT VIEWS ============

class RationItemListView(RoleRequiredMixin, ListView):
    model = RationItem
    template_name = 'prison/ration_item_list.html'
    context_object_name = 'ration_items'
    paginate_by = 10
    roles_required = ['warden', 'prison_admin', 'superuser', 'reception']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                queryset = queryset.filter(prison_station=user.prison_station)
            else:
                queryset = RationItem.objects.none()
                messages.warning(self.request, "You are not assigned to a prison station. Cannot view ration items.")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = RationItemForm(user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form_data = request.POST.copy()
        user = request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user and hasattr(user, 'prison_station') and user.prison_station:
            form_data['prison_station'] = user.prison_station.pk

        form = RationItemForm(form_data, user=user)

        if form.is_valid():
            ration_item = form.save(commit=False)

            if is_super_admin_user and not ration_item.prison_station:
                messages.error(request, "Superuser must select a prison station for the new ration item.")
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context['form'] = form
                return render(request, self.template_name, context)

            ration_item.save()
            messages.success(request, f"Ration item '{ration_item.name}' added successfully.")
            ActivityLog.objects.create(
                user=request.user, action='create', model='RationItem',
                object_id=ration_item.id, details=f'Added ration item: {ration_item.name} for {ration_item.prison_station.name}'
            )
            return redirect('ration_item_list')
        else:
            messages.error(request, "Error adding ration item. Please correct the errors.")
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context['form'] = form
            return render(request, self.template_name, context)


class RationItemUpdateView(RoleRequiredMixin, UpdateView):
    model = RationItem
    form_class = RationItemForm
    template_name = 'prison/ration_item_form.html'
    context_object_name = 'ration_item'
    pk_url_kwarg = 'pk'
    roles_required = ['warden', 'prison_admin', 'superuser']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                queryset = queryset.filter(prison_station=user.prison_station)
            else:
                queryset = RationItem.objects.none()
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        ration_item = form.save(commit=False)
        is_super_admin_user = hasattr(self.request.user, 'is_super_admin') and self.request.user.is_super_admin()

        if not is_super_admin_user and hasattr(self.request.user, 'prison_station') and self.request.user.prison_station:
            ration_item.prison_station = self.request.user.prison_station

        ration_item.save()
        messages.success(self.request, f"Ration item '{self.object.name}' updated successfully.")
        ActivityLog.objects.create(
            user=self.request.user, action='update', model='RationItem',
            object_id=self.object.id,
            details=f'Updated ration item: {self.object.name} for {self.object.prison_station.name}'
        )
        return redirect('ration_item_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = f"Edit Ration Item: {self.object.name}"
        return context


class RationItemDeleteView(RoleRequiredMixin, DeleteView):
    model = RationItem
    template_name = 'prison/ration_item_confirm_delete.html'
    success_url = reverse_lazy('ration_item_list')
    context_object_name = 'ration_item'
    roles_required = ['prison_admin', 'superuser']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        is_super_admin_user = hasattr(user, 'is_super_admin') and user.is_super_admin()

        if not is_super_admin_user:
            if hasattr(user, 'prison_station') and user.prison_station:
                queryset = queryset.filter(prison_station=user.prison_station)
            else:
                queryset = RationItem.objects.none()
        return queryset

    def form_valid(self, form):
        item_name = self.get_object().name
        item_id = self.get_object().id
        item_station_name = self.get_object().prison_station.name

        response = super().form_valid(form)

        messages.success(self.request, f"Ration item '{item_name}' deleted successfully.")
        ActivityLog.objects.create(
            user=self.request.user, action='delete', model='RationItem',
            object_id=str(item_id), details=f'Deleted ration item: {item_name} from {item_station_name}'
        )
        return response


class RationConsumptionCreateView(RoleRequiredMixin, CreateView):
    model = RationConsumption
    form_class = RationConsumptionForm
    template_name = 'prison/ration_consumption_form.html'
    success_url = reverse_lazy('ration_dashboard')
    roles_required = ['reception', 'warden', 'prison_admin', 'superuser']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.consumed_by = self.request.user
        form.instance.consumption_date = timezone.now().date()

        try:
            response = super().form_valid(form)
            messages.success(self.request,
                             f"Recorded {form.instance.quantity_used_kg}kg of {form.instance.item.name} for {form.instance.num_prisoners_fed} people.")
            ActivityLog.objects.create(
                user=self.request.user,
                action='record_consumption',
                model='RationConsumption',
                object_id=form.instance.id,
                details=f'Recorded {form.instance.quantity_used_kg}kg of {form.instance.item.name}'
            )
            return response
        except Exception as e:
            messages.error(self.request, f"Error recording consumption: {str(e)}")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "Record Daily Ration Consumption"

        if hasattr(self.request.user, 'prison_station') and self.request.user.prison_station:
            active_prisoners = Prisoner.objects.filter(
                prison_station=self.request.user.prison_station,
                is_active=True
            )
            total_inmates = active_prisoners.count()
            children_count = sum(
                p.physical.children_count for p in active_prisoners.filter(sex='female')
                if hasattr(p, 'physical') and p.physical and p.physical.children_count is not None
            )
            context['total_people_requiring_ration'] = total_inmates + children_count
            context['recommended_ration_per_person_kg'] = Decimal('0.680')

        return context


class RationProcurementCreateView(RoleRequiredMixin, CreateView):
    model = RationProcurement
    form_class = RationProcurementForm
    template_name = 'prison/ration_procurement_form.html'
    success_url = reverse_lazy('ration_dashboard')
    roles_required = ['warden', 'prison_admin', 'superuser']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        procurement = form.save(commit=False)
        procurement.procured_by = self.request.user
        procurement.save()
        messages.success(self.request,
                         f"Procurement of {procurement.quantity_procured_kg}kg of {procurement.item.name} recorded successfully.")
        ActivityLog.objects.create(
            user=self.request.user, action='record_procurement', model='RationProcurement',
            object_id=procurement.id,
            details=f'Recorded procurement of {procurement.quantity_procured_kg}kg of {procurement.item.name} from {procurement.supplier or "N/A"}.'
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = "Record New Ration Procurement"
        return context


# ============ FINGERPRINT / BIOMETRIC VIEWS ============

@login_required
def capture_fingerprint(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user or is_warden_user):
        raise PermissionDenied("You do not have permission to capture fingerprints.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id)

    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied("You do not have permission for this prisoner's station.")

    if request.method == 'POST' and 'recidivism_confirmed' in request.POST:
        form = RecidivismConfirmationForm(request.POST)

        if form.is_valid():
            confirmed = form.cleaned_data.get('confirmed')
            notes = form.cleaned_data.get('notes', '')
            link_previous = form.cleaned_data.get('link_previous_record', True)

            if confirmed:
                prisoner.is_recidivist = True
                prisoner.recidivism_detected_at = timezone.now()
                prisoner.recidivism_detected_by = request.user

                if notes:
                    prisoner.recidivism_notes = notes

                matched_prisoner_id = request.session.get('recidivism_matched_prisoner_id')
                if matched_prisoner_id and link_previous:
                    try:
                        matched_prisoner = Prisoner.objects.get(id=matched_prisoner_id)
                        prisoner.previous_identities.add(matched_prisoner)
                        prisoner.recidivism_notes += f"\nLinked to: {matched_prisoner.prisoner_number} ({matched_prisoner.full_name})"
                    except Prisoner.DoesNotExist:
                        pass

                prisoner.save()

                messages.success(
                    request,
                    f"✅ Recidivism confirmed for {prisoner.full_name}. This person has been flagged as a recidivist."
                )

                ActivityLog.objects.create(
                    user=request.user,
                    action='confirm_recidivism',
                    model='Prisoner',
                    object_id=prisoner.id,
                    details=f'Confirmed recidivism for prisoner {prisoner.prisoner_number} - Notes: {notes}'
                )

                request.session.pop('recidivism_data', None)
                request.session.pop('recidivism_matched_prisoner_id', None)

                return redirect('prisoner_detail', prisoner_id=prisoner.id)
            else:
                messages.warning(request, "Recidivism not confirmed. Please review the data.")
                return redirect('prisoner_detail', prisoner_id=prisoner.id)

    if request.method == 'POST' and 'fingerprint_data' in request.POST:
        form = FingerprintCaptureForm(request.POST)

        if form.is_valid():
            fingerprint_data = form.cleaned_data.get('fingerprint_data')
            quality_score = form.cleaned_data.get('quality_score', 80)
            device_id = form.cleaned_data.get('device_id')

            try:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0].strip()
                else:
                    ip_address = request.META.get('REMOTE_ADDR')

                user_agent = request.META.get('HTTP_USER_AGENT', '')

                recidivism_check = BiometricService.check_recidivism(fingerprint_data, threshold=80.0)

                if recidivism_check['is_recidivist']:
                    matched_prisoner = recidivism_check['matched_prisoner']
                    if matched_prisoner.pk != prisoner.pk:
                        request.session['recidivism_data'] = {
                            'match_score': recidivism_check['match_score'],
                            'previous_prisoner_number': matched_prisoner.prisoner_number,
                            'previous_full_name': matched_prisoner.full_name,
                            'previous_status': matched_prisoner.is_active,
                            'previous_release_date': str(
                                matched_prisoner.date_released) if matched_prisoner.date_released else None,
                        }
                        request.session['recidivism_matched_prisoner_id'] = matched_prisoner.id

                        context = {
                            'prisoner': prisoner,
                            'recidivism_data': recidivism_check,
                            'confirmation_form': RecidivismConfirmationForm(),
                            'fingerprint_data': fingerprint_data,
                            'quality_score': quality_score,
                            'device_id': device_id,
                        }
                        return render(request, 'prison/recidivism_confirmation.html', context)

                BiometricService.register_fingerprint(
                    prisoner=prisoner,
                    fingerprint_data=fingerprint_data,
                    quality_score=quality_score,
                    captured_by=request.user,
                    device_id=device_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )

                if prisoner.is_recidivist:
                    messages.warning(
                        request,
                        f"⚠️ This prisoner has been flagged as a recidivist! Previous record: {prisoner.previous_prisoner_numbers}"
                    )
                else:
                    messages.success(request, f"Fingerprint captured successfully for {prisoner.full_name}")

                return redirect('prisoner_detail', prisoner_id=prisoner.id)

            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Invalid fingerprint data. Please try again.")

    station = request.user.prison_station if hasattr(request.user, 'prison_station') else None
    devices = FingerprintDeviceManager.get_available_devices(station)
    lenovo_device = FingerprintDeviceManager.get_lenovo_integrated_device(station)

    context = {
        'prisoner': prisoner,
        'devices': devices,
        'lenovo_device': lenovo_device,
        'form': FingerprintCaptureForm(),
    }
    return render(request, 'prison/capture_fingerprint.html', context)


@login_required
@csrf_exempt
def fingerprint_search_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user or is_warden_user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        fingerprint_data = data.get('fingerprint_data')

        if not fingerprint_data:
            return JsonResponse({'error': 'Fingerprint data required'}, status=400)

        threshold = data.get('threshold', BiometricService.MATCH_THRESHOLD)

        matches = BiometricService.search_fingerprint(fingerprint_data, threshold)

        results = []
        for prisoner in matches:
            if not is_super_admin_user:
                if not prisoner.prison_station or prisoner.prison_station != request.user.prison_station:
                    continue

            results.append({
                'id': prisoner.id,
                'prisoner_number': prisoner.prisoner_number,
                'full_name': prisoner.full_name,
                'prison_station': prisoner.prison_station.name if prisoner.prison_station else None,
                'date_admitted': prisoner.date_admitted.isoformat(),
                'is_active': prisoner.is_active,
                'has_fingerprint': prisoner.has_fingerprint,
                'is_identity_verified': prisoner.is_identity_verified,
                'prisoner_class': prisoner.prisoner_class,
            })

        return JsonResponse({
            'success': True,
            'matches': results,
            'count': len(results)
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Fingerprint search failed: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def fingerprint_identify(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user or is_warden_user):
        raise PermissionDenied("You do not have permission to identify prisoners.")

    if request.method == 'POST':
        form = FingerprintSearchForm(request.POST)

        if form.is_valid():
            fingerprint_data = form.cleaned_data.get('fingerprint_data')
            threshold = form.cleaned_data.get('search_threshold', BiometricService.MATCH_THRESHOLD)

            matches = BiometricService.search_fingerprint(fingerprint_data, threshold)

            if matches:
                if not is_super_admin_user and hasattr(request.user, 'prison_station'):
                    matches = [p for p in matches if p.prison_station == request.user.prison_station]

                if matches:
                    best_match = matches[0]
                    previous_identities = best_match.previous_identities.all()

                    messages.success(
                        request,
                        f"Prisoner identified: {best_match.prisoner_number} - {best_match.full_name}"
                    )

                    context = {
                        'prisoner': best_match,
                        'previous_identities': previous_identities,
                        'matches': matches,
                        'form': form,
                    }
                    return render(request, 'prison/fingerprint_identify_result.html', context)
                else:
                    messages.warning(request, "No matching prisoner found in your station.")
            else:
                messages.warning(request, "No matching prisoner found.")

    else:
        form = FingerprintSearchForm()

    station = request.user.prison_station if hasattr(request.user, 'prison_station') else None
    devices = FingerprintDeviceManager.get_available_devices(station)
    lenovo_device = FingerprintDeviceManager.get_lenovo_integrated_device(station)

    context = {
        'form': form,
        'devices': devices,
        'lenovo_device': lenovo_device,
    }
    return render(request, 'prison/fingerprint_identify.html', context)


@login_required
def verify_prisoner_identity(request, prisoner_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user or is_warden_user):
        raise PermissionDenied("You do not have permission to verify prisoner identity.")

    prisoner = get_object_or_404(Prisoner, id=prisoner_id)

    if not is_super_admin_user and (
            not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
        raise PermissionDenied("You do not have permission for this prisoner.")

    if not prisoner.has_fingerprint:
        messages.warning(request,
                         f"{prisoner.full_name} does not have a registered fingerprint. Please capture their fingerprint first.")
        return redirect('prisoner_detail', prisoner_id=prisoner.id)

    if request.method == 'POST':
        form = FingerprintCaptureForm(request.POST)

        if form.is_valid():
            fingerprint_data = form.cleaned_data.get('fingerprint_data')

            is_verified, score = BiometricService.verify_identity(prisoner, fingerprint_data)

            if is_verified:
                prisoner.is_identity_verified = True
                prisoner.identity_verified_at = timezone.now()
                prisoner.identity_verified_by = request.user
                prisoner.save()

                messages.success(
                    request,
                    f"Identity verified for {prisoner.full_name} (Confidence: {score:.1f}%)"
                )

                ActivityLog.objects.create(
                    user=request.user,
                    action='verify_identity',
                    model='Prisoner',
                    object_id=prisoner.id,
                    details=f'Verified identity for prisoner {prisoner.prisoner_number} (Confidence: {score:.1f}%)'
                )
            else:
                messages.error(
                    request,
                    f"Identity verification failed. Match score: {score:.1f}%. Please try again."
                )

            return redirect('prisoner_detail', prisoner_id=prisoner.id)
    else:
        form = FingerprintCaptureForm()

    context = {
        'prisoner': prisoner,
        'form': form,
    }
    return render(request, 'prison/verify_identity.html', context)


@login_required
def fingerprint_device_list(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()

    if not is_super_admin_user:
        raise PermissionDenied("You do not have permission to manage devices.")

    devices = FingerprintDevice.objects.all().order_by('prison_station', 'name')

    if request.method == 'POST':
        form = FingerprintDeviceForm(request.POST)

        if form.is_valid():
            device = form.save()
            messages.success(request, f"Device '{device.name}' added successfully.")
            return redirect('fingerprint_device_list')
    else:
        form = FingerprintDeviceForm()

    context = {
        'devices': devices,
        'form': form,
    }
    return render(request, 'prison/fingerprint_device_list.html', context)


@login_required
def fingerprint_match_history(request, prisoner_id=None):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()

    if not (is_super_admin_user or is_prison_admin_user):
        raise PermissionDenied("You do not have permission to view fingerprint match history.")

    if prisoner_id:
        prisoner = get_object_or_404(Prisoner, id=prisoner_id)

        if not is_super_admin_user and (
                not prisoner.prison_station or prisoner.prison_station != request.user.prison_station):
            raise PermissionDenied("You do not have permission for this prisoner.")

        matches = FingerprintMatch.objects.filter(
            Q(searched_prisoner=prisoner) | Q(matched_prisoner=prisoner)
        ).select_related('searched_prisoner', 'matched_prisoner', 'searched_by')

        context = {
            'prisoner': prisoner,
            'matches': matches,
        }
    else:
        if not is_super_admin_user:
            raise PermissionDenied("You do not have permission to view all matches.")

        matches = FingerprintMatch.objects.all().select_related(
            'searched_prisoner', 'matched_prisoner', 'searched_by'
        )

        context = {
            'matches': matches,
        }

    return render(request, 'prison/fingerprint_match_history.html', context)


@login_required
def link_prisoner_identities(request, prisoner1_id, prisoner2_id):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()

    if not (is_super_admin_user or is_prison_admin_user):
        raise PermissionDenied("You do not have permission to link prisoner identities.")

    prisoner1 = get_object_or_404(Prisoner, id=prisoner1_id)
    prisoner2 = get_object_or_404(Prisoner, id=prisoner2_id)

    if not is_super_admin_user:
        if (prisoner1.prison_station != request.user.prison_station or
                prisoner2.prison_station != request.user.prison_station):
            raise PermissionDenied("You do not have permission for these prisoners.")

    if request.method == 'POST':
        form = FingerprintMatchConfirmForm(request.POST)

        if form.is_valid():
            confirmed = form.cleaned_data.get('confirmed')
            notes = form.cleaned_data.get('notes', '')
            link_identities = form.cleaned_data.get('link_identities', False)

            if confirmed:
                if link_identities:
                    success = BiometricService.link_identities(
                        prisoner1, prisoner2,
                        verified_by=request.user,
                        confidence=95.0
                    )

                    if success:
                        messages.success(request,
                                         f"Successfully linked identities: {prisoner1.full_name} ↔ {prisoner2.full_name}")

                        ActivityLog.objects.create(
                            user=request.user,
                            action='link_identity',
                            model='Prisoner',
                            object_id=prisoner1.id,
                            details=f'Linked identities: {prisoner1.prisoner_number} ↔ {prisoner2.prisoner_number}. Notes: {notes}'
                        )
                    else:
                        messages.error(request, "Failed to link identities.")
                else:
                    messages.info(request, "Identity linking was not performed.")

                return redirect('prisoner_detail', prisoner_id=prisoner1.id)
    else:
        form = FingerprintMatchConfirmForm()

    context = {
        'prisoner1': prisoner1,
        'prisoner2': prisoner2,
        'form': form,
    }
    return render(request, 'prison/link_identities.html', context)


@login_required
def fingerprint_dashboard(request):
    is_super_admin_user = hasattr(request.user, 'is_super_admin') and request.user.is_super_admin()
    is_prison_admin_user = hasattr(request.user, 'is_prison_admin') and request.user.is_prison_admin()
    is_reception_user = hasattr(request.user, 'is_reception') and request.user.is_reception()
    is_warden_user = hasattr(request.user, 'is_warden') and request.user.is_warden()

    if not (is_super_admin_user or is_prison_admin_user or is_reception_user or is_warden_user):
        raise PermissionDenied("You do not have permission to view the fingerprint dashboard.")

    prisoners = Prisoner.objects.filter(is_active=True)

    if not is_super_admin_user and hasattr(request.user, 'prison_station'):
        prisoners = prisoners.filter(prison_station=request.user.prison_station)

    stats = {
        'total_prisoners': prisoners.count(),
        'with_fingerprint': prisoners.filter(fingerprint_template__isnull=False).exclude(fingerprint_template='').count(),
        'identity_verified': prisoners.filter(is_identity_verified=True).count(),
        'pending_verification': prisoners.filter(
            fingerprint_template__isnull=False
        ).exclude(fingerprint_template='').filter(is_identity_verified=False).count(),
        'no_fingerprint': prisoners.filter(Q(fingerprint_template__isnull=True) | Q(fingerprint_template='')).count(),
    }

    recent_matches = FingerprintMatch.objects.all().select_related(
        'searched_prisoner', 'matched_prisoner', 'searched_by'
    ).order_by('-search_timestamp')[:20]

    if not is_super_admin_user and hasattr(request.user, 'prison_station'):
        station = request.user.prison_station
        recent_matches = recent_matches.filter(
            Q(searched_prisoner__prison_station=station) |
            Q(matched_prisoner__prison_station=station)
        )

    devices = FingerprintDevice.objects.filter(status='active')
    if not is_super_admin_user and hasattr(request.user, 'prison_station'):
        devices = devices.filter(prison_station=request.user.prison_station)

    context = {
        'stats': stats,
        'recent_matches': recent_matches,
        'devices': devices,
        'today': timezone.now().date(),
    }
    return render(request, 'prison/fingerprint_dashboard.html', context)