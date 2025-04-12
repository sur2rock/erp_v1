from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import datetime


class Breed(models.Model):
    """Model for animal breeds."""
    name = models.CharField(_('Name'), max_length=100)
    description = models.TextField(_('Description'), blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Breed')
        verbose_name_plural = _('Breeds')


class Buffalo(models.Model):
    """Model for buffalo/cattle inventory."""
    # Status choices
    STATUS_MILKING = 'MILKING'
    STATUS_DRY = 'DRY'
    STATUS_PREGNANT = 'PREGNANT'
    STATUS_HEIFER = 'HEIFER'
    STATUS_CALF = 'CALF'
    STATUS_BULL = 'BULL'
    STATUS_SOLD = 'SOLD'
    STATUS_RETIRED = 'RETIRED'
    STATUS_DECEASED = 'DECEASED'

    STATUS_CHOICES = [
        (STATUS_MILKING, _('Active-Milking')),
        (STATUS_DRY, _('Active-Dry')),
        (STATUS_PREGNANT, _('Active-Pregnant')),
        (STATUS_HEIFER, _('Heifer')),
        (STATUS_CALF, _('Calf')),
        (STATUS_BULL, _('Bull')),
        (STATUS_SOLD, _('Sold')),
        (STATUS_RETIRED, _('Retired')),
        (STATUS_DECEASED, _('Deceased')),
    ]

    # Gender choices
    GENDER_FEMALE = 'FEMALE'
    GENDER_MALE = 'MALE'

    GENDER_CHOICES = [
        (GENDER_FEMALE, _('Female')),
        (GENDER_MALE, _('Male')),
    ]

    buffalo_id = models.CharField(_('ID/Tag Number'), max_length=50, unique=True)
    name = models.CharField(_('Name'), max_length=100, blank=True)
    breed = models.ForeignKey(Breed, on_delete=models.PROTECT, related_name='buffaloes')
    date_of_birth = models.DateField(_('Date of Birth'))
    purchase_date = models.DateField(_('Purchase Date'), null=True, blank=True)
    purchase_price = models.DecimalField(_('Purchase Price'), max_digits=12, decimal_places=2, null=True, blank=True)
    gender = models.CharField(_('Gender'), max_length=10, choices=GENDER_CHOICES)
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default=STATUS_CALF)
    current_location = models.CharField(_('Current Location'), max_length=100, blank=True)
    dam = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='calves_as_dam')
    sire = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='calves_as_sire')
    date_last_calved = models.DateField(_('Date Last Calved'), null=True, blank=True)
    date_due = models.DateField(_('Due Date'), null=True, blank=True)
    expected_dry_off_date = models.DateField(_('Expected Dry Off Date'), null=True, blank=True)
    lactation_number = models.PositiveIntegerField(_('Lactation Number'), default=0)
    cumulative_cost = models.DecimalField(_('Cumulative Cost'), max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(_('Notes'), blank=True)
    is_active = models.BooleanField(_('Active'), default=True)
    image = models.ImageField(_('Image'), upload_to='buffalo_images/', null=True, blank=True)
    custom_data = models.JSONField(_('Custom Data'), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.buffalo_id} - {self.name or 'Unnamed'}"

    @property
    def age(self):
        """Calculate age in years."""
        if self.date_of_birth:
            today = timezone.now().date()
            return (today - self.date_of_birth).days // 365
        return None

    @property
    def days_in_milk(self):
        """Calculate days in milk if in milking status."""
        if self.status == self.STATUS_MILKING and self.date_last_calved:
            today = timezone.now().date()
            return (today - self.date_last_calved).days
        return None

    def update_status_from_lifecycle_event(self, event_type, event_date):
        """Update buffalo status based on lifecycle event."""
        if event_type == 'CALVING':
            self.status = self.STATUS_MILKING
            self.date_last_calved = event_date
            self.lactation_number += 1
            # Calculate expected dry off date - default to 305 days
            self.expected_dry_off_date = event_date + datetime.timedelta(days=305)

        elif event_type == 'DRY_OFF':
            self.status = self.STATUS_DRY

        elif event_type == 'BRED':
            # Calculate due date - default to 280 days
            self.date_due = event_date + datetime.timedelta(days=280)

        elif event_type == 'CONFIRMED_PREGNANT':
            self.status = self.STATUS_PREGNANT

        elif event_type == 'SOLD':
            self.status = self.STATUS_SOLD
            self.is_active = False

        elif event_type == 'RETIRED':
            self.status = self.STATUS_RETIRED
            self.is_active = False

        elif event_type == 'DECEASED':
            self.status = self.STATUS_DECEASED
            self.is_active = False

        elif event_type == 'WEANED':
            if self.status == self.STATUS_CALF:
                self.status = self.STATUS_HEIFER if self.gender == self.GENDER_FEMALE else self.STATUS_BULL

        self.save()

    class Meta:
        verbose_name = _('Buffalo')
        verbose_name_plural = _('Buffaloes')
        ordering = ['buffalo_id']


class LifecycleEvent(models.Model):
    """Model for buffalo lifecycle events."""
    EVENT_BIRTH = 'BIRTH'
    EVENT_PURCHASE = 'PURCHASE'
    EVENT_CALVING = 'CALVING'
    EVENT_DRY_OFF = 'DRY_OFF'
    EVENT_BRED = 'BRED'
    EVENT_CONFIRMED_PREGNANT = 'CONFIRMED_PREGNANT'
    EVENT_SOLD = 'SOLD'
    EVENT_RETIRED = 'RETIRED'
    EVENT_DECEASED = 'DECEASED'
    EVENT_WEANED = 'WEANED'

    EVENT_CHOICES = [
        (EVENT_BIRTH, _('Birth')),
        (EVENT_PURCHASE, _('Purchase')),
        (EVENT_CALVING, _('Calving')),
        (EVENT_DRY_OFF, _('Dry Off')),
        (EVENT_BRED, _('Bred')),
        (EVENT_CONFIRMED_PREGNANT, _('Confirmed Pregnant')),
        (EVENT_SOLD, _('Sold')),
        (EVENT_RETIRED, _('Retired')),
        (EVENT_DECEASED, _('Deceased')),
        (EVENT_WEANED, _('Weaned')),
    ]

    event_id = models.AutoField(primary_key=True)
    buffalo = models.ForeignKey(Buffalo, on_delete=models.CASCADE, related_name='lifecycle_events')
    event_type = models.CharField(_('Event Type'), max_length=50, choices=EVENT_CHOICES)
    event_date = models.DateField(_('Event Date'))
    notes = models.TextField(_('Notes'), blank=True)
    related_calf = models.ForeignKey(Buffalo, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='birth_event')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.buffalo} - {self.event_type} on {self.event_date}"

    class Meta:
        verbose_name = _('Lifecycle Event')
        verbose_name_plural = _('Lifecycle Events')
        ordering = ['-event_date']


