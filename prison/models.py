# models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from dateutil.relativedelta import relativedelta
from django.core.validators import MinValueValidator
from django.db.models import Count, Sum
import math
from django.conf import settings
from django.core.exceptions import ValidationError
import base64
import hashlib
import json

User = get_user_model()

# ============ PRISONER NUMBER COUNTER ============

class PrisonerNumberCounter(models.Model):
    """Track prisoner number counters by station, class, and year"""

    PRISONER_CLASS_CHOICES = [
        ('convicted', 'Convicted'),
        ('remand', 'Remand'),
    ]

    prison_station = models.ForeignKey(
        'PrisonStation',
        on_delete=models.CASCADE,
        related_name='number_counters'
    )
    prisoner_class = models.CharField(max_length=10, choices=PRISONER_CLASS_CHOICES)
    year = models.IntegerField()
    last_number = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['prison_station', 'prisoner_class', 'year']
        ordering = ['prison_station', 'prisoner_class', '-year']
        verbose_name = "Prisoner Number Counter"
        verbose_name_plural = "Prisoner Number Counters"

    def __str__(self):
        return f"{self.prison_station.code}-{self.get_prisoner_class_display()} {self.year}: {self.last_number}"

    @classmethod
    def get_next_number(cls, prison_station, prisoner_class):
        """
        Get the next sequential number for a station, class, and current year

        Args:
            prison_station: PrisonStation instance
            prisoner_class: 'convicted' or 'remand'

        Returns:
            int: The next sequential number
        """
        current_year = timezone.now().year

        # Get or create the counter for this station, class, and year
        counter, created = cls.objects.get_or_create(
            prison_station=prison_station,
            prisoner_class=prisoner_class,
            year=current_year,
            defaults={'last_number': 0}
        )

        # Increment and save
        counter.last_number += 1
        counter.save(update_fields=['last_number', 'updated_at'])

        return counter.last_number

    @classmethod
    def generate_prisoner_number(cls, prison_station, prisoner_class):
        """
        Generate a complete prisoner number

        Args:
            prison_station: PrisonStation instance
            prisoner_class: 'convicted' or 'remand'

        Returns:
            str: Generated prisoner number in format like BT001/2026 or BT-R001/2026
        """
        station_code = prison_station.code.upper()
        current_year = timezone.now().year
        next_num = cls.get_next_number(prison_station, prisoner_class)
        num_str = str(next_num).zfill(3)  # Pad with zeros to 3 digits

        if prisoner_class == 'convicted':
            return f"{station_code}{num_str}/{current_year}"
        else:  # remand
            return f"{station_code}-R{num_str}/{current_year}"

    @classmethod
    def reset_counter(cls, prison_station, prisoner_class, year=None):
        """
        Reset a counter (for admin use only)

        Args:
            prison_station: PrisonStation instance
            prisoner_class: 'convicted' or 'remand'
            year: The year to reset (defaults to current year)
        """
        if year is None:
            year = timezone.now().year

        counter, created = cls.objects.get_or_create(
            prison_station=prison_station,
            prisoner_class=prisoner_class,
            year=year,
            defaults={'last_number': 0}
        )

        if not created:
            counter.last_number = 0
            counter.save(update_fields=['last_number', 'updated_at'])

        return counter


# ============ PRISON STATION ============

class PrisonStation(models.Model):
    REGION_CHOICES = [
        ('southern', 'Southern Region'),
        ('northern', 'Northern Region'),
        ('eastern', 'Eastern Region'),
        ('central', 'Central Region'),
    ]

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    location = models.CharField(max_length=100)
    region = models.CharField(max_length=10, choices=REGION_CHOICES, default='southern')
    capacity = models.PositiveIntegerField()
    date_established = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_stations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_region_display()})"

    class Meta:
        verbose_name = "Prison Station"
        verbose_name_plural = "Prison Stations"


# ============ PRISONER ============

class Prisoner(models.Model):
    PRISONER_CLASS_CHOICES = [
        ('convicted', 'Convicted'),
        ('remand', 'Remand'),
    ]

    SEX_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    prisoner_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text="Auto-generated prisoner number. Leave blank to auto-generate."
    )
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    surname = models.CharField(max_length=100)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    age = models.PositiveIntegerField()
    prisoner_class = models.CharField(max_length=10, choices=PRISONER_CLASS_CHOICES)
    prison_station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE)
    block_number = models.CharField(max_length=10)
    cell_number = models.CharField(max_length=10)
    image = models.ImageField(upload_to='prisoner_images/', blank=True, null=True)
    document = models.FileField(upload_to='prisoner_documents/', blank=True, null=True,
        help_text="Attach PDF document (court orders, medical reports, etc.)")
    date_admitted = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    date_released = models.DateField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_prisoners')
    last_modified = models.DateTimeField(auto_now=True)

    # ============ BIOMETRIC / FINGERPRINT FIELDS ============
    fingerprint_template = models.TextField(blank=True, null=True,
        help_text="Base64 encoded fingerprint template")
    fingerprint_hash = models.CharField(max_length=64, blank=True, null=True,
        help_text="SHA-256 hash of fingerprint for quick matching")
    fingerprint_captured_at = models.DateTimeField(blank=True, null=True)
    fingerprint_captured_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='captured_fingerprints'
    )
    fingerprint_quality = models.IntegerField(blank=True, null=True,
        help_text="Quality score 0-100")
    fingerprint_device = models.ForeignKey(
        'FingerprintDevice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='captured_fingerprints'
    )

    # Identity tracking
    previous_identities = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='linked_identities'
    )
    is_identity_verified = models.BooleanField(default=False,
        help_text="Indicates if identity has been verified via fingerprint")
    identity_verified_at = models.DateTimeField(blank=True, null=True)
    identity_verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_identities'
    )
    identity_verification_notes = models.TextField(blank=True,
        help_text="Notes about identity verification process")

    # ============ RECIDIVISM TRACKING ============
    is_recidivist = models.BooleanField(default=False,
        help_text="Indicates if this prisoner has been incarcerated before")
    previous_prisoner_numbers = models.TextField(blank=True,
        help_text="Comma-separated list of previous prisoner numbers")
    first_incarceration_date = models.DateField(blank=True, null=True,
        help_text="Date of first incarceration (if recidivist)")
    recidivism_detected_at = models.DateTimeField(blank=True, null=True,
        help_text="When recidivism was detected")
    recidivism_detected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detected_recidivists'
    )
    recidivism_notes = models.TextField(blank=True,
        help_text="Notes about recidivism detection")

    def __str__(self):
        return f"{self.prisoner_number} - {self.first_name} {self.surname}"

    @property
    def has_fingerprint(self):
        return bool(self.fingerprint_template and self.fingerprint_hash)

    @property
    def full_name(self):
        return f"{self.first_name} {self.middle_name} {self.surname}".strip()

    @property
    def is_biometrically_verified(self):
        return self.is_identity_verified and self.has_fingerprint

    def get_fingerprint_metadata(self):
        """Get fingerprint metadata as dictionary"""
        if not self.has_fingerprint:
            return None
        return {
            'has_fingerprint': True,
            'quality': self.fingerprint_quality,
            'captured_at': self.fingerprint_captured_at.isoformat() if self.fingerprint_captured_at else None,
            'captured_by': self.fingerprint_captured_by.username if self.fingerprint_captured_by else None,
            'device': self.fingerprint_device.name if self.fingerprint_device else None,
            'is_verified': self.is_identity_verified
        }

    def save(self, *args, **kwargs):
        if not self.prisoner_number:
            self.prisoner_number = PrisonerNumberCounter.generate_prisoner_number(
                self.prison_station,
                self.prisoner_class
            )

        if self.fingerprint_template and not self.fingerprint_hash:
            self.fingerprint_hash = hashlib.sha256(
                self.fingerprint_template.encode()
            ).hexdigest()

        super().save(*args, **kwargs)


class PrisonerAttachment(models.Model):
    ATTACHMENT_TYPE_CHOICES = [
        ('photo', 'Photo'),
        ('document', 'Document'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='prisoner_attachments/')
    attachment_type = models.CharField(max_length=10, choices=ATTACHMENT_TYPE_CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.prisoner.prisoner_number} - {self.file.name}"


# ============ PRISONER RELEASE REVIEW ============

class PrisonerReleaseReview(models.Model):
    REVIEW_ROLE_CHOICES = [
        ('officer_in_charge', 'Officer in Charge'),
        ('station_officer', 'Station Officer'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='release_reviews')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_release_reviews'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_release_reviews'
    )
    review_role = models.CharField(max_length=25, choices=REVIEW_ROLE_CHOICES)
    station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='release_reviews')
    release_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.prisoner.prisoner_number} - {self.get_review_role_display()}"


# ============ CONVICTED PRISONER ============

