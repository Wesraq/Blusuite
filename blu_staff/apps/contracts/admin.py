from django.contrib import admin
from .models import EmployeeContract, ContractAmendment, ContractRenewal, ContractTemplate


@admin.register(EmployeeContract)
class EmployeeContractAdmin(admin.ModelAdmin):
    list_display = ['contract_number', 'employee', 'contract_type', 'status', 'start_date', 'end_date', 'is_expiring_soon']
    list_filter = ['status', 'contract_type', 'company', 'start_date']
    search_fields = ['contract_number', 'employee__first_name', 'employee__last_name', 'employee__email', 'job_title']
    readonly_fields = ['contract_number', 'created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('employee', 'company', 'contract_type', 'status', 'contract_number')
        }),
        ('Contract Details', {
            'fields': ('job_title', 'department', 'start_date', 'end_date', 'signed_date')
        }),
        ('Renewal Settings', {
            'fields': ('renewal_notice_period_days', 'auto_renew', 'renewed_from')
        }),
        ('Compensation', {
            'fields': ('salary', 'currency', 'salary_frequency')
        }),
        ('Work Details', {
            'fields': ('working_hours_per_week', 'probation_period_months', 'notice_period_days')
        }),
        ('Documents', {
            'fields': ('contract_document', 'signed_contract_document')
        }),
        ('Terms', {
            'fields': ('terms_and_conditions', 'special_clauses')
        }),
        ('Tracking', {
            'fields': ('created_by', 'created_at', 'updated_at', 'renewal_notification_sent', 'expiry_notification_sent')
        }),
    )


@admin.register(ContractAmendment)
class ContractAmendmentAdmin(admin.ModelAdmin):
    list_display = ['amendment_number', 'contract', 'amendment_date', 'effective_date', 'created_by']
    list_filter = ['amendment_date', 'effective_date']
    search_fields = ['amendment_number', 'contract__contract_number', 'contract__employee__first_name', 'contract__employee__last_name']
    readonly_fields = ['created_at']
    date_hierarchy = 'amendment_date'


@admin.register(ContractRenewal)
class ContractRenewalAdmin(admin.ModelAdmin):
    list_display = ['original_contract', 'status', 'proposed_start_date', 'requested_by', 'requested_at']
    list_filter = ['status', 'requested_at']
    search_fields = ['original_contract__contract_number', 'original_contract__employee__first_name', 'original_contract__employee__last_name']
    readonly_fields = ['requested_at', 'reviewed_at']
    date_hierarchy = 'requested_at'


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'contract_type', 'company', 'is_active', 'created_at']
    list_filter = ['contract_type', 'is_active', 'company']
    search_fields = ['name', 'contract_type']
    readonly_fields = ['created_at', 'updated_at']
