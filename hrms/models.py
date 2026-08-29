from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import date, timedelta
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

# Import models from accounts app to use the unified models
from accounts.models import CustomUser, Region, PrisonStation

# --- Helper Functions ---

def calculate_end_date_excluding_weekends(start_date, leave_days):
    """
    Calculates the leave end date by adding the specified number of leave days,
    excluding Saturdays and Sundays.

    Args:
        start_date (date): The date when the leave starts.
        leave_days (int): The total number of leave days requested.

    Returns:
        date: The calculated end date of the leave.
    """
    # Ensure a positive number of leave days
    if leave_days < 0:
        raise ValueError("leave_days cannot be negative.")

    # Initialize the current date to the start date
    current_date = start_date
    days_counted = 0

    while days_counted < leave_days:
        # Check if the current day is a weekday (Monday is 0, Sunday is 6)
        if current_date.weekday() < 5:
            days_counted += 1
        current_date += timedelta(days=1)

    # The loop adds an extra day, so subtract one to get the correct end date.
    return current_date - timedelta(days=1)


def calculate_end_date_including_weekends(start_date, leave_days):
    """
    Calculates the leave end date by adding the specified number of leave days,
    including Saturdays and Sundays (for maternity leave).

    Args:
        start_date (date): The date when the leave starts.
        leave_days (int): The total number of leave days requested.

    Returns:
        date: The calculated end date of the leave.
    """
    # Ensure a positive number of leave days
    if leave_days < 0:
        raise ValueError("leave_days cannot be negative.")

    # For maternity leave, we simply add the days including weekends
    # Subtract 1 because leave days are counted as inclusive of start date
    end_date = start_date + timedelta(days=leave_days - 1)
    return end_date


# --- Core Models ---

class Rank(models.Model):
    """
    Represents the different ranks within the prison department.
    """
    RANK_CHOICES = (
        ('watchman', _('Watchman')),
        ('messenger', _('Messenger')),
        ('recruit', _('Recruit')),
        ('warder', _('Warder')),
        ('sergeant', _('Sergeant')),
        ('gaoler', _('Gaoler')),
        ('inspector', _('Inspector')),
        ('assistant_superintendent', _('Assistant Superintendent')),
        ('superintendent', _('Superintendent')),
        ('senior_superintendent', _('Senior Superintendent')),
        ('assistant_commissioner', _('Assistant Commissioner of Prison')),
        ('deputy_commissioner', _('Deputy Commissioner of Prison')),
        ('commissioner', _('Commissioner')),
        ('commissioner_general', _('Commissioner General')),
    )
    name = models.CharField(max_length=50, choices=RANK_CHOICES, unique=True, verbose_name=_("Rank Name"))
    leave_days_annual = models.IntegerField(default=24, verbose_name=_("Annual Leave Days"))

    class Meta:
        verbose_name = _("Rank")
        verbose_name_plural = _("Ranks")
        ordering = ['name']

    def __str__(self):
        # This ensures the human-readable name is displayed in dropdowns and admin
        return self.get_name_display()


