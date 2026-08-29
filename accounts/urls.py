from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from . import views

# No app_name: url names are global so both the prison and hrms templates can
# reverse them ('login', 'logout', ...) without a namespace prefix.
urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard-choice/', views.dashboard_choice_view, name='dashboard_choice'),
    path('profile/', views.user_profile_view, name='user_profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('change-password/', views.CustomPasswordChangeView.as_view(), name='change_password'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),

    # Password reset flow
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset_form.html',
             email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt',
             success_url=reverse_lazy('password_reset_done')
         ),
         name='password_reset'),
    path('password-reset-done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url=reverse_lazy('password_reset_complete')
         ),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]
