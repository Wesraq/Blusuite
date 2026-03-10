from django.contrib import admin
from .audit import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user_email', 'action', 'model_name', 'object_repr', 'company', 'ip_address')
    list_filter = ('action', 'model_name', 'company')
    search_fields = ('user_email', 'object_repr', 'ip_address')
    readonly_fields = ('user', 'user_email', 'action', 'model_name', 'object_id',
                       'object_repr', 'changes', 'company', 'ip_address',
                       'user_agent', 'extra', 'timestamp')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False  # Audit logs are immutable

    def has_change_permission(self, request, obj=None):
        return False  # Audit logs are immutable

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only platform superusers can purge
