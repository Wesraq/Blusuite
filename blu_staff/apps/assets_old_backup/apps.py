from django.apps import AppConfig


class AssetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # Expose as 'assets' module (via APPS_ROOT) to keep migrations and URLs aligned
    # Django import path for this legacy app package
    name = 'blu_staff.apps.assets_old_backup'
    label = 'assets'
    verbose_name = 'Asset Management'

    def import_models(self):
        """
        Prevent Django from loading legacy models to avoid reverse accessor clashes.
        This app is present only to satisfy historical migration dependencies.
        """
        # Populate an empty model registry so calls to get_models() work
        self.models = {}
        self.models_module = None
