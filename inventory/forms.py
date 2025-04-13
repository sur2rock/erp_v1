"""
Forms for the Inventory app in Super Duper Dairy ERP System

This module defines custom forms for the inventory management system,
including validation logic and UI enhancements.
"""

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    FodderType,
    FeedInventory,
    FeedPurchase,
    FeedConsumption,
    InHouseFeedProduction
)

try:
    from finance.models import ExpenseRecord
    FINANCE_MODELS_EXIST = True
except ImportError:
    FINANCE_MODELS_EXIST = False

try:
    from herd.models import Buffalo
    BUFFALO_MODEL_EXISTS = True
except ImportError:
    BUFFALO_MODEL_EXISTS = False


class FodderTypeForm(forms.ModelForm):
    """Form for creating and editing fodder types"""

    class Meta:
        model = FodderType
        fields = [
            'name', 'category', 'unit', 'current_cost_per_unit',
            'is_produced_in_house', 'nutrient_info', 'min_stock_level',
            'costing_method'
        ]
        widgets = {
            'nutrient_info': forms.Textarea(attrs={'rows': 3}),
            'current_cost_per_unit': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'min_stock_level': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()

        # Validate that produced in-house fodder has min stock level
        is_produced = cleaned_data.get('is_produced_in_house')
        min_stock = cleaned_data.get('min_stock_level')

        if is_produced and (min_stock is None or min_stock <= 0):
            self.add_error('min_stock_level',
                _("In-house produced fodder should have a minimum stock level defined."))

        return cleaned_data


class FeedInventoryForm(forms.ModelForm):
    """Form for managing feed inventory levels"""

    adjust_quantity = forms.DecimalField(
        required=False,
        label=_("Adjust Quantity (+/-)"),
        help_text=_("Enter a positive or negative value to adjust the inventory. Leave blank to set exact value."),
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )

    adjustment_reason = forms.CharField(
        required=False,
        label=_("Reason for Adjustment"),
        widget=forms.Textarea(attrs={'rows': 2}),
        help_text=_("Provide a reason if making a manual adjustment")
    )

    class Meta:
        model = FeedInventory
        fields = ['fodder_type', 'quantity_on_hand', 'location', 'notes']
        widgets = {
            'quantity_on_hand': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If editing existing inventory, populate adjustment fields
        if self.instance and self.instance.pk:
            self.fields['adjust_quantity'].initial = 0
            # Make the direct quantity_on_hand field read-only for existing records
            self.fields['quantity_on_hand'].widget.attrs['readonly'] = True
        else:
            # For new records, hide adjustment fields
            self.fields['adjust_quantity'].widget = forms.HiddenInput()
            self.fields['adjustment_reason'].widget = forms.HiddenInput()

    def clean(self):
        """Validate form data and handle quantity adjustments"""
        cleaned_data = super().clean()

        # Handle quantity adjustments for existing records
        if self.instance and self.instance.pk:
            quantity = cleaned_data.get('quantity_on_hand', 0)
            adjustment = cleaned_data.get('adjust_quantity')

            if adjustment:
                # User is adjusting by a relative amount
                new_quantity = quantity + adjustment
                if new_quantity < 0:
                    self.add_error('adjust_quantity',
                        _("Adjustment would result in negative inventory"))
                else:
                    cleaned_data['quantity_on_hand'] = new_quantity

                # Require reason for significant adjustments
                reason = cleaned_data.get('adjustment_reason', '')
                if abs(adjustment) > (quantity * 0.1) and not reason:  # >10% change
                    self.add_error('adjustment_reason',
                        _("Please provide a reason for significant inventory adjustments"))

        return cleaned_data

    def save(self, commit=True):
        """Override save to handle manual inventory adjustments"""
        instance = super().save(commit=False)

        # Create inventory transaction for manual adjustments
        adjustment = self.cleaned_data.get('adjust_quantity')
        if self.instance.pk and adjustment and commit:
            from .models import InventoryTransaction

            # Record the transaction
            InventoryTransaction.objects.create(
                fodder_type=instance.fodder_type,
                transaction_type='ADJUSTMENT',
                date=timezone.now().date(),
                quantity=adjustment,  # Can be positive or negative
                unit_value=instance.fodder_type.current_cost_per_unit,
                total_value=adjustment * instance.fodder_type.current_cost_per_unit,
                previous_balance=self.instance.quantity_on_hand,
                new_balance=instance.quantity_on_hand,
                notes=f"Manual adjustment: {self.cleaned_data.get('adjustment_reason', 'No reason provided')}"
            )

        if commit:
            instance.save()
        return instance


class FeedPurchaseForm(forms.ModelForm):
    """Form for recording feed purchases"""

    class Meta:
        model = FeedPurchase
        fields = [
            'fodder_type', 'date', 'supplier', 'quantity_purchased',
            'cost_per_unit', 'invoice_number', 'payment_status', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'quantity_purchased': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'cost_per_unit': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default date to today
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()

        # Filter fodder types to exclude those produced in-house only
        self.fields['fodder_type'].queryset = FodderType.objects.all()

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()

        # Calculate total cost for display
        quantity = cleaned_data.get('quantity_purchased')
        cost_per_unit = cleaned_data.get('cost_per_unit')

        if quantity and cost_per_unit:
            total_cost = quantity * cost_per_unit
            # This is just for display - the actual calculation happens in the model
            self.instance.total_cost = total_cost

        return cleaned_data


class FeedConsumptionForm(forms.ModelForm):
    """Form for recording feed consumption"""

    class Meta:
        model = FeedConsumption
        fields = [
            'fodder_type', 'date', 'quantity_consumed', 'consumed_by',
            'specific_buffalo', 'group_name', 'notes'
        ] if BUFFALO_MODEL_EXISTS else [
            'fodder_type', 'date', 'quantity_consumed', 'consumed_by',
            'group_name', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'quantity_consumed': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default date to today
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()

        # Dynamic field customization based on consumed_by
        if 'specific_buffalo' in self.fields and BUFFALO_MODEL_EXISTS:
            self.fields['specific_buffalo'].queryset = Buffalo.objects.filter(
                is_active=True
            )

        # Add help text for group name
        if 'group_name' in self.fields:
            self.fields['group_name'].help_text = _("Required if 'Consumed By' is set to 'Specific Group'")

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()

        # Validate based on consumed_by selection
        consumed_by = cleaned_data.get('consumed_by')
        specific_buffalo = cleaned_data.get('specific_buffalo')
        group_name = cleaned_data.get('group_name')

        if consumed_by == 'INDIVIDUAL' and 'specific_buffalo' in self.fields and not specific_buffalo:
            self.add_error('specific_buffalo', _("Please select a buffalo for individual consumption"))

        if consumed_by == 'GROUP' and not group_name:
            self.add_error('group_name', _("Please enter a group name for group consumption"))

        # Validate available inventory
        fodder_type = cleaned_data.get('fodder_type')
        quantity = cleaned_data.get('quantity_consumed')

        if fodder_type and quantity:
            try:
                inventory = FeedInventory.objects.get(fodder_type=fodder_type)
                if inventory.quantity_on_hand < quantity:
                    self.add_error('quantity_consumed',
                        _("Cannot consume more than available inventory. Available: {} {}").format(
                            inventory.quantity_on_hand, fodder_type.unit))
            except FeedInventory.DoesNotExist:
                self.add_error('fodder_type',
                    _("No inventory record exists for this fodder type"))

        return cleaned_data


class InHouseFeedProductionForm(forms.ModelForm):
    """Form for recording in-house feed production"""

    expense_selection = forms.CharField(
        required=False,
        label=_("Associated Expenses"),
        widget=forms.Textarea(attrs={'rows': 2}),
        help_text=_("Enter expense IDs separated by commas (e.g., '12,15,22')")
    )

    class Meta:
        model = InHouseFeedProduction
        fields = [
            'fodder_type', 'date', 'quantity_produced',
            'production_location', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'quantity_produced': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default date to today
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()

        # Filter fodder types to only show those that can be produced in-house
        self.fields['fodder_type'].queryset = FodderType.objects.filter(
            is_produced_in_house=True
        )

        # If editing existing record, populate expense selection
        if self.instance.pk and self.instance.associated_costs:
            expense_ids = ','.join(str(k) for k in self.instance.associated_costs.keys())
            self.fields['expense_selection'].initial = expense_ids

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()

        # Validate fodder type is produced in-house
        fodder_type = cleaned_data.get('fodder_type')
        if fodder_type and not fodder_type.is_produced_in_house:
            self.add_error('fodder_type',
                _("This fodder type is not marked as producible in-house"))

        # Process associated expenses
        expense_ids = cleaned_data.get('expense_selection', '')
        associated_costs = {}

        if expense_ids and FINANCE_MODELS_EXIST:
            try:
                # Parse comma-separated expense IDs
                ids = [int(id.strip()) for id in expense_ids.split(',') if id.strip()]

                # Create a dictionary of expense_id: amount pairs
                for expense_id in ids:
                    try:
                        expense = ExpenseRecord.objects.get(id=expense_id)
                        associated_costs[str(expense_id)] = float(expense.amount)
                    except ExpenseRecord.DoesNotExist:
                        self.add_error('expense_selection',
                            _("Expense ID {} does not exist").format(expense_id))

            except ValueError:
                self.add_error('expense_selection',
                    _("Invalid expense ID format. Use comma-separated numbers only."))

        # Store the associated costs in the proper field
        cleaned_data['associated_costs'] = associated_costs

        return cleaned_data

    def save(self, commit=True):
        """Override save to handle associated_costs"""
        instance = super().save(commit=False)

        # Set associated costs
        instance.associated_costs = self.cleaned_data.get('associated_costs', {})

        # Calculate total production cost
        total_cost = sum(float(amount) for amount in instance.associated_costs.values())
        instance.total_production_cost = total_cost

        # Calculate cost per unit if quantity is positive
        if instance.quantity_produced > 0:
            instance.cost_per_unit = total_cost / instance.quantity_produced
        else:
            instance.cost_per_unit = 0

        if commit:
            instance.save()

        return instance


class BatchMilkConsumptionForm(forms.Form):
    """Form for recording feed consumption for multiple animals at once"""

    date = forms.DateField(
        label=_("Consumption Date"),
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=timezone.now().date()
    )

    fodder_type = forms.ModelChoiceField(
        label=_("Fodder Type"),
        queryset=FodderType.objects.all(),
        help_text=_("Select the type of feed consumed")
    )

    quantity_per_animal = forms.DecimalField(
        label=_("Quantity Per Animal"),
        min_value=0.01,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
        help_text=_("Amount given to each animal")
    )

    group = forms.ChoiceField(
        label=_("Animal Group"),
        choices=[
            ('MILKING', _("Milking")),
            ('DRY', _("Dry")),
            ('PREGNANT', _("Pregnant")),
            ('CALVES', _("Calves")),
            ('ALL', _("All Animals")),
        ],
        help_text=_("Select which group of animals consumed this feed")
    )

    notes = forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text=_("Any additional notes about this consumption")
    )

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()

        # Ensure buffalo model exists
        if not BUFFALO_MODEL_EXISTS:
            raise ValidationError(_("The herd module is not available"))

        # Ensure sufficient inventory
        fodder_type = cleaned_data.get('fodder_type')
        quantity_per_animal = cleaned_data.get('quantity_per_animal')
        group = cleaned_data.get('group')

        if fodder_type and quantity_per_animal and group:
            # Get count of animals in the selected group
            animal_count = 0

            if group == 'ALL':
                animal_count = Buffalo.objects.filter(is_active=True).count()
            elif group == 'MILKING':
                animal_count = Buffalo.objects.filter(is_active=True, status='Active-Milking').count()
            elif group == 'DRY':
                animal_count = Buffalo.objects.filter(is_active=True, status='Active-Dry').count()
            elif group == 'PREGNANT':
                animal_count = Buffalo.objects.filter(is_active=True, status='Active-Pregnant').count()
            elif group == 'CALVES':
                animal_count = Buffalo.objects.filter(is_active=True, status__in=['Calf', 'Heifer']).count()

            # Calculate total consumption
            total_quantity = quantity_per_animal * animal_count

            # Validate against inventory
            try:
                inventory = FeedInventory.objects.get(fodder_type=fodder_type)
                if inventory.quantity_on_hand < total_quantity:
                    self.add_error('quantity_per_animal',
                        _("Insufficient inventory. Required: {} {}, Available: {} {}").format(
                            total_quantity, fodder_type.unit,
                            inventory.quantity_on_hand, fodder_type.unit))
            except FeedInventory.DoesNotExist:
                self.add_error('fodder_type',
                    _("No inventory record exists for this fodder type"))

        return cleaned_data