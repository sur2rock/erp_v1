"""
finance/models.py

This file contains the core database models for the finance module of the Dairy ERP system.
It includes models to record expenses, income, loans, loan payments, and profitability summaries.
Each model includes detailed inline comments explaining fields, formulas, dependencies, and business rules.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, F
from decimal import Decimal
from herd.models import Buffalo  # Buffalo model from the herd app

# ------------------- Expense Category -------------------
class ExpenseCategory(models.Model):
    """
    Model for expense categories.
    These categories will be used to differentiate direct and indirect costs.
    Direct costs are later used in the calculation of Gross Profit.
    """
    name = models.CharField(_('Name'), max_length=100, unique=True)
    is_direct_cost = models.BooleanField(
        _('Is Direct Cost'),
        default=True,
        help_text=_('Direct costs are used for Gross Profit calculation')
    )
    description = models.TextField(_('Description'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp when record was created
    updated_at = models.DateTimeField(auto_now=True)      # Timestamp when record was last updated

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Expense Category')
        verbose_name_plural = _('Expense Categories')
        ordering = ['name']


# ------------------- Expense Record -------------------
class ExpenseRecord(models.Model):
    """
    Model to track all farm expenses.
    Includes details on date, category, amount, related modules, and optionally links to a buffalo.
    The save method automatically updates the cumulative cost on the related buffalo.
    """
    expense_id = models.AutoField(primary_key=True)  # Explicit PK field for clarity
    date = models.DateField(_('Date'))
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name='expenses'
    )
    description = models.CharField(_('Description'), max_length=255)
    amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=2)
    # Field to indicate if this expense is linked to another module's record (e.g., FeedPurchase)
    related_module = models.CharField(
        _('Related Module'), max_length=50, blank=True,
        help_text=_('e.g., FeedPurchase, HealthRecord, UtilityBill')
    )
    # Optionally store the related record's primary key
    related_record_id = models.IntegerField(_('Related Record ID'), null=True, blank=True)
    # Optional link to a buffalo record if the expense is attributable to a specific animal
    related_buffalo = models.ForeignKey(
        Buffalo, null=True, blank=True, on_delete=models.SET_NULL, related_name='expenses'
    )
    supplier_vendor = models.CharField(_('Supplier/Vendor'), max_length=100, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.category}: {self.amount}"

    def save(self, *args, **kwargs):
        # Save the ExpenseRecord normally
        super().save(*args, **kwargs)
        # If this expense is related to a buffalo, recalculate the buffalo's cumulative cost
        if self.related_buffalo:
            total_cost = ExpenseRecord.objects.filter(
                related_buffalo=self.related_buffalo
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            self.related_buffalo.cumulative_cost = total_cost
            self.related_buffalo.save(update_fields=['cumulative_cost'])

    class Meta:
        verbose_name = _('Expense Record')
        verbose_name_plural = _('Expense Records')
        ordering = ['-date']


# ------------------- Income Category -------------------
class IncomeCategory(models.Model):
    """
    Model for income categories.
    For example, "Milk Sales", "Calf Sales", etc.
    """
    name = models.CharField(_('Name'), max_length=100, unique=True)
    description = models.TextField(_('Description'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Income Category')
        verbose_name_plural = _('Income Categories')
        ordering = ['name']


# ------------------- Income Record -------------------
class IncomeRecord(models.Model):
    """
    Model for tracking all farm income records.
    It includes optional fields such as quantity and unit price which can be used
    to auto-calculate the total amount if not manually provided.
    """
    income_id = models.AutoField(primary_key=True)
    date = models.DateField(_('Date'))
    category = models.ForeignKey(
        IncomeCategory, on_delete=models.PROTECT, related_name='income_records'
    )
    description = models.CharField(_('Description'), max_length=255)
    quantity = models.DecimalField(
        _('Quantity'), max_digits=10, decimal_places=2, null=True, blank=True
    )
    unit_price = models.DecimalField(
        _('Unit Price'), max_digits=10, decimal_places=2, null=True, blank=True
    )
    total_amount = models.DecimalField(_('Total Amount'), max_digits=12, decimal_places=2)
    # Optionally link an income record to a specific buffalo
    related_buffalo = models.ForeignKey(
        Buffalo, null=True, blank=True, on_delete=models.SET_NULL, related_name='income_records'
    )
    customer = models.CharField(_('Customer'), max_length=100, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.category}: {self.total_amount}"

    def save(self, *args, **kwargs):
        # If both quantity and unit_price are provided and total_amount is empty, calculate it.
        if self.quantity is not None and self.unit_price is not None and (self.total_amount is None or self.total_amount == 0):
            self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Income Record')
        verbose_name_plural = _('Income Records')
        ordering = ['-date']


# ------------------- Loan Model -------------------
class Loan(models.Model):
    """
    Model for tracking loan details.
    Includes principal, interest rate, tenure, and the EMI amount.
    """
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PAID = 'PAID_OFF'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, _('Active')),
        (STATUS_PAID, _('Paid Off')),
    ]

    loan_id = models.AutoField(primary_key=True)
    loan_name = models.CharField(_('Loan Name'), max_length=100)
    issuer = models.CharField(_('Bank/Lender Name'), max_length=100)
    principal_amount = models.DecimalField(_('Principal Amount'), max_digits=12, decimal_places=2)
    annual_interest_rate = models.DecimalField(_('Annual Interest Rate (%)'), max_digits=5, decimal_places=2)
    loan_start_date = models.DateField(_('Loan Start Date'))
    tenure_months = models.PositiveIntegerField(_('Tenure (Months)'))
    # The EMI amount can be auto-calculated if not provided manually.
    emi_amount = models.DecimalField(_('EMI Amount'), max_digits=12, decimal_places=2, blank=True, null=True)
    status = models.CharField(
        _('Status'), max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.loan_name} - {self.principal_amount} ({self.get_status_display()})"

    def calculate_emi(self):
        """
        Calculates the Equated Monthly Installment (EMI) using the formula:
        EMI = (P * r * (1+r)^n) / ((1+r)^n - 1)
        where:
            P = principal_amount,
            r = monthly interest rate (annual_interest_rate / 12 / 100),
            n = tenure_months.
        """
        p = self.principal_amount
        r = self.annual_interest_rate / Decimal(12 * 100)  # Convert to monthly decimal rate
        n = self.tenure_months
        try:
            emi = (p * r * (1 + r) ** n) / (((1 + r) ** n) - 1)
            return round(emi, 2)
        except (ZeroDivisionError, ValueError):
            return Decimal('0.00')

    def save(self, *args, **kwargs):
        # Auto-calculate EMI amount if not explicitly set.
        if not self.emi_amount or self.emi_amount == 0:
            self.emi_amount = self.calculate_emi()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Loan')
        verbose_name_plural = _('Loans')
        ordering = ['-loan_start_date']


# ------------------- Loan Payment -------------------
class LoanPayment(models.Model):
    """
    Model for tracking each loan payment.
    It includes calculated interest and principal components.
    If an interest expense record is not linked, it automatically creates one.
    """
    payment_id = models.AutoField(primary_key=True)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(_('Payment Date'))
    amount_paid = models.DecimalField(_('Amount Paid'), max_digits=12, decimal_places=2)
    principal_component = models.DecimalField(_('Principal Component'), max_digits=12, decimal_places=2)
    interest_component = models.DecimalField(_('Interest Component'), max_digits=12, decimal_places=2)
    outstanding_balance = models.DecimalField(_('Outstanding Balance'), max_digits=12, decimal_places=2)
    # Link to the automatically created expense record for the interest part
    related_interest_expense = models.ForeignKey(
        ExpenseRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name='loan_payment'
    )
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.loan.loan_name} - Payment on {self.payment_date}: {self.amount_paid}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # If there is no linked interest expense and interest_component > 0, create it.
        if not self.related_interest_expense and self.interest_component > 0:
            try:
                loan_interest_category, created = ExpenseCategory.objects.get_or_create(
                    name='Loan Interest',
                    defaults={'is_direct_cost': False, 'description': 'Interest payment for loans'}
                )
                expense = ExpenseRecord.objects.create(
                    date=self.payment_date,
                    category=loan_interest_category,
                    description=f"Interest payment for loan: {self.loan.loan_name}",
                    amount=self.interest_component,
                    related_module='LoanPayment',
                    related_record_id=self.payment_id,
                    notes=self.notes
                )
                # Link the newly created expense to this payment and update the record
                self.related_interest_expense = expense
                self.save(update_fields=['related_interest_expense'])
            except Exception as e:
                # In production, log the error appropriately
                pass
        # Update the loan's status if the outstanding balance is zero or negative.
        if self.outstanding_balance <= 0 and self.loan.status != Loan.STATUS_PAID:
            self.loan.status = Loan.STATUS_PAID
            self.loan.save(update_fields=['status'])

    class Meta:
        verbose_name = _('Loan Payment')
        verbose_name_plural = _('Loan Payments')
        ordering = ['-payment_date']


# ------------------- Profitability Summary -------------------
class Profitability(models.Model):
    """
    Model for storing monthly profitability data.
    The calculations (Gross Profit, Net Profit, ROI, Cash Surplus) are performed elsewhere and saved here.
    """
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    direct_costs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    indirect_costs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    # ROI calculated as (Net Profit / Total Investment) * 100. Total Investment should be defined elsewhere.
    roi = models.DecimalField(_('Return on Investment (%)'), max_digits=7, decimal_places=2, default=0)
    # Cash Surplus is calculated by adding back non-cash expenses and subtracting actual outflows like principal repayments.
    cash_surplus = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('year', 'month')
        verbose_name = _('Profitability Summary')
        verbose_name_plural = _('Profitability Summaries')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.month}/{self.year} Profitability"
