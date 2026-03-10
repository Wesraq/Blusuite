"""
Advanced Reporting & Analytics for BluSuite
Comprehensive business intelligence, metrics, and insights
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from datetime import datetime, timedelta, date
from decimal import Decimal


User = get_user_model()


class CompanyAnalytics(models.Model):
    """Company-wide analytics and KPIs"""
    
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='analytics_snapshots')
    snapshot_date = models.DateField(db_index=True)
    
    # Employee Metrics
    total_employees = models.IntegerField(default=0)
    active_employees = models.IntegerField(default=0)
    new_hires_this_month = models.IntegerField(default=0)
    terminations_this_month = models.IntegerField(default=0)
    turnover_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Attendance Metrics
    average_attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_absences = models.IntegerField(default=0)
    total_late_arrivals = models.IntegerField(default=0)
    
    # Leave Metrics
    total_leave_requests = models.IntegerField(default=0)
    approved_leaves = models.IntegerField(default=0)
    pending_leaves = models.IntegerField(default=0)
    total_leave_days_taken = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Payroll Metrics
    total_payroll_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_overtime_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_overtime_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Performance Metrics
    average_performance_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    pending_performance_reviews = models.IntegerField(default=0)
    completed_performance_reviews = models.IntegerField(default=0)
    
    # Training Metrics
    total_training_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employees_in_training = models.IntegerField(default=0)
    training_completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Document Metrics
    total_documents = models.IntegerField(default=0)
    pending_document_approvals = models.IntegerField(default=0)
    expired_documents = models.IntegerField(default=0)
    
    # Onboarding Metrics
    active_onboardings = models.IntegerField(default=0)
    completed_onboardings = models.IntegerField(default=0)
    average_onboarding_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # System Metrics
    total_storage_used_mb = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    active_users_last_30_days = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Company Analytics'
        verbose_name_plural = 'Company Analytics'
        unique_together = [('company', 'snapshot_date')]
        ordering = ['-snapshot_date']
        indexes = [
            models.Index(fields=['company', '-snapshot_date']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.snapshot_date}"


class AnalyticsReport(models.Model):
    """Generated analytics reports"""
    
    class ReportType(models.TextChoices):
        COMPANY_OVERVIEW = 'COMPANY_OVERVIEW', 'Company Overview'
        HR_METRICS = 'HR_METRICS', 'HR Metrics'
        PAYROLL_SUMMARY = 'PAYROLL_SUMMARY', 'Payroll Summary'
        ATTENDANCE_REPORT = 'ATTENDANCE_REPORT', 'Attendance Report'
        LEAVE_ANALYSIS = 'LEAVE_ANALYSIS', 'Leave Analysis'
        PERFORMANCE_REVIEW = 'PERFORMANCE_REVIEW', 'Performance Review'
        TRAINING_REPORT = 'TRAINING_REPORT', 'Training Report'
        TURNOVER_ANALYSIS = 'TURNOVER_ANALYSIS', 'Turnover Analysis'
        CUSTOM = 'CUSTOM', 'Custom Report'
    
    class Format(models.TextChoices):
        PDF = 'PDF', 'PDF'
        EXCEL = 'EXCEL', 'Excel'
        CSV = 'CSV', 'CSV'
        JSON = 'JSON', 'JSON'
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        GENERATING = 'GENERATING', 'Generating'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
    
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='analytics_reports')
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Date Range
    date_from = models.DateField()
    date_to = models.DateField()
    
    # Filters
    filters_json = models.JSONField(default=dict, blank=True)
    
    # Output
    format = models.CharField(max_length=10, choices=Format.choices, default=Format.PDF)
    file_path = models.CharField(max_length=500, blank=True)
    file_size_kb = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    
    # Execution
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_reports')
    generated_at = models.DateTimeField(null=True, blank=True)
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(max_length=20, blank=True)  # DAILY, WEEKLY, MONTHLY
    next_run_date = models.DateTimeField(null=True, blank=True)
    
    # Sharing
    recipients = models.ManyToManyField(User, related_name='received_reports', blank=True)
    email_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Analytics Report'
        verbose_name_plural = 'Analytics Reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', '-created_at']),
            models.Index(fields=['status', 'is_scheduled']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.company.name}"


class MetricTrend(models.Model):
    """Track metric trends over time"""
    
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='metric_trends')
    metric_name = models.CharField(max_length=100, db_index=True)
    metric_category = models.CharField(max_length=50)  # HR, PAYROLL, ATTENDANCE, etc.
    
    date = models.DateField(db_index=True)
    value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Trend Analysis
    previous_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    change_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    change_percentage = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Metric Trend'
        verbose_name_plural = 'Metric Trends'
        unique_together = [('company', 'metric_name', 'date')]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['company', 'metric_name', '-date']),
            models.Index(fields=['metric_category', '-date']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.metric_name} - {self.date}"


# ─────────────────────────────────────────────────────────────────────────────
# Analytics Calculation Functions
# ─────────────────────────────────────────────────────────────────────────────

def calculate_company_analytics(company, snapshot_date=None):
    """Calculate and store company-wide analytics"""
    if snapshot_date is None:
        snapshot_date = date.today()
    
    analytics, created = CompanyAnalytics.objects.get_or_create(
        company=company,
        snapshot_date=snapshot_date
    )
    
    # Employee Metrics
    employees = User.objects.filter(company=company, role='EMPLOYEE')
    analytics.total_employees = employees.count()
    analytics.active_employees = employees.filter(is_active=True).count()
    
    # New hires this month
    month_start = snapshot_date.replace(day=1)
    analytics.new_hires_this_month = employees.filter(
        date_hired__gte=month_start,
        date_hired__lte=snapshot_date
    ).count()
    
    # Terminations this month
    analytics.terminations_this_month = employees.filter(
        termination_date__gte=month_start,
        termination_date__lte=snapshot_date
    ).count()
    
    # Turnover rate (annual)
    if analytics.total_employees > 0:
        year_start = snapshot_date.replace(month=1, day=1)
        year_terminations = employees.filter(
            termination_date__gte=year_start,
            termination_date__lte=snapshot_date
        ).count()
        analytics.turnover_rate = (year_terminations / analytics.total_employees) * 100
    
    # Attendance Metrics
    try:
        from blu_staff.apps.attendance.models import Attendance
        
        month_attendance = Attendance.objects.filter(
            employee__company=company,
            date__gte=month_start,
            date__lte=snapshot_date
        )
        
        total_days = month_attendance.count()
        present_days = month_attendance.filter(status='PRESENT').count()
        
        if total_days > 0:
            analytics.average_attendance_rate = (present_days / total_days) * 100
        
        analytics.total_absences = month_attendance.filter(status='ABSENT').count()
        analytics.total_late_arrivals = month_attendance.filter(is_late=True).count()
    except Exception:
        pass
    
    # Leave Metrics
    try:
        from blu_staff.apps.leave.models import LeaveRequest
        
        month_leaves = LeaveRequest.objects.filter(
            employee__company=company,
            start_date__gte=month_start,
            start_date__lte=snapshot_date
        )
        
        analytics.total_leave_requests = month_leaves.count()
        analytics.approved_leaves = month_leaves.filter(status='APPROVED').count()
        analytics.pending_leaves = month_leaves.filter(status='PENDING').count()
        analytics.total_leave_days_taken = month_leaves.filter(
            status='APPROVED'
        ).aggregate(total=Sum('total_days'))['total'] or 0
    except Exception:
        pass
    
    # Payroll Metrics
    try:
        from blu_staff.apps.payroll.models import Payroll
        
        month_payrolls = Payroll.objects.filter(
            employee__company=company,
            pay_period_start__gte=month_start,
            pay_period_start__lte=snapshot_date
        )
        
        analytics.total_payroll_cost = month_payrolls.aggregate(
            total=Sum('net_pay')
        )['total'] or 0
        
        if analytics.active_employees > 0:
            analytics.average_salary = analytics.total_payroll_cost / analytics.active_employees
        
        analytics.total_overtime_hours = month_payrolls.aggregate(
            total=Sum('overtime_hours')
        )['total'] or 0
        
        analytics.total_overtime_cost = month_payrolls.aggregate(
            total=Sum('overtime_pay')
        )['total'] or 0
    except Exception:
        pass
    
    # Performance Metrics
    try:
        from blu_staff.apps.performance.models import PerformanceReview
        
        reviews = PerformanceReview.objects.filter(
            employee__company=company,
            review_period_end__gte=month_start,
            review_period_end__lte=snapshot_date
        )
        
        analytics.completed_performance_reviews = reviews.filter(status='COMPLETED').count()
        analytics.pending_performance_reviews = reviews.filter(status='PENDING').count()
        
        avg_score = reviews.filter(status='COMPLETED').aggregate(
            avg=Avg('overall_rating')
        )['avg']
        
        if avg_score:
            analytics.average_performance_score = avg_score
    except Exception:
        pass
    
    # Training Metrics
    try:
        from blu_staff.apps.training.models import TrainingEnrollment
        
        enrollments = TrainingEnrollment.objects.filter(
            employee__company=company,
            enrolled_date__gte=month_start,
            enrolled_date__lte=snapshot_date
        )
        
        analytics.employees_in_training = enrollments.values('employee').distinct().count()
        
        total_enrollments = enrollments.count()
        completed = enrollments.filter(status='COMPLETED').count()
        
        if total_enrollments > 0:
            analytics.training_completion_rate = (completed / total_enrollments) * 100
        
        analytics.total_training_hours = enrollments.filter(
            status='COMPLETED'
        ).aggregate(total=Sum('course__duration_hours'))['total'] or 0
    except Exception:
        pass
    
    # Document Metrics
    try:
        from blu_staff.apps.documents.models import EmployeeDocument
        
        docs = EmployeeDocument.objects.filter(employee__company=company)
        
        analytics.total_documents = docs.count()
        analytics.pending_document_approvals = docs.filter(status='PENDING').count()
        analytics.expired_documents = docs.filter(
            expiry_date__lt=snapshot_date,
            status='APPROVED'
        ).count()
    except Exception:
        pass
    
    # Onboarding Metrics
    try:
        from blu_staff.apps.onboarding.models import EmployeeOnboarding
        
        onboardings = EmployeeOnboarding.objects.filter(
            employee__company=company
        )
        
        analytics.active_onboardings = onboardings.filter(status='IN_PROGRESS').count()
        analytics.completed_onboardings = onboardings.filter(status='COMPLETED').count()
        
        completed = onboardings.filter(
            status='COMPLETED',
            actual_completion_date__isnull=False
        )
        
        if completed.exists():
            avg_days = completed.annotate(
                days=F('actual_completion_date') - F('start_date')
            ).aggregate(avg=Avg('days'))['avg']
            
            if avg_days:
                analytics.average_onboarding_days = avg_days.days
    except Exception:
        pass
    
    # Storage Metrics
    try:
        from blu_staff.apps.documents.models import EmployeeDocument
        
        total_size = EmployeeDocument.objects.filter(
            employee__company=company
        ).aggregate(total=Sum('file_size'))['total'] or 0
        
        analytics.total_storage_used_mb = total_size / (1024 * 1024)
    except Exception:
        pass
    
    # Active Users
    try:
        thirty_days_ago = snapshot_date - timedelta(days=30)
        analytics.active_users_last_30_days = User.objects.filter(
            company=company,
            last_login__gte=thirty_days_ago
        ).count()
    except Exception:
        pass
    
    analytics.save()
    
    return analytics


def track_metric_trend(company, metric_name, metric_category, value, date=None):
    """Track a metric trend over time"""
    if date is None:
        date = timezone.now().date()
    
    # Get previous value
    previous = MetricTrend.objects.filter(
        company=company,
        metric_name=metric_name,
        date__lt=date
    ).order_by('-date').first()
    
    trend = MetricTrend.objects.create(
        company=company,
        metric_name=metric_name,
        metric_category=metric_category,
        date=date,
        value=value
    )
    
    if previous:
        trend.previous_value = previous.value
        trend.change_amount = value - previous.value
        
        if previous.value != 0:
            trend.change_percentage = ((value - previous.value) / previous.value) * 100
        
        trend.save()
    
    return trend


def get_metric_trends(company, metric_name, days=30):
    """Get metric trends for the last N days"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    trends = MetricTrend.objects.filter(
        company=company,
        metric_name=metric_name,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    return list(trends.values('date', 'value', 'change_percentage'))


