from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from herd.models import Buffalo
from finance.models import ExpenseRecord, ExpenseCategory
from core.models import GlobalSettings


class FodderType(models.Model):
    """Model for types of feed/fodder."""
    CATEGORY_GREEN = 'GREEN'
    CATEGORY_DRY = 'DRY'
    CATEGORY_CONCENTRATE = 'CONCENTRATE'
    CATEGORY_SUPPLEMENT = 'SUPPLEMENT'

    CATEGORY_CHOICES = [
        (CATEGORY_GREEN, _('Green Fodder')),
        (CATEGORY_DRY, _('Dry Fodder')),
        (CATEGORY_CONCENTRATE, _('Concentrate')),
        (CATEGORY_SUPPLEMENT, _('Supplement')),
    ]

    fodder_type_id = models.AutoField(primary_key=True)
    name = models.CharField(_('Name'), max_length=100, unique=True)
    category = models.CharField(_('Category'), max_length=20, choices=CATEGORY_CHOICES)
    unit = models.CharField(_('Unit'), max_length=20, help_text=_('e.g., kg, bag'))
    current_cost_per_unit = models.DecimalField(_('Current Cost per Unit'), max_digits=10, decimal_places=2,
                                                null=True, blank=True)
    nutrient_info = models.TextField(_('Nutrient Information'), blank=True)
    is_produced_in_house = models.BooleanField(_('Produced In-House'), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        category_display = dict(self.CATEGORY_CHOICES).get(self.category, self.category)
        return f"{self.name} ({category_display})"

    class Meta:
        verbose_name = _('Fodder Type')
        verbose_name_plural = _('Fodder Types')
        ordering = ['category', 'name']


class FeedInventory(models.Model):
    """Model for current inventory levels of feed/fodder."""
    inventory_id = models.AutoField(primary_key=True)
    fodder_type = models.ForeignKey(FodderType, on_delete=models.CASCADE, related_name='inventory')
    quantity_on_hand = models.DecimalField(_('Quantity on Hand'), max_digits=10, decimal_places=2)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.fodder_type}: {self.quantity_on_hand} {self.fodder_type.unit}"

    class Meta:
        verbose_name = _('Feed Inventory')
        verbose_name_plural = _('Feed Inventories')
        ordering = ['fodder_type']