class OfficeAssignment(models.Model):
    """
    Represents various office assignments or departments within the prison service.
    """
    OFFICE_CHOICES = (
        ('general_duties', _('General Duties')),
        ('medical_officer', _('Medical Officer')),
        ('female_in_charge', _('Female In-Charge')),
        ('administration', _('Administration')),
        ('accounts_office', _('Accounts Office')),
        ('research_office', _('Research Office')),
        ('gender', _('Gender Desk')),
        ('rehabilitation', _('Rehabilitation')),
        ('public_relations_office', _('Public Relations Office')),
        ('chaplaincy', _('Chaplaincy')),
        ('secretary', _('Secretary')),
        ('staff_officer', _('Staff Officer')),
        ('protocol', _('Protocol')),
        ('restorative_justice', _('Restorative Justice')),
        ('radio_communication', _('Radio Communication')),
        ('registry', _('Registry')),
        ('ict', _('ICT')),
        ('education', _('Education')),
        ('driver', _('Driver')),
        ('transport', _('Transport')),
        ('logistics', _('Logistics')),
        ('intelligence', _('Intelligence')),
        ('legal_office', _('Legal Office')),
        ('human_resources', _('Human Resources')),
        ('trainer/instructor', _('Trainer/Instructor')),
        ('disciplinary', _('Disciplinary')),
        ('procurement', _('Procurement')),
        ('audit', _('Audit')),
        ('stores', _('Stores')),
        ('gatekeeper', _('Gatekeeper')),
        ('station_officer', _('Station Officer')),
        ('station_hr', _('Station HR')),
        ('regional_commanding_officer', _('Regional Commanding Officer')),
        ('regional_headquarters_officer', _('Regional Headquarters Officer')),
        ('regional_hr', _('Regional HR')),
        ('commissioner_administration_and_human_resource', _('Commissioner of Admin')),
        ('commissioner_rehabilitation', _('Commissioner of Rehab')),
        ('commissioner_operations', _('Commissioner of Ops')),
        ('commissioner_training_school', _('Commissioner of Training School')),
        ('commissioner_correctional_services', _('Commissioner of Correctional Services')),
        ('director_of_farms', _('Director of Farms')),
        ('national_hr', _('National HR')),
        ('station_officer_in_charge', _('Station Officer (SO)')),
        ('general_duties_officer', _('General Duties Officer (GDO)')),
        ("disciplinary_officer", _('Disciplinary Officer (DO)')),
        ('messenger', _('Messenger')),
        ('watchman', _('Watchman')),
        ('farms', _('Farms')),
        ('finance_officer', _('Finance Officer')),
        ('male_in_charge',_('Male In-Charge')),
        ('hiv/aids_coordinator', _('HIV/AIDS Coordinator')),
        ('htc', _('HTC')), # Changed duplicated key
        ('mental_health_officer', _('Mental Health Officer')),
        ('youth_officer', _('Youth Officer')),
        ('commandant', _('Commandant')),
        ('deputy_commandant', _('Deputy Commandant')),
        ('o/c_junior_training_school', _('Officer In-Charge of Junior Training School')),
        ('o/c_advance_training_school', _('Officer In-Charge of Advance Training School')),
        ('field_officer', _('Field Officer')),
        ('reception_officer', _('Reception Officer')),
        ('nutrition_officer', _('Nutritionist')),
        ('welfare_officer', _('Welfare Officer')),
        ('plumbing_officer', _('Plumbing Officer')),
        ('electrician_officer', _('Electrician Officer')),
        ('mechanical_officer', _('Mechanical Officer')),
        ('welder_officer', _('Welder Officer')),
        ('carpentry_officer', _('Carpentry Officer')),
    )
    name = models.CharField(max_length=100, choices=OFFICE_CHOICES, unique=True, verbose_name=_("Office Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Office Assignment")
        verbose_name_plural = _("Office Assignments")
        ordering = ['name']

    def __str__(self):
        return self.get_name_display()


class Officer(models.Model):
    """
    Represents a prison officer with their personal, employment, and other details.
    """
    # Personal Details
    officer_picture = models.ImageField(upload_to='officer_pictures/', blank=True, null=True, verbose_name=_("Officer Picture"))
    service_number = models.CharField(max_length=50, unique=True, verbose_name=_("Service Number"), help_text=_("Unique official service number."))
    employment_number = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name=_("Employment Number"), help_text=_("Internal government employment number."))
    first_name = models.CharField(max_length=100, verbose_name=_("First Name"))
    middle_name = models.CharField(max_length=100, blank=True, verbose_name=_("Middle Name"))
    surname = models.CharField(max_length=100, verbose_name=_("Surname"))
    date_of_birth = models.DateField(verbose_name=_("Date of Birth"))
    date_joined_service = models.DateField(verbose_name=_("Date Joined Service"))
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='officer_profile', verbose_name=_("Associated User Account"))
    GENDER_CHOICES = (
        ('male', _('Male')),
        ('female', _('Female')),

    )
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name=_("Gender"))

    STATUS_CHOICES = (
        ('active', _('Active')),
        ('on_leave', _('On Leave')),
        ('suspended', _('Suspended')),
        ('interdicted', _('Interdicted')),
        ('retired', _('Retired')),
        ('resigned', _('Resigned')),
        ('deceased', _('Deceased')),

    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name=_("Current Status"))

    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True, related_name='officers', verbose_name=_("Current Rank"))
    current_office_assignment = models.ForeignKey(OfficeAssignment, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_officers', verbose_name=_("Current Office Assignment"))
    grade = models.CharField(max_length=5, blank= True, verbose_name=_("Grade"))

    # Contact Information
    contact_number = models.CharField(max_length=20, blank=True, verbose_name=_("Contact Number"))
    email = models.EmailField(max_length=255, unique=True, blank=True, null=True, verbose_name=_("Official Email"))

    # Location Information
    village = models.CharField(max_length=100, blank=True, verbose_name=_("Village"))
    traditional_authority = models.CharField(max_length=100, blank=True, verbose_name=_("Traditional Authority (T/A)"))
    district = models.CharField(max_length=100, blank=True, verbose_name=_("District"))
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name='officers', verbose_name=_("Assigned Region"))
    prison_station = models.ForeignKey(PrisonStation, on_delete=models.SET_NULL, null=True, blank=True, related_name='officers', verbose_name=_("Assigned Prison Station"))

    # Family Information
    MARITAL_STATUS_CHOICES = (
        ('single', _('Single')),
        ('married', _('Married')),
        ('divorced', _('Divorced')),
        ('widowed', _('Widowed')),
    )
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True, verbose_name=_("Marital Status"))
    spouse_name = models.CharField(max_length=200, blank=True, verbose_name=_("Spouse Name"))
    number_of_children = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)], verbose_name=_("Number of Children"))

    # Next of Kin
    next_of_kin_name = models.CharField(max_length=200, blank=True, verbose_name=_("Next of Kin Name"))
    next_of_kin_relationship = models.CharField(max_length=100, blank=True, verbose_name=_("Next of Kin Relationship"))
    next_of_kin_location = models.CharField(max_length=255, blank=True, verbose_name=_("Next of Kin Location"))
    next_of_kin_contact = models.CharField(max_length=20, blank=True, verbose_name=_("Next of Kin Contact"))

    # Skills and Languages
    notable_skills = models.TextField(blank=True, verbose_name=_("Notable Skills"))
    languages_spoken = models.TextField(blank=True, verbose_name=_("Languages Spoken"))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Officer")
        verbose_name_plural = _("Officers")
        ordering = ['surname', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.surname} ({self.service_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.middle_name} {self.surname}".strip()

    @property
    def age(self):
        """Calculates the current age of the officer in years."""
        if self.date_of_birth:
            today = date.today()
            # Calculate years, then adjust if birthday hasn't occurred yet this year
            years = today.year - self.date_of_birth.year
            if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
                years -= 1
            return max(0, years) # Ensure age is not negative
        return None # Return None if date_of_birth is not set

    @property
    def retirement_date(self):
        """Calculates the estimated retirement date (60 years after birth date)."""
        if self.date_of_birth:
            return self.date_of_birth.replace(year=self.date_of_birth.year + 60)
        return None

    @property
    def period_of_service(self):
        """Calculates the period of service in years."""
        if self.date_joined_service:
            today = date.today()
            # Calculate years, then adjust if anniversary hasn't occurred yet this year
            years = today.year - self.date_joined_service.year
            if (today.month, today.day) < (self.date_joined_service.month, self.date_joined_service.day):
                years -= 1
            return max(0, years) # Ensure it's not negative
        return 0

    @property
    def months_until_retirement(self):
        """Calculates months until retirement (assuming retirement at 60 years old)."""
        if self.date_of_birth:
            retirement_date = self.retirement_date # Use the newly defined retirement_date property
            today = date.today()

            if not retirement_date or today >= retirement_date:
                return 0 # Already retired or retirement date cannot be calculated

            # Calculate total months difference
            delta_months = (retirement_date.year - today.year) * 12 + (retirement_date.month - today.month)

            # Adjust if current day is after retirement day in the retirement month
            if today.day > retirement_date.day:
                delta_months -= 1

            return max(0, delta_months)
        return None


class Education(models.Model):
    """
    Records educational qualifications of an officer.
    """
    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='education', verbose_name=_("Officer"))
    institution = models.CharField(max_length=255, verbose_name=_("Institution"))
    qualification = models.CharField(max_length=255, verbose_name=_("Qualification"))
    year_obtained = models.IntegerField(validators=[MinValueValidator(1900), MaxValueValidator(date.today().year)], verbose_name=_("Year Obtained"))
    supporting_document = models.FileField(upload_to='education_documents/', blank=True, null=True, verbose_name=_("Supporting Document"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Education Qualification")
        verbose_name_plural = _("Education Qualifications")
        ordering = ['-year_obtained']

    def __str__(self):
        return f"{self.officer.full_name} - {self.qualification} ({self.year_obtained})"


class PromotionHistory(models.Model):
    """
    Records an officer's promotion history.
    """
    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='promotions', verbose_name=_("Officer"))
    previous_rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True, related_name='promoted_from', verbose_name=_("Previous Rank"))
    new_rank = models.ForeignKey(Rank, on_delete=models.CASCADE, related_name='promoted_to', verbose_name=_("New Rank"))
    promotion_date = models.DateField(default=timezone.now, verbose_name=_("Promotion Date"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Recorded By"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Promotion History")
        verbose_name_plural = _("Promotion Histories")
        ordering = ['-promotion_date']

    def __str__(self):
        return f"{self.officer.full_name} promoted to {self.new_rank.get_name_display()} on {self.promotion_date}"


class TransferHistory(models.Model):
    """
    Records an officer's transfer history between prison stations.
    """
    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='transfers', verbose_name=_("Officer"))
    previous_station = models.ForeignKey(PrisonStation, on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_from', verbose_name=_("Previous Station"))
    new_station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='transferred_to', verbose_name=_("New Station"))
    transfer_date = models.DateField(default=timezone.now, verbose_name=_("Transfer Date"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Recorded By"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Transfer History")
        verbose_name_plural = _("Transfer Histories")
        ordering = ['-transfer_date']

    def __str__(self):
        return f"{self.officer.full_name} transferred to {self.new_station.name} on {self.transfer_date}"


class LeaveType(models.Model):
    """
    Defines different types of leave available (e.g., Annual, Maternity, Study).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Leave Type Name"))
    is_maternity = models.BooleanField(default=False, verbose_name=_("Is Maternity Leave?"))
    is_study = models.BooleanField(default=False, verbose_name=_("Is Study Leave?"))
    default_days = models.IntegerField(null=True, blank=True, verbose_name=_("Default Days (if applicable)"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Leave Type")
        verbose_name_plural = _("Leave Types")
        ordering = ['name']

    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    """
    Records an officer's leave requests.
    """
    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='leave_requests', verbose_name=_("Officer"))
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='requests', verbose_name=_("Leave Type"))
    start_date = models.DateField(verbose_name=_("Start Date"))
    number_of_days = models.IntegerField(validators=[MinValueValidator(1)], verbose_name=_("Number of Days"))
    end_date = models.DateField(null=True, blank=True, verbose_name=_("End Date"))  # Auto-calculated
    supporting_document = models.FileField(upload_to='leave_documents/', blank=True, null=True, verbose_name=_("Supporting Document"))

    STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('cancelled', _('Cancelled')),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_("Status"))
    rejection_notes = models.TextField(blank=True, verbose_name=_("Rejection Notes"))
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Requested At"))
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leave_requests', verbose_name=_("Approved/Rejected By"))
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Approved/Rejected At"))

    class Meta:
        verbose_name = _("Leave Request")
        verbose_name_plural = _("Leave Requests")
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.officer.full_name} - {self.leave_type.name} ({self.status})"

    def save(self, *args, **kwargs):
        # Auto-calculate the end date based on the number of days and leave type
        if self.start_date and self.number_of_days:
            if self.leave_type.is_maternity:
                # For maternity leave, include weekends
                self.end_date = calculate_end_date_including_weekends(self.start_date, self.number_of_days)
            else:
                # For annual leave and other types, exclude weekends
                self.end_date = calculate_end_date_excluding_weekends(self.start_date, self.number_of_days)
        super().save(*args, **kwargs)


class AnnualLeaveBalance(models.Model):
    """
    Tracks an officer's annual leave balance for a given year.
    """
    officer = models.OneToOneField(Officer, on_delete=models.CASCADE, related_name='annual_leave_balance', verbose_name=_("Officer"))
    year = models.IntegerField(verbose_name=_("Year"))
    total_days_entitled = models.IntegerField(default=0, verbose_name=_("Total Days Entitled"))
    days_taken = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name=_("Days Taken"))
    last_reset_date = models.DateField(null=True, blank=True, verbose_name=_("Last Reset Date"))

    class Meta:
        verbose_name = _("Annual Leave Balance")
        verbose_name_plural = _("Annual Leave Balances")
        unique_together = ('officer', 'year')

    def __str__(self):
        return f"{self.officer.full_name} - {self.year} Leave Balance"

    @property
    def remaining_days(self):
        return self.total_days_entitled - self.days_taken


class OfficerDocument(models.Model):
    """
    Stores various official documents related to an officer (e.g., appointment letters, disciplinary records).
    """
    FILE_TYPE_CHOICES = (
        ('letter_of_appointment', _('Letter of Appointment')),
        ('academic_certificate', _('Academic Certificate')),
        ('id_card', _('ID Card')),
        ('disciplinary_case', _('Disciplinary Case Document')),
        ('transfer_order', _('Transfer Order')),
        ('promotion_letter', _('Promotion Letter')),
        ('marriage_certificate', _('Marriage Certificate')),
        ('loan_request', _('Loan Request')),
        ('submissions', _('Submissions')),
        )

    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='documents', verbose_name=_("Officer"))
    file_name = models.CharField(max_length=50, verbose_name=_("File Name"))
    file_number = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("File Number"))
    file_type = models.CharField(max_length=50, choices=FILE_TYPE_CHOICES, verbose_name=_("File Type"))
    document = models.FileField(upload_to='officer_documents/', verbose_name=_("Document File"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    response_notes = models.TextField(blank=True, verbose_name=_("Response Notes"))

    STATUS_CHOICES = (
        ('pending', _('Pending Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_("Status"))

    ACTION_TO_CHOICES = (
        ('national_commissioner', _('National Commissioner')),
        ('national_hr', _('National HR')),
        ('regional_commanding_officer', _('Regional Commanding Officer')),
        ('regional_headquarters_officer', _('Regional Headquarters Officer')),
        ('regional_hr', _('Regional HR')),
        ('officer_in_charge', _('Station Officer In-Charge')),
        ('station_officer', _('Station Officer')),
        ('station_hr', _('Station HR')),
        ('officer_self', _('Officer (Self)')),
        ('all', _('All Relevant Parties')),
    )
    action_to = models.CharField(max_length=50, choices=ACTION_TO_CHOICES, blank=True, null=True, verbose_name=_("Action Required By Role"))
    action_to_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents_for_action', verbose_name=_("Action Required By Specific User"))

    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_documents', verbose_name=_("Uploaded By"))
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Uploaded At"))
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_documents', verbose_name=_("Reviewed By"))
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Reviewed At"))
    response_notes = models.TextField(blank=True, verbose_name=_("Response Notes"))

    class Meta:
        verbose_name = _("Officer Document")
        verbose_name_plural = _("Officer Documents")
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.officer.full_name} - {self.file_name} ({self.get_status_display()})"


class PerformanceMetric(models.Model):
    """
    Defines different metrics for officer performance evaluation.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Metric Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active?"))

    class Meta:
        verbose_name = _("Performance Metric")
        verbose_name_plural = _("Performance Metrics")
        ordering = ['name']

    def __str__(self):
        return self.name


class OfficerPerformance(models.Model):
    """
    Records an officer's performance against specific metrics.
    """
    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='performance_records', verbose_name=_("Officer"))
    metric = models.ForeignKey(PerformanceMetric, on_delete=models.CASCADE, related_name='performance_entries', verbose_name=_("Metric"))
    date = models.DateField(default=timezone.now, verbose_name=_("Date of Record"))
    score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name=_("Score (0-100)"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Recorded By"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Officer Performance")
        verbose_name_plural = _("Officer Performance")
        ordering = ['-date', 'officer__surname']
        unique_together = ('officer', 'metric', 'date')

    def __str__(self):
        return f"{self.officer.full_name} - {self.metric.name} ({self.score})"


