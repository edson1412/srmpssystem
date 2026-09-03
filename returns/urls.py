from django.urls import path
from . import views

app_name = 'returns'

urlpatterns = [
    # Dashboard
    path('', views.returns_dashboard, name='dashboard'),

    # Template Management
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/download/<str:category>/', views.download_template, name='download_template'),
    path('templates/download/<str:category>/xlsx/', views.download_template_xlsx, name='download_template_xlsx'),

    # Submissions
    path('submissions/', views.submission_list, name='submission_list'),
    path('submissions/create/', views.submission_create, name='submission_create'),
    path('submissions/<int:pk>/', views.submission_detail, name='submission_detail'),
    path('submissions/<int:pk>/approve/', views.submission_approve, name='submission_approve'),
    path('submissions/<int:pk>/reject/', views.submission_reject, name='submission_reject'),
    path('submissions/<int:pk>/download/', views.submission_download, name='submission_download'),
    path('submissions/<int:pk>/export-pdf/', views.export_submission_pdf, name='export_submission_pdf'),

    # Export PDFs
    path('export/', views.export_options, name='export_options'),
    path('export/station/<int:station_id>/<int:template_id>/', views.export_station_returns_pdf, name='export_station_returns_pdf'),
    path('export/region/<str:region>/<int:template_id>/', views.export_regional_returns_pdf, name='export_regional_returns_pdf'),
    path('export/all/<int:template_id>/', views.export_all_returns_pdf, name='export_all_returns_pdf'),

    # Station Status
    path('station-status/', views.station_status, name='station_status'),
    path('station-status/initialize/', views.initialize_monthly_tracking, name='initialize_monthly_tracking'),

    # Regional Summary
    path('regional-summary/', views.regional_summary, name='regional_summary'),
    path('regional-summary/export/', views.regional_summary_export, name='regional_summary_export'),

    # Monthly Status Report
    path('monthly-status/', views.monthly_status_report, name='monthly_status_report'),

    # API Endpoints
    path('api/summary/', views.api_returns_summary, name='api_returns_summary'),
    path('api/monthly-status/', views.api_monthly_status, name='api_monthly_status'),
]