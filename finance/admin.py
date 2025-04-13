"""
admin.py

This file registers the finance app models with the Django admin site.
It defines custom ModelAdmin classes to improve the admin interface with list displays,
filters, search fields, and autocomplete for related models.
"""

from django.contrib import admin
from .models import ExpenseCategory, IncomeCategory, ExpenseRecord, IncomeRecord, Profitability

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    """
    Custom admin interface for ExpenseCategory.
    - list_display: Shows 'name', 'is_direct_cost' flag, and 'description' on the change list page.
    - list_filter: Allows filtering by whether the expense is a direct cost.
    - search_fields: Enables searching by the category name.
    """
    list_display = ('name', 'is_direct_cost', 'description')
    list_filter = ('is_direct_cost',)
    search_fields = ('name',)

@admin.register(IncomeCategory)
class IncomeCategoryAdmin(admin.ModelAdmin):
    """
    Custom admin interface for IncomeCategory.
    - list_display: Displays the income category name and description.
    - search_fields: Enables searching based on the income category name.
    """
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(ExpenseRecord)
class ExpenseRecordAdmin(admin.ModelAdmin):
    """
    Custom admin interface for ExpenseRecord.
    - list_display: Displays key fields (date, category, description, amount, etc.).
    - list_filter: Enables filtering by category and date.
    - search_fields: Allows searching by description and supplier/vendor.
    - date_hierarchy: Provides navigation by date.
    - autocomplete_fields: Uses an autocomplete widget for the 'related_buffalo' field.
    """
    list_display = ('date', 'category', 'description', 'amount', 'supplier_vendor', 'related_buffalo')
    list_filter = ('category', 'date')
    search_fields = ('description', 'supplier_vendor')
    date_hierarchy = 'date'
    autocomplete_fields = ['related_buffalo']

@admin.register(IncomeRecord)
class IncomeRecordAdmin(admin.ModelAdmin):
    """
    Custom admin interface for IncomeRecord.
    - list_display: Shows important income record fields including amounts and linked buffalo.
    - list_filter: Allows filtering by category and date.
    - search_fields: Enables search on description and customer fields.
    - date_hierarchy: Provides navigation based on date.
    - autocomplete_fields: Uses autocomplete for the 'related_buffalo' field.
    """
    list_display = ('date', 'category', 'description', 'quantity', 'unit_price', 'total_amount', 'customer', 'related_buffalo')
    list_filter = ('category', 'date')
    search_fields = ('description', 'customer')
    date_hierarchy = 'date'
    autocomplete_fields = ['related_buffalo']

@admin.register(Profitability)
class ProfitabilityAdmin(admin.ModelAdmin):
    """
    Custom admin interface for Profitability.
    - list_display: Shows year, month, and key financial metrics.
    - list_filter: Enables filtering by year.
    - date_hierarchy: Uses 'calculated_at' to navigate by date.
    - readonly_fields: Marks the calculated_at field as read-only.
    """
    list_display = ('year', 'month', 'total_income', 'direct_costs', 'indirect_costs', 'gross_profit', 'net_profit')
    list_filter = ('year',)
    date_hierarchy = 'calculated_at'
    readonly_fields = ('calculated_at',)
