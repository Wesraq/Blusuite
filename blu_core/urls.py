"""
URL Configuration for Operational Muscles
"""
from django.urls import path
from . import operational_views

app_name = 'blu_core'

urlpatterns = [
    # Overview
    path('', operational_views.operational_overview_view, name='operational_overview'),
    
    # Audit & Security
    path('audit-logs/', operational_views.audit_logs_view, name='audit_logs'),
    
    # System Monitoring
    path('monitoring/', operational_views.system_monitoring_view, name='system_monitoring'),
    path('alerts/', operational_views.alerts_view, name='alerts'),
    
    # MFA
    path('mfa/', operational_views.mfa_settings_view, name='mfa_settings'),
    
    # Settings
    path('settings/', operational_views.settings_management_view, name='settings_management'),
    
    # Onboarding
    path('onboarding/', operational_views.onboarding_dashboard_view, name='onboarding_dashboard'),
    
    # Analytics
    path('analytics/', operational_views.analytics_dashboard_view, name='analytics_dashboard'),
    path('reports/', operational_views.reports_view, name='reports'),
    path('metrics/', operational_views.metric_trends_view, name='metric_trends'),
]