class ConvictedPrisoner(models.Model):
    SENTENCE_STRUCTURE_CHOICES = [
        ('concurrent', 'Concurrent'),
        ('consecutive', 'Consecutive'),
    ]

    OFFENSE_CHOICES = [
    ('Treason contrary to section 38 of the Penal Code', 'Treason contrary to section 38 of the Penal Code'),
    ('Concealment of treason (misprision of treason) contrary to section 39 of the Penal Code', 'Concealment of treason (misprision of treason) contrary to section 39 of the Penal Code'),
    ('Promoting war, etc., amongst groups contrary to section 40 of the Penal Code', 'Promoting war, etc., amongst groups contrary to section 40 of the Penal Code'),
    ('Inciting to mutiny contrary to section 41 of the Penal Code', 'Inciting to mutiny contrary to section 41 of the Penal Code'),
    ('Aiding soldiers or policemen in acts of mutiny contrary to section 42 of the Penal Code', 'Aiding soldiers or policemen in acts of mutiny contrary to section 42 of the Penal Code'),
    ('Inducing soldiers or policemen to desert contrary to section 43 of the Penal Code', 'Inducing soldiers or policemen to desert contrary to section 43 of the Penal Code'),
    ('Aiding prisoners of war to escape contrary to section 44 of the Penal Code', 'Aiding prisoners of war to escape contrary to section 44 of the Penal Code'),
    ('Seditious offences contrary to section 51 of the Penal Code', 'Seditious offences contrary to section 51 of the Penal Code'),
    ('Possession of seditious publication contrary to section 51(2) of the Penal Code', 'Possession of seditious publication contrary to section 51(2) of the Penal Code'),
    ('Unlawful oaths to commit capital offences contrary to section 54 of the Penal Code', 'Unlawful oaths to commit capital offences contrary to section 54 of the Penal Code'),
    ('Other unlawful oaths to commit offences contrary to section 55 of the Penal Code', 'Other unlawful oaths to commit offences contrary to section 55 of the Penal Code'),
    ('Compelling another person to take an oath contrary to section 56 of the Penal Code', 'Compelling another person to take an oath contrary to section 56 of the Penal Code'),
    ('Being present at administering of oath without reporting contrary to section 58 of the Penal Code', 'Being present at administering of oath without reporting contrary to section 58 of the Penal Code'),
    ('Unlawful drilling contrary to section 59 of the Penal Code', 'Unlawful drilling contrary to section 59 of the Penal Code'),
    ('Publication of false news likely to cause fear and alarm contrary to section 60 of the Penal Code', 'Publication of false news likely to cause fear and alarm contrary to section 60 of the Penal Code'),
    ('Defamation of foreign dignitaries contrary to section 61 of the Penal Code', 'Defamation of foreign dignitaries contrary to section 61 of the Penal Code'),
    ('Foreign enlistment contrary to section 62 of the Penal Code', 'Foreign enlistment contrary to section 62 of the Penal Code'),
    ('Piracy contrary to section 63 of the Penal Code', 'Piracy contrary to section 63 of the Penal Code'),
    ('Managing unlawful society contrary to section 65 of the Penal Code', 'Managing unlawful society contrary to section 65 of the Penal Code'),
    ('Being member of unlawful society contrary to section 66 of the Penal Code', 'Being member of unlawful society contrary to section 66 of the Penal Code'),
    ('Unlawful assembly contrary to section 71 of the Penal Code', 'Unlawful assembly contrary to section 71 of the Penal Code'),
    ('Taking part in unlawful assembly contrary to section 72 of the Penal Code', 'Taking part in unlawful assembly contrary to section 72 of the Penal Code'),
    ('Taking part in riot contrary to section 73 of the Penal Code', 'Taking part in riot contrary to section 73 of the Penal Code'),
    ('Rioting after proclamation contrary to section 76 of the Penal Code', 'Rioting after proclamation contrary to section 76 of the Penal Code'),
    ('Preventing or obstructing making of proclamation contrary to section 77 of the Penal Code', 'Preventing or obstructing making of proclamation contrary to section 77 of the Penal Code'),
    ('Rioters demolishing buildings, etc. contrary to section 78 of the Penal Code', 'Rioters demolishing buildings, etc. contrary to section 78 of the Penal Code'),
    ('Rioters injuring buildings, machinery, etc. contrary to section 79 of the Penal Code', 'Rioters injuring buildings, machinery, etc. contrary to section 79 of the Penal Code'),
    ('Riotously preventing sailing of ship contrary to section 80 of the Penal Code', 'Riotously preventing sailing of ship contrary to section 80 of the Penal Code'),
    ('Carrying offensive weapons without lawful authority contrary to section 81 of the Penal Code', 'Carrying offensive weapons without lawful authority contrary to section 81 of the Penal Code'),
    ('Forcible entry contrary to section 82 of the Penal Code', 'Forcible entry contrary to section 82 of the Penal Code'),
    ('Forcible detainer contrary to section 83 of the Penal Code', 'Forcible detainer contrary to section 83 of the Penal Code'),
    ('Fighting in public contrary to section 84 of the Penal Code', 'Fighting in public contrary to section 84 of the Penal Code'),
    ('Challenge to fight a duel contrary to section 85 of the Penal Code', 'Challenge to fight a duel contrary to section 85 of the Penal Code'),
    ('Threatening violence contrary to section 86 of the Penal Code', 'Threatening violence contrary to section 86 of the Penal Code'),
    ('Proposing violence at assemblies contrary to section 87 of the Penal Code', 'Proposing violence at assemblies contrary to section 87 of the Penal Code'),
    ('Intimidation contrary to section 88 of the Penal Code', 'Intimidation contrary to section 88 of the Penal Code'),
    ('Assembling for purpose of smuggling contrary to section 89 of the Penal Code', 'Assembling for purpose of smuggling contrary to section 89 of the Penal Code'),
    ('Official corruption contrary to section 90 of the Penal Code', 'Official corruption contrary to section 90 of the Penal Code'),
    ('Extortion by public officers contrary to section 91 of the Penal Code', 'Extortion by public officers contrary to section 91 of the Penal Code'),
    ('Public officers receiving property to show favour contrary to section 92 of the Penal Code', 'Public officers receiving property to show favour contrary to section 92 of the Penal Code'),
    ('Officers charged with administration of property of special character contrary to section 93 of the Penal Code', 'Officers charged with administration of property of special character contrary to section 93 of the Penal Code'),
    ('False claims by officials contrary to section 94 of the Penal Code', 'False claims by officials contrary to section 94 of the Penal Code'),
    ('Abuse of office contrary to section 95 of the Penal Code', 'Abuse of office contrary to section 95 of the Penal Code'),
    ('False certificates by public officers contrary to section 96 of the Penal Code', 'False certificates by public officers contrary to section 96 of the Penal Code'),
    ('Unauthorized administration of oaths contrary to section 97 of the Penal Code', 'Unauthorized administration of oaths contrary to section 97 of the Penal Code'),
    ('False assumption of authority contrary to section 98 of the Penal Code', 'False assumption of authority contrary to section 98 of the Penal Code'),
    ('Personating public officers contrary to section 99 of the Penal Code', 'Personating public officers contrary to section 99 of the Penal Code'),
    ('Threat of injury to persons employed in public service contrary to section 100 of the Penal Code', 'Threat of injury to persons employed in public service contrary to section 100 of the Penal Code'),
    ('Perjury contrary to section 101 of the Penal Code', 'Perjury contrary to section 101 of the Penal Code'),
    ('Subornation of perjury contrary to section 101(3) of the Penal Code', 'Subornation of perjury contrary to section 101(3) of the Penal Code'),
    ('False statements by interpreters contrary to section 103 of the Penal Code', 'False statements by interpreters contrary to section 103 of the Penal Code'),
    ('Fabricating evidence contrary to section 105 of the Penal Code', 'Fabricating evidence contrary to section 105 of the Penal Code'),
    ('False swearing contrary to section 106 of the Penal Code', 'False swearing contrary to section 106 of the Penal Code'),
    ('Deceiving witnesses contrary to section 107 of the Penal Code', 'Deceiving witnesses contrary to section 107 of the Penal Code'),
    ('Destroying evidence contrary to section 108 of the Penal Code', 'Destroying evidence contrary to section 108 of the Penal Code'),
    ('Conspiracy to defeat justice contrary to section 109 of the Penal Code', 'Conspiracy to defeat justice contrary to section 109 of the Penal Code'),
    ('Interference with witnesses contrary to section 109 of the Penal Code', 'Interference with witnesses contrary to section 109 of the Penal Code'),
    ('Compounding felonies contrary to section 110 of the Penal Code', 'Compounding felonies contrary to section 110 of the Penal Code'),
    ('Compounding penal actions contrary to section 111 of the Penal Code', 'Compounding penal actions contrary to section 111 of the Penal Code'),
    ('Advertisements for stolen property contrary to section 112 of the Penal Code', 'Advertisements for stolen property contrary to section 112 of the Penal Code'),
    ('Offences relating to judicial proceedings contrary to section 113 of the Penal Code', 'Offences relating to judicial proceedings contrary to section 113 of the Penal Code'),
    ('Rescue from lawful custody contrary to section 114 of the Penal Code', 'Rescue from lawful custody contrary to section 114 of the Penal Code'),
    ('Escape from lawful custody contrary to section 115 of the Penal Code', 'Escape from lawful custody contrary to section 115 of the Penal Code'),
    ('Permitting prisoners to escape contrary to section 116 of the Penal Code', 'Permitting prisoners to escape contrary to section 116 of the Penal Code'),
    ('Aiding prisoners to escape contrary to section 117 of the Penal Code', 'Aiding prisoners to escape contrary to section 117 of the Penal Code'),
    ('Removal of property under lawful seizure contrary to section 118 of the Penal Code', 'Removal of property under lawful seizure contrary to section 118 of the Penal Code'),
    ('Obstructing court officers contrary to section 119 of the Penal Code', 'Obstructing court officers contrary to section 119 of the Penal Code'),
    ('Frauds and breaches of trust by public officers contrary to section 120 of the Penal Code', 'Frauds and breaches of trust by public officers contrary to section 120 of the Penal Code'),
    ('Neglect of official duty contrary to section 121 of the Penal Code', 'Neglect of official duty contrary to section 121 of the Penal Code'),
    ('False information to person employed in the public service contrary to section 122 of the Penal Code', 'False information to person employed in the public service contrary to section 122 of the Penal Code'),
    ('Disobedience of statutory duty contrary to section 123 of the Penal Code', 'Disobedience of statutory duty contrary to section 123 of the Penal Code'),
    ('Soliciting to break the law contrary to section 124 of the Penal Code', 'Soliciting to break the law contrary to section 124 of the Penal Code'),
    ('Soliciting public officers to fail to carry out duties contrary to section 125 of the Penal Code', 'Soliciting public officers to fail to carry out duties contrary to section 125 of the Penal Code'),
    ('Insult to religion of any class contrary to section 127 of the Penal Code', 'Insult to religion of any class contrary to section 127 of the Penal Code'),
    ('Disturbing religious assemblies contrary to section 128 of the Penal Code', 'Disturbing religious assemblies contrary to section 128 of the Penal Code'),
    ('Trespassing on burial places contrary to section 129 of the Penal Code', 'Trespassing on burial places contrary to section 129 of the Penal Code'),
    ('Writing or uttering words with intent to wound religious feelings contrary to section 130 of the Penal Code', 'Writing or uttering words with intent to wound religious feelings contrary to section 130 of the Penal Code'),
    ('Hindering burial of dead body contrary to section 131 of the Penal Code', 'Hindering burial of dead body contrary to section 131 of the Penal Code'),
    ('Rape contrary to section 132 of the Penal Code', 'Rape contrary to section 132 of the Penal Code'),
    ('Attempted rape contrary to section 134 of the Penal Code', 'Attempted rape contrary to section 134 of the Penal Code'),
    ('Abduction contrary to section 135 of the Penal Code', 'Abduction contrary to section 135 of the Penal Code'),
    ('Abduction of girls under sixteen contrary to section 136 of the Penal Code', 'Abduction of girls under sixteen contrary to section 136 of the Penal Code'),
    ('Indecent assault on females contrary to section 137 of the Penal Code', 'Indecent assault on females contrary to section 137 of the Penal Code'),
    ('Insulting the modesty of a woman contrary to section 137(3) of the Penal Code', 'Insulting the modesty of a woman contrary to section 137(3) of the Penal Code'),
    ('Indecent practices between females contrary to section 137A of the Penal Code', 'Indecent practices between females contrary to section 137A of the Penal Code'),
    ('Defilement of girls under sixteen contrary to section 138 of the Penal Code', 'Defilement of girls under sixteen contrary to section 138 of the Penal Code'),
    ('Defilement of idiots or imbeciles contrary to section 139 of the Penal Code', 'Defilement of idiots or imbeciles contrary to section 139 of the Penal Code'),
    ('Procuration contrary to section 140 of the Penal Code', 'Procuration contrary to section 140 of the Penal Code'),
    ('Procuring defilement by threats or fraud or administering drugs contrary to section 141 of the Penal Code', 'Procuring defilement by threats or fraud or administering drugs contrary to section 141 of the Penal Code'),
    ('Householder permitting defilement of girl under sixteen on premises contrary to section 142 of the Penal Code', 'Householder permitting defilement of girl under sixteen on premises contrary to section 142 of the Penal Code'),
    ('Detention with intent or in brothel contrary to section 143 of the Penal Code', 'Detention with intent or in brothel contrary to section 143 of the Penal Code'),
    ('Male person living on earnings of prostitution contrary to section 145 of the Penal Code', 'Male person living on earnings of prostitution contrary to section 145 of the Penal Code'),
    ('Woman aiding prostitution for gain contrary to section 146 of the Penal Code', 'Woman aiding prostitution for gain contrary to section 146 of the Penal Code'),
    ('Keeping a brothel contrary to section 147 of the Penal Code', 'Keeping a brothel contrary to section 147 of the Penal Code'),
    ('Promoting prostitution contrary to section 147A of the Penal Code', 'Promoting prostitution contrary to section 147A of the Penal Code'),
    ('Conspiracy to defile contrary to section 148 of the Penal Code', 'Conspiracy to defile contrary to section 148 of the Penal Code'),
    ('Attempts to procure abortion contrary to section 149 of the Penal Code', 'Attempts to procure abortion contrary to section 149 of the Penal Code'),
    ('Woman procuring her own miscarriage contrary to section 150 of the Penal Code', 'Woman procuring her own miscarriage contrary to section 150 of the Penal Code'),
    ('Supplying drugs or instruments to procure abortion contrary to section 151 of the Penal Code', 'Supplying drugs or instruments to procure abortion contrary to section 151 of the Penal Code'),
    ('Unnatural offences contrary to section 153 of the Penal Code', 'Unnatural offences contrary to section 153 of the Penal Code'),
    ('Attempt to commit unnatural offences contrary to section 154 of the Penal Code', 'Attempt to commit unnatural offences contrary to section 154 of the Penal Code'),
    ('Indecent assault of boys under fourteen contrary to section 155 of the Penal Code', 'Indecent assault of boys under fourteen contrary to section 155 of the Penal Code'),
    ('Indecent assault against idiots and imbeciles contrary to section 155A of the Penal Code', 'Indecent assault against idiots and imbeciles contrary to section 155A of the Penal Code'),
    ('Indecent practices between males contrary to section 156 of the Penal Code', 'Indecent practices between males contrary to section 156 of the Penal Code'),
    ('Incest by males contrary to section 157 of the Penal Code', 'Incest by males contrary to section 157 of the Penal Code'),
    ('Incest by females contrary to section 158 of the Penal Code', 'Incest by females contrary to section 158 of the Penal Code'),
    ('Sexual intercourse with minors under care or protection contrary to section 159A of the Penal Code', 'Sexual intercourse with minors under care or protection contrary to section 159A of the Penal Code'),
    ('Sexual activity with a child contrary to section 160B of the Penal Code', 'Sexual activity with a child contrary to section 160B of the Penal Code'),
    ('Indecent practice in the presence of or with a child contrary to section 160C of the Penal Code', 'Indecent practice in the presence of or with a child contrary to section 160C of the Penal Code'),
    ('Showing, selling, exposing offensive materials to a child contrary to section 160D of the Penal Code', 'Showing, selling, exposing offensive materials to a child contrary to section 160D of the Penal Code'),
    ('Recording a child contrary to section 160E of the Penal Code', 'Recording a child contrary to section 160E of the Penal Code'),
    ('Procuring child to take part in public entertainment contrary to section 160F of the Penal Code', 'Procuring child to take part in public entertainment contrary to section 160F of the Penal Code'),
    ('Fraudulent pretence of marriage contrary to section 161 of the Penal Code', 'Fraudulent pretence of marriage contrary to section 161 of the Penal Code'),
    ('Bigamy contrary to section 162 of the Penal Code', 'Bigamy contrary to section 162 of the Penal Code'),
    ('Marriage ceremony fraudulently gone through without lawful marriage contrary to section 163 of the Penal Code', 'Marriage ceremony fraudulently gone through without lawful marriage contrary to section 163 of the Penal Code'),
    ('Desertion of children contrary to section 164 of the Penal Code', 'Desertion of children contrary to section 164 of the Penal Code'),
    ('Neglecting to provide food for children contrary to section 165 of the Penal Code', 'Neglecting to provide food for children contrary to section 165 of the Penal Code'),
    ('Master not providing for servants or apprentices contrary to section 166 of the Penal Code', 'Master not providing for servants or apprentices contrary to section 166 of the Penal Code'),
    ('Child stealing contrary to section 167 of the Penal Code', 'Child stealing contrary to section 167 of the Penal Code'),
    ('Common nuisance contrary to section 168 of the Penal Code', 'Common nuisance contrary to section 168 of the Penal Code'),
    ('Keeping a common gaming house contrary to section 169 of the Penal Code', 'Keeping a common gaming house contrary to section 169 of the Penal Code'),
    ('Found in a common gaming house contrary to section 169(4) of the Penal Code', 'Found in a common gaming house contrary to section 169(4) of the Penal Code'),
    ('Keeping a common betting house contrary to section 170 of the Penal Code', 'Keeping a common betting house contrary to section 170 of the Penal Code'),
    ('Lotteries contrary to section 173 of the Penal Code', 'Lotteries contrary to section 173 of the Penal Code'),
    ('Organizing, managing or conducting pools contrary to section 176 of the Penal Code', 'Organizing, managing or conducting pools contrary to section 176 of the Penal Code'),
    ('Chain letters contrary to section 177 of the Penal Code', 'Chain letters contrary to section 177 of the Penal Code'),
    ('Obscene matters or things contrary to section 179 of the Penal Code', 'Obscene matters or things contrary to section 179 of the Penal Code'),
    ('Idle and disorderly persons contrary to section 180 of the Penal Code', 'Idle and disorderly persons contrary to section 180 of the Penal Code'),
    ('Conduct likely to cause a breach of the peace contrary to section 181 of the Penal Code', 'Conduct likely to cause a breach of the peace contrary to section 181 of the Penal Code'),
    ('Use of insulting language contrary to section 182 of the Penal Code', 'Use of insulting language contrary to section 182 of the Penal Code'),
    ('Nuisances by drunken persons contrary to section 183 of the Penal Code', 'Nuisances by drunken persons contrary to section 183 of the Penal Code'),
    ('Rogues and vagabonds contrary to section 184 of the Penal Code', 'Rogues and vagabonds contrary to section 184 of the Penal Code'),
    ('Failing to comply with removal order contrary to section 189 of the Penal Code', 'Failing to comply with removal order contrary to section 189 of the Penal Code'),
    ('Wearing uniform without authority contrary to section 191 of the Penal Code', 'Wearing uniform without authority contrary to section 191 of the Penal Code'),
    ('Negligent act likely to spread disease dangerous to life contrary to section 192 of the Penal Code', 'Negligent act likely to spread disease dangerous to life contrary to section 192 of the Penal Code'),
    ('Adulteration of food or drink intended for sale contrary to section 193 of the Penal Code', 'Adulteration of food or drink intended for sale contrary to section 193 of the Penal Code'),
    ('Importation of adulterated food or drinks contrary to section 193A of the Penal Code', 'Importation of adulterated food or drinks contrary to section 193A of the Penal Code'),
    ('Sale of noxious food or drink contrary to section 194 of the Penal Code', 'Sale of noxious food or drink contrary to section 194 of the Penal Code'),
    ('Adulteration of drugs contrary to section 195 of the Penal Code', 'Adulteration of drugs contrary to section 195 of the Penal Code'),
    ('Importation of adulterated drugs contrary to section 195A of the Penal Code', 'Importation of adulterated drugs contrary to section 195A of the Penal Code'),
    ('Sale of adulterated drugs contrary to section 196 of the Penal Code', 'Sale of adulterated drugs contrary to section 196 of the Penal Code'),
    ('Fouling water contrary to section 197 of the Penal Code', 'Fouling water contrary to section 197 of the Penal Code'),
    ('Fouling air contrary to section 198 of the Penal Code', 'Fouling air contrary to section 198 of the Penal Code'),
    ('Offensive trades contrary to section 199 of the Penal Code', 'Offensive trades contrary to section 199 of the Penal Code'),
    ('Libel contrary to section 200 of the Penal Code', 'Libel contrary to section 200 of the Penal Code'),
    ('Publication of defamatory matter concerning a dead person without consent contrary to section 201 of the Penal Code', 'Publication of defamatory matter concerning a dead person without consent contrary to section 201 of the Penal Code'),
    ('Manslaughter contrary to section 208 of the Penal Code', 'Manslaughter contrary to section 208 of the Penal Code'),
    ('Murder contrary to section 209 of the Penal Code', 'Murder contrary to section 209 of the Penal Code'),
    ('Genocide contrary to section 217A of the Penal Code', 'Genocide contrary to section 217A of the Penal Code'),
    ('Attempt to murder contrary to section 223 of the Penal Code', 'Attempt to murder contrary to section 223 of the Penal Code'),
    ('Accessory after the fact to murder contrary to section 225 of the Penal Code', 'Accessory after the fact to murder contrary to section 225 of the Penal Code'),
    ('Written threats to murder contrary to section 226 of the Penal Code', 'Written threats to murder contrary to section 226 of the Penal Code'),
    ('Conspiracy to murder contrary to section 227 of the Penal Code', 'Conspiracy to murder contrary to section 227 of the Penal Code'),
    ('Aiding suicide contrary to section 228 of the Penal Code', 'Aiding suicide contrary to section 228 of the Penal Code'),
    ('Attempting suicide contrary to section 229 of the Penal Code', 'Attempting suicide contrary to section 229 of the Penal Code'),
    ('Infanticide contrary to section 230 of the Penal Code', 'Infanticide contrary to section 230 of the Penal Code'),
    ('Killing unborn child contrary to section 231 of the Penal Code', 'Killing unborn child contrary to section 231 of the Penal Code'),
    ('Concealing birth of child contrary to section 232 of the Penal Code', 'Concealing birth of child contrary to section 232 of the Penal Code'),
    ('Abandonment of child at birth contrary to section 232A of the Penal Code', 'Abandonment of child at birth contrary to section 232A of the Penal Code'),
    ('Disabling in order to commit felony or misdemeanor contrary to section 233 of the Penal Code', 'Disabling in order to commit felony or misdemeanor contrary to section 233 of the Penal Code'),
    ('Stupefying in order to commit felony or misdemeanor contrary to section 234 of the Penal Code', 'Stupefying in order to commit felony or misdemeanor contrary to section 234 of the Penal Code'),
    ('Acts intended to cause grievous harm or prevent arrest contrary to section 235 of the Penal Code', 'Acts intended to cause grievous harm or prevent arrest contrary to section 235 of the Penal Code'),
    ('Preventing escape from wreck contrary to section 236 of the Penal Code', 'Preventing escape from wreck contrary to section 236 of the Penal Code'),
    ('Intentionally endangering safety of persons travelling by railway or road contrary to section 237 of the Penal Code', 'Intentionally endangering safety of persons travelling by railway or road contrary to section 237 of the Penal Code'),
    ('Grievous harm contrary to section 238 of the Penal Code', 'Grievous harm contrary to section 238 of the Penal Code'),
    ('Attempting to injure by explosive substances contrary to section 239 of the Penal Code', 'Attempting to injure by explosive substances contrary to section 239 of the Penal Code'),
    ('Maliciously administering poison with intent to harm contrary to section 240 of the Penal Code', 'Maliciously administering poison with intent to harm contrary to section 240 of the Penal Code'),
    ('Wounding and similar acts contrary to section 241 of the Penal Code', 'Wounding and similar acts contrary to section 241 of the Penal Code'),
    ('Failure to supply necessaries contrary to section 242 of the Penal Code', 'Failure to supply necessaries contrary to section 242 of the Penal Code'),
    ('Endangering the environment contrary to section 245A of the Penal Code', 'Endangering the environment contrary to section 245A of the Penal Code'),
    ('Reckless and negligent acts contrary to section 246 of the Penal Code', 'Reckless and negligent acts contrary to section 246 of the Penal Code'),
    ('Other negligent acts causing harm contrary to section 247 of the Penal Code', 'Other negligent acts causing harm contrary to section 247 of the Penal Code'),
    ('Dealing in poisonous substances in negligent manner contrary to section 248 of the Penal Code', 'Dealing in poisonous substances in negligent manner contrary to section 248 of the Penal Code'),
    ('Endangering safety of persons travelling by railway or road contrary to section 249 of the Penal Code', 'Endangering safety of persons travelling by railway or road contrary to section 249 of the Penal Code'),
    ('Exhibition of false light, mark or buoy contrary to section 250 of the Penal Code', 'Exhibition of false light, mark or buoy contrary to section 250 of the Penal Code'),
    ('Conveying person by water for hire in unsafe or overloaded vessel contrary to section 251 of the Penal Code', 'Conveying person by water for hire in unsafe or overloaded vessel contrary to section 251 of the Penal Code'),
    ('Danger or obstruction in public way or line of navigation contrary to section 252 of the Penal Code', 'Danger or obstruction in public way or line of navigation contrary to section 252 of the Penal Code'),
    ('Common assault contrary to section 253 of the Penal Code', 'Common assault contrary to section 253 of the Penal Code'),
    ('Assaults occasioning actual bodily harm contrary to section 254 of the Penal Code', 'Assaults occasioning actual bodily harm contrary to section 254 of the Penal Code'),
    ('Assaults on persons protecting wreck contrary to section 255 of the Penal Code', 'Assaults on persons protecting wreck contrary to section 255 of the Penal Code'),
    ('Assaults punishable with more than five years imprisonment contrary to section 256 of the Penal Code', 'Assaults punishable with more than five years imprisonment contrary to section 256 of the Penal Code'),
    ('Kidnapping from the Republic contrary to section 257 of the Penal Code', 'Kidnapping from the Republic contrary to section 257 of the Penal Code'),
    ('Kidnapping from lawful guardianship contrary to section 258 of the Penal Code', 'Kidnapping from lawful guardianship contrary to section 258 of the Penal Code'),
    ('Abduction contrary to section 259 of the Penal Code', 'Abduction contrary to section 259 of the Penal Code'),
    ('Kidnapping contrary to section 260 of the Penal Code', 'Kidnapping contrary to section 260 of the Penal Code'),
    ('Kidnapping or abducting in order to murder contrary to section 261 of the Penal Code', 'Kidnapping or abducting in order to murder contrary to section 261 of the Penal Code'),
    ('Kidnapping or abducting with intent to confine person contrary to section 262 of the Penal Code', 'Kidnapping or abducting with intent to confine person contrary to section 262 of the Penal Code'),
    ('Kidnapping or abducting to subject person to grievous harm, ransom, slavery etc. contrary to section 263 of the Penal Code', 'Kidnapping or abducting to subject person to grievous harm, ransom, slavery etc. contrary to section 263 of the Penal Code'),
    ('Wrongfully concealing or keeping in confinement kidnapped or abducted person contrary to section 264 of the Penal Code', 'Wrongfully concealing or keeping in confinement kidnapped or abducted person contrary to section 264 of the Penal Code'),
    ('Kidnapping or abducting child under sixteen with intent to steal from its person contrary to section 265 of the Penal Code', 'Kidnapping or abducting child under sixteen with intent to steal from its person contrary to section 265 of the Penal Code'),
    ('Wrongful confinement contrary to section 266 of the Penal Code', 'Wrongful confinement contrary to section 266 of the Penal Code'),
    ('Buying or disposing of any person as a slave contrary to section 267 of the Penal Code', 'Buying or disposing of any person as a slave contrary to section 267 of the Penal Code'),
    ('Habitual dealing in slaves contrary to section 268 of the Penal Code', 'Habitual dealing in slaves contrary to section 268 of the Penal Code'),
    ('Unlawful compulsory labour contrary to section 269 of the Penal Code', 'Unlawful compulsory labour contrary to section 269 of the Penal Code'),
    ('Theft contrary to section 278 of the Penal Code', 'Theft contrary to section 278 of the Penal Code'),
    ('Stealing wills contrary to section 279 of the Penal Code', 'Stealing wills contrary to section 279 of the Penal Code'),
    ('Stealing postal matter contrary to section 280 of the Penal Code', 'Stealing postal matter contrary to section 280 of the Penal Code'),
    ('Stealing cattle contrary to section 281 of the Penal Code', 'Stealing cattle contrary to section 281 of the Penal Code'),
    ('Stealing from the person contrary to section 282 of the Penal Code', 'Stealing from the person contrary to section 282 of the Penal Code'),
    ('Stealing goods in transit contrary to section 282 of the Penal Code', 'Stealing goods in transit contrary to section 282 of the Penal Code'),
    ('Stealing by persons in public service contrary to section 283 of the Penal Code', 'Stealing by persons in public service contrary to section 283 of the Penal Code'),
    ('Negligence by public officer in preserving money or property contrary to section 284 of the Penal Code', 'Negligence by public officer in preserving money or property contrary to section 284 of the Penal Code'),
    ('Theft of public subscriptions contrary to section 285 of the Penal Code', 'Theft of public subscriptions contrary to section 285 of the Penal Code'),
    ('Stealing by clerks and servants contrary to section 286 of the Penal Code', 'Stealing by clerks and servants contrary to section 286 of the Penal Code'),
    ('Stealing by directors or officers of companies contrary to section 287 of the Penal Code', 'Stealing by directors or officers of companies contrary to section 287 of the Penal Code'),
    ('Stealing by agents contrary to section 288 of the Penal Code', 'Stealing by agents contrary to section 288 of the Penal Code'),
    ('Stealing by tenants or lodgers contrary to section 289 of the Penal Code', 'Stealing by tenants or lodgers contrary to section 289 of the Penal Code'),
    ('Stealing after previous conviction contrary to section 290 of the Penal Code', 'Stealing after previous conviction contrary to section 290 of the Penal Code'),
    ('Concealing registers contrary to section 291 of the Penal Code', 'Concealing registers contrary to section 291 of the Penal Code'),
    ('Concealing wills contrary to section 292 of the Penal Code', 'Concealing wills contrary to section 292 of the Penal Code'),
    ('Concealing deeds contrary to section 293 of the Penal Code', 'Concealing deeds contrary to section 293 of the Penal Code'),
    ('Killing animals with intent to steal contrary to section 294 of the Penal Code', 'Killing animals with intent to steal contrary to section 294 of the Penal Code'),
    ('Severing with intent to steal contrary to section 295 of the Penal Code', 'Severing with intent to steal contrary to section 295 of the Penal Code'),
    ('Fraudulent disposal of mortgaged goods contrary to section 296 of the Penal Code', 'Fraudulent disposal of mortgaged goods contrary to section 296 of the Penal Code'),
    ('Fraudulent dealing with minerals in mines contrary to section 297 of the Penal Code', 'Fraudulent dealing with minerals in mines contrary to section 297 of the Penal Code'),
    ('Fraudulent appropriation of power contrary to section 298 of the Penal Code', 'Fraudulent appropriation of power contrary to section 298 of the Penal Code'),
    ('Fraudulent appropriation of water contrary to section 298A of the Penal Code', 'Fraudulent appropriation of water contrary to section 298A of the Penal Code'),
    ('Fraudulent appropriation of telecommunication services contrary to section 298B of the Penal Code', 'Fraudulent appropriation of telecommunication services contrary to section 298B of the Penal Code'),
    ('Unlawful use of vehicles, animals etc. contrary to section 299 of the Penal Code', 'Unlawful use of vehicles, animals etc. contrary to section 299 of the Penal Code'),
    ('Robbery contrary to section 300 of the Penal Code', 'Robbery contrary to section 300 of the Penal Code'),
    ('Attempted robbery contrary to section 302 of the Penal Code', 'Attempted robbery contrary to section 302 of the Penal Code'),
    ('Assault with intent to steal contrary to section 303 of the Penal Code', 'Assault with intent to steal contrary to section 303 of the Penal Code'),
    ('Demanding property by written threats contrary to section 304 of the Penal Code', 'Demanding property by written threats contrary to section 304 of the Penal Code'),
    ('Attempts at extortion by threats contrary to section 305 of the Penal Code', 'Attempts at extortion by threats contrary to section 305 of the Penal Code'),
    ('Procuring execution of deeds by threats contrary to section 306 of the Penal Code', 'Procuring execution of deeds by threats contrary to section 306 of the Penal Code'),
    ('Demanding property with menaces with intent to steal contrary to section 307 of the Penal Code', 'Demanding property with menaces with intent to steal contrary to section 307 of the Penal Code'),
    ('Housebreaking contrary to section 309 of the Penal Code', 'Housebreaking contrary to section 309 of the Penal Code'),
    ('Burglary contrary to section 309(2) of the Penal Code', 'Burglary contrary to section 309(2) of the Penal Code'),
    ('Entering dwelling-house with intent to commit felony contrary to section 310 of the Penal Code', 'Entering dwelling-house with intent to commit felony contrary to section 310 of the Penal Code'),
    ('Breaking into building and committing a felony contrary to section 311 of the Penal Code', 'Breaking into building and committing a felony contrary to section 311 of the Penal Code'),
    ('Breaking into building with intent to commit a felony contrary to section 312 of the Penal Code', 'Breaking into building with intent to commit a felony contrary to section 312 of the Penal Code'),
    ('Persons found armed with intent to commit felony contrary to section 313 of the Penal Code', 'Persons found armed with intent to commit felony contrary to section 313 of the Penal Code'),
    ('Criminal trespass contrary to section 314 of the Penal Code', 'Criminal trespass contrary to section 314 of the Penal Code'),
    ('Unauthorized user of land premises contrary to section 316 of the Penal Code', 'Unauthorized user of land premises contrary to section 316 of the Penal Code'),
    ('Obtaining by false pretences contrary to section 319 of the Penal Code', 'Obtaining by false pretences contrary to section 319 of the Penal Code'),
    ('Fraud other than false pretence contrary to section 319A of the Penal Code', 'Fraud other than false pretence contrary to section 319A of the Penal Code'),
    ('Evasion of liability by false pretence contrary to section 319B of the Penal Code', 'Evasion of liability by false pretence contrary to section 319B of the Penal Code'),
    ('Making off without payment contrary to section 319C of the Penal Code', 'Making off without payment contrary to section 319C of the Penal Code'),
    ('Passing valueless cheque contrary to section 319D of the Penal Code', 'Passing valueless cheque contrary to section 319D of the Penal Code'),
    ('Obtaining execution of a security by false pretences contrary to section 320 of the Penal Code', 'Obtaining execution of a security by false pretences contrary to section 320 of the Penal Code'),
    ('Cheating contrary to section 321 of the Penal Code', 'Cheating contrary to section 321 of the Penal Code'),
    ('Obtaining credit by false pretences contrary to section 322 of the Penal Code', 'Obtaining credit by false pretences contrary to section 322 of the Penal Code'),
    ('Conspiracy to defraud contrary to section 323 of the Penal Code', 'Conspiracy to defraud contrary to section 323 of the Penal Code'),
    ('Frauds on sale or mortgage of property contrary to section 324 of the Penal Code', 'Frauds on sale or mortgage of property contrary to section 324 of the Penal Code'),
    ('Pretending to tell fortunes contrary to section 325 of the Penal Code', 'Pretending to tell fortunes contrary to section 325 of the Penal Code'),
    ('Obtaining registration by false pretence contrary to section 326 of the Penal Code', 'Obtaining registration by false pretence contrary to section 326 of the Penal Code'),
    ('False declaration for passport contrary to section 327 of the Penal Code', 'False declaration for passport contrary to section 327 of the Penal Code'),
    ('Receiving stolen property contrary to section 328 of the Penal Code', 'Receiving stolen property contrary to section 328 of the Penal Code'),
    ('Retaining stolen property contrary to section 328 of the Penal Code', 'Retaining stolen property contrary to section 328 of the Penal Code'),
    ('Person having in possession property suspected of being stolen contrary to section 329 of the Penal Code', 'Person having in possession property suspected of being stolen contrary to section 329 of the Penal Code'),
    ('Receiving or bringing in property dishonestly acquired outside Malawi contrary to section 331 of the Penal Code', 'Receiving or bringing in property dishonestly acquired outside Malawi contrary to section 331 of the Penal Code'),
    ('Money laundering contrary to section 331A of the Penal Code', 'Money laundering contrary to section 331A of the Penal Code'),
    ('Trustees fraudulently disposing of trust property contrary to section 332 of the Penal Code', 'Trustees fraudulently disposing of trust property contrary to section 332 of the Penal Code'),
    ('Directors and officers fraudulently appropriating property contrary to section 333 of the Penal Code', 'Directors and officers fraudulently appropriating property contrary to section 333 of the Penal Code'),
    ('False statements by officials of companies contrary to section 334 of the Penal Code', 'False statements by officials of companies contrary to section 334 of the Penal Code'),
    ('Fraudulent false accounting contrary to section 335 of the Penal Code', 'Fraudulent false accounting contrary to section 335 of the Penal Code'),
    ('False accounting by public officer contrary to section 336 of the Penal Code', 'False accounting by public officer contrary to section 336 of the Penal Code'),
    ('Fraudulent trading by a company contrary to section 336A of the Penal Code', 'Fraudulent trading by a company contrary to section 336A of the Penal Code'),
    ('Arson contrary to section 337 of the Penal Code', 'Arson contrary to section 337 of the Penal Code'),
    ('Attempts to commit arson contrary to section 338 of the Penal Code', 'Attempts to commit arson contrary to section 338 of the Penal Code'),
    ('Setting fire to crops and growing plants contrary to section 339 of the Penal Code', 'Setting fire to crops and growing plants contrary to section 339 of the Penal Code'),
    ('Attempting to set fire to crops contrary to section 340 of the Penal Code', 'Attempting to set fire to crops contrary to section 340 of the Penal Code'),
    ('Casting away ships contrary to section 341 of the Penal Code', 'Casting away ships contrary to section 341 of the Penal Code'),
    ('Attempts to cast away ships contrary to section 342 of the Penal Code', 'Attempts to cast away ships contrary to section 342 of the Penal Code'),
    ('Killing or injuring animals contrary to section 343 of the Penal Code', 'Killing or injuring animals contrary to section 343 of the Penal Code'),
    ('Malicious injuries to property contrary to section 344 of the Penal Code', 'Malicious injuries to property contrary to section 344 of the Penal Code'),
    ('Attempts to destroy property by explosives contrary to section 345 of the Penal Code', 'Attempts to destroy property by explosives contrary to section 345 of the Penal Code'),
    ('Communicating infectious diseases to animals contrary to section 346 of the Penal Code', 'Communicating infectious diseases to animals contrary to section 346 of the Penal Code'),
    ('Removing boundary marks with intent to defraud contrary to section 347 of the Penal Code', 'Removing boundary marks with intent to defraud contrary to section 347 of the Penal Code'),
    ('Wilful damage to survey and boundary marks contrary to section 348 of the Penal Code', 'Wilful damage to survey and boundary marks contrary to section 348 of the Penal Code'),
    ('Damages to railway works contrary to section 349 of the Penal Code', 'Damages to railway works contrary to section 349 of the Penal Code'),
    ('Threats to burn contrary to section 350 of the Penal Code', 'Threats to burn contrary to section 350 of the Penal Code'),
    ('Forgery contrary to section 356 of the Penal Code', 'Forgery contrary to section 356 of the Penal Code'),
    ('Forgery of wills etc. contrary to section 357 of the Penal Code', 'Forgery of wills etc. contrary to section 357 of the Penal Code'),
    ('Forgery of judicial or official documents contrary to section 358 of the Penal Code', 'Forgery of judicial or official documents contrary to section 358 of the Penal Code'),
    ('Forgery of stamps contrary to section 359 of the Penal Code', 'Forgery of stamps contrary to section 359 of the Penal Code'),
    ('Uttering false document contrary to section 360 of the Penal Code', 'Uttering false document contrary to section 360 of the Penal Code'),
    ('Uttering cancelled or exhausted documents contrary to section 361 of the Penal Code', 'Uttering cancelled or exhausted documents contrary to section 361 of the Penal Code'),
    ('Procuring execution of documents by false pretences contrary to section 362 of the Penal Code', 'Procuring execution of documents by false pretences contrary to section 362 of the Penal Code'),
    ('Obliterating crossings on cheques contrary to section 363 of the Penal Code', 'Obliterating crossings on cheques contrary to section 363 of the Penal Code'),
    ('Making documents without authority contrary to section 364 of the Penal Code', 'Making documents without authority contrary to section 364 of the Penal Code'),
    ('Demanding property upon forged testamentary instruments contrary to section 365 of the Penal Code', 'Demanding property upon forged testamentary instruments contrary to section 365 of the Penal Code'),
    ('Importing or purchasing forged notes contrary to section 366 of the Penal Code', 'Importing or purchasing forged notes contrary to section 366 of the Penal Code'),
    ('Falsifying warrants for money payable under public authority contrary to section 367 of the Penal Code', 'Falsifying warrants for money payable under public authority contrary to section 367 of the Penal Code'),
    ('Falsification of register contrary to section 368 of the Penal Code', 'Falsification of register contrary to section 368 of the Penal Code'),
    ('Sending false certificate of marriage to Registrar contrary to section 369 of the Penal Code', 'Sending false certificate of marriage to Registrar contrary to section 369 of the Penal Code'),
    ('False statements for registers of births, deaths and marriages contrary to section 370 of the Penal Code', 'False statements for registers of births, deaths and marriages contrary to section 370 of the Penal Code'),
    ('Counterfeiting coin contrary to section 372 of the Penal Code', 'Counterfeiting coin contrary to section 372 of the Penal Code'),
    ('Preparations for coining contrary to section 373 of the Penal Code', 'Preparations for coining contrary to section 373 of the Penal Code'),
    ('Making or having in possession paper or implements for forgery contrary to section 374 of the Penal Code', 'Making or having in possession paper or implements for forgery contrary to section 374 of the Penal Code'),
    ('Clipping contrary to section 375 of the Penal Code', 'Clipping contrary to section 375 of the Penal Code'),
    ('Melting down of currency contrary to section 376 of the Penal Code', 'Melting down of currency contrary to section 376 of the Penal Code'),
    ('Possession of clippings contrary to section 378 of the Penal Code', 'Possession of clippings contrary to section 378 of the Penal Code'),
    ('Uttering counterfeit coin contrary to section 379 of the Penal Code', 'Uttering counterfeit coin contrary to section 379 of the Penal Code'),
    ('Repeated uttering contrary to section 380 of the Penal Code', 'Repeated uttering contrary to section 380 of the Penal Code'),
    ('Uttering metal or coin not current as coin contrary to section 381 of the Penal Code', 'Uttering metal or coin not current as coin contrary to section 381 of the Penal Code'),
    ('Selling articles bearing designs in imitation of currency contrary to section 382 of the Penal Code', 'Selling articles bearing designs in imitation of currency contrary to section 382 of the Penal Code'),
    ('Exporting counterfeit coin contrary to section 383 of the Penal Code', 'Exporting counterfeit coin contrary to section 383 of the Penal Code'),
    ('Possession of die used for purpose of making stamps contrary to section 385 of the Penal Code', 'Possession of die used for purpose of making stamps contrary to section 385 of the Penal Code'),
    ('Paper and dies for postage stamps contrary to section 386 of the Penal Code', 'Paper and dies for postage stamps contrary to section 386 of the Penal Code'),
    ('Counterfeiting trade marks contrary to section 388 of the Penal Code', 'Counterfeiting trade marks contrary to section 388 of the Penal Code'),
    ('Personation in general contrary to section 389 of the Penal Code', 'Personation in general contrary to section 389 of the Penal Code'),
    ('Falsely acknowledging deeds, recognizances contrary to section 390 of the Penal Code', 'Falsely acknowledging deeds, recognizances contrary to section 390 of the Penal Code'),
    ('Personation of a person named in a certificate contrary to section 391 of the Penal Code', 'Personation of a person named in a certificate contrary to section 391 of the Penal Code'),
    ('Lending certificate for personation contrary to section 392 of the Penal Code', 'Lending certificate for personation contrary to section 392 of the Penal Code'),
    ('Personation of person named in a testimonial of character contrary to section 393 of the Penal Code', 'Personation of person named in a testimonial of character contrary to section 393 of the Penal Code'),
    ('Lending testimonial for personation contrary to section 394 of the Penal Code', 'Lending testimonial for personation contrary to section 394 of the Penal Code'),
    ('Corrupt practices contrary to section 396 of the Penal Code', 'Corrupt practices contrary to section 396 of the Penal Code'),
    ('Secret commission on government contracts contrary to section 397 of the Penal Code', 'Secret commission on government contracts contrary to section 397 of the Penal Code'),
    ('Attempt contrary to section 400 of the Penal Code', 'Attempt contrary to section 400 of the Penal Code'),
    ('Attempts to commit offences contrary to section 401 of the Penal Code', 'Attempts to commit offences contrary to section 401 of the Penal Code'),
    ('Attempts to commit certain felonies contrary to section 402 of the Penal Code', 'Attempts to commit certain felonies contrary to section 402 of the Penal Code'),
    ('Neglect to prevent felony contrary to section 403 of the Penal Code', 'Neglect to prevent felony contrary to section 403 of the Penal Code'),
    ('Conspiracy to commit felony contrary to section 404 of the Penal Code', 'Conspiracy to commit felony contrary to section 404 of the Penal Code'),
    ('Conspiracy to commit misdemeanor contrary to section 405 of the Penal Code', 'Conspiracy to commit misdemeanor contrary to section 405 of the Penal Code'),
    ('Other conspiracies contrary to section 406 of the Penal Code', 'Other conspiracies contrary to section 406 of the Penal Code'),
    ('Accessory after the fact to felony contrary to section 408 of the Penal Code', 'Accessory after the fact to felony contrary to section 408 of the Penal Code'),
    ('Accessory after the fact to misdemeanor contrary to section 409 of the Penal Code', 'Accessory after the fact to misdemeanor contrary to section 409 of the Penal Code'),
]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='convicted_details')
    sentence = models.FloatField(validators=[MinValueValidator(1)], help_text="Sentence in months")
    court = models.CharField(max_length=100)
    case_number = models.CharField(max_length=50, blank=True, help_text="Case number on the warrant of committal")
    offense = models.CharField(max_length=150, choices=OFFENSE_CHOICES, blank=True, null=True)
    sentence_structure = models.CharField(max_length=12, choices=SENTENCE_STRUCTURE_CHOICES, default='concurrent')
    date_of_committal = models.DateField()
    wef_date = models.DateField(verbose_name="With Effect From Date")
    date_of_release = models.DateField(blank=True, null=True)
    date_of_release_on_remission = models.DateField(blank=True, null=True)
    confirmation_status = models.BooleanField(default=False)
    notes = models.CharField(blank=True)
    reduction_months = models.FloatField(default=0, blank=True, validators=[MinValueValidator(0)])
    reduction_notes = models.CharField(blank=True)

    @property
    def sentence_terms(self):
        return [self] + list(self.additional_sentences.all())

    @property
    def effective_sentence(self):
        terms = [term.sentence for term in self.sentence_terms if term.sentence]
        if not terms:
            return self.sentence
        if self.sentence_structure == 'consecutive':
            return sum(terms)
        return max(terms)

    def save(self, *args, **kwargs):
        AVG_DAYS_PER_MONTH = 30.4375
        effective_sentence = self.effective_sentence
        if self.wef_date and effective_sentence:
            adjusted_wef = self.wef_date - relativedelta(days=1)
            sentence_months_val = int(effective_sentence)
            sentence_fraction = effective_sentence - sentence_months_val
            sentence_days = int(sentence_fraction * AVG_DAYS_PER_MONTH)
            self.date_of_release = adjusted_wef + relativedelta(months=sentence_months_val, days=sentence_days)

        if self.date_of_release:
            remission_months_total = effective_sentence / 3
            remission_months_val = int(remission_months_total)
            remission_fraction = remission_months_total - remission_months_val
            remission_days = int(remission_fraction * AVG_DAYS_PER_MONTH)
            self.date_of_release_on_remission = self.date_of_release - relativedelta(months=remission_months_val, days=remission_days)

        if self.reduction_months and self.reduction_months > 0 and self.date_of_release_on_remission:
            reduction_months_val = int(self.reduction_months)
            reduction_fraction = self.reduction_months - reduction_months_val
            reduction_days = int(reduction_fraction * AVG_DAYS_PER_MONTH)
            self.date_of_release_on_remission -= relativedelta(months=reduction_months_val, days=reduction_days)
        super().save(*args, **kwargs)


