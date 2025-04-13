"""
URL Configuration for the Inventory app in Super Duper Dairy ERP System

This module defines the URL patterns for the inventory management functionality,
organizing routes by feature area (fodder types, inventory, purchases, consumption, etc.).
"""

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard
    path('', views.InventoryDashboardView.as_view(), name='dashboard'),

    # Fodder Types
    path('fodder-types/', views.FodderTypeListView.as_view(), name='fodder_type_list'),
    path('fodder-types/add/', views.FodderTypeCreateView.as_view(), name='fodder_type_add'),
    path('fodder-types/<int:pk>/', views.FodderTypeDetailView.as_view(), name='fodder_type_detail'),
    path('fodder-types/<int:pk>/edit/', views.FodderTypeUpdateView.as_view(), name='fodder_type_edit'),

    # Inventory Management
    path('levels/', views.InventoryListView.as_view(), name='inventory_list'),
    path('levels/add/', views.InventoryCreateView.as_view(), name='inventory_add'),
    path('levels/<int:pk>/edit/', views.InventoryUpdateView.as_view(), name='inventory_edit'),

    # Purchases
    path('purchases/', views.PurchaseListView.as_view(), name='purchase_list'),
    path('purchases/add/', views.PurchaseCreateView.as_view(), name='purchase_add'),
    path('purchases/<int:pk>/edit/', views.PurchaseUpdateView.as_view(), name='purchase_edit'),
    path('purchases/<int:pk>/delete/', views.PurchaseDeleteView.as_view(), name='purchase_delete'),

    # Consumption
    path('consumption/', views.ConsumptionListView.as_view(), name='consumption_list'),
    path('consumption/add/', views.ConsumptionCreateView.as_view(), name='consumption_add'),
    path('consumption/batch/', views.BatchConsumptionView.as_view(), name='batch_consumption'),
    path('consumption/<int:pk>/edit/', views.ConsumptionUpdateView.as_view(), name='consumption_edit'),
    path('consumption/<int:pk>/delete/', views.ConsumptionDeleteView.as_view(), name='consumption_delete'),

    # In-House Production
    path('production/', views.ProductionListView.as_view(), name='production_list'),
    path('production/add/', views.ProductionCreateView.as_view(), name='production_add'),
    path('production/<int:pk>/edit/', views.ProductionUpdateView.as_view(), name='production_edit'),
    path('production/<int:pk>/delete/', views.ProductionDeleteView.as_view(), name='production_delete'),

    # Transactions (Audit Log)
    path('transactions/', views.InventoryTransactionListView.as_view(), name='transaction_list'),
    path('transactions/<int:pk>/', views.InventoryTransactionDetailView.as_view(), name='transaction_detail'),

    # Reports
    path('reports/inventory/', views.InventoryReportView.as_view(), name='inventory_report'),
    path('reports/inventory/export-csv/', views.ExportInventoryCSVView.as_view(), name='export_inventory_csv'),
    path('reports/consumption/export-csv/', views.ExportConsumptionCSVView.as_view(), name='export_consumption_csv'),

    # API Endpoints for AJAX
    path('api/fodder-types/autocomplete/', views.FodderTypeAutocompleteView.as_view(), name='fodder_type_autocomplete'),
    path('api/inventory-level/<int:fodder_id>/', views.GetInventoryLevelView.as_view(), name='get_inventory_level'),
    path('api/animal-count/<str:group>/', views.GetAnimalCountView.as_view(), name='get_animal_count'),
]