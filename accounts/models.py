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
        
    ]

    RANK_CHOICES = [
        ('warder', 'Warder'),
        ('sergeant', 'Sergeant'),
        ('gaoler', 'Gaoler'),
        ('inspector', 'Inspector'),
        ( 'Supritendent', 'Supritendent'),
        (  'ACP', 'ACP'),
        (  'DCP', 'DCP'),
    ]

    REGION_CHOICES = [
        ('southern', 'Southern Region'),
        ('northern', 'Northern Region'),
        ('eastern', 'Eastern Region'),
        ('western', 'Western Region'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='reception')
    rank = models.CharField(max_length=20, choices=RANK_CHOICES)
    prison_station = models.ForeignKey(
        'prison.PrisonStation', # Use string reference to avoid circular import
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    region = models.CharField(max_length=10, choices=REGION_CHOICES, blank=True, null=True, help_text="Region permission (for regional admins)")
    must_change_password = models.BooleanField(default=True)

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

    def has_region_permission(self):
        """Check if user has region-level permission"""
        return self.region is not None and (self.is_super_admin() or self.is_prison_admin())

    def has_station_permission(self):
        """Check if user has station-level permission"""
        return self.prison_station is not None