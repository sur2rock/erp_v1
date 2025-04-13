from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.conf import settings
from finance.models import ExpenseRecord, ExpenseCategory

# Import Buffalo model if it exists in another app
try:
    from herd.models import Buffalo
except ImportError:
    # Create a placeholder model if Buffalo model doesn't exist yet
    class Buffalo(models.Model):
        name = models.CharField(max_length=100)

        def __str__(self):
            return self.name

        class Meta:
            abstract = True


class UtilityReading(models.Model):
    UTILITY_TYPES = [
        ('electricity', 'Electricity'),
        ('water', 'Water'),
        ('fuel', 'Fuel'),
        ('ro_system', 'RO System'),
        ('other', 'Other'),
    ]

    utility_type = models.CharField(max_length=20, choices=UTILITY_TYPES)
    date = models.DateField()
    reading_value = models.FloatField(validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=20)  # kWh, cubic meters, liters, etc.
    meter_id = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='utility_readings_created'
    )

    def __str__(self):
        return f"{self.get_utility_type_display()} Reading: {self.reading_value} {self.unit} on {self.date}"

    def get_absolute_url(self):
        return reverse('operations:utility_reading_detail', kwargs={'pk': self.pk})

    class Meta:
        ordering = ['-date', 'utility_type']
        verbose_name = 'Utility Reading'
        verbose_name_plural = 'Utility Readings'