class AdditionalSentence(models.Model):
    convicted_prisoner = models.ForeignKey(
        ConvictedPrisoner,
        on_delete=models.CASCADE,
        related_name='additional_sentences'
    )
    sentence = models.FloatField(validators=[MinValueValidator(1)], help_text="Sentence in months")
    court = models.CharField(max_length=100, blank=True)
    case_number = models.CharField(max_length=50, blank=True)
    offense = models.CharField(max_length=150, choices=ConvictedPrisoner.OFFENSE_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.case_number or 'Additional sentence'} - {self.sentence} months"


# ============ REMAND PRISONER ============

class RemandPrisoner(models.Model):
    OFFENSE_CHOICES = ConvictedPrisoner.OFFENSE_CHOICES

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='remand_details')
    court_case_number = models.CharField(max_length=50)
    next_court_date = models.DateField()
    remand_extensions = models.PositiveIntegerField(default=0)
    offense = models.CharField(max_length=150, choices=OFFENSE_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.prisoner.prisoner_number} - {self.court_case_number}"


# ============ RISK ASSESSMENT ============

class RiskAssessment(models.Model):
    RISK_LEVEL_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('need_support', 'Need Support'),
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='risk_assessment')
    previous_conviction = models.BooleanField(default=False)
    previous_convictions_count = models.PositiveIntegerField(default=0)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES)

    def __str__(self):
        return f"Risk Assessment for {self.prisoner.prisoner_number}"


