"""
Admin configuration for the Inventory app in Super Duper Dairy ERP System

This module configures the Django admin interface for inventory management,
including customized list displays, filters, and actions for each model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils.html import format_html, escape
from django.contrib import messages

from .models import (
    FodderType,
    FeedInventory,
    FeedPurchase,
    FeedConsumption,
    InHouseFeedProduction,
    InventoryTransaction
)


class LowStockFilter(admin.SimpleListFilter):
    """Custom filter to show fodder types with low stock levels"""
    title = _('Stock Level')
    parameter_name = 'stock_level'

    def lookups(self, request, model_admin):
        return (
            ('low', _('Below Minimum')),
            ('normal', _('Normal')),
            ('empty', _('Empty (Zero)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'low':
            # Get fodder types where inventory is below minimum
            low_stock_fodder_ids = []
            for fodder_type in queryset:
                if fodder_type.is_below_min_stock():
                    low_stock_fodder_ids.append(fodder_type.id)
            return queryset.filter(id__in=low_stock_fodder_ids)

        if self.value() == 'normal':
            # Get fodder types where inventory is above minimum
            normal_stock_fodder_ids = []
            for fodder_type in queryset:
                if not fodder_type.is_below_min_stock():
                    normal_stock_fodder_ids.append(fodder_type.id)
            return queryset.filter(id__in=normal_stock_fodder_ids)

        if self.value() == 'empty':
            # Get fodder types with zero inventory
            empty_stock_fodder_ids = []
            for fodder_type in queryset:
                inventory = fodder_type.inventory.first()
                if inventory and inventory.quantity_on_hand == 0:
                    empty_stock_fodder_ids.append(fodder_type.id)
            return queryset.filter(id__in=empty_stock_fodder_ids)

        return queryset


@admin.register(FodderType)
class FodderTypeAdmin(admin.ModelAdmin):
    """Admin interface for FodderType model"""
    list_display = (
        'name',
        'category',
        'unit',
        'display_current_inventory',
        'current_cost_per_unit',
        'is_produced_in_house',
        'min_stock_level',
        'display_stock_status'
    )
    list_filter = ('category', 'is_produced_in_house', LowStockFilter)
    search_fields = ('name', 'category')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'category', 'unit', 'is_produced_in_house')
        }),
        (_('Costing Information'), {
            'fields': ('current_cost_per_unit', 'costing_method')
        }),
        (_('Inventory Management'), {
            'fields': ('min_stock_level',)
        }),
        (_('Additional Information'), {
            'fields': ('nutrient_info', 'created_at', 'updated_at')
        }),
    )

    def display_current_inventory(self, obj):
        """Display current inventory level with link to inventory record"""
        inventory = obj.inventory.first()
        if inventory:
            quantity = inventory.quantity_on_hand
            url = reverse('admin:inventory_feedinventory_change', args=[inventory.id])
            return format_html('<a href="{}">{} {}</a>', url, quantity, obj.unit)
        return f"0 {obj.unit}"
    display_current_inventory.short_description = _("Current Inventory")

    def display_stock_status(self, obj):
        """Display stock status with color-coded indicator"""
        inventory = obj.inventory.first()
        if not inventory or inventory.quantity_on_hand == 0:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ OUT OF STOCK</span>')

        if obj.is_below_min_stock():
            return format_html('<span style="color: orange; font-weight: bold;">⚠️ LOW STOCK</span>')

        return format_html('<span style="color: green;">✓ ADEQUATE</span>')
    display_stock_status.short_description = _("Stock Status")


class FeedInventoryInline(admin.TabularInline):
    """Inline admin for FeedInventory to be used in FodderType admin"""
    model = FeedInventory
    extra = 0
    fields = ('quantity_on_hand', 'location', 'last_updated')
    readonly_fields = ('last_updated',)


@admin.register(FeedInventory)
class FeedInventoryAdmin(admin.ModelAdmin):
    """Admin interface for FeedInventory model"""
    list_display = ('fodder_type', 'quantity_on_hand', 'location', 'last_updated')
    list_filter = ('fodder_type__category', 'location')
    search_fields = ('fodder_type__name', 'location')
    readonly_fields = ('last_updated',)
    fieldsets = (
        (None, {
            'fields': ('fodder_type', 'quantity_on_hand', 'location', 'notes', 'last_updated')
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly for existing records"""
        if obj:  # editing an existing object
            return self.readonly_fields + ('fodder_type',)
        return self.readonly_fields


