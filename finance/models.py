from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, F
from herd.models import Buffalo


class ExpenseCategory(models.Model):
    """Model for expense categories."""
    name = models.CharField(_('Name'), max_length=100, unique=True)
    is_direct_cost = models.BooleanField(_('Is Direct Cost'), default=True,
                                         help_text=_('Direct costs are used for Gross Profit calculation'))
    description = models.TextField(_('Description'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Expense Category')
        verbose_name_plural = _('Expense Categories')
        ordering = ['name']


class ExpenseRecord(models.Model):
    """Model for tracking all farm expenses."""
    expense_id = models.AutoField(primary_key=True)
    date = models.DateField(_('Date'))
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    description = models.CharField(_('Description'), max_length=255)
    amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=2)
    related_module = models.CharField(_('Related Module'), max_length=50, blank=True,
                                      help_text=_('e.g., FeedPurchase, HealthRecord, UtilityBill'))
    related_record_id = models.IntegerField(_('Related Record ID'), null=True, blank=True)
    related_buffalo = models.ForeignKey(Buffalo, null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name='expenses')
    supplier_vendor = models.CharField(_('Supplier/Vendor'), max_length=100, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.category}: {self.amount}"

    def save(self, *args, **kwargs):
        # Call the original save method
        super().save(*args, **kwargs)

        # Update Buffalo.cumulative_cost if related_buffalo is set
        if self.related_buffalo:
            # Get all expenses for this buffalo
            total_cost = ExpenseRecord.objects.filter(
                related_buffalo=self.related_buffalo
            ).aggregate(total=Sum('amount'))['total'] or 0

            # Update the buffalo's cumulative cost
            self.related_buffalo.cumulative_cost = total_cost
            self.related_buffalo.save(update_fields=['cumulative_cost'])

    class Meta:
        verbose_name = _('Expense Record')
        verbose_name_plural = _('Expense Records')
        ordering = ['-date']


class IncomeCategory(models.Model):
    """Model for income categories."""
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


class IncomeRecord(models.Model):
    """Model for tracking all farm income."""
    income_id = models.AutoField(primary_key=True)
    date = models.DateField(_('Date'))
    category = models.ForeignKey(IncomeCategory, on_delete=models.PROTECT, related_name='income_records')
    description = models.CharField(_('Description'), max_length=255)
    quantity = models.DecimalField(_('Quantity'), max_digits=10, decimal_places=2, null=True, blank=True)
    unit_price = models.DecimalField(_('Unit Price'), max_digits=10, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(_('Total Amount'), max_digits=12, decimal_places=2)
    related_buffalo = models.ForeignKey(Buffalo, null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name='income_records')
    customer = models.CharField(_('Customer'), max_length=100, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.category}: {self.total_amount}"

    def save(self, *args, **kwargs):
        # Auto-calculate total_amount if quantity and unit_price are provided
        if self.quantity and self.unit_price and not self.total_amount:
            self.total_amount = self.quantity * self.unit_price

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Income Record')
        verbose_name_plural = _('Income Records')
        ordering = ['-date']


# Loan Management Models
class Loan(models.Model):
    """Model for loan details and tracking."""
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
    emi_amount = models.DecimalField(_('EMI Amount'), max_digits=12, decimal_places=2)
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.loan_name} - {self.principal_amount} ({self.get_status_display()})"

    def calculate_emi(self):
        """Calculate EMI amount using the formula: EMI = [P × r × (1+r)^n] / [(1+r)^n - 1]"""
        p = self.principal_amount
        r = self.annual_interest_rate / 12 / 100  # Monthly interest rate
        n = self.tenure_months

        # Calculate EMI
        try:
            emi = (p * r * (1 + r) ** n) / ((1 + r) ** n - 1)
            return round(emi, 2)
        except (ZeroDivisionError, ValueError):
            return 0

    def save(self, *args, **kwargs):
        # Calculate EMI if not already set
        if not self.emi_amount:
            self.emi_amount = self.calculate_emi()

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Loan')
        verbose_name_plural = _('Loans')
        ordering = ['-loan_start_date']


class LoanPayment(models.Model):
    """Model for tracking loan EMI payments."""
    payment_id = models.AutoField(primary_key=True)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(_('Payment Date'))
    amount_paid = models.DecimalField(_('Amount Paid'), max_digits=12, decimal_places=2)
    principal_component = models.DecimalField(_('Principal Component'), max_digits=12, decimal_places=2)
    interest_component = models.DecimalField(_('Interest Component'), max_digits=12, decimal_places=2)
    outstanding_balance = models.DecimalField(_('Outstanding Balance'), max_digits=12, decimal_places=2)
    related_interest_expense = models.ForeignKey(ExpenseRecord, null=True, blank=True,
                                                 on_delete=models.SET_NULL, related_name='loan_payment')
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.loan} - Payment on {self.payment_date}: {self.amount_paid}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Create expense record for interest component if not exists
        if not self.related_interest_expense and self.interest_component > 0:
            try:
                loan_interest_category, _ = ExpenseCategory.objects.get_or_create(
                    name='Loan Interest',
                    defaults={'is_direct_cost': False}
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

                self.related_interest_expense = expense
                self.save(update_fields=['related_interest_expense'])
            except Exception as e:
                # Log error or handle exception
                pass

        # Check if loan is paid off
        if self.outstanding_balance <= 0 and self.loan.status != Loan.STATUS_PAID:
            self.loan.status = Loan.STATUS_PAID
            self.loan.save(update_fields=['status'])

    class Meta:
        verbose_name = _('Loan Payment')
        verbose_name_plural = _('Loan Payments')
        ordering = ['-payment_date']