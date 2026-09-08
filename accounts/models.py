from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('superuser', 'Super Administrator'),
        ('admin', 'Prison Administrator'),
        ('reception', 'Reception Officer'),
        ('officer_in_charge', 'Officer in Charge'),
        ('station_officer', 'Station Officer'),
        ('visitor_attendant', 'Visitor Attendant'),
        ('medical', 'Medical Officer'),
        ('warden', 'Warden'),
        ('ict_personnel', 'ICT Personnel'),
        ('rco', 'Regional Commanding Officer'),
        ('rho', 'Regional Headquarters Officer'),
        ('regional_data_control', 'Regional Data Control Officer'),
    ]

    RANK_CHOICES = [
        ('warder', 'Warder'),
        ('sergeant', 'Sergeant'),
        ('gaoler', 'Gaoler'),
        ('inspector', 'Inspector'),
        ('supritendent', 'Supritendent'),
        ('acp', 'ACP'),
        ('dcp', 'DCP'),
        ('ict_officer', 'ICT Officer'),
        ('systems_analyst', 'Systems Analyst'),
        ('network_admin', 'Network Administrator'),
        ('security_analyst', 'Security Analyst'),
    ]

    REGION_CHOICES = [
        ('southern', 'Southern Region'),
        ('northern', 'Northern Region'),
        ('eastern', 'Eastern Region'),
        ('central', 'Central Region'),
    ]

    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='reception')
    rank = models.CharField(max_length=20, choices=RANK_CHOICES, blank=True, null=True)
    prison_station = models.ForeignKey(
        'prison.PrisonStation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    region = models.CharField(max_length=10, choices=REGION_CHOICES, blank=True, null=True, help_text="Region permission (for regional admins)")
    must_change_password = models.BooleanField(default=True)

    # Security fields for ICT monitoring
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_user_agent = models.TextField(blank=True)
    is_suspicious = models.BooleanField(default=False)
    suspicious_reason = models.TextField(blank=True)

    def __str__(self):
        station_name = self.prison_station.name if self.prison_station else 'No station'
        return f"{self.get_full_name()} ({station_name})"

    def is_super_admin(self):
        return self.role == 'superuser' or self.is_superuser

    def is_prison_admin(self):
        return self.role == 'admin'

    def is_reception(self):
        return self.role == 'reception'

    def is_officer_in_charge(self):
        return self.role == 'officer_in_charge'

    def is_station_officer(self):
        return self.role == 'station_officer'

    def is_visitor_attendant(self):
        return self.role == 'visitor_attendant'

    def is_medical_officer(self):
        return self.role == 'medical'

    def is_warden(self):
        return self.role == 'warden'

    def is_ict_personnel(self):
        return self.role == 'ict_personnel'

    def is_rco(self):
        return self.role == 'rco'

    def is_rho(self):
        return self.role == 'rho'

    def is_regional_data_control(self):
        return self.role == 'regional_data_control'

    def has_region_permission(self):
        """Check if user has region-level permission"""
        return self.region is not None and (
            self.is_super_admin() or self.is_prison_admin() or
            self.is_rco() or self.is_rho() or self.is_regional_data_control()
        )

    def has_station_permission(self):
        """Check if user has station-level permission"""
        return self.prison_station is not None