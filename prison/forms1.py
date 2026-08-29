from django import forms
from .models import *
from accounts.models import CustomUser
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from dateutil.relativedelta import relativedelta

User = get_user_model()

class PrisonStationForm(forms.ModelForm):
    class Meta:
        model = PrisonStation
        fields = ['name', 'code', 'location', 'capacity', 'date_established']
        widgets = {
            'date_established': forms.DateInput(attrs={'type': 'date'}),
        }

class PrisonerForm(forms.ModelForm):
    class Meta:
        model = Prisoner
        exclude = ['created_by', 'last_modified', 'is_active']
        widgets = {
            'date_admitted': forms.DateInput(attrs={'type': 'date'}),
            'image': forms.FileInput(attrs={'accept': 'image/*'}),
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
        # Make optional fields explicit
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
        # Make optional fields explicit
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
            'id_number',            # <-- New field from screenshot
            'contact_number',       # <-- New field from screenshot
            'address',              # <-- New field from screenshot
            'relationship',
            'purpose_of_visit',     # <-- New field from screenshot
            'visit_date',
            'visit_time',
            'items',
            'is_approved',
            'denial_reason', # You might want to add this if it's part of the form flow for denials
        ]
        widgets = {
            'visit_date': forms.DateInput(attrs={'type': 'date'}),
            'visit_time': forms.TimeInput(attrs={'type': 'time'}),
            'is_approved': forms.CheckboxInput(),
            # You might want to add widgets for other fields for better UX, e.g.:
            'purpose_of_visit': forms.Textarea(attrs={'rows': 4}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Ensure 'prisoner' field is initialized before trying to filter its queryset
        if 'prisoner' in self.fields:
            if self.user and not self.user.is_superuser:
                # Assuming your User model has a 'prison_station' attribute
                # and Prisoner model has 'prison_station' attribute
                self.fields['prisoner'].queryset = Prisoner.objects.filter(
                    prison_station=self.user.prison_station
                )
            elif not self.user:
                # If no user is passed, you might want to show all prisoners
                # or handle it based on your application's security requirements.
                # For now, we'll let it default to all if no user restriction.
                pass


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
            # Filter prisoners by the user's prison station
            # Assuming 'prison_station' is directly accessible on the user object
            # and that Prisoner model has a 'prison_station' foreign key.
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

# New forms for PrisonerItem and PrisonerItemTransaction
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
        # Make quantity and initial_amount not required by default, will be handled by clean method
        self.fields['quantity'].required = False
        self.fields['initial_amount'].required = False
        self.fields['currency'].initial = 'MWK' # Set default currency

    def clean(self):
        cleaned_data = super().clean()
        item_type = cleaned_data.get('item_type')
        quantity = cleaned_data.get('quantity')
        initial_amount = cleaned_data.get('initial_amount')

        if item_type == 'money':
            if not initial_amount or initial_amount <= 0:
                self.add_error('initial_amount', 'Initial amount must be a positive value for money items.')
            cleaned_data['quantity'] = 1 # Force quantity to 1 for money items
        else: # For other item types
            if not quantity or quantity <= 0:
                self.add_error('quantity', 'Quantity must be a positive value for non-money items.')
            cleaned_data['initial_amount'] = 0 # Force initial_amount to 0 for non-money items
            cleaned_data['currency'] = 'MWK' # Currency is irrelevant for non-money items, but keep default

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
            if self.instance.pk is None and amount > self.item.current_amount: # Only for new withdrawals
                raise ValidationError(f"Withdrawal amount ({amount} {self.item.currency}) exceeds current balance ({self.item.current_amount} {self.item.currency}).")
        return amount

# New: Extended Search Form
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

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_superuser:
            self.fields['prison_station'].queryset = PrisonStation.objects.filter(name=user.prison_station)
            self.fields['prison_station'].initial = PrisonStation.objects.get(name=user.prison_station)
            self.fields['prison_station'].widget.attrs['disabled'] = True

# --- New Ration Management Forms ---

class RationItemForm(forms.ModelForm):
    class Meta:
        model = RationItem
        exclude = ['current_stock_kg', 'is_active'] # current_stock_kg is managed by transactions
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Non-superusers cannot select prison station; it's auto-assigned
        if user and not user.is_superuser:
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(pk=user.prison_station.pk)
                self.fields['prison_station'].initial = user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = 'readonly'
                self.fields['prison_station'].widget.attrs['disabled'] = 'disabled'
                self.fields['prison_station'].required = False
            else:
                self.fields.pop('prison_station', None) # Remove field if no station assigned


class RationConsumptionForm(forms.ModelForm):
    class Meta:
        model = RationConsumption
        exclude = ['consumed_by', 'num_prisoners_fed', 'consumption_date', 'quantity_used_kg'] # These are auto-set
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            if hasattr(user, 'prison_station') and user.prison_station:
                # Filter ration items to only those belonging to the user's prison station
                self.fields['item'].queryset = RationItem.objects.filter(prison_station=user.prison_station, is_active=True)
            else:
                self.fields['item'].queryset = RationItem.objects.none() # No items if no station
                self.fields['item'].help_text = "You must be assigned to a prison station to record consumption."


class RationProcurementForm(forms.ModelForm):
    class Meta:
        model = RationProcurement
        exclude = ['procured_by', 'procurement_date']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            if hasattr(user, 'prison_station') and user.prison_station:
                # Filter ration items to only those belonging to the user's prison station
                self.fields['item'].queryset = RationItem.objects.filter(prison_station=user.prison_station, is_active=True)
            else:
                self.fields['item'].queryset = RationItem.objects.none() # No items if no station
                self.fields['item'].help_text = "You must be assigned to a prison station to record procurement."