def generate_company_overview_report(company, date_from, date_to):
    """Generate comprehensive company overview report"""
    report_data = {
        'company': company.name,
        'period': f"{date_from} to {date_to}",
        'generated_at': timezone.now().isoformat(),
    }
    
    # Get analytics snapshots for period
    snapshots = CompanyAnalytics.objects.filter(
        company=company,
        snapshot_date__gte=date_from,
        snapshot_date__lte=date_to
    ).order_by('snapshot_date')
    
    if snapshots.exists():
        latest = snapshots.last()
        first = snapshots.first()
        
        report_data['summary'] = {
            'total_employees': latest.total_employees,
            'active_employees': latest.active_employees,
            'turnover_rate': float(latest.turnover_rate),
            'attendance_rate': float(latest.average_attendance_rate),
            'total_payroll': float(latest.total_payroll_cost),
            'average_salary': float(latest.average_salary),
        }
        
        # Calculate changes
        report_data['changes'] = {
            'employee_growth': latest.total_employees - first.total_employees,
            'new_hires': sum(s.new_hires_this_month for s in snapshots),
            'terminations': sum(s.terminations_this_month for s in snapshots),
        }
    
    return report_data


def calculate_predictive_metrics(company):
    """Calculate predictive analytics"""
    predictions = {}
    
    # Predict turnover
    recent_trends = MetricTrend.objects.filter(
        company=company,
        metric_name='turnover_rate',
        date__gte=date.today() - timedelta(days=90)
    ).order_by('date')
    
    if recent_trends.count() >= 3:
        values = [float(t.value) for t in recent_trends]
        # Simple linear regression
        avg_change = sum(values[i+1] - values[i] for i in range(len(values)-1)) / (len(values)-1)
        predictions['turnover_forecast_next_month'] = values[-1] + avg_change
    
    return predictions