class Attendance(models.Model):
    """
    Records daily attendance for officers.
    """
    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='attendance_records', verbose_name=_("Officer"))
    date = models.DateField(default=timezone.now, verbose_name=_("Date"))
    ATTENDANCE_STATUS_CHOICES = [
        ('present', _('Present')),
        ('absent', _('Absent')),
        ('leave', _('On Leave')),
        ('sick', _('Sick Leave')),
        ('duty', _('On Duty')),
        ('suspended', _('Suspended')),
    ]
    
    SHIFT_CHOICES = [
        ('early_morning', _('Early Morning (6:00 AM - 12:00 PM)')),
        ('morning', _('Morning (7:30 AM - 4:30 PM)')),
        ('afternoon', _('Afternoon (12:00 PM - 6:00 PM)')),
        ('night', _('Night (6:00 PM - 6:00 AM)')),
    ]
    
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default='present', verbose_name=_("Status"))
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='morning', verbose_name=_("Shift"))
    check_in_time = models.TimeField(null=True, blank=True, verbose_name=_("Check In Time"))
    check_out_time = models.TimeField(null=True, blank=True, verbose_name=_("Check Out Time"))
    remarks = models.TextField(blank=True, verbose_name=_("Remarks"))
    marked_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Marked By"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        verbose_name = _("Attendance")
        verbose_name_plural = _("Attendance Records")
        ordering = ['-date', 'officer__surname', 'officer__first_name']
        unique_together = ['officer', 'date', 'shift']

    def __str__(self):
        return f"{self.officer.full_name} - {self.date}: {self.get_status_display()}"


