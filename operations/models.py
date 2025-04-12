from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from herd.models import Buffalo
from finance.models import ExpenseRecord, ExpenseCategory
from core.models import GlobalSettings, Alert


class UtilityReading(models.Model):
    """Model for utility meter readings."""
    UTILITY_ELECTRICITY = 'ELECTRICITY'
    UTILITY_WATER = 'WATER'
    UTILITY_FUEL = 'FUEL'
    UTILITY_RO = 'RO_SYSTEM'
    UTILITY_OTHER = 'OTHER'

    UTILITY_TYPE_CHOICES = [
        (UTILITY_ELECTRICITY, _('Electricity')),
        (UTILITY_WATER, _('Water')),
        (UTILITY_FUEL, _('Fuel')),
        (UTILITY_RO, _('RO System')),
        (UTILITY_OTHER, _('Other')),
    ]

    reading_id = models.AutoField(primary_key=True)
    utility_type = models.CharField(_('Utility Type'), max_length=20, choices=UTILITY_TYPE_CHOICES)
    date = models.DateField(_('Reading Date'))
    reading_value = models.DecimalField(_('Reading Value'), max_digits=10, decimal_places=2)
    unit = models.CharField(_('Unit'), max_length=20, help_text=_('e.g., kWh, Cubic meters, Litres'))
    meter_id = models.CharField(_('Meter ID'), max_length=50, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        utility_display = dict(self.UTILITY_TYPE_CHOICES).get(self.utility_type, self.utility_type)
        return f"{self.date} - {utility_display}: {self.reading_value} {self.unit}"

    class Meta:
        verbose_name = _('Utility Reading')
        verbose_name_plural = _('Utility Readings')
        ordering = ['-date', 'utility_type']


class UtilityBill(models.Model):
    """Model for utility bills."""
    UTILITY_ELECTRICITY = 'ELECTRICITY'
    UTILITY_WATER = 'WATER'
    UTILITY_FUEL = 'FUEL'
    UTILITY_RO = 'RO_SYSTEM'
    UTILITY_OTHER = 'OTHER'

    UTILITY_TYPE_CHOICES = [
        (UTILITY_ELECTRICITY, _('Electricity')),
        (UTILITY_WATER, _('Water')),
        (UTILITY_FUEL, _('Fuel')),
        (UTILITY_RO, _('RO System')),
        (UTILITY_OTHER, _('Other')),
    ]

    bill_id = models.AutoField(primary_key=True)
    utility_type = models.CharField(_('Utility Type'), max_length=20, choices=UTILITY_TYPE_CHOICES)
    billing_period_start = models.DateField(_('Billing Period Start'))
    billing_period_end = models.DateField(_('Billing Period End'))
    consumption = models.DecimalField(_('Consumption'), max_digits=10, decimal_places=2, null=True, blank=True,
                                      help_text=_('Total units consumed during the period'))
    unit_rate = models.DecimalField(_('Unit Rate'), max_digits=8, decimal_places=2, null=True, blank=True)
    fixed_charges = models.DecimalField(_('Fixed Charges'), max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(_('Total Amount'), max_digits=10, decimal_places=2)
    due_date = models.DateField(_('Due Date'), null=True, blank=True)
    paid_date = models.DateField(_('Paid Date'), null=True, blank=True)
    related_expense = models.OneToOneField(ExpenseRecord, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='utility_bill')
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-calculate total amount if not set
        if self.consumption and self.unit_rate and not self.total_amount:
            self.total_amount = (self.consumption * self.unit_rate) + self.fixed_charges

        super().save(*args, **kwargs)

        # Create expense record if it doesn't exist
        if not self.related_expense:
            try:
                utility_category, _ = ExpenseCategory.objects.get_or_create(
                    name='Utilities',
                    defaults={'is_direct_cost': False}
                )

                utility_display = dict(self.UTILITY_TYPE_CHOICES).get(self.utility_type, self.utility_type)
                expense = ExpenseRecord.objects.create(
                    date=self.billing_period_end,
                    category=utility_category,
                    description=f"{utility_display} bill for period {self.billing_period_start} to {self.billing_period_end}",
                    amount=self.total_amount,
                    related_module='UtilityBill',
                    related_record_id=self.bill_id,
                    notes=self.notes
                )

                self.related_expense = expense
                self.save(update_fields=['related_expense'])
            except Exception as e:
                # Log the error
                print(f"Error creating expense record: {e}")

    def __str__(self):
        utility_display = dict(self.UTILITY_TYPE_CHOICES).get(self.utility_type, self.utility_type)
        return f"{utility_display} bill: {self.billing_period_start} - {self.billing_period_end}"

    class Meta:
        verbose_name = _('Utility Bill')
        verbose_name_plural = _('Utility Bills')
        ordering = ['-billing_period_end', 'utility_type']


class HealthRecord(models.Model):
    """Model for animal health records and treatments."""
    RECORD_VACCINATION = 'VACCINATION'
    RECORD_TREATMENT = 'TREATMENT'
    RECORD_CHECKUP = 'CHECKUP'
    RECORD_BREEDING = 'BREEDING'

    RECORD_TYPE_CHOICES = [
        (RECORD_VACCINATION, _('Vaccination')),
        (RECORD_TREATMENT, _('Treatment')),
        (RECORD_CHECKUP, _('Checkup')),
        (RECORD_BREEDING, _('Breeding Procedure')),
    ]

    health_record_id = models.AutoField(primary_key=True)
    buffalo = models.ForeignKey(Buffalo, on_delete=models.CASCADE, related_name='health_records')
    date = models.DateField(_('Date'))
    record_type = models.CharField(_('Record Type'), max_length=20, choices=RECORD_TYPE_CHOICES)
    description = models.CharField(_('Description'), max_length=255)
    vet_name = models.CharField(_('Veterinarian'), max_length=100, blank=True)
    medication_used = models.CharField(_('Medication Used'), max_length=255, blank=True)
    medication_cost = models.DecimalField(_('Medication Cost'), max_digits=10, decimal_places=2, default=0)
    service_cost = models.DecimalField(_('Service Cost'), max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(_('Total Cost'), max_digits=10, decimal_places=2, blank=True)
    follow_up_date = models.DateField(_('Follow-up Date'), null=True, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    related_expense = models.OneToOneField(ExpenseRecord, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='health_record')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Calculate total cost
        self.total_cost = self.medication_cost + self.service_cost

        # Save the record
        super().save(*args, **kwargs)

        # Update buffalo status if it's a breeding record
        if self.record_type == self.RECORD_BREEDING:
            if 'AI' in self.description.upper() or 'ARTIFICIAL INSEMINATION' in self.description.upper():
                self.buffalo.update_status_from_lifecycle_event('BRED', self.date)
            elif 'CONFIRM' in self.description.upper() or 'PREGNANCY CHECK' in self.description.upper():
                self.buffalo.update_status_from_lifecycle_event('CONFIRMED_PREGNANT', self.date)

        # Create expense record if there are costs and no related expense yet
        if self.total_cost > 0 and not self.related_expense:
            try:
                vet_category, _ = ExpenseCategory.objects.get_or_create(
                    name='Veterinary',
                    defaults={'is_direct_cost': True}
                )

                expense = ExpenseRecord.objects.create(
                    date=self.date,
                    category=vet_category,
                    description=f"{self.get_record_type_display()}: {self.description}",
                    amount=self.total_cost,
                    related_module='HealthRecord',
                    related_record_id=self.health_record_id,
                    related_buffalo=self.buffalo,
                    notes=self.notes
                )

                self.related_expense = expense
                self.save(update_fields=['related_expense'])
            except Exception as e:
                # Log the error
                print(f"Error creating expense record: {e}")

    def __str__(self):
        return f"{self.buffalo} - {self.get_record_type_display()}: {self.description} on {self.date}"

    class Meta:
        verbose_name = _('Health Record')
        verbose_name_plural = _('Health Records')
        ordering = ['-date']


class ScheduledAppointment(models.Model):
    """Model for scheduling health and breeding appointments."""
    APPOINTMENT_VACCINATION = 'VACCINATION'
    APPOINTMENT_CHECKUP = 'CHECKUP'
    APPOINTMENT_BREEDING = 'BREEDING'

    APPOINTMENT_TYPE_CHOICES = [
        (APPOINTMENT_VACCINATION, _('Vaccination')),
        (APPOINTMENT_CHECKUP, _('Checkup')),
        (APPOINTMENT_BREEDING, _('Breeding')),
    ]

    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_MISSED = 'MISSED'

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, _('Scheduled')),
        (STATUS_COMPLETED, _('Completed')),
        (STATUS_MISSED, _('Missed')),
    ]

    appointment_id = models.AutoField(primary_key=True)
    buffalo = models.ForeignKey(Buffalo, on_delete=models.CASCADE, related_name='scheduled_appointments',
                                null=True, blank=True, help_text=_('If null, appointment is for whole herd'))
    appointment_type = models.CharField(_('Appointment Type'), max_length=20, choices=APPOINTMENT_TYPE_CHOICES)
    scheduled_date = models.DateField(_('Scheduled Date'))
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    related_health_record = models.OneToOneField(HealthRecord, on_delete=models.SET_NULL,
                                                 null=True, blank=True, related_name='scheduled_appointment')
    description = models.CharField(_('Description'), max_length=255)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Check if appointment is overdue and create alert if needed
        if self.status == self.STATUS_SCHEDULED:
            from django.utils import timezone
            today = timezone.now().date()

            if today > self.scheduled_date:
                try:
                    settings = GlobalSettings.objects.first()
                    overdue_days = (today - self.scheduled_date).days

                    if settings and overdue_days >= settings.alert_vet_visit_overdue_days:
                        # Check if alert already exists
                        existing_alert = Alert.objects.filter(
                            related_module='ScheduledAppointment',
                            related_record_id=self.appointment_id,
                            status=Alert.STATUS_ACTIVE
                        ).exists()

                        if not existing_alert:
                            buffalo_str = f"for {self.buffalo}" if self.buffalo else "for Herd"
                            Alert.objects.create(
                                title=f"Overdue {self.get_appointment_type_display()} {buffalo_str}",
                                message=f"Appointment scheduled for {self.scheduled_date} is overdue by {overdue_days} days.",
                                priority=Alert.PRIORITY_HIGH,
                                related_module='ScheduledAppointment',
                                related_record_id=self.appointment_id
                            )
                except Exception as e:
                    # Log the error
                    print(f"Error creating alert: {e}")

    def __str__(self):
        buffalo_str = f"Buffalo: {self.buffalo}" if self.buffalo else "Whole Herd"
        return f"{self.get_appointment_type_display()} for {buffalo_str} on {self.scheduled_date}"

    class Meta:
        verbose_name = _('Scheduled Appointment')
        verbose_name_plural = _('Scheduled Appointments')
        ordering = ['scheduled_date', 'status']


@receiver(post_save, sender=HealthRecord)
def update_appointment_status(sender, instance, created, **kwargs):
    """Update associated appointment as completed when health record is created."""
    if created:
        # Find appointment for this buffalo and type that is still scheduled
        appointments = ScheduledAppointment.objects.filter(
            buffalo=instance.buffalo,
            appointment_type__in=[
                ScheduledAppointment.APPOINTMENT_VACCINATION if instance.record_type == HealthRecord.RECORD_VACCINATION else
                ScheduledAppointment.APPOINTMENT_CHECKUP if instance.record_type == HealthRecord.RECORD_CHECKUP else
                ScheduledAppointment.APPOINTMENT_BREEDING if instance.record_type == HealthRecord.RECORD_BREEDING else None
            ],
            status=ScheduledAppointment.STATUS_SCHEDULED,
            scheduled_date__lte=instance.date
        ).order_by('scheduled_date')

        if appointments.exists():
            appointment = appointments.first()
            appointment.status = ScheduledAppointment.STATUS_COMPLETED
            appointment.related_health_record = instance
            appointment.save()