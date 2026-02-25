from django.contrib import admin
from .models import ProjectAnalytics, TeamMemberAnalytics, CustomReport, ReportExecution, Dashboard


@admin.register(ProjectAnalytics)
class ProjectAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['project', 'completion_rate', 'total_hours_logged', 'sla_compliance_rate', 'last_calculated']
    list_filter = ['last_calculated']
    search_fields = ['project__name']
    readonly_fields = ['last_calculated', 'created_at']
    
    fieldsets = (
        ('Project', {
            'fields': ('project',)
        }),
        ('Time Metrics', {
            'fields': ('total_hours_logged', 'billable_hours', 'non_billable_hours')
        }),
        ('Task Metrics', {
            'fields': ('total_tasks', 'completed_tasks', 'overdue_tasks', 'in_progress_tasks')
        }),
        ('Financial Metrics', {
            'fields': ('total_budget', 'total_cost', 'budget_variance')
        }),
        ('Performance Metrics', {
            'fields': ('completion_rate', 'on_time_delivery_rate', 'average_task_completion_days')
        }),
        ('Team Metrics', {
            'fields': ('team_size', 'active_team_members')
        }),
        ('Client Metrics', {
            'fields': ('client_satisfaction_score', 'total_issues_reported', 'resolved_issues', 'sla_compliance_rate')
        }),
        ('Timestamps', {
            'fields': ('last_calculated', 'created_at')
        }),
    )


@admin.register(TeamMemberAnalytics)
class TeamMemberAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['user', 'project', 'completion_rate', 'total_hours_logged', 'period_start', 'period_end']
    list_filter = ['period_start', 'period_end', 'project']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'project__name']
    readonly_fields = ['last_calculated']


@admin.register(CustomReport)
class CustomReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'frequency', 'is_scheduled', 'is_active', 'created_by', 'created_at']
    list_filter = ['report_type', 'frequency', 'is_scheduled', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['projects', 'recipients']


@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = ['report', 'status', 'executed_by', 'started_at', 'completed_at']
    list_filter = ['status', 'started_at', 'completed_at']
    search_fields = ['report__name']
    readonly_fields = ['created_at']


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_public', 'is_default', 'created_at']
    list_filter = ['is_public', 'is_default', 'created_at']
    search_fields = ['name', 'description', 'owner__email']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['shared_with']
