from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm
from .models import CustomUser, Region, PrisonStation


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    model = CustomUser
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'rank', 'region', 'prison_station', 'is_active')
    list_filter = ('is_active', 'role', 'rank', 'region', 'prison_station')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Assignment', {'fields': ('role', 'rank', 'region', 'prison_station', 'must_change_password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'rank',
                       'region', 'prison_station', 'password1', 'password2', 'is_staff', 'is_active')}
         ),
    )


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(PrisonStation)
class PrisonStationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location_address', 'region', 'capacity', 'date_established')
    list_filter = ('region',)
    search_fields = ('name', 'code', 'location_address')
