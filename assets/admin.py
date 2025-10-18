from django.contrib import admin
from .models import AssetCategory, EmployeeAsset, AssetMaintenanceLog, AssetRequest


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(EmployeeAsset)
class EmployeeAssetAdmin(admin.ModelAdmin):
    list_display = ['asset_tag', 'name', 'asset_type', 'department', 'employee', 'status', 'condition', 'assigned_date']
    list_filter = ['asset_type', 'status', 'condition', 'department', 'assigned_date']
    search_fields = ['asset_tag', 'name', 'serial_number', 'employee__first_name', 'employee__last_name', 'department__name']
    readonly_fields = ['created_at', 'updated_at', 'days_with_employee', 'is_warranty_valid']
    ordering = ['-assigned_date', '-created_at']
    
    fieldsets = (
        ('Asset Information', {
            'fields': ('asset_type', 'asset_tag', 'name', 'description', 'category')
        }),
        ('Department & Location', {
            'fields': ('department', 'custodian', 'location')
        }),
        ('Details', {
            'fields': ('brand', 'model', 'serial_number', 'purchase_date', 'purchase_price', 'warranty_expiry')
        }),
        ('Assignment', {
            'fields': ('employee', 'status', 'condition', 'assigned_date', 'return_date', 'assigned_by')
        }),
        ('Additional Information', {
            'fields': ('notes', 'days_with_employee', 'is_warranty_valid')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AssetMaintenanceLog)
class AssetMaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ['asset', 'maintenance_type', 'performed_date', 'cost', 'performed_by']
    list_filter = ['maintenance_type', 'performed_date']
    search_fields = ['asset__asset_tag', 'asset__name', 'description', 'performed_by']
    ordering = ['-performed_date']
    
    fieldsets = (
        ('Maintenance Information', {
            'fields': ('asset', 'maintenance_type', 'performed_date', 'performed_by')
        }),
        ('Details', {
            'fields': ('description', 'cost', 'notes')
        }),
        ('System Information', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AssetRequest)
class AssetRequestAdmin(admin.ModelAdmin):
    list_display = ['department', 'asset_name', 'quantity', 'priority', 'status', 'requested_by', 'created_at']
    list_filter = ['status', 'priority', 'department', 'created_at']
    search_fields = ['asset_name', 'description', 'department__name', 'requested_by__first_name', 'requested_by__last_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('department', 'requested_by', 'asset_type', 'asset_name', 'quantity', 'priority')
        }),
        ('Details', {
            'fields': ('description', 'urgency_reason', 'estimated_cost')
        }),
        ('Approval', {
            'fields': ('status', 'approved_by', 'approval_date', 'rejection_reason', 'admin_notes')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
