# forms.py
from django import forms
from .models import *
from accounts.models import CustomUser
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import os
from django.forms import inlineformset_factory

User = get_user_model()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file_data, initial) for file_data in data]
        return [single_file_clean(data, initial)]

# ============ PRISON STATION FORM ============

class PrisonStationForm(forms.ModelForm):
    class Meta:
        model = PrisonStation
        fields = ['name', 'code', 'location', 'region', 'capacity', 'date_established']
        widgets = {
            'date_established': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., BT'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.Select(attrs={'class': 'form-select'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
            if not code.isalpha():
                raise ValidationError("Station code must contain only letters.")
            if len(code) < 2 or len(code) > 4:
                raise ValidationError("Station code must be between 2 and 4 characters.")
        return code


# ============ PRISONER FORM ============

class PrisonerForm(forms.ModelForm):
    """Form for creating and editing prisoners with auto-numbering"""

    class Meta:
        model = Prisoner
        exclude = [
            'created_by', 'last_modified', 'is_active', 'prisoner_number',
            'fingerprint_template', 'fingerprint_hash',
            'fingerprint_captured_at', 'fingerprint_captured_by',
            'fingerprint_quality', 'fingerprint_device',
            'previous_identities', 'is_identity_verified',
            'identity_verified_at', 'identity_verified_by',
            'identity_verification_notes',
            'is_recidivist', 'previous_prisoner_numbers',
            'first_incarceration_date', 'recidivism_detected_at',
            'recidivism_detected_by', 'recidivism_notes'
        ]
        widgets = {
            'date_admitted': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'image': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'}),
            'document': forms.FileInput(attrs={'accept': '.pdf,application/pdf', 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter middle name'}),
            'surname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter surname'}),
            'sex': forms.Select(attrs={'class': 'form-select'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 120}),
            'prisoner_class': forms.Select(attrs={'class': 'form-select', 'id': 'id_prisoner_class'}),
            'prison_station': forms.Select(attrs={'class': 'form-select'}),
            'block_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., A1'}),
            'cell_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 5'}),
            'date_admitted': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        labels = {
            'first_name': 'First Name *',
            'surname': 'Surname *',
            'sex': 'Sex *',
            'age': 'Age *',
            'prisoner_class': 'Prisoner Class *',
            'prison_station': 'Prison Station *',
            'block_number': 'Block Number *',
            'cell_number': 'Cell Number *',
            'date_admitted': 'Date Admitted',
            'image': 'Prisoner Photo',
            'document': 'Document (PDF)',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Style all fields with appropriate classes
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

        # Handle prison station based on user role
        if self.user and not self.user.is_super_admin():
            # Non-superuser: Station is auto-set and read-only
            if hasattr(self.user, 'prison_station') and self.user.prison_station:
                # Set queryset to only the user's station
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(
                    id=self.user.prison_station.id
                )
                self.fields['prison_station'].initial = self.user.prison_station
                self.fields['prison_station'].empty_label = None
                # Make it disabled/read-only
                self.fields['prison_station'].widget.attrs['disabled'] = True
                self.fields['prison_station'].required = False
                self.fields['prison_station'].help_text = f"Your station: {self.user.prison_station.name}"
            else:
                # User has no station assigned
                self.fields['prison_station'].widget = forms.HiddenInput()
                self.fields['prison_station'].required = False
                self.fields['prison_station'].help_text = "No station assigned. Please contact administrator."
        else:
            # Superuser: Can select any station
            self.fields['prison_station'].required = True
            self.fields['prison_station'].help_text = "Select the prison station for this prisoner"
            self.fields['prison_station'].queryset = PrisonStation.objects.all().order_by('name')

        # Add help text for auto-numbering on new prisoner
        if not self.instance.pk:  # New prisoner
            self.fields['prisoner_class'].help_text = "Select class to preview the auto-generated prisoner number"
            self.fields['prison_station'].help_text += " (Number will be auto-generated based on station and class)"

        self.fields['additional_photos'] = MultipleFileField(
            required=False,
            label='Additional Photos',
            widget=MultipleFileInput(attrs={'accept': 'image/*', 'class': 'form-control', 'multiple': True}),
        )
        self.fields['additional_documents'] = MultipleFileField(
            required=False,
            label='Additional Documents',
            widget=MultipleFileInput(attrs={'accept': '.pdf,application/pdf', 'class': 'form-control', 'multiple': True}),
        )

    def clean_prisoner_class(self):
        """Validate that prisoner class is set"""
        prisoner_class = self.cleaned_data.get('prisoner_class')
        if not prisoner_class:
            raise ValidationError("Prisoner class is required.")
        return prisoner_class

    def clean_prison_station(self):
        """Validate that prison station is set"""
        prison_station = self.cleaned_data.get('prison_station')

        # For non-superusers, we already set the station, so just return it
        if self.user and not self.user.is_super_admin():
            if hasattr(self.user, 'prison_station') and self.user.prison_station:
                return self.user.prison_station

        # For superusers, validate that a station is selected
        if not prison_station:
            raise ValidationError("Prison station is required.")
        return prison_station

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is not None and age < 0:
            raise ValidationError("Age cannot be negative.")
        if age is not None and age > 120:
            raise ValidationError("Please enter a valid age.")
        return age

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if first_name:
            first_name = first_name.strip()
            if len(first_name) < 2:
                raise ValidationError("First name must be at least 2 characters.")
        return first_name

    def clean_surname(self):
        surname = self.cleaned_data.get('surname')
        if surname:
            surname = surname.strip()
            if len(surname) < 2:
                raise ValidationError("Surname must be at least 2 characters.")
        return surname

    def clean_image(self):
        """Validate uploaded image"""
        image = self.cleaned_data.get('image')
        if image:
            # Check if file exists
            if not image:
                return None

            # Check file size (max 5MB)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError("Image file size must be under 5MB.")

            # Check file extension
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in valid_extensions:
                raise ValidationError("Only JPG, PNG, and GIF images are allowed.")

            # Check file content type
            if not image.content_type.startswith('image/'):
                raise ValidationError("Invalid image format. Please upload a valid image file.")
        return image

    def clean_document(self):
        """Validate uploaded document"""
        document = self.cleaned_data.get('document')
        if document:
            # Check if file exists
            if not document:
                return None

            # Check file size (max 10MB)
            if document.size > 10 * 1024 * 1024:
                raise ValidationError("Document file size must be under 10MB.")

            # Check file extension
            ext = os.path.splitext(document.name)[1].lower()
            if ext != '.pdf':
                raise ValidationError("Only PDF documents are allowed.")

            # Check file content type
            if document.content_type != 'application/pdf':
                raise ValidationError("Only PDF documents are allowed.")
        return document

    def clean_additional_photos(self):
        photos = self.cleaned_data.get('additional_photos', [])
        for photo in photos:
            if photo.size > 5 * 1024 * 1024 or not os.path.splitext(photo.name)[1].lower() in {'.jpg', '.jpeg', '.png', '.gif'}:
                raise ValidationError('Each additional photo must be JPG, PNG, or GIF and under 5MB.')
            if not photo.content_type.startswith('image/'):
                raise ValidationError('Each additional photo must be a valid image.')
        return photos

    def clean_additional_documents(self):
        documents = self.cleaned_data.get('additional_documents', [])
        for document in documents:
            if document.size > 10 * 1024 * 1024 or os.path.splitext(document.name)[1].lower() != '.pdf':
                raise ValidationError('Each additional document must be a PDF and under 10MB.')
            if document.content_type != 'application/pdf':
                raise ValidationError('Each additional document must be a PDF.')
        return documents


# ============ CONVICTED PRISONER FORM ============

class ConvictedPrisonerForm(forms.ModelForm):
    class Meta:
        model = ConvictedPrisoner
        exclude = [
            'prisoner',
            'release_date',
            'date_of_release_on_remission',
            'reduction_months',
            'reduction_notes',
        ]
        widgets = {
            'date_of_committal': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'wef_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'reduction_notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'sentence': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 0.5}),
            'case_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 233/2026'}),
            'sentence_structure': forms.Select(attrs={'class': 'form-select'}),
            'court': forms.TextInput(attrs={'class': 'form-control'}),
            'offense': forms.Select(attrs={'class': 'form-select'}),
            'confirmation_status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'sentence': 'Sentence (in months) *',
            'court': 'Court *',
            'case_number': 'Case Number',
            'sentence_structure': 'Other sentences run',
            'offense': 'Offense',
            'date_of_committal': 'Date of Committal *',
            'wef_date': 'With Effect From Date *',
            'confirmation_status': 'Confirmation Status',
            'notes': 'Additional Notes',
            'reduction_months': 'Reduction Months',
            'reduction_notes': 'Reduction Notes',
        }
        help_texts = {
            'wef_date': 'This is the date the sentence takes effect. Can be before or on the date of committal.',
            'date_of_committal': 'The date the prisoner was committed to prison.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reduction_months'].required = False
        self.fields['reduction_notes'].required = False
        self.fields['notes'].required = False
        self.fields['offense'].required = False

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_sentence(self):
        sentence = self.cleaned_data.get('sentence')
        if sentence is not None and sentence <= 0:
            raise ValidationError("Sentence must be greater than 0 months.")
        return sentence

    def clean_reduction_months(self):
        reduction = self.cleaned_data.get('reduction_months')
        if reduction is None:
            return 0
        if reduction < 0:
            raise ValidationError("Reduction months cannot be negative.")
        if self.instance and self.instance.sentence and reduction > self.instance.sentence:
            raise ValidationError(f"Reduction months ({reduction}) cannot exceed the original sentence ({self.instance.sentence}).")
        return reduction

    def clean(self):
        cleaned_data = super().clean()
        wef_date = cleaned_data.get('wef_date')
        date_of_committal = cleaned_data.get('date_of_committal')

        # WEF date can be BEFORE the date of committal (time served before committal)
        # This is a common scenario in prison systems
        # Only validate that both dates are provided and valid

        if wef_date and date_of_committal:
            # We don't restrict WEF from being before date_of_committal
            # WEF before committal is perfectly valid (time served before committal)
            pass

        return cleaned_data


