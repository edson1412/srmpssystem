# hrms/urls.py

from django.urls import path
from . import views

app_name = 'hrms'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard_home'),
    path('dashboard/', views.dashboard_view, name='dashboard'), # Main HRMS dashboard
    path('dashboard/data/', views.dashboard_data_api_view, name='dashboard_data_api'),

    # Officer Management
    path('officers/', views.officer_list_view, name='officer_list'),
    path('officers/add/', views.officer_create_view, name='officer_create'),
    path('officers/<str:service_number>/', views.officer_detail_view, name='officer_detail'),
    path('officers/<str:service_number>/edit/', views.officer_update_view, name='officer_update'),
    path('officers/<str:service_number>/delete/', views.officer_delete_view, name='officer_delete'),

    # Service History (Promotions & Transfers)
    path('officers/<str:service_number>/add-history/', views.service_history_create_view, name='service_history_create'),
    path('service-history/', views.service_history_list_view, name='service_history_list'), # Service History List
    path('service-history/<int:pk>/edit/', views.service_history_update_view, name='service_history_update'),
    path('service-history/<int:pk>/delete/', views.service_history_delete_view, name='service_history_delete'),
    path('service-history-report/', views.service_history_report_view, name='service_history_report'),

    # Leave Requests
    path('officers/<str:service_number>/request-leave/', views.leave_request_create_view, name='leave_request_create'),
    path('leave-requests/', views.leave_request_list_view, name='leave_request_list'),
    path('leave-requests/<int:pk>/detail/', views.leave_request_detail_view, name='leave_request_detail'),
    path('leave-requests/<int:pk>/approve/', views.leave_request_approve_view, name='leave_request_approve'),
    path('leave-requests/<int:pk>/reject/', views.leave_request_reject_view, name='leave_request_reject'),
    path('leave-report/', views.leave_report_view, name='leave_report'),

    # Officer Files
    path('officers/<str:service_number>/upload-file/', views.officer_file_upload_view, name='officer_file_upload'),
    path('officer-files/', views.officer_file_list_view, name='officer_file_list'),
    path('officer-files/<int:pk>/detail/', views.officer_file_detail_view, name='officer_file_detail'),
    path('officer-files/<int:pk>/respond/', views.officer_file_respond_view, name='officer_file_respond'),

    # Performance
    path('officers/<str:service_number>/add-performance/', views.performance_record_create_view, name='performance_record_create'),
    path('performance-records/', views.performance_record_list_view, name='performance_record_list'),
    path('performance-report/', views.performance_report_view, name='performance_report'),

    # Office Assignments
    path('officers/<str:service_number>/assign-office/', views.office_assignment_create_view, name='office_assignment_create'),
    path('office-assignments/<int:pk>/edit/', views.office_assignment_update_view, name='office_assignment_update'),

    # Region Management
    path('regions/', views.region_list_view, name='region_list'),
    path('regions/add/', views.region_create_view, name='region_create'),
    path('regions/<int:pk>/edit/', views.region_update_view, name='region_update'),
    path('regions/<int:pk>/delete/', views.region_delete_view, name='region_delete'),

    # Prison Station Management
    path('prison-stations/', views.prison_station_list_view, name='prison_station_list'),
    path('prison-stations/add/', views.prison_station_create_view, name='prison_station_create'),
    path('prison-stations/<int:pk>/edit/', views.prison_station_update_view, name='prison_station_update'),
    path('prison-stations/<int:pk>/delete/', views.prison_station_delete_view, name='prison_station_delete'),

    # Attendance Management
    path('officers/<str:service_number>/add-attendance/', views.attendance_record_create_view, name='attendance_record_create'),
    path('attendance-records/', views.attendance_record_list_view, name='attendance_record_list'),
    path('attendance-records/<int:pk>/edit/', views.attendance_record_update_view, name='attendance_record_update'),
    path('attendance-records/<int:pk>/delete/', views.attendance_record_delete_view, name='attendance_record_delete'),
    path('attendance-report/', views.attendance_report_view, name='attendance_report'),
    path('attendance-report/export/pdf/', views.attendance_report_pdf_export_view, name='attendance_report_pdf_export'),
    path('attendance/export/officer/<str:service_number>/', views.export_officer_attendance_view, name='export_officer_attendance'),

    # Disciplinary Cases Management
    path('officers/<str:service_number>/add-disciplinary-case/', views.disciplinary_case_create_view, name='disciplinary_case_create'),
    path('disciplinary-cases/', views.disciplinary_case_list_view, name='disciplinary_case_list'),
    path('disciplinary-cases/<int:pk>/edit/', views.disciplinary_case_update_view, name='disciplinary_case_update'),
    path('disciplinary-cases/<int:pk>/delete/', views.disciplinary_case_delete_view, name='disciplinary_case_delete'),
    path('disciplinary-report/', views.disciplinary_report_view, name='disciplinary_report'),

    # Demographics Report
    path('demographics-report/', views.demographics_report_view, name='demographics_report'),

    # Reports List
    path('reports/', views.report_list_view, name='report_list'),

    # Initial Data Setup (for superuser)
    path('setup-data/', views.setup_initial_data, name='setup_initial_data'),

    # Annual Leave Management
    path('annual-leave-reset/', views.annual_leave_reset_view, name='annual_leave_reset'),

    # Notification Management URLs
    path('notifications/', views.notification_list_view, name='notification_list'),
    path('notifications/<int:pk>/', views.notification_detail_view, name='notification_detail'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    # NEW: Real-time Notification Count URL (AJAX endpoint)
    path('notifications/unread-count/', views.get_unread_notification_count_view, name='unread_notification_count'),

    # Attendance Management
    path('attendance/', views.daily_attendance_view, name='daily_attendance'),
    path('attendance/save/', views.save_daily_attendance_view, name='save_daily_attendance'),
    path('attendance/<str:date_str>/', views.get_attendance_for_date_view, name='get_attendance_for_date'),
    path('attendance/export/<str:date_str>/', views.export_attendance_view, name='export_attendance'),
    
    # Office Assignments
    path('office-assignments/', views.office_assignment_list_view, name='office_assignment_list'),

    # Training Wing URLs
    path('training/', views.training_dashboard, name='training_dashboard'),
    path('training/intakes/', views.intake_list, name='intake_list'),
    path('training/intakes/create/', views.intake_create, name='intake_create'),
    path('training/intakes/<int:pk>/', views.intake_detail, name='intake_detail'),
    path('training/intakes/<int:pk>/graduation/', views.intake_graduation_view, name='intake_graduation'),
    path('training/intakes/<int:pk>/ranking/', views.class_ranking_view, name='class_ranking'),
    path('training/intakes/<int:pk>/export-graduation/', views.export_graduation_list_view, name='export_graduation_list'),
    
    # Courses Management
    path('training/courses/', views.course_list, name='course_list'),
    path('training/courses/create/', views.course_create, name='course_create'),
    path('training/courses/<int:pk>/', views.course_detail, name='course_detail'),
    path('training/courses/<int:pk>/edit/', views.course_update, name='course_update'),
    
    # Recruits Management
    path('training/recruits/', views.recruit_list, name='recruit_list'),
    path('training/recruits/<int:pk>/', views.recruit_detail, name='recruit_detail'),
    path('training/recruits/<int:pk>/edit/', views.recruit_update, name='recruit_update'),
    path('training/intakes/<int:intake_pk>/recruits/create/', views.recruit_create, name='recruit_create'),
    
    # Marks Management
    path('training/recruits/<int:recruit_pk>/marks/add/', views.add_mark, name='add_mark'),
    path('training/marks/<int:pk>/edit/', views.edit_mark, name='edit_mark'),
    
    # Bulk Operations - Grouped under /training/bulk/
    path('training/bulk/marks/import/csv/', 
         views.bulk_marks_import_csv_view, 
         name='bulk_marks_import_csv'),
    path('training/bulk/marks/import/excel/', 
         views.bulk_marks_import_excel_view, 
         name='bulk_marks_import_excel'),
    path('training/bulk/marks/add/', views.bulk_add_marks_view, name='bulk_add_marks'),
    path('training/bulk/marks/add/<int:module_pk>/', views.bulk_add_marks_view, name='bulk_add_marks_module'),
    path('training/bulk/templates/download/', 
         views.download_csv_template_view, 
         name='download_csv_template'),
    path('training/bulk/import-failures/download/', 
         views.download_import_failures_view, 
         name='download_import_failures'),
    path('training/bulk/import/status/', 
         views.marks_import_status_view, 
         name='marks_import_status'),

    # System Error Page
    path('system-error/', views.system_error_view, name='system_error'),
    path('system-error/<str:error_code>/', views.system_error_view, name='system_error_with_code'),

    # ICT Personnel Dashboard and User Management
    path('ict/dashboard/', views.ict_dashboard_view, name='ict_dashboard'),
    path('ict/users/', views.ict_user_list_view, name='ict_user_list'),
    path('ict/users/create/', views.ict_user_create_view, name='ict_user_create'),
    path('ict/users/<int:user_id>/', views.ict_user_detail_view, name='ict_user_detail'),
    path('ict/users/<int:user_id>/edit/', views.ict_user_update_view, name='ict_user_update'),
    path('ict/users/<int:user_id>/delete/', views.ict_user_delete_view, name='ict_user_delete'),
    path('ict/system-logs/', views.ict_system_logs_view, name='ict_system_logs'),
]
