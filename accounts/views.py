from django.urls import path
from . import views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomPasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from .models import CustomUser
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json


def login_view(request):
    if request.user.is_authenticated:
        return redirect(reverse_lazy('dashboard'))

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)

                # Track login info
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0].strip()
                else:
                    ip_address = request.META.get('REMOTE_ADDR')

                user.last_login_ip = ip_address
                user.last_login_user_agent = request.META.get('HTTP_USER_AGENT', '')
                user.failed_login_attempts = 0
                user.save(update_fields=['last_login_ip', 'last_login_user_agent', 'failed_login_attempts'])

                # Log login activity
                try:
                    from prison.audit_service import AuditService
                    AuditService.log_action(
                        user=user,
                        action='LOGIN',
                        model_name='User',
                        object_id=user.id,
                        object_repr=user.username,
                        request=request,
                        severity='info',
                        description=f"User {user.username} logged in"
                    )
                except ImportError:
                    pass

                # ===== IMPORTANT: Redirect ICT Personnel FIRST =====
                if user.is_ict_personnel():
                    return redirect('ict_dashboard')

                # ===== Other role-based redirects =====
                if user.is_super_admin():
                    return redirect('dashboard')
                elif user.is_prison_admin():
                    return redirect('dashboard')
                elif user.is_reception():
                    return redirect('release_hub')
                elif user.is_officer_in_charge():
                    return redirect('release_hub')
                elif user.is_station_officer():
                    return redirect('release_hub')
                elif user.is_visitor_attendant():
                    return redirect('visitor_list')
                elif user.is_medical_officer():
                    return redirect('medical_record_list')
                elif user.is_warden():
                    return redirect('incident_report_list')
                elif user.is_rco() or user.is_rho() or user.is_regional_data_control():
                    return redirect('dashboard')
                else:
                    return redirect('dashboard')
        else:
            # Track failed login attempts
            username = request.POST.get('username')
            try:
                user = CustomUser.objects.get(username=username)
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.is_suspicious = True
                    user.suspicious_reason = f"Multiple failed login attempts ({user.failed_login_attempts})"
                user.save(update_fields=['failed_login_attempts', 'is_suspicious', 'suspicious_reason'])
            except CustomUser.DoesNotExist:
                pass
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    # Log logout activity
    try:
        from prison.audit_service import AuditService
        AuditService.log_action(
            user=request.user,
            action='LOGOUT',
            model_name='User',
            object_id=request.user.id,
            object_repr=request.user.username,
            request=request,
            severity='info',
            description=f"User {request.user.username} logged out"
        )
    except ImportError:
        pass

    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save()

            # Log password change
            try:
                from prison.audit_service import AuditService
                AuditService.log_action(
                    user=request.user,
                    action='UPDATE',
                    model_name='User',
                    object_id=request.user.id,
                    object_repr=request.user.username,
                    request=request,
                    severity='warning',
                    description=f"User {request.user.username} changed their password"
                )
            except ImportError:
                pass

            messages.success(request, 'Your password was successfully updated!')

            # Redirect ICT Personnel to ICT Dashboard
            if request.user.is_ict_personnel():
                return redirect('ict_dashboard')
            return redirect('dashboard')
    else:
        form = CustomPasswordChangeForm(request.user)

    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
