from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from blu_projects.models import Project, Task, TimeEntry, ClientIssue
from .models import ProjectAnalytics, TeamMemberAnalytics, CustomReport, ReportExecution, Dashboard
import json


@login_required
def analytics_dashboard(request):
    """Main analytics dashboard"""
    company = request.user.company
    
    # Get all projects for the company
    projects = Project.objects.filter(company=company)
    
    # Overall Statistics
    total_projects = projects.count()
    active_projects = projects.filter(status='ACTIVE').count()
    completed_projects = projects.filter(status='COMPLETED').count()
    
    # Time Statistics
    total_hours = TimeEntry.objects.filter(project__company=company).aggregate(
        total=Sum('hours')
    )['total'] or 0
    
    billable_hours = TimeEntry.objects.filter(
        project__company=company,
        is_billable=True
    ).aggregate(total=Sum('hours'))['total'] or 0
    
    # Task Statistics
    total_tasks = Task.objects.filter(project__company=company).count()
    completed_tasks = Task.objects.filter(
        project__company=company,
        status='COMPLETED'
    ).count()
    
    # Issue Statistics
    total_issues = ClientIssue.objects.filter(project__company=company).count()
    open_issues = ClientIssue.objects.filter(
        project__company=company,
        status__in=['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS']
    ).count()
    
    # Recent Projects with Analytics
    recent_projects = []
    for project in projects.order_by('-created_at')[:10]:
        analytics, created = ProjectAnalytics.objects.get_or_create(project=project)
        if created or (timezone.now() - analytics.last_calculated).seconds > 3600:
            analytics.calculate_metrics()
        recent_projects.append({
            'project': project,
            'analytics': analytics
        })
    
    context = {
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'total_hours': total_hours,
        'billable_hours': billable_hours,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'total_issues': total_issues,
        'open_issues': open_issues,
        'recent_projects': recent_projects,
    }
    
    return render(request, 'blu_analytics/dashboard.html', context)


