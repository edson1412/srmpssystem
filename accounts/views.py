from django.urls import path
from . import views
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomPasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from .models import CustomUser
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied

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

                # Redirect based on user role
                if user.is_super_admin():
                    return redirect(reverse_lazy('dashboard'))
                elif user.is_prison_admin():
                    return redirect(reverse_lazy('dashboard'))
                elif user.is_reception():
                    return redirect(reverse_lazy('release_hub'))
                elif user.is_officer_in_charge():
                    return redirect(reverse_lazy('release_hub'))
                elif user.is_station_officer():
                    return redirect(reverse_lazy('release_hub'))
                elif user.is_visitor_attendant():
                    return redirect(reverse_lazy('visitor_list'))
                elif user.is_medical_officer():
                    return redirect(reverse_lazy('medical_record_list'))
                elif user.is_warden():
                    return redirect(reverse_lazy('incident_report_list'))
                else:
                    return redirect(reverse_lazy('dashboard'))
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged in successfully.')
    return redirect('login')

@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save()
            messages.success(request, 'Your password was successfully updated!')
            return redirect('dashboard')
    else:
        form = CustomPasswordChangeForm(request.user)

    return render(request, 'accounts/change_password.html', {'form': form})

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
                if form.cleaned_data['role'] in ['superuser', 'admin']:
                    messages.error(request, "You don't have permission to create users with this role.")
                    return render(request, 'accounts/create_user.html', {'form': form})

            user.save()
            messages.success(request, f'User {user.username} created successfully.')
            return redirect('user_list')
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
        users = CustomUser.objects.exclude(role__in=['superuser', 'admin'])

    return render(request, 'accounts/user_list.html', {'users': users})

@login_required
def toggle_user_status(request, user_id):
    # Only super admins can toggle user status
    if not request.user.is_super_admin():
        raise PermissionDenied("You don't have permission to perform this action.")

    user = CustomUser.objects.get(id=user_id)

    # Prevent deactivating yourself
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account!')
        return redirect('user_list')

    user.is_active = not user.is_active
    user.save()

    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.username} has been {status}.')
    return redirect('user_list')

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

urlpatterns = [
    # ... other url patterns ...
    path('change-password/', views.CustomPasswordChangeView.as_view(), name='change_password'),
]