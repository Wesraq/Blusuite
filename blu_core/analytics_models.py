"""
BLU Analytics - Advanced Analytics Models
Custom dashboards, KPIs, and data visualization
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()


class Dashboard(models.Model):
    """Custom analytics dashboards"""
    VISIBILITY_CHOICES = [
        ('PRIVATE', 'Private'),
        ('TEAM', 'Team'),
        ('COMPANY', 'Company-wide'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='dashboards')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_dashboards')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='PRIVATE')
    
    # Layout configuration (JSON)
    layout_config = models.JSONField(default=dict, blank=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.company.name}"


class Widget(models.Model):
    """Dashboard widgets"""
    WIDGET_TYPES = [
        ('CHART_LINE', 'Line Chart'),
        ('CHART_BAR', 'Bar Chart'),
        ('CHART_PIE', 'Pie Chart'),
        ('CHART_DOUGHNUT', 'Doughnut Chart'),
        ('CHART_AREA', 'Area Chart'),
        ('METRIC_CARD', 'Metric Card'),
        ('TABLE', 'Data Table'),
        ('GAUGE', 'Gauge'),
        ('HEATMAP', 'Heatmap'),
        ('TIMELINE', 'Timeline'),
    ]
    
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='widgets')
    
    title = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=30, choices=WIDGET_TYPES)
    
    # Data source configuration
    data_source = models.CharField(max_length=100)  # e.g., 'projects', 'employees', 'attendance'
    query_config = models.JSONField(default=dict)  # Filters, aggregations, etc.
    
    # Display configuration
    display_config = models.JSONField(default=dict)  # Colors, labels, etc.
    
    # Position and size
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)
    width = models.IntegerField(default=4)  # Grid units
    height = models.IntegerField(default=3)  # Grid units
    
    refresh_interval = models.IntegerField(default=300)  # Seconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['position_y', 'position_x']
    
    def __str__(self):
        return f"{self.title} ({self.get_widget_type_display()})"


class KPI(models.Model):
    """Key Performance Indicators"""
    CATEGORY_CHOICES = [
        ('FINANCIAL', 'Financial'),
        ('OPERATIONAL', 'Operational'),
        ('HR', 'Human Resources'),
        ('SALES', 'Sales'),
        ('CUSTOMER', 'Customer'),
        ('PROJECT', 'Project'),
        ('CUSTOM', 'Custom'),
    ]
    
    TREND_CHOICES = [
        ('UP', 'Increasing'),
        ('DOWN', 'Decreasing'),
        ('STABLE', 'Stable'),
    ]
    
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='kpis')
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    
    # Current value
    current_value = models.DecimalField(max_digits=15, decimal_places=2)
    target_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=20, blank=True)  # %, $, units, etc.
    
    # Trend
    trend = models.CharField(max_length=10, choices=TREND_CHOICES, default='STABLE')
    change_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Calculation
    calculation_method = models.CharField(max_length=100)  # Python path or SQL query
    
    last_calculated = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'KPI'
        verbose_name_plural = 'KPIs'
    
    def __str__(self):
        return f"{self.name}: {self.current_value}{self.unit}"
    
    def achievement_percentage(self):
        """Calculate % of target achieved"""
        if self.target_value:
            return (float(self.current_value) / float(self.target_value)) * 100
        return 0


class Report(models.Model):
    """Saved reports"""
    REPORT_TYPES = [
        ('EMPLOYEE_ROSTER', 'Employee Roster'),
        ('ATTENDANCE_SUMMARY', 'Attendance Summary'),
        ('LEAVE_REPORT', 'Leave Report'),
        ('PAYROLL_REPORT', 'Payroll Report'),
        ('PROJECT_STATUS', 'Project Status'),
        ('TIME_TRACKING', 'Time Tracking'),
        ('PERFORMANCE_REVIEW', 'Performance Review'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    FORMAT_CHOICES = [
        ('PDF', 'PDF'),
        ('EXCEL', 'Excel'),
        ('CSV', 'CSV'),
        ('JSON', 'JSON'),
    ]
    
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='reports')
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    
    # Report configuration
    filters = models.JSONField(default=dict)
    columns = models.JSONField(default=list)
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(max_length=20, blank=True)  # daily, weekly, monthly
    schedule_day = models.IntegerField(null=True, blank=True)
    schedule_time = models.TimeField(null=True, blank=True)
    
    # Recipients
    recipients = models.ManyToManyField(User, related_name='scheduled_reports', blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"


class ReportExecution(models.Model):
    """Report execution history"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='executions')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    format = models.CharField(max_length=10, choices=Report.FORMAT_CHOICES)
    
    file_path = models.FileField(upload_to='reports/%Y/%m/', null=True, blank=True)
    file_size = models.IntegerField(default=0)
    
    rows_generated = models.IntegerField(default=0)
    execution_time = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # seconds
    
    error_message = models.TextField(blank=True)
    
    executed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    executed_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-executed_at']
    
    def __str__(self):
        return f"{self.report.name} - {self.executed_at.strftime('%Y-%m-%d %H:%M')}"


class DataExport(models.Model):
    """Data export requests"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='data_exports')
    
    export_type = models.CharField(max_length=100)
    filters = models.JSONField(default=dict)
    format = models.CharField(max_length=10)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    file_path = models.FileField(upload_to='exports/%Y/%m/', null=True, blank=True)
    
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.export_type} - {self.requested_at.strftime('%Y-%m-%d')}"