class DisciplinaryCase(models.Model):
    """
    Records disciplinary cases against officers.
    """
    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='disciplinary_cases', verbose_name=_("Officer"))
    case_date = models.DateField(default=timezone.now, verbose_name=_("Case Date"))
    offense = models.CharField(max_length=255, verbose_name=_("Offense"))
    description = models.TextField(verbose_name=_("Description"))
    ACTION_TAKEN_CHOICES = (
        ('warning', _('Warning')),
        ('suspension', _('Suspension')),
        ('interdiction', _('Interdiction')),
        ('dismissal', _('Dismissal')),
        ('extra_duty', _('Extra duty')),
        ('less_pay', _('Less Pay')),
    )
    action_taken = models.CharField(max_length=50, choices=ACTION_TAKEN_CHOICES, blank=True, verbose_name=_("Action Taken"))
    action_date = models.DateField(null=True, blank=True, verbose_name=_("Action Date"))
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Recorded By"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Disciplinary Case")
        verbose_name_plural = _("Disciplinary Cases")
        ordering = ['-case_date']

    def __str__(self):
        return f"{self.officer.full_name} - {self.offense} ({self.case_date})"


class DisciplinaryCaseFile(models.Model):
    """
    Model to store file attachments for disciplinary cases.
    """
    disciplinary_case = models.ForeignKey(DisciplinaryCase, on_delete=models.CASCADE, related_name='files', verbose_name=_("Disciplinary Case"))
    file_name = models.CharField(max_length=255, verbose_name=_("File Name"))
    file = models.FileField(upload_to='disciplinary_case_files/', verbose_name=_("File"))
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Uploaded At"))
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Uploaded By"))
    
    class Meta:
        verbose_name = _("Disciplinary Case File")
        verbose_name_plural = _("Disciplinary Case Files")
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.file_name} - {self.disciplinary_case}"