# ============ PRISONER PARTICULARS ============

class PrisonerParticulars(models.Model):
    NATIONALITY_CHOICES = [
        ('malawian', 'Malawian'),
        ('mozambican', 'Mozambican'),
        ('zimbabwean', 'Zimbabwean'),
        ('congolese', 'Congolese'),
        ('zambian', 'Zambian'),
        ('tanzanian', 'Tanzanian'),
        ('chinese', 'Chinese'),
        ('japanese', 'Japanese'),
        ('korean', 'Korean'),
        ('indian', 'Indian'),
        ('british', 'British'),
        ('south_african', 'South African'),
        ('burundi', 'Burundi'),
        ('rwandan', 'Rwandan'),
        ('botswana', 'Botswana'),
        ('other', 'Other'),
    ]

    RELIGION_CHOICES = [
        ('christian', 'Christian'),
        ('muslim', 'Muslim'),
        ('other', 'Other'),
    ]

    EDUCATION_LEVEL_CHOICES = [
        ('none', 'No formal education'),
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('tertiary', 'Tertiary'),
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='particulars')
    nationality = models.CharField(max_length=20, choices=NATIONALITY_CHOICES)
    district = models.CharField(max_length=100)
    chief = models.CharField(max_length=100)
    village = models.CharField(max_length=100)
    home_location = models.CharField(max_length=200, blank=True)
    religion = models.CharField(max_length=20, choices=RELIGION_CHOICES)
    denomination = models.CharField(max_length=100, blank=True)
    fathers_name = models.CharField(max_length=200)
    mothers_name = models.CharField(max_length=200)
    married = models.BooleanField(default=False)
    spouse_name = models.CharField(max_length=200, blank=True)
    spouse_location = models.CharField(max_length=300, blank=True)
    next_of_kin = models.CharField(max_length=200)
    next_of_kin_location = models.CharField(max_length=300)
    mobile_number = models.CharField(max_length=20, blank=True)
    national_id = models.CharField(max_length=50, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)
    driving_license = models.CharField(max_length=50, blank=True)
    education_level = models.CharField(max_length=20, choices=EDUCATION_LEVEL_CHOICES)
    literate = models.BooleanField(default=False)
    profession = models.CharField(max_length=100, blank=True)
    past_occupation = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Particulars for {self.prisoner.prisoner_number}"


