# hrms/forms.py

from datetime import date

from django import forms
from .models import (
    Officer, Education, PromotionHistory, TransferHistory, LeaveRequest, OfficerDocument, 
    PerformanceMetric, OfficerPerformance, Attendance, DisciplinaryCase, DisciplinaryCaseFile, 
    Rank, OfficeAssignment, LeaveType,
    TrainingIntake, TrainingCourse, Recruit, RecruitMark, 
    GraduationBatch, CourseEnrollment, BulkMarkImport, ProvisionalServiceNumber
)
from accounts.models import Region, PrisonStation
from accounts.forms import RegionForm, PrisonStationForm as BasePrisonStationForm
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, Field, HTML
from django.utils.translation import gettext_lazy as _

# Use the base form from accounts but don't duplicate the definition
PrisonStationForm = BasePrisonStationForm

class OfficerForm(forms.ModelForm):
    """
    Form for creating and updating Officer records.
    Uses crispy-forms for better layout.
    """
    class Meta:
        model = Officer
        # Include all fields you want to be editable via the form
        fields = [
            'officer_picture', 'service_number', 'employment_number', 'status', 'gender',
            'first_name', 'middle_name', 'surname', 'date_of_birth', 'date_joined_service',
            'rank', 'grade', 'contact_number', 'email', 'village', 'traditional_authority', 'district',
            'marital_status', 'spouse_name', 'number_of_children',
            'next_of_kin_name', 'next_of_kin_relationship', 'next_of_kin_location', 'next_of_kin_contact',
            'region', 'prison_station', 'current_office_assignment',
            'notable_skills', 'languages_spoken'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_joined_service': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notable_skills': forms.Textarea(attrs={'rows': 3}),
            'languages_spoken': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            # Personal Information Section
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-primary">
                    <div class="card-header bg-primary text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-info-circle me-2"></i>Personal Information</h5>
                    </div>
                    <div class="card-body">
            '''),
            Row(
                Column('officer_picture', css_class='form-group col-md-12 mb-3'),
                Column('service_number', css_class='form-group col-md-12 mb-3'),
                Column('employment_number', css_class='form-group col-md-12 mb-3'),
                Column('first_name', css_class='form-group col-md-12 mb-3'),
                Column('middle_name', css_class='form-group col-md-12 mb-3'),
                Column('surname', css_class='form-group col-md-12 mb-3'),
                Column('date_of_birth', css_class='form-group col-md-12 mb-3'),
                Column('date_joined_service', css_class='form-group col-md-12 mb-3'),
                Column('gender', css_class='form-group col-md-12 mb-3'),
                Column('status', css_class='form-group col-md-12 mb-3'),
                Column('rank', css_class='form-group col-md-12 mb-3'),
                Column('current_office_assignment', css_class='form-group col-md-12 mb-3'),
                Column('grade',css_class='form-group col-md-12 mb-3'),
                css_class='row' # Ensure these columns are within a row
            ),
            HTML('</div></div>'), # Close card-body and card

            # Contact & Location Section
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-success">
                    <div class="card-header bg-success text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-map-marker-alt me-2"></i>Contact & Location</h5>
                    </div>
                    <div class="card-body">
            '''),
            Row(
                Column('contact_number', css_class='form-group col-md-12 mb-3'),
                Column('email', css_class='form-group col-md-12 mb-3'),
                Column('village', css_class='form-group col-md-12 mb-3'),
                Column('traditional_authority', css_class='form-group col-md-12 mb-3'),
                Column('district', css_class='form-group col-md-12 mb-3'),
                Column('region', css_class='form-group col-md-12 mb-3'),
                Column('prison_station', css_class='form-group col-md-12 mb-3'),
                css_class='row'
            ),
            HTML('</div></div>'), # Close card-body and card

            # Family Information Section
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-info">
                    <div class="card-header bg-info text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-heart me-2"></i>Family Information</h5>
                    </div>
                    <div class="card-body">
            '''),
            Row(
                Column('marital_status', css_class='form-group col-md-12 mb-3'),
                Column('spouse_name', css_class='form-group col-md-12 mb-3'),
                Column('number_of_children', css_class='form-group col-md-12 mb-3'),
                css_class='row'
            ),
            HTML('</div></div>'), # Close card-body and card

            # Next of Kin Section
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-warning">
                    <div class="card-header bg-warning text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-user-friends me-2"></i>Next of Kin</h5>
                    </div>
                    <div class="card-body">
            '''),
            Row(
                Column('next_of_kin_name', css_class='form-group col-md-12 mb-3'),
                Column('next_of_kin_relationship', css_class='form-group col-md-12 mb-3'),
                Column('next_of_kin_location', css_class='form-group col-md-12 mb-3'),
                Column('next_of_kin_contact', css_class='form-group col-md-12 mb-3'),
                css_class='row'
            ),
            HTML('</div></div>'), # Close card-body and card

            # Skills & Languages Section
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-danger">
                    <div class="card-header bg-danger text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-lightbulb me-2"></i>Skills & Languages</h5>
                    </div>
                    <div class="card-body">
            '''),
            Row(
                Column('notable_skills', css_class='form-group col-md-12 mb-3'),
                Column('languages_spoken', css_class='form-group col-md-12 mb-3'),
                css_class='row'
            ),
            HTML('</div></div>'), # Close card-body and card

            # Note: Educational Qualifications (formset) will be rendered manually in the template,
            # as Crispy Forms doesn't handle inline formsets with custom layouts as elegantly.

            # Filter choices based on user role (if applicable, for station/regional HR)
            # This logic remains the same
        )

        if user:
            if user.is_station_level and user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(pk=user.prison_station.pk)
                self.fields['prison_station'].initial = user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = True
                self.fields['region'].queryset = Region.objects.filter(pk=user.prison_station.region.pk)
                self.fields['region'].initial = user.prison_station.region
                self.fields['region'].widget.attrs['readonly'] = True
            elif user.is_regional_level and user.region:
                self.fields['region'].queryset = Region.objects.filter(pk=user.region.pk)
                self.fields['region'].initial = user.region
                self.fields['region'].widget.attrs['readonly'] = True
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(region=user.region)
            # For national level, no filtering needed, they see all

    def clean(self):
        cleaned_data = super().clean()
        marital_status = cleaned_data.get('marital_status')
        spouse_name = cleaned_data.get('spouse_name')

        if marital_status == 'married' and not spouse_name:
            self.add_error('spouse_name', _("Spouse name is required if marital status is 'Married'."))
        return cleaned_data


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = ['institution', 'qualification', 'year_obtained', 'supporting_document']
        widgets = {
            'year_obtained': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('institution', css_class='form-group col-md-12 mb-3'),
            Column('qualification', css_class='form-group col-md-12 mb-3'),
            Column('year_obtained', css_class='form-group col-md-12 mb-3'),
            Column('supporting_document', css_class='form-group col-md-12 mb-3'),
        )


# Inline formset for Education to allow adding multiple education records
EducationFormSet = inlineformset_factory(Officer, Education, form=EducationForm, extra=1, can_delete=True)

class PromotionHistoryForm(forms.ModelForm):
    class Meta:
        model = PromotionHistory
        fields = ['previous_rank', 'new_rank', 'promotion_date', 'notes']
        widgets = {
            'promotion_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('previous_rank', css_class='form-group col-md-12 mb-3'),
            Column('new_rank', css_class='form-group col-md-12 mb-3'),
            Column('promotion_date', css_class='form-group col-md-12 mb-3'),
            Column('notes', css_class='form-group col-md-12 mb-3'),
        )

class TransferHistoryForm(forms.ModelForm):
    class Meta:
        model = TransferHistory
        fields = ['previous_station', 'new_station', 'transfer_date', 'notes']
        widgets = {
            'transfer_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('previous_station', css_class='form-group col-md-12 mb-3'),
            Column('new_station', css_class='form-group col-md-12 mb-3'),
            Column('transfer_date', css_class='form-group col-md-12 mb-3'),
            Column('notes', css_class='form-group col-md-12 mb-3'),
        )

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'number_of_days', 'supporting_document']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('leave_type', css_class='form-group col-md-12 mb-3'),
            Column('start_date', css_class='form-group col-md-12 mb-3'),
            Column('number_of_days', css_class='form-group col-md-12 mb-3'),
            Column('supporting_document', css_class='form-group col-md-12 mb-3'),
        )
        # Add JavaScript to dynamically update default_days based on selected leave_type
        self.fields['leave_type'].widget.attrs.update({'onchange': 'updateLeaveDays(this)'})

class LeaveApprovalForm(forms.ModelForm):
    """
    Form for approving or rejecting a leave request.
    """
    class Meta:
        model = LeaveRequest
        fields = ['status', 'rejection_notes']
        widgets = {
            'rejection_notes': forms.Textarea(attrs={'rows': 3}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('status', css_class='form-group col-md-12 mb-3'),
            Column('rejection_notes', css_class='form-group col-md-12 mb-3'),
        )

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_notes = cleaned_data.get('rejection_notes')

        if status == 'rejected' and not rejection_notes:
            self.add_error('rejection_notes', _("Rejection notes are required if the request is rejected."))
        return cleaned_data


class OfficerDocumentForm(forms.ModelForm):
    class Meta:
        model = OfficerDocument
        fields = ['file_name', 'file_number', 'file_type', 'document', 'notes','action_to']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('file_name', 'file_number', 'file_type', css_class='form-row'),
            Column('document', 'notes', css_class='form-row'),
            Column('action_to', css_class='form-group col-md-12 mb-3'),

        )

class OfficerFileResponseForm(forms.ModelForm):
    """
    Form for responding to an officer file (approving/rejecting).
    """
    class Meta:
        model = OfficerDocument
        fields = ['status', 'response_notes']
        widgets = {
            'response_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('status', css_class='form-group col-md-12 mb-3'),
            Column('response_notes', css_class='form-group col-md-12 mb-3'),
        )

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        notes = cleaned_data.get('notes')
        response_notes = cleaned_data.get('response_notes')


        return cleaned_data



class OfficerPerformanceForm(forms.ModelForm):
    class Meta:
        model = OfficerPerformance
        fields = ['metric', 'date', 'score', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('metric', css_class='form-group col-md-12 mb-3'),
            Column('date', css_class='form-group col-md-12 mb-3'),
            Column('score', css_class='form-group col-md-12 mb-3'),
            Column('notes', css_class='form-group col-md-12 mb-3'),
        )

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['date', 'status', 'remarks']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('date', css_class='form-group col-md-12 mb-3'),
            Column('status', css_class='form-group col-md-12 mb-3'),
            Column('remarks', css_class='form-group col-md-12 mb-3'),
        )

class DisciplinaryCaseForm(forms.ModelForm):
    class Meta:
        model = DisciplinaryCase
        fields = ['case_date', 'offense', 'description', 'action_taken', 'action_date']
        widgets = {
            'case_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'action_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('case_date', css_class='form-group col-md-12 mb-3'),
            Column('offense', css_class='form-group col-md-12 mb-3'),
            Column('description', css_class='form-group col-md-12 mb-3'),
            Column('action_taken', css_class='form-group col-md-12 mb-3'),
            Column('action_date', css_class='form-group col-md-12 mb-3'),
        )


class DisciplinaryCaseFileForm(forms.ModelForm):
    class Meta:
        model = DisciplinaryCaseFile
        fields = ['file_name', 'file']
        widgets = {
            'file_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter file description'}),
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.doc,.docx,.jpg,.jpeg,.png'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('file_name', css_class='form-group col-md-12 mb-3'),
            Column('file', css_class='form-group col-md-12 mb-3'),
        )


DisciplinaryCaseFileFormSet = forms.modelformset_factory(DisciplinaryCaseFile, form=DisciplinaryCaseFileForm, extra=1, can_delete=True)

class OfficeAssignmentForm(forms.ModelForm):
    class Meta:
        model = Officer
        fields = ['current_office_assignment']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Column('current_office_assignment', css_class='form-group col-md-12 mb-3'),
        )


# ========== TRAINING WING FORMS ==========

class TrainingIntakeForm(forms.ModelForm):
    """
    Form for creating and updating training intakes.
    Supports custom intake naming (e.g., "7th Intake", "Special Intake").
    """
    class Meta:
        model = TrainingIntake
        fields = [
            'intake_number', 'intake_suffix', 'custom_suffix', 'year',
            'start_date', 'pass_out_date', 'estimated_end_date', 'description',
            'is_active', 'last_pass_out_number'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'pass_out_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'estimated_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'last_pass_out_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 3499'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-primary">
                    <div class="card-header bg-primary text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-calendar-alt me-2"></i>Intake Information</h5>
                    </div>
                    <div class="card-body">
            '''),
            Row(
                Column('intake_number', css_class='form-group col-md-3 mb-3'),
                Column('intake_suffix', css_class='form-group col-md-3 mb-3'),
                Column('custom_suffix', css_class='form-group col-md-3 mb-3'),
                Column('year', css_class='form-group col-md-3 mb-3'),
                css_class='row'
            ),
            Row(
                Column('start_date', css_class='form-group col-md-4 mb-3'),
                Column('estimated_end_date', css_class='form-group col-md-4 mb-3'),
                Column('pass_out_date', css_class='form-group col-md-4 mb-3'),
                css_class='row'
            ),
            Column('description', css_class='form-group mb-3'),
            Row(
                Column('is_active', css_class='form-group col-md-6 mb-3'),
                Column('last_pass_out_number', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            HTML('</div></div>'),
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        estimated_end_date = cleaned_data.get('estimated_end_date')
        pass_out_date = cleaned_data.get('pass_out_date')

        if start_date and estimated_end_date and estimated_end_date <= start_date:
            self.add_error('estimated_end_date', _("Estimated end date must be after start date."))
        
        if start_date and pass_out_date and pass_out_date <= start_date:
            self.add_error('pass_out_date', _("Pass out date must be after start date."))

        if cleaned_data.get('intake_suffix') == 'custom' and not cleaned_data.get('custom_suffix'):
            self.add_error(
                'custom_suffix',
                _("Provide a custom suffix when the suffix is set to 'Custom'."),
            )

        return cleaned_data


class TrainingCourseForm(forms.ModelForm):
    """
    Form for creating and updating training courses.
    Simplified structure without modules.
    """
    
    class Meta:
        model = TrainingCourse
        fields = [
            'course_code', 'category', 'name', 'description', 'total_marks',
            'passing_mark', 'duration_hours', 'is_required', 'is_active',
        ]
        widgets = {
            'course_code': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'total_marks': forms.NumberInput(attrs={'class': 'form-control'}),
            'passing_mark': forms.NumberInput(attrs={'class': 'form-control'}),
            'duration_hours': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # The subject name is derived from the selected course code on save.
        self.fields['name'].required = False
        self.fields['name'].help_text = _(
            "Leave blank to use the standard curriculum name for the selected course."
        )

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-success">
                    <div class="card-header bg-success text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-book me-2"></i>Course Information</h5>
                    </div>
                    <div class="card-body">
            '''),
            Row(
                Column('course_code', css_class='form-group col-md-6 mb-3'),
                Column('category', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            Column('name', css_class='form-group mb-3'),
            Column('description', css_class='form-group mb-3'),
            Row(
                Column('total_marks', css_class='form-group col-md-4 mb-3'),
                Column('passing_mark', css_class='form-group col-md-4 mb-3'),
                Column('duration_hours', css_class='form-group col-md-4 mb-3'),
                css_class='row'
            ),
            Row(
                Column('is_required', css_class='form-group col-md-6 mb-3'),
                Column('is_active', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            HTML('''
                    </div>
                </div>
            '''),
        )

    def clean(self):
        cleaned_data = super().clean()
        total_marks = cleaned_data.get('total_marks')
        passing_mark = cleaned_data.get('passing_mark')

        if total_marks is not None and total_marks <= 0:
            self.add_error('total_marks', _("Total marks must be greater than zero."))

        if passing_mark is not None:
            if passing_mark < 0:
                self.add_error('passing_mark', _("Passing mark cannot be negative."))
            elif total_marks is not None and passing_mark > total_marks:
                self.add_error(
                    'passing_mark',
                    _("Passing mark cannot be greater than the total marks."),
                )

        return cleaned_data


class RecruitForm(forms.ModelForm):
    """
    Form for creating and updating recruits.
    Training ID is auto-generated on save.
    """
    class Meta:
        model = Recruit
        fields = [
            'intake', 'first_name', 'middle_name', 'surname',
            'date_of_birth', 'gender', 'recruit_type', 'status',
            'contact_number', 'email', 'home_district',
            'next_of_kin', 'next_of_kin_relationship', 
            'next_of_kin_contact', 'next_of_kin_address'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+265...'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'recruit@example.com'}),
            'home_district': forms.TextInput(attrs={'class': 'form-control'}),
            'next_of_kin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name of next of kin'}),
            'next_of_kin_relationship': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Father, Mother, Spouse'}),
            'next_of_kin_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+265...'}),
            'next_of_kin_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Physical address of next of kin'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        intake_pk = kwargs.pop('intake_pk', None)
        super().__init__(*args, **kwargs)
        
        # Filter choices based on intake if provided
        if intake_pk:
            self.fields['intake'].initial = intake_pk
            self.fields['intake'].widget = forms.HiddenInput()

        for field_name in ('next_of_kin', 'next_of_kin_relationship', 'next_of_kin_contact', 'next_of_kin_address'):
            self.fields[field_name].required = True

        # Status defaults to the recruit's current value (or "enrolled") when the
        # template does not expose it.
        self.fields['status'].required = False
        self.fields['status'].widget.attrs['class'] = 'form-select'

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-warning">
                    <div class="card-header bg-warning text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-user-graduate me-2"></i>Personal Information</h5>
                    </div>
                    <div class="card-body">
            '''),
            Column('intake', css_class='form-group mb-3'),
            Row(
                Column('first_name', css_class='form-group col-md-4 mb-3'),
                Column('middle_name', css_class='form-group col-md-4 mb-3'),
                Column('surname', css_class='form-group col-md-4 mb-3'),
                css_class='row'
            ),
            Row(
                Column('date_of_birth', css_class='form-group col-md-4 mb-3'),
                Column('gender', css_class='form-group col-md-4 mb-3'),
                Column('recruit_type', css_class='form-group col-md-4 mb-3'),
                css_class='row'
            ),
            HTML('</div></div>'),
            
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-secondary">
                    <div class="card-header bg-secondary text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-address-card me-2"></i>Contact Information</h5>
                    </div>
                    <div class="card-body">
            '''),
            Row(
                Column('contact_number', css_class='form-group col-md-6 mb-3'),
                Column('email', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            Column('home_district', css_class='form-group mb-3'),
            Column('status', css_class='form-group mb-3'),
            HTML('</div></div>'),
        )

    def clean_status(self):
        status = self.cleaned_data.get('status')
        if status:
            return status
        return self.instance.status or 'enrolled'

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get('date_of_birth')
        if date_of_birth:
            today = date.today()
            age = today.year - date_of_birth.year
            if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
                age -= 1
            if age < 18:
                raise forms.ValidationError(_("Recruit must be at least 18 years old."))
            if age > 60:
                raise forms.ValidationError(_("Recruit exceeds maximum age limit of 60 years."))
        return date_of_birth


class RecruitMarkForm(forms.ModelForm):
    """
    Form for adding/editing marks for a recruit in a specific course.
    """
    class Meta:
        model = RecruitMark
        fields = ['course', 'obtained_marks', 'exam_date', 'remarks']
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'obtained_marks': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop('recruit', None)
        self.course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)

        self.fields['course'].queryset = TrainingCourse.objects.filter(
            is_active=True
        ).order_by('course_code')

        if self.course is not None:
            # The course is fixed by the caller, so the template need not post it.
            self.fields['course'].required = False

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-danger">
                    <div class="card-header bg-danger text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-chart-line me-2"></i>Mark Entry</h5>
                    </div>
                    <div class="card-body">
            '''),
            Column('course', css_class='form-group mb-3'),
            Row(
                Column('obtained_marks', css_class='form-group col-md-6 mb-3'),
                Column('exam_date', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            Column('remarks', css_class='form-group mb-3'),
            HTML('</div></div>'),
        )

    def clean_course(self):
        return self.cleaned_data.get('course') or self.course

    def clean(self):
        cleaned_data = super().clean()
        obtained_marks = cleaned_data.get('obtained_marks')
        course = cleaned_data.get('course') or self.course

        if obtained_marks is not None and course:
            if obtained_marks < 0:
                self.add_error('obtained_marks', _("Marks cannot be negative."))
            elif obtained_marks > course.total_marks:
                self.add_error('obtained_marks', 
                    _("Marks cannot exceed course total marks of {}.").format(course.total_marks))

        return cleaned_data


class BulkMarksForm(forms.Form):
    """
    Form for bulk marks entry across multiple recruits.
    """
    module = forms.ModelChoiceField(  # Keep as module for template compatibility
        queryset=TrainingCourse.objects.none(),
        label=_("Select Course"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    exam_date = forms.DateField(
        label=_("Exam Date"),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        if course:
            self.fields['module'].queryset = TrainingCourse.objects.filter(
                is_active=True
            ).order_by('course_code')


class IntakeGraduationForm(forms.Form):
    """Ceremony details captured when passing out an intake."""

    graduation_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label=_("Graduation Date"),
    )
    ceremony_location = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_("Ceremony Location"),
    )


class GraduationBatchForm(forms.ModelForm):
    """
    Form for creating a graduation batch and assigning service numbers.
    """
    class Meta:
        model = GraduationBatch
        fields = [
            'intake', 'graduation_date', 'ceremony_location',
            'service_number_start', 'service_number_end'
        ]
        widgets = {
            'graduation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'ceremony_location': forms.TextInput(attrs={'class': 'form-control'}),
            'service_number_start': forms.NumberInput(attrs={'class': 'form-control'}),
            'service_number_end': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-success">
                    <div class="card-header bg-success text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-graduation-cap me-2"></i>Graduation Information</h5>
                    </div>
                    <div class="card-body">
            '''),
            Column('intake', css_class='form-group mb-3'),
            Row(
                Column('graduation_date', css_class='form-group col-md-6 mb-3'),
                Column('ceremony_location', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            Row(
                Column('service_number_start', css_class='form-group col-md-6 mb-3'),
                Column('service_number_end', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            HTML('</div></div>'),
        )


class CourseEnrollmentForm(forms.ModelForm):
    """
    Form for enrolling an officer in a training course (for refresher tracking).
    """
    class Meta:
        model = CourseEnrollment
        fields = ['course', 'completion_date', 'score', 'certificate_issued', 'certificate_number']
        widgets = {
            'completion_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 100}),
            'certificate_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('''
                <div class="card shadow-sm rounded-3 mb-4 border-info">
                    <div class="card-header bg-info text-white rounded-top-3">
                        <h5 class="mb-0"><i class="fas fa-certificate me-2"></i>Course Enrollment</h5>
                    </div>
                    <div class="card-body">
            '''),
            Column('course', css_class='form-group mb-3'),
            Row(
                Column('completion_date', css_class='form-group col-md-6 mb-3'),
                Column('score', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            Row(
                Column('certificate_issued', css_class='form-group col-md-6 mb-3'),
                Column('certificate_number', css_class='form-group col-md-6 mb-3'),
                css_class='row'
            ),
            HTML('</div></div>'),
        )


# Note: TrainingModuleFormSet removed since TrainingModule and TrainingCourse now have ManyToMany relationship

# Inline formset for marks within a recruit
RecruitMarkFormSet = inlineformset_factory(
    Recruit,
    RecruitMark,
    form=RecruitMarkForm,
    extra=1,
    can_delete=True,
    fields=['course', 'obtained_marks', 'exam_date', 'remarks']
)


class BulkMarkImportForm(forms.ModelForm):
    """
    Form for uploading bulk mark import files (CSV or Excel).
    Allows training coordinators to import marks in batch for multiple recruits.
    """
    class Meta:
        model = BulkMarkImport
        fields = ['intake', 'import_file', 'file_type']
        widgets = {
            'intake': forms.Select(attrs={'class': 'form-control'}),
            'file_type': forms.RadioSelect(choices=[
                ('csv', 'CSV File (.csv)'),
                ('excel', 'Excel File (.xlsx/.xls)'),
            ]),
            'import_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv,.xlsx,.xls'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                _('Bulk Mark Import'),
                'intake',
                'file_type',
                'import_file',
                HTML('''
                    <div class="alert alert-info mt-3">
                        <i class="fas fa-info-circle me-2"></i>
                        <strong>CSV Format Requirements:</strong>
                        <ul class="mb-0 mt-2">
                            <li><strong>Column 1:</strong> Training ID (e.g., R-022/001)</li>
                            <li><strong>Column 2:</strong> Course Code (e.g., history_organisation)</li>
                            <li><strong>Column 3:</strong> Obtained Marks (0-100)</li>
                            <li><strong>Column 4:</strong> Exam Date (YYYY-MM-DD)</li>
                        </ul>
                    </div>
                '''),
                Submit('submit', _('Import Marks'), css_class='btn btn-primary mt-3')
            )
        )

    def clean_import_file(self):
        import_file = self.cleaned_data.get('import_file')
        if import_file:
            # Validate file size (max 5MB)
            if import_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError(_("File size must be less than 5MB."))
            
            # Validate file extension
            allowed_extensions = ['csv', 'xlsx', 'xls']
            file_ext = import_file.name.split('.')[-1].lower()
            if file_ext not in allowed_extensions:
                raise forms.ValidationError(_("File must be CSV or Excel format."))
        
        return import_file
