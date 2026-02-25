from django.urls import path
from . import views

app_name = 'blu_analytics'

urlpatterns = [
    # Main Dashboard
    path('', views.analytics_dashboard, name='dashboard'),
    
    # Project Analytics
    path('project/<int:project_id>/', views.project_analytics, name='project_analytics'),
    path('project/<int:project_id>/recalculate/', views.recalculate_analytics, name='recalculate_analytics'),
    
    # Team Productivity
    path('team-productivity/', views.team_productivity, name='team_productivity'),
    
    # Financial Analytics
    path('financial/', views.financial_analytics, name='financial_analytics'),
    
    # Custom Reports
    path('reports/', views.reports_list, name='reports_list'),
    path('reports/create/', views.report_create, name='report_create'),
    path('reports/<int:report_id>/', views.report_detail, name='report_detail'),
    path('reports/<int:report_id>/execute/', views.report_execute, name='report_execute'),
]