@receiver(post_save, sender=LifecycleEvent)
def update_buffalo_status(sender, instance, created, **kwargs):
    """Signal handler to update buffalo status when lifecycle event is created/updated."""
    if created or instance.event_type in [choice[0] for choice in LifecycleEvent.EVENT_CHOICES]:
        instance.buffalo.update_status_from_lifecycle_event(instance.event_type, instance.event_date)


class MilkProduction(models.Model):
    """Model for recording daily milk production."""
    TIME_AM = 'AM'
    TIME_PM = 'PM'

    TIME_CHOICES = [
        (TIME_AM, _('Morning')),
        (TIME_PM, _('Evening')),
    ]

    production_id = models.AutoField(primary_key=True)
    buffalo = models.ForeignKey(Buffalo, on_delete=models.CASCADE, related_name='milk_records')
    date = models.DateField(_('Date'))
    time_of_day = models.CharField(_('Time of Day'), max_length=2, choices=TIME_CHOICES)
    quantity_litres = models.DecimalField(_('Quantity (Litres)'), max_digits=7, decimal_places=2)
    somatic_cell_count = models.PositiveIntegerField(_('Somatic Cell Count'), null=True, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        time_display = 'Morning' if self.time_of_day == self.TIME_AM else 'Evening'
        return f"{self.buffalo} - {self.date} {time_display}: {self.quantity_litres} L"

    class Meta:
        verbose_name = _('Milk Production Record')
        verbose_name_plural = _('Milk Production Records')
        ordering = ['-date', 'time_of_day']
        # Ensure only one record per buffalo per date and time of day
        unique_together = ['buffalo', 'date', 'time_of_day']