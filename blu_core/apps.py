from django.apps import AppConfig


class BluCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blu_core'
    verbose_name = 'BLU Core'

    def ready(self):
        from .signals import register_all
        register_all()
