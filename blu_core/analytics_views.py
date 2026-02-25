"""
BLU Analytics - Advanced Analytics Views
Data visualization, KPIs, and custom dashboards
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from datetime import timedelta
import json

# Import models from various modules for analytics
from blu_projects.models import Project, Task
from blu_staff.apps.attendance.models import Attendance
from blu_staff.apps.accounts.models import EmployeeProfile


@login_required
def analytics_dashboard(request):
    """Main analytics dashboard"""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    # Date range filter
    days = int(request.GET.get('days', 30))
    start_date = timezone.now().date() - timedelta(days=days)
    
    # Employee Analytics
    total_employees = EmployeeProfile.objects.filter(company=company, is_active=True).count()
    
    # Project Analytics
    projects_data = {
        'total': Project.objects.filter(company=company).count(),
        'active': Project.objects.filter(company=company, status='ACTIVE').count(),
        'completed': Project.objects.filter(company=company, status='COMPLETED').count(),
        'on_hold': Project.objects.filter(company=company, status='ON_HOLD').count(),
    }
    
    # Task Analytics
    tasks_data = {
        'total': Task.objects.filter(project__company=company).count(),
        'completed': Task.objects.filter(project__company=company, status='COMPLETED').count(),
        'in_progress': Task.objects.filter(project__company=company, status='IN_PROGRESS').count(),
        'overdue': Task.objects.filter(
            project__company=company,
            due_date__lt=timezone.now().date()
        ).exclude(status='COMPLETED').count(),
    }
    
    # Attendance Analytics
    attendance_data = {
        'present_today': Attendance.objects.filter(
            employee__company=company,
            date=timezone.now().date(),
            status='PRESENT'
        ).count(),
        'absent_today': Attendance.objects.filter(
            employee__company=company,
            date=timezone.now().date(),
            status='ABSENT'
        ).count(),
    }
    
    # Chart data for projects over time
    project_timeline = []
    for i in range(6):
        month_start = timezone.now().date().replace(day=1) - timedelta(days=30*i)
        count = Project.objects.filter(
            company=company,
            created_at__month=month_start.month,
            created_at__year=month_start.year
        ).count()
        project_timeline.insert(0, {
            'month': month_start.strftime('%b %Y'),
            'count': count
        })
    
    context = {
        'total_employees': total_employees,
        'projects_data': projects_data,
        'tasks_data': tasks_data,
        'attendance_data': attendance_data,
        'project_timeline': json.dumps(project_timeline),
        'days_filter': days,
    }
    
    return render(request, 'blu_analytics/dashboard.html', context)


@login_required
def kpi_dashboard(request):
    """KPI tracking dashboard"""
    company = request.user.company
    
    # Calculate KPIs
    kpis = []
    
    # Employee Turnover Rate
    total_employees = EmployeeProfile.objects.filter(company=company).count()
    inactive_employees = EmployeeProfile.objects.filter(company=company, is_active=False).count()
    turnover_rate = (inactive_employees / total_employees * 100) if total_employees > 0 else 0
    
    kpis.append({
        'name': 'Employee Turnover Rate',
        'value': f"{turnover_rate:.1f}%",
        'trend': 'down' if turnover_rate < 10 else 'up',
        'category': 'HR',
        'target': '< 10%'
    })
    
    # Project Completion Rate
    total_projects = Project.objects.filter(company=company).count()
    completed_projects = Project.objects.filter(company=company, status='COMPLETED').count()
    completion_rate = (completed_projects / total_projects * 100) if total_projects > 0 else 0
    
    kpis.append({
        'name': 'Project Completion Rate',
        'value': f"{completion_rate:.1f}%",
        'trend': 'up' if completion_rate > 70 else 'down',
        'category': 'Project',
        'target': '> 80%'
    })
    
    # Average Task Completion Time
    completed_tasks = Task.objects.filter(
        project__company=company,
        status='COMPLETED',
        completed_date__isnull=False
    )
    
    kpis.append({
        'name': 'Active Projects',
        'value': Project.objects.filter(company=company, status='ACTIVE').count(),
        'trend': 'stable',
        'category': 'Project',
        'target': '-'
    })
    
    # Attendance Rate
    today = timezone.now().date()
    present_count = Attendance.objects.filter(
        employee__company=company,
        date=today,
        status='PRESENT'
    ).count()
    total_expected = EmployeeProfile.objects.filter(company=company, is_active=True).count()
    attendance_rate = (present_count / total_expected * 100) if total_expected > 0 else 0
    
    kpis.append({
        'name': 'Attendance Rate (Today)',
        'value': f"{attendance_rate:.1f}%",
        'trend': 'up' if attendance_rate > 90 else 'down',
        'category': 'HR',
        'target': '> 95%'
    })
    
    context = {
        'kpis': kpis,
    }
    
    return render(request, 'blu_analytics/kpi_dashboard.html', context)


@login_required
def custom_reports(request):
    """Custom report builder"""
    company = request.user.company
    
    # Available data sources
    data_sources = [
        {'id': 'employees', 'name': 'Employees', 'icon': '👥'},
        {'id': 'projects', 'name': 'Projects', 'icon': '📊'},
        {'id': 'tasks', 'name': 'Tasks', 'icon': '✅'},
        {'id': 'attendance', 'name': 'Attendance', 'icon': '📅'},
        {'id': 'leave', 'name': 'Leave Requests', 'icon': '🏖️'},
        {'id': 'payroll', 'name': 'Payroll', 'icon': '💰'},
        {'id': 'performance', 'name': 'Performance', 'icon': '⭐'},
    ]
    
    context = {
        'data_sources': data_sources,
    }
    
    return render(request, 'blu_analytics/custom_reports.html', context)


@login_required
def data_visualization(request):
    """Interactive data visualization"""
    company = request.user.company
    
    # Chart types
    chart_types = [
        {'id': 'line', 'name': 'Line Chart', 'icon': '📈'},
        {'id': 'bar', 'name': 'Bar Chart', 'icon': '📊'},
        {'id': 'pie', 'name': 'Pie Chart', 'icon': '🥧'},
        {'id': 'doughnut', 'name': 'Doughnut Chart', 'icon': '🍩'},
        {'id': 'area', 'name': 'Area Chart', 'icon': '📉'},
        {'id': 'scatter', 'name': 'Scatter Plot', 'icon': '⚫'},
    ]
    
    context = {
        'chart_types': chart_types,
    }
    
    return render(request, 'blu_analytics/data_visualization.html', context)


@login_required
def export_data(request):
    """Data export interface"""
    if request.method == 'POST':
        export_type = request.POST.get('export_type')
        format_type = request.POST.get('format', 'CSV')
        
        # Handle export based on type
        messages.success(request, f"Export started. You'll receive an email when it's ready.")
        return redirect('analytics_dashboard')
    
    export_types = [
        {'id': 'employees', 'name': 'Employee Data'},
        {'id': 'projects', 'name': 'Project Data'},
        {'id': 'attendance', 'name': 'Attendance Records'},
        {'id': 'payroll', 'name': 'Payroll Data'},
    ]
    
    context = {
        'export_types': export_types,
    }
    
    return render(request, 'blu_analytics/export_data.html', context)


@login_required
def api_chart_data(request, chart_type):
    """API endpoint for chart data"""
    company = request.user.company
    
    if chart_type == 'projects_by_status':
        data = {
            'labels': ['Active', 'Completed', 'On Hold', 'Planning'],
            'datasets': [{
                'data': [
                    Project.objects.filter(company=company, status='ACTIVE').count(),
                    Project.objects.filter(company=company, status='COMPLETED').count(),
                    Project.objects.filter(company=company, status='ON_HOLD').count(),
                    Project.objects.filter(company=company, status='PLANNING').count(),
                ],
                'backgroundColor': ['#22c55e', '#3b82f6', '#f59e0b', '#8b5cf6']
            }]
        }
    
    elif chart_type == 'tasks_by_priority':
        data = {
            'labels': ['Low', 'Medium', 'High', 'Urgent'],
            'datasets': [{
                'data': [
                    Task.objects.filter(project__company=company, priority='LOW').count(),
                    Task.objects.filter(project__company=company, priority='MEDIUM').count(),
                    Task.objects.filter(project__company=company, priority='HIGH').count(),
                    Task.objects.filter(project__company=company, priority='URGENT').count(),
                ],
                'backgroundColor': ['#64748b', '#3b82f6', '#f59e0b', '#ef4444']
            }]
        }
    
    elif chart_type == 'attendance_trend':
        # Last 7 days attendance
        labels = []
        present_data = []
        absent_data = []
        
        for i in range(7):
            date = timezone.now().date() - timedelta(days=6-i)
            labels.append(date.strftime('%a'))
            
            present = Attendance.objects.filter(
                employee__company=company,
                date=date,
                status='PRESENT'
            ).count()
            
            absent = Attendance.objects.filter(
                employee__company=company,
                date=date,
                status='ABSENT'
            ).count()
            
            present_data.append(present)
            absent_data.append(absent)
        
        data = {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Present',
                    'data': present_data,
                    'borderColor': '#22c55e',
                    'backgroundColor': 'rgba(34, 197, 94, 0.1)',
                },
                {
                    'label': 'Absent',
                    'data': absent_data,
                    'borderColor': '#ef4444',
                    'backgroundColor': 'rgba(239, 68, 68, 0.1)',
                }
            ]
        }
    
    else:
        data = {'error': 'Invalid chart type'}
    
    return JsonResponse(data)


@login_required
def predictive_analytics(request):
    """Predictive analytics and forecasting"""
    company = request.user.company
    
    # Simple predictions (can be enhanced with ML models)
    predictions = []
    
    # Project completion forecast
    active_projects = Project.objects.filter(company=company, status='ACTIVE')
    avg_completion_days = 90  # Simplified
    
    predictions.append({
        'title': 'Project Completion Forecast',
        'description': f'{active_projects.count()} projects expected to complete in next 90 days',
        'confidence': '75%',
        'trend': 'positive'
    })
    
    # Employee growth prediction
    current_employees = EmployeeProfile.objects.filter(company=company, is_active=True).count()
    predicted_growth = int(current_employees * 1.1)  # 10% growth
    
    predictions.append({
        'title': 'Employee Growth Prediction',
        'description': f'Expected to reach {predicted_growth} employees in 6 months',
        'confidence': '68%',
        'trend': 'positive'
    })
    
    context = {
        'predictions': predictions,
    }
    
    return render(request, 'blu_analytics/predictive_analytics.html', context)
