"""
Operational Muscles - Frontend Views
Access all operational muscle models from the main interface
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta, date

from .models import (
    AuditLog, SystemMetric, HealthCheckResult, AlertRule, Alert,
    MFAMethod, BackupCode, MFAChallenge,
    SystemSetting, CompanySettingOverride, SettingsVersion, SettingsTemplate,
    CompanyOnboarding, OnboardingReminder,
    CompanyAnalytics, AnalyticsReport, MetricTrend
)
from .rbac import require_role


# ─────────────────────────────────────────────────────────────────────────────
# Audit & Security Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_role(['ADMINISTRATOR', 'EMPLOYER_ADMIN'])
def audit_logs_view(request):
    """View audit logs with filtering"""
    logs = AuditLog.objects.filter(company=request.user.company).order_by('-timestamp')
    
    # Filtering
    action_filter = request.GET.get('action')
    model_filter = request.GET.get('model')
    user_filter = request.GET.get('user')
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    if model_filter:
        logs = logs.filter(model_name=model_filter)
    if user_filter:
        logs = logs.filter(user_email__icontains=user_filter)
    
    # Pagination
    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    logs_page = paginator.get_page(page)
    
    # Get unique values for filters
    actions = AuditLog.objects.filter(company=request.user.company).values_list('action', flat=True).distinct()
    models = AuditLog.objects.filter(company=request.user.company).values_list('model_name', flat=True).distinct()
    
    context = {
        'logs': logs_page,
        'actions': actions,
        'models': models,
        'total_logs': logs.count(),
    }
    
    return render(request, 'blu_core/audit_logs.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# System Monitoring Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_role(['ADMINISTRATOR'])
def system_monitoring_view(request):
    """System monitoring dashboard"""
    # Get latest metrics
    latest_metrics = SystemMetric.objects.order_by('-timestamp')[:100]
    
    # Get latest health checks
    latest_health = HealthCheckResult.objects.order_by('-timestamp')[:20]
    
    # Get active alerts
    active_alerts = Alert.objects.filter(
        status='ACTIVE'
    ).order_by('-triggered_at')[:10]
    
    # Get alert rules
    alert_rules = AlertRule.objects.filter(is_active=True)
    
    # Calculate averages
    recent_metrics = SystemMetric.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=1)
    )
    
    avg_cpu = recent_metrics.aggregate(avg=Avg('cpu_percent'))['avg'] or 0
    avg_memory = recent_metrics.aggregate(avg=Avg('memory_percent'))['avg'] or 0
    avg_disk = recent_metrics.aggregate(avg=Avg('disk_percent'))['avg'] or 0
    
    context = {
        'latest_metrics': latest_metrics[:10],
        'latest_health': latest_health,
        'active_alerts': active_alerts,
        'alert_rules': alert_rules,
        'avg_cpu': round(avg_cpu, 2),
        'avg_memory': round(avg_memory, 2),
        'avg_disk': round(avg_disk, 2),
        'total_alerts': active_alerts.count(),
    }
    
    return render(request, 'blu_core/system_monitoring.html', context)


@login_required
@require_role(['ADMINISTRATOR'])
def alerts_view(request):
    """View all alerts"""
    alerts = Alert.objects.all().order_by('-triggered_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        alerts = alerts.filter(status=status_filter)
    
    paginator = Paginator(alerts, 50)
    page = request.GET.get('page', 1)
    alerts_page = paginator.get_page(page)
    
    context = {
        'alerts': alerts_page,
        'active_count': Alert.objects.filter(status='ACTIVE').count(),
        'acknowledged_count': Alert.objects.filter(status='ACKNOWLEDGED').count(),
        'resolved_count': Alert.objects.filter(status='RESOLVED').count(),
    }
    
    return render(request, 'blu_core/alerts.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# MFA Management Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def mfa_settings_view(request):
    """User's MFA settings"""
    mfa_methods = MFAMethod.objects.filter(user=request.user, is_active=True)
    backup_codes = BackupCode.objects.filter(user=request.user, is_used=False)
    recent_challenges = MFAChallenge.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    context = {
        'mfa_methods': mfa_methods,
        'backup_codes': backup_codes,
        'recent_challenges': recent_challenges,
        'has_mfa': mfa_methods.exists(),
    }
    
    return render(request, 'blu_core/mfa_settings.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Settings Management Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_role(['ADMINISTRATOR', 'EMPLOYER_ADMIN'])
def settings_management_view(request):
    """Company settings management"""
    # Get system settings
    system_settings = SystemSetting.objects.all().order_by('category', 'key')
    
    # Get company overrides
    company_overrides = CompanySettingOverride.objects.filter(
        company=request.user.company
    ).order_by('setting__category', 'setting__key')
    
    # Get settings versions
    versions = SettingsVersion.objects.filter(
        company=request.user.company
    ).order_by('-created_at')[:10]
    
    # Get available templates
    templates = SettingsTemplate.objects.filter(is_active=True)
    
    # Group settings by category
    settings_by_category = {}
    for setting in system_settings:
        if setting.category not in settings_by_category:
            settings_by_category[setting.category] = []
        
        # Check if company has override
        override = company_overrides.filter(setting=setting).first()
        settings_by_category[setting.category].append({
            'setting': setting,
            'override': override,
            'effective_value': override.value if override else setting.default_value,
        })
    
    context = {
        'settings_by_category': settings_by_category,
        'versions': versions,
        'templates': templates,
        'total_settings': system_settings.count(),
        'total_overrides': company_overrides.count(),
    }
    
    return render(request, 'blu_core/settings_management.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding Management Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_role(['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'HR_MANAGER'])
