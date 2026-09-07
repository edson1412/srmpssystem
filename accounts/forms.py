from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import CustomUser
from prison.models import PrisonStation

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'rank', 'prison_station')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'rank': forms.Select(attrs={'class': 'form-select'}),
            'prison_station': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Style password inputs
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

        # Only superusers can create other superusers or admins
        if not (self.request and self.request.user.is_super_admin()):
            self.fields['role'].choices = [
                (role, label)
                for role, label in self.Meta.model.ROLE_CHOICES
                if role not in ['superuser', 'admin']
            ]

        # Filter prison stations based on user permissions
        if self.request and not self.request.user.is_super_admin():
            if hasattr(self.request.user, 'prison_station') and self.request.user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(
                    id=self.request.user.prison_station.id
                )
                self.fields['prison_station'].initial = self.request.user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = True
                self.fields['prison_station'].widget.attrs['disabled'] = True

        # Make rank optional for some roles
        if self.data and self.data.get('role') in ['ict_personnel']:
            self.fields['rank'].required = False

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})