"""
BLU Projects - Admin Configuration
"""
from django.contrib import admin
from .models import (
    Project, ProjectMilestone, Task, TimeEntry,
    TaskComment, ProjectDocument, ProjectActivity,
    ProjectSLA, ClientIssue, IssueComment, IssueAttachment, ClientAccess
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'company', 'status', 'priority', 'progress_percentage', 'start_date', 'end_date']
    list_filter = ['status', 'priority', 'company', 'created_at']
    search_fields = ['code', 'name', 'description', 'client_name']
    filter_horizontal = ['team_members']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'company')
        }),
        ('Project Details', {
            'fields': ('status', 'priority', 'progress_percentage')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'actual_start_date', 'actual_end_date')
        }),
        ('Budget', {
            'fields': ('budget', 'actual_cost')
        }),
        ('Team', {
            'fields': ('project_manager', 'team_members')
        }),
        ('Client', {
            'fields': ('client_name', 'client_contact', 'client_email')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'status', 'due_date', 'completion_date', 'order']
    list_filter = ['status', 'project']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'status', 'priority', 'assigned_to', 'due_date']
    list_filter = ['status', 'priority', 'project']
    search_fields = ['title', 'description']
    filter_horizontal = ['depends_on']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'milestone', 'title', 'description')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority')
        }),
        ('Assignment', {
            'fields': ('assigned_to',)
        }),
        ('Dates', {
            'fields': ('start_date', 'due_date', 'completed_date')
        }),
        ('Effort', {
            'fields': ('estimated_hours', 'actual_hours')
        }),
        ('Dependencies', {
            'fields': ('depends_on',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['task', 'user', 'date', 'hours', 'is_billable', 'hourly_rate']
    list_filter = ['is_billable', 'date', 'user']
    search_fields = ['task__title', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ['task', 'user', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['comment', 'task__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'category', 'uploaded_by', 'uploaded_at']
    list_filter = ['category', 'uploaded_at', 'project']
    search_fields = ['title', 'description']
    readonly_fields = ['uploaded_at', 'file_size']


@admin.register(ProjectActivity)
class ProjectActivityAdmin(admin.ModelAdmin):
    list_display = ['project', 'action', 'user', 'created_at']
    list_filter = ['action', 'created_at', 'project']
    search_fields = ['description']
    readonly_fields = ['created_at']


# ============================================================================
# CLIENT PORTAL ADMIN
# ============================================================================

@admin.register(ProjectSLA)
class ProjectSLAAdmin(admin.ModelAdmin):
    list_display = ['project', 'critical_response_time', 'maintenance_start_date', 'maintenance_end_date']
    list_filter = ['project']
    search_fields = ['project__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Response Times (hours)', {
            'fields': ('critical_response_time', 'high_response_time', 'medium_response_time', 'low_response_time')
        }),
        ('Resolution Times (hours)', {
            'fields': ('critical_resolution_time', 'high_resolution_time', 'medium_resolution_time', 'low_resolution_time')
        }),
        ('Support Contact', {
            'fields': ('support_hours', 'support_email', 'support_phone')
        }),
        ('Maintenance Period', {
            'fields': ('maintenance_start_date', 'maintenance_end_date', 'maintenance_terms')
        }),
    )


@admin.register(ClientIssue)
class ClientIssueAdmin(admin.ModelAdmin):
    list_display = ['issue_number', 'title', 'project', 'status', 'priority', 'reported_by', 'reported_at', 'response_sla_breached', 'resolution_sla_breached']
    list_filter = ['status', 'priority', 'category', 'response_sla_breached', 'resolution_sla_breached', 'is_maintenance_issue']
    search_fields = ['issue_number', 'title', 'description']
    readonly_fields = ['issue_number', 'reported_at', 'acknowledged_at', 'resolved_at', 'closed_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'issue_number', 'title', 'description')
        }),
        ('Classification', {
            'fields': ('status', 'priority', 'category')
        }),
        ('Assignment', {
            'fields': ('reported_by', 'assigned_to')
        }),
        ('SLA Tracking', {
            'fields': ('reported_at', 'acknowledged_at', 'resolved_at', 'closed_at', 'response_sla_breached', 'resolution_sla_breached')
        }),
        ('Additional', {
            'fields': ('is_maintenance_issue', 'attachments_count')
        }),
    )


@admin.register(IssueComment)
class IssueCommentAdmin(admin.ModelAdmin):
    list_display = ['issue', 'user', 'is_internal', 'is_resolution', 'created_at']
    list_filter = ['is_internal', 'is_resolution', 'created_at']
    search_fields = ['comment', 'issue__issue_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(IssueAttachment)
class IssueAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'issue', 'uploaded_by', 'file_size', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['filename', 'issue__issue_number']
    readonly_fields = ['uploaded_at', 'file_size']


@admin.register(ClientAccess)
class ClientAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'project', 'access_level', 'can_view_internal_notes', 'granted_at']
    list_filter = ['access_level', 'can_view_internal_notes', 'granted_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'project__name']
    readonly_fields = ['granted_at']
