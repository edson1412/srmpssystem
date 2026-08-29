from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Region(models.Model):
    """
    Represents a geographical region where prison stations are located.
    Shared by both HRMS and Prison modules.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Region Name"))
    code = models.SlugField(max_length=20, unique=True, verbose_name=_("Region Code"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Region")
        verbose_name_plural = _("Regions")
        ordering = ['name']

    def __str__(self):
        return self.name


class PrisonStation(models.Model):
    """
    Represents an individual prison station within a region.
    Shared by both HRMS and Prison modules.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Station Name"))
    code = models.CharField(max_length=10, unique=True, verbose_name=_("Station Code"))
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='stations', verbose_name=_("Region"))
    location_address = models.CharField(max_length=255, blank=True, verbose_name=_("Location Address"))
    contact_number = models.CharField(max_length=20, blank=True, verbose_name=_("Contact Number"))
    capacity = models.PositiveIntegerField(default=100, verbose_name=_("Capacity"))
    date_established = models.DateField(verbose_name=_("Date Established"))

    class Meta:
        verbose_name = _("Prison Station")
        verbose_name_plural = _("Prison Stations")
        ordering = ['region__name', 'name']

    def __str__(self):
        return f"{self.name} ({self.region.name})"


class CustomUser(AbstractUser):
    """
    Unified Custom User model for both HRMS (Officer Management) and Prison (Inmate Management) modules.
    Extends Django's AbstractUser to include specific roles, region, and prison station assignments.
    """

    # HRMS/Officer Management Roles
    ROLE_NATIONAL_COMMISSIONER = 'national_commissioner'
    ROLE_NATIONAL_HR = 'national_hr'
    ROLE_REGIONAL_COMMANDING_OFFICER = 'regional_commanding_officer'
    ROLE_REGIONAL_HEADQUARTERS_OFFICER = 'regional_headquarters_officer'
    ROLE_REGIONAL_HR = 'regional_hr'
    ROLE_STATION_HR = 'station_hr'
    ROLE_TRAINING_WING_OFFICER = 'training_wing_officer'
    ROLE_COMMISSIONER_TRAINING_SCHOOL = 'commissioner_training_school'
    ROLE_ICT_PERSONNEL = 'ict_personnel'

    # Prison/Inmate Management Roles
    ROLE_SUPERUSER = 'superuser'
    ROLE_ADMIN = 'admin'
    ROLE_RECEPTION = 'reception'
    ROLE_OFFICER_IN_CHARGE = 'officer_in_charge'
    ROLE_STATION_OFFICER = 'station_officer'
    ROLE_VISITOR_ATTENDANT = 'visitor_attendant'
    ROLE_MEDICAL = 'medical'

    ROLE_CHOICES = (
        # HRMS Roles
        (ROLE_NATIONAL_COMMISSIONER, _('Commissioner of Administration/HR (National)')),
        (ROLE_NATIONAL_HR, _('National HR Officer')),
        (ROLE_REGIONAL_COMMANDING_OFFICER, _('Region Commanding Officer (RCO)')),
        (ROLE_REGIONAL_HEADQUARTERS_OFFICER, _('Region Headquarters Officer (RHO)')),
        (ROLE_REGIONAL_HR, _('Regional HR Officer')),
        (ROLE_STATION_HR, _('Station HR Officer')),
        (ROLE_TRAINING_WING_OFFICER, _('Training Wing Officer')),
        (ROLE_COMMISSIONER_TRAINING_SCHOOL, _('Commissioner of Training School')),
        (ROLE_ICT_PERSONNEL, _('ICT Personnel')),
        # Prison Roles
        (ROLE_SUPERUSER, _('Super Administrator')),
        (ROLE_ADMIN, _('Prison Administrator')),
        (ROLE_RECEPTION, _('Reception Officer')),
        (ROLE_OFFICER_IN_CHARGE, _('Officer in Charge')),
        (ROLE_STATION_OFFICER, _('Station Officer')),
        (ROLE_VISITOR_ATTENDANT, _('Visitor Attendant')),
        (ROLE_MEDICAL, _('Medical Officer')),
    )

    # Roles that work primarily in HRMS module
    HRMS_ROLES = [
        ROLE_NATIONAL_COMMISSIONER,
        ROLE_NATIONAL_HR,
        ROLE_REGIONAL_COMMANDING_OFFICER,
        ROLE_REGIONAL_HEADQUARTERS_OFFICER,
        ROLE_REGIONAL_HR,
        ROLE_STATION_HR,
        ROLE_TRAINING_WING_OFFICER,
        ROLE_COMMISSIONER_TRAINING_SCHOOL,
        ROLE_ICT_PERSONNEL,
    ]

    # Roles that work primarily in Prison module
    PRISON_ROLES = [
        ROLE_SUPERUSER,
        ROLE_ADMIN,
        ROLE_RECEPTION,
        ROLE_STATION_OFFICER,
        ROLE_VISITOR_ATTENDANT,
        ROLE_MEDICAL,
    ]

    # Roles that can access both modules (dual access)
    DUAL_ACCESS_ROLES = [
        ROLE_OFFICER_IN_CHARGE,
        ROLE_REGIONAL_COMMANDING_OFFICER,
        ROLE_REGIONAL_HEADQUARTERS_OFFICER,
    ]

    # Training-specific roles
    TRAINING_ROLES = [
        ROLE_TRAINING_WING_OFFICER,
        ROLE_COMMISSIONER_TRAINING_SCHOOL,
    ]

    RANK_CHOICES = [
        ('warder', _('Warder')),
        ('sergeant', _('Sergeant')),
        ('gaoler', _('Gaoler')),
        ('inspector', _('Inspector')),
        ('superintendent', _('Superintendent')),
        ('assistant_superintendent', _('Assistant Superintendent')),
        ('senior_superintendent', _('Senior Superintendent')),
        ('assistant_commissioner', _('Assistant Commissioner')),
        ('deputy_commissioner', _('Deputy Commissioner')),
        ('commissioner', _('Commissioner')),
        ('commissioner_general', _('Commissioner General')),
    ]

    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default=ROLE_RECEPTION,
        verbose_name=_("User Role")
    )
    rank = models.CharField(
        max_length=50,
        choices=RANK_CHOICES,
        blank=True,
        verbose_name=_("Rank")
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_("Assigned Region"),
        help_text=_("Region scope, required for regional level roles.")
    )
    prison_station = models.ForeignKey(
        PrisonStation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_("Assigned Prison Station")
    )
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True,
        default='images/default_profile.jpg',
        verbose_name=_("Profile Picture")
    )
    must_change_password = models.BooleanField(default=True, verbose_name=_("Must Change Password"))

    # Security: track failed login attempts and lock status
    failed_login_attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Failed Login Attempts"),
        help_text=_("Number of consecutive failed login attempts.")
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_("Locked"),
        help_text=_("When set, the account is locked and cannot be used to login until ICT resets it.")
    )
    require_password_reset = models.BooleanField(
        default=False,
        verbose_name=_("Require Password Reset"),
        help_text=_("When set, the user must have their password reset by ICT personnel before logging in.")
    )

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ['username']

    def __str__(self):
        station_name = self.prison_station.name if self.prison_station else 'No station'
        return f"{self.get_full_name() or self.username} ({station_name})"

    # ================= HRMS Role Helper Methods =================
    @property
    def is_national_level(self):
        return self.is_superuser or self.role in [
            self.ROLE_NATIONAL_COMMISSIONER,
            self.ROLE_NATIONAL_HR,
        ]

    @property
    def is_regional_level(self):
        return self.role in [
            self.ROLE_REGIONAL_COMMANDING_OFFICER,
            self.ROLE_REGIONAL_HEADQUARTERS_OFFICER,
            self.ROLE_REGIONAL_HR,
        ]

    @property
    def is_station_level(self):
        return self.role in [
            self.ROLE_OFFICER_IN_CHARGE,
            self.ROLE_STATION_OFFICER,
            self.ROLE_STATION_HR,
            self.ROLE_RECEPTION,
            self.ROLE_VISITOR_ATTENDANT,
            self.ROLE_MEDICAL,
        ]

    @property
    def is_commissioner(self):
        return self.role == self.ROLE_NATIONAL_COMMISSIONER

    @property
    def is_national_hr(self):
        return self.role == self.ROLE_NATIONAL_HR

    @property
    def is_rco(self):
        return self.role == self.ROLE_REGIONAL_COMMANDING_OFFICER

    @property
    def is_rho(self):
        return self.role == self.ROLE_REGIONAL_HEADQUARTERS_OFFICER

    @property
    def is_regional_hr(self):
        return self.role == self.ROLE_REGIONAL_HR

    @property
    def is_oc(self):
        return self.role == self.ROLE_OFFICER_IN_CHARGE

    @property
    def is_so(self):
        return self.role == self.ROLE_STATION_OFFICER

    @property
    def is_station_hr(self):
        return self.role == self.ROLE_STATION_HR

    @property
    def is_training_wing_officer(self):
        return self.role == self.ROLE_TRAINING_WING_OFFICER

    @property
    def is_commissioner_training_school(self):
        return self.role == self.ROLE_COMMISSIONER_TRAINING_SCHOOL

    @property
    def is_ict_personnel(self):
        return self.role == self.ROLE_ICT_PERSONNEL

    @property
    def can_access_training(self):
        return (
            self.is_superuser
            or self.is_national_level
            or self.role in self.TRAINING_ROLES
        )

    # ================= Prison Role Helper Methods =================
    def is_super_admin(self):
        return self.role == self.ROLE_SUPERUSER or self.is_superuser

    def is_prison_admin(self):
        return self.role == self.ROLE_ADMIN

    def is_reception(self):
        return self.role == self.ROLE_RECEPTION

    def is_officer_in_charge(self):
        return self.role == self.ROLE_OFFICER_IN_CHARGE

    def is_station_officer(self):
        return self.role == self.ROLE_STATION_OFFICER

    def is_visitor_attendant(self):
        return self.role == self.ROLE_VISITOR_ATTENDANT

    def is_medical_officer(self):
        return self.role == self.ROLE_MEDICAL

    def has_region_permission(self):
        """Check if user has region-level permission"""
        return self.region is not None and (
            self.is_super_admin() or self.is_prison_admin() or self.is_regional_level
        )

    def has_station_permission(self):
        """Check if user has station-level permission"""
        return self.prison_station is not None

    # ================= Module Access Methods =================
    @property
    def can_access_hrms(self):
        return self.is_superuser or self.role in self.HRMS_ROLES + self.DUAL_ACCESS_ROLES

    @property
    def can_access_prison(self):
        return self.is_superuser or self.role in self.PRISON_ROLES + self.DUAL_ACCESS_ROLES

    @property
    def is_hrms_user(self):
        """Check if user is primarily an HRMS user"""
        return self.role in self.HRMS_ROLES and self.role not in self.DUAL_ACCESS_ROLES

    @property
    def is_prison_user(self):
        """Check if user is primarily a prison/inmate management user"""
        return self.role in self.PRISON_ROLES and self.role not in self.DUAL_ACCESS_ROLES

    @property
    def is_dual_access_user(self):
        """Check if user has access to both modules"""
        return self.role in self.DUAL_ACCESS_ROLES

    @property
    def primary_module(self):
        """Determine the primary module for this user"""
        if self.is_dual_access_user:
            # For dual access users, prioritize HRMS as it's typically their primary function
            return 'hrms'
        elif self.is_hrms_user:
            return 'hrms'
        elif self.is_prison_user:
            return 'prison'
        else:
            return 'prison'  # Default fallback

    def get_landing_url_name(self):
        """Get the appropriate landing URL name based on user role"""
        from .routing import landing_url_name_for
        return landing_url_name_for(self)

    def get_all_dashboard_urls(self):
        """Get all accessible dashboard URLs for this user"""
        dashboards = []
        
        # Primary dashboard
        primary_url = self.get_landing_url_name()
        dashboards.append({
            'name': 'Primary Dashboard',
            'url_name': primary_url,
            'module': self.primary_module,
        })
        
        # Secondary dashboard for dual-access users
        if self.is_dual_access_user:
            if self.primary_module == 'hrms':
                dashboards.append({
                    'name': 'Prison Dashboard',
                    'url_name': 'dashboard',
                    'module': 'prison',
                })
            else:
                dashboards.append({
                    'name': 'HRMS Dashboard',
                    'url_name': 'hrms:dashboard',
                    'module': 'hrms',
                })
        
        return dashboards

    def has_dual_dashboards(self):
        """Check if user has access to multiple dashboards"""
        return len(self.get_all_dashboard_urls()) > 1