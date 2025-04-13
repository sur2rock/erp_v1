"""
urls.py

This file defines URL patterns for the finance app.
It includes both view-based URLs and DRF API endpoints (using a DefaultRouter).
Each URL pattern is documented to explain its purpose.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a DRF router and register viewsets for API endpoints.
router = DefaultRouter()
router.register(r'expense-categories', views.ExpenseCategoryViewSet)
router.register(r'income-categories', views.IncomeCategoryViewSet)
router.register(r'expenses', views.ExpenseRecordViewSet)
router.register(r'income', views.IncomeRecordViewSet)
router.register(r'profitability', views.ProfitabilityViewSet)

app_name = 'finance'

urlpatterns = [
    # ----------------- Expense Category URLs -----------------
    # List all expense categories.
    path('expense-categories/', views.expense_category_list, name='expense_category_list'),
    # Add a new expense category.
    path('expense-categories/add/', views.expense_category_add, name='expense_category_add'),
    # Edit an existing expense category.
    path('expense-categories/<int:category_id>/edit/', views.expense_category_edit, name='expense_category_edit'),

    # ----------------- Income Category URLs -----------------
    # List all income categories.
    path('income-categories/', views.income_category_list, name='income_category_list'),
    # Add a new income category.
    path('income-categories/add/', views.income_category_add, name='income_category_add'),
    # Edit an existing income category.
    path('income-categories/<int:category_id>/edit/', views.income_category_edit, name='income_category_edit'),

    # ----------------- Expense Record URLs -----------------
    # List expense records with optional filters.
    path('expenses/', views.expense_list, name='expense_list'),
    # Create a new expense record.
    path('expenses/add/', views.expense_add, name='expense_add'),
    # Edit an expense record.
    path('expenses/<int:expense_id>/edit/', views.expense_edit, name='expense_edit'),
    # Delete an expense record (with confirmation page).
    path('expenses/<int:expense_id>/delete/', views.expense_delete, name='expense_delete'),
    # Export filtered expense records as CSV.
    path('expenses/export/', views.export_expenses, name='export_expenses'),

    # ----------------- Income Record URLs -----------------
    # List income records with optional filters.
    path('income/', views.income_list, name='income_list'),
    # Create a new income record.
    path('income/add/', views.income_add, name='income_add'),
    # Edit an income record.
    path('income/<int:income_id>/edit/', views.income_edit, name='income_edit'),
    # Delete an income record.
    path('income/<int:income_id>/delete/', views.income_delete, name='income_delete'),
    # Export filtered income records as CSV.
    path('income/export/', views.export_income, name='export_income'),
    # Generate milk income records based on milk production data.
    path('income/generate-milk-income/', views.milk_income_generator, name='milk_income_generator'),

    # ----------------- Profitability URLs -----------------
    # View profitability reports with charts and KPIs.
    path('profitability/', views.profitability, name='profitability'),
    # Manually trigger profitability calculation for a specific month.
    path('profitability/calculate/', views.calculate_profitability, name='calculate_profitability'),
    # Export profitability data as CSV.
    path('profitability/export/', views.export_profitability, name='export_profitability'),

    # ----------------- API URLs -----------------
    # Include the DRF router URLs for API endpoints.
    path('api/', include(router.urls)),
]
