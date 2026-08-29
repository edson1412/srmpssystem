"""
URL configuration for audit trail views.
"""
from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    # Audit log views
    path('logs/', views.audit_log_list, name='audit_log_list'),
    path('logs/<int:pk>/', views.audit_log_detail, name='audit_log_detail'),
    path('logs/user/<int:user_id>/', views.audit_log_by_user, name='audit_log_by_user'),
    path('logs/export/', views.audit_log_export, name='audit_log_export'),
    
    # Summary dashboard
    path('summary/', views.audit_summary, name='audit_summary'),
]