class FeedPurchase(models.Model):
    """Model for recording feed purchases."""
    purchase_id = models.AutoField(primary_key=True)
    fodder_type = models.ForeignKey(FodderType, on_delete=models.PROTECT, related_name='purchases')
    date = models.DateField(_('Purchase Date'))
    supplier = models.CharField(_('Supplier'), max_length=100, blank=True)
    quantity_purchased = models.DecimalField(_('Quantity Purchased'), max_digits=10, decimal_places=2)
    cost_per_unit = models.DecimalField(_('Cost per Unit'), max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(_('Total Cost'), max_digits=12, decimal_places=2, blank=True)
    related_expense = models.OneToOneField(ExpenseRecord, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='feed_purchase')
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Calculate total cost
        self.total_cost = self.quantity_purchased * self.cost_per_unit

        # Save the record
        super().save(*args, **kwargs)

        # Update fodder type current cost per unit (weighted average)
        self.update_fodder_cost()

        # Create expense record if it doesn't exist
        if not self.related_expense:
            try:
                feed_category, _ = ExpenseCategory.objects.get_or_create(
                    name='Feed',
                    defaults={'is_direct_cost': True}
                )

                expense = ExpenseRecord.objects.create(
                    date=self.date,
                    category=feed_category,
                    description=f"Purchase of {self.fodder_type.name}",
                    amount=self.total_cost,
                    related_module='FeedPurchase',
                    related_record_id=self.purchase_id,
                    supplier_vendor=self.supplier,
                    notes=self.notes
                )

                self.related_expense = expense
                self.save(update_fields=['related_expense'])
            except Exception as e:
                # Log the error
                print(f"Error creating expense record: {e}")

        # Update inventory
        self.update_inventory()

    def update_fodder_cost(self):
        """Update the current cost per unit of fodder type using weighted average."""
        fodder = self.fodder_type

        # Get current inventory
        try:
            inventory = FeedInventory.objects.get(fodder_type=fodder)
            current_qty = inventory.quantity_on_hand

            if current_qty > 0 and fodder.current_cost_per_unit:
                # Calculate weighted average
                total_cost = (current_qty * fodder.current_cost_per_unit) + self.total_cost
                total_qty = current_qty + self.quantity_purchased
                new_cost_per_unit = total_cost / total_qty if total_qty > 0 else self.cost_per_unit
            else:
                new_cost_per_unit = self.cost_per_unit

            # Update fodder type cost
            fodder.current_cost_per_unit = new_cost_per_unit
            fodder.save(update_fields=['current_cost_per_unit', 'updated_at'])

        except FeedInventory.DoesNotExist:
            # If no inventory exists, just set cost to purchase cost
            fodder.current_cost_per_unit = self.cost_per_unit
            fodder.save(update_fields=['current_cost_per_unit', 'updated_at'])

        def update_inventory(self):
            """Update inventory levels after purchase."""
            try:
                inventory = FeedInventory.objects.get(fodder_type=self.fodder_type)
                inventory.quantity_on_hand += self.quantity_purchased
                inventory.save()
            except FeedInventory.DoesNotExist:
                # Create new inventory record if it doesn't exist
                FeedInventory.objects.create(
                    fodder_type=self.fodder_type,
                    quantity_on_hand=self.quantity_purchased
                )

        def __str__(self):
            return f"{self.date} - {self.fodder_type}: {self.quantity_purchased} {self.fodder_type.unit}"

        class Meta:
            verbose_name = _('Feed Purchase')
            verbose_name_plural = _('Feed Purchases')
            ordering = ['-date']

class FeedConsumption(models.Model):
    """Model for recording feed consumption."""
    CONSUMPTION_WHOLE_HERD = 'WHOLE_HERD'
    CONSUMPTION_GROUP = 'GROUP'
    CONSUMPTION_INDIVIDUAL = 'INDIVIDUAL'

    CONSUMPTION_TYPE_CHOICES = [
        (CONSUMPTION_WHOLE_HERD, _('Whole Herd')),
        (CONSUMPTION_GROUP, _('Specific Group')),
        (CONSUMPTION_INDIVIDUAL, _('Individual Buffalo')),
    ]

    consumption_id = models.AutoField(primary_key=True)
    fodder_type = models.ForeignKey(FodderType, on_delete=models.PROTECT, related_name='consumption_records')
    date = models.DateField(_('Consumption Date'))
    quantity_consumed = models.DecimalField(_('Quantity Consumed'), max_digits=10, decimal_places=2)
    consumed_by = models.CharField(_('Consumed By'), max_length=20, choices=CONSUMPTION_TYPE_CHOICES)
    specific_buffalo = models.ForeignKey(Buffalo, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='feed_consumption_records')
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Update inventory
        self.update_inventory()

        # Optional: Create expense allocation for specific buffalo
        if self.consumed_by == self.CONSUMPTION_INDIVIDUAL and self.specific_buffalo:
            self.allocate_expense_to_buffalo()

    def update_inventory(self):
        """Update inventory levels after consumption."""
        try:
            inventory = FeedInventory.objects.get(fodder_type=self.fodder_type)
            if inventory.quantity_on_hand >= self.quantity_consumed:
                inventory.quantity_on_hand -= self.quantity_consumed
                inventory.save()
            else:
                # Handle insufficient inventory scenario
                # This could raise an exception or set quantity to zero
                inventory.quantity_on_hand = 0
                inventory.save()

                # Check if we need to trigger an alert
                try:
                    settings = GlobalSettings.objects.first()
                    if settings and inventory.quantity_on_hand < settings.alert_low_feed_inventory_threshold_kg:
                        from core.models import Alert
                        # Create an alert
                        Alert.objects.create(
                            title=f"Low Feed Inventory: {self.fodder_type.name}",
                            message=f"Inventory level ({inventory.quantity_on_hand} {self.fodder_type.unit}) is below threshold.",
                            priority=Alert.PRIORITY_HIGH,
                            related_module='FeedInventory',
                            related_record_id=inventory.inventory_id
                        )
                except Exception as e:
                    # Log the error
                    print(f"Error creating alert: {e}")
        except FeedInventory.DoesNotExist:
            # If no inventory exists, create one with zero quantity
            FeedInventory.objects.create(
                fodder_type=self.fodder_type,
                quantity_on_hand=0
            )

    def allocate_expense_to_buffalo(self):
        """Allocate feed cost as an expense to the specific buffalo."""
        if not self.fodder_type.current_cost_per_unit:
            return

        # Calculate cost
        cost = self.quantity_consumed * self.fodder_type.current_cost_per_unit

        # Get or create Feed expense category
        try:
            feed_category, _ = ExpenseCategory.objects.get_or_create(
                name='Feed',
                defaults={'is_direct_cost': True}
            )

            # Create expense record
            ExpenseRecord.objects.create(
                date=self.date,
                category=feed_category,
                description=f"Feed consumption: {self.fodder_type.name}",
                amount=cost,
                related_module='FeedConsumption',
                related_record_id=self.consumption_id,
                related_buffalo=self.specific_buffalo,
                notes=self.notes
            )
        except Exception as e:
            # Log the error
            print(f"Error creating expense record: {e}")

    def __str__(self):
        consumed_by_str = dict(self.CONSUMPTION_TYPE_CHOICES).get(self.consumed_by, self.consumed_by)
        if self.consumed_by == self.CONSUMPTION_INDIVIDUAL and self.specific_buffalo:
            consumed_by_str = f"{consumed_by_str}: {self.specific_buffalo}"
        return f"{self.date} - {self.fodder_type}: {self.quantity_consumed} {self.fodder_type.unit} by {consumed_by_str}"

    class Meta:
        verbose_name = _('Feed Consumption')
        verbose_name_plural = _('Feed Consumptions')
        ordering = ['-date']

class InHouseFeedProduction(models.Model):
    """Model for recording in-house feed production."""
    production_id = models.AutoField(primary_key=True)
    fodder_type = models.ForeignKey(FodderType, on_delete=models.PROTECT,
                                    related_name='in_house_production_records',
                                    limit_choices_to={'is_produced_in_house': True})
    date = models.DateField(_('Production Date'))
    quantity_produced = models.DecimalField(_('Quantity Produced'), max_digits=10, decimal_places=2)
    associated_costs = models.JSONField(_('Associated Costs'), default=dict, blank=True,
                                        help_text=_('JSON of linked expense IDs and amounts'))
    total_production_cost = models.DecimalField(_('Total Production Cost'), max_digits=12, decimal_places=2)
    cost_per_unit = models.DecimalField(_('Cost per Unit'), max_digits=10, decimal_places=2)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Calculate cost_per_unit if not set
        if self.total_production_cost and not self.cost_per_unit and self.quantity_produced:
            self.cost_per_unit = self.total_production_cost / self.quantity_produced

        super().save(*args, **kwargs)

        # Update inventory
        self.update_inventory()

        # Update feed strategy if needed based on GlobalSettings
        try:
            settings = GlobalSettings.objects.first()
            if settings and settings.feed_strategy_toggle == GlobalSettings.FEED_STRATEGY_IN_HOUSE:
                # Update the fodder type cost to prioritize in-house production
                self.fodder_type.current_cost_per_unit = self.cost_per_unit
                self.fodder_type.save(update_fields=['current_cost_per_unit', 'updated_at'])
        except Exception as e:
            # Log the error or handle appropriately
            print(f"Error updating feed strategy: {e}")

    def update_inventory(self):
        """Update inventory levels after in-house production."""
        try:
            inventory = FeedInventory.objects.get(fodder_type=self.fodder_type)
            inventory.quantity_on_hand += self.quantity_produced
            inventory.save()
        except FeedInventory.DoesNotExist:
            # Create new inventory record if it doesn't exist
            FeedInventory.objects.create(
                fodder_type=self.fodder_type,
                quantity_on_hand=self.quantity_produced
            )

    def __str__(self):
        return f"{self.date} - {self.fodder_type}: {self.quantity_produced} {self.fodder_type.unit} produced in-house"

    class Meta:
        verbose_name = _('In-House Feed Production')
        verbose_name_plural = _('In-House Feed Productions')
        ordering = ['-date']