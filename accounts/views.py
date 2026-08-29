from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy

from .forms import CustomUserCreationForm, CustomPasswordChangeForm, UserProfileForm
from .models import CustomUser
from .routing import landing_url_for


MAX_FAILED_LOGIN_ATTEMPTS = 3


def login_view(request):
    """Single sign-in page for both the officers (HRMS) and inmates modules."""
    if request.user.is_authenticated:
        return redirect(landing_url_for(request.user))

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data.get('username'),
                password=form.cleaned_data.get('password'),
            )
            if user is not None:
                if user.is_locked or user.require_password_reset:
                    form.add_error(None, 'Your account is locked. Contact ICT to reset your password.')
                    return render(request, 'accounts/login.html', {'form': form})

                if user.failed_login_attempts:
                    user.failed_login_attempts = 0
                    user.save(update_fields=['failed_login_attempts'])
                login(request, user)
                if user.must_change_password:
                    messages.info(request, 'Please change your password before continuing.')
                    return redirect('change_password')
                return redirect(landing_url_for(user))
        else:
            _register_failed_login(request.POST.get('username', ''))
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


def _register_failed_login(username):
    """Counts a failed attempt and locks the account once the threshold is hit."""
    user = CustomUser.objects.filter(username=username).first()
    if user is None:
        return
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.is_locked = True
        user.require_password_reset = True
    user.save(update_fields=['failed_login_attempts', 'is_locked', 'require_password_reset'])


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def dashboard_choice_view(request):
    """Display dashboard choice for users with dual access."""
    if not request.user.has_dual_dashboards():
        # User doesn't have dual access, redirect to their primary dashboard
        return redirect(landing_url_for(request.user))
    
    dashboards = request.user.get_all_dashboard_urls()
    return render(request, 'accounts/dashboard_choice.html', {
        'dashboards': dashboards,
        'title': 'Select Dashboard',
    })



@login_required
def user_profile_view(request):
    """Displays the current user's profile information."""
    return render(request, 'accounts/user_profile.html', {
        'user': request.user,
        'title': 'User Profile',
    })


@login_required
def edit_profile_view(request):
    """Lets a user update their own names, email and profile picture."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('user_profile')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'accounts/edit_profile.html', {
        'form': form,
        'title': 'Edit Profile',
    })


@login_required
def create_user(request):
    # Only super admins and prison admins can create users
    if not (request.user.is_super_admin() or request.user.is_prison_admin()):
        raise PermissionDenied("You don't have permission to access this page.")

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request=request)
        if form.is_valid():
            user = form.save(commit=False)
            user.must_change_password = True

            # Prison admins can't create super admins or other admins
            if request.user.is_prison_admin():
                if form.cleaned_data['role'] in [CustomUser.ROLE_SUPERUSER, CustomUser.ROLE_ADMIN]:
                    messages.error(request, "You don't have permission to create users with this role.")
                    return render(request, 'accounts/create_user.html', {'form': form})

            user.save()
            messages.success(request, f'User {user.username} created successfully.')
            return redirect(landing_url_for(request.user))
    else:
        form = CustomUserCreationForm(request=request)

    return render(request, 'accounts/create_user.html', {'form': form})


@login_required
def user_list(request):
    # Only super admins and prison admins can view user list
    if not (request.user.is_super_admin() or request.user.is_prison_admin()):
        raise PermissionDenied("You don't have permission to access this page.")

    # Super admins see all users, prison admins see non-admin users
    if request.user.is_super_admin():
        users = CustomUser.objects.all()
    else:
        users = CustomUser.objects.exclude(role__in=[CustomUser.ROLE_SUPERUSER, CustomUser.ROLE_ADMIN])

    return render(request, 'accounts/user_list.html', {'users': users, 'user': request.user})


@login_required
def toggle_user_status(request, user_id):
    # Only super admins can toggle user status
    if not request.user.is_super_admin():
        raise PermissionDenied("You don't have permission to perform this action.")

    user = CustomUser.objects.get(id=user_id)

    # Prevent deactivating yourself
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account!')
        return redirect(landing_url_for(request.user))

    user.is_active = not user.is_active
    user.save()

    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.username} has been {status}.')
    return redirect(landing_url_for(request.user))


class CustomPasswordChangeView(PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'accounts/change_password.html'

    def get_success_url(self):
        return landing_url_for(self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save(update_fields=['must_change_password'])
        messages.success(self.request, 'Your password was successfully updated!')
        return response