@login_required
def project_analytics(request, project_id):
    """Detailed analytics for a specific project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    # Get or create analytics
    analytics, created = ProjectAnalytics.objects.get_or_create(project=project)
    
    # Recalculate if stale (older than 1 hour)
    if created or (timezone.now() - analytics.last_calculated).seconds > 3600:
        analytics.calculate_metrics()
    
    # Get team member analytics
    team_analytics = TeamMemberAnalytics.objects.filter(
        project=project,
        period_start__lte=timezone.now().date(),
        period_end__gte=timezone.now().date()
    )
    
    # Time tracking data for charts
    time_entries = TimeEntry.objects.filter(project=project).order_by('date')
    time_data = {}
    for entry in time_entries:
        date_str = entry.date.strftime('%Y-%m-%d')
        if date_str not in time_data:
            time_data[date_str] = 0
        time_data[date_str] += float(entry.hours)
    
    # Task completion data
    tasks = Task.objects.filter(project=project)
    task_status_data = tasks.values('status').annotate(count=Count('id'))
    
    context = {
        'project': project,
        'analytics': analytics,
        'team_analytics': team_analytics,
        'time_data': json.dumps(time_data),
        'task_status_data': list(task_status_data),
    }
    
    return render(request, 'blu_analytics/project_analytics.html', context)


@login_required
def team_productivity(request):
    """Team productivity analytics"""
    company = request.user.company
    
    # Get date range from request or default to last 30 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    # Get all team members
    from accounts.models import User
    team_members = User.objects.filter(company=company, is_active=True)
    
    team_data = []
    for member in team_members:
        # Calculate metrics for this team member
        hours_logged = TimeEntry.objects.filter(
            user=member,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('hours'))['total'] or 0
        
        tasks_completed = Task.objects.filter(
            assigned_to=member,
            status='COMPLETED',
            completed_date__gte=start_date,
            completed_date__lte=end_date
        ).count()
        
        tasks_assigned = Task.objects.filter(
            assigned_to=member,
            created_at__gte=start_date
        ).count()
        
        issues_resolved = ClientIssue.objects.filter(
            assigned_to=member,
            status__in=['RESOLVED', 'CLOSED'],
            resolved_at__gte=start_date,
            resolved_at__lte=end_date
        ).count()
        
        team_data.append({
            'member': member,
            'hours_logged': hours_logged,
            'tasks_completed': tasks_completed,
            'tasks_assigned': tasks_assigned,
            'issues_resolved': issues_resolved,
        })
    
    context = {
        'team_data': team_data,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'blu_analytics/team_productivity.html', context)


@login_required
def financial_analytics(request):
    """Financial analytics and reports"""
    company = request.user.company
    projects = Project.objects.filter(company=company)
    
    # Overall financial metrics
    total_budget = projects.aggregate(total=Sum('budget'))['total'] or 0
    
    # Calculate total costs from time entries
    billable_hours = TimeEntry.objects.filter(
        project__company=company,
        is_billable=True
    ).aggregate(total=Sum('hours'))['total'] or 0
    
    # Assuming $100/hour rate (should be configurable)
    hourly_rate = 100
    total_revenue = billable_hours * hourly_rate
    
    # Project-wise financial data
    project_financials = []
    for project in projects:
        project_hours = TimeEntry.objects.filter(
            project=project,
            is_billable=True
        ).aggregate(total=Sum('hours'))['total'] or 0
        
        project_revenue = project_hours * hourly_rate
        project_budget = project.budget or 0
        variance = project_budget - project_revenue
        
        project_financials.append({
            'project': project,
            'budget': project_budget,
            'revenue': project_revenue,
            'variance': variance,
            'hours': project_hours,
        })
    
    context = {
        'total_budget': total_budget,
        'total_revenue': total_revenue,
        'billable_hours': billable_hours,
        'hourly_rate': hourly_rate,
        'project_financials': project_financials,
    }
    
    return render(request, 'blu_analytics/financial_analytics.html', context)


@login_required
def reports_list(request):
    """List all custom reports"""
    reports = CustomReport.objects.filter(company=request.user.company)
    
    context = {
        'reports': reports,
    }
    
    return render(request, 'blu_analytics/reports_list.html', context)


@login_required
def report_create(request):
    """Create a new custom report"""
    if request.method == 'POST':
        try:
            report = CustomReport.objects.create(
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                report_type=request.POST.get('report_type'),
                frequency=request.POST.get('frequency', 'ON_DEMAND'),
                is_scheduled=request.POST.get('is_scheduled') == 'on',
                created_by=request.user,
                company=request.user.company
            )
            
            # Add projects if selected
            project_ids = request.POST.getlist('projects')
            if project_ids:
                report.projects.set(project_ids)
            
            messages.success(request, f"Report '{report.name}' created successfully!")
            return redirect('blu_analytics:report_detail', report_id=report.id)
            
        except Exception as e:
            messages.error(request, f"Error creating report: {str(e)}")
    
    projects = Project.objects.filter(company=request.user.company)
    
    context = {
        'projects': projects,
        'report_types': CustomReport.REPORT_TYPES,
        'frequency_choices': CustomReport.FREQUENCY_CHOICES,
    }
    
    return render(request, 'blu_analytics/report_form.html', context)


@login_required
def report_detail(request, report_id):
    """View report details and executions"""
    report = get_object_or_404(CustomReport, id=report_id, company=request.user.company)
    executions = report.executions.all()[:20]
    
    context = {
        'report': report,
        'executions': executions,
    }
    
    return render(request, 'blu_analytics/report_detail.html', context)


@login_required
def report_execute(request, report_id):
    """Execute a report"""
    report = get_object_or_404(CustomReport, id=report_id, company=request.user.company)
    
    # Create execution record
    execution = ReportExecution.objects.create(
        report=report,
        status='RUNNING',
        executed_by=request.user,
        started_at=timezone.now()
    )
    
    try:
        # Generate report data based on type
        result_data = generate_report_data(report)
        
        execution.result_data = json.dumps(result_data)
        execution.status = 'COMPLETED'
        execution.completed_at = timezone.now()
        execution.save()
        
        messages.success(request, "Report executed successfully!")
        
    except Exception as e:
        execution.status = 'FAILED'
        execution.error_message = str(e)
        execution.completed_at = timezone.now()
        execution.save()
        
        messages.error(request, f"Report execution failed: {str(e)}")
    
    return redirect('blu_analytics:report_detail', report_id=report.id)


def generate_report_data(report):
    """Generate report data based on report type"""
    data = {}
    
    if report.report_type == 'PROJECT_SUMMARY':
        projects = report.projects.all() if report.projects.exists() else Project.objects.filter(company=report.company)
        data['projects'] = []
        
        for project in projects:
            analytics, _ = ProjectAnalytics.objects.get_or_create(project=project)
            analytics.calculate_metrics()
            
            data['projects'].append({
                'name': project.name,
                'status': project.status,
                'completion_rate': float(analytics.completion_rate),
                'total_hours': float(analytics.total_hours_logged),
                'budget': float(analytics.total_budget),
                'cost': float(analytics.total_cost),
            })
    
    elif report.report_type == 'TIME_TRACKING':
        time_entries = TimeEntry.objects.filter(project__company=report.company)
        if report.date_range_start:
            time_entries = time_entries.filter(date__gte=report.date_range_start)
        if report.date_range_end:
            time_entries = time_entries.filter(date__lte=report.date_range_end)
        
        data['total_hours'] = float(time_entries.aggregate(total=Sum('hours'))['total'] or 0)
        data['billable_hours'] = float(time_entries.filter(is_billable=True).aggregate(total=Sum('hours'))['total'] or 0)
        data['entries_count'] = time_entries.count()
    
    elif report.report_type == 'SLA_COMPLIANCE':
        issues = ClientIssue.objects.filter(project__company=report.company)
        total = issues.count()
        breached = issues.filter(Q(response_sla_breached=True) | Q(resolution_sla_breached=True)).count()
        
        data['total_issues'] = total
        data['breached_issues'] = breached
        data['compliance_rate'] = ((total - breached) / total * 100) if total > 0 else 100
    
    return data


@login_required
def recalculate_analytics(request, project_id):
    """Manually recalculate analytics for a project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    analytics, created = ProjectAnalytics.objects.get_or_create(project=project)
    analytics.calculate_metrics()
    
    messages.success(request, f"Analytics recalculated for {project.name}")
    return redirect('blu_analytics:project_analytics', project_id=project.id)
