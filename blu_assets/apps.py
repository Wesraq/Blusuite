from django.apps import AppConfig


class BluAssetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blu_assets'
    label = 'blu_assets'
    verbose_name = 'BLU Asset Management Suite (AMS)'
    
    def ready(self):
        """Import signals and perform app initialization"""
        # Import signals if any
        pass