@admin.register(FeedPurchase)
class FeedPurchaseAdmin(admin.ModelAdmin):
    """Admin interface for FeedPurchase model"""
    list_display = (
        'date',
        'fodder_type',
        'quantity_purchased',
        'cost_per_unit',
        'total_cost',
        'supplier',
        'payment_status',
        'display_expense_link'
    )
    list_filter = ('date', 'fodder_type__category', 'supplier', 'payment_status')
    search_fields = ('fodder_type__name', 'supplier', 'invoice_number')
    readonly_fields = ('total_cost', 'related_expense', 'created_at', 'updated_at')
    date_hierarchy = 'date'
    fieldsets = (
        (_('Purchase Information'), {
            'fields': ('date', 'fodder_type', 'quantity_purchased', 'cost_per_unit', 'total_cost')
        }),
        (_('Supplier Details'), {
            'fields': ('supplier', 'invoice_number', 'payment_status')
        }),
        (_('Additional Information'), {
            'fields': ('notes', 'related_expense', 'created_at', 'updated_at')
        }),
    )

    def display_expense_link(self, obj):
        """Display link to related expense record"""
        if obj.related_expense:
            url = reverse('admin:finance_expenserecord_change', args=[obj.related_expense.id])
            return format_html('<a href="{}">{}</a>', url, _("View Expense"))
        return "-"
    display_expense_link.short_description = _("Expense Record")

    def save_model(self, request, obj, form, change):
        """Add user message after successful save"""
        super().save_model(request, obj, form, change)
        if not change:  # only for new records
            messages.success(request,
                _("Purchase record created successfully. Inventory has been updated."))


@admin.register(FeedConsumption)
class FeedConsumptionAdmin(admin.ModelAdmin):
    """Admin interface for FeedConsumption model"""
    list_display = (
        'date',
        'fodder_type',
        'quantity_consumed',
        'consumed_by',
        'display_specific_consumer',
        'cost_at_consumption'
    )
    list_filter = ('date', 'fodder_type__category', 'consumed_by')
    search_fields = ('fodder_type__name', 'group_name')
    readonly_fields = ('cost_at_consumption', 'created_at', 'updated_at')
    date_hierarchy = 'date'

    def get_fieldsets(self, request, obj=None):
        """Dynamically adjust fieldsets based on 'consumed_by' value"""
        # Common fields
        fieldsets = [
            (_('Consumption Information'), {
                'fields': ('date', 'fodder_type', 'quantity_consumed', 'consumed_by')
            }),
            (_('Cost Information'), {
                'fields': ('cost_at_consumption',)
            }),
            (_('Additional Information'), {
                'fields': ('notes', 'created_at', 'updated_at')
            }),
        ]

        # Add fields based on model configuration
        try:
            from django.apps import apps
            Buffalo = apps.get_model('herd', 'Buffalo')
            fieldsets[0][1]['fields'] += ('specific_buffalo',)
        except (LookupError, ImportError):
            pass

        # Always add group_name
        fieldsets[0][1]['fields'] += ('group_name',)

        return fieldsets

    def display_specific_consumer(self, obj):
        """Display the specific consumer (buffalo or group)"""
        if obj.consumed_by == 'INDIVIDUAL' and hasattr(obj, 'specific_buffalo') and obj.specific_buffalo:
            url = reverse('admin:herd_buffalo_change', args=[obj.specific_buffalo.id])
            return format_html('<a href="{}">{}</a>', url, obj.specific_buffalo)
        elif obj.consumed_by == 'GROUP' and obj.group_name:
            return obj.group_name
        return "-"
    display_specific_consumer.short_description = _("Consumer")

    def save_model(self, request, obj, form, change):
        """Add user message after successful save"""
        # Get current inventory before saving
        try:
            inventory = FeedInventory.objects.get(fodder_type=obj.fodder_type)
            if inventory.quantity_on_hand < obj.quantity_consumed:
                messages.error(request,
                    _("Cannot record consumption: Insufficient inventory. Available: {} {}").format(
                        inventory.quantity_on_hand, obj.fodder_type.unit))
                return
        except FeedInventory.DoesNotExist:
            messages.error(request, _("Cannot record consumption: No inventory record exists for this fodder type."))
            return

        super().save_model(request, obj, form, change)
        messages.success(request, _("Consumption record created successfully. Inventory has been updated."))


@admin.register(InHouseFeedProduction)
class InHouseFeedProductionAdmin(admin.ModelAdmin):
    """Admin interface for InHouseFeedProduction model"""
    list_display = (
        'date',
        'fodder_type',
        'quantity_produced',
        'total_production_cost',
        'cost_per_unit',
        'production_location'
    )
    list_filter = ('date', 'fodder_type', 'production_location')
    search_fields = ('fodder_type__name', 'production_location')
    readonly_fields = ('total_production_cost', 'cost_per_unit', 'created_at', 'updated_at')
    date_hierarchy = 'date'
    fieldsets = (
        (_('Production Information'), {
            'fields': ('date', 'fodder_type', 'quantity_produced', 'production_location')
        }),
        (_('Cost Information'), {
            'fields': ('associated_costs', 'total_production_cost', 'cost_per_unit')
        }),
        (_('Additional Information'), {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        """Add user message after successful save"""
        if not obj.fodder_type.is_produced_in_house:
            messages.error(request,
                _("Cannot record production: This fodder type is not marked as producible in-house."))
            return

        super().save_model(request, obj, form, change)
        messages.success(request,
            _("Production record created successfully. Inventory has been updated."))


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    """Admin interface for InventoryTransaction model - read-only audit log"""
    list_display = (
        'date',
        'transaction_type',
        'fodder_type',
        'quantity',
        'unit_value',
        'total_value',
        'previous_balance',
        'new_balance',
        'created_at'
    )
    list_filter = ('transaction_type', 'date', 'fodder_type__category')
    search_fields = ('fodder_type__name', 'notes')
    readonly_fields = (
        'fodder_type', 'transaction_type', 'date', 'quantity', 'unit_value',
        'total_value', 'reference_id', 'reference_model', 'previous_balance',
        'new_balance', 'notes', 'created_by', 'created_at'
    )
    date_hierarchy = 'date'

    def has_add_permission(self, request):
        """Disable add permission - transactions are created automatically"""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable edit permission - transactions are immutable audit records"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable delete permission - transactions should not be deleted"""
        return False


# Add custom actions for the admin site

def update_fodder_min_stock_levels(modeladmin, request, queryset):
    """Action to update minimum stock levels for selected fodder types"""
    # In a real system, this would be a more sophisticated form
    for fodder in queryset:
        current_inventory = fodder.inventory.first()
        if current_inventory and current_inventory.quantity_on_hand > 0:
            fodder.min_stock_level = current_inventory.quantity_on_hand * 0.2  # Set to 20% of current
            fodder.save(update_fields=['min_stock_level'])

    messages.success(request, _("Updated minimum stock levels for {} fodder types").format(queryset.count()))
update_fodder_min_stock_levels.short_description = _("Set min stock to 20% of current inventory")


def recalculate_inventory_values(modeladmin, request, queryset):
    """Action to recalculate inventory values based on current costs"""
    updated_count = 0
    for fodder in queryset:
        current_inventory = fodder.inventory.first()
        if current_inventory:
            # Record the recalculation in transaction log
            from django.utils import timezone
            InventoryTransaction.objects.create(
                fodder_type=fodder,
                transaction_type='ADJUSTMENT',
                date=timezone.now().date(),
                quantity=0,  # No quantity change
                unit_value=fodder.current_cost_per_unit,
                total_value=0,  # No value change
                previous_balance=current_inventory.quantity_on_hand,
                new_balance=current_inventory.quantity_on_hand,
                notes=f"Inventory value recalculation from admin action",
                created_by=request.user if request.user.is_authenticated else None
            )
            updated_count += 1

    messages.success(request, _("Recalculated inventory values for {} fodder types").format(updated_count))
recalculate_inventory_values.short_description = _("Recalculate inventory values")


# Add the actions to FodderTypeAdmin
FodderTypeAdmin.actions = [update_fodder_min_stock_levels, recalculate_inventory_values]

# Add FeedInventoryInline to FodderTypeAdmin
FodderTypeAdmin.inlines = [FeedInventoryInline]