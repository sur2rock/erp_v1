"""
Signal handlers for the Inventory app in Super Duper Dairy ERP System

This module defines additional Django signal handlers for inventory-related models,
handling operations like inventory updates and expense record creation.
"""

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import (
    FodderType,
    FeedInventory,
    FeedPurchase,
    FeedConsumption,
    InHouseFeedProduction,
    InventoryTransaction
)

User = get_user_model()


@receiver(pre_delete, sender=FeedPurchase)
def handle_purchase_deletion(sender, instance, **kwargs):
    """
    Handle inventory adjustment when a purchase record is deleted.

    This function reverses the effect of a purchase on the inventory system:
    1. Decreases the inventory quantity by the purchased amount
    2. Updates the weighted average cost if needed
    3. Creates a transaction record for the adjustment
    """
    try:
        with transaction.atomic():
            # Get inventory
            inventory = FeedInventory.objects.select_for_update().get(fodder_type=instance.fodder_type)

            # Store previous value for transaction record
            previous_balance = inventory.quantity_on_hand

            # Update inventory quantity
            inventory.quantity_on_hand -= instance.quantity_purchased

            # Ensure inventory doesn't go negative
            if inventory.quantity_on_hand < 0:
                inventory.quantity_on_hand = 0

            inventory.save()

            # Create inventory transaction record
            InventoryTransaction.objects.create(
                fodder_type=instance.fodder_type,
                transaction_type='ADJUSTMENT',
                date=timezone.now().date(),
                quantity=-instance.quantity_purchased,  # Negative for reduction
                unit_value=instance.cost_per_unit,
                total_value=-(instance.total_cost),
                reference_model='FeedPurchase (Deleted)',
                reference_id=instance.id,
                previous_balance=previous_balance,
                new_balance=inventory.quantity_on_hand,
                notes=f"Reversal of purchase record #{instance.id} deletion"
            )

    except FeedInventory.DoesNotExist:
        # No inventory record to adjust
        pass


@receiver(pre_delete, sender=FeedConsumption)
def handle_consumption_deletion(sender, instance, **kwargs):
    """
    Handle inventory adjustment when a consumption record is deleted.

    This function reverses the effect of consumption on the inventory system:
    1. Increases the inventory quantity by the consumed amount
    2. Creates a transaction record for the adjustment
    """
    try:
        with transaction.atomic():
            # Get inventory
            inventory = FeedInventory.objects.select_for_update().get(fodder_type=instance.fodder_type)

            # Store previous value for transaction record
            previous_balance = inventory.quantity_on_hand

            # Update inventory quantity
            inventory.quantity_on_hand += instance.quantity_consumed
            inventory.save()

            # Create inventory transaction record
            InventoryTransaction.objects.create(
                fodder_type=instance.fodder_type,
                transaction_type='ADJUSTMENT',
                date=timezone.now().date(),
                quantity=instance.quantity_consumed,  # Positive for addition
                unit_value=instance.fodder_type.current_cost_per_unit,
                total_value=instance.cost_at_consumption or (
                        instance.quantity_consumed * instance.fodder_type.current_cost_per_unit
                ),
                reference_model='FeedConsumption (Deleted)',
                reference_id=instance.id,
                previous_balance=previous_balance,
                new_balance=inventory.quantity_on_hand,
                notes=f"Reversal of consumption record #{instance.id} deletion"
            )

    except FeedInventory.DoesNotExist:
        # No inventory record to adjust
        pass


@receiver(pre_delete, sender=InHouseFeedProduction)
def handle_production_deletion(sender, instance, **kwargs):
    """
    Handle inventory adjustment when a production record is deleted.

    This function reverses the effect of production on the inventory system:
    1. Decreases the inventory quantity by the produced amount
    2. Updates the weighted average cost if needed
    3. Creates a transaction record for the adjustment
    """
    try:
        with transaction.atomic():
            # Get inventory
            inventory = FeedInventory.objects.select_for_update().get(fodder_type=instance.fodder_type)

            # Store previous value for transaction record
            previous_balance = inventory.quantity_on_hand

            # Update inventory quantity
            inventory.quantity_on_hand -= instance.quantity_produced

            # Ensure inventory doesn't go negative
            if inventory.quantity_on_hand < 0:
                inventory.quantity_on_hand = 0

            inventory.save()

            # Create inventory transaction record
            InventoryTransaction.objects.create(
                fodder_type=instance.fodder_type,
                transaction_type='ADJUSTMENT',
                date=timezone.now().date(),
                quantity=-instance.quantity_produced,  # Negative for reduction
                unit_value=instance.cost_per_unit,
                total_value=-(instance.total_production_cost),
                reference_model='InHouseFeedProduction (Deleted)',
                reference_id=instance.id,
                previous_balance=previous_balance,
                new_balance=inventory.quantity_on_hand,
                notes=f"Reversal of production record #{instance.id} deletion"
            )

    except FeedInventory.DoesNotExist:
        # No inventory record to adjust
        pass


@receiver(post_save, sender=FodderType)
def create_initial_inventory(sender, instance, created, **kwargs):
    """
    Create an initial inventory record when a new fodder type is created.

    This ensures that every fodder type has an associated inventory record
    for easier tracking and reporting.
    """
    if created:
        FeedInventory.objects.get_or_create(
            fodder_type=instance,
            defaults={
                'quantity_on_hand': 0,
                'location': 'Main Storage'
            }
        )


# Connect these signals to the apps.py ready method
def connect_signals():
    # The functions above will automatically connect due to the @receiver decorator
    # This function is just a placeholder called in apps.py to ensure
    # that this module is imported when the app is ready
    pass