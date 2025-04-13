"""
Custom template tags and filters for the Inventory app

This module provides template tags and filters for displaying inventory-related
information in Django templates, including formatting and calculation helpers.
"""

from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

from inventory.models import FodderType, FeedInventory, FeedConsumption

register = template.Library()


@register.filter
def format_quantity(value, unit):
    """
    Format a quantity with its unit

    Args:
        value: The quantity value
        unit: The unit of measurement

    Returns:
        Formatted string with quantity and unit
    """
    if value is None:
        return "-"

    # Format as integer if it's a whole number
    if float(value) == int(float(value)):
        return f"{int(value)} {unit}"

    # Otherwise format with 2 decimal places
    return f"{value:.2f} {unit}"


@register.filter
def percentage_of(value, total):
    """
    Calculate what percentage value is of total

    Args:
        value: The part value
        total: The total value

    Returns:
        Percentage as a formatted string
    """
    try:
        value = float(value)
        total = float(total)
        if total == 0:
            return "0%"

        percentage = (value / total) * 100
        return f"{percentage:.1f}%"
    except (ValueError, TypeError):
        return "0%"


@register.simple_tag
def stock_status_badge(fodder_type_id):
    """
    Generate a color-coded badge for the current stock status of a fodder type

    Args:
        fodder_type_id: The ID of the fodder type

    Returns:
        HTML for a colored badge indicating stock status
    """
    try:
        fodder_type = FodderType.objects.get(id=fodder_type_id)
        inventory = FeedInventory.objects.filter(fodder_type=fodder_type).first()

        if not inventory or inventory.quantity_on_hand == 0:
            return mark_safe('<span class="badge badge-danger">OUT OF STOCK</span>')

        if fodder_type.is_below_min_stock():
            return mark_safe('<span class="badge badge-warning">LOW STOCK</span>')

        return mark_safe('<span class="badge badge-success">ADEQUATE</span>')
    except FodderType.DoesNotExist:
        return ""


@register.simple_tag
def get_consumption_trend(fodder_type_id, days=30):
    """
    Calculate consumption trend for a fodder type over the specified period

    Args:
        fodder_type_id: The ID of the fodder type
        days: Number of days to analyze (default: 30)

    Returns:
        A dictionary with consumption data
    """
    try:
        fodder_type = FodderType.objects.get(id=fodder_type_id)

        # Get date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Get consumption in the period
        consumption = FeedConsumption.objects.filter(
            fodder_type=fodder_type,
            date__range=[start_date, end_date]
        ).order_by('date')

        # Calculate total consumption
        total_consumed = sum(record.quantity_consumed for record in consumption)

        # Calculate average daily consumption
        if days > 0:
            avg_daily = total_consumed / days
        else:
            avg_daily = 0

        # Calculate days of inventory left
        inventory = FeedInventory.objects.filter(fodder_type=fodder_type).first()
        if inventory and avg_daily > 0:
            days_left = inventory.quantity_on_hand / avg_daily
        else:
            days_left = None

        return {
            'total_consumed': total_consumed,
            'avg_daily': avg_daily,
            'days_left': days_left
        }
    except FodderType.DoesNotExist:
        return {
            'total_consumed': 0,
            'avg_daily': 0,
            'days_left': None
        }


@register.simple_tag
def days_of_stock_badge(days_left):
    """
    Generate a color-coded badge for days of stock remaining

    Args:
        days_left: Number of days of stock remaining

    Returns:
        HTML for a colored badge indicating days of stock
    """
    if days_left is None:
        return mark_safe('<span class="badge badge-secondary">N/A</span>')

    if days_left <= 7:
        return mark_safe(f'<span class="badge badge-danger">{days_left:.1f} days</span>')

    if days_left <= 30:
        return mark_safe(f'<span class="badge badge-warning">{days_left:.1f} days</span>')

    return mark_safe(f'<span class="badge badge-success">{days_left:.1f} days</span>')


@register.filter
def transaction_type_badge(transaction_type):
    """
    Generate a color-coded badge for transaction types

    Args:
        transaction_type: The transaction type code

    Returns:
        HTML for a colored badge with the transaction type
    """
    badges = {
        'PURCHASE': 'badge-primary',
        'CONSUMPTION': 'badge-warning',
        'PRODUCTION': 'badge-success',
        'ADJUSTMENT': 'badge-info',
        'TRANSFER': 'badge-secondary',
        'RETURN': 'badge-danger',
        'WASTAGE': 'badge-dark'
    }

    badge_class = badges.get(transaction_type, 'badge-secondary')
    return mark_safe(f'<span class="badge {badge_class}">{transaction_type}</span>')


@register.filter
def quantity_with_sign(value):
    """
    Format a quantity with a sign (+ or -) and colorize based on sign

    Args:
        value: The quantity value

    Returns:
        HTML with formatted quantity and color
    """
    if value is None:
        return "-"

    try:
        value = float(value)
        if value > 0:
            return mark_safe(f'<span class="text-success">+{value:.2f}</span>')
        elif value < 0:
            return mark_safe(f'<span class="text-danger">{value:.2f}</span>')
        else:
            return "0.00"
    except (ValueError, TypeError):
        return str(value)

@register.filter
def multiply(value, arg):
    """
    Multiply two numerical values and return the result.

    Args:
        value: The first number (quantity)
        arg: The second number (current cost per unit)

    Returns:
        Product of the two numbers or an empty string in case of error.
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''