def create_user(request):
    # Only super admins, prison admins, and ICT personnel can create users
    if not (request.user.is_super_admin() or request.user.is_prison_admin() or request.user.is_ict_personnel()):
        raise PermissionDenied("You don't have permission to access this page.")

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request=request)
        if form.is_valid():
            user = form.save(commit=False)
            user.must_change_password = True

            # Prison admins can't create super admins or other admins
            if request.user.is_prison_admin():
                if form.cleaned_data['role'] in ['superuser', 'admin']:
                    messages.error(request, "You don't have permission to create users with this role.")
                    return render(request, 'accounts/create_user.html', {'form': form})

            user.save()

            # Log user creation
            try:
                from prison.audit_service import AuditService
                AuditService.log_action(
                    user=request.user,
                    action='CREATE',
                    model_name='User',
                    object_id=user.id,
                    object_repr=user.username,
                    request=request,
                    severity='info',
                    description=f"Created user {user.username} with role {user.get_role_display()}"
                )
            except ImportError:
                pass

            messages.success(request, f'User {user.username} created successfully.')

            # Redirect ICT Personnel to ICT Dashboard
            if request.user.is_ict_personnel():
                return redirect('ict_dashboard')
            return redirect('user_list')
    else:
        form = CustomUserCreationForm(request=request)

    return render(request, 'accounts/create_user.html', {'form': form})


@login_required
def user_list(request):
    # Only super admins, prison admins, and ICT personnel can view user list
    if not (request.user.is_super_admin() or request.user.is_prison_admin() or request.user.is_ict_personnel()):
        raise PermissionDenied("You don't have permission to access this page.")

    # Super admins see all users, prison admins see non-admin users
    if request.user.is_super_admin() or request.user.is_ict_personnel():
        users = CustomUser.objects.all()
    else:
        users = CustomUser.objects.exclude(role__in=['superuser', 'admin'])

    return render(request, 'accounts/user_list.html', {'users': users})


@login_required
def toggle_user_status(request, user_id):
    # Only super admins and ICT personnel can toggle user status
    if not (request.user.is_super_admin() or request.user.is_ict_personnel()):
        raise PermissionDenied("You don't have permission to perform this action.")

    user = get_object_or_404(CustomUser, id=user_id)

    # Prevent deactivating yourself
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account!')
        return redirect('user_list')

    user.is_active = not user.is_active
    user.save()

    # Log user status change
    try:
        from prison.audit_service import AuditService
        AuditService.log_action(
            user=request.user,
            action='UPDATE',
            model_name='User',
            object_id=user.id,
            object_repr=user.username,
            request=request,
            severity='warning',
            description=f"{'Activated' if user.is_active else 'Deactivated'} user {user.username}"
        )
    except ImportError:
        pass

    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.username} has been {status}.')

    # Redirect ICT Personnel to ICT Dashboard
    if request.user.is_ict_personnel():
        return redirect('ict_dashboard')
    return redirect('user_list')


@login_required
@csrf_exempt
def mark_user_suspicious(request, user_id):
    """Mark a user as suspicious (ICT Personnel only)"""
    if not (hasattr(request.user, 'is_ict_personnel') and request.user.is_ict_personnel()):
        if not request.user.is_super_admin():
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

    try:
        user = get_object_or_404(CustomUser, id=user_id)
        data = json.loads(request.body) if request.body else {}
        reason = data.get('reason', '')

        user.is_suspicious = True
        user.suspicious_reason = reason
        user.save(update_fields=['is_suspicious', 'suspicious_reason'])

        return JsonResponse({
            'success': True,
            'message': f'User {user.username} marked as suspicious'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def clear_user_suspicious(request, user_id):
    """Clear suspicious flag from a user (ICT Personnel only)"""
    if not (hasattr(request.user, 'is_ict_personnel') and request.user.is_ict_personnel()):
        if not request.user.is_super_admin():
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

    try:
        user = get_object_or_404(CustomUser, id=user_id)
        data = json.loads(request.body) if request.body else {}
        notes = data.get('notes', '')

        user.is_suspicious = False
        user.suspicious_reason = ''
        user.failed_login_attempts = 0
        user.save(update_fields=['is_suspicious', 'suspicious_reason', 'failed_login_attempts'])

        return JsonResponse({
            'success': True,
            'message': f'User {user.username} cleared from suspicious status'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


class CustomPasswordChangeView(PasswordChangeView):
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy('dashboard')
    template_name = 'accounts/change_password.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save()
        messages.success(self.request, 'Your password was successfully updated!')
        return response