# ============ PHYSICAL CHARACTERISTICS ============

class PhysicalCharacteristics(models.Model):
    BODY_BUILD_CHOICES = [
        ('medium', 'Medium body build'),
        ('slim', 'Slim body build'),
        ('fat', 'Fat'),
        ('muscular', 'Muscular'),
        ('heavy', 'Heavy'),
    ]

    SKIN_COLOR_CHOICES = [
        ('light', 'Light in Complexion'),
        ('dark', 'Dark in complexion'),
        ('brown', 'Brown in Complexion'),
        ('albino', 'Albino'),
    ]

    EYES_COLOR_CHOICES = [
        ('brown', 'Brown'),
        ('black', 'Black'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('other', 'Other'),
    ]

    HEALTH_CHOICES = [
        ('none', 'None'),
        ('tb', 'TB'),
        ('hiv', 'HIV'),
        ('malaria', 'Malaria prone'),
        ('ptsd', 'PTSD'),
        ('stis', 'STIs'),
        ('malnutrition', 'Malnutrition'),
        ('other', 'Other'),
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='physical')
    height = models.DecimalField(max_digits=5, decimal_places=2, help_text="Height in cm")
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight in kg")
    body_build = models.CharField(max_length=20, choices=BODY_BUILD_CHOICES)
    skin_color = models.CharField(max_length=20, choices=SKIN_COLOR_CHOICES)
    eyes_color = models.CharField(max_length=20, choices=EYES_COLOR_CHOICES)
    head_abnormalities = models.CharField(max_length=100, blank=True)
    health_status = models.CharField(max_length=20, choices=HEALTH_CHOICES, default='none')
    circumcised = models.BooleanField(default=False)
    marks_tattoos_scars = models.CharField(blank=True, max_length=255)
    has_child = models.BooleanField(default=False)
    children_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Physical Characteristics for {self.prisoner.prisoner_number}"


# ============ REHABILITATION PROGRAM ============

class RehabilitationProgram(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert'),
        ('not_applicable', 'Not Applicable'),
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='rehabilitation')
    employed_in_program = models.BooleanField(default=False)
    program_name = models.CharField(max_length=200, blank=True)
    program_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, blank=True)

    def __str__(self):
        return f"Rehabilitation for {self.prisoner.prisoner_number}"


