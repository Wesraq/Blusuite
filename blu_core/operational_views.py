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
def audit_logs_view(request):
    """View audit logs with filtering"""
    # Superadmin sees all logs, others see only their company
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        logs = AuditLog.objects.all().order_by('-timestamp')
    elif hasattr(request.user, 'company') and request.user.company:
        logs = AuditLog.objects.filter(company=request.user.company).order_by('-timestamp')
    else:
        logs = AuditLog.objects.none()
    
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
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        actions = AuditLog.objects.values_list('action', flat=True).distinct()
        models = AuditLog.objects.values_list('model_name', flat=True).distinct()
    elif hasattr(request.user, 'company') and request.user.company:
        actions = AuditLog.objects.filter(company=request.user.company).values_list('action', flat=True).distinct()
        models = AuditLog.objects.filter(company=request.user.company).values_list('model_name', flat=True).distinct()
    else:
        actions = []
        models = []
    
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
def system_monitoring_view(request):
    """System monitoring dashboard"""
    # Get latest metrics
    latest_metrics = SystemMetric.objects.order_by('-timestamp')[:100]
    
    # Get latest health checks
    latest_health = HealthCheckResult.objects.order_by('-timestamp')[:20]
    
    # Get active alerts (alerts that haven't been resolved)
    active_alerts = Alert.objects.filter(
        resolved_at__isnull=True
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
def alerts_view(request):
    """View all alerts"""
    alerts = Alert.objects.all().order_by('-triggered_at')
    
    # Filter by resolved status
    status_filter = request.GET.get('status')
    if status_filter == 'active':
        alerts = alerts.filter(resolved_at__isnull=True)
    elif status_filter == 'resolved':
        alerts = alerts.filter(resolved_at__isnull=False)
    elif status_filter == 'acknowledged':
        alerts = alerts.filter(acknowledged_at__isnull=False, resolved_at__isnull=True)
    
    paginator = Paginator(alerts, 50)
    page = request.GET.get('page', 1)
    alerts_page = paginator.get_page(page)
    
    context = {
        'alerts': alerts_page,
        'active_count': Alert.objects.filter(resolved_at__isnull=True).count(),
        'acknowledged_count': Alert.objects.filter(acknowledged_at__isnull=False, resolved_at__isnull=True).count(),
        'resolved_count': Alert.objects.filter(resolved_at__isnull=False).count(),
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
def settings_management_view(request):
    """Company settings management"""
    # Get system settings
    system_settings = SystemSetting.objects.all().order_by('category', 'key')
    
    # Get company overrides
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        company_overrides = CompanySettingOverride.objects.all().order_by('setting__category', 'setting__key')
    elif hasattr(request.user, 'company') and request.user.company:
        company_overrides = CompanySettingOverride.objects.filter(
            company=request.user.company
        ).order_by('setting__category', 'setting__key')
    else:
        company_overrides = CompanySettingOverride.objects.none()
    
    # Get settings versions
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        versions = SettingsVersion.objects.all().order_by('-created_at')[:10]
    elif hasattr(request.user, 'company') and request.user.company:
        versions = SettingsVersion.objects.filter(
            company=request.user.company
        ).order_by('-created_at')[:10]
    else:
        versions = SettingsVersion.objects.none()
    
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
def onboarding_dashboard_view(request):
    """Company onboarding dashboard"""
    # Get company onboarding
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        company_onboarding = CompanyOnboarding.objects.first()
    elif hasattr(request.user, 'company') and request.user.company:
        company_onboarding = CompanyOnboarding.objects.filter(
            company=request.user.company
        ).first()
    else:
        company_onboarding = None
    
    # Get onboarding reminders
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        reminders = OnboardingReminder.objects.all().order_by('-created_at')[:20]
    elif hasattr(request.user, 'company') and request.user.company:
        reminders = OnboardingReminder.objects.filter(
            company_onboarding__company=request.user.company
        ).order_by('-created_at')[:20]
    else:
        reminders = OnboardingReminder.objects.none()
    
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
def analytics_dashboard_view(request):
    """Company analytics dashboard"""
    # Get latest analytics snapshot
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        latest_analytics = CompanyAnalytics.objects.order_by('-snapshot_date').first()
    elif hasattr(request.user, 'company') and request.user.company:
        latest_analytics = CompanyAnalytics.objects.filter(
            company=request.user.company
        ).order_by('-snapshot_date').first()
    else:
        latest_analytics = None
    
    # Get recent analytics (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        recent_analytics = CompanyAnalytics.objects.filter(
            snapshot_date__gte=thirty_days_ago
        ).order_by('snapshot_date')
    elif hasattr(request.user, 'company') and request.user.company:
        recent_analytics = CompanyAnalytics.objects.filter(
            company=request.user.company,
            snapshot_date__gte=thirty_days_ago
        ).order_by('snapshot_date')
    else:
        recent_analytics = CompanyAnalytics.objects.none()
    
    # Get recent reports
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        recent_reports = AnalyticsReport.objects.all().order_by('-created_at')[:10]
    elif hasattr(request.user, 'company') and request.user.company:
        recent_reports = AnalyticsReport.objects.filter(
            company=request.user.company
        ).order_by('-created_at')[:10]
    else:
        recent_reports = AnalyticsReport.objects.none()
    
    # Get key metric trends
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        employee_trends = MetricTrend.objects.filter(
            metric_name='employee_count',
            date__gte=thirty_days_ago
        ).order_by('date')
        
        turnover_trends = MetricTrend.objects.filter(
            metric_name='turnover_rate',
            date__gte=thirty_days_ago
        ).order_by('date')
    elif hasattr(request.user, 'company') and request.user.company:
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
    else:
        employee_trends = MetricTrend.objects.none()
        turnover_trends = MetricTrend.objects.none()
    
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
def reports_view(request):
    """View all analytics reports"""
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        reports = AnalyticsReport.objects.all().order_by('-created_at')
    elif hasattr(request.user, 'company') and request.user.company:
        reports = AnalyticsReport.objects.filter(
            company=request.user.company
        ).order_by('-created_at')
    else:
        reports = AnalyticsReport.objects.none()
    
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
def metric_trends_view(request):
    """View metric trends"""
    # Get available metrics
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        metrics = MetricTrend.objects.values('metric_name', 'metric_category').distinct()
    elif hasattr(request.user, 'company') and request.user.company:
        metrics = MetricTrend.objects.filter(
            company=request.user.company
        ).values('metric_name', 'metric_category').distinct()
    else:
        metrics = []
    
    # Selected metric
    selected_metric = request.GET.get('metric', 'employee_count')
    days = int(request.GET.get('days', 30))
    
    # Get trend data
    start_date = date.today() - timedelta(days=days)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        trends = MetricTrend.objects.filter(
            metric_name=selected_metric,
            date__gte=start_date
        ).order_by('date')
    elif hasattr(request.user, 'company') and request.user.company:
        trends = MetricTrend.objects.filter(
            company=request.user.company,
            metric_name=selected_metric,
            date__gte=start_date
        ).order_by('date')
    else:
        trends = MetricTrend.objects.none()
    
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
def operational_overview_view(request):
    """Overview of all operational muscles"""
    # Superadmin sees all data, others see only their company
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        total_audit_logs = AuditLog.objects.count()
        recent_audit_logs = AuditLog.objects.order_by('-timestamp')[:5]
        company_overrides = CompanySettingOverride.objects.count()
        company_onboarding = CompanyOnboarding.objects.first()
        latest_analytics = CompanyAnalytics.objects.order_by('-snapshot_date').first()
        total_reports = AnalyticsReport.objects.count()
    elif hasattr(request.user, 'company') and request.user.company:
        total_audit_logs = AuditLog.objects.filter(company=request.user.company).count()
        recent_audit_logs = AuditLog.objects.filter(company=request.user.company).order_by('-timestamp')[:5]
        company_overrides = CompanySettingOverride.objects.filter(company=request.user.company).count()
        company_onboarding = CompanyOnboarding.objects.filter(company=request.user.company).first()
        latest_analytics = CompanyAnalytics.objects.filter(company=request.user.company).order_by('-snapshot_date').first()
        total_reports = AnalyticsReport.objects.filter(company=request.user.company).count()
    else:
        total_audit_logs = 0
        recent_audit_logs = []
        company_overrides = 0
        company_onboarding = None
        latest_analytics = None
        total_reports = 0
    
    context = {
        # Audit & Security
        'total_audit_logs': total_audit_logs,
        'recent_audit_logs': recent_audit_logs,
        
        # System Monitoring
        'active_alerts': Alert.objects.filter(resolved_at__isnull=True).count(),
        'alert_rules': AlertRule.objects.filter(is_active=True).count(),
        
        # MFA
        'users_with_mfa': MFAMethod.objects.filter(is_active=True).values('user').distinct().count(),
        
        # Settings
        'system_settings': SystemSetting.objects.count(),
        'company_overrides': company_overrides,
        
        # Onboarding
        'company_onboarding': company_onboarding,
        
        # Analytics
        'latest_analytics': latest_analytics,
        'total_reports': total_reports,
    }
    
    return render(request, 'blu_core/operational_overview.html', context)
