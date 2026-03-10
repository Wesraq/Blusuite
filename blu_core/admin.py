from django.contrib import admin
from .audit import AuditLog
from .monitoring import SystemMetric, HealthCheckResult, AlertRule, Alert
from .mfa import MFAMethod, BackupCode, MFAChallenge
from .settings_manager import SystemSetting, CompanySettingOverride, SettingsVersion, SettingsTemplate
from .onboarding_automation import CompanyOnboarding, OnboardingReminder


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


@admin.register(MFAMethod)
class MFAMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'method_type', 'is_primary', 'is_active', 'verified_status', 'last_used_at')
    list_filter = ('method_type', 'is_primary', 'is_active', 'verified_at')
    search_fields = ('user__email', 'email', 'phone_number')
    readonly_fields = ('user', 'created_at', 'last_used_at', 'verified_at')
    ordering = ('-created_at',)
    
    def verified_status(self, obj):
        return obj.is_verified()
    verified_status.short_description = 'Verified'
    verified_status.boolean = True


@admin.register(BackupCode)
class BackupCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code_masked', 'used_status', 'created_at', 'used_at')
    list_filter = ('used_at', 'created_at')
    search_fields = ('user__email',)
    readonly_fields = ('user', 'code', 'created_at', 'used_at')
    ordering = ('-created_at',)
    
    def code_masked(self, obj):
        if obj.is_used():
            return obj.code
        return obj.code[:4] + '-****-****'
    code_masked.short_description = 'Code'
    
    def used_status(self, obj):
        return obj.is_used()
    used_status.short_description = 'Used'
    used_status.boolean = True


@admin.register(MFAChallenge)
class MFAChallengeAdmin(admin.ModelAdmin):
    list_display = ('user', 'method_type', 'created_at', 'expires_at', 'verified_status', 'attempts', 'ip_address')
    list_filter = ('method_type', 'verified_at', 'created_at')
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('user', 'method_type', 'code', 'created_at', 'expires_at', 'verified_at', 'attempts', 'ip_address')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    def verified_status(self, obj):
        return obj.is_verified()
    verified_status.short_description = 'Verified'
    verified_status.boolean = True
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'category', 'data_type', 'value_display', 'is_required', 'is_sensitive', 'updated_at')
    list_filter = ('category', 'data_type', 'is_required', 'is_sensitive')
    search_fields = ('key', 'description')
    readonly_fields = ('created_at', 'updated_at', 'updated_by')
    ordering = ('category', 'key')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'key', 'description')
        }),
        ('Value Configuration', {
            'fields': ('value', 'default_value', 'data_type')
        }),
        ('Validation', {
            'fields': ('validation_rules', 'is_required', 'is_sensitive')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'updated_by')
        }),
    )
    
    def value_display(self, obj):
        if obj.is_sensitive:
            return '********'
        return str(obj.value)[:50]
    value_display.short_description = 'Value'


@admin.register(CompanySettingOverride)
class CompanySettingOverrideAdmin(admin.ModelAdmin):
    list_display = ('company', 'setting_key', 'value_display', 'is_active', 'updated_at')
    list_filter = ('is_active', 'system_setting__category', 'updated_at')
    search_fields = ('company__name', 'system_setting__key')
    readonly_fields = ('created_at', 'updated_at', 'updated_by')
    ordering = ('company', 'system_setting__category', 'system_setting__key')
    
    def setting_key(self, obj):
        return obj.system_setting.key
    setting_key.short_description = 'Setting'
    
    def value_display(self, obj):
        if obj.system_setting.is_sensitive:
            return '********'
        return str(obj.value)[:50]
    value_display.short_description = 'Value'


@admin.register(SettingsVersion)
class SettingsVersionAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'category', 'version_number', 'created_at', 'created_by', 'changes_count')
    list_filter = ('category', 'created_at')
    search_fields = ('company__name', 'comment')
    readonly_fields = ('company', 'category', 'settings_snapshot', 'changes', 'version_number', 'created_at', 'created_by')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    def company_name(self, obj):
        return obj.company.name if obj.company else 'System'
    company_name.short_description = 'Company'
    
    def changes_count(self, obj):
        return len(obj.changes)
    changes_count.short_description = 'Changes'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SettingsTemplate)
class SettingsTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active', 'is_default', 'updated_at')
    list_filter = ('category', 'is_active', 'is_default')
    search_fields = ('name', 'description')
    ordering = ('category', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category')
        }),
        ('Configuration', {
            'fields': ('settings_data', 'is_active', 'is_default')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(CompanyOnboarding)
class CompanyOnboardingAdmin(admin.ModelAdmin):
    list_display = ('company', 'status', 'completion_percentage', 'current_step', 'started_at', 'completed_at')
    list_filter = ('status', 'started_at', 'completed_at')
    search_fields = ('company__name',)
    readonly_fields = ('completion_percentage', 'is_complete', 'created_at', 'updated_at')
    ordering = ('-started_at',)
    
    fieldsets = (
        ('Company Information', {
            'fields': ('company', 'status', 'current_step')
        }),
        ('Progress', {
            'fields': ('completion_percentage', 'is_complete')
        }),
        ('Setup Steps', {
            'fields': (
                'company_info_complete',
                'admin_account_complete',
                'settings_configured',
                'first_employee_added',
                'first_department_created',
                'attendance_configured',
                'leave_policies_set',
                'payroll_configured',
                'documents_uploaded',
                'integrations_setup',
            )
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at', 'created_at', 'updated_at')
        }),
    )
    
    def completion_percentage(self, obj):
        return f"{obj.completion_percentage}%"
    completion_percentage.short_description = 'Completion'


@admin.register(OnboardingReminder)
class OnboardingReminderAdmin(admin.ModelAdmin):
    list_display = ('sent_to', 'reminder_type', 'sent_at', 'onboarding_type')
    list_filter = ('reminder_type', 'sent_at')
    search_fields = ('sent_to__email', 'sent_to__first_name', 'sent_to__last_name')
    readonly_fields = ('sent_at',)
    ordering = ('-sent_at',)
    
    def onboarding_type(self, obj):
        if obj.employee_onboarding:
            return f"Employee: {obj.employee_onboarding.employee.get_full_name()}"
        elif obj.company_onboarding:
            return f"Company: {obj.company_onboarding.company.name}"
        return "N/A"
    onboarding_type.short_description = 'Onboarding'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
