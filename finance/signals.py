"""
finance/signals.py

Defines Django signals to update dependent models when finance data changes.
For example, when an ExpenseRecord is saved, update the cumulative cost of the related buffalo.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from django.db.models import Sum
from .models import ExpenseRecord, Buffalo

@receiver(post_save, sender=ExpenseRecord)
def update_buffalo_cumulative_cost(sender, instance, **kwargs):
    """
    Signal triggered after an ExpenseRecord is saved.
    This function recalculates the cumulative cost for the related buffalo and updates it.
    """
    if instance.related_buffalo:
        total_cost = ExpenseRecord.objects.filter(related_buffalo=instance.related_buffalo).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        instance.related_buffalo.cumulative_cost = total_cost
        instance.related_buffalo.save(update_fields=['cumulative_cost'])
