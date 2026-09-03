from django import forms
from .models import ReturnTemplate, ReturnSubmission
from prison.models import PrisonStation
from datetime import date
from django.utils import timezone


class ReturnSubmissionForm(forms.ModelForm):
    class Meta:
        model = ReturnSubmission
        fields = ['template', 'prison_station', 'file', 'period', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional notes about this submission...'}),
            'period': forms.TextInput(attrs={'type': 'month', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and not self.user.is_superuser:
            if hasattr(self.user, 'prison_station') and self.user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(pk=self.user.prison_station.pk)
                self.fields['prison_station'].initial = self.user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = True
                self.fields['prison_station'].widget.attrs['disabled'] = True

        # Set default period to current month
        from django.utils import timezone
        self.fields['period'].initial = timezone.now().strftime('%Y-%m')


class ReturnTemplateForm(forms.ModelForm):
    class Meta:
        model = ReturnTemplate
        fields = ['name', 'category', 'description', 'template_file', 'required_columns', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'required_columns': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Enter column names separated by commas: Name,Age,Sex,Offense,Court,Case No,Sentence,Date of Committal,Expiry Date'
            }),
        }

    def clean_required_columns(self):
        data = self.cleaned_data.get('required_columns', [])
        if isinstance(data, str):
            # Handle text input format
            columns = [col.strip() for col in data.split(',') if col.strip()]
            return columns
        return data


class ReturnsFilterForm(forms.Form):
    """
    Form for filtering returns.
    """
    CATEGORY_CHOICES = [
        ('', 'All Categories'),
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

    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    period = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 2026-11', 'type': 'month'}),
        label='Period (YYYY-MM)'
    )
    year = forms.ChoiceField(
        choices=[(str(y), str(y)) for y in range(2020, 2031)],
        required=False,
        label='Year'
    )
    month = forms.ChoiceField(
        choices=[('', 'All Months')] + [(str(m), date(2000, m, 1).strftime('%B')) for m in range(1, 13)],
        required=False,
        label='Month'
    )
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, required=False, label='Category')
    prison_station = forms.ModelChoiceField(
        queryset=PrisonStation.objects.all(),
        required=False,
        label='Prison Station'
    )
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False, label='Status')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and not self.user.is_superuser:
            if hasattr(self.user, 'prison_station') and self.user.prison_station:
                self.fields['prison_station'].queryset = PrisonStation.objects.filter(pk=self.user.prison_station.pk)
                self.fields['prison_station'].initial = self.user.prison_station
                self.fields['prison_station'].widget.attrs['readonly'] = True
                self.fields['prison_station'].widget.attrs['disabled'] = True


class PeriodSelectionForm(forms.Form):
    """
    Form for selecting a reporting period.
    """
    period = forms.CharField(
        widget=forms.TextInput(attrs={'type': 'month', 'class': 'form-control'}),
        label='Reporting Period'
    )
    category = forms.ChoiceField(
        choices=ReturnsFilterForm.CATEGORY_CHOICES,
        required=False,
        label='Category'
    )


class MonthlyTrackingForm(forms.Form):
    """
    Form for initializing monthly tracking.
    """
    year = forms.ChoiceField(
        choices=[(str(y), str(y)) for y in range(2020, 2031)],
        initial=str(timezone.now().year)
    )
    month = forms.ChoiceField(
        choices=[(str(m), date(2000, m, 1).strftime('%B')) for m in range(1, 13)],
        initial=str(timezone.now().month)
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['year'].initial = str(timezone.now().year)
        self.fields['month'].initial = str(timezone.now().month)