# ============ PRISONER TRANSFER ============

class PrisonerTransfer(models.Model):
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='transfers')
    from_prison = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='transfers_out')
    to_prison = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='transfers_in')
    transfer_date = models.DateField(default=timezone.now)
    reason = models.TextField()
    transferred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Transfer of {self.prisoner.prisoner_number} from {self.from_prison} to {self.to_prison}"


# ============ ACTIVITY LOG ============

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('transfer', 'Transfer'),
        ('approve', 'Approve'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('add_item', 'Add Item'),
        ('withdraw_money', 'Withdraw Money'),
        ('collect_item', 'Collect Item'),
        ('capture_fingerprint', 'Capture Fingerprint'),
        ('verify_identity', 'Verify Identity'),
        ('fingerprint_match', 'Fingerprint Match'),
        ('link_identity', 'Link Identity'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    model = models.CharField(max_length=50)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} {self.action}d {self.model} {self.object_id or ''} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# ============ RELEASE ON REMISSION ============

class ReleaseOnRemission(models.Model):
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE)
    release_date = models.DateField()
    original_sentence = models.FloatField()
    remission_months = models.DecimalField(max_digits=5, decimal_places=2)
    reduction_months = models.FloatField(default=0)
    reduction_reason = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    processed_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Release on remission for {self.prisoner.prisoner_number}"


