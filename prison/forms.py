# forms.py
from django import forms
from .models import *
from accounts.models import CustomUser, PrisonStation, Region
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

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

# In forms.py - Update FingerprintCaptureForm

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
                # Validate that the device exists
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