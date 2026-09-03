from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from prison.models import PrisonStation
from django.conf import settings
from django.core.validators import FileExtensionValidator
from datetime import datetime

User = get_user_model()


class ReturnTemplate(models.Model):
    """
    Template definitions for different return types.
    """
    CATEGORY_CHOICES = [
        ('convicted_inmates', 'Convicted Inmates'),
        ('due_discharge', 'Due Discharge'),
        ('remand_murder', 'Remand Murder Prisoners'),
        ('convicted_foreigners', 'Convicted Foreigners'),
        ('general_remand', 'General Remandees'),
        ('pardon_consideration', 'Pardon Consideration'),
        ('chronically_ill', 'Chronically Ill Convicted'),
        ('elderly_inmates', 'Elderly Inmates (70+)'),
        ('discharged_reduction', 'Discharged After Reduction'),
        ('children_with_mothers', 'Children Accompanying Mothers'),
        ('pregnant_convicted', 'Pregnant Convicted'),
        ('pregnant_remand', 'Pregnant Remand'),
        ('children_remand', 'Children with Mothers on Remand'),
        ('foreigners_remand', 'Foreigners on Remand'),
    ]

    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False, help_text="Indicates if this is a system default template")
    template_file = models.FileField(
        upload_to='return_templates/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['csv', 'xlsx', 'xls'])]
    )
    required_columns = models.JSONField(default=list, help_text="List of required column headers")
    column_headers = models.JSONField(default=list, help_text="Display headers for the template")
    example_data = models.JSONField(default=list, help_text="Example rows for reference")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    class Meta:
        ordering = ['category', 'name']