# ============ VISITOR ============

class Visitor(models.Model):
    RELATIONSHIP_CHOICES = [
        ('family', 'Family Member'),
        ('friend', 'Friend'),
        ('lawyer', 'Lawyer'),
        ('official', 'Government Official'),
        ('other', 'Other'),
    ]

    ID_TYPE_CHOICES = [
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('other', 'Other'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    purpose_of_visit = models.TextField(blank=True, null=True)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    visit_date = models.DateField()
    visit_time = models.TimeField()
    location = models.CharField(max_length=200, blank=True)
    items = models.CharField(max_length=200, blank=True)
    is_approved = models.BooleanField(default=False)
    denial_reason = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_visitors")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_visitors")
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.surname} (Visitor for {self.prisoner.full_name})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.surname}"

    class Meta:
        pass


# ============ MEDICAL RECORD ============

class MedicalRecord(models.Model):
    MEDICAL_CATEGORIES = [
        ('routine', 'Routine Checkup'),
        ('emergency', 'Emergency'),
        ('chronic', 'Chronic Condition'),
        ('mental', 'Mental Health'),
        ('dental', 'Dental'),
        ('other', 'Other'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='medical_records')
    record_date = models.DateField()
    category = models.CharField(max_length=20, choices=MEDICAL_CATEGORIES)
    diagnosis = models.CharField(max_length=200)
    treatment = models.TextField()
    prescribed_medication = models.TextField(blank=True)
    next_checkup = models.DateField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='medical_records_recorded')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_category_display()} for {self.prisoner} on {self.record_date}"


# ============ INCIDENT REPORT ============

class IncidentReport(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    date_occurred = models.DateTimeField()
    location = models.CharField(max_length=100)
    involved_prisoners = models.ManyToManyField(Prisoner, related_name='incidents', blank=True)
    involved_staff = models.TextField(blank=True)
    actions_taken = models.TextField()
    follow_up_required = models.BooleanField(default=False)
    follow_up_notes = models.TextField(blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_incidents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.get_severity_display()} ({self.date_occurred.strftime('%Y-%m-%d %H:%M')})"


# ============ PRISONER ITEM ============

class PrisonerItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('money', 'Money'),
        ('clothing', 'Clothing'),
        ('personal_belonging', 'Personal Belonging'),
        ('other', 'Other'),
    ]
    CURRENCY_CHOICES = [
        ('MWK', 'Malawi Kwacha (MWK)'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=50, choices=ITEM_TYPE_CHOICES)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1, blank=True, null=True,
                                           help_text="Quantity for non-monetary items. Leave blank for money.")
    initial_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True,
                                         help_text="Initial amount for money. Leave blank for other items.")
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True,
                                         help_text="Current amount for money. Leave blank for other items.")
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default='MWK')
    date_received = models.DateField(default=timezone.now)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_prisoner_items')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_collected = models.BooleanField(default=False, help_text="Indicates if the item has been collected/reclaimed by the prisoner or their representative.")

    class Meta:
        verbose_name = "Prisoner Item"
        verbose_name_plural = "Prisoner Items"
        ordering = ['-date_received', 'item_type']

    def __str__(self):
        status = " (Collected)" if self.is_collected else ""
        if self.item_type == 'money':
            return f"{self.prisoner.full_name} - Money ({self.currency} {self.current_amount}){status}"
        return f"{self.prisoner.full_name} - {self.get_item_type_display()}: {self.description} (x{self.quantity}){status}"

    def clean(self):
        if self.item_type == 'money':
            if self.quantity is not None and self.quantity != 1:
                raise ValidationError({'quantity': 'Quantity must be 1 or blank for money items.'})
            if self.initial_amount is None or self.initial_amount < 0:
                raise ValidationError({'initial_amount': 'Initial amount is required and must be non-negative for money items.'})
        else:
            if self.initial_amount is not None and self.initial_amount != 0:
                raise ValidationError({'initial_amount': 'Initial amount must be 0 or blank for non-money items.'})
            if self.current_amount is not None and self.current_amount != 0:
                raise ValidationError({'current_amount': 'Current amount must be 0 or blank for non-money items.'})
            if self.quantity is None or self.quantity < 1:
                raise ValidationError({'quantity': 'Quantity is required and must be at least 1 for non-money items.'})
        super().clean()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        if is_new and self.item_type == 'money':
            self.current_amount = self.initial_amount
        super().save(*args, **kwargs)


# ============ PRISONER ITEM TRANSACTION ============

class PrisonerItemTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]

    item = models.ForeignKey(PrisonerItem, on_delete=models.CASCADE, related_name='transactions',
                             limit_choices_to={'item_type': 'money'})
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    transaction_date = models.DateTimeField(default=timezone.now)
    transacted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='item_transactions')
    reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Prisoner Item Transaction"
        verbose_name_plural = "Prisoner Item Transactions"
        ordering = ['-transaction_date']

    def clean(self):
        if self.transaction_type == 'withdrawal':
            if self.amount > self.item.current_amount:
                raise ValidationError({'amount': f'Withdrawal amount ({self.amount} {self.item.currency}) exceeds current balance ({self.item.current_amount} {self.item.currency}).'})
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk is None:
            if self.transaction_type == 'deposit':
                self.item.current_amount += self.amount
            elif self.transaction_type == 'withdrawal':
                self.item.current_amount -= self.amount
            self.item.save()
        super().save(*args, **kwargs)


# ============ BIOMETRIC / FINGERPRINT MODELS ============

class FingerprintDevice(models.Model):
    """Manage fingerprint scanner devices"""
    DEVICE_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
        ('offline', 'Offline'),
    ]

    DEVICE_TYPE_CHOICES = [
        ('integrated', 'Integrated (Laptop)'),
        ('usb', 'USB Scanner'),
        ('mobile', 'Mobile Scanner'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES, default='integrated')
    serial_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=DEVICE_STATUS_CHOICES, default='active')
    prison_station = models.ForeignKey(
        PrisonStation,
        on_delete=models.CASCADE,
        related_name='fingerprint_devices'
    )
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Fingerprint Device"
        verbose_name_plural = "Fingerprint Devices"
        ordering = ['prison_station', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()}) - {self.status}"


class FingerprintMatch(models.Model):
    """Track fingerprint matching history for auditing"""
    MATCH_STATUS_CHOICES = [
        ('exact', 'Exact Match'),
        ('probable', 'Probable Match'),
        ('potential', 'Potential Match'),
        ('no_match', 'No Match'),
        ('error', 'Match Error'),
    ]

    searched_prisoner = models.ForeignKey(
        Prisoner,
        on_delete=models.CASCADE,
        related_name='searched_fingerprints',
        null=True,
        blank=True,
        help_text="The prisoner whose fingerprint was used for search (null for unknown)"
    )
    matched_prisoner = models.ForeignKey(
        Prisoner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_fingerprints'
    )
    match_score = models.FloatField(help_text="Match confidence score 0-100")
    match_status = models.CharField(max_length=20, choices=MATCH_STATUS_CHOICES)
    search_timestamp = models.DateTimeField(auto_now_add=True)
    searched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    search_ip = models.GenericIPAddressField(blank=True, null=True)
    match_details = models.TextField(blank=True)

    class Meta:
        verbose_name = "Fingerprint Match"
        verbose_name_plural = "Fingerprint Matches"
        ordering = ['-search_timestamp']
        indexes = [
            models.Index(fields=['searched_prisoner', '-search_timestamp']),
            models.Index(fields=['matched_prisoner', '-search_timestamp']),
            models.Index(fields=['match_status']),
        ]

    def __str__(self):
        status = "Matched" if self.matched_prisoner else "No Match"
        return f"{self.searched_prisoner or 'Unknown'} - {status} ({self.match_score:.1f}%)"


