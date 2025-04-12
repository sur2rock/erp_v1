from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class GlobalSettings(models.Model):
    """Model for global farm settings and configuration."""
    FEED_STRATEGY_BUY_ALL = 'BUY_ALL'
    FEED_STRATEGY_IN_HOUSE = 'IN_HOUSE_PRIORITY'

    FEED_STRATEGY_CHOICES = [
        (FEED_STRATEGY_BUY_ALL, _('Buy All')),
        (FEED_STRATEGY_IN_HOUSE, _('In-House Priority')),
    ]

    DEPRECIATION_SLM = 'SLM'
    DEPRECIATION_WDV = 'WDV'

    DEPRECIATION_METHOD_CHOICES = [
        (DEPRECIATION_SLM, _('Straight Line Method')),
        (DEPRECIATION_WDV, _('Written Down Value Method')),
    ]

    # General settings
    farm_name = models.CharField(_('Farm Name'), max_length=100)
    start_date = models.DateField(_('Start Date'))
    currency_symbol = models.CharField(_('Currency Symbol'), max_length=5, default='$')

    # Financial defaults
    default_milk_price_per_litre = models.DecimalField(_('Default Milk Price (per litre)'),
                                                       max_digits=10, decimal_places=2)
    default_inflation_rate_yearly = models.DecimalField(_('Default Inflation Rate (% yearly)'),
                                                        max_digits=5, decimal_places=2, default=3.0)
    default_tax_rate_yearly = models.DecimalField(_('Default Tax Rate (% yearly)'),
                                                  max_digits=5, decimal_places=2, default=20.0)
    default_loan_interest_rate_yearly = models.DecimalField(_('Default Loan Interest Rate (% yearly)'),
                                                            max_digits=5, decimal_places=2, default=10.0)
    default_depreciation_method = models.CharField(_('Default Depreciation Method'),
                                                   max_length=3, choices=DEPRECIATION_METHOD_CHOICES,
                                                   default=DEPRECIATION_SLM)

    # Operational defaults
    default_lactation_period_days = models.PositiveIntegerField(_('Default Lactation Period (days)'), default=305)
    default_dry_period_days = models.PositiveIntegerField(_('Default Dry Period (days)'), default=60)
    default_pregnancy_duration_days = models.PositiveIntegerField(_('Default Pregnancy Duration (days)'), default=280)

    # Feed strategy
    feed_strategy_toggle = models.CharField(_('Feed Strategy'), max_length=20,
                                            choices=FEED_STRATEGY_CHOICES, default=FEED_STRATEGY_BUY_ALL)

    # Alert thresholds
    reinvestment_surplus_threshold = models.DecimalField(_('Reinvestment Surplus Threshold'),
                                                         max_digits=12, decimal_places=2, default=10000)
    alert_vet_visit_overdue_days = models.PositiveIntegerField(_('Vet Visit Overdue Alert (days)'), default=7)
    alert_low_feed_inventory_threshold_kg = models.DecimalField(_('Low Feed Inventory Alert Threshold (kg)'),
                                                                max_digits=10, decimal_places=2, default=100)

    # Contact information
    contact_email = models.EmailField(_('Contact Email'), blank=True)
    contact_phone = models.CharField(_('Contact Phone'), max_length=20, blank=True)
    farm_address = models.TextField(_('Farm Address'), blank=True)

    # System settings
    enable_email_alerts = models.BooleanField(_('Enable Email Alerts'), default=False)

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Ensure only one instance exists
        if not self.pk and GlobalSettings.objects.exists():
            raise ValidationError(_('Only one global settings instance is allowed.'))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Global Settings: {self.farm_name}"

    class Meta:
        verbose_name = _('Global Settings')
        verbose_name_plural = _('Global Settings')


class CustomFieldDefinition(models.Model):
    """Model for defining custom fields for various modules."""
    TYPE_TEXT = 'TEXT'
    TYPE_NUMBER = 'NUMBER'
    TYPE_DATE = 'DATE'
    TYPE_BOOLEAN = 'BOOLEAN'

    FIELD_TYPE_CHOICES = [
        (TYPE_TEXT, _('Text')),
        (TYPE_NUMBER, _('Number')),
        (TYPE_DATE, _('Date')),
        (TYPE_BOOLEAN, _('Boolean')),
    ]

    TARGET_BUFFALO = 'Buffalo'
    TARGET_EXPENSE = 'ExpenseRecord'
    TARGET_INCOME = 'IncomeRecord'
    TARGET_EMPLOYEE = 'Employee'

    TARGET_MODEL_CHOICES = [
        (TARGET_BUFFALO, _('Buffalo')),
        (TARGET_EXPENSE, _('Expense Record')),
        (TARGET_INCOME, _('Income Record')),
        (TARGET_EMPLOYEE, _('Employee')),
    ]

    field_id = models.AutoField(primary_key=True)
    target_model = models.CharField(_('Target Model'), max_length=50, choices=TARGET_MODEL_CHOICES)
    field_name = models.CharField(_('Field Name'), max_length=50)
    field_label = models.CharField(_('Field Label'), max_length=100)
    field_type = models.CharField(_('Field Type'), max_length=10, choices=FIELD_TYPE_CHOICES)
    is_required = models.BooleanField(_('Required'), default=False)
    default_value = models.CharField(_('Default Value'), max_length=255, blank=True)
    help_text = models.CharField(_('Help Text'), max_length=255, blank=True)
    validation_regex = models.CharField(_('Validation Regex'), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.target_model}: {self.field_label} ({self.get_field_type_display()})"

    class Meta:
        verbose_name = _('Custom Field Definition')
        verbose_name_plural = _('Custom Field Definitions')
        ordering = ['target_model', 'field_label']
        # Ensure field names are unique per target model
        unique_together = ['target_model', 'field_name']


