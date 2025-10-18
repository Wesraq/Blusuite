from django.contrib import admin
from .models import (
    RequestType,
    EmployeeRequest,
    RequestApproval,
    RequestComment,
    PettyCashRequest,
    AdvanceRequest,
    ReimbursementRequest
)


@admin.register(RequestType)
class RequestTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'requires_approval', 'approval_levels')
    list_filter = ('is_active', 'requires_approval')
    search_fields = ('name', 'code')


@admin.register(EmployeeRequest)
class EmployeeRequestAdmin(admin.ModelAdmin):
    list_display = ('request_number', 'request_type', 'employee', 'status', 'priority', 'created_at')
    list_filter = ('status', 'priority', 'request_type', 'created_at')
    search_fields = ('request_number', 'title', 'employee__first_name', 'employee__last_name')
    readonly_fields = ('request_number', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Request Information', {
            'fields': ('request_number', 'request_type', 'title', 'description')
        }),
        ('Employee Information', {
            'fields': ('employee', 'department')
        }),
        ('Financial Information', {
            'fields': ('amount', 'currency')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'current_approval_level')
        }),
        ('Dates', {
            'fields': ('request_date', 'required_by', 'completed_date')
        }),
        ('Attachments', {
            'fields': ('attachment',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RequestApproval)
class RequestApprovalAdmin(admin.ModelAdmin):
    list_display = ('request', 'approval_level', 'approver', 'action', 'assigned_date', 'action_date')
    list_filter = ('action', 'approval_level')
    search_fields = ('request__request_number', 'approver__first_name', 'approver__last_name')


@admin.register(RequestComment)
class RequestCommentAdmin(admin.ModelAdmin):
    list_display = ('request', 'user', 'is_internal', 'created_at')
    list_filter = ('is_internal', 'created_at')
    search_fields = ('request__request_number', 'user__first_name', 'user__last_name', 'comment')


@admin.register(PettyCashRequest)
class PettyCashRequestAdmin(admin.ModelAdmin):
    list_display = ('request', 'purpose', 'disbursed', 'receipt_submitted')
    list_filter = ('disbursed', 'receipt_submitted', 'payment_method')
    search_fields = ('request__request_number', 'purpose')


@admin.register(AdvanceRequest)
class AdvanceRequestAdmin(admin.ModelAdmin):
    list_display = ('request', 'approved_amount', 'installments', 'disbursed')
    list_filter = ('disbursed',)
    search_fields = ('request__request_number',)


@admin.register(ReimbursementRequest)
class ReimbursementRequestAdmin(admin.ModelAdmin):
    list_display = ('request', 'expense_date', 'expense_category', 'paid')
    list_filter = ('paid', 'expense_category')
    search_fields = ('request__request_number', 'vendor_name')
