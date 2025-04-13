"""
Application configuration for the Inventory app in Super Duper Dairy ERP System

This module defines the Django AppConfig for the inventory management module.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InventoryConfig(AppConfig):
    """Configuration for the Inventory application"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    verbose_name = _('Inventory')

    def ready(self):
        """
        Connect signals when the app is ready

        This ensures that signal handlers are properly connected
        when Django starts up, enabling the automatic inventory
        tracking functionality.
        """
        # Import signals module to connect signal handlers
        from . import signals
        signals.connect_signals()