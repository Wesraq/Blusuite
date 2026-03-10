from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blu_staff.apps.notifications'
    label = 'notifications'

    def ready(self):
        """Import signals when app is ready"""
        from . import signals
        signals.register_all()