class AdditionalSentenceForm(forms.ModelForm):
    class Meta:
        model = AdditionalSentence
        fields = ['sentence', 'offense', 'court', 'case_number']
        widgets = {
            'sentence': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 0.5}),
            'offense': forms.Select(attrs={'class': 'form-select'}),
            'court': forms.TextInput(attrs={'class': 'form-control'}),
            'case_number': forms.TextInput(attrs={'class': 'form-control'}),
        }


AdditionalSentenceFormSet = inlineformset_factory(
    ConvictedPrisoner,
    AdditionalSentence,
    form=AdditionalSentenceForm,
    extra=1,
    can_delete=True,
)


# ============ REMAND PRISONER FORM ============

class RemandPrisonerForm(forms.ModelForm):
    class Meta:
        model = RemandPrisoner
        exclude = ['prisoner']
        widgets = {
            'next_court_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'court_case_number': forms.TextInput(attrs={'class': 'form-control'}),
            'remand_extensions': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'offense': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'court_case_number': 'Court Case Number *',
            'next_court_date': 'Next Court Date *',
            'remand_extensions': 'Remand Extensions',
            'offense': 'Offense',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['offense'].required = False
        self.fields['remand_extensions'].required = False

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_remand_extensions(self):
        extensions = self.cleaned_data.get('remand_extensions')
        if extensions is None:
            return 0
        if extensions < 0:
            raise ValidationError("Remand extensions cannot be negative.")
        return extensions

    def clean_next_court_date(self):
        next_court_date = self.cleaned_data.get('next_court_date')
        if next_court_date and next_court_date < timezone.now().date():
            raise ValidationError("Next court date cannot be in the past.")
        return next_court_date


# ============ RISK ASSESSMENT FORM ============

class RiskAssessmentForm(forms.ModelForm):
    class Meta:
        model = RiskAssessment
        exclude = ['prisoner']
        widgets = {
            'previous_conviction': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'previous_convictions_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'risk_level': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'previous_conviction': 'Previous Conviction',
            'previous_convictions_count': 'Previous Convictions Count',
            'risk_level': 'Risk Level *',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['previous_convictions_count'].required = False

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_previous_convictions_count(self):
        count = self.cleaned_data.get('previous_convictions_count')
        if count is None:
            return 0
        if count < 0:
            raise ValidationError("Previous convictions count cannot be negative.")
        return count


# ============ PRISONER PARTICULARS FORM ============

class PrisonerParticularsForm(forms.ModelForm):
    class Meta:
        model = PrisonerParticulars
        exclude = ['prisoner']
        widgets = {
            'nationality': forms.Select(attrs={'class': 'form-select'}),
            'district': forms.TextInput(attrs={'class': 'form-control'}),
            'chief': forms.TextInput(attrs={'class': 'form-control'}),
            'village': forms.TextInput(attrs={'class': 'form-control'}),
            'home_location': forms.TextInput(attrs={'class': 'form-control'}),
            'religion': forms.Select(attrs={'class': 'form-select'}),
            'denomination': forms.TextInput(attrs={'class': 'form-control'}),
            'fathers_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mothers_name': forms.TextInput(attrs={'class': 'form-control'}),
            'married': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'spouse_name': forms.TextInput(attrs={'class': 'form-control'}),
            'spouse_location': forms.TextInput(attrs={'class': 'form-control'}),
            'next_of_kin': forms.TextInput(attrs={'class': 'form-control'}),
            'next_of_kin_location': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-control'}),
            'driving_license': forms.TextInput(attrs={'class': 'form-control'}),
            'education_level': forms.Select(attrs={'class': 'form-select'}),
            'literate': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'profession': forms.TextInput(attrs={'class': 'form-control'}),
            'past_occupation': forms.TextInput(attrs={'class': 'form-control'}),
        }

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

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'


# ============ PHYSICAL CHARACTERISTICS FORM ============

class PhysicalCharacteristicsForm(forms.ModelForm):
    class Meta:
        model = PhysicalCharacteristics
        exclude = ['prisoner']
        widgets = {
            'height': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'body_build': forms.Select(attrs={'class': 'form-select'}),
            'skin_color': forms.Select(attrs={'class': 'form-select'}),
            'eyes_color': forms.Select(attrs={'class': 'form-select'}),
            'head_abnormalities': forms.TextInput(attrs={'class': 'form-control'}),
            'health_status': forms.Select(attrs={'class': 'form-select'}),
            'circumcised': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'marks_tattoos_scars': forms.TextInput(attrs={'class': 'form-control'}),
            'has_child': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'children_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
        labels = {
            'height': 'Height (cm) *',
            'weight': 'Weight (kg) *',
            'body_build': 'Body Build *',
            'skin_color': 'Skin Color *',
            'eyes_color': 'Eyes Color *',
            'health_status': 'Health Status',
            'marks_tattoos_scars': 'Marks, Tattoos, or Scars',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['head_abnormalities'].required = False
        self.fields['marks_tattoos_scars'].required = False
        self.fields['children_count'].required = False

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_height(self):
        height = self.cleaned_data.get('height')
        if height is not None and height <= 0:
            raise ValidationError("Height must be greater than 0.")
        if height is not None and height > 300:
            raise ValidationError("Please enter a valid height in cm.")
        return height

    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight is not None and weight <= 0:
            raise ValidationError("Weight must be greater than 0.")
        if weight is not None and weight > 500:
            raise ValidationError("Please enter a valid weight in kg.")
        return weight

    def clean_children_count(self):
        count = self.cleaned_data.get('children_count')
        if count is None:
            return 0
        if count < 0:
            raise ValidationError("Children count cannot be negative.")
        return count


# ============ REHABILITATION PROGRAM FORM ============

class RehabilitationProgramForm(forms.ModelForm):
    class Meta:
        model = RehabilitationProgram
        exclude = ['prisoner']
        widgets = {
            'employed_in_program': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'program_name': forms.TextInput(attrs={'class': 'form-control'}),
            'program_level': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['program_name'].required = False
        self.fields['program_level'].required = False

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'


# ============ PRISONER TRANSFER FORM ============

class PrisonerTransferForm(forms.ModelForm):
    class Meta:
        model = PrisonerTransfer
        fields = ['to_prison', 'reason']
        widgets = {
            'to_prison': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }
        labels = {
            'to_prison': 'Transfer To Prison *',
            'reason': 'Reason for Transfer *',
        }

    def __init__(self, *args, **kwargs):
        self.prisoner = kwargs.pop('prisoner', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.prisoner:
            self.fields['to_prison'].queryset = PrisonStation.objects.exclude(
                id=self.prisoner.prison_station.id
            )

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_to_prison(self):
        to_prison = self.cleaned_data.get('to_prison')
        if self.prisoner and to_prison == self.prisoner.prison_station:
            raise ValidationError("Cannot transfer to the same prison station.")
        return to_prison


# ============ SENTENCE REDUCTION FORM ============

class SentenceReductionForm(forms.ModelForm):
    class Meta:
        model = ConvictedPrisoner
        fields = ['reduction_months', 'reduction_notes']
        widgets = {
            'reduction_months': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.5}),
            'reduction_notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }
        labels = {
            'reduction_months': 'Reduction Months',
            'reduction_notes': 'Reduction Notes',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reduction_months'].required = False
        self.fields['reduction_notes'].required = False

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_reduction_months(self):
        reduction = self.cleaned_data.get('reduction_months')
        if reduction is None:
            return 0
        if reduction < 0:
            raise ValidationError("Reduction months cannot be negative.")
        if self.instance and self.instance.sentence and reduction > self.instance.sentence:
            raise ValidationError(f"Reduction months ({reduction}) cannot exceed the original sentence ({self.instance.sentence}).")
        return reduction


# ============ VISITOR FORMS ============

class VisitorForm(forms.ModelForm):
    """Form for registering a visitor with optional items"""
    items_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'e.g., Money (5000 MWK), Bread, Soap, Clothes...',
            'class': 'form-control'
        }),
        label='Items Brought'
    )

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
            'items_description',
            'is_approved',
            'denial_reason',
        ]
        widgets = {
            'visit_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'visit_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'is_approved': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'purpose_of_visit': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'items': forms.TextInput(attrs={'placeholder': 'List items separated by commas', 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'surname': forms.TextInput(attrs={'class': 'form-control'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-select'}),
            'denial_reason': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if 'prisoner' in self.fields:
            if self.user and not self.user.is_super_admin():
                if hasattr(self.user, 'prison_station') and self.user.prison_station:
                    self.fields['prisoner'].queryset = Prisoner.objects.filter(
                        prison_station=self.user.prison_station,
                        is_active=True
                    )

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_visit_date(self):
        visit_date = self.cleaned_data.get('visit_date')
        if visit_date and visit_date < timezone.now().date():
            raise ValidationError("Visit date cannot be in the past.")
        return visit_date


class VisitorItemForm(forms.ModelForm):
    """Form for adding items to a prisoner during a visitor's visit"""
    class Meta:
        model = PrisonerItem
        fields = ['item_type', 'description', 'quantity', 'initial_amount', 'currency', 'notes']
        widgets = {
            'item_type': forms.Select(attrs={
                'onchange': 'toggleAmountAndQuantity(this)',
                'class': 'form-select'
            }),
            'description': forms.TextInput(attrs={'placeholder': 'e.g., Money, Bread, Soap...', 'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Quantity', 'class': 'form-control'}),
            'initial_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': 'Amount', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes...', 'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quantity'].required = False
        self.fields['initial_amount'].required = False
        self.fields['currency'].initial = 'MWK'

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

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


# ============ MEDICAL RECORD FORM ============

class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = '__all__'
        exclude = ['created_by', 'created_at', 'updated_at']
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'next_checkup': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'category': forms.Select(choices=MedicalRecord.MEDICAL_CATEGORIES, attrs={'class': 'form-select'}),
            'diagnosis': forms.TextInput(attrs={'maxlength': 200, 'class': 'form-control'}),
            'treatment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'prescribed_medication': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'attending_staff': forms.TextInput(attrs={'maxlength': 100, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_super_admin():
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['prisoner'].queryset = Prisoner.objects.filter(
                    prison_station=user.prison_station,
                    is_active=True
                )

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_next_checkup(self):
        next_checkup = self.cleaned_data.get('next_checkup')
        record_date = self.cleaned_data.get('record_date')
        if next_checkup and record_date and next_checkup < record_date:
            raise ValidationError("Next checkup date cannot be before the record date.")
        return next_checkup


# ============ INCIDENT REPORT FORM ============

class IncidentReportForm(forms.ModelForm):
    class Meta:
        model = IncidentReport
        fields = '__all__'
        exclude = ['reported_by', 'created_at', 'updated_at']
        widgets = {
            'date_occurred': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'actions_taken': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'follow_up_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'severity': forms.Select(choices=IncidentReport.SEVERITY_CHOICES, attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'placeholder': 'Enter location within the prison', 'class': 'form-control'}),
            'involved_prisoners': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'involved_staff': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_super_admin():
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['involved_prisoners'].queryset = Prisoner.objects.filter(
                    prison_station=user.prison_station,
                    is_active=True
                )

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_date_occurred(self):
        date_occurred = self.cleaned_data.get('date_occurred')
        if date_occurred and date_occurred > timezone.now():
            raise ValidationError("Incident date cannot be in the future.")
        return date_occurred


# ============ SEARCH FORMS ============

class SearchForm(forms.Form):
    search_query = forms.CharField(required=False, label='Search Prisoners',
                                   widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search by name or number...'}))
    prisoner_class = forms.ChoiceField(
        choices=[('', 'All')] + Prisoner.PRISONER_CLASS_CHOICES,
        required=False,
        label='Prisoner Class',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    prison_station = forms.ModelChoiceField(
        queryset=PrisonStation.objects.all(),
        required=False,
        label='Prison Station',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    risk_level = forms.ChoiceField(
        choices=[('', 'All')] + RiskAssessment.RISK_LEVEL_CHOICES,
        required=False,
        label='Risk Level',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_super_admin():
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(id=user.prison_station.id)
                self.fields['prison_station'].initial = user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = True
                self.fields['prison_station'].widget.attrs['disabled'] = True

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


class ExtendedSearchForm(forms.Form):
    search_query = forms.CharField(required=False, label='Search by Name/Number',
                                   widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search...'}))
    gender = forms.ChoiceField(
        choices=[('', 'All')] + Prisoner.SEX_CHOICES,
        required=False,
        label='Gender',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    prisoner_class = forms.ChoiceField(
        choices=[('', 'All')] + Prisoner.PRISONER_CLASS_CHOICES,
        required=False,
        label='Prisoner Class',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    previous_conviction = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        label='Previous Conviction',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    release_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Release Date From'
    )
    release_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Release Date To'
    )
    prison_station = forms.ModelChoiceField(
        queryset=PrisonStation.objects.all(),
        required=False,
        label='Prison Station',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    has_fingerprint = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        label='Has Fingerprint',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    identity_verified = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        label='Identity Verified',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_super_admin():
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(id=user.prison_station.id)
                self.fields['prison_station'].initial = user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = True
                self.fields['prison_station'].widget.attrs['disabled'] = True

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        release_date_from = cleaned_data.get('release_date_from')
        release_date_to = cleaned_data.get('release_date_to')

        if release_date_from and release_date_to and release_date_from > release_date_to:
            raise ValidationError("Release Date From cannot be after Release Date To.")

        return cleaned_data


# ============ PRISONER ITEM FORMS ============

class PrisonerItemForm(forms.ModelForm):
    class Meta:
        model = PrisonerItem
        fields = ['item_type', 'description', 'quantity', 'initial_amount', 'currency', 'notes']
        widgets = {
            'item_type': forms.Select(attrs={'onchange': 'toggleAmountAndQuantity(this)', 'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'initial_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quantity'].required = False
        self.fields['initial_amount'].required = False
        self.fields['currency'].initial = 'MWK'

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

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
            'reason': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.item = kwargs.pop('item', None)
        super().__init__(*args, **kwargs)
        if self.item:
            self.fields['amount'].label = f"Amount ({self.item.currency})"
        else:
            self.fields['amount'].label = "Amount"

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if self.item and self.item.item_type == 'money':
            if self.instance.pk is None and amount > self.item.current_amount:
                raise ValidationError(
                    f"Withdrawal amount ({amount} {self.item.currency}) exceeds current balance "
                    f"({self.item.current_amount} {self.item.currency})."
                )
        return amount


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
        help_text="Minimum match percentage (0-100)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
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
            'identity_verified_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'identity_verification_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'is_identity_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['identity_verified_at'].required = False
        self.fields['identity_verification_notes'].required = False
        if self.instance and self.instance.pk:
            self.fields['identity_verified_at'].initial = timezone.now()

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__ == forms.CheckboxInput:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'


class FingerprintDeviceForm(forms.ModelForm):
    """Form for managing fingerprint devices"""
    class Meta:
        model = FingerprintDevice
        fields = ['name', 'device_type', 'serial_number', 'status', 'prison_station', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'device_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'prison_station': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_serial_number(self):
        serial = self.cleaned_data.get('serial_number')
        if serial and FingerprintDevice.objects.filter(
            serial_number=serial
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError("A device with this serial number already exists.")
        return serial


class FingerprintMatchConfirmForm(forms.Form):
    """Form for confirming a fingerprint match"""
    confirmed = forms.BooleanField(required=True, label="Confirm this match",
                                   widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        label="Additional Notes"
    )
    link_identities = forms.BooleanField(
        required=False,
        label="Link identities (if this is the same person with different names)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# ============ RATION MANAGEMENT FORMS ============

class RationItemForm(forms.ModelForm):
    class Meta:
        model = RationItem
        exclude = ['current_stock_kg', 'is_active', 'estimated_days_remaining', 'last_stock_update', 'last_consumption_date']
        widgets = {
            'low_stock_threshold_kg': forms.NumberInput(attrs={'step': '0.001', 'min': '0', 'class': 'form-control'}),
            'daily_consumption_per_prisoner_kg': forms.NumberInput(attrs={'step': '0.0001', 'min': '0', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'prison_station': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.is_super_admin():
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(pk=user.prison_station.pk)
                self.fields['prison_station'].initial = user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = 'readonly'
                self.fields['prison_station'].widget.attrs['disabled'] = 'disabled'
                self.fields['prison_station'].required = False
                self.fields['prison_station'].help_text = f"Will be set to: {user.prison_station.name}"
            else:
                self.fields.pop('prison_station', None)

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


class RationConsumptionForm(forms.ModelForm):
    class Meta:
        model = RationConsumption
        exclude = ['consumed_by', 'num_prisoners_fed', 'consumption_date', 'quantity_used_kg']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'item': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and not self.user.is_super_admin():
            if hasattr(self.user, 'prison_station') and self.user.prison_station:
                self.fields['item'].queryset = RationItem.objects.filter(
                    prison_station=self.user.prison_station,
                    is_active=True
                )
            else:
                self.fields['item'].queryset = RationItem.objects.none()
                self.fields['item'].help_text = "You must be assigned to a prison station to record consumption."

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

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
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'quantity_procured_kg': forms.NumberInput(attrs={'step': '0.001', 'min': '0.001', 'class': 'form-control'}),
            'item': forms.Select(attrs={'class': 'form-select'}),
            'supplier': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_super_admin():
            if hasattr(user, 'prison_station') and user.prison_station:
                self.fields['item'].queryset = RationItem.objects.filter(
                    prison_station=user.prison_station,
                    is_active=True
                )
            else:
                self.fields['item'].queryset = RationItem.objects.none()
                self.fields['item'].help_text = "You must be assigned to a prison station to record procurement."

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


# ============ RECIDIVISM CONFIRMATION FORM ============

class RecidivismConfirmationForm(forms.Form):
    """Form for confirming recidivism detection"""
    confirmed = forms.BooleanField(
        required=True,
        label="I confirm this person is a recidivist",
        help_text="This person has been incarcerated before and should be flagged as a recidivist",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Additional notes about the recidivism...', 'class': 'form-control'}),
        label="Additional Notes"
    )
    link_previous_record = forms.BooleanField(
        required=False,
        initial=True,
        label="Link to previous record",
        help_text="Link this prisoner to their previous record for tracking",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# ============ AUDIT / SECURITY FORMS ============

class AuditFilterForm(forms.Form):
    """Form for filtering audit trail entries"""
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Start Date'
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='End Date'
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='User'
    )
    action = forms.ChoiceField(
        choices=[('', 'All Actions')] + AuditTrail.ACTION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Action'
    )
    severity = forms.ChoiceField(
        choices=[('', 'All Severities')] + AuditTrail.SEVERITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Severity'
    )
    model_name = forms.ChoiceField(
        choices=[('', 'All Models')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Model'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate model choices dynamically
        try:
            if AuditTrail.objects.exists():
                self.fields['model_name'].choices = [('', 'All Models')] + [
                    (model, model) for model in AuditTrail.objects.values_list('model_name', flat=True).distinct()
                ]
        except Exception:
            pass

        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date.")

        return cleaned_data


class SentryAlertFilterForm(forms.Form):
    """Form for filtering sentry alerts"""
    status = forms.ChoiceField(
        choices=[('', 'All Statuses'), ('active', 'Active'), ('resolved', 'Resolved')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Status'
    )
    severity = forms.ChoiceField(
        choices=[('', 'All Severities')] + SentryAlert.SEVERITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Severity'
    )
    alert_type = forms.ChoiceField(
        choices=[('', 'All Types')] + SentryAlert.ALERT_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Alert Type'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.Select, forms.SelectMultiple]:
                field.widget.attrs['class'] = 'form-select'


class ResolveAlertForm(forms.Form):
    """Form for resolving a sentry alert"""
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Resolution notes...', 'class': 'form-control'}),
        label='Resolution Notes'
    )