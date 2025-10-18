from django.contrib import admin
from .models import TrainingProgram, TrainingEnrollment, Certification, TrainingRequest


@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ['title', 'program_type', 'department', 'duration_hours', 'is_mandatory', 'is_active', 'created_by']
    list_filter = ['program_type', 'is_mandatory', 'is_active', 'department']
    search_fields = ['title', 'description', 'provider', 'instructor']
    ordering = ['title']
    
    fieldsets = (
        ('Program Information', {
            'fields': ('title', 'description', 'program_type', 'duration_hours')
        }),
        ('Department & Access', {
            'fields': ('department', 'created_by', 'requires_approval')
        }),
        ('Details', {
            'fields': ('is_mandatory', 'cost', 'provider', 'instructor')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(TrainingEnrollment)
class TrainingEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['employee', 'program', 'status', 'enrollment_date', 'completion_date', 'score']
    list_filter = ['status', 'enrollment_date']
    search_fields = ['employee__first_name', 'employee__last_name', 'program__title']
    ordering = ['-enrollment_date']
    
    fieldsets = (
        ('Enrollment Information', {
            'fields': ('employee', 'program', 'enrollment_date', 'status')
        }),
        ('Progress', {
            'fields': ('start_date', 'completion_date', 'score')
        }),
        ('Feedback', {
            'fields': ('feedback', 'certificate_url', 'notes')
        }),
    )


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'name', 'issuing_organization', 'issue_date', 'expiry_date', 'status']
    list_filter = ['status', 'issue_date']
    search_fields = ['employee__first_name', 'employee__last_name', 'name', 'issuing_organization']
    ordering = ['-issue_date']
    
    fieldsets = (
        ('Certification Information', {
            'fields': ('employee', 'name', 'issuing_organization')
        }),
        ('Dates', {
            'fields': ('issue_date', 'expiry_date', 'status')
        }),
        ('Credentials', {
            'fields': ('credential_id', 'credential_url')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
    )


@admin.register(TrainingRequest)
class TrainingRequestAdmin(admin.ModelAdmin):
    list_display = ['department', 'training_title', 'target_employees', 'priority', 'status', 'requested_by', 'created_at']
    list_filter = ['status', 'priority', 'program_type', 'department', 'created_at']
    search_fields = ['training_title', 'description', 'department__name', 'requested_by__first_name', 'requested_by__last_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('department', 'requested_by', 'training_title', 'program_type', 'target_employees', 'priority')
        }),
        ('Training Details', {
            'fields': ('description', 'duration_hours', 'estimated_cost', 'preferred_provider')
        }),
        ('Justification', {
            'fields': ('business_justification', 'urgency_reason')
        }),
        ('Approval', {
            'fields': ('status', 'approved_by', 'approval_date', 'rejection_reason', 'admin_notes', 'created_training')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
