from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class ForecastSimulation(models.Model):
    """Model for storing forecast simulation parameters and results."""
    simulation_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Simulation Name'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(_('Created By'), max_length=100, blank=True)

    # Input parameters
    forecast_period_years = models.PositiveSmallIntegerField(_('Forecast Period (Years)'), default=1)
    milk_price_change_percentage = models.DecimalField(_('Milk Price Change (%)'), max_digits=6, decimal_places=2,
                                                       default=0)
    feed_cost_inflation_percentage = models.DecimalField(_('Feed Cost Inflation (%)'), max_digits=6, decimal_places=2,
                                                         default=0)
    labor_cost_escalation_percentage = models.DecimalField(_('Labor Cost Escalation (%)'), max_digits=6,
                                                           decimal_places=2, default=0)
    herd_growth_rate_percentage = models.DecimalField(_('Herd Growth Rate (%)'), max_digits=6, decimal_places=2,
                                                      default=0)
    other_parameters = models.JSONField(_('Other Parameters'), default=dict, blank=True)

    # Results storage
    results = models.JSONField(_('Simulation Results'), default=dict, blank=True,
                               help_text=_('JSON of projected metrics for each period'))

    def __str__(self):
        return f"{self.name} - {self.created_at.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = _('Forecast Simulation')
        verbose_name_plural = _('Forecast Simulations')
        ordering = ['-created_at']


class ForecastChart(models.Model):
    """Model for storing forecast chart configurations."""
    CHART_LINE = 'LINE'
    CHART_BAR = 'BAR'
    CHART_STACKED_BAR = 'STACKED_BAR'
    CHART_PIE = 'PIE'

    CHART_TYPE_CHOICES = [
        (CHART_LINE, _('Line Chart')),
        (CHART_BAR, _('Bar Chart')),
        (CHART_STACKED_BAR, _('Stacked Bar Chart')),
        (CHART_PIE, _('Pie Chart')),
    ]

    chart_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    simulation = models.ForeignKey(ForecastSimulation, on_delete=models.CASCADE, related_name='charts')
    title = models.CharField(_('Chart Title'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    chart_type = models.CharField(_('Chart Type'), max_length=15, choices=CHART_TYPE_CHOICES)
    x_axis_label = models.CharField(_('X-Axis Label'), max_length=50, blank=True)
    y_axis_label = models.CharField(_('Y-Axis Label'), max_length=50, blank=True)
    data_series = models.JSONField(_('Data Series'), default=list,
                                   help_text=_('JSON array of data series configurations'))
    config = models.JSONField(_('Chart Configuration'), default=dict, blank=True,
                              help_text=_('JSON of additional chart configuration options'))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_chart_type_display()}) - {self.simulation.name}"

    class Meta:
        verbose_name = _('Forecast Chart')
        verbose_name_plural = _('Forecast Charts')
        ordering = ['simulation', 'title']