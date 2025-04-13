from django import forms
from .models import UtilityReading, UtilityBill, HealthRecord, ScheduledAppointment
from django.utils import timezone


class UtilityReadingForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date()
    )

    class Meta:
        model = UtilityReading
        fields = ['utility_type', 'date', 'reading_value', 'unit', 'meter_id', 'notes']
        widgets = {
            'utility_type': forms.Select(attrs={'class': 'form-select'}),
            'reading_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'meter_id': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class UtilityBillForm(forms.ModelForm):
    billing_period_start = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    billing_period_end = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    paid_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = UtilityBill
        fields = [
            'utility_type', 'billing_period_start', 'billing_period_end',
            'consumption', 'unit', 'unit_rate', 'fixed_charges', 'total_amount',
            'invoice_number', 'due_date', 'paid_date', 'payment_status', 'notes'
        ]
        widgets = {
            'utility_type': forms.Select(attrs={'class': 'form-select'}),
            'consumption': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'unit_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fixed_charges': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        billing_start = cleaned_data.get('billing_period_start')
        billing_end = cleaned_data.get('billing_period_end')
        due_date = cleaned_data.get('due_date')
        paid_date = cleaned_data.get('paid_date')
        payment_status = cleaned_data.get('payment_status')

        if billing_start and billing_end and billing_start > billing_end:
            raise forms.ValidationError("Billing period start date cannot be after end date.")

        if due_date and billing_end and due_date < billing_end:
            raise forms.ValidationError("Due date should be after the billing period end date.")

        if paid_date and payment_status != 'paid':
            cleaned_data['payment_status'] = 'paid'

        # Calculate total amount if not set
        consumption = cleaned_data.get('consumption')
        unit_rate = cleaned_data.get('unit_rate')
        fixed_charges = cleaned_data.get('fixed_charges')

        if consumption and unit_rate and fixed_charges:
            calculated_total = (consumption * float(unit_rate)) + float(fixed_charges)
            cleaned_data['total_amount'] = calculated_total

        return cleaned_data


class HealthRecordForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date()
    )
    follow_up_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = HealthRecord
        fields = [
            'buffalo', 'date', 'record_type', 'description', 'vet_name',
            'medication_used', 'medication_cost', 'service_cost', 'total_cost',
            'follow_up_date', 'notes'
        ]
        widgets = {
            'buffalo': forms.Select(attrs={'class': 'form-select'}),
            'record_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'vet_name': forms.TextInput(attrs={'class': 'form-control'}),
            'medication_used': forms.TextInput(attrs={'class': 'form-control'}),
            'medication_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'service_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        medication_cost = cleaned_data.get('medication_cost') or 0
        service_cost = cleaned_data.get('service_cost') or 0

        # Calculate total cost
        total_cost = medication_cost + service_cost
        cleaned_data['total_cost'] = total_cost

        # Validate follow_up_date
        date = cleaned_data.get('date')
        follow_up_date = cleaned_data.get('follow_up_date')

        if follow_up_date and date and follow_up_date <= date:
            raise forms.ValidationError("Follow-up date must be after the treatment date.")

        return cleaned_data


class ScheduledAppointmentForm(forms.ModelForm):
    scheduled_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    scheduled_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = ScheduledAppointment
        fields = [
            'buffalo', 'appointment_type', 'scheduled_date', 'scheduled_time',
            'description', 'vet_name', 'status', 'notes'
        ]
        widgets = {
            'buffalo': forms.Select(attrs={'class': 'form-select'}),
            'appointment_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'vet_name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        scheduled_date = cleaned_data.get('scheduled_date')
        status = cleaned_data.get('status')

        # Check if scheduled date is in the past and status is still 'scheduled'
        if scheduled_date and scheduled_date < timezone.now().date() and status == 'scheduled':
            self.add_warning("The scheduled date has passed. Consider updating the status.")

        return cleaned_data

    def add_warning(self, message):
        """Add a non-blocking warning message that will be displayed to the user."""
        if not hasattr(self, 'warnings'):
            self.warnings = []
        self.warnings.append(message)


class CompleteAppointmentForm(forms.Form):
    """Form to quickly complete an appointment and create a health record."""
    record_type = forms.ChoiceField(
        choices=HealthRecord.RECORD_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    vet_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False
    )
    medication_used = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False
    )
    medication_cost = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        required=False,
        initial=0
    )
    service_cost = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        required=False,
        initial=0
    )
    follow_up_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )