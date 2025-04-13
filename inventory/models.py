"""
Inventory Management Models for Super Duper Dairy ERP System

This module defines the data models for the inventory management system, specifically
focusing on feed and fodder inventory, purchases, consumption, and in-house production.
The module implements business logic for:
- Tracking different types of fodder and feed
- Managing inventory levels
- Recording purchases and consumption
- Supporting in-house production with cost calculation
- Implementing different inventory costing methods (FIFO, LIFO, Average)
"""

from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from decimal import Decimal
from finance.models import ExpenseRecord, ExpenseCategory

# Import Buffalo model if tracking consumption by specific animal
try:
    from herd.models import Buffalo

    BUFFALO_MODEL_EXISTS = True
except ImportError:
    BUFFALO_MODEL_EXISTS = False

# Constants for choice fields
FODDER_CATEGORIES = [
    ('GREEN', 'Green Fodder'),
    ('DRY', 'Dry Fodder'),
    ('CONCENTRATE', 'Concentrate'),
    ('SUPPLEMENT', 'Supplement'),
    ('OTHER', 'Other'),
]

INVENTORY_COSTING_METHODS = [
    ('FIFO', 'First In, First Out'),
    ('LIFO', 'Last In, First Out'),
    ('AVG', 'Weighted Average'),
]

CONSUMPTION_BY_CHOICES = [
    ('WHOLE_HERD', 'Whole Herd'),
    ('GROUP', 'Specific Group'),
    ('INDIVIDUAL', 'Individual Buffalo'),
]


class FodderType(models.Model):
    """
    Defines types of fodder/feed used in the dairy farm.

    This model stores information about different types of fodder, including
    their category, unit of measurement, and whether they can be produced in-house.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Name of the fodder/feed type")
    )
    category = models.CharField(
        max_length=20,
        choices=FODDER_CATEGORIES,
        help_text=_("Category of fodder/feed")
    )
    unit = models.CharField(
        max_length=20,
        help_text=_("Unit of measurement (e.g., kg, bag)")
    )
    current_cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Current cost per unit for this fodder type")
    )
    is_produced_in_house = models.BooleanField(
        default=False,
        help_text=_("Whether this fodder can be produced in-house")
    )
    nutrient_info = models.TextField(
        blank=True,
        null=True,
        help_text=_("Optional nutritional information")
    )
    min_stock_level = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Minimum stock level to trigger alerts")
    )
    costing_method = models.CharField(
        max_length=10,
        choices=INVENTORY_COSTING_METHODS,
        default='AVG',
        help_text=_("Method used for inventory costing")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _("Fodder Type")
        verbose_name_plural = _("Fodder Types")

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def clean(self):
        """Validate model data before saving"""
        if self.current_cost_per_unit < 0:
            raise ValidationError(_("Cost per unit cannot be negative"))
        if self.min_stock_level < 0:
            raise ValidationError(_("Minimum stock level cannot be negative"))

    def is_below_min_stock(self):
        """Check if current inventory is below minimum stock level"""
        try:
            inventory = self.inventory.first()
            if inventory:
                return inventory.quantity_on_hand <= self.min_stock_level
            return False
        except FeedInventory.DoesNotExist:
            return False


class FeedInventory(models.Model):
    """
    Tracks current inventory levels for each fodder type.

    This model maintains the current quantity on hand for each fodder type,
    and is updated whenever purchases or consumption occur.
    """
    fodder_type = models.ForeignKey(
        FodderType,
        on_delete=models.CASCADE,
        related_name='inventory',
        help_text=_("Type of fodder/feed")
    )
    quantity_on_hand = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Current quantity in stock")
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text=_("When the inventory was last updated")
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Storage location of this inventory")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text=_("Additional notes about this inventory")
    )

    class Meta:
        verbose_name = _("Feed Inventory")
        verbose_name_plural = _("Feed Inventories")

    def __str__(self):
        return f"{self.fodder_type.name}: {self.quantity_on_hand} {self.fodder_type.unit}"

    def clean(self):
        """Validate model data before saving"""
        if self.quantity_on_hand < 0:
            raise ValidationError(_("Quantity on hand cannot be negative"))

    def update_quantity(self, change_amount):
        """
        Update inventory quantity by adding the change amount

        Args:
            change_amount: Amount to add (positive) or subtract (negative)

        Returns:
            bool: True if update successful, False otherwise
        """
        new_quantity = self.quantity_on_hand + change_amount
        if new_quantity < 0:
            return False  # Cannot have negative inventory
        self.quantity_on_hand = new_quantity
        self.save()
        return True


class FeedPurchase(models.Model):
    """
    Records purchases of fodder/feed from suppliers.

    Each purchase automatically updates the inventory and creates
    an expense record in the finance module.
    """
    fodder_type = models.ForeignKey(
        FodderType,
        on_delete=models.CASCADE,
        related_name='purchases',
        help_text=_("Type of fodder/feed purchased")
    )
    date = models.DateField(
        help_text=_("Date of purchase")
    )
    supplier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Name of the supplier")
    )
    quantity_purchased = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Quantity purchased")
    )
    cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Cost per unit")
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        help_text=_("Total cost (calculated)")
    )
    invoice_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Invoice number for this purchase")
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PAID', 'Paid'),
            ('PARTIAL', 'Partially Paid'),
        ],
        default='PAID',
        help_text=_("Payment status of this purchase")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text=_("Additional notes about this purchase")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Link to the expense record generated automatically
    related_expense = models.OneToOneField(
        ExpenseRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feed_purchase',
        help_text=_("Associated expense record")
    )

    class Meta:
        ordering = ['-date']
        verbose_name = _("Feed Purchase")
        verbose_name_plural = _("Feed Purchases")

    def __str__(self):
        return f"{self.fodder_type.name} - {self.date} - {self.quantity_purchased} {self.fodder_type.unit}"

    def save(self, *args, **kwargs):
        """Override save to calculate total cost"""
        self.total_cost = self.quantity_purchased * self.cost_per_unit
        super().save(*args, **kwargs)

    def clean(self):
        """Validate model data before saving"""
        if self.quantity_purchased <= 0:
            raise ValidationError(_("Quantity purchased must be positive"))
        if self.cost_per_unit < 0:
            raise ValidationError(_("Cost per unit cannot be negative"))


class FeedConsumption(models.Model):
    """
    Records consumption of fodder/feed by the herd.

    This model tracks when and how much feed is consumed, and can be linked
    to specific buffalo or groups if needed.
    """
    fodder_type = models.ForeignKey(
        FodderType,
        on_delete=models.CASCADE,
        related_name='consumption_records',
        help_text=_("Type of fodder/feed consumed")
    )
    date = models.DateField(
        help_text=_("Date of consumption")
    )
    quantity_consumed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Quantity consumed")
    )
    consumed_by = models.CharField(
        max_length=20,
        choices=CONSUMPTION_BY_CHOICES,
        default='WHOLE_HERD',
        help_text=_("Who consumed this feed")
    )
    # Only used if consumed_by is 'INDIVIDUAL'
    specific_buffalo = models.ForeignKey(
        'herd.Buffalo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feed_consumption',
        help_text=_("Specific buffalo (if individual consumption)")
    ) if BUFFALO_MODEL_EXISTS else None
    # Only used if consumed_by is 'GROUP'
    group_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Name of the group (if group consumption)")
    )
    cost_at_consumption = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Cost based on inventory valuation method")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text=_("Additional notes about this consumption")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = _("Feed Consumption")
        verbose_name_plural = _("Feed Consumption Records")

    def __str__(self):
        return f"{self.fodder_type.name} - {self.date} - {self.quantity_consumed} {self.fodder_type.unit}"

    def clean(self):
        """Validate model data before saving"""
        if self.quantity_consumed <= 0:
            raise ValidationError(_("Quantity consumed must be positive"))

        # Validation for buffalo/group selection based on consumed_by field
        if self.consumed_by == 'INDIVIDUAL' and not hasattr(self, 'specific_buffalo'):
            raise ValidationError(_("Must specify a buffalo for individual consumption"))
        if self.consumed_by == 'GROUP' and not self.group_name:
            raise ValidationError(_("Must specify a group name for group consumption"))


class InHouseFeedProduction(models.Model):
    """
    Records in-house production of fodder/feed.

    This model tracks when fodder is produced on-site, with associated costs
    and quantities. It helps calculate the cost per unit for in-house produced feed.
    """
    fodder_type = models.ForeignKey(
        FodderType,
        on_delete=models.CASCADE,
        related_name='production_records',
        help_text=_("Type of fodder/feed produced")
    )
    date = models.DateField(
        help_text=_("Date of production")
    )
    quantity_produced = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Quantity produced")
    )
    # Store expense records as a JSON array of IDs and amounts
    associated_costs = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("JSON of associated expense records (e.g., {expense_id: amount})")
    )
    total_production_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Total cost of production")
    )
    cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Calculated cost per unit")
    )
    production_location = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Location where production occurred")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text=_("Additional notes about this production")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = _("In-House Feed Production")
        verbose_name_plural = _("In-House Feed Production Records")

    def __str__(self):
        return f"{self.fodder_type.name} - {self.date} - {self.quantity_produced} {self.fodder_type.unit}"

    def save(self, *args, **kwargs):
        """Override save to calculate cost per unit"""
        if self.quantity_produced > 0:
            self.cost_per_unit = self.total_production_cost / self.quantity_produced
        else:
            self.cost_per_unit = 0
        super().save(*args, **kwargs)

    def clean(self):
        """Validate model data before saving"""
        if self.quantity_produced <= 0:
            raise ValidationError(_("Quantity produced must be positive"))

        # Ensure the fodder type is marked as producible in-house
        if not self.fodder_type.is_produced_in_house:
            raise ValidationError(_("This fodder type is not marked as producible in-house"))

    def calculate_total_cost(self):
        """Calculate total cost from associated expense records"""
        total = Decimal('0.00')
        if self.associated_costs:
            for expense_id, amount in self.associated_costs.items():
                # Convert amount to Decimal to avoid float precision issues
                total += Decimal(str(amount))
        self.total_production_cost = total
        return total


class InventoryTransaction(models.Model):
    """
    Records all inventory transactions for auditing and tracking purposes.

    This model keeps a log of all changes to inventory, whether from purchases,
    consumption, production, or manual adjustments.
    """
    TRANSACTION_TYPES = [
        ('PURCHASE', 'Purchase'),
        ('CONSUMPTION', 'Consumption'),
        ('PRODUCTION', 'In-House Production'),
        ('ADJUSTMENT', 'Manual Adjustment'),
        ('TRANSFER', 'Location Transfer'),
        ('RETURN', 'Return to Supplier'),
        ('WASTAGE', 'Wastage/Spoilage'),
    ]

    fodder_type = models.ForeignKey(
        FodderType,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text=_("Type of fodder/feed")
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        help_text=_("Type of inventory transaction")
    )
    date = models.DateField(
        help_text=_("Date of transaction")
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Quantity affected (positive for in, negative for out)")
    )
    unit_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Value per unit")
    )
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Total transaction value")
    )
    reference_id = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("ID of referenced record (purchase, consumption, etc.)")
    )
    reference_model = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text=_("Model name of the referenced record")
    )
    previous_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Inventory balance before this transaction")
    )
    new_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Inventory balance after this transaction")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text=_("Additional notes about this transaction")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("User who created this transaction")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = _("Inventory Transaction")
        verbose_name_plural = _("Inventory Transactions")

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.fodder_type.name} - {self.date} - {self.quantity}"


# Signal handlers for automatic processing

@receiver(post_save, sender=FeedPurchase)
def process_feed_purchase(sender, instance, created, **kwargs):
    """
    Signal handler to process a feed purchase:
    1. Update inventory quantity
    2. Update fodder type cost per unit if using weighted average
    3. Create an expense record
    4. Create an inventory transaction record
    """
    if created:  # Only process on initial creation
        # Get or create inventory record
        inventory, created = FeedInventory.objects.get_or_create(
            fodder_type=instance.fodder_type,
            defaults={'quantity_on_hand': 0}
        )

        # Store previous balance for transaction record
        previous_balance = inventory.quantity_on_hand

        # Update inventory quantity
        inventory.quantity_on_hand += instance.quantity_purchased
        inventory.save()

        # Update fodder cost per unit if using weighted average
        if instance.fodder_type.costing_method == 'AVG':
            # Previous total value
            prev_value = previous_balance * instance.fodder_type.current_cost_per_unit
            # New purchase value
            new_value = instance.quantity_purchased * instance.cost_per_unit
            # Total quantity after purchase
            total_qty = previous_balance + instance.quantity_purchased

            if total_qty > 0:  # Avoid division by zero
                # Calculate new weighted average cost
                new_avg_cost = (prev_value + new_value) / total_qty
                instance.fodder_type.current_cost_per_unit = new_avg_cost
                instance.fodder_type.save()

        # Create expense record if not already linked
        if not instance.related_expense:
            # Get or create Feed expense category
            expense_category, _ = ExpenseCategory.objects.get_or_create(
                name='Feed',
                defaults={'is_direct_cost': True}
            )

            # Create expense record
            expense_record = ExpenseRecord.objects.create(
                date=instance.date,
                category=expense_category,
                description=f"Purchase of {instance.quantity_purchased} {instance.fodder_type.unit} of {instance.fodder_type.name}",
                amount=instance.total_cost,
                related_module='FeedPurchase',
                related_record_id=instance.id,
                supplier_vendor=instance.supplier,
                notes=instance.notes
            )

            # Link expense record to purchase
            instance.related_expense = expense_record
            instance.save(update_fields=['related_expense'])

        # Create inventory transaction record
        InventoryTransaction.objects.create(
            fodder_type=instance.fodder_type,
            transaction_type='PURCHASE',
            date=instance.date,
            quantity=instance.quantity_purchased,
            unit_value=instance.cost_per_unit,
            total_value=instance.total_cost,
            reference_id=instance.id,
            reference_model='FeedPurchase',
            previous_balance=previous_balance,
            new_balance=inventory.quantity_on_hand,
            notes=f"Purchase from {instance.supplier or 'Unknown supplier'}"
        )


@receiver(post_save, sender=FeedConsumption)
def process_feed_consumption(sender, instance, created, **kwargs):
    """
    Signal handler to process feed consumption:
    1. Update inventory quantity
    2. Calculate cost based on inventory costing method
    3. Create an inventory transaction record
    """
    # Get inventory record
    try:
        inventory = FeedInventory.objects.get(fodder_type=instance.fodder_type)
    except FeedInventory.DoesNotExist:
        # If no inventory exists, create one
        inventory = FeedInventory.objects.create(
            fodder_type=instance.fodder_type,
            quantity_on_hand=0
        )

    # Store previous balance for transaction record
    previous_balance = inventory.quantity_on_hand

    # Update inventory quantity (only if there's enough)
    if inventory.quantity_on_hand >= instance.quantity_consumed:
        inventory.quantity_on_hand -= instance.quantity_consumed
        inventory.save()

        # Calculate cost based on fodder type's costing method
        if instance.cost_at_consumption is None:
            # For simplicity, use current cost - in a real system, this would
            # implement FIFO/LIFO logic using batches
            instance.cost_at_consumption = instance.quantity_consumed * instance.fodder_type.current_cost_per_unit
            # Save the instance with the calculated cost
            instance.save(update_fields=['cost_at_consumption'])

        # Create inventory transaction record
        InventoryTransaction.objects.create(
            fodder_type=instance.fodder_type,
            transaction_type='CONSUMPTION',
            date=instance.date,
            quantity=-instance.quantity_consumed,  # Negative for consumption
            unit_value=instance.fodder_type.current_cost_per_unit,
            total_value=instance.cost_at_consumption,
            reference_id=instance.id,
            reference_model='FeedConsumption',
            previous_balance=previous_balance,
            new_balance=inventory.quantity_on_hand,
            notes=f"Consumed by: {instance.get_consumed_by_display()}"
        )


@receiver(post_save, sender=InHouseFeedProduction)
def process_feed_production(sender, instance, created, **kwargs):
    """
    Signal handler to process in-house feed production:
    1. Calculate total cost from associated expenses
    2. Update cost per unit
    3. Update inventory quantity
    4. Create an inventory transaction record
    """
    # Calculate total cost from associated expenses
    instance.calculate_total_cost()

    # Calculate cost per unit
    if instance.quantity_produced > 0:
        instance.cost_per_unit = instance.total_production_cost / instance.quantity_produced
    else:
        instance.cost_per_unit = 0

    # Disable the signal temporarily to avoid infinite loop
    post_save.disconnect(process_feed_production, sender=InHouseFeedProduction)
    instance.save(update_fields=['total_production_cost', 'cost_per_unit'])
    post_save.connect(process_feed_production, sender=InHouseFeedProduction)

    # Get or create inventory record
    inventory, created = FeedInventory.objects.get_or_create(
        fodder_type=instance.fodder_type,
        defaults={'quantity_on_hand': 0}
    )

    # Store previous balance for transaction record
    previous_balance = inventory.quantity_on_hand

    # Update inventory quantity
    inventory.quantity_on_hand += instance.quantity_produced
    inventory.save()

    # Update fodder cost per unit if using weighted average
    if instance.fodder_type.costing_method == 'AVG':
        # Consider only if we have existing inventory besides this production
        if previous_balance > 0:
            # Previous total value
            prev_value = previous_balance * instance.fodder_type.current_cost_per_unit
            # New production value
            new_value = instance.quantity_produced * instance.cost_per_unit
            # Total quantity after production
            total_qty = previous_balance + instance.quantity_produced

            if total_qty > 0:  # Avoid division by zero
                # Calculate new weighted average cost
                new_avg_cost = (prev_value + new_value) / total_qty
                instance.fodder_type.current_cost_per_unit = new_avg_cost
                instance.fodder_type.save()
        else:
            # If no previous inventory, set cost to production cost
            instance.fodder_type.current_cost_per_unit = instance.cost_per_unit
            instance.fodder_type.save()

    # Create inventory transaction record
    InventoryTransaction.objects.create(
        fodder_type=instance.fodder_type,
        transaction_type='PRODUCTION',
        date=instance.date,
        quantity=instance.quantity_produced,
        unit_value=instance.cost_per_unit,
        total_value=instance.total_production_cost,
        reference_id=instance.id,
        reference_model='InHouseFeedProduction',
        previous_balance=previous_balance,
        new_balance=inventory.quantity_on_hand,
        notes=f"In-house production at {instance.production_location or 'farm'}"
    )