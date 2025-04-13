"""
finance/forms.py

This file contains Django forms for managing finance-related models.
Each form includes inline comments to explain how fields are enhanced with Bootstrap classes,
how custom fields are dynamically added based on definitions, and how calculations are performed.
"""

from django import forms
from .models import ExpenseRecord, IncomeRecord, ExpenseCategory, IncomeCategory
from configuration.models import CustomFieldDefinition, GlobalSettings
from herd.models import Buffalo
from datetime import date, datetime


# ---------------- Expense Category Form ----------------
class ExpenseCategoryForm(forms.ModelForm):
    """
    Form for creating/editing an ExpenseCategory.
    Applies Bootstrap classes to enhance the UI.
    """

    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description', 'is_direct_cost']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to each field widget.
        for field in self.fields:
            if field == 'is_direct_cost':
                self.fields[field].widget.attrs.update({'class': 'form-check-input'})
            else:
                self.fields[field].widget.attrs.update({'class': 'form-control'})


# ---------------- Income Category Form ----------------
class IncomeCategoryForm(forms.ModelForm):
    """
    Form for creating/editing an IncomeCategory.
    """

    class Meta:
        model = IncomeCategory
        fields = ['name', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap styling to all fields.
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})


# ---------------- Expense Record Form ----------------
class ExpenseRecordForm(forms.ModelForm):
    """
    Form for creating/editing an ExpenseRecord.
    Dynamically adds any custom fields defined for the "EXPENSE" target model.
    """

    class Meta:
        model = ExpenseRecord
        fields = ['date', 'category', 'description', 'amount', 'related_buffalo',
                  'supplier_vendor', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap class to each widget.
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        # Limit the related_buffalo queryset to only active buffaloes.
        self.fields['related_buffalo'].queryset = Buffalo.objects.filter(is_active=True)

        # Dynamically add custom fields based on the CustomFieldDefinition for expenses.
        custom_fields = CustomFieldDefinition.objects.filter(target_model='EXPENSE')
        for cf in custom_fields:
            field_name = f"custom_{cf.field_name}"
            # Check if editing an instance that already has a stored value.
            initial_value = None
            if self.instance.pk and cf.field_name in self.instance.custom_data:
                initial_value = self.instance.custom_data.get(cf.field_name)
            # Depending on the field type, create the proper form field.
            if cf.field_type == 'TEXT':
                self.fields[field_name] = forms.CharField(
                    label=cf.field_label,
                    required=cf.is_required,
                    initial=initial_value,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
            elif cf.field_type == 'NUMBER':
                self.fields[field_name] = forms.DecimalField(
                    label=cf.field_label,
                    required=cf.is_required,
                    initial=initial_value,
                    widget=forms.NumberInput(attrs={'class': 'form-control'})
                )
            elif cf.field_type == 'DATE':
                self.fields[field_name] = forms.DateField(
                    label=cf.field_label,
                    required=cf.is_required,
                    initial=initial_value,
                    widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
                )
            elif cf.field_type == 'BOOLEAN':
                self.fields[field_name] = forms.BooleanField(
                    label=cf.field_label,
                    required=cf.is_required,
                    initial=initial_value,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )

    def save(self, commit=True):
        # Save the standard fields first.
        instance = super().save(commit=False)
        # Ensure custom_data is a dictionary.
        if not instance.custom_data:
            instance.custom_data = {}
        # Update the instance's custom_data with the custom field values.
        custom_fields = CustomFieldDefinition.objects.filter(target_model='EXPENSE')
        for cf in custom_fields:
            field_name = f"custom_{cf.field_name}"
            if field_name in self.cleaned_data:
                value = self.cleaned_data[field_name]
                # If the value is a date/datetime, store it in ISO format.
                if isinstance(value, (datetime, date)):
                    value = value.isoformat()
                instance.custom_data[cf.field_name] = value
        if commit:
            instance.save()
        return instance


# ---------------- Income Record Form ----------------
class IncomeRecordForm(forms.ModelForm):
    """
    Form for creating/editing an IncomeRecord.
    Also dynamically adds custom fields defined for the "INCOME" target model.
    Auto-calculates total_amount if not provided.
    """

    class Meta:
        model = IncomeRecord
        fields = ['date', 'category', 'description', 'quantity', 'unit_price', 'total_amount',
                  'related_buffalo', 'customer', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap styling to each field.
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        # Limit the dropdown to only active buffaloes.
        self.fields['related_buffalo'].queryset = Buffalo.objects.filter(is_active=True)
        # Set default milk price from GlobalSettings if creating a new record.
        settings = GlobalSettings.objects.first()
        if settings and not self.instance.pk:
            self.fields['unit_price'].initial = settings.default_milk_price_per_litre
        # Add any custom fields defined for income.
        custom_fields = CustomFieldDefinition.objects.filter(target_model='INCOME')
        for cf in custom_fields:
            field_name = f"custom_{cf.field_name}"
            initial_value = None
            if self.instance.pk and cf.field_name in self.instance.custom_data:
                initial_value = self.instance.custom_data.get(cf.field_name)
            if cf.field_type == 'TEXT':
                self.fields[field_name] = forms.CharField(
                    label=cf.field_label,
                    required=cf.is_required,
                    initial=initial_value,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
            elif cf.field_type == 'NUMBER':
                self.fields[field_name] = forms.DecimalField(
                    label=cf.field_label,
                    required=cf.is_required,
                    initial=initial_value,
                    widget=forms.NumberInput(attrs={'class': 'form-control'})
                )
            elif cf.field_type == 'DATE':
                self.fields[field_name] = forms.DateField(
                    label=cf.field_label,
                    required=cf.is_required,
                    initial=initial_value,
                    widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
                )
            elif cf.field_type == 'BOOLEAN':
                self.fields[field_name] = forms.BooleanField(
                    label=cf.field_label,
                    required=cf.is_required,
                    initial=initial_value,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('unit_price')
        total_amount = cleaned_data.get('total_amount')
        # If both quantity and unit_price are provided, calculate total_amount if it is empty or zero.
        if quantity and unit_price and (not total_amount or total_amount == 0):
            cleaned_data['total_amount'] = quantity * unit_price
        # If total_amount is absent and either quantity or unit_price is missing, raise an error.
        if not total_amount and (not quantity or not unit_price):
            self.add_error('total_amount', 'Please provide either Total Amount or both Quantity and Unit Price')
        return cleaned_data

    def save(self, commit=True):
        # Save standard fields.
        instance = super().save(commit=False)
        if self.cleaned_data.get('quantity') and self.cleaned_data.get('unit_price') and (
        not self.cleaned_data.get('total_amount')):
            instance.total_amount = self.cleaned_data['quantity'] * self.cleaned_data['unit_price']
        if not instance.custom_data:
            instance.custom_data = {}
        # Save custom field values into the instance's custom_data dictionary.
        custom_fields = CustomFieldDefinition.objects.filter(target_model='INCOME')
        for cf in custom_fields:
            field_name = f"custom_{cf.field_name}"
            if field_name in self.cleaned_data:
                value = self.cleaned_data[field_name]
                if isinstance(value, (datetime, date)):
                    value = value.isoformat()
                instance.custom_data[cf.field_name] = value
        if commit:
            instance.save()
        return instance


# ---------------- Milk Income Generator Form ----------------
class MilkIncomeGeneratorForm(forms.Form):
    """
    Form to automatically generate income records based on milk production data.
    This form collects a date range, milk price, and optional customer details.
    """
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    milk_price = forms.DecimalField(
        min_value=0.01,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    customer = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the default milk price based on GlobalSettings.
        settings = GlobalSettings.objects.first()
        if settings:
            self.fields['milk_price'].initial = settings.default_milk_price_per_litre
