from django.apps import AppConfig


class EmsProjectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ems_project'

    def ready(self):
        """Import signals when app is ready"""
        import ems_project.signals
