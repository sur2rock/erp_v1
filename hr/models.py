from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from finance.models import ExpenseRecord, ExpenseCategory


class Employee(models.Model):
    """Model for employee data."""
    ROLE_MANAGER = 'MANAGER'
    ROLE_MILKER = 'MILKER'
    ROLE_FEEDER = 'FEEDER'
    ROLE_VET_TECH = 'VET_TECH'
    ROLE_CLEANER = 'CLEANER'
    ROLE_DRIVER = 'DRIVER'
    ROLE_OTHER = 'OTHER'

    ROLE_CHOICES = [
        (ROLE_MANAGER, _('Farm Manager')),
        (ROLE_MILKER, _('Milker')),
        (ROLE_FEEDER, _('Feeder')),
        (ROLE_VET_TECH, _('Veterinary Technician')),
        (ROLE_CLEANER, _('Cleaner')),
        (ROLE_DRIVER, _('Driver')),
        (ROLE_OTHER, _('Other')),
    ]

    SALARY_MONTHLY = 'MONTHLY'
    SALARY_HOURLY = 'HOURLY'

    SALARY_TYPE_CHOICES = [
        (SALARY_MONTHLY, _('Monthly')),
        (SALARY_HOURLY, _('Hourly')),
    ]

    employee_id = models.AutoField(primary_key=True)
    name = models.CharField(_('Name'), max_length=100)
    role = models.CharField(_('Role'), max_length=20, choices=ROLE_CHOICES)
    join_date = models.DateField(_('Join Date'))
    salary_type = models.CharField(_('Salary Type'), max_length=10, choices=SALARY_TYPE_CHOICES)
    base_salary_rate = models.DecimalField(_('Base Salary/Rate'), max_digits=10, decimal_places=2)
    overtime_rate_multiplier = models.DecimalField(_('Overtime Rate Multiplier'), max_digits=3,
                                                   decimal_places=1, default=1.5)
    benefit_details = models.TextField(_('Benefit Details'), blank=True)
    contact_number = models.CharField(_('Contact Number'), max_length=20, blank=True)
    address = models.TextField(_('Address'), blank=True)
    emergency_contact = models.CharField(_('Emergency Contact'), max_length=100, blank=True)
    is_active = models.BooleanField(_('Active'), default=True)
    termination_date = models.DateField(_('Termination Date'), null=True, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    class Meta:
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')
        ordering = ['name']


class Timesheet(models.Model):
    """Model for tracking employee work hours."""
    timesheet_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='timesheets')
    date = models.DateField(_('Date'))
    hours_worked = models.DecimalField(_('Hours Worked'), max_digits=5, decimal_places=2)
    overtime_hours = models.DecimalField(_('Overtime Hours'), max_digits=5, decimal_places=2, default=0)
    activity_description = models.CharField(_('Activity Description'), max_length=255, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee} - {self.date}: {self.hours_worked} hrs"

    class Meta:
        verbose_name = _('Timesheet')
        verbose_name_plural = _('Timesheets')
        ordering = ['-date', 'employee']
        # Ensure only one timesheet entry per employee per day
        unique_together = ['employee', 'date']


class Payroll(models.Model):
    """Model for calculating and recording employee payroll."""
    payroll_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_records')
    pay_period_start = models.DateField(_('Pay Period Start'))
    pay_period_end = models.DateField(_('Pay Period End'))
    gross_pay = models.DecimalField(_('Gross Pay'), max_digits=10, decimal_places=2)
    deductions = models.DecimalField(_('Deductions'), max_digits=10, decimal_places=2, default=0)
    net_pay = models.DecimalField(_('Net Pay'), max_digits=10, decimal_places=2)
    payment_date = models.DateField(_('Payment Date'))
    payment_method = models.CharField(_('Payment Method'), max_length=50, blank=True)
    related_expense = models.OneToOneField(ExpenseRecord, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='payroll')
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Calculate net pay if not set
        if self.gross_pay and not self.net_pay:
            self.net_pay = self.gross_pay - self.deductions

        super().save(*args, **kwargs)

        # Create expense record if it doesn't exist
        if not self.related_expense:
            try:
                labor_category, _ = ExpenseCategory.objects.get_or_create(
                    name='Labor',
                    defaults={'is_direct_cost': False}
                )

                expense = ExpenseRecord.objects.create(
                    date=self.payment_date,
                    category=labor_category,
                    description=f"Salary for {self.employee.name} ({self.pay_period_start} to {self.pay_period_end})",
                    amount=self.gross_pay,
                    related_module='Payroll',
                    related_record_id=self.payroll_id,
                    notes=self.notes
                )

                self.related_expense = expense
                self.save(update_fields=['related_expense'])
            except Exception as e:
                # Log the error
                print(f"Error creating expense record: {e}")

    @classmethod
    def calculate_payroll(cls, employee, start_date, end_date, payment_date=None):
        """Calculate payroll for an employee for a specified period."""
        if not payment_date:
            from django.utils import timezone
            payment_date = timezone.now().date()

        # Get relevant timesheets
        timesheets = Timesheet.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        )

        # If no timesheets found, return None
        if not timesheets.exists():
            return None

        # Calculate hours
        total_hours = timesheets.aggregate(
            regular=Sum('hours_worked'),
            overtime=Sum('overtime_hours')
        )
        regular_hours = total_hours['regular'] or 0
        overtime_hours = total_hours['overtime'] or 0

        # Calculate pay based on salary type
        if employee.salary_type == Employee.SALARY_MONTHLY:
            # For monthly salary, prorate based on work days if needed
            import calendar
            from datetime import timedelta

            # Calculate total days in month and worked days in period
            total_days = calendar.monthrange(start_date.year, start_date.month)[1]
            work_days = (end_date - start_date).days + 1

            # Prorate if period is not full month
            if work_days < total_days:
                gross_pay = (employee.base_salary_rate / total_days) * work_days
            else:
                gross_pay = employee.base_salary_rate

            # Add overtime if applicable
            hourly_rate = employee.base_salary_rate / (total_days * 8)  # Assuming 8-hour workday
            overtime_pay = overtime_hours * hourly_rate * employee.overtime_rate_multiplier
            gross_pay += overtime_pay

        else:  # Hourly
            # Calculate pay based on regular and overtime hours
            regular_pay = regular_hours * employee.base_salary_rate
            overtime_pay = overtime_hours * employee.base_salary_rate * employee.overtime_rate_multiplier
            gross_pay = regular_pay + overtime_pay

        # Default deduction rate (can be more sophisticated based on tax rules, benefits, etc.)
        deductions = gross_pay * 0.1  # Example: 10% deduction

        net_pay = gross_pay - deductions

        # Create payroll record
        payroll = cls.objects.create(
            employee=employee,
            pay_period_start=start_date,
            pay_period_end=end_date,
            gross_pay=gross_pay,
            deductions=deductions,
            net_pay=net_pay,
            payment_date=payment_date,
            notes=f"Regular hours: {regular_hours}, Overtime hours: {overtime_hours}"
        )

        return payroll

    def __str__(self):
        return f"{self.employee} - Payroll for {self.pay_period_start} to {self.pay_period_end}"

    class Meta:
        verbose_name = _('Payroll')
        verbose_name_plural = _('Payrolls')
        ordering = ['-payment_date', 'employee']