class Alert(models.Model):
    """Model for system alerts and notifications."""
    PRIORITY_LOW = 'LOW'
    PRIORITY_MEDIUM = 'MEDIUM'
    PRIORITY_HIGH = 'HIGH'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, _('Low')),
        (PRIORITY_MEDIUM, _('Medium')),
        (PRIORITY_HIGH, _('High')),
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_ACKNOWLEDGED = 'ACKNOWLEDGED'
    STATUS_RESOLVED = 'RESOLVED'
    STATUS_DISMISSED = 'DISMISSED'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, _('Active')),
        (STATUS_ACKNOWLEDGED, _('Acknowledged')),
        (STATUS_RESOLVED, _('Resolved')),
        (STATUS_DISMISSED, _('Dismissed')),
    ]

    alert_id = models.AutoField(primary_key=True)
    date_created = models.DateTimeField(_('Date Created'), auto_now_add=True)
    title = models.CharField(_('Title'), max_length=100)
    message = models.TextField(_('Message'))
    priority = models.CharField(_('Priority'), max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status = models.CharField(_('Status'), max_length=15, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    related_module = models.CharField(_('Related Module'), max_length=50, blank=True)
    related_record_id = models.IntegerField(_('Related Record ID'), null=True, blank=True)
    acknowledged_at = models.DateTimeField(_('Acknowledged At'), null=True, blank=True)
    resolved_at = models.DateTimeField(_('Resolved At'), null=True, blank=True)
    notes = models.TextField(_('Notes'), blank=True)

    def __str__(self):
        return f"{self.title} ({self.get_priority_display()}) - {self.get_status_display()}"

    class Meta:
        verbose_name = _('Alert')
        verbose_name_plural = _('Alerts')
        ordering = ['-date_created', '-priority']


class ReportSchedule(models.Model):
    """Model for scheduling automated reports."""
    REPORT_FARM_SUMMARY = 'FARM_SUMMARY'
    REPORT_HERD = 'HERD'
    REPORT_MILK_PRODUCTION = 'MILK_PRODUCTION'
    REPORT_FINANCIAL = 'FINANCIAL'
    REPORT_EXPENSE = 'EXPENSE'
    REPORT_ASSET = 'ASSET'
    REPORT_LOAN = 'LOAN'

    REPORT_TYPE_CHOICES = [
        (REPORT_FARM_SUMMARY, _('Farm Summary')),
        (REPORT_HERD, _('Herd Report')),
        (REPORT_MILK_PRODUCTION, _('Milk Production')),
        (REPORT_FINANCIAL, _('Financial Statement')),
        (REPORT_EXPENSE, _('Expense Report')),
        (REPORT_ASSET, _('Asset Report')),
        (REPORT_LOAN, _('Loan Summary')),
    ]

    FREQUENCY_DAILY = 'DAILY'
    FREQUENCY_WEEKLY = 'WEEKLY'
    FREQUENCY_MONTHLY = 'MONTHLY'
    FREQUENCY_QUARTERLY = 'QUARTERLY'

    FREQUENCY_CHOICES = [
        (FREQUENCY_DAILY, _('Daily')),
        (FREQUENCY_WEEKLY, _('Weekly')),
        (FREQUENCY_MONTHLY, _('Monthly')),
        (FREQUENCY_QUARTERLY, _('Quarterly')),
    ]

    schedule_id = models.AutoField(primary_key=True)
    report_type = models.CharField(_('Report Type'), max_length=20, choices=REPORT_TYPE_CHOICES)
    name = models.CharField(_('Schedule Name'), max_length=100)
    frequency = models.CharField(_('Frequency'), max_length=10, choices=FREQUENCY_CHOICES)
    # For weekly reports
    day_of_week = models.PositiveSmallIntegerField(_('Day of Week (0=Mon, 6=Sun)'), null=True, blank=True)
    # For monthly/quarterly reports
    day_of_month = models.PositiveSmallIntegerField(_('Day of Month (1-31)'), null=True, blank=True)
    time_of_day = models.TimeField(_('Time of Day'))
    recipients = models.TextField(_('Recipients (email addresses, one per line)'))
    is_active = models.BooleanField(_('Active'), default=True)
    last_run = models.DateTimeField(_('Last Run'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()}) - {self.get_frequency_display()}"

    class Meta:
        verbose_name = _('Report Schedule')
        verbose_name_plural = _('Report Schedules')
        ordering = ['report_type', 'frequency']