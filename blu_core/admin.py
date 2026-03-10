from django.contrib import admin
from .audit import AuditLog
from .monitoring import SystemMetric, HealthCheckResult, AlertRule, Alert


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


@admin.register(SystemMetric)
class SystemMetricAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'metric_type', 'value', 'metadata_summary')
    list_filter = ('metric_type', 'timestamp')
    search_fields = ('metric_type',)
    readonly_fields = ('metric_type', 'value', 'timestamp', 'metadata')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    def metadata_summary(self, obj):
        if obj.metadata:
            return ', '.join(f'{k}={v}' for k, v in obj.metadata.items())
        return '-'
    metadata_summary.short_description = 'Metadata'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(HealthCheckResult)
class HealthCheckResultAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'check_name', 'status', 'response_time_ms', 'error_summary')
    list_filter = ('check_name', 'status', 'timestamp')
    search_fields = ('check_name', 'error_message')
    readonly_fields = ('check_name', 'status', 'response_time_ms', 'error_message', 'timestamp')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    def error_summary(self, obj):
        if obj.error_message:
            return obj.error_message[:100] + '...' if len(obj.error_message) > 100 else obj.error_message
        return '-'
    error_summary.short_description = 'Error'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'metric_type', 'threshold', 'severity', 'is_active', 'alert_count')
    list_filter = ('metric_type', 'severity', 'is_active')
    search_fields = ('name',)
    ordering = ('name',)
    
    def alert_count(self, obj):
        return obj.alerts.count()
    alert_count.short_description = 'Alerts Triggered'


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('triggered_at', 'rule', 'severity', 'metric_value', 'is_active_status', 'acknowledged_by')
    list_filter = ('severity', 'triggered_at', 'resolved_at')
    search_fields = ('rule__name', 'message')
    readonly_fields = ('rule', 'metric_value', 'message', 'severity', 'triggered_at')
    ordering = ('-triggered_at',)
    date_hierarchy = 'triggered_at'
    
    def is_active_status(self, obj):
        return obj.is_active
    is_active_status.short_description = 'Active'
    is_active_status.boolean = True
