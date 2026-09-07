from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    VisitorListView, VisitorCreateView, VisitorUpdateView, VisitorApproveView, VisitorDetailView,
    VisitorItemCreateView,
    MedicalRecordListView, MedicalRecordCreateView, MedicalRecordUpdateView, MedicalRecordDetailView, MedicalRecordDeleteView,
    IncidentReportListView, IncidentReportCreateView, IncidentReportDetailView,
    ActivityLogListView,
    PrisonerItemListView, PrisonerItemDetailView, AddPrisonerItemView, WithdrawPrisonerMoneyView, CollectPrisonerItemView,
    extended_prisoner_search,
    RationItemListView, RationItemUpdateView, RationItemDeleteView,
    RationConsumptionCreateView, RationProcurementCreateView, capture_fingerprint,
    fingerprint_search_api,
    fingerprint_identify,
    verify_prisoner_identity,
    fingerprint_device_list,
    fingerprint_match_history,
    link_prisoner_identities,
    fingerprint_dashboard,
)


urlpatterns = [
    # Dashboard (now also serves as the ration dashboard)
    path('', views.dashboard, name='dashboard'),
    path('ration_dashboard/', views.dashboard, name='ration_dashboard'),

    # NEW: Lockup Summary Page
    path('lockup_summary/', views.lockup_summary_view, name='lockup_summary'),

    # Prisoner URLs
    path('prisoners/', views.prisoner_list, name='prisoner_list'),
    path('prisoners/add/', views.add_prisoner, name='add_prisoner'),
    path('prisoners/<int:prisoner_id>/', views.prisoner_detail, name='prisoner_detail'),
    path('prisoners/<int:prisoner_id>/edit/', views.edit_prisoner, name='edit_prisoner'),
    path('prisoners/<int:prisoner_id>/delete/', views.delete_prisoner, name='delete_prisoner'),
    path('prisoners/<int:prisoner_id>/convicted/', views.add_convicted_details, name='add_convicted_details'),
    path('prisoners/<int:prisoner_id>/remand/', views.add_remand_details, name='add_remand_details'),
    path('prisoners/<int:prisoner_id>/edit_convicted/', views.edit_convicted_details, name='edit_convicted_details'),
    path('prisoners/<int:prisoner_id>/edit_remand/', views.edit_remand_details, name='edit_remand_details'),
    path('prisoners/<int:prisoner_id>/transfer/', views.transfer_prisoner, name='transfer_prisoner'),
    path('prisoners/<int:prisoner_id>/sentence_reduction/', views.apply_sentence_reduction, name='apply_sentence_reduction'),
    path('prisoners/<int:prisoner_id>/report/', views.generate_prisoner_report, name='generate_prisoner_report'),
    path('prisoners/search/extended/', views.extended_prisoner_search, name='extended_prisoner_search'),

    # Visitor URLs
    path('visitors/', VisitorListView.as_view(), name='visitor_list'),
    path('visitors/add/', VisitorCreateView.as_view(), name='visitor_add'),
    path('visitors/<int:pk>/edit/', VisitorUpdateView.as_view(), name='visitor_edit'),
    path('visitors/<int:pk>/approve/', VisitorApproveView.as_view(), name='visitor_approve'),
    path('visitors/<int:pk>/', VisitorDetailView.as_view(), name='visitor_detail'),
    path('visitors/<int:visitor_id>/items/add/', VisitorItemCreateView.as_view(), name='visitor_item_add'),

    # Medical Record URLs
    path('medical/', MedicalRecordListView.as_view(), name='medical_record_list'),
    path('medical/add/', MedicalRecordCreateView.as_view(), name='medical_record_add'),
    path('medical/<int:pk>/edit/', MedicalRecordUpdateView.as_view(), name='medical_record_edit'),
    path('medical/<int:pk>/', MedicalRecordDetailView.as_view(), name='medical_record_detail'),
    path('medical/<int:pk>/delete/', MedicalRecordDeleteView.as_view(), name='medical_record_delete'),

    # Prisoner Item URLs (Money/Property Management)
    path('prisoners/<int:prisoner_id>/items/', PrisonerItemListView.as_view(), name='prisoner_item_list'),
    path('prisoners/<int:prisoner_id>/items/add/', AddPrisonerItemView.as_view(), name='add_prisoner_item'),
    path('prisoners/items/<int:pk>/', PrisonerItemDetailView.as_view(), name='prisoner_item_detail'),
    path('prisoners/items/<int:pk>/withdraw/', WithdrawPrisonerMoneyView.as_view(), name='withdraw_prisoner_money'),
    path('prisoners/items/<int:pk>/collect/', CollectPrisonerItemView.as_view(), name='collect_prisoner_item'),

    # Incident Report URLs
    path('incidents/', IncidentReportListView.as_view(), name='incident_report_list'),
    path('incidents/add/', IncidentReportCreateView.as_view(), name='incident_report_add'),
    path('incidents/<int:pk>/', IncidentReportDetailView.as_view(), name='incident_report_detail'),

    # Activity Log URLs (Superuser/Admin only)
    path('activity-log/', ActivityLogListView.as_view(), name='activity_log_list'),

    # Reports
    path('reports/upcoming-releases/', views.upcoming_releases_report, name='upcoming_releases_report'),

    # Release Hub URLs
    path('release-hub/', views.release_hub, name='release_hub'),
    path('release-hub/<int:prisoner_id>/forward/', views.forward_release_for_review, name='forward_release_for_review'),
    path('release-hub/reviews/<int:review_id>/approve/', views.approve_release_review, name='approve_release_review'),
    path('release-hub/reviews/<int:review_id>/reject/', views.reject_release_review, name='reject_release_review'),
    path('prisoners/<int:prisoner_id>/release-details/', views.prisoner_release_details_api, name='prisoner_release_details_api'),

    # Release Hub API endpoints
    path('release-hub/api/forward/', views.release_forward_api, name='release_forward_api'),
    path('release-hub/api/approve/', views.release_approve_api, name='release_approve_api'),
    path('release-hub/api/reject/', views.release_reject_api, name='release_reject_api'),

    # NEW: Ration Management URLs
    path('rations/', RationItemListView.as_view(), name='ration_item_list'),
    path('rations/<int:pk>/edit/', RationItemUpdateView.as_view(), name='edit_ration_item'),
    path('rations/<int:pk>/delete/', RationItemDeleteView.as_view(), name='delete_ration_item'),
    path('rations/consume/', RationConsumptionCreateView.as_view(), name='record_consumption'),
    path('rations/procure/', RationProcurementCreateView.as_view(), name='record_procurement'),

    # Authentication URLs
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),

    # Notification URLs
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/count/', views.notification_count, name='notification_count'),

    # NEW: Prison Station Management URLs
    path('stations/manage/', views.manage_prison_stations, name='manage_prison_stations'),
    path('stations/create/', views.create_prison_station, name='create_prison_station'),
    path('stations/<int:station_id>/edit/', views.edit_prison_station, name='edit_prison_station'),
    path('stations/<int:station_id>/delete/', views.delete_prison_station, name='delete_prison_station'),

    # NEW: ICT Security Dashboard URLs
    path('ict-dashboard/', views.ict_dashboard, name='ict_dashboard'),
    path('audit-trail/', views.audit_trail_list, name='audit_trail_list'),
    path('audit-trail/prisoner/<int:prisoner_id>/', views.prisoner_audit_view, name='prisoner_audit_view'),
    path('audit-trail/sentry-alerts/', views.sentry_alerts_view, name='sentry_alerts_view'),
    path('audit-trail/sentry-alerts/<int:alert_id>/resolve/', views.resolve_sentry_alert, name='resolve_sentry_alert'),
    path('audit-trail/export/', views.export_audit_trail, name='export_audit_trail'),

    # Fingerprint / Biometric URLs
    path('fingerprint/dashboard/', fingerprint_dashboard, name='fingerprint_dashboard'),
    path('prisoners/<int:prisoner_id>/fingerprint/capture/', capture_fingerprint, name='capture_fingerprint'),
    path('fingerprint/search/', fingerprint_identify, name='fingerprint_identify'),
    path('fingerprint/search/api/', fingerprint_search_api, name='fingerprint_search_api'),
    path('prisoners/<int:prisoner_id>/fingerprint/verify/', verify_prisoner_identity, name='verify_prisoner_identity'),
    path('fingerprint/devices/', fingerprint_device_list, name='fingerprint_device_list'),
    path('fingerprint/matches/', fingerprint_match_history, name='fingerprint_match_history'),
    path('fingerprint/matches/<int:prisoner_id>/', fingerprint_match_history, name='fingerprint_match_history_prisoner'),
    path('fingerprint/link/<int:prisoner1_id>/<int:prisoner2_id>/', link_prisoner_identities, name='link_prisoner_identities'),
]