"""
finance/utils.py

Provides utility functions for finance calculations.
For example, calculate_monthly_profitability computes income, expenses, profits,
ROI, and cash surplus for a given month.
"""

from django.db.models import Sum
from .models import IncomeRecord, ExpenseRecord, Profitability
from assets.models import Asset  # Asset details to calculate total investment
from finance.models import LoanPayment
from datetime import date
from calendar import monthrange


def calculate_monthly_profitability(year, month):
    """
    Calculates the monthly profitability metrics.

    Steps:
    1. Define the start and end date of the month.
    2. Aggregate total income from IncomeRecord.
    3. Aggregate direct expenses (where ExpenseCategory.is_direct_cost is True).
    4. Aggregate indirect expenses.
    5. Compute Gross Profit = Total Income - Direct Costs.
    6. Compute Net Profit = Gross Profit - Indirect Costs.
    7. Retrieve depreciation expense (assumed to be recorded as an ExpenseRecord with category 'Depreciation').
    8. Retrieve principal repayment from LoanPayment (sum of principal components).
    9. Retrieve capital expenditure (from Asset purchase costs during the month).
    10. Compute ROI based on total investment.
    11. Compute Cash Surplus = Net Profit + Depreciation - Principal Repayment - CapEx.
    12. Update or create a Profitability record with these values.
    """
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    income = IncomeRecord.objects.filter(date__range=(start_date, end_date)).aggregate(total=Sum('total_amount'))[
                 'total'] or 0
    direct_costs = ExpenseRecord.objects.filter(
        date__range=(start_date, end_date), category__is_direct_cost=True
    ).aggregate(total=Sum('amount'))['total'] or 0
    indirect_costs = ExpenseRecord.objects.filter(
        date__range=(start_date, end_date), category__is_direct_cost=False
    ).aggregate(total=Sum('amount'))['total'] or 0

    gross_profit = income - direct_costs
    net_profit = gross_profit - indirect_costs

    # Depreciation is calculated as an expense under the 'Depreciation' category.
    depreciation = ExpenseRecord.objects.filter(
        date__range=(start_date, end_date), category__name='Depreciation'
    ).aggregate(total=Sum('amount'))['total'] or 0
    # Principal repayment from loans
    principal_repayment = LoanPayment.objects.filter(payment_date__range=(start_date, end_date)).aggregate(
        total=Sum('principal_component')
    )['total'] or 0
    # Capital Expenditure; assets purchased in the period.
    capex = Asset.objects.filter(purchase_date__range=(start_date, end_date)).aggregate(
        total=Sum('purchase_cost')
    )['total'] or 0

    total_investment = Asset.objects.aggregate(total=Sum('purchase_cost'))['total'] or 1  # Prevent division by zero
    roi = (net_profit / total_investment) * 100 if total_investment else 0

    cash_surplus = net_profit + depreciation - principal_repayment - capex

    # Update or create the Profitability record.
    record, _ = Profitability.objects.update_or_create(
        year=year,
        month=month,
        defaults={
            'total_income': income,
            'direct_costs': direct_costs,
            'indirect_costs': indirect_costs,
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'roi': roi,
            'cash_surplus': cash_surplus
        }
    )
    return record
