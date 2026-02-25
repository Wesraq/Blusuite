from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from blu_projects.models import Project, Task
import json

User = get_user_model()


class ProjectAnalytics(models.Model):
    """Stores aggregated analytics data for projects"""
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='analytics')
    
    # Time Metrics
    total_hours_logged = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billable_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    non_billable_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Task Metrics
    total_tasks = models.IntegerField(default=0)
    completed_tasks = models.IntegerField(default=0)
    overdue_tasks = models.IntegerField(default=0)
    in_progress_tasks = models.IntegerField(default=0)
    
    # Financial Metrics
    total_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_variance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Performance Metrics
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Percentage
    on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    average_task_completion_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # Team Metrics
    team_size = models.IntegerField(default=0)
    active_team_members = models.IntegerField(default=0)
    
    # Client Metrics
    client_satisfaction_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    total_issues_reported = models.IntegerField(default=0)
    resolved_issues = models.IntegerField(default=0)
    sla_compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Timestamps
    last_calculated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Project Analytics'
        verbose_name_plural = 'Project Analytics'
    
    def __str__(self):
        return f"Analytics for {self.project.name}"
    
    def calculate_metrics(self):
        """Recalculate all metrics for this project"""
        from blu_projects.models import TimeEntry, ClientIssue
        from django.db.models import Sum, Count, Q, Avg
        from datetime import timedelta
        
        # Time Metrics
        time_entries = TimeEntry.objects.filter(project=self.project)
        self.total_hours_logged = time_entries.aggregate(total=Sum('hours'))['total'] or 0
        self.billable_hours = time_entries.filter(is_billable=True).aggregate(total=Sum('hours'))['total'] or 0
        self.non_billable_hours = self.total_hours_logged - self.billable_hours
        
        # Task Metrics
        tasks = Task.objects.filter(project=self.project)
        self.total_tasks = tasks.count()
        self.completed_tasks = tasks.filter(status='COMPLETED').count()
        self.in_progress_tasks = tasks.filter(status='IN_PROGRESS').count()
        self.overdue_tasks = tasks.filter(
            due_date__lt=timezone.now().date(),
            status__in=['TODO', 'IN_PROGRESS']
        ).count()
        
        # Completion Rate
        if self.total_tasks > 0:
            self.completion_rate = (self.completed_tasks / self.total_tasks) * 100
        
        # Financial Metrics
        self.total_budget = self.project.budget or 0
        self.total_cost = self.billable_hours * 100  # Assuming $100/hour rate
        self.budget_variance = self.total_budget - self.total_cost
        
        # Team Metrics
        self.team_size = self.project.team_members.count()
        self.active_team_members = time_entries.values('user').distinct().count()
        
        # Client Metrics
        issues = ClientIssue.objects.filter(project=self.project)
        self.total_issues_reported = issues.count()
        self.resolved_issues = issues.filter(status__in=['RESOLVED', 'CLOSED']).count()
        
        if self.total_issues_reported > 0:
            non_breached = issues.filter(
                response_sla_breached=False,
                resolution_sla_breached=False
            ).count()
            self.sla_compliance_rate = (non_breached / self.total_issues_reported) * 100
        
        self.save()


class TeamMemberAnalytics(models.Model):
    """Analytics for individual team members"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='team_analytics')
    
    # Productivity Metrics
    total_hours_logged = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billable_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tasks_assigned = models.IntegerField(default=0)
    tasks_completed = models.IntegerField(default=0)
    tasks_overdue = models.IntegerField(default=0)
    
    # Performance Metrics
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    average_task_completion_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    on_time_completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Quality Metrics
    issues_assigned = models.IntegerField(default=0)
    issues_resolved = models.IntegerField(default=0)
    average_resolution_time_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Timestamps
    period_start = models.DateField()
    period_end = models.DateField()
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Team Member Analytics'
        verbose_name_plural = 'Team Member Analytics'
        unique_together = ['user', 'project', 'period_start', 'period_end']
        indexes = [
            models.Index(fields=['user', 'project']),
            models.Index(fields=['period_start', 'period_end']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.project.name}"


class CustomReport(models.Model):
    """User-defined custom reports"""
    REPORT_TYPES = [
        ('PROJECT_SUMMARY', 'Project Summary'),
        ('TIME_TRACKING', 'Time Tracking'),
        ('FINANCIAL', 'Financial Report'),
        ('TEAM_PRODUCTIVITY', 'Team Productivity'),
        ('CLIENT_ISSUES', 'Client Issues'),
        ('SLA_COMPLIANCE', 'SLA Compliance'),
        ('CUSTOM', 'Custom Query'),
    ]
    
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
        ('ON_DEMAND', 'On Demand'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    
    # Filters
    projects = models.ManyToManyField(Project, blank=True)
    date_range_start = models.DateField(null=True, blank=True)
    date_range_end = models.DateField(null=True, blank=True)
    filters_json = models.TextField(blank=True)  # JSON string for custom filters
    
    # Scheduling
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='ON_DEMAND')
    is_scheduled = models.BooleanField(default=False)
    next_run_date = models.DateTimeField(null=True, blank=True)
    
    # Recipients
    recipients = models.ManyToManyField(User, related_name='subscribed_reports', blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_reports')
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Custom Report'
        verbose_name_plural = 'Custom Reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_filters(self):
        """Parse JSON filters"""
        if self.filters_json:
            try:
                return json.loads(self.filters_json)
            except:
                return {}
        return {}


class ReportExecution(models.Model):
    """Track report execution history"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    report = models.ForeignKey(CustomReport, on_delete=models.CASCADE, related_name='executions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Results
    result_data = models.TextField(blank=True)  # JSON string of results
    file_path = models.CharField(max_length=500, blank=True)  # Path to generated file
    
    # Execution Details
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    executed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Report Execution'
        verbose_name_plural = 'Report Executions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.report.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class Dashboard(models.Model):
    """Custom user dashboards"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Configuration
    layout_json = models.TextField()  # JSON string defining widget layout
    widgets_json = models.TextField()  # JSON string defining widgets and their configs
    
    # Sharing
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(User, related_name='shared_dashboards', blank=True)
    
    # Metadata
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboards')
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.owner.get_full_name()})"
