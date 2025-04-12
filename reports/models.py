from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid


class Report(models.Model):
    """Model for storing generated reports."""
    REPORT_FARM_SUMMARY = 'FARM_SUMMARY'
    REPORT_HERD = 'HERD'
    REPORT_MILK_PRODUCTION = 'MILK_PRODUCTION'
    REPORT_FINANCIAL = 'FINANCIAL'
    REPORT_EXPENSE = 'EXPENSE'
    REPORT_ASSET = 'ASSET'
    REPORT_LOAN = 'LOAN'
    REPORT_BUFFALO_PROFILE = 'BUFFALO_PROFILE'

    REPORT_TYPE_CHOICES = [
        (REPORT_FARM_SUMMARY, _('Farm Summary')),
        (REPORT_HERD, _('Herd Report')),
        (REPORT_MILK_PRODUCTION, _('Milk Production')),
        (REPORT_FINANCIAL, _('Financial Statement')),
        (REPORT_EXPENSE, _('Expense Report')),
        (REPORT_ASSET, _('Asset Report')),
        (REPORT_LOAN, _('Loan Summary')),
        (REPORT_BUFFALO_PROFILE, _('Buffalo Profile')),
    ]

    FORMAT_PDF = 'PDF'
    FORMAT_HTML = 'HTML'
    FORMAT_CSV = 'CSV'
    FORMAT_EXCEL = 'EXCEL'

    FORMAT_CHOICES = [
        (FORMAT_PDF, _('PDF')),
        (FORMAT_HTML, _('HTML')),
        (FORMAT_CSV, _('CSV')),
        (FORMAT_EXCEL, _('Excel')),
    ]

    report_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_type = models.CharField(_('Report Type'), max_length=20, choices=REPORT_TYPE_CHOICES)
    title = models.CharField(_('Title'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    parameters = models.JSONField(_('Parameters'), default=dict, blank=True,
                                  help_text=_('JSON of parameters used to generate the report'))
    format = models.CharField(_('Format'), max_length=5, choices=FORMAT_CHOICES)
    file_path = models.FileField(_('File Path'), upload_to='reports/', null=True, blank=True)
    date_range_start = models.DateField(_('Date Range Start'), null=True, blank=True)
    date_range_end = models.DateField(_('Date Range End'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(_('Created By'), max_length=100, blank=True)
    is_scheduled = models.BooleanField(_('Is Scheduled'), default=False)

    def __str__(self):
        return f"{self.title} ({self.get_report_type_display()}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = _('Report')
        verbose_name_plural = _('Reports')
        ordering = ['-created_at']


class ReportEmail(models.Model):
    """Model for tracking report email deliveries."""
    email_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='emails')
    recipients = models.TextField(_('Recipients'))
    subject = models.CharField(_('Subject'), max_length=200)
    body = models.TextField(_('Body'))
    sent_at = models.DateTimeField(_('Sent At'), auto_now_add=True)
    status = models.CharField(_('Status'), max_length=50, default='SENT')
    error_message = models.TextField(_('Error Message'), blank=True)

    def __str__(self):
        return f"Email for {self.report} - {self.sent_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = _('Report Email')
        verbose_name_plural = _('Report Emails')
        ordering = ['-sent_at']


class ProfitabilityReport(models.Model):
    """Model for storing calculated profitability metrics for reports."""
    report_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.CharField(_('Period'), max_length=20, help_text=_('e.g., "2023-01", "2023-Q1", "2023"'))
    total_income = models.DecimalField(_('Total Income'), max_digits=12, decimal_places=2)
    direct_costs = models.DecimalField(_('Direct Costs'), max_digits=12, decimal_places=2)
    gross_profit = models.DecimalField(_('Gross Profit'), max_digits=12, decimal_places=2)
    indirect_costs = models.DecimalField(_('Indirect Costs'), max_digits=12, decimal_places=2)
    net_profit = models.DecimalField(_('Net Profit'), max_digits=12, decimal_places=2)
    total_investment = models.DecimalField(_('Total Investment'), max_digits=12, decimal_places=2)
    roi_percentage = models.DecimalField(_('ROI (%)'), max_digits=8, decimal_places=2)
    depreciation = models.DecimalField(_('Depreciation'), max_digits=12, decimal_places=2)
    loan_principal_repayment = models.DecimalField(_('Loan Principal Repayment'), max_digits=12, decimal_places=2)
    capital_expenditures = models.DecimalField(_('Capital Expenditures'), max_digits=12, decimal_places=2)
    cash_surplus = models.DecimalField(_('Cash Surplus'), max_digits=12, decimal_places=2)
    cost_breakdowns = models.JSONField(_('Cost Breakdowns'), default=dict, blank=True,
                                       help_text=_('JSON of cost category breakdowns'))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profitability Report - {self.period}"

    class Meta:
        verbose_name = _('Profitability Report')
        verbose_name_plural = _('Profitability Reports')
        ordering = ['-period']
        unique_together = ['period']