from django.apps import AppConfig


class RequestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blu_staff.apps.requests'
    label = 'requests'
    verbose_name = 'Employee Requests'
