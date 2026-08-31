# forms.py - Complete fixed version

from django import forms
from .models import *
from accounts.models import CustomUser, PrisonStation, Region
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import json
import csv
import io

User = get_user_model()

# PrisonStationForm is now in accounts/forms.py, imported from there

class PrisonerForm(forms.ModelForm):
    class Meta:
        model = Prisoner
        exclude = ['created_by', 'last_modified', 'is_active', 
                   'fingerprint_template', 'fingerprint_hash', 
                   'fingerprint_captured_at', 'fingerprint_captured_by',
                   'fingerprint_quality', 'fingerprint_device',
                   'previous_identities', 'is_identity_verified',
                   'identity_verified_at', 'identity_verified_by',
                   'identity_verification_notes']
        widgets = {
            'date_admitted': forms.DateInput(attrs={'type': 'date'}),
            'image': forms.FileInput(attrs={'accept': 'image/*'}),
            'document': forms.FileInput(attrs={'accept': '.pdf,application/pdf'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and not self.user.is_superuser:
            self.fields['prison_station'].queryset = PrisonStation.objects.filter(name=self.user.prison_station)

class ConvictedPrisonerForm(forms.ModelForm):
    class Meta:
        model = ConvictedPrisoner
        exclude = ['prisoner', 'release_date', 'date_of_release_on_remission']
        widgets = {
            'date_of_committal': forms.DateInput(attrs={'type': 'date'}),
            'wef_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
            'reduction_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reduction_months'].required = False
        self.fields['reduction_notes'].required = False
        self.fields['notes'].required = False

class RemandPrisonerForm(forms.ModelForm):
    class Meta:
        model = RemandPrisoner
        exclude = ['prisoner']
        widgets = {
            'next_court_date': forms.DateInput(attrs={'type': 'date'}),
        }

class RiskAssessmentForm(forms.ModelForm):
    class Meta:
        model = RiskAssessment
        exclude = ['prisoner']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['previous_convictions_count'].required = False

class PrisonerParticularsForm(forms.ModelForm):
    class Meta:
        model = PrisonerParticulars
        exclude = ['prisoner']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['denomination'].required = False
        self.fields['spouse_name'].required = False
        self.fields['spouse_location'].required = False
        self.fields['mobile_number'].required = False
        self.fields['national_id'].required = False
        self.fields['passport_number'].required = False
        self.fields['driving_license'].required = False
        self.fields['profession'].required = False
        self.fields['past_occupation'].required = False
        self.fields['home_location'].required = False

class PhysicalCharacteristicsForm(forms.ModelForm):
    class Meta:
        model = PhysicalCharacteristics
        exclude = ['prisoner']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['head_abnormalities'].required = False
        self.fields['marks_tattoos_scars'].required = False
        self.fields['children_count'].required = False

class RehabilitationProgramForm(forms.ModelForm):
    class Meta:
        model = RehabilitationProgram
        exclude = ['prisoner']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['program_name'].required = False
        self.fields['program_level'].required = False

class PrisonerTransferForm(forms.ModelForm):
    class Meta:
        model = PrisonerTransfer
        fields = ['to_prison', 'reason']

    def __init__(self, *args, **kwargs):
        self.prisoner = kwargs.pop('prisoner', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.prisoner:
            self.fields['to_prison'].queryset = PrisonStation.objects.exclude(id=self.prisoner.prison_station.id)

class SentenceReductionForm(forms.ModelForm):
    class Meta:
        model = ConvictedPrisoner
        fields = ['reduction_months', 'reduction_notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reduction_months'].required = False
        self.fields['reduction_notes'].required = False

class VisitorForm(forms.ModelForm):
    class Meta:
        model = Visitor
        fields = [
            'prisoner',
            'first_name',
            'surname',
            'id_number',
            'contact_number',
            'address',
            'relationship',
            'purpose_of_visit',
            'visit_date',
            'visit_time',
            'items',
            'is_approved',
            'denial_reason',
        ]
        widgets = {
            'visit_date': forms.DateInput(attrs={'type': 'date'}),
            'visit_time': forms.TimeInput(attrs={'type': 'time'}),
            'is_approved': forms.CheckboxInput(),
            'purpose_of_visit': forms.Textarea(attrs={'rows': 4}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if 'prisoner' in self.fields:
            if self.user and not self.user.is_superuser:
                self.fields['prisoner'].queryset = Prisoner.objects.filter(
                    prison_station=self.user.prison_station
                )

class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = '__all__'
        exclude = ['created_by', 'created_at', 'updated_at']
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date'}),
            'next_checkup': forms.DateInput(attrs={'type': 'date'}),
            'category': forms.Select(choices=MedicalRecord.MEDICAL_CATEGORIES),
            'diagnosis': forms.TextInput(attrs={'maxlength': 200}),
            'treatment': forms.Textarea(attrs={'rows': 3}),
            'prescribed_medication': forms.Textarea(attrs={'rows': 3}),
            'attending_staff': forms.TextInput(attrs={'maxlength': 100}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_superuser:
            self.fields['prisoner'].queryset = Prisoner.objects.filter(
                prison_station=user.prison_station
            )

class IncidentReportForm(forms.ModelForm):
    class Meta:
        model = IncidentReport
        fields = '__all__'
        exclude = ['reported_by', 'created_at', 'updated_at']
        widgets = {
            'date_occurred': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'actions_taken': forms.Textarea(attrs={'rows': 3}),
            'follow_up_notes': forms.Textarea(attrs={'rows': 3}),
            'severity': forms.Select(choices=IncidentReport.SEVERITY_CHOICES),
            'location': forms.TextInput(attrs={'placeholder': 'Enter location within the prison'}),
            'involved_prisoners': forms.SelectMultiple(),
            'involved_staff': forms.Textarea(attrs={'rows': 2}),
            'follow_up_required': forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_superuser:
            self.fields['involved_prisoners'].queryset = Prisoner.objects.filter(prison_station=user.prison_station)

class SearchForm(forms.Form):
    search_query = forms.CharField(required=False, label='Search Prisoners')
    prisoner_class = forms.ChoiceField(
        choices=[('', 'All')] + Prisoner.PRISONER_CLASS_CHOICES,
        required=False,
        label='Prisoner Class'
    )
    prison_station = forms.ModelChoiceField(
        queryset=PrisonStation.objects.all(),
        required=False,
        label='Prison Station'
    )
    risk_level = forms.ChoiceField(
        choices=[('', 'All')] + RiskAssessment.RISK_LEVEL_CHOICES,
        required=False,
        label='Risk Level'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_superuser:
            self.fields['prison_station'].queryset = PrisonStation.objects.filter(name=user.prison_station)
            self.fields['prison_station'].initial = PrisonStation.objects.get(name=user.prison_station)
            self.fields['prison_station'].widget.attrs['disabled'] = True

class PrisonerItemForm(forms.ModelForm):
    class Meta:
        model = PrisonerItem
        fields = ['item_type', 'description', 'quantity', 'initial_amount', 'currency', 'notes']
        widgets = {
            'item_type': forms.Select(attrs={'onchange': 'toggleAmountAndQuantity(this)'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quantity'].required = False
        self.fields['initial_amount'].required = False
        self.fields['currency'].initial = 'MWK'

    def clean(self):
        cleaned_data = super().clean()
        item_type = cleaned_data.get('item_type')
        quantity = cleaned_data.get('quantity')
        initial_amount = cleaned_data.get('initial_amount')

        if item_type == 'money':
            if not initial_amount or initial_amount <= 0:
                self.add_error('initial_amount', 'Initial amount must be a positive value for money items.')
            cleaned_data['quantity'] = 1
        else:
            if not quantity or quantity <= 0:
                self.add_error('quantity', 'Quantity must be a positive value for non-money items.')
            cleaned_data['initial_amount'] = 0
            cleaned_data['currency'] = 'MWK'

        return cleaned_data

class PrisonerItemTransactionForm(forms.ModelForm):
    class Meta:
        model = PrisonerItemTransaction
        fields = ['amount', 'reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.item = kwargs.pop('item', None)
        super().__init__(*args, **kwargs)
        if self.item:
            self.fields['amount'].label = f"Amount ({self.item.currency})"
        else:
            self.fields['amount'].label = "Amount"

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if self.item and self.item.item_type == 'money':
            if self.instance.pk is None and amount > self.item.current_amount:
                raise ValidationError(f"Withdrawal amount ({amount} {self.item.currency}) exceeds current balance ({self.item.current_amount} {self.item.currency}).")
        return amount

class ExtendedSearchForm(forms.Form):
    search_query = forms.CharField(required=False, label='Search by Name/Number')
    gender = forms.ChoiceField(
        choices=[('', 'All')] + Prisoner.SEX_CHOICES,
        required=False,
        label='Gender'
    )
    prisoner_class = forms.ChoiceField(
        choices=[('', 'All')] + Prisoner.PRISONER_CLASS_CHOICES,
        required=False,
        label='Prisoner Class'
    )
    previous_conviction = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        label='Previous Conviction'
    )
    release_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Release Date From'
    )
    release_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Release Date To'
    )
    prison_station = forms.ModelChoiceField(
        queryset=PrisonStation.objects.all(),
        required=False,
        label='Prison Station'
    )
    has_fingerprint = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        label='Has Fingerprint'
    )
    identity_verified = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        label='Identity Verified'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_superuser:
            self.fields['prison_station'].queryset = PrisonStation.objects.filter(name=user.prison_station)
            self.fields['prison_station'].initial = PrisonStation.objects.get(name=user.prison_station)
            self.fields['prison_station'].widget.attrs['disabled'] = True

# ============ FINGERPRINT / BIOMETRIC FORMS ============

class FingerprintCaptureForm(forms.Form):
    """Form for capturing fingerprint data"""
    fingerprint_data = forms.CharField(widget=forms.HiddenInput(), required=True)
    quality_score = forms.IntegerField(required=False, widget=forms.HiddenInput())
    device_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
    def clean_fingerprint_data(self):
        data = self.cleaned_data.get('fingerprint_data')
        if not data or len(data) < 10:
            raise ValidationError("Invalid fingerprint data. Please try again.")
        return data
    
    def clean_quality_score(self):
        score = self.cleaned_data.get('quality_score')
        if score is not None:
            if score < 0 or score > 100:
                raise ValidationError("Quality score must be between 0 and 100.")
        return score
    
    def clean_device_id(self):
        device_id = self.cleaned_data.get('device_id')
        if device_id:
            try:
                from .models import FingerprintDevice
                FingerprintDevice.objects.get(id=device_id)
            except FingerprintDevice.DoesNotExist:
                raise ValidationError("Selected device does not exist.")
        return device_id

class FingerprintSearchForm(forms.Form):
    """Form for searching prisoners by fingerprint"""
    fingerprint_data = forms.CharField(widget=forms.HiddenInput(), required=True)
    search_threshold = forms.FloatField(
        initial=70.0,
        required=False,
        min_value=0,
        max_value=100,
        help_text="Minimum match percentage (0-100)"
    )
    
    def clean_fingerprint_data(self):
        data = self.cleaned_data.get('fingerprint_data')
        if not data or len(data) < 10:
            raise ValidationError("Invalid fingerprint data. Please try again.")
        return data

class PrisonerIdentityVerificationForm(forms.ModelForm):
    """Form for verifying prisoner identity"""
    class Meta:
        model = Prisoner
        fields = ['is_identity_verified', 'identity_verified_at', 'identity_verification_notes']
        widgets = {
            'identity_verified_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'identity_verification_notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['identity_verified_at'].required = False
        self.fields['identity_verification_notes'].required = False
        if self.instance and self.instance.pk:
            self.fields['identity_verified_at'].initial = timezone.now()

class FingerprintDeviceForm(forms.ModelForm):
    """Form for managing fingerprint devices"""
    class Meta:
        model = FingerprintDevice
        fields = ['name', 'device_type', 'serial_number', 'status', 'prison_station', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_serial_number(self):
        serial = self.cleaned_data.get('serial_number')
        if serial and FingerprintDevice.objects.filter(
            serial_number=serial
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError("A device with this serial number already exists.")
        return serial

class FingerprintMatchConfirmForm(forms.Form):
    """Form for confirming a fingerprint match"""
    confirmed = forms.BooleanField(required=True, label="Confirm this match")
    notes = forms.CharField(
        required=False, 
        widget=forms.Textarea(attrs={'rows': 3}),
        label="Additional Notes"
    )
    link_identities = forms.BooleanField(
        required=False,
        label="Link identities (if this is the same person with different names)"
    )

class RationItemForm(forms.ModelForm):
    class Meta:
        model = RationItem
        exclude = ['current_stock_kg', 'is_active', 'estimated_days_remaining', 'last_stock_update', 'last_consumption_date']
        widgets = {
            'low_stock_threshold_kg': forms.NumberInput(attrs={'step': '0.001', 'min': '0'}),
            'daily_consumption_per_prisoner_kg': forms.NumberInput(attrs={'step': '0.0001', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_superuser:
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(pk=user.prison_station.pk)
                self.fields['prison_station'].initial = user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = 'readonly'
                self.fields['prison_station'].widget.attrs['disabled'] = 'disabled'
                self.fields['prison_station'].required = False
            else:
                self.fields.pop('prison_station', None)

class RationConsumptionForm(forms.ModelForm):
    class Meta:
        model = RationConsumption
        exclude = ['consumed_by', 'num_prisoners_fed', 'consumption_date', 'quantity_used_kg']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and not self.user.is_superuser:
            if hasattr(self.user, 'prison_station') and self.user.prison_station:
                self.fields['item'].queryset = RationItem.objects.filter(
                    prison_station=self.user.prison_station,
                    is_active=True
                )
            else:
                self.fields['item'].queryset = RationItem.objects.none()
                self.fields['item'].help_text = "You must be assigned to a prison station to record consumption."

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')

        if item and self.user and hasattr(self.user, 'prison_station') and self.user.prison_station:
            try:
                active_prisoners = Prisoner.objects.filter(
                    prison_station=self.user.prison_station,
                    is_active=True
                )
                total_inmates = active_prisoners.count()
                children_count = sum(
                    p.physical.children_count for p in active_prisoners.filter(sex='female')
                    if hasattr(p, 'physical') and p.physical and p.physical.children_count is not None
                )
                total_people = total_inmates + children_count
                recommended_quantity = Decimal(total_people) * Decimal('0.680')

                if item.current_stock_kg is None:
                    raise ValidationError(
                        {'item': f"Current stock for {item.name} is not set. Cannot record consumption."}
                    )
                if recommended_quantity > item.current_stock_kg:
                    raise ValidationError(
                        {'item': f"Recommended consumption ({recommended_quantity} kg) exceeds current stock ({item.current_stock_kg} kg). Reduce portion sizes or procure more stock."}
                    )

                self.instance.quantity_used_kg = recommended_quantity
                self.instance.num_prisoners_fed = total_people

            except Exception as e:
                raise ValidationError(
                    {'item': f"Error calculating consumption: {str(e)}"}
                )

        return cleaned_data

class RationProcurementForm(forms.ModelForm):
    class Meta:
        model = RationProcurement
        exclude = ['procured_by', 'procurement_date']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'quantity_procured_kg': forms.NumberInput(attrs={'step': '0.001', 'min': '0.001'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['item'].queryset = RationItem.objects.filter(
                    prison_station=user.prison_station, 
                    is_active=True
                )
            else:
                self.fields['item'].queryset = RationItem.objects.none()
                self.fields['item'].help_text = "You must be assigned to a prison station to record procurement."

class RecidivismConfirmationForm(forms.Form):
    """Form for confirming recidivism detection"""
    confirmed = forms.BooleanField(
        required=True,
        label="I confirm this person is a recidivist",
        help_text="This person has been incarcerated before and should be flagged as a recidivist"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Additional notes about the recidivism...'}),
        label="Additional Notes"
    )
    link_previous_record = forms.BooleanField(
        required=False,
        initial=True,
        label="Link to previous record",
        help_text="Link this prisoner to their previous record for tracking"
    )

class InmateReturnForm(forms.ModelForm):
    """Form for uploading and managing inmate returns with CSV support"""
    
    # Additional fields for CSV import
    csv_file = forms.FileField(
        required=False,
        label='CSV File',
        help_text='Upload a CSV file with inmate data. The file should match the selected return type template.',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv',
            'data-max-size': '10485760',  # 10MB
        })
    )
    
    # Preview options
    preview_data = forms.BooleanField(
        required=False,
        initial=True,
        label='Preview data after import',
        help_text='Show a preview of the imported data before saving'
    )
    
    # Override station field to filter by user permissions
    station = forms.ModelChoiceField(
        queryset=PrisonStation.objects.all(),
        required=True,
        label='Prison Station',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = InmateReturn
        fields = [
            'title',
            'return_type',
            'month',
            'year',
            'station',
            'file',
            'status',
            'remarks',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Convicted Inmates Return - Zomba - November 2026'
            }),
            'return_type': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'updateTemplateInfo(this.value)'
            }),
            'month': forms.Select(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2020',
                'max': '2030'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.csv'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any additional remarks...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.imported_data = kwargs.pop('imported_data', None)
        super().__init__(*args, **kwargs)
        
        # Set month choices
        self.fields['month'].choices = [
            ('', 'Select Month'),
            (1, 'January'),
            (2, 'February'),
            (3, 'March'),
            (4, 'April'),
            (5, 'May'),
            (6, 'June'),
            (7, 'July'),
            (8, 'August'),
            (9, 'September'),
            (10, 'October'),
            (11, 'November'),
            (12, 'December'),
        ]
        
        # Set year choices (last 5 years to next 2 years)
        current_year = timezone.now().year
        year_choices = [(y, str(y)) for y in range(current_year - 5, current_year + 3)]
        self.fields['year'].choices = [('', 'Select Year')] + year_choices
        
        # Set status choices
        status_choices = [('', 'Select Status')] + list(InmateReturn.STATUS_CHOICES)
        self.fields['status'].choices = status_choices
        
        # Filter stations based on user permissions
        if self.user:
            if not (hasattr(self.user, 'is_super_admin') and self.user.is_super_admin()):
                if hasattr(self.user, 'prison_station') and self.user.prison_station:
                    self.fields['station'].queryset = PrisonStation.objects.filter(
                        id=self.user.prison_station.id
                    )
                    self.fields['station'].initial = self.user.prison_station
                    self.fields['station'].widget.attrs['readonly'] = True
                    self.fields['station'].widget.attrs['disabled'] = True
                    self.fields['station'].required = False
                else:
                    self.fields['station'].queryset = PrisonStation.objects.none()
                    self.fields['station'].help_text = "You must be assigned to a prison station."
            else:
                self.fields['station'].queryset = PrisonStation.objects.all().order_by('name')
        
        # Set default values for new instances
        if not self.instance.pk:
            self.fields['year'].initial = current_year
            self.fields['month'].initial = timezone.now().month
            self.fields['status'].initial = 'draft'
    
    def clean_file(self):
        """Validate the uploaded file"""
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File size cannot exceed 10MB.")
            
            # Check file type
            allowed_extensions = [
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', 
                '.jpg', '.jpeg', '.png', '.csv'
            ]
            file_ext = file.name.split('.')[-1].lower()
            if f'.{file_ext}' not in allowed_extensions:
                raise forms.ValidationError(
                    "File type not allowed. Please upload PDF, Word, Excel, CSV, or image files."
                )
        
        return file
    
    def clean_csv_file(self):
        """Validate the CSV file"""
        csv_file = self.cleaned_data.get('csv_file')
        if csv_file:
            # Check file size (max 10MB)
            if csv_file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("CSV file size cannot exceed 10MB.")
            
            # Check file type
            if not csv_file.name.endswith('.csv'):
                raise forms.ValidationError("Please upload a CSV file.")
            
            # Validate CSV structure
            try:
                content = csv_file.read().decode('utf-8')
                csv_reader = csv.reader(io.StringIO(content))
                rows = list(csv_reader)
                
                if not rows:
                    raise forms.ValidationError("CSV file is empty.")
                
                # Get headers and check against template
                headers = [h.strip().lower() for h in rows[0]]
                return_type = self.cleaned_data.get('return_type')
                
                if return_type:
                    try:
                        template = ReturnTemplate.objects.get(return_type=return_type)
                        template_headers = [col['header'].strip().lower() for col in template.columns]
                        
                        # Check if required headers are present
                        missing_headers = []
                        for req_header in template_headers:
                            if not any(req_header in h or h in req_header for h in headers):
                                missing_headers.append(req_header)
                        
                        if missing_headers:
                            # Check if it's a different template format
                            if len(missing_headers) > len(template_headers) // 2:
                                raise forms.ValidationError(
                                    f"CSV headers don't match the template. Missing: {', '.join(missing_headers[:5])}"
                                )
                    
                    except ReturnTemplate.DoesNotExist:
                        pass  # No template defined, skip validation
                
                # Reset file pointer
                csv_file.seek(0)
                
                # Store row count for later use
                self.csv_row_count = len(rows) - 1  # Exclude header row
                
            except Exception as e:
                raise forms.ValidationError(f"Error reading CSV file: {str(e)}")
        
        return csv_file
    
    def clean(self):
        """Clean and validate all form data"""
        cleaned_data = super().clean()
        
        # Validate return type and station combination
        return_type = cleaned_data.get('return_type')
        station = cleaned_data.get('station')
        
        if return_type and station:
            # Check if a return of this type already exists for this month/year
            month = cleaned_data.get('month')
            year = cleaned_data.get('year')
            
            if month and year and not self.instance.pk:
                existing = InmateReturn.objects.filter(
                    station=station,
                    return_type=return_type,
                    month=month,
                    year=year
                ).exclude(status='rejected')
                
                if existing.exists():
                    existing_return = existing.first()
                    raise forms.ValidationError(
                        f"A {existing_return.get_return_type_display()} return for {existing_return.get_month_display()} {year} "
                        f"already exists for {station.name} (Status: {existing_return.get_status_display()})."
                    )
        
        # Auto-generate title if not provided
        title = cleaned_data.get('title')
        if not title and return_type and station and month and year:
            type_label = dict(InmateReturn.RETURN_TYPE_CHOICES).get(return_type, return_type)
            month_name = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December'][month]
            cleaned_data['title'] = f"{type_label} - {station.name} - {month_name} {year}"
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the form and handle CSV import"""
        instance = super().save(commit=False)
        
        # Set uploaded_by if not set
        if self.user:
            instance.uploaded_by = self.user
        
        # Store file metadata
        if instance.file:
            instance.file_name = instance.file.name
            instance.file_size = instance.file.size if hasattr(instance.file, 'size') else None
            instance.file_type = instance.file.name.split('.')[-1].lower() if '.' in instance.file.name else None
        
        # Handle CSV import
        csv_file = self.cleaned_data.get('csv_file')
        if csv_file:
            # Save the instance first to get an ID
            if commit:
                instance.save()
            
            # Import CSV data
            from .import_export_utils import ReturnDataImporter
            importer = ReturnDataImporter(instance, csv_file)
            success = importer.import_data()
            
            if success:
                instance.has_csv_data = True
                instance.csv_row_count = importer.imported_count
                instance.csv_imported_at = timezone.now()
                instance.update_summary()
                
                # Add imported data to instance for use in views
                self.imported_data = {
                    'count': importer.imported_count,
                    'errors': importer.errors,
                    'warnings': importer.warnings,
                }
        else:
            if commit:
                instance.save()
        
        if commit and not csv_file:
            instance.save()
        
        return instance
    
    def get_template_info(self):
        """Get template information for the selected return type"""
        return_type = self.cleaned_data.get('return_type')
        if return_type:
            try:
                template = ReturnTemplate.objects.get(return_type=return_type)
                return {
                    'name': template.name,
                    'columns': template.columns,
                    'headers': template.get_column_headers(),
                    'sample_data': template.sample_data,
                    'description': template.description,
                }
            except ReturnTemplate.DoesNotExist:
                pass
        return None
    
    def get_csv_preview(self):
        """Get preview of CSV data if available"""
        if hasattr(self, 'csv_preview_data'):
            return self.csv_preview_data
        return None
    
    def get_summary_stats(self):
        """Get summary statistics for the imported data"""
        if hasattr(self, 'imported_data'):
            return {
                'total_rows': self.imported_data.get('count', 0),
                'errors': self.imported_data.get('errors', []),
                'warnings': self.imported_data.get('warnings', []),
            }
        return None


class InmateReturnFilterForm(forms.Form):
    """Form for filtering inmate returns in list views"""
    
    return_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(InmateReturn.RETURN_TYPE_CHOICES),
        required=False,
        label='Return Type',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    station = forms.ModelChoiceField(
        queryset=PrisonStation.objects.all(),
        required=False,
        label='Station',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + list(InmateReturn.STATUS_CHOICES),
        required=False,
        label='Status',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    month = forms.ChoiceField(
        choices=[('', 'All Months')] + [(i, ['January', 'February', 'March', 'April', 'May', 'June',
                                              'July', 'August', 'September', 'October', 'November', 'December'][i-1]) 
                                        for i in range(1, 13)],
        required=False,
        label='Month',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    year = forms.ChoiceField(
        required=False,
        label='Year',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    has_csv_data = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'Has CSV Data'), ('no', 'No CSV Data')],
        required=False,
        label='CSV Data',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    search_query = forms.CharField(
        required=False,
        label='Search',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title, station, or type...'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        label='From Date',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        label='To Date',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set year choices
        current_year = timezone.now().year
        year_choices = [(y, str(y)) for y in range(current_year - 5, current_year + 2)]
        self.fields['year'].choices = [('', 'All Years')] + year_choices
        
        # Filter stations based on user permissions
        if self.user:
            if not (hasattr(self.user, 'is_super_admin') and self.user.is_super_admin()):
                if hasattr(self.user, 'prison_station') and self.user.prison_station:
                    self.fields['station'].queryset = PrisonStation.objects.filter(
                        id=self.user.prison_station.id
                    )
                    self.fields['station'].initial = self.user.prison_station
                    self.fields['station'].widget.attrs['readonly'] = True
                else:
                    self.fields['station'].queryset = PrisonStation.objects.none()
    
    def filter_queryset(self, queryset):
        """Apply filters to the queryset"""
        cleaned_data = self.cleaned_data
        
        if cleaned_data.get('return_type'):
            queryset = queryset.filter(return_type=cleaned_data['return_type'])
        
        if cleaned_data.get('station'):
            queryset = queryset.filter(station=cleaned_data['station'])
        
        if cleaned_data.get('status'):
            queryset = queryset.filter(status=cleaned_data['status'])
        
        if cleaned_data.get('month'):
            queryset = queryset.filter(month=cleaned_data['month'])
        
        if cleaned_data.get('year'):
            queryset = queryset.filter(year=cleaned_data['year'])
        
        if cleaned_data.get('has_csv_data'):
            if cleaned_data['has_csv_data'] == 'yes':
                queryset = queryset.filter(has_csv_data=True)
            elif cleaned_data['has_csv_data'] == 'no':
                queryset = queryset.filter(has_csv_data=False)
        
        if cleaned_data.get('search_query'):
            search = cleaned_data['search_query']
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(station__name__icontains=search) |
                Q(return_type__icontains=search) |
                Q(file_name__icontains=search)
            )
        
        if cleaned_data.get('date_from'):
            queryset = queryset.filter(uploaded_at__date__gte=cleaned_data['date_from'])
        
        if cleaned_data.get('date_to'):
            queryset = queryset.filter(uploaded_at__date__lte=cleaned_data['date_to'])
        
        return queryset


class ReturnDataImportForm(forms.Form):
    """Form for importing CSV data into an existing return"""
    
    csv_file = forms.FileField(
        required=True,
        label='CSV File',
        help_text='Upload a CSV file with inmate data matching the return type template.',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        })
    )
    
    replace_existing = forms.BooleanField(
        required=False,
        initial=False,
        label='Replace existing data',
        help_text='If checked, existing data will be replaced with the new CSV data.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    skip_errors = forms.BooleanField(
        required=False,
        initial=False,
        label='Skip rows with errors',
        help_text='Continue importing even if some rows have errors.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.inmate_return = kwargs.pop('inmate_return', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.inmate_return:
            self.fields['csv_file'].help_text = f'Upload CSV data for {self.inmate_return.get_return_type_display()}'
    
    def clean_csv_file(self):
        """Validate the CSV file"""
        csv_file = self.cleaned_data.get('csv_file')
        
        if not csv_file:
            raise forms.ValidationError("Please select a CSV file.")
        
        # Check file size
        if csv_file.size > 10 * 1024 * 1024:
            raise forms.ValidationError("CSV file size cannot exceed 10MB.")
        
        # Check file type
        if not csv_file.name.endswith('.csv'):
            raise forms.ValidationError("Please upload a CSV file.")
        
        # Validate CSV structure
        try:
            content = csv_file.read().decode('utf-8')
            csv_reader = csv.reader(io.StringIO(content))
            rows = list(csv_reader)
            
            if not rows:
                raise forms.ValidationError("CSV file is empty.")
            
            if len(rows) < 2:
                raise forms.ValidationError("CSV file must contain at least one data row.")
            
            # Check headers against template
            if self.inmate_return:
                headers = [h.strip().lower() for h in rows[0]]
                try:
                    template = ReturnTemplate.objects.get(return_type=self.inmate_return.return_type)
                    template_headers = [col['header'].strip().lower() for col in template.columns]
                    
                    # Check if at least some headers match
                    matching_headers = []
                    for h in headers:
                        for th in template_headers:
                            if h in th or th in h:
                                matching_headers.append(h)
                                break
                    
                    if len(matching_headers) < len(template_headers) // 3:
                        raise forms.ValidationError(
                            f"CSV headers don't match the template. Found: {', '.join(headers[:5])}. "
                            f"Expected headers include: {', '.join(template_headers[:5])}"
                        )
                
                except ReturnTemplate.DoesNotExist:
                    pass  # No template defined, skip validation
            
            # Store the CSV data for processing
            self.csv_rows = rows
            self.csv_headers = rows[0]
            self.csv_data_rows = rows[1:]
            
            # Reset file pointer
            csv_file.seek(0)
            
        except Exception as e:
            raise forms.ValidationError(f"Error reading CSV file: {str(e)}")
        
        return csv_file
    
    def import_data(self):
        """Import the CSV data into the return"""
        if not self.inmate_return or not hasattr(self, 'csv_data_rows'):
            return {'success': False, 'error': 'No data to import'}
        
        from .import_export_utils import ReturnDataImporter
        
        if self.cleaned_data.get('replace_existing'):
            # Delete existing data
            self.inmate_return.data_rows.all().delete()
        
        # Import the data
        importer = ReturnDataImporter(self.inmate_return, self.cleaned_data['csv_file'])
        success = importer.import_data()
        
        if success:
            self.inmate_return.has_csv_data = True
            self.inmate_return.csv_row_count = importer.imported_count
            self.inmate_return.csv_imported_at = timezone.now()
            self.inmate_return.update_summary()
            self.inmate_return.save()
        
        return {
            'success': success,
            'count': importer.imported_count,
            'errors': importer.errors,
            'warnings': importer.warnings,
        }

class ReturnTemplateForm(forms.ModelForm):
    """Form for creating and managing return templates"""
    
    class Meta:
        model = ReturnTemplate
        fields = [
            'name',
            'return_type',
            'description',
            'columns',
            'sample_data',
            'is_active',
            'is_default',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'return_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'columns': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'sample_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Add help texts
        self.fields['columns'].help_text = 'JSON array of column definitions with key, header, and type.'
        self.fields['columns'].initial = json.dumps([
            {'key': 'serial_no', 'header': 'Ser. No.', 'type': 'number', 'required': True},
            {'key': 'prisoner_number', 'header': 'Pri. No.', 'type': 'string', 'required': True},
            {'key': 'full_name', 'header': 'Names', 'type': 'string', 'required': True},
        ], indent=2)
        
        self.fields['sample_data'].help_text = 'JSON array of sample data rows (optional).'
        self.fields['sample_data'].initial = json.dumps([
            {'serial_no': 1, 'prisoner_number': 'P-0001', 'full_name': 'Sample Prisoner 1'},
            {'serial_no': 2, 'prisoner_number': 'P-0002', 'full_name': 'Sample Prisoner 2'},
        ], indent=2)
    
    def clean_columns(self):
        """Validate the columns JSON"""
        columns = self.cleaned_data.get('columns')
        if isinstance(columns, str):
            try:
                columns = json.loads(columns)
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON format for columns.")
        
        if not columns or not isinstance(columns, list):
            raise forms.ValidationError("Columns must be a non-empty JSON array.")
        
        # Validate each column
        for idx, col in enumerate(columns):
            if not col.get('key'):
                raise forms.ValidationError(f"Column {idx + 1} is missing a 'key' field.")
            if not col.get('header'):
                raise forms.ValidationError(f"Column '{col.get('key')}' is missing a 'header' field.")
        
        return columns
    
    def clean_sample_data(self):
        """Validate the sample data JSON"""
        sample_data = self.cleaned_data.get('sample_data')
        if sample_data:
            if isinstance(sample_data, str):
                try:
                    sample_data = json.loads(sample_data)
                except json.JSONDecodeError:
                    raise forms.ValidationError("Invalid JSON format for sample data.")
            
            if sample_data and not isinstance(sample_data, list):
                raise forms.ValidationError("Sample data must be a JSON array.")
        
        return sample_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Convert JSON strings to lists if needed
        columns = self.cleaned_data.get('columns')
        if isinstance(columns, str):
            instance.columns = json.loads(columns)
        
        sample_data = self.cleaned_data.get('sample_data')
        if sample_data and isinstance(sample_data, str):
            instance.sample_data = json.loads(sample_data)
        
        if self.user:
            instance.created_by = self.user
        
        if commit:
            instance.save()
        
        return instance

class ReturnBulkActionForm(forms.Form):
    """Form for performing bulk actions on returns"""
    
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('submit', 'Submit for Approval'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('delete', 'Delete'),
        ('export_csv', 'Export as CSV'),
        ('export_pdf', 'Export as PDF'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    return_ids = forms.ModelMultipleChoiceField(
        queryset=InmateReturn.objects.all(),
        required=True,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'})
    )
    
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='Rejection Reason (required for reject action)'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if action == 'reject' and not rejection_reason:
            self.add_error('rejection_reason', 'Rejection reason is required for reject action.')
        
        return cleaned_data
    
    def execute_action(self):
        """Execute the bulk action"""
        action = self.cleaned_data.get('action')
        return_ids = self.cleaned_data.get('return_ids')
        rejection_reason = self.cleaned_data.get('rejection_reason')
        
        results = {
            'success': [],
            'failed': [],
            'total': return_ids.count()
        }
        
        for return_obj in return_ids:
            try:
                if action == 'submit':
                    return_obj.submit(self.user)
                    results['success'].append(return_obj.id)
                
                elif action == 'approve':
                    return_obj.approve(self.user)
                    results['success'].append(return_obj.id)
                
                elif action == 'reject':
                    return_obj.reject(self.user, rejection_reason)
                    results['success'].append(return_obj.id)
                
                elif action == 'delete':
                    return_obj.delete()
                    results['success'].append(return_obj.id)
                
                elif action == 'export_csv':
                    # Handle export logic here
                    results['success'].append(return_obj.id)
                
                elif action == 'export_pdf':
                    # Handle export logic here
                    results['success'].append(return_obj.id)
            
            except Exception as e:
                results['failed'].append({
                    'id': return_obj.id,
                    'reason': str(e)
                })
        
        return results


# Temporarily commented out due to import issues with ReturnTemplate
# class ReturnTemplateForm(forms.ModelForm):
#     """Form for creating and managing return templates"""
#     
#     class Meta:
#         model = ReturnTemplate
#         fields = [
#             'name',
#             'return_type',
#             'description',
#             'columns',
#             'sample_data',
#             'is_active',
#             'is_default',
#         ]
#         widgets = {
#             'name': forms.TextInput(attrs={'class': 'form-control'}),
#             'return_type': forms.Select(attrs={'class': 'form-control'}),
#             'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
#             'columns': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
#             'sample_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
#             'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
#             'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
#         }
#     
#     def __init__(self, *args, **kwargs):
#         self.user = kwargs.pop('user', None)
#         super().__init__(*args, **kwargs)
#         
#         # Add help texts
#         self.fields['columns'].help_text = 'JSON array of column definitions with key, header, and type.'
#         self.fields['columns'].initial = json.dumps([
#             {'key': 'serial_no', 'header': 'Ser. No.', 'type': 'number', 'required': True},
#             {'key': 'prisoner_number', 'header': 'Pri. No.', 'type': 'string', 'required': True},
#             {'key': 'full_name', 'header': 'Names', 'type': 'string', 'required': True},
#         ], indent=2)
#         
#         self.fields['sample_data'].help_text = 'JSON array of sample data rows (optional).'
#         self.fields['sample_data'].initial = json.dumps([
#             {'serial_no': 1, 'prisoner_number': 'P-0001', 'full_name': 'Sample Prisoner 1'},
#             {'serial_no': 2, 'prisoner_number': 'P-0002', 'full_name': 'Sample Prisoner 2'},
#         ], indent=2)
#     
#     def clean_columns(self):
#         """Validate the columns JSON"""
#         columns = self.cleaned_data.get('columns')
#         if isinstance(columns, str):
#             try:
#                 columns = json.loads(columns)
#             except json.JSONDecodeError:
#                 raise forms.ValidationError("Invalid JSON format for columns.")
#         
#         if not columns or not isinstance(columns, list):
#             raise forms.ValidationError("Columns must be a non-empty JSON array.")
#         
#         # Validate each column
#         for idx, col in enumerate(columns):
#             if not col.get('key'):
#                 raise forms.ValidationError(f"Column {idx + 1} is missing a 'key' field.")
#             if not col.get('header'):
#                 raise forms.ValidationError(f"Column '{col.get('key')}' is missing a 'header' field.")
#         
#         return columns
#     
#     def clean_sample_data(self):
#         """Validate the sample data JSON"""
#         sample_data = self.cleaned_data.get('sample_data')
#         if sample_data:
#             if isinstance(sample_data, str):
#                 try:
#                     sample_data = json.loads(sample_data)
#                 except json.JSONDecodeError:
#                     raise forms.ValidationError("Invalid JSON format for sample data.")
#             
#             if sample_data and not isinstance(sample_data, list):
#                 raise forms.ValidationError("Sample data must be a JSON array.")
#         
#         return sample_data
#     
#     def save(self, commit=True):
#         instance = super().save(commit=False)
#         
#         # Convert JSON strings to lists if needed
#         if isinstance(self.cleaned_data['columns'], str):
#             instance.columns = json.loads(self.cleaned_data['columns'])
#         
#         if self.cleaned_data.get('sample_data') and isinstance(self.cleaned_data['sample_data'], str):
#             instance.sample_data = json.loads(self.cleaned_data['sample_data'])
#         
#         if self.user:
#             instance.created_by = self.user
#         
#         if commit:
#             instance.save()
#         
#         return instance


class ReturnSearchForm(forms.Form):
    """Advanced search form for return data"""
    
    SEARCH_FIELDS = [
        ('prisoner_number', 'Prisoner Number'),
        ('full_name', 'Full Name'),
        ('offense', 'Offense'),
        ('court', 'Court'),
        ('district', 'District'),
        ('nationality', 'Nationality'),
        ('case_status', 'Case Status'),
    ]
    
    search_field = forms.ChoiceField(
        choices=SEARCH_FIELDS,
        required=False,
        label='Search Field',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    search_value = forms.CharField(
        required=False,
        label='Search Value',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    sex = forms.ChoiceField(
        choices=[('', 'All')] + [('m', 'Male'), ('f', 'Female')],
        required=False,
        label='Gender',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    age_from = forms.IntegerField(
        required=False,
        label='Age From',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    age_to = forms.IntegerField(
        required=False,
        label='Age To',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    return_type = forms.ChoiceField(
        choices=[('', 'All Return Types')] + list(InmateReturn.RETURN_TYPE_CHOICES),
        required=False,
        label='Return Type',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    month = forms.ChoiceField(
        choices=[('', 'All Months')] + [(i, ['January', 'February', 'March', 'April', 'May', 'June',
                                              'July', 'August', 'September', 'October', 'November', 'December'][i-1]) 
                                        for i in range(1, 13)],
        required=False,
        label='Month',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    year = forms.ChoiceField(
        required=False,
        label='Year',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set year choices
        current_year = timezone.now().year
        year_choices = [(y, str(y)) for y in range(current_year - 10, current_year + 1)]
        self.fields['year'].choices = [('', 'All Years')] + year_choices
    
    def search(self, queryset):
        """Apply search filters to the queryset"""
        cleaned_data = self.cleaned_data
        
        # Search by field
        search_field = cleaned_data.get('search_field')
        search_value = cleaned_data.get('search_value')
        
        if search_field and search_value:
            field_lookup = f"{search_field}__icontains"
            queryset = queryset.filter(**{field_lookup: search_value})
        
        # Filter by gender
        sex = cleaned_data.get('sex')
        if sex:
            queryset = queryset.filter(sex__iexact=sex)
        
        # Filter by age range
        age_from = cleaned_data.get('age_from')
        age_to = cleaned_data.get('age_to')
        
        if age_from:
            queryset = queryset.filter(age__gte=age_from)
        if age_to:
            queryset = queryset.filter(age__lte=age_to)
        
        # Filter by return type
        return_type = cleaned_data.get('return_type')
        if return_type:
            queryset = queryset.filter(inmate_return__return_type=return_type)
        
        # Filter by month/year
        month = cleaned_data.get('month')
        year = cleaned_data.get('year')
        
        if month:
            queryset = queryset.filter(inmate_return__month=month)
        if year:
            queryset = queryset.filter(inmate_return__year=year)
        
        return queryset