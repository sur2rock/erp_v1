"""
Views for the Inventory app in Super Duper Dairy ERP System

This module defines the views for managing inventory, including:
- Dashboard views for inventory overview
- CRUD views for fodder types, inventory records, purchases, and consumption
- Special views for batch operations and reporting
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Sum, Avg, F, Q, Count
from django.db.models.functions import TruncMonth, TruncYear
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import json
from datetime import timedelta, date
import csv

from .models import (
    FodderType,
    FeedInventory,
    FeedPurchase,
    FeedConsumption,
    InHouseFeedProduction,
    InventoryTransaction
)
from .forms import (
    FodderTypeForm,
    FeedInventoryForm,
    FeedPurchaseForm,
    FeedConsumptionForm,
    InHouseFeedProductionForm,
    BatchMilkConsumptionForm
)

# Try to import Buffalo model if it exists for batch consumption
try:
    from herd.models import Buffalo

    BUFFALO_MODEL_EXISTS = True
except ImportError:
    BUFFALO_MODEL_EXISTS = False


class InventoryDashboardView(LoginRequiredMixin, TemplateView):
    """
    Inventory dashboard showing overview of current inventory status,
    recent transactions, and alerts.
    """
    template_name = 'dairy_erp/inventory/inventory_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get inventory summary
        inventory_summary = FeedInventory.objects.select_related('fodder_type').all()

        # Calculate low stock items
        low_stock_items = []
        for inv in inventory_summary:
            if inv.fodder_type.is_below_min_stock():
                low_stock_items.append(inv)

        # Get recent purchases
        recent_purchases = FeedPurchase.objects.select_related('fodder_type').order_by('-date')[:10]

        # Get recent consumption
        recent_consumption = FeedConsumption.objects.select_related('fodder_type').order_by('-date')[:10]

        # Get recent transactions
        recent_transactions = InventoryTransaction.objects.select_related('fodder_type').order_by('-date',
                                                                                                  '-created_at')[:20]

        # Calculate inventory value
        total_inventory_value = sum(
            inv.quantity_on_hand * inv.fodder_type.current_cost_per_unit
            for inv in inventory_summary
        )

        # Calculate monthly consumption (for chart)
        today = timezone.now().date()
        start_date = today - timedelta(days=180)  # Last 6 months

        monthly_consumption = FeedConsumption.objects.filter(
            date__gte=start_date
        ).annotate(
            month=TruncMonth('date')
        ).values('month', 'fodder_type__name').annotate(
            total_consumed=Sum('quantity_consumed')
        ).order_by('month', 'fodder_type__name')

        # Chart data
        chart_data = {
            'labels': [],
            'datasets': []
        }

        if monthly_consumption:
            # Get unique months and fodder types
            months = sorted(set(item['month'] for item in monthly_consumption))
            fodder_types = set(item['fodder_type__name'] for item in monthly_consumption)

            # Prepare labels (months)
            chart_data['labels'] = [month.strftime('%b %Y') for month in months]

            # Prepare datasets (one per fodder type)
            colors = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796', '#5a5c69']
            for i, fodder_type in enumerate(fodder_types):
                dataset = {
                    'label': fodder_type,
                    'backgroundColor': colors[i % len(colors)],
                    'borderColor': colors[i % len(colors)],
                    'data': []
                }

                # Fill in data for each month
                for month in months:
                    value = 0
                    for item in monthly_consumption:
                        if item['month'] == month and item['fodder_type__name'] == fodder_type:
                            value = float(item['total_consumed'])
                            break
                    dataset['data'].append(value)

                chart_data['datasets'].append(dataset)

        context.update({
            'inventory_summary': inventory_summary,
            'low_stock_items': low_stock_items,
            'recent_purchases': recent_purchases,
            'recent_consumption': recent_consumption,
            'recent_transactions': recent_transactions,
            'total_inventory_value': total_inventory_value,
            'chart_data': json.dumps(chart_data)
        })

        return context


# FodderType Views

class FodderTypeListView(LoginRequiredMixin, ListView):
    """List view for fodder types"""
    model = FodderType
    template_name = 'dairy_erp/inventory/fodder_type_list.html'
    context_object_name = 'fodder_types'

    def get_queryset(self):
        """Get fodder types with inventory information"""
        return FodderType.objects.all().prefetch_related('inventory')


class FodderTypeDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single fodder type"""
    model = FodderType
    template_name = 'dairy_erp/inventory/fodder_type_detail.html'
    context_object_name = 'fodder_type'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fodder_type = self.object

        # Get inventory
        try:
            inventory = FeedInventory.objects.get(fodder_type=fodder_type)
        except FeedInventory.DoesNotExist:
            inventory = None

        # Get purchase history
        purchases = FeedPurchase.objects.filter(fodder_type=fodder_type).order_by('-date')[:10]

        # Get consumption history
        consumption = FeedConsumption.objects.filter(fodder_type=fodder_type).order_by('-date')[:10]

        # Get in-house production (if applicable)
        if fodder_type.is_produced_in_house:
            production = InHouseFeedProduction.objects.filter(fodder_type=fodder_type).order_by('-date')[:10]
        else:
            production = None

        # Chart data for historical cost/unit
        today = timezone.now().date()
        start_date = today - timedelta(days=365)  # Last year

        price_history = FeedPurchase.objects.filter(
            fodder_type=fodder_type,
            date__gte=start_date
        ).order_by('date')

        price_chart = {
            'labels': [purchase.date.strftime('%d-%b-%Y') for purchase in price_history],
            'datasets': [{
                'label': _('Cost per Unit'),
                'data': [float(purchase.cost_per_unit) for purchase in price_history],
                'borderColor': '#4e73df',
                'backgroundColor': 'rgba(78, 115, 223, 0.05)',
                'fill': True
            }]
        }

        context.update({
            'inventory': inventory,
            'purchases': purchases,
            'consumption': consumption,
            'production': production,
            'price_chart': json.dumps(price_chart)
        })

        return context


class FodderTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for a new fodder type"""
    model = FodderType
    form_class = FodderTypeForm
    template_name = 'dairy_erp/inventory/fodder_type_form.html'
    permission_required = 'inventory.add_foddertype'

    def get_success_url(self):
        messages.success(self.request, _("Fodder type created successfully"))
        return reverse_lazy('inventory:fodder_type_list')


class FodderTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update view for an existing fodder type"""
    model = FodderType
    form_class = FodderTypeForm
    template_name = 'dairy_erp/inventory/fodder_type_form.html'
    permission_required = 'inventory.change_foddertype'

    def get_success_url(self):
        messages.success(self.request, _("Fodder type updated successfully"))
        return reverse_lazy('inventory:fodder_type_detail', kwargs={'pk': self.object.pk})


# Feed Inventory Views

class InventoryListView(LoginRequiredMixin, ListView):
    """List view for all inventory records"""
    model = FeedInventory
    template_name = 'dairy_erp/inventory/inventory_list.html'
    context_object_name = 'inventory_items'

    def get_queryset(self):
        """Get inventory with related fodder type information"""
        return FeedInventory.objects.select_related('fodder_type').all()


class InventoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update view for adjusting inventory levels"""
    model = FeedInventory
    form_class = FeedInventoryForm
    template_name = 'dairy_erp/inventory/inventory_form.html'
    permission_required = 'inventory.change_feedinventory'

    def get_success_url(self):
        messages.success(self.request, _("Inventory updated successfully"))
        return reverse_lazy('inventory:inventory_list')


class InventoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for a new inventory record"""
    model = FeedInventory
    form_class = FeedInventoryForm
    template_name = 'dairy_erp/inventory/inventory_form.html'
    permission_required = 'inventory.add_feedinventory'

    def get_success_url(self):
        messages.success(self.request, _("Inventory record created successfully"))
        return reverse_lazy('inventory:inventory_list')


# Feed Purchase Views

class PurchaseListView(LoginRequiredMixin, ListView):
    """List view for feed purchases"""
    model = FeedPurchase
    template_name = 'dairy_erp/inventory/purchase_list.html'
    context_object_name = 'purchases'

    def get_queryset(self):
        """Filter purchases by date if provided"""
        queryset = FeedPurchase.objects.select_related('fodder_type').order_by('-date')

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter form data
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')

        # Calculate totals
        purchases = context['purchases']
        context['total_cost'] = sum(purchase.total_cost for purchase in purchases)

        return context


class PurchaseCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for recording a new feed purchase"""
    model = FeedPurchase
    form_class = FeedPurchaseForm
    template_name = 'dairy_erp/inventory/purchase_form.html'
    permission_required = 'inventory.add_feedpurchase'

    def get_success_url(self):
        messages.success(
            self.request,
            _("Purchase recorded successfully. Inventory has been updated.")
        )
        return reverse_lazy('inventory:purchase_list')


class PurchaseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update view for an existing purchase record"""
    model = FeedPurchase
    form_class = FeedPurchaseForm
    template_name = 'dairy_erp/inventory/purchase_form.html'
    permission_required = 'inventory.change_feedpurchase'

    def get_success_url(self):
        messages.success(self.request, _("Purchase record updated successfully"))
        return reverse_lazy('inventory:purchase_list')


class PurchaseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete view for a purchase record"""
    model = FeedPurchase
    template_name = 'dairy_erp/inventory/purchase_delete.html'
    permission_required = 'inventory.delete_feedpurchase'
    success_url = reverse_lazy('inventory:purchase_list')

    def delete(self, request, *args, **kwargs):
        """Override delete to prevent deletion if inventory depends on it"""
        purchase = self.get_object()

        # Check if this would cause negative inventory
        try:
            inventory = FeedInventory.objects.get(fodder_type=purchase.fodder_type)
            if inventory.quantity_on_hand < purchase.quantity_purchased:
                messages.error(
                    request,
                    _("Cannot delete this purchase: It would result in negative inventory. Adjust consumption records first.")
                )
                return redirect('inventory:purchase_list')
        except FeedInventory.DoesNotExist:
            pass  # If no inventory exists, deletion is okay

        messages.success(request, _("Purchase record deleted successfully"))
        return super().delete(request, *args, **kwargs)


# Feed Consumption Views

class ConsumptionListView(LoginRequiredMixin, ListView):
    """List view for feed consumption records"""
    model = FeedConsumption
    template_name = 'dairy_erp/inventory/consumption_list.html'
    context_object_name = 'consumption_records'

    def get_queryset(self):
        """Filter consumption by date if provided"""
        queryset = FeedConsumption.objects.select_related('fodder_type').order_by('-date')

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter form data
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')

        return context


class ConsumptionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for recording feed consumption"""
    model = FeedConsumption
    form_class = FeedConsumptionForm
    template_name = 'dairy_erp/inventory/consumption_form.html'
    permission_required = 'inventory.add_feedconsumption'

    def get_success_url(self):
        messages.success(
            self.request,
            _("Consumption recorded successfully. Inventory has been updated.")
        )
        return reverse_lazy('inventory:consumption_list')


class ConsumptionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update view for an existing consumption record"""
    model = FeedConsumption
    form_class = FeedConsumptionForm
    template_name = 'dairy_erp/inventory/consumption_form.html'
    permission_required = 'inventory.change_feedconsumption'

    def get_success_url(self):
        messages.success(self.request, _("Consumption record updated successfully"))
        return reverse_lazy('inventory:consumption_list')


class ConsumptionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete view for a consumption record"""
    model = FeedConsumption
    template_name = 'dairy_erp/inventory/consumption_delete.html'
    permission_required = 'inventory.delete_feedconsumption'
    success_url = reverse_lazy('inventory:consumption_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Consumption record deleted successfully"))
        return super().delete(request, *args, **kwargs)


class BatchConsumptionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View for recording batch consumption for multiple animals"""
    permission_required = 'inventory.add_feedconsumption'
    template_name = 'dairy_erp/inventory/batch_consumption_form.html'

    def get(self, request):
        form = BatchMilkConsumptionForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = BatchMilkConsumptionForm(request.POST)

        if form.is_valid() and BUFFALO_MODEL_EXISTS:
            # Get form data
            date_val = form.cleaned_data['date']
            fodder_type = form.cleaned_data['fodder_type']
            quantity_per_animal = form.cleaned_data['quantity_per_animal']
            group = form.cleaned_data['group']
            notes = form.cleaned_data['notes']

            # Get animals based on group
            if group == 'ALL':
                animals = Buffalo.objects.filter(is_active=True)
            elif group == 'MILKING':
                animals = Buffalo.objects.filter(is_active=True, status='Active-Milking')
            elif group == 'DRY':
                animals = Buffalo.objects.filter(is_active=True, status='Active-Dry')
            elif group == 'PREGNANT':
                animals = Buffalo.objects.filter(is_active=True, status='Active-Pregnant')
            elif group == 'CALVES':
                animals = Buffalo.objects.filter(is_active=True, status__in=['Calf', 'Heifer'])
            else:
                animals = []

            if animals:
                # Get or create inventory
                try:
                    inventory = FeedInventory.objects.get(fodder_type=fodder_type)
                except FeedInventory.DoesNotExist:
                    messages.error(request, _("No inventory exists for this fodder type"))
                    return render(request, self.template_name, {'form': form})

                # Calculate total consumption
                total_quantity = quantity_per_animal * animals.count()

                # Check inventory
                if inventory.quantity_on_hand < total_quantity:
                    messages.error(
                        request,
                        _("Insufficient inventory. Required: {} {}, Available: {} {}").format(
                            total_quantity, fodder_type.unit,
                            inventory.quantity_on_hand, fodder_type.unit)
                    )
                    return render(request, self.template_name, {'form': form})

                # Create consumption record
                consumption = FeedConsumption.objects.create(
                    fodder_type=fodder_type,
                    date=date_val,
                    quantity_consumed=total_quantity,
                    consumed_by='GROUP',
                    group_name=f"Batch: {group}",
                    notes=f"{notes}\nBatch consumption for {animals.count()} animals ({group})"
                )

                messages.success(
                    request,
                    _("Batch consumption recorded successfully for {} animals. Total consumed: {} {}.").format(
                        animals.count(), total_quantity, fodder_type.unit
                    )
                )
                return redirect('inventory:consumption_list')
            else:
                messages.error(request, _("No animals found in the selected group"))
                return render(request, self.template_name, {'form': form})

        return render(request, self.template_name, {'form': form})


# In-House Production Views

class ProductionListView(LoginRequiredMixin, ListView):
    """List view for in-house feed production records"""
    model = InHouseFeedProduction
    template_name = 'dairy_erp/inventory/production_list.html'
    context_object_name = 'production_records'

    def get_queryset(self):
        """Filter production by date if provided"""
        queryset = InHouseFeedProduction.objects.select_related('fodder_type').order_by('-date')

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter form data
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')

        return context


class ProductionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for recording in-house feed production"""
    model = InHouseFeedProduction
    form_class = InHouseFeedProductionForm
    template_name = 'dairy_erp/inventory/production_form.html'
    permission_required = 'inventory.add_inhousefeedproduction'

    def get_success_url(self):
        messages.success(
            self.request,
            _("Production recorded successfully. Inventory has been updated.")
        )
        return reverse_lazy('inventory:production_list')


class ProductionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update view for an existing production record"""
    model = InHouseFeedProduction
    form_class = InHouseFeedProductionForm
    template_name = 'dairy_erp/inventory/production_form.html'
    permission_required = 'inventory.change_inhousefeedproduction'

    def get_success_url(self):
        messages.success(self.request, _("Production record updated successfully"))
        return reverse_lazy('inventory:production_list')


class ProductionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete view for a production record"""
    model = InHouseFeedProduction
    template_name = 'dairy_erp/inventory/production_delete.html'
    permission_required = 'inventory.delete_inhousefeedproduction'
    success_url = reverse_lazy('inventory:production_list')

    def delete(self, request, *args, **kwargs):
        """Override delete to prevent deletion if inventory depends on it"""
        production = self.get_object()

        # Check if this would cause negative inventory
        try:
            inventory = FeedInventory.objects.get(fodder_type=production.fodder_type)
            if inventory.quantity_on_hand < production.quantity_produced:
                messages.error(
                    request,
                    _("Cannot delete this production record: It would result in negative inventory. Adjust consumption records first.")
                )
                return redirect('inventory:production_list')
        except FeedInventory.DoesNotExist:
            pass  # If no inventory exists, deletion is okay

        messages.success(request, _("Production record deleted successfully"))
        return super().delete(request, *args, **kwargs)


# Inventory Transactions View

class InventoryTransactionListView(LoginRequiredMixin, ListView):
    """List view for inventory transactions (audit log)"""
    model = InventoryTransaction
    template_name = 'dairy_erp/inventory/inventory_transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 50

    def get_queryset(self):
        """Filter transactions by various parameters"""
        queryset = InventoryTransaction.objects.select_related('fodder_type').order_by('-date', '-created_at')

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        # Filter by transaction type if provided
        transaction_type = self.request.GET.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        # Filter by fodder type if provided
        fodder_type_id = self.request.GET.get('fodder_type')
        if fodder_type_id and fodder_type_id.isdigit():
            queryset = queryset.filter(fodder_type_id=int(fodder_type_id))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter form data
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['transaction_type'] = self.request.GET.get('transaction_type', '')
        context['fodder_type_id'] = self.request.GET.get('fodder_type', '')

        # Add fodder types for filter
        context['fodder_types'] = FodderType.objects.all()

        # Add transaction types for filter
        context['transaction_types'] = [
            {'value': t[0], 'label': t[1]}
            for t in InventoryTransaction.TRANSACTION_TYPES
        ]

        return context


class InventoryTransactionDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single inventory transaction"""
    model = InventoryTransaction
    template_name = 'dairy_erp/inventory/inventory_transaction_detail.html'
    context_object_name = 'transaction'


# Report Views

class InventoryReportView(LoginRequiredMixin, TemplateView):
    """View for generating inventory reports"""
    template_name = 'dairy_erp/inventory/inventory_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current inventory with value
        inventory = FeedInventory.objects.select_related('fodder_type').all()

        # Calculate inventory value
        for item in inventory:
            item.value = item.quantity_on_hand * item.fodder_type.current_cost_per_unit

        # Categorize by fodder type category
        categorized_inventory = {}
        for item in inventory:
            category = item.fodder_type.get_category_display()
            if category not in categorized_inventory:
                categorized_inventory[category] = {
                    'items': [],
                    'total_value': 0,
                }
            categorized_inventory[category]['items'].append(item)
            categorized_inventory[category]['total_value'] += item.value

        # Calculate total inventory value
        total_inventory_value = sum(item.value for item in inventory)

        # Get monthly consumption data for the last year
        today = timezone.now().date()
        start_date = today - timedelta(days=365)

        monthly_consumption = FeedConsumption.objects.filter(
            date__gte=start_date
        ).annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            total_consumed=Sum('quantity_consumed'),
            total_cost=Sum('cost_at_consumption')
        ).order_by('month')

        # Prepare monthly consumption chart data
        consumption_chart = {
            'labels': [item['month'].strftime('%b %Y') for item in monthly_consumption],
            'datasets': [
                {
                    'label': _('Quantity Consumed'),
                    'data': [float(item['total_consumed']) for item in monthly_consumption],
                    'borderColor': '#4e73df',
                    'backgroundColor': 'rgba(78, 115, 223, 0.05)',
                    'yAxisID': 'y-quantity'
                },
                {
                    'label': _('Cost'),
                    'data': [float(item['total_cost'] or 0) for item in monthly_consumption],
                    'borderColor': '#1cc88a',
                    'backgroundColor': 'rgba(28, 200, 138, 0.05)',
                    'yAxisID': 'y-cost'
                }
            ]
        }

        context.update({
            'inventory': inventory,
            'categorized_inventory': categorized_inventory,
            'total_inventory_value': total_inventory_value,
            'consumption_chart': json.dumps(consumption_chart)
        })

        return context


class ExportInventoryCSVView(LoginRequiredMixin, View):
    """View for exporting current inventory to CSV"""

    def get(self, request):
        # Create response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventory_export_{}.csv"'.format(
            timezone.now().strftime('%Y%m%d')
        )

        # Create CSV writer
        writer = csv.writer(response)

        # Write header
        writer.writerow([
            _('Fodder Type'),
            _('Category'),
            _('Unit'),
            _('Current Quantity'),
            _('Cost per Unit'),
            _('Total Value'),
            _('Location'),
            _('Last Updated')
        ])

        # Get inventory data
        inventory = FeedInventory.objects.select_related('fodder_type').all()

        # Write data rows
        for item in inventory:
            writer.writerow([
                item.fodder_type.name,
                item.fodder_type.get_category_display(),
                item.fodder_type.unit,
                item.quantity_on_hand,
                item.fodder_type.current_cost_per_unit,
                item.quantity_on_hand * item.fodder_type.current_cost_per_unit,
                item.location or '',
                item.last_updated.strftime('%Y-%m-%d %H:%M')
            ])

        return response


class ExportConsumptionCSVView(LoginRequiredMixin, View):
    """View for exporting consumption data to CSV"""

    def get(self, request):
        # Get date range filters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Create response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="consumption_export_{}.csv"'.format(
            timezone.now().strftime('%Y%m%d')
        )

        # Create CSV writer
        writer = csv.writer(response)

        # Write header
        writer.writerow([
            _('Date'),
            _('Fodder Type'),
            _('Category'),
            _('Quantity Consumed'),
            _('Unit'),
            _('Cost'),
            _('Consumed By'),
            _('Consumer Detail'),
            _('Notes')
        ])

        # Get consumption data
        queryset = FeedConsumption.objects.select_related('fodder_type').order_by('-date')

        # Apply date filters
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        # Write data rows
        for item in queryset:
            # Determine consumer detail
            if item.consumed_by == 'INDIVIDUAL' and hasattr(item, 'specific_buffalo') and item.specific_buffalo:
                consumer_detail = str(item.specific_buffalo)
            elif item.consumed_by == 'GROUP' and item.group_name:
                consumer_detail = item.group_name
            else:
                consumer_detail = ''

            writer.writerow([
                item.date.strftime('%Y-%m-%d'),
                item.fodder_type.name,
                item.fodder_type.get_category_display(),
                item.quantity_consumed,
                item.fodder_type.unit,
                item.cost_at_consumption or '',
                item.get_consumed_by_display(),
                consumer_detail,
                item.notes or ''
            ])

        return response


# API Views for AJAX

class FodderTypeAutocompleteView(LoginRequiredMixin, View):
    """API view for fodder type autocomplete"""

    def get(self, request):
        search_term = request.GET.get('term', '')
        fodder_types = FodderType.objects.filter(name__icontains=search_term)[:10]

        results = []
        for fodder_type in fodder_types:
            results.append({
                'id': fodder_type.id,
                'text': fodder_type.name,
                'category': fodder_type.get_category_display(),
                'unit': fodder_type.unit,
                'cost': float(fodder_type.current_cost_per_unit)
            })

        return JsonResponse({'results': results})


class GetInventoryLevelView(LoginRequiredMixin, View):
    """API view for getting current inventory level for a fodder type"""

    def get(self, request, fodder_id):
        try:
            fodder_type = FodderType.objects.get(pk=fodder_id)

            try:
                inventory = FeedInventory.objects.get(fodder_type=fodder_type)
                data = {
                    'available': float(inventory.quantity_on_hand),
                    'unit': fodder_type.unit,
                    'below_min': fodder_type.is_below_min_stock(),
                    'min_level': float(fodder_type.min_stock_level)
                }
            except FeedInventory.DoesNotExist:
                data = {
                    'available': 0,
                    'unit': fodder_type.unit,
                    'below_min': True,
                    'min_level': float(fodder_type.min_stock_level)
                }

            return JsonResponse(data)

        except FodderType.DoesNotExist:
            return JsonResponse({'error': 'Fodder type not found'}, status=404)


class GetAnimalCountView(LoginRequiredMixin, View):
    """API view for getting animal count by group"""

    def get(self, request, group):
        if not BUFFALO_MODEL_EXISTS:
            return JsonResponse({'count': 0})

        if group == 'ALL':
            count = Buffalo.objects.filter(is_active=True).count()
        elif group == 'MILKING':
            count = Buffalo.objects.filter(is_active=True, status='Active-Milking').count()
        elif group == 'DRY':
            count = Buffalo.objects.filter(is_active=True, status='Active-Dry').count()
        elif group == 'PREGNANT':
            count = Buffalo.objects.filter(is_active=True, status='Active-Pregnant').count()
        elif group == 'CALVES':
            count = Buffalo.objects.filter(is_active=True, status__in=['Calf', 'Heifer']).count()
        else:
            count = 0

        return JsonResponse({'count': count})