def onboarding_dashboard_view(request):
    """Company onboarding dashboard"""
    # Get company onboarding
    company_onboarding = CompanyOnboarding.objects.filter(
        company=request.user.company
    ).first()
    
    # Get onboarding reminders
    reminders = OnboardingReminder.objects.filter(
        company_onboarding__company=request.user.company
    ).order_by('-created_at')[:20]
    
    # Get employee onboardings
    from blu_staff.apps.onboarding.models import EmployeeOnboarding
    employee_onboardings = EmployeeOnboarding.objects.filter(
        tenant__company=request.user.company
    ).order_by('-start_date')[:10]
    
    context = {
        'company_onboarding': company_onboarding,
        'reminders': reminders,
        'employee_onboardings': employee_onboardings,
        'active_onboardings': employee_onboardings.filter(status='IN_PROGRESS').count(),
        'completed_onboardings': employee_onboardings.filter(status='COMPLETED').count(),
    }
    
    return render(request, 'blu_core/onboarding_dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics & Reporting Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_role(['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'HR_MANAGER'])
def analytics_dashboard_view(request):
    """Company analytics dashboard"""
    # Get latest analytics snapshot
    latest_analytics = CompanyAnalytics.objects.filter(
        company=request.user.company
    ).order_by('-snapshot_date').first()
    
    # Get recent analytics (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    recent_analytics = CompanyAnalytics.objects.filter(
        company=request.user.company,
        snapshot_date__gte=thirty_days_ago
    ).order_by('snapshot_date')
    
    # Get recent reports
    recent_reports = AnalyticsReport.objects.filter(
        company=request.user.company
    ).order_by('-created_at')[:10]
    
    # Get key metric trends
    employee_trends = MetricTrend.objects.filter(
        company=request.user.company,
        metric_name='employee_count',
        date__gte=thirty_days_ago
    ).order_by('date')
    
    turnover_trends = MetricTrend.objects.filter(
        company=request.user.company,
        metric_name='turnover_rate',
        date__gte=thirty_days_ago
    ).order_by('date')
    
    context = {
        'latest_analytics': latest_analytics,
        'recent_analytics': recent_analytics,
        'recent_reports': recent_reports,
        'employee_trends': list(employee_trends.values('date', 'value', 'change_percentage')),
        'turnover_trends': list(turnover_trends.values('date', 'value', 'change_percentage')),
        'has_data': latest_analytics is not None,
    }
    
    return render(request, 'blu_core/analytics_dashboard.html', context)


@login_required
@require_role(['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'HR_MANAGER'])
def reports_view(request):
    """View all analytics reports"""
    reports = AnalyticsReport.objects.filter(
        company=request.user.company
    ).order_by('-created_at')
    
    # Filter by type
    report_type = request.GET.get('type')
    if report_type:
        reports = reports.filter(report_type=report_type)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        reports = reports.filter(status=status)
    
    paginator = Paginator(reports, 20)
    page = request.GET.get('page', 1)
    reports_page = paginator.get_page(page)
    
    context = {
        'reports': reports_page,
        'report_types': AnalyticsReport.ReportType.choices,
        'total_reports': reports.count(),
        'completed_reports': reports.filter(status='COMPLETED').count(),
    }
    
    return render(request, 'blu_core/reports.html', context)


@login_required
@require_role(['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'HR_MANAGER'])
def metric_trends_view(request):
    """View metric trends"""
    # Get available metrics
    metrics = MetricTrend.objects.filter(
        company=request.user.company
    ).values('metric_name', 'metric_category').distinct()
    
    # Selected metric
    selected_metric = request.GET.get('metric', 'employee_count')
    days = int(request.GET.get('days', 30))
    
    # Get trend data
    start_date = date.today() - timedelta(days=days)
    trends = MetricTrend.objects.filter(
        company=request.user.company,
        metric_name=selected_metric,
        date__gte=start_date
    ).order_by('date')
    
    context = {
        'metrics': metrics,
        'selected_metric': selected_metric,
        'trends': trends,
        'days': days,
        'trend_data': list(trends.values('date', 'value', 'change_percentage')),
    }
    
    return render(request, 'blu_core/metric_trends.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Operational Muscles Overview
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_role(['ADMINISTRATOR', 'EMPLOYER_ADMIN'])
def operational_overview_view(request):
    """Overview of all operational muscles"""
    context = {
        # Audit & Security
        'total_audit_logs': AuditLog.objects.filter(company=request.user.company).count(),
        'recent_audit_logs': AuditLog.objects.filter(company=request.user.company).order_by('-timestamp')[:5],
        
        # System Monitoring
        'active_alerts': Alert.objects.filter(status='ACTIVE').count(),
        'alert_rules': AlertRule.objects.filter(is_active=True).count(),
        
        # MFA
        'users_with_mfa': MFAMethod.objects.filter(is_active=True).values('user').distinct().count(),
        
        # Settings
        'system_settings': SystemSetting.objects.count(),
        'company_overrides': CompanySettingOverride.objects.filter(company=request.user.company).count(),
        
        # Onboarding
        'company_onboarding': CompanyOnboarding.objects.filter(company=request.user.company).first(),
        
        # Analytics
        'latest_analytics': CompanyAnalytics.objects.filter(company=request.user.company).order_by('-snapshot_date').first(),
        'total_reports': AnalyticsReport.objects.filter(company=request.user.company).count(),
    }
    
    return render(request, 'blu_core/operational_overview.html', context)
