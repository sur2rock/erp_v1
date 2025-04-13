"""
finance/views.py

This file contains view functions and API viewsets for the finance module.
Each view includes detailed comments explaining data aggregation, filtering,
and business logic applied.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Sum, Count
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
import csv, io, json
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from .models import ExpenseCategory, IncomeCategory, ExpenseRecord, IncomeRecord, Profitability
from .forms import ExpenseCategoryForm, IncomeCategoryForm, ExpenseRecordForm, IncomeRecordForm, MilkIncomeGeneratorForm
from .serializers import ExpenseCategorySerializer, IncomeCategorySerializer, ExpenseRecordSerializer, \
    IncomeRecordSerializer, ProfitabilitySerializer
from herd.models import MilkProduction
from configuration.models import GlobalSettings


# ---------------- Expense Category Views ----------------
@login_required
def expense_category_list(request):
    """
    Displays a list of all Expense Categories.
    Also calculates the count and total expense for each category.
    """
    categories = ExpenseCategory.objects.all()
    for category in categories:
        category.expense_count = ExpenseRecord.objects.filter(category=category).count()
        category.expense_total = ExpenseRecord.objects.filter(category=category).aggregate(total=Sum('amount'))[
                                     'total'] or 0
    context = {'title': 'Expense Categories', 'categories': categories}
    return render(request, 'dairy_erp/finance/expense_category_list.html', context)


@login_required
def expense_category_add(request):
    """
    View to add a new Expense Category.
    On POST, validates the form and saves the new category.
    """
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Expense category {category.name} has been added successfully!')
            return redirect('finance:expense_category_list')
    else:
        form = ExpenseCategoryForm()
    context = {'title': 'Add Expense Category', 'form': form}
    return render(request, 'dairy_erp/finance/expense_category_form.html', context)


@login_required
def expense_category_edit(request, category_id):
    """
    View to edit an existing Expense Category.
    Loads the instance using get_object_or_404 and updates on submission.
    """
    category = get_object_or_404(ExpenseCategory, id=category_id)
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Expense category {category.name} has been updated successfully!')
            return redirect('finance:expense_category_list')
    else:
        form = ExpenseCategoryForm(instance=category)
    context = {'title': 'Edit Expense Category', 'form': form, 'category': category}
    return render(request, 'dairy_erp/finance/expense_category_form.html', context)


# ---------------- Income Category Views ----------------
@login_required
def income_category_list(request):
    """
    Displays all Income Categories and aggregates the number and total income for each.
    """
    categories = IncomeCategory.objects.all()
    for category in categories:
        category.income_count = IncomeRecord.objects.filter(category=category).count()
        category.income_total = IncomeRecord.objects.filter(category=category).aggregate(total=Sum('total_amount'))[
                                    'total'] or 0
    context = {'title': 'Income Categories', 'categories': categories}
    return render(request, 'dairy_erp/finance/income_category_list.html', context)


@login_required
def income_category_add(request):
    """
    View to add a new Income Category.
    """
    if request.method == 'POST':
        form = IncomeCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Income category {category.name} has been added successfully!')
            return redirect('finance:income_category_list')
    else:
        form = IncomeCategoryForm()
    context = {'title': 'Add Income Category', 'form': form}
    return render(request, 'dairy_erp/finance/income_category_form.html', context)


@login_required
def income_category_edit(request, category_id):
    """
    View to edit an existing Income Category.
    """
    category = get_object_or_404(IncomeCategory, id=category_id)
    if request.method == 'POST':
        form = IncomeCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Income category {category.name} has been updated successfully!')
            return redirect('finance:income_category_list')
    else:
        form = IncomeCategoryForm(instance=category)
    context = {'title': 'Edit Income Category', 'form': form, 'category': category}
    return render(request, 'dairy_erp/finance/income_category_form.html', context)


# ---------------- Expense Record Views ----------------
@login_required
def expense_list(request):
    """
    Lists expense records with optional filtering by date range and category.
    Also prepares data for the expense breakdown chart.
    """
    today = timezone.now().date()
    default_start = (today - timedelta(days=30)).isoformat()
    start_date = request.GET.get('start_date', default_start)
    end_date = request.GET.get('end_date', today.isoformat())
    category_id = request.GET.get('category_id', '')

    expenses = ExpenseRecord.objects.all()
    if start_date:
        expenses = expenses.filter(date__gte=start_date)
    if end_date:
        expenses = expenses.filter(date__lte=end_date)
    if category_id:
        expenses = expenses.filter(category_id=category_id)
    categories = ExpenseCategory.objects.all()
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0

    # Prepare chart data by aggregating expenses by category.
    expense_breakdown = expenses.values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')
    chart_labels = [entry['category__name'] for entry in expense_breakdown]
    chart_values = [float(entry['total']) for entry in expense_breakdown]

    context = {
        'title': 'Expenses',
        'expenses': expenses,
        'categories': categories,
        'start_date': start_date,
        'end_date': end_date,
        'category_id': category_id,
        'total_expenses': total_expenses,
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
    }
    return render(request, 'dairy_erp/finance/expense_list.html', context)


@login_required
def expense_add(request):
    """
    View to add a new Expense Record.
    On GET, displays a form pre-filled with current date.
    """
    if request.method == 'POST':
        form = ExpenseRecordForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense record has been added successfully!')
            return redirect('finance:expense_list')
    else:
        form = ExpenseRecordForm(initial={'date': timezone.now().date()})
    context = {'title': 'Add Expense', 'form': form}
    return render(request, 'dairy_erp/finance/expense_form.html', context)


@login_required
def expense_edit(request, expense_id):
    """
    View to edit an existing Expense Record.
    """
    expense = get_object_or_404(ExpenseRecord, id=expense_id)
    if request.method == 'POST':
        form = ExpenseRecordForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense record has been updated successfully!')
            return redirect('finance:expense_list')
    else:
        form = ExpenseRecordForm(instance=expense)
    context = {'title': 'Edit Expense', 'form': form, 'expense': expense}
    return render(request, 'dairy_erp/finance/expense_form.html', context)


@login_required
def expense_delete(request, expense_id):
    """
    View to confirm and delete an Expense Record.
    """
    expense = get_object_or_404(ExpenseRecord, id=expense_id)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense record has been deleted successfully!')
        return redirect('finance:expense_list')
    context = {'title': 'Delete Expense', 'expense': expense}
    return render(request, 'dairy_erp/finance/expense_delete.html', context)


@login_required
def export_expenses(request):
    """
    Exports filtered expense records to a CSV file.
    """
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    category_id = request.GET.get('category_id', '')

    expenses = ExpenseRecord.objects.all()
    if start_date:
        expenses = expenses.filter(date__gte=start_date)
    if end_date:
        expenses = expenses.filter(date__lte=end_date)
    if category_id:
        expenses = expenses.filter(category_id=category_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Date', 'Category', 'Description', 'Amount', 'Supplier/Vendor', 'Related Buffalo', 'Notes'])
    for expense in expenses:
        writer.writerow([
            expense.date,
            expense.category.name,
            expense.description,
            expense.amount,
            expense.supplier_vendor or '',
            str(expense.related_buffalo) if expense.related_buffalo else '',
            expense.notes or ''
        ])
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="expenses_export_{timezone.now().strftime("%Y_%m_%d")}.csv"'
    return response


# ---------------- Income Record Views ----------------
@login_required
def income_list(request):
    """
    Lists income records with optional filtering by date range and category.
    Also aggregates the total income and prepares chart data.
    """
    today = timezone.now().date()
    default_start = (today - timedelta(days=30)).isoformat()
    start_date = request.GET.get('start_date', default_start)
    end_date = request.GET.get('end_date', today.isoformat())
    category_id = request.GET.get('category_id', '')

    income_records = IncomeRecord.objects.all()
    if start_date:
        income_records = income_records.filter(date__gte=start_date)
    if end_date:
        income_records = income_records.filter(date__lte=end_date)
    if category_id:
        income_records = income_records.filter(category_id=category_id)
    categories = IncomeCategory.objects.all()
    total_income = income_records.aggregate(total=Sum('total_amount'))['total'] or 0

    # Chart data aggregation: group income by category.
    income_breakdown = income_records.values('category__name').annotate(total=Sum('total_amount')).order_by('-total')
    chart_labels = [entry['category__name'] for entry in income_breakdown]
    chart_values = [float(entry['total']) for entry in income_breakdown]

    context = {
        'title': 'Income',
        'income_records': income_records,
        'categories': categories,
        'start_date': start_date,
        'end_date': end_date,
        'category_id': category_id,
        'total_income': total_income,
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
    }
    return render(request, 'dairy_erp/finance/income_list.html', context)


@login_required
def income_add(request):
    """
    View to add a new Income Record.
    Uses the IncomeRecordForm and sets the default date.
    """
    if request.method == 'POST':
        form = IncomeRecordForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Income record has been added successfully!')
            return redirect('finance:income_list')
    else:
        form = IncomeRecordForm(initial={'date': timezone.now().date()})
    context = {'title': 'Add Income', 'form': form}
    return render(request, 'dairy_erp/finance/income_form.html', context)


@login_required
def income_edit(request, income_id):
    """
    View to edit an existing Income Record.
    """
    income = get_object_or_404(IncomeRecord, id=income_id)
    if request.method == 'POST':
        form = IncomeRecordForm(request.POST, instance=income)
        if form.is_valid():
            form.save()
            messages.success(request, 'Income record has been updated successfully!')
            return redirect('finance:income_list')
    else:
        form = IncomeRecordForm(instance=income)
    context = {'title': 'Edit Income', 'form': form, 'income': income}
    return render(request, 'dairy_erp/finance/income_form.html', context)


@login_required
def income_delete(request, income_id):
    """
    View to delete an Income Record after confirmation.
    """
    income = get_object_or_404(IncomeRecord, id=income_id)
    if request.method == 'POST':
        income.delete()
        messages.success(request, 'Income record has been deleted successfully!')
        return redirect('finance:income_list')
    context = {'title': 'Delete Income', 'income': income}
    return render(request, 'dairy_erp/finance/income_delete.html', context)


@login_required
def export_income(request):
    """
    Exports the filtered income records as a CSV file.
    """
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    category_id = request.GET.get('category_id', '')

    income_records = IncomeRecord.objects.all()
    if start_date:
        income_records = income_records.filter(date__gte=start_date)
    if end_date:
        income_records = income_records.filter(date__lte=end_date)
    if category_id:
        income_records = income_records.filter(category_id=category_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ['Date', 'Category', 'Description', 'Quantity', 'Unit Price', 'Total Amount', 'Customer', 'Related Buffalo',
         'Notes'])
    for income in income_records:
        writer.writerow([
            income.date,
            income.category.name,
            income.description,
            income.quantity or '',
            income.unit_price or '',
            income.total_amount,
            income.customer or '',
            str(income.related_buffalo) if income.related_buffalo else '',
            income.notes or ''
        ])
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="income_export_{timezone.now().strftime("%Y_%m_%d")}.csv"'
    return response


@login_required
def milk_income_generator(request):
    """
    View to generate income records automatically based on milk production data.
    It groups milk production records by date and creates a corresponding income record
    if one doesn't already exist for that date.
    """
    if request.method == 'POST':
        form = MilkIncomeGeneratorForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            milk_price = form.cleaned_data['milk_price']
            customer = form.cleaned_data['customer']

            # Retrieve milk production data between the provided dates.
            milk_production = MilkProduction.objects.filter(date__gte=start_date, date__lte=end_date)
            milk_by_date = {}
            for record in milk_production:
                date_key = record.date
                # Accumulate milk production using Decimal for precision.
                milk_by_date[date_key] = milk_by_date.get(date_key, Decimal('0.00')) + record.quantity_litres

            records_created = 0
            # For each date, create an income record if one for "Milk Sales" does not exist.
            for record_date, quantity in milk_by_date.items():
                existing = IncomeRecord.objects.filter(
                    date=record_date,
                    category__name='Milk Sales'
                ).exists()
                if not existing:
                    milk_category, created = IncomeCategory.objects.get_or_create(
                        name='Milk Sales',
                        defaults={'description': 'Income from selling milk'}
                    )
                    IncomeRecord.objects.create(
                        date=record_date,
                        category=milk_category,
                        description=f'Milk sales for {record_date.strftime("%Y-%m-%d")}',
                        quantity=quantity,
                        unit_price=milk_price,
                        total_amount=quantity * milk_price,
                        customer=customer,
                        notes='Auto-generated from milk production records'
                    )
                    records_created += 1
            messages.success(request, f'{records_created} income records have been generated!')
            return redirect('finance:income_list')
    else:
        # Set default date range to the last 7 days.
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)
        form = MilkIncomeGeneratorForm(initial={'start_date': start_date, 'end_date': end_date})
    context = {'title': 'Generate Milk Income', 'form': form}
    return render(request, 'dairy_erp/finance/milk_income_generator.html', context)


@login_required
def profitability(request):
    """
    Displays profitability summaries.
    If no records exist for the last 12 months, calculates them on-the-fly.
    Aggregates data for charts showing trends in income, expenses, and profits.
    """
    today = timezone.now().date()
    # Display last 12 months starting from 11 months ago.
    start_date = today - relativedelta(months=11)
    profitability_records = Profitability.objects.filter(year__gte=start_date.year).order_by('year', 'month')

    # If no profitability records exist, calculate and create them.
    if not profitability_records.exists():
        current_date = start_date
        while current_date <= today:
            year = current_date.year
            month = current_date.month
            income = \
            IncomeRecord.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('total_amount'))[
                'total'] or Decimal('0.00')
            direct_expenses = ExpenseRecord.objects.filter(
                date__year=year, date__month=month, category__is_direct_cost=True
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            indirect_expenses = ExpenseRecord.objects.filter(
                date__year=year, date__month=month, category__is_direct_cost=False
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            gross_profit = income - direct_expenses
            net_profit = gross_profit - indirect_expenses
            Profitability.objects.create(
                year=year,
                month=month,
                total_income=income,
                direct_costs=direct_expenses,
                indirect_costs=indirect_expenses,
                gross_profit=gross_profit,
                net_profit=net_profit,
                roi=0,
                cash_surplus=0
            )
            current_date += relativedelta(months=1)
        profitability_records = Profitability.objects.filter(year__gte=start_date.year).order_by('year', 'month')

    # Prepare chart data for display on the dashboard.
    months = []
    income_data = []
    direct_costs_data = []
    indirect_costs_data = []
    gross_profit_data = []
    net_profit_data = []
    for record in profitability_records:
        month_label = f"{record.year}-{record.month:02d}"
        months.append(month_label)
        income_data.append(float(record.total_income))
        direct_costs_data.append(float(record.direct_costs))
        indirect_costs_data.append(float(record.indirect_costs))
        gross_profit_data.append(float(record.gross_profit))
        net_profit_data.append(float(record.net_profit))

    overall_income = sum(income_data)
    overall_direct_costs = sum(direct_costs_data)
    overall_indirect_costs = sum(indirect_costs_data)
    overall_gross_profit = sum(gross_profit_data)
    overall_net_profit = sum(net_profit_data)

    context = {
        'title': 'Profitability',
        'profitability_records': profitability_records,
        'months': json.dumps(months),
        'income_data': json.dumps(income_data),
        'direct_costs_data': json.dumps(direct_costs_data),
        'indirect_costs_data': json.dumps(indirect_costs_data),
        'gross_profit_data': json.dumps(gross_profit_data),
        'net_profit_data': json.dumps(net_profit_data),
        'overall_income': overall_income,
        'overall_direct_costs': overall_direct_costs,
        'overall_indirect_costs': overall_indirect_costs,
        'overall_gross_profit': overall_gross_profit,
        'overall_net_profit': overall_net_profit,
    }
    return render(request, 'dairy_erp/finance/profitability.html', context)


@login_required
@require_POST
def calculate_profitability(request):
    """
    Manually triggers the recalculation of profitability for a specific month.
    Expects 'year' and 'month' in POST data and updates/creates a Profitability record.
    """
    year = int(request.POST.get('year'))
    month = int(request.POST.get('month'))
    income = IncomeRecord.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('total_amount'))[
                 'total'] or Decimal('0.00')
    direct_expenses = ExpenseRecord.objects.filter(
        date__year=year, date__month=month, category__is_direct_cost=True
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    indirect_expenses = ExpenseRecord.objects.filter(
        date__year=year, date__month=month, category__is_direct_cost=False
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    gross_profit = income - direct_expenses
    net_profit = gross_profit - indirect_expenses
    Profitability.objects.update_or_create(
        year=year,
        month=month,
        defaults={
            'total_income': income,
            'direct_costs': direct_expenses,
            'indirect_costs': indirect_expenses,
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'roi': 0,
            'cash_surplus': 0
        }
    )
    messages.success(request, f'Profitability has been calculated for {year}-{month:02d}!')
    return redirect('finance:profitability')


# --------------- REST API ViewSets ---------------
class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for ExpenseCategory.
    Allows search by name.
    """
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class IncomeCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for IncomeCategory.
    """
    queryset = IncomeCategory.objects.all()
    serializer_class = IncomeCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class ExpenseRecordViewSet(viewsets.ModelViewSet):
    """
    API endpoint for ExpenseRecord.
    Provides filtering by category, date, or related buffalo.
    """
    queryset = ExpenseRecord.objects.all()
    serializer_class = ExpenseRecordSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['category', 'date', 'related_buffalo']
    ordering_fields = ['date', 'amount']


class IncomeRecordViewSet(viewsets.ModelViewSet):
    """
    API endpoint for IncomeRecord.
    Allows filtering by category, date, or related buffalo.
    """
    queryset = IncomeRecord.objects.all()
    serializer_class = IncomeRecordSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['category', 'date', 'related_buffalo']
    ordering_fields = ['date', 'total_amount']


class ProfitabilityViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Profitability records.
    """
    queryset = Profitability.objects.all()
    serializer_class = ProfitabilitySerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['year', 'month']
    ordering_fields = ['year', 'month']


@login_required
def export_profitability(request):
    """
    Exports all profitability records to CSV.
    """
    records = Profitability.objects.all().order_by('-year', '-month')
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ['Year', 'Month', 'Total Income', 'Direct Costs', 'Indirect Costs', 'Gross Profit', 'Net Profit', 'ROI (%)',
         'Cash Surplus'])
    for r in records:
        writer.writerow([
            r.year, r.month, r.total_income, r.direct_costs, r.indirect_costs,
            r.gross_profit, r.net_profit, r.roi, r.cash_surplus
        ])
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="profitability_{date.today().isoformat()}.csv"'
    return response
