from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from finance.models import ExpenseRecord, ExpenseCategory


class Asset(models.Model):
    """Model for fixed assets."""
    CATEGORY_LAND = 'LAND'
    CATEGORY_BUILDING = 'BUILDING'
    CATEGORY_MACHINERY = 'MACHINERY'
    CATEGORY_VEHICLE = 'VEHICLE'
    CATEGORY_EQUIPMENT = 'EQUIPMENT'
    CATEGORY_OTHER = 'OTHER'

    CATEGORY_CHOICES = [
        (CATEGORY_LAND, _('Land')),
        (CATEGORY_BUILDING, _('Building')),
        (CATEGORY_MACHINERY, _('Machinery')),
        (CATEGORY_VEHICLE, _('Vehicle')),
        (CATEGORY_EQUIPMENT, _('Equipment')),
        (CATEGORY_OTHER, _('Other')),
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_SOLD = 'SOLD'
    STATUS_RETIRED = 'RETIRED'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, _('Active')),
        (STATUS_SOLD, _('Sold')),
        (STATUS_RETIRED, _('Retired')),
    ]

    DEPRECIATION_SLM = 'SLM'
    DEPRECIATION_WDV = 'WDV'

    DEPRECIATION_METHOD_CHOICES = [
        (DEPRECIATION_SLM, _('Straight Line Method')),
        (DEPRECIATION_WDV, _('Written Down Value Method')),
    ]

    asset_id = models.AutoField(primary_key=True)
    name = models.CharField(_('Asset Name'), max_length=100)
    category = models.CharField(_('Category'), max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(_('Description'), blank=True)
    purchase_date = models.DateField(_('Purchase Date'))
    purchase_cost = models.DecimalField(_('Purchase Cost'), max_digits=12, decimal_places=2)
    useful_life_years = models.PositiveIntegerField(_('Useful Life (Years)'))
    salvage_value = models.DecimalField(_('Salvage Value'), max_digits=12, decimal_places=2)
    depreciation_method = models.CharField(_('Depreciation Method'), max_length=3,
                                           choices=DEPRECIATION_METHOD_CHOICES, default=DEPRECIATION_SLM)
    status = models.CharField(_('Status'), max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    disposal_date = models.DateField(_('Disposal Date'), null=True, blank=True)
    disposal_price = models.DecimalField(_('Disposal Price'), max_digits=12, decimal_places=2, null=True, blank=True)
    location = models.CharField(_('Location'), max_length=100, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_monthly_depreciation(self, book_value=None):
        """Calculate monthly depreciation amount based on method."""
        if book_value is None:
            book_value = self.purchase_cost

        if self.depreciation_method == self.DEPRECIATION_SLM:
            # Straight Line Method
            if self.useful_life_years > 0:
                return (self.purchase_cost - self.salvage_value) / (self.useful_life_years * 12)
            return 0

        elif self.depreciation_method == self.DEPRECIATION_WDV:
            # Written Down Value Method
            # Calculate annual rate: (1 - (Salvage/Cost)^(1/Life))
            if self.useful_life_years > 0 and self.salvage_value < self.purchase_cost:
                annual_rate = 1 - (self.salvage_value / self.purchase_cost) ** (1 / self.useful_life_years)
                return book_value * (annual_rate / 12)
            return 0

        return 0

    def run_monthly_depreciation(self, for_date=None):
        """Run depreciation calculation for a specific month."""
        if not for_date:
            for_date = timezone.now().date().replace(day=1) - timezone.timedelta(days=1)  # Last day of previous month

        # Check if depreciation already exists for this month
        if DepreciationRecord.objects.filter(
                asset=self,
                date__year=for_date.year,
                date__month=for_date.month
        ).exists():
            return None

        # Get latest depreciation record to determine current book value
        latest_record = DepreciationRecord.objects.filter(asset=self).order_by('-date').first()

        if latest_record:
            book_value = latest_record.book_value
            accumulated_depreciation = latest_record.accumulated_depreciation
        else:
            book_value = self.purchase_cost
            accumulated_depreciation = 0

        # Check if book value has reached or is below salvage value
        if book_value <= self.salvage_value:
            return None

        # Calculate depreciation for current month
        monthly_depreciation = self.calculate_monthly_depreciation(book_value)

        # Ensure book value doesn't drop below salvage value
        if book_value - monthly_depreciation < self.salvage_value:
            monthly_depreciation = book_value - self.salvage_value

        # Update accumulated depreciation and book value
        accumulated_depreciation += monthly_depreciation
        book_value -= monthly_depreciation

        # Create depreciation record
        depreciation_record = DepreciationRecord.objects.create(
            asset=self,
            date=for_date,
            depreciation_amount=monthly_depreciation,
            accumulated_depreciation=accumulated_depreciation,
            book_value=book_value
        )

        return depreciation_record

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    class Meta:
        verbose_name = _('Asset')
        verbose_name_plural = _('Assets')
        ordering = ['-purchase_date', 'name']


class DepreciationRecord(models.Model):
    """Model for recording depreciation of assets."""
    depreciation_id = models.AutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='depreciation_records')
    date = models.DateField(_('Depreciation Date'))
    depreciation_amount = models.DecimalField(_('Depreciation Amount'), max_digits=12, decimal_places=2)
    accumulated_depreciation = models.DecimalField(_('Accumulated Depreciation'), max_digits=12, decimal_places=2)
    book_value = models.DecimalField(_('Book Value'), max_digits=12, decimal_places=2)
    related_expense = models.OneToOneField(ExpenseRecord, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='depreciation_record')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Create expense record if it doesn't exist
        if not self.related_expense:
            try:
                depreciation_category, _ = ExpenseCategory.objects.get_or_create(
                    name='Depreciation',
                    defaults={'is_direct_cost': False}
                )

                expense = ExpenseRecord.objects.create(
                    date=self.date,
                    category=depreciation_category,
                    description=f"Depreciation for {self.asset.name}",
                    amount=self.depreciation_amount,
                    related_module='DepreciationRecord',
                    related_record_id=self.depreciation_id,
                    notes=f"Monthly depreciation for {self.asset.name} ({self.asset.get_category_display()})"
                )

                self.related_expense = expense
                self.save(update_fields=['related_expense'])
            except Exception as e:
                # Log the error
                print(f"Error creating expense record: {e}")

    def __str__(self):
        return f"{self.asset} - Depreciation on {self.date}: {self.depreciation_amount}"

    class Meta:
        verbose_name = _('Depreciation Record')
        verbose_name_plural = _('Depreciation Records')
        ordering = ['-date', 'asset']
        # Ensure only one depreciation record per asset per month
        unique_together = [['asset', 'date']]


class AssetMaintenance(models.Model):
    """Model for tracking asset maintenance."""
    maintenance_id = models.AutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenance_records')
    date = models.DateField(_('Maintenance Date'))
    description = models.CharField(_('Description'), max_length=255)
    cost = models.DecimalField(_('Cost'), max_digits=10, decimal_places=2)
    performed_by = models.CharField(_('Performed By'), max_length=100, blank=True)
    next_maintenance_date = models.DateField(_('Next Maintenance Date'), null=True, blank=True)
    related_expense = models.OneToOneField(ExpenseRecord, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='asset_maintenance')
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Create expense record if it doesn't exist
        if not self.related_expense and self.cost > 0:
            try:
                maintenance_category, _ = ExpenseCategory.objects.get_or_create(
                    name='Maintenance',
                    defaults={'is_direct_cost': False}
                )

                expense = ExpenseRecord.objects.create(
                    date=self.date,
                    category=maintenance_category,
                    description=f"Maintenance for {self.asset.name}: {self.description}",
                    amount=self.cost,
                    related_module='AssetMaintenance',
                    related_record_id=self.maintenance_id,
                    notes=self.notes
                )

                self.related_expense = expense
                self.save(update_fields=['related_expense'])
            except Exception as e:
                # Log the error
                print(f"Error creating expense record: {e}")

    def __str__(self):
        return f"{self.asset} - Maintenance on {self.date}: {self.description}"

    class Meta:
        verbose_name = _('Asset Maintenance')
        verbose_name_plural = _('Asset Maintenances')
        ordering = ['-date', 'asset']