class UtilityBill(models.Model):
    UTILITY_TYPES = [
        ('electricity', 'Electricity'),
        ('water', 'Water'),
        ('fuel', 'Fuel'),
        ('ro_system', 'RO System'),
        ('other', 'Other'),
    ]

    PAYMENT_STATUS = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('disputed', 'Disputed'),
    ]

    utility_type = models.CharField(max_length=20, choices=UTILITY_TYPES)
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    consumption = models.FloatField(validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=20)  # kWh, cubic meters, liters, etc.
    unit_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    fixed_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    invoice_number = models.CharField(max_length=50, blank=True, null=True)
    due_date = models.DateField()
    paid_date = models.DateField(blank=True, null=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='unpaid')
    related_expense = models.OneToOneField(
        ExpenseRecord,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='utility_bill'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='utility_bills_created'
    )

    def __str__(self):
        return f"{self.get_utility_type_display()} Bill: {self.total_amount} for {self.billing_period_start} to {self.billing_period_end}"

    def get_absolute_url(self):
        return reverse('operations:utility_bill_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        # Calculate total amount if not provided
        if not self.total_amount:
            self.total_amount = (self.consumption * float(self.unit_rate)) + float(self.fixed_charges)

        # Create or update expense record
        if not self.related_expense:
            try:
                expense_category = ExpenseCategory.objects.get(name='Utilities')
            except ExpenseCategory.DoesNotExist:
                expense_category = ExpenseCategory.objects.create(
                    name='Utilities',
                    is_direct_cost=False
                )

            expense_record = ExpenseRecord.objects.create(
                date=self.billing_period_end,
                category=expense_category,
                description=f"{self.get_utility_type_display()} bill from {self.billing_period_start} to {self.billing_period_end}",
                amount=self.total_amount,
                related_module='UtilityBill',
                related_record_id=self.pk if self.pk else None,
                supplier_vendor=f"{self.get_utility_type_display()} Provider",
                notes=self.notes
            )
            self.related_expense = expense_record
        else:
            self.related_expense.amount = self.total_amount
            self.related_expense.date = self.billing_period_end
            self.related_expense.description = f"{self.get_utility_type_display()} bill from {self.billing_period_start} to {self.billing_period_end}"
            self.related_expense.notes = self.notes
            self.related_expense.save()

        # Update payment status based on due date and paid date
        if self.paid_date:
            self.payment_status = 'paid'
        elif self.due_date < timezone.now().date() and self.payment_status != 'paid':
            self.payment_status = 'overdue'

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-billing_period_end', 'utility_type']
        verbose_name = 'Utility Bill'
        verbose_name_plural = 'Utility Bills'


class HealthRecord(models.Model):
    RECORD_TYPES = [
        ('vaccination', 'Vaccination'),
        ('treatment', 'Treatment'),
        ('checkup', 'Checkup'),
        ('breeding', 'Breeding Procedure'),
        ('other', 'Other'),
    ]

    buffalo = models.ForeignKey(
        'herd.Buffalo',
        on_delete=models.CASCADE,
        related_name='health_records'
    )
    date = models.DateField()
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    description = models.CharField(max_length=255)
    vet_name = models.CharField(max_length=100, blank=True, null=True)
    medication_used = models.CharField(max_length=255, blank=True, null=True)
    medication_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    service_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        null=True
    )
    follow_up_date = models.DateField(blank=True, null=True)
    related_expense = models.OneToOneField(
        ExpenseRecord,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='health_record'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='health_records_created'
    )

    def __str__(self):
        return f"{self.buffalo.name} - {self.get_record_type_display()} on {self.date}"

    def get_absolute_url(self):
        return reverse('operations:health_record_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        # Calculate total cost if not provided
        if not self.total_cost:
            self.total_cost = self.medication_cost + self.service_cost

        # Create or update expense record if costs exist
        if float(self.total_cost) > 0:
            if not self.related_expense:
                try:
                    expense_category = ExpenseCategory.objects.get(name='Veterinary')
                except ExpenseCategory.DoesNotExist:
                    expense_category = ExpenseCategory.objects.create(
                        name='Veterinary',
                        is_direct_cost=True
                    )

                expense_record = ExpenseRecord.objects.create(
                    date=self.date,
                    category=expense_category,
                    description=f"{self.get_record_type_display()} for {self.buffalo.name}: {self.description}",
                    amount=self.total_cost,
                    related_module='HealthRecord',
                    related_record_id=self.pk if self.pk else None,
                    related_buffalo=self.buffalo,
                    supplier_vendor=self.vet_name,
                    notes=self.notes
                )
                self.related_expense = expense_record
            else:
                self.related_expense.amount = self.total_cost
                self.related_expense.date = self.date
                self.related_expense.description = f"{self.get_record_type_display()} for {self.buffalo.name}: {self.description}"
                self.related_expense.related_buffalo = self.buffalo
                self.related_expense.supplier_vendor = self.vet_name
                self.related_expense.notes = self.notes
                self.related_expense.save()

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date', 'buffalo']
        verbose_name = 'Health Record'
        verbose_name_plural = 'Health Records'


class ScheduledAppointment(models.Model):
    APPOINTMENT_TYPES = [
        ('vaccination', 'Vaccination'),
        ('checkup', 'Checkup'),
        ('breeding', 'Breeding'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    ]

    buffalo = models.ForeignKey(
        'herd.Buffalo',
        on_delete=models.CASCADE,
        related_name='scheduled_appointments',
        blank=True,
        null=True
    )
    appointment_type = models.CharField(max_length=20, choices=APPOINTMENT_TYPES)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(blank=True, null=True)
    description = models.CharField(max_length=255)
    vet_name = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='scheduled')
    related_health_record = models.OneToOneField(
        HealthRecord,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='scheduled_appointment'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='appointments_created'
    )

    def __str__(self):
        if self.buffalo:
            return f"{self.buffalo.name} - {self.get_appointment_type_display()} on {self.scheduled_date}"
        return f"Herd {self.get_appointment_type_display()} on {self.scheduled_date}"

    def get_absolute_url(self):
        return reverse('operations:appointment_detail', kwargs={'pk': self.pk})

    @property
    def is_overdue(self):
        return self.scheduled_date < timezone.now().date() and self.status == 'scheduled'

    @property
    def days_until_appointment(self):
        if self.scheduled_date >= timezone.now().date():
            return (self.scheduled_date - timezone.now().date()).days
        return 0

    class Meta:
        ordering = ['scheduled_date', 'buffalo']
        verbose_name = 'Scheduled Appointment'
        verbose_name_plural = 'Scheduled Appointments'