class FingerprintAuditLog(models.Model):
    """Detailed audit log for fingerprint operations"""
    OPERATION_CHOICES = [
        ('capture', 'Fingerprint Capture'),
        ('verify', 'Identity Verification'),
        ('search', 'Fingerprint Search'),
        ('match', 'Fingerprint Match'),
        ('link', 'Identity Link'),
        ('unlink', 'Identity Unlink'),
        ('delete', 'Fingerprint Delete'),
        ('update', 'Fingerprint Update'),
    ]

    prisoner = models.ForeignKey(
        Prisoner,
        on_delete=models.CASCADE,
        related_name='fingerprint_audits'
    )
    operation = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = "Fingerprint Audit Log"
        verbose_name_plural = "Fingerprint Audit Logs"
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['prisoner', '-performed_at']),
            models.Index(fields=['operation', '-performed_at']),
        ]

    def __str__(self):
        return f"{self.prisoner} - {self.get_operation_display()} at {self.performed_at}"


# ============ RATION MANAGEMENT MODELS ============

class RationItem(models.Model):
    UNIT_CHOICES = [
        ('kg', 'Kilograms (kg)'),
        ('bags', 'Bags'),
        ('pieces', 'Pieces'),
        ('liters', 'Liters (L)'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100, unique=True, help_text="e.g., Peas, Cabbages, Beef, Flour")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='kg')
    current_stock_kg = models.DecimalField(
        max_digits=10, decimal_places=3, default=0.000,
        help_text="Current stock in Kilograms (kg)"
    )
    low_stock_threshold_kg = models.DecimalField(
        max_digits=10, decimal_places=3, default=50.000,
        help_text="Threshold in kg to trigger a low stock alert"
    )
    daily_consumption_per_prisoner_kg = models.DecimalField(
        max_digits=10, decimal_places=4, default=0.500,
        help_text="Daily consumption per prisoner in kg (used for automatic calculations)"
    )
    estimated_days_remaining = models.PositiveIntegerField(
        default=0,
        help_text="Estimated days ration will last based on current stock and prisoner count"
    )
    last_stock_update = models.DateTimeField(auto_now=True)
    last_consumption_date = models.DateField(blank=True, null=True)
    prison_station = models.ForeignKey(
        PrisonStation,
        on_delete=models.CASCADE,
        related_name='ration_items'
    )
    is_active = models.BooleanField(default=True, help_text="Whether this ration item is currently in use")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ration Item"
        verbose_name_plural = "Ration Items"
        unique_together = ('name', 'prison_station')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.prison_station.name})"

    @property
    def is_low_stock(self):
        return self.current_stock_kg < self.low_stock_threshold_kg

    def get_current_prisoner_count(self):
        """Get current number of prisoners for this station"""
        from .models import Prisoner
        return Prisoner.objects.filter(
            prison_station=self.prison_station,
            is_active=True
        ).count()

    def calculate_estimated_days(self):
        """Calculate estimated days remaining based on current stock and prisoner count"""
        if self.current_stock_kg <= 0 or self.daily_consumption_per_prisoner_kg <= 0:
            return 0

        prisoner_count = self.get_current_prisoner_count()
        if prisoner_count == 0:
            return 0

        daily_total_consumption = self.daily_consumption_per_prisoner_kg * prisoner_count
        if daily_total_consumption <= 0:
            return 0

        days_remaining = self.current_stock_kg / daily_total_consumption
        return int(days_remaining)

    def update_estimated_days(self):
        """Update the estimated days remaining field"""
        self.estimated_days_remaining = self.calculate_estimated_days()
        self.save(update_fields=['estimated_days_remaining', 'last_stock_update'])

    def record_daily_consumption(self, auto=True):
        """
        Record daily consumption based on current prisoner count.
        If auto=True, uses daily_consumption_per_prisoner_kg * prisoner_count
        If auto=False, requires manual quantity entry
        """
        prisoner_count = self.get_current_prisoner_count()
        if prisoner_count == 0:
            return None

        if auto:
            quantity_used = self.daily_consumption_per_prisoner_kg * prisoner_count
        else:
            quantity_used = 0

        consumption = RationConsumption.objects.create(
            item=self,
            consumption_date=timezone.now().date(),
            quantity_used_kg=quantity_used,
            num_prisoners_fed=prisoner_count,
            is_auto_calculated=auto
        )

        self.current_stock_kg -= quantity_used
        self.last_consumption_date = timezone.now().date()
        self.save(update_fields=['current_stock_kg', 'last_consumption_date', 'last_stock_update'])
        self.update_estimated_days()

        return consumption


class RationConsumption(models.Model):
    item = models.ForeignKey(RationItem, on_delete=models.CASCADE, related_name='consumptions')
    consumption_date = models.DateField(default=timezone.now)
    quantity_used_kg = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantity consumed in Kilograms (kg)",
        validators=[MinValueValidator(0.001)]
    )
    num_prisoners_fed = models.PositiveIntegerField(
        help_text="Number of prisoners (including children) fed with this ration on this day"
    )
    is_auto_calculated = models.BooleanField(
        default=False,
        help_text="Whether this consumption was automatically calculated based on prisoner count"
    )
    consumed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rations_consumed')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ration Consumption"
        verbose_name_plural = "Ration Consumptions"
        ordering = ['-consumption_date', 'item__name']

    def clean(self):
        if self.item and self.quantity_used_kg is not None:
            if self.item.current_stock_kg is None:
                raise ValidationError(
                    {'quantity_used_kg': f"Current stock for {self.item.name} is not set (None). Cannot record consumption."}
                )
            if self.quantity_used_kg > self.item.current_stock_kg:
                raise ValidationError(
                    {'quantity_used_kg': f"Consumption amount ({self.quantity_used_kg} kg) exceeds current stock ({self.item.current_stock_kg} kg) for {self.item.name}."}
                )
        super().clean()

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.item and self.quantity_used_kg:
                self.item.current_stock_kg -= self.quantity_used_kg
                self.item.last_consumption_date = self.consumption_date
                self.item.save(update_fields=['current_stock_kg', 'last_consumption_date', 'last_stock_update'])
                self.item.update_estimated_days()
        super().save(*args, **kwargs)


class RationProcurement(models.Model):
    item = models.ForeignKey(RationItem, on_delete=models.CASCADE, related_name='procurements')
    procurement_date = models.DateField(default=timezone.now)
    quantity_procured_kg = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantity procured in Kilograms (kg)",
        validators=[MinValueValidator(0.001)]
    )
    procured_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rations_procured')
    supplier = models.CharField(max_length=200, blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ration Procurement"
        verbose_name_plural = "Ration Procurements"
        ordering = ['-procurement_date', 'item__name']

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.item and self.quantity_procured_kg:
                self.item.current_stock_kg += self.quantity_procured_kg
                self.item.save(update_fields=['current_stock_kg', 'last_stock_update'])
                self.item.update_estimated_days()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Procured {self.quantity_procured_kg}kg of {self.item.name} on {self.procurement_date}"


# ============ NOTIFICATION ============

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('medical_checkup', 'Medical Checkup Reminder'),
        ('near_release', 'Prisoner Near Release'),
        ('new_admission', 'New Prisoner Admission'),
        ('general', 'General Notification'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    target_users = models.ManyToManyField(User, related_name='notifications', blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='read_notifications')
    action_required = models.BooleanField(default=False)
    action_url = models.CharField(max_length=255, blank=True, null=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.get_notification_type_display()}"

    def mark_as_read(self, user):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.read_by = user
            self.save(update_fields=['is_read', 'read_at', 'read_by'])

    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


# ============ AUDIT TRAIL MODELS ============

class AuditTrail(models.Model):
    """Comprehensive audit trail for all system actions"""

    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('RELEASE', 'Release'),
        ('TRANSFER', 'Transfer'),
        ('SENTENCE_CHANGE', 'Sentence Change'),
        ('DATE_CHANGE', 'Date Change'),
        ('PERMISSION_CHANGE', 'Permission Change'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('FORWARD', 'Forward'),
        ('IMPORT', 'Import'),
        ('EXPORT', 'Export'),
    ]

    SEVERITY_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_trails'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='info')
    prison_station = models.ForeignKey(
        PrisonStation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_trails'
    )
    description = models.TextField(blank=True)
    request_path = models.CharField(max_length=200, blank=True)
    session_id = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action']),
            models.Index(fields=['severity']),
        ]

    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"

    @property
    def is_sensitive(self):
        sensitive_actions = ['DATE_CHANGE', 'SENTENCE_CHANGE', 'RELEASE', 'PERMISSION_CHANGE']
        return self.action in sensitive_actions


class PrisonerAuditHistory(models.Model):
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='audit_history')
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='prisoner_audit_changes'
    )
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    change_reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['prisoner', '-changed_at']),
        ]

    def __str__(self):
        return f"{self.prisoner.prisoner_number} - {self.field_name} - {self.changed_at}"


class ReleaseAuditLog(models.Model):
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='release_audit_logs')
    action = models.CharField(max_length=20)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='release_audit_actions'
    )
    original_release_date = models.DateField(null=True, blank=True)
    modified_release_date = models.DateField(null=True, blank=True)
    original_sentence = models.FloatField(null=True, blank=True)
    modified_sentence = models.FloatField(null=True, blank=True)
    review_role = models.CharField(max_length=30, blank=True)
    approval_status = models.CharField(max_length=20, blank=True)
    change_reason = models.TextField(blank=True)
    risk_flags = models.JSONField(default=dict, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['prisoner', '-performed_at']),
        ]

    def __str__(self):
        return f"{self.prisoner.prisoner_number} - {self.action} - {self.performed_at}"


class SentryAlert(models.Model):
    ALERT_TYPES = [
        ('date_manipulation', 'Date Manipulation'),
        ('sentence_reduction', 'Unexplained Sentence Reduction'),
        ('early_release', 'Early Release Detected'),
        ('unauthorized_access', 'Unauthorized Access'),
        ('multiple_changes', 'Multiple Changes in Short Period'),
        ('off_hours_access', 'Off-hours Access'),
        ('foreign_ip', 'Foreign IP Address'),
        ('privilege_escalation', 'Privilege Escalation'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    title = models.CharField(max_length=200)
    description = models.TextField()
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, null=True, blank=True, related_name='sentry_alerts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sentry_alerts')
    audit_trail = models.ForeignKey(AuditTrail, on_delete=models.SET_NULL, null=True, blank=True, related_name='sentry_alerts')
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_sentry_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['alert_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['is_resolved']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.severity} - {self.detected_at}"

    def resolve(self, user, notes=""):
        self.is_resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()