class ReturnSubmission(models.Model):
    """
    Represents a submitted return file for a specific prison station.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('validated', 'Validated'),
        ('rejected', 'Rejected'),
        ('imported', 'Imported Successfully'),
        ('approved', 'Approved'),
    ]

    template = models.ForeignKey(ReturnTemplate, on_delete=models.CASCADE, related_name='submissions')
    prison_station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='return_submissions')
    file = models.FileField(
        upload_to='return_submissions/',
        validators=[FileExtensionValidator(['csv', 'xlsx', 'xls'])]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='return_submissions'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='processed_returns'
    )
    
    # Month and Year fields for reporting period
    year = models.PositiveIntegerField(
        default=timezone.now().year,
        help_text="Reporting year (e.g., 2026)"
    )
    month = models.PositiveIntegerField(
        default=timezone.now().month,
        help_text="Reporting month (1-12)"
    )
    period = models.CharField(
        max_length=20,
        default=timezone.now().strftime('%Y-%m'),
        help_text="Reporting period (YYYY-MM)"
    )
    
    row_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    total_male = models.PositiveIntegerField(default=0)
    total_female = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.template.name} - {self.prison_station.name} - {self.period}"

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['period']),
            models.Index(fields=['prison_station', 'template']),
        ]

    def save(self, *args, **kwargs):
        # Auto-update period based on year and month
        if self.year and self.month:
            self.period = f"{self.year}-{self.month:02d}"
        super().save(*args, **kwargs)

    @property
    def month_name(self):
        """Get month name for display."""
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        return month_names.get(self.month, 'Unknown')

    @property
    def period_display(self):
        """Get display format for period."""
        return f"{self.month_name} {self.year}"

    @property
    def submission_date_display(self):
        """Get formatted submission date."""
        return self.submitted_at.strftime('%d-%m-%Y %H:%M')


class ReturnData(models.Model):
    """
    Stores imported return data for display and reporting.
    """
    submission = models.ForeignKey(ReturnSubmission, on_delete=models.CASCADE, related_name='data_rows')
    row_data = models.JSONField(default=dict)
    row_number = models.PositiveIntegerField(default=0, help_text="Original row number from the file")
    prisoner_number = models.CharField(max_length=20, blank=True)
    name = models.CharField(max_length=200, blank=True)
    sex = models.CharField(max_length=10, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    offense = models.CharField(max_length=300, blank=True)
    court_case_number = models.CharField(max_length=100, blank=True)
    sentence = models.CharField(max_length=100, blank=True)
    date_of_committal = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)
    validation_errors = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prisoner_number or 'Unknown'} - {self.name or 'No Name'}"

    class Meta:
        ordering = ['row_number']  # Order by row number for ascending display
        indexes = [
            models.Index(fields=['submission', 'row_number']),
        ]


class RegionalReturnSummary(models.Model):
    """
    Aggregated return data for regional overview.
    """
    PERIOD_TYPE_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]

    category = models.CharField(max_length=50)
    region = models.CharField(max_length=50, blank=True)
    year = models.PositiveIntegerField(default=timezone.now().year)
    month = models.PositiveIntegerField(default=timezone.now().month)
    period = models.CharField(max_length=20)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES, default='monthly')
    total_records = models.PositiveIntegerField(default=0)
    male_count = models.PositiveIntegerField(default=0)
    female_count = models.PositiveIntegerField(default=0)
    additional_data = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_summaries'
    )

    class Meta:
        ordering = ['-generated_at']
        unique_together = ('category', 'region', 'period', 'period_type')

    def __str__(self):
        return f"{self.category} - {self.region or 'All Regions'} - {self.period}"

    @property
    def month_name(self):
        """Get month name for display."""
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        return month_names.get(self.month, 'Unknown')


class StationReturnStatus(models.Model):
    """
    Tracks which returns have been submitted by each station for a given period.
    This is the key model for tracking monthly submissions.
    """
    STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending Review'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    prison_station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='return_statuses')
    template = models.ForeignKey(ReturnTemplate, on_delete=models.CASCADE, related_name='station_statuses')
    
    # Period fields
    year = models.PositiveIntegerField(default=timezone.now().year)
    month = models.PositiveIntegerField(default=timezone.now().month)
    period = models.CharField(max_length=20, help_text="e.g., 2026-11 for November 2026")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_submitted')
    submission = models.ForeignKey(ReturnSubmission, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Tracking fields
    submitted_at = models.DateTimeField(null=True, blank=True, help_text="When the return was submitted")
    approved_at = models.DateTimeField(null=True, blank=True, help_text="When the return was approved")
    rejected_at = models.DateTimeField(null=True, blank=True, help_text="When the return was rejected")
    due_date = models.DateField(null=True, blank=True, help_text="Due date for submission")
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('prison_station', 'template', 'period')
        ordering = ['prison_station', 'template__category', 'year', 'month']
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['period']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.prison_station.name} - {self.template.name} - {self.period}"

    @property
    def month_name(self):
        """Get month name for display."""
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        return month_names.get(self.month, 'Unknown')

    @property
    def period_display(self):
        """Get display format for period."""
        return f"{self.month_name} {self.year}"

    def save(self, *args, **kwargs):
        # Auto-update period based on year and month
        if self.year and self.month:
            self.period = f"{self.year}-{self.month:02d}"
        super().save(*args, **kwargs)


class MonthlySubmissionTracker(models.Model):
    """
    Tracks all return submissions for a given month/year across all stations.
    Helps display which stations have/haven't submitted for each month.
    """
    STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    prison_station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='monthly_trackers')
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    period = models.CharField(max_length=20)
    
    # Counts by category
    total_required = models.PositiveIntegerField(default=0)
    total_submitted = models.PositiveIntegerField(default=0)
    total_approved = models.PositiveIntegerField(default=0)
    total_rejected = models.PositiveIntegerField(default=0)
    total_pending = models.PositiveIntegerField(default=0)
    
    # Track individual template statuses as JSON
    template_statuses = models.JSONField(default=dict, help_text="JSON dict of template category statuses")
    
    is_complete = models.BooleanField(default=False, help_text="Indicates if all required returns are submitted")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('prison_station', 'year', 'month', 'period')
        ordering = ['-year', '-month', 'prison_station__name']
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['period']),
        ]

    def __str__(self):
        return f"{self.prison_station.name} - {self.period}"

    @property
    def month_name(self):
        """Get month name for display."""
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        return month_names.get(self.month, 'Unknown')

    @property
    def period_display(self):
        """Get display format for period."""
        return f"{self.month_name} {self.year}"

    @property
    def submission_percentage(self):
        """Calculate percentage of submissions completed."""
        if self.total_required == 0:
            return 0
        return (self.total_submitted / self.total_required) * 100


class ReturnTypeStatus(models.Model):
    """
    Status tracking for a specific return type for a specific period.
    This provides a fine-grained view of which returns are pending for each station.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    prison_station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='return_type_statuses')
    template = models.ForeignKey(ReturnTemplate, on_delete=models.CASCADE, related_name='type_statuses')
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    period = models.CharField(max_length=20)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submission = models.ForeignKey(ReturnSubmission, on_delete=models.SET_NULL, null=True, blank=True)
    
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    remarks = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('prison_station', 'template', 'period')
        ordering = ['prison_station', 'template__category', 'year', 'month']
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['period']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.prison_station.name} - {self.template.name} - {self.period}"

    @property
    def month_name(self):
        """Get month name for display."""
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        return month_names.get(self.month, 'Unknown')

    @property
    def period_display(self):
        """Get display format for period."""
        return f"{self.month_name} {self.year}"

    def save(self, *args, **kwargs):
        # Auto-update period based on year and month
        if self.year and self.month:
            self.period = f"{self.year}-{self.month:02d}"
        super().save(*args, **kwargs)