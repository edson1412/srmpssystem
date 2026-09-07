from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import PasswordChangeView

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.CustomPasswordChangeView.as_view(), name='change_password'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),

    # ICT Security endpoints
    path('users/<int:user_id>/mark-suspicious/', views.mark_user_suspicious, name='mark_user_suspicious'),
    path('users/<int:user_id>/clear-suspicious/', views.clear_user_suspicious, name='clear_user_suspicious'),
]