class Notification(models.Model):
    """
    Model to store notifications for users.
    """
    NOTIFICATION_TYPE_CHOICES = (
        ('leave_request', _('Leave Request')),
        ('file_action', _('File Action')),
        ('disciplinary_action', _('Disciplinary Action')),
        ('promotion', _('Promotion')),
        ('transfer', _('Transfer')),
        ('system_alert', _('System Alert')),
        ('new_officer', _('New Officer Added')),
    )

    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hrms_notifications', verbose_name=_("Recipient"))
    sender = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_hrms_notifications', verbose_name=_("Sender"))
    message = models.TextField(verbose_name=_("Message"))
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES, verbose_name=_("Notification Type"))
    is_read = models.BooleanField(default=False, verbose_name=_("Is Read"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username} - {self.get_notification_type_display()}: {self.message[:50]}..."

    def get_absolute_url(self):
        # This method will return the URL to the related object if available,
        # or a generic notification detail page.
        if self.notification_type == 'leave_request' and self.content_object:
            return reverse('hrms:leave_request_detail', kwargs={'pk': self.content_object.pk})
        elif self.notification_type == 'file_action' and self.content_object:
            return reverse('hrms:officer_file_detail', kwargs={'pk': self.content_object.pk})
        elif self.notification_type == 'disciplinary_action' and self.content_object:
            return reverse('hrms:disciplinary_case_detail', kwargs={'pk': self.content_object.pk})
        elif self.notification_type == 'promotion' and self.content_object:
            return reverse('hrms:officer_detail', kwargs={'service_number': self.content_object.officer.service_number})
        elif self.notification_type == 'transfer' and self.content_object:
            return reverse('hrms:officer_detail', kwargs={'service_number': self.content_object.officer.service_number})
        elif self.notification_type == 'new_officer' and self.content_object:
            return reverse('hrms:officer_detail', kwargs={'service_number': self.content_object.service_number})
        # Fallback to a generic notification detail if no specific URL is found
        return reverse('hrms:notification_detail', kwargs={'pk': self.pk})


# ========== REDESIGNED TRAINING WING MODELS ==========

class TrainingIntake(models.Model):
    """
    Represents a training intake batch with custom intake number.
    Example: "7th Intake", "15th Intake"
    """
    intake_number = models.PositiveIntegerField(unique=True, verbose_name=_("Intake Number"))
    intake_suffix = models.CharField(max_length=10, choices=[
        ('st', 'st'), ('nd', 'nd'), ('rd', 'rd'), ('th', 'th'),
        ('custom', 'Custom')
    ], default='th', verbose_name=_("Intake Suffix"))
    custom_suffix = models.CharField(max_length=20, blank=True, verbose_name=_("Custom Suffix"))
    
    year = models.IntegerField(verbose_name=_("Start Year"))
    start_date = models.DateField(verbose_name=_("Intake Start Date"))
    pass_out_date = models.DateField(verbose_name=_("Pass Out / Graduation Date"))
    estimated_end_date = models.DateField(verbose_name=_("Estimated End Date"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    
    # Last officer number from previous intake (reference for generating new numbers)
    last_pass_out_number = models.PositiveIntegerField(null=True, blank=True, 
        help_text=_("Last service number from previous intake pass-out"))
    
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Training Intake")
        verbose_name_plural = _("Training Intakes")
        ordering = ['-year', 'intake_number']
        unique_together = ('intake_number', 'year')

    def get_display_name(self):
        if self.intake_suffix == 'custom' and self.custom_suffix:
            return f"{self.custom_suffix} Intake {self.year}"
        return f"{self.intake_number}{self.intake_suffix} Intake {self.year}"
    
    def get_ordinal(self, n):
        if 11 <= n % 100 <= 13:
            return 'th'
        return {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    
    def __str__(self):
        return self.get_display_name()



class TrainingCourse(models.Model):
    """
    Represents an individual training course/subject from the Correctional Officers' Basic Training Curriculum.
    Each subject is its own course with its own marks, assessments, and grading.
    """
    
    # Course Categories (formerly Modules)
    CATEGORY_CHOICES = (
        ('security_ops_1', _('Prison Security and Operations I')),
        ('security_ops_2', _('Prison Security and Operations II')),
        ('rehabilitation', _('Rehabilitation, Reformation and Prison Industry Programmes')),
        ('community_correction', _('Community Correction and Reintegration Programmes')),
        ('hr_admin', _('Human Resources and Administration Services')),
        ('health_wellness', _('Physical and Mental Health and Wellness')),
    )
    
    # Individual Courses - Each subject becomes a course
    COURSE_CHOICES = (
        # Module 1: Prison Security and Operations I
        ('history_organisation', _('History and Organisation of Prisons in Malawi')),
        ('criminal_justice_system', _('The Criminal Justice System and its Agencies in Malawi')),
        ('international_rules', _('International Rules and Regulations for the Management of Prisons')),
        ('prisons_acts', _('Malawi Prisons Acts and Subsidiary Legislations')),
        ('human_rights', _('Human Rights in Malawi Prisons – Juveniles, Women and Foreigners')),
        ('vulnerable_prisoners', _('Categories of Vulnerable Prisoners')),
        ('service_communication', _('Service Communication Skills')),
        ('emergency_crisis', _('Emergency and Crisis Intervention/Management')),
        ('ict_cybercrime', _('Use of ICT and Prevention of Cybercrimes in Prisons')),
        ('extremism_radicalisation', _('Preventing Extremism and Radicalisation in Prisons')),
        ('intelligence_gathering', _('Prison Intelligence Gathering')),
        ('foot_arms_drill', _('Foot and Arms Drill')),
        ('weapon_handling', _('Tactical and Lethal Weapon Handling')),
        
        # Module 2: Prison Security and Operations II
        ('prisoners_security', _('Prisoners Security, Supervision and Discipline')),
        ('dynamic_security', _('The Concept of Security in Prisons: Towards Dynamic Security')),
        ('reception_registration', _('Reception, Registration and Record Keeping for Prisoners')),
        ('classification_remission', _('Prisoners\' Classification and Remission')),
        ('conditional_release', _('Prisoners\' Conditional and Unconditional Release')),
        ('search_prohibited', _('Search and Prohibited Articles')),
        
        # Module 3: Rehabilitation, Reformation and Prison Industry Programmes
        ('crime_theories', _('Causes, Theories and Prevention of Crime and Delinquency')),
        ('psychological_sociological', _('Psychological and Sociological Issues in Prisons')),
        ('rehabilitation_programmes', _('Types of Rehabilitation and Reformation Programmes')),
        ('rehabilitation_malawi', _('Rehabilitation and Reformation in Malawi Prisons')),
        ('unit_management', _('Unit Management Model in Prisons')),
        ('prison_industry', _('Introduction to Prison Industry Activities')),
        
        # Module 4: Community Correction and Reintegration Programmes
        ('community_correction_intro', _('Introduction to the Concept of Community Correction')),
        ('reintegration_programmes', _('Post-Release Reintegration Programmes')),
        ('parole_probation', _('Introduction to Parole and Probation Services')),
        ('public_awareness', _('Building Public Awareness and Support')),
        
        # Module 5: Human Resources and Administration Services
        ('finance_administration', _('Introduction to Finance and Administrative Division of the MPS')),
        ('conditions_of_service', _('Malawi Prisons Service Conditions of Service')),
        ('integrity_ethics', _('Integrity, Ethics and Professionalism')),
        ('gender_policies', _('National Gender Policies and Prisons')),
        ('financial_literacy', _('Financial Literacy – Personal Income Management and Budgeting')),
        ('marriage_family', _('Marriage, Divorce and Family Relations')),
        
        # Module 6: Physical and Mental Health and Wellness
        ('infectious_diseases', _('Infectious Diseases in Prison Context')),
        ('hiv_aids', _('HIV and AIDS in Prisons')),
        ('first_aid', _('First Aid and Cardio-Pulmonary Resuscitation')),
        ('mental_health', _('Mental Health Issues and Awareness')),
        ('drug_alcohol', _('Drug and Alcohol Awareness')),
    )
    
    course_code = models.CharField(max_length=50, choices=COURSE_CHOICES, unique=True, verbose_name=_("Course Code"))
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, verbose_name=_("Course Category/Module"))
    name = models.CharField(max_length=200, verbose_name=_("Course Name"))
    description = models.TextField(blank=True, verbose_name=_("Course Description"))
    
    # Course configuration
    total_marks = models.IntegerField(default=100, verbose_name=_("Total Marks"))
    passing_mark = models.IntegerField(default=50, verbose_name=_("Passing Mark"))
    duration_hours = models.IntegerField(default=0, verbose_name=_("Duration (Hours)"))
    is_required = models.BooleanField(default=True, verbose_name=_("Required Course"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    
    # Sorting and display
    display_order = models.IntegerField(default=0, verbose_name=_("Display Order"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Training Course")
        verbose_name_plural = _("Training Courses")
        ordering = ['category', 'display_order', 'course_code']

    def __str__(self):
        return f"[{self.get_category_display_name()}] {self.name}"
    
    def get_category_display_name(self):
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)
    
    def save(self, *args, **kwargs):
        """Override save to set the name and category from course_code"""
        if not self.name or self._state.adding:
            # Get the display name from COURSE_CHOICES
            for code, display_name in self.COURSE_CHOICES:
                if code == self.course_code:
                    self.name = display_name
                    break
            
            # Set category based on course_code mapping
            if self.course_code in ['history_organisation', 'criminal_justice_system', 'international_rules', 
                                     'prisons_acts', 'human_rights', 'vulnerable_prisoners', 'service_communication',
                                     'emergency_crisis', 'ict_cybercrime', 'extremism_radicalisation', 
                                     'intelligence_gathering', 'foot_arms_drill', 'weapon_handling']:
                self.category = 'security_ops_1'
            elif self.course_code in ['prisoners_security', 'dynamic_security', 'reception_registration',
                                       'classification_remission', 'conditional_release', 'search_prohibited']:
                self.category = 'security_ops_2'
            elif self.course_code in ['crime_theories', 'psychological_sociological', 'rehabilitation_programmes',
                                       'rehabilitation_malawi', 'unit_management', 'prison_industry']:
                self.category = 'rehabilitation'
            elif self.course_code in ['community_correction_intro', 'reintegration_programmes',
                                       'parole_probation', 'public_awareness']:
                self.category = 'community_correction'
            elif self.course_code in ['finance_administration', 'conditions_of_service', 'integrity_ethics',
                                       'gender_policies', 'financial_literacy', 'marriage_family']:
                self.category = 'hr_admin'
            elif self.course_code in ['infectious_diseases', 'hiv_aids', 'first_aid', 'mental_health', 'drug_alcohol']:
                self.category = 'health_wellness'
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_courses_by_category(cls):
        """Return courses grouped by category"""
        result = {}
        for category in cls.CATEGORY_CHOICES:
            result[category[0]] = {
                'name': category[1],
                'courses': cls.objects.filter(category=category[0], is_active=True).order_by('display_order')
            }
        return result
    
    @classmethod
    def get_all_courses_list(cls):
        """Return flat list of all courses with their codes"""
        return [{'code': code, 'name': name} for code, name in cls.COURSE_CHOICES]


class Recruit(models.Model):
    """
    Represents a prison recruit undergoing training.
    """
    
    RECRUIT_TYPE_CHOICES = (
        ('recruit', _('Recruit')),
        ('officer', _('Officer')),
        ('staff', _('Staff')),
    )
    
    STATUS_CHOICES = (
        ('enrolled', _('Enrolled')),
        ('in_training', _('In Training')),
        ('graduated', _('Graduated')),
        ('dismissed', _('Dismissed')),
        ('withdrawn', _('Withdrawn')),
    )

    # Fallback first service number when no previous intake or officer exists.
    DEFAULT_SERVICE_NUMBER_START = 10000
    
    # Automatic service number (assigned during pass-out/graduation)
    service_number = models.CharField(max_length=50, unique=True, blank=True, null=True, 
        verbose_name=_("Service Number"), help_text=_("Auto-assigned after graduation"))
    
    # Temporary ID during training
    training_id = models.CharField(max_length=50, unique=True, blank=True, null=True,
        verbose_name=_("Training ID"), help_text=_("Temporary ID used during training (e.g., R-2024-001)"))
    
    intake = models.ForeignKey(TrainingIntake, on_delete=models.CASCADE, related_name='recruits')
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    surname = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=Officer.GENDER_CHOICES)
    
    recruit_type = models.CharField(max_length=20, choices=RECRUIT_TYPE_CHOICES, default='recruit')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='enrolled')

    
    contact_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    home_district = models.CharField(max_length=100, blank=True)

    next_of_kin = models.CharField(max_length=100, blank=True)
    next_of_kin_contact = models.CharField(max_length=20, blank=True)
    next_of_kin_relationship = models.CharField(max_length=50, blank=True)
    next_of_kin_address = models.TextField(blank=True)
    
    # Performance tracking
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    final_grade = models.CharField(max_length=2, blank=True)
    rank_in_class = models.IntegerField(null=True, blank=True, verbose_name=_("Rank in Class"))
    total_recruits_in_class = models.IntegerField(null=True, blank=True)
    
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    graduated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Recruit")
        verbose_name_plural = _("Recruits")
        ordering = ['intake', 'surname', 'first_name']

    @property
    def age(self):
        """Calculate current age from date of birth"""
        today = date.today()
        if self.date_of_birth:
            age = today.year - self.date_of_birth.year
            # Adjust age if birthday hasn't occurred yet this year
            if today.month < self.date_of_birth.month or (today.month == self.date_of_birth.month and today.day < self.date_of_birth.day):
                age -= 1
            return age
        return None

    def __str__(self):
        if self.service_number:
            return f"{self.full_name} ({self.service_number})"
        return f"{self.full_name} (Training: {self.training_id or 'No ID'})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.middle_name} {self.surname}".strip()
    
    def generate_training_id(self):
        """
        Generate training ID in format: R-{intake_number}/{recruit_position}
        Example: R-022/165
        """
        if self.training_id:
            return self.training_id

        # Get the intake number (zero-padded to 3 digits)
        intake_num = str(self.intake.intake_number).zfill(3)
        prefix = f"R-{intake_num}/"

        # Continue from the highest position already used in this intake so that
        # withdrawn or deleted recruits never cause a duplicate training id.
        used_positions = [
            int(existing.rsplit('/', 1)[-1])
            for existing in self.intake.recruits.filter(
                training_id__startswith=prefix
            ).values_list('training_id', flat=True)
            if existing and existing.rsplit('/', 1)[-1].isdigit()
        ]
        next_position = max(used_positions, default=0) + 1

        self.training_id = f"{prefix}{str(next_position).zfill(3)}"
        return self.training_id
    
    def auto_create_course_marks(self):
        """
        Auto-create RecruitMark records for all active required courses so the
        recruit starts with a full mark sheet.
        """
        active_courses = TrainingCourse.objects.filter(is_active=True, is_required=True)
        existing_course_ids = set(self.marks.values_list('course_id', flat=True))

        new_marks = [
            RecruitMark(
                recruit=self,
                course=course,
                obtained_marks=0,
                exam_date=self.intake.pass_out_date,
            )
            for course in active_courses
            if course.pk not in existing_course_ids
        ]

        # bulk_create skips RecruitMark.save(), so results are recalculated once
        # below instead of once per mark.
        RecruitMark.objects.bulk_create(new_marks)

        if new_marks:
            self.calculate_final_results()

        return len(new_marks)
    
    def calculate_final_results(self):
        """Calculate final scores, grade, and ranking"""
        marks = self.marks.select_related('course').all()
        if not marks:
            return None
        
        total_obtained = 0
        total_possible = 0
        course_results = []
        
        for mark in marks:
            course_total = mark.course.total_marks
            total_obtained += mark.obtained_marks
            total_possible += course_total
            course_results.append({
                'course_name': mark.course.name,
                'course_code': mark.course.course_code,
                'obtained': mark.obtained_marks,
                'total': course_total,
                'percentage': (mark.obtained_marks / course_total) * 100 if course_total > 0 else 0
            })
        
        if total_possible == 0:
            return None
        
        overall_percentage = (total_obtained / total_possible) * 100
        self.overall_score = round(overall_percentage, 2)
        self.final_grade = self._get_grade(overall_percentage)
        super().save(update_fields=['overall_score', 'final_grade', 'updated_at'])
        
        return {
            'overall_percentage': overall_percentage,
            'grade': self.final_grade,
            'total_obtained': total_obtained,
            'total_possible': total_possible,
            'course_results': course_results
        }
    
    def _get_grade(self, percentage):
        if percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B'
        elif percentage >= 60:
            return 'C'
        elif percentage >= 50:
            return 'D'
        else:
            return 'F'
    
    def assign_service_number(self, base_number=None):
        """Assign permanent service number based on class ranking"""
        if self.service_number:
            return self.service_number  # Already assigned
        
        # Get all graduates from this intake, ordered by rank (highest score first)
        graduates = Recruit.objects.filter(
            intake=self.intake,
            status='graduated'
        ).order_by('-overall_score', 'surname', 'first_name')
        
        # Find the last pass-out officer number from previous intake
        previous_intake = TrainingIntake.objects.filter(
            year__lt=self.intake.year
        ).order_by('-year', '-intake_number').first()
        
        if previous_intake and previous_intake.last_pass_out_number:
            start_number = previous_intake.last_pass_out_number + 1
        else:
            # Try to get last officer from Officer model
            last_officer = Officer.objects.filter(
                service_number__regex=r'^\d+$'
            ).order_by('-service_number').first()
            if last_officer:
                start_number = int(last_officer.service_number) + 1
            else:
                start_number = self.DEFAULT_SERVICE_NUMBER_START
        
        # Assign numbers based on ranking
        for idx, graduate in enumerate(graduates):
            if not graduate.service_number:
                graduate.service_number = str(start_number + idx)
                graduate.save()
        
        # Refresh from DB
        self.refresh_from_db()
        return self.service_number
    
    def calculate_rank_in_class(self):
        """Calculate and store rank within the intake"""
        classmates = Recruit.objects.filter(
            intake=self.intake,
            status__in=['graduated', 'in_training']
        ).exclude(overall_score__isnull=True).order_by('-overall_score', 'surname')
        
        self.total_recruits_in_class = classmates.count()
        for idx, classmate in enumerate(classmates, 1):
            if classmate.id == self.id:
                self.rank_in_class = idx
                self.save()
                return idx
        return None
    
    def get_current_ranking(self):
        """
        Get current ranking and total recruits without saving.
        Returns tuple: (rank, total_recruits)
        """
        classmates = Recruit.objects.filter(
            intake=self.intake,
            status__in=['enrolled', 'in_training', 'graduated']
        ).exclude(overall_score__isnull=True).order_by('-overall_score', 'surname', 'first_name')
        
        total = classmates.count()
        for idx, classmate in enumerate(classmates, 1):
            if classmate.id == self.id:
                return (idx, total)
        
        return (None, total)
    
    def get_provisional_service_number(self):
        """
        Get a provisional service number based on current ranking.
        This is calculated dynamically and not saved.
        Format: {base_number + rank_position}
        """
        rank, total = self.get_current_ranking()
        if not rank:
            return None
        
        # Get the base service number (from previous intake or last officer)
        previous_intake = TrainingIntake.objects.filter(
            year__lt=self.intake.year
        ).order_by('-year', '-intake_number').first()
        
        if previous_intake and previous_intake.last_pass_out_number:
            base_number = previous_intake.last_pass_out_number + 1
        else:
            # Try to get last officer from Officer model
            last_officer = Officer.objects.filter(
                service_number__regex=r'^\d+$'
            ).order_by('-service_number').first()
            if last_officer:
                base_number = int(last_officer.service_number) + 1
            else:
                base_number = self.DEFAULT_SERVICE_NUMBER_START
        
        provisional_number = str(base_number + (rank - 1))
        return provisional_number
    
    def save(self, *args, **kwargs):
        """
        Override save to:
        1. Auto-generate training_id if not already set
        2. Auto-create course marks for all active courses
        """
        # Auto-generate training ID on first save
        if not self.training_id:
            self.training_id = self.generate_training_id()
        
        # Save the recruit first
        super().save(*args, **kwargs)
        
        # Auto-create course marks on first creation
        if self.pk and not self.marks.exists():
            self.auto_create_course_marks()


class RecruitMark(models.Model):
    """
    Stores marks obtained by a recruit in a specific course.
    Each course is now an individual subject.
    """
    recruit = models.ForeignKey(Recruit, on_delete=models.CASCADE, related_name='marks')
    course = models.ForeignKey(TrainingCourse, on_delete=models.CASCADE, related_name='marks')
    obtained_marks = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_("Obtained Marks"))
    exam_date = models.DateField()
    remarks = models.TextField(blank=True)
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Recruit Mark")
        verbose_name_plural = _("Recruit Marks")
        unique_together = ('recruit', 'course')
        ordering = ['recruit', 'course__category', 'course__display_order']

    def __str__(self):
        return f"{self.recruit.full_name} - {self.course.name}: {self.obtained_marks}/{self.course.total_marks}"

    @property
    def percentage(self):
        if self.course.total_marks == 0:
            return 0
        return (self.obtained_marks / self.course.total_marks) * 100

    @property
    def grade(self):
        return self.recruit._get_grade(self.percentage)
    
    @property
    def is_passing(self):
        return self.obtained_marks >= self.course.passing_mark

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Recalculate overall results after saving marks
        self.recruit.calculate_final_results()


class GraduationBatch(models.Model):
    """
    Tracks graduation events and service number assignments.
    """
    intake = models.OneToOneField(TrainingIntake, on_delete=models.CASCADE, related_name='graduation')
    graduation_date = models.DateField()
    ceremony_location = models.CharField(max_length=200)
    total_graduates = models.IntegerField(default=0)
    total_passed = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    best_performing_recruit = models.ForeignKey(Recruit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    # Service number range assigned
    service_number_start = models.PositiveIntegerField()
    service_number_end = models.PositiveIntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Graduation Batch")
        verbose_name_plural = _("Graduation Batches")
    
    def __str__(self):
        return f"Graduation - {self.intake.get_display_name()} ({self.graduation_date})"
    
    def generate_report(self):
        """Generate graduation report with rankings"""
        graduates = Recruit.objects.filter(
            intake=self.intake,
            status='graduated'
        ).order_by('-overall_score', 'surname', 'first_name')
        
        report = []
        for idx, grad in enumerate(graduates, 1):
            report.append({
                'rank': idx,
                'service_number': grad.service_number,
                'full_name': grad.full_name,
                'overall_score': grad.overall_score,
                'grade': grad.final_grade,
                'district': grad.home_district,
            })
        
        return report


class CourseEnrollment(models.Model):
    """
    Tracks which courses an officer has completed (for refresher tracking).
    """
    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name='course_enrollments')
    course = models.ForeignKey(TrainingCourse, on_delete=models.CASCADE)
    completion_date = models.DateField()
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    certificate_issued = models.BooleanField(default=False)
    certificate_number = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Course Enrollment")
        verbose_name_plural = _("Course Enrollments")
        unique_together = ('officer', 'course')
    
    def __str__(self):
        return f"{self.officer.full_name} - {self.course.name}"




class AttendanceSummary(models.Model):
    """
    Model for storing monthly attendance summaries and statistics.
    """
    officer = models.ForeignKey('Officer', on_delete=models.CASCADE, verbose_name=_("Officer"))
    year = models.PositiveIntegerField(verbose_name=_("Year"))
    month = models.PositiveIntegerField(verbose_name=_("Month"), validators=[MinValueValidator(1), MaxValueValidator(12)])
    
    # Attendance counts
    total_days = models.PositiveIntegerField(default=0, verbose_name=_("Total Days"))
    present_days = models.PositiveIntegerField(default=0, verbose_name=_("Present Days"))
    absent_days = models.PositiveIntegerField(default=0, verbose_name=_("Absent Days"))
    leave_days = models.PositiveIntegerField(default=0, verbose_name=_("Leave Days"))
    sick_days = models.PositiveIntegerField(default=0, verbose_name=_("Sick Days"))
    duty_days = models.PositiveIntegerField(default=0, verbose_name=_("Duty Days"))
    
    # Calculated fields
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_("Attendance Percentage"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    
    class Meta:
        verbose_name = _("Attendance Summary")
        verbose_name_plural = _("Attendance Summaries")
        ordering = ['-year', '-month', 'officer__surname', 'officer__first_name']
        unique_together = ['officer', 'year', 'month']
        
    def __str__(self):
        return f"{self.officer.full_name} - {self.year}/{self.month:02d}"
    
    @property
    def attendance_rate(self):
        if self.total_days > 0:
            return float(self.attendance_percentage)
        return 0.0
    
    def calculate_statistics(self):
        """Calculate attendance statistics from individual attendance records."""
        attendances = Attendance.objects.filter(
            officer=self.officer,
            date__year=self.year,
            date__month=self.month
        )
        
        self.total_days = attendances.count()
        self.present_days = attendances.filter(status='present').count()
        self.absent_days = attendances.filter(status='absent').count()
        self.leave_days = attendances.filter(status='leave').count()
        self.sick_days = attendances.filter(status='sick').count()
        self.duty_days = attendances.filter(status='duty').count()
        
        # Calculate attendance percentage (excluding leave days)
        workable_days = self.total_days - self.leave_days - self.sick_days - self.duty_days
        if workable_days > 0:
            self.attendance_percentage = (self.present_days / workable_days) * 100
        else:
            self.attendance_percentage = 0
        
        self.save()


class AttendancePattern(models.Model):
    """
    Model for tracking attendance patterns and anomalies.
    """
    officer = models.ForeignKey('Officer', on_delete=models.CASCADE, verbose_name=_("Officer"))
    pattern_type = models.CharField(max_length=50, verbose_name=_("Pattern Type"))
    description = models.TextField(verbose_name=_("Description"))
    severity = models.CharField(max_length=20, choices=[
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ], default='medium', verbose_name=_("Severity"))
    
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(null=True, blank=True, verbose_name=_("End Date"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    
    class Meta:
        verbose_name = _("Attendance Pattern")
        verbose_name_plural = _("Attendance Patterns")
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.officer.full_name} - {self.pattern_type}"


class BulkMarkImport(models.Model):
    """
    Tracks bulk mark import operations for recruits.
    """
    IMPORT_STATUS = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    ]
    
    intake = models.ForeignKey(TrainingIntake, on_delete=models.CASCADE, related_name='bulk_imports')
    import_file = models.FileField(upload_to='mark_imports/%Y/%m/%d/')
    file_type = models.CharField(max_length=10, choices=[('csv', 'CSV'), ('excel', 'Excel')])
    status = models.CharField(max_length=20, choices=IMPORT_STATUS, default='pending')
    
    total_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    
    error_log = models.TextField(blank=True, help_text=_("Log of any errors during import"))
    
    imported_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = _("Bulk Mark Import")
        verbose_name_plural = _("Bulk Mark Imports")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Import {self.intake.get_display_name()} - {self.get_status_display()}"


class ProvisionalServiceNumber(models.Model):
    """
    Tracks provisional service numbers assigned to recruits during training.
    These become permanent after graduation and final grading.
    """
    recruit = models.OneToOneField(Recruit, on_delete=models.CASCADE, related_name='provisional_service_number')
    provisional_number = models.CharField(max_length=50, unique=True)
    rank_position = models.IntegerField()  # Rank in the intake
    total_in_intake = models.IntegerField()  # Total recruits in intake
    
    assigned_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    finalized_date = models.DateTimeField(null=True, blank=True)  # When it became permanent
    
    class Meta:
        verbose_name = _("Provisional Service Number")
        verbose_name_plural = _("Provisional Service Numbers")
        ordering = ['-assigned_date']
    
    def __str__(self):
        return f"{self.recruit.full_name} - {self.provisional_number}"
    
    def finalize_to_permanent(self, permanent_number):
        """
        Convert this provisional number to a permanent service number.
        """
        self.recruit.service_number = permanent_number
        self.recruit.status = 'graduated'
        self.recruit.graduated_at = timezone.now()
        self.recruit.save()
        
        self.finalized_date = timezone.now()
        self.save()


# Django signals for automatic module addition
from django.db.models.signals import post_save


