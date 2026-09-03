from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import CustomUser
from prison.models import PrisonStation

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'rank', 'prison_station')
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Only superusers can create other superusers or admins
        if not (self.request and self.request.user.is_super_admin()):
            self.fields['role'].choices = [
                (role, label) 
                for role, label in self.Meta.model.ROLE_CHOICES 
                if role not in ['superuser', 'admin']
            ]
        
        self.fields['prison_station'].queryset = PrisonStation.objects.all()

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})