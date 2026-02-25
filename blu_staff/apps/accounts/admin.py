# flake8: noqa

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Company,
    CompanyAttendanceSettings,
    CompanyBiometricSettings,
    CompanyDepartment,
    CompanyEmailSettings,
    CompanyHoliday,
    CompanyPayGrade,
    CompanyPosition,
    CompanyRegistrationRequest,
    EmployeeIdConfiguration,
    EmployeeProfile,
    EmployerProfile,
    User,
    CompanyNotificationSettings,
    CompanyAPIKey,
    CompanyBranch,
    EnhancedDepartment,
)
from .integration_models import Integration, CompanyIntegration, IntegrationLog


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'email',
        'first_name',
        'last_name',
        'role',
        'is_active',
        'is_verified',
        'date_joined',
    )
    list_filter = ('role', 'is_active', 'is_verified', 'date_joined', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'employee_id',
        'job_title',
        'department',
        'date_hired',
        'salary',
        'pay_grade',
    )
    list_filter = ('department', 'job_title', 'pay_grade')
    search_fields = ('employee_id', 'user__email', 'user__first_name', 'user__last_name')


@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'company_phone', 'company_email')
    search_fields = ('company_name', 'user__email', 'user__first_name', 'user__last_name')


admin.site.register(Company)
admin.site.register(CompanyRegistrationRequest)
admin.site.register(EmployeeIdConfiguration)
admin.site.register(CompanyDepartment)
admin.site.register(CompanyPosition)
admin.site.register(CompanyPayGrade)
admin.site.register(CompanyEmailSettings)
admin.site.register(CompanyBiometricSettings)
admin.site.register(CompanyAttendanceSettings)
admin.site.register(CompanyHoliday)
admin.site.register(CompanyNotificationSettings)
admin.site.register(CompanyIntegration)
admin.site.register(CompanyAPIKey)
admin.site.register(Integration)
admin.site.register(IntegrationLog)


@admin.register(CompanyBranch)
class CompanyBranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company', 'city', 'manager', 'is_active', 'is_head_office')
    list_filter = ('is_active', 'is_head_office', 'city', 'country')
    search_fields = ('name', 'code', 'address', 'city')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Branch Information', {
            'fields': ('company', 'name', 'code', 'manager')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state_province', 'country', 'postal_code')
        }),
        ('Contact', {
            'fields': ('phone', 'email')
        }),
        ('Status', {
            'fields': ('is_active', 'is_head_office')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EnhancedDepartment)
class EnhancedDepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company', 'branch', 'head', 'get_employee_count', 'is_active')
    list_filter = ('is_active', 'company', 'branch')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Department Information', {
            'fields': ('company', 'branch', 'name', 'code', 'description')
        }),
        ('Management', {
            'fields': ('head', 'parent_department')
        }),
        ('Budget', {
            'fields': ('budget', 'currency')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
