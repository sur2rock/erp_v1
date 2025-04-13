"""
finance/apps.py

Configures the Finance app.
The ready() method is used to import signal handlers so that they are active when the app is loaded.
"""

from django.apps import AppConfig

class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finance'

    def ready(self):
        # Import signals so that they are connected.
        import finance.signals
