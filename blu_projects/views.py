"""
BLU Projects - Views
Comprehensive project management views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from decimal import Decimal
from datetime import timedelta

from .models import (
    Project, ProjectMilestone, Task, TimeEntry,
    TaskComment, ProjectDocument, ProjectActivity,
    ProjectRisk, ProjectStakeholder,
    ClientIssue, ProjectSLA, ClientAccess,
)


def _is_pms_admin(user):
    """Check if user has PMS admin rights (can see all projects, create projects, manage team)."""
    role = (getattr(user, 'role', '') or '').upper()
    if role in ('ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN'):
        return True
    if hasattr(user, 'employee_profile'):
        emp_role = (user.employee_profile.employee_role or '').upper()
        if emp_role in ('HR', 'SUPERVISOR'):
            return True
    return False


def _get_user_projects(user, company):
    """Return project queryset scoped to user's access level."""
    if _is_pms_admin(user):
        return Project.objects.filter(company=company)
    return Project.objects.filter(company=company, team_members=user)


def _get_user_tasks(user, company):
    """Return task queryset for the current user."""
    return Task.objects.filter(assigned_to=user, project__company=company)


@login_required
def projects_home(request):
    """Projects Suite home dashboard - personalized to current user."""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    is_admin = _is_pms_admin(user)
    my_projects = _get_user_projects(user, company)
    my_tasks_qs = _get_user_tasks(user, company)
    today = timezone.now().date()
    
    # Personal statistics
    stats = {
        'my_projects': my_projects.count(),
        'my_projects_active': my_projects.filter(status='ACTIVE').count(),
        'my_tasks_total': my_tasks_qs.count(),
        'my_tasks_pending': my_tasks_qs.exclude(status='COMPLETED').count(),
        'my_tasks_overdue': my_tasks_qs.filter(due_date__lt=today).exclude(status='COMPLETED').count(),
        'my_tasks_completed': my_tasks_qs.filter(status='COMPLETED').count(),
    }
    # Portfolio-level stats (admin / all users)
    all_company_projects = Project.objects.filter(company=company)
    portfolio = {
        'total': all_company_projects.count(),
        'planning': all_company_projects.filter(status='PLANNING').count(),
        'active': all_company_projects.filter(status='ACTIVE').count(),
        'in_progress': all_company_projects.filter(status='IN_PROGRESS').count(),
        'completed': all_company_projects.filter(status='COMPLETED').count(),
        'on_hold': all_company_projects.filter(status='ON_HOLD').count(),
        'cancelled': all_company_projects.filter(status='CANCELLED').count(),
        'overdue_projects': all_company_projects.filter(end_date__lt=today).exclude(status__in=['COMPLETED', 'CANCELLED']).count(),
        'open_risks': ProjectRisk.objects.filter(project__company=company, status='OPEN').count(),
        'critical_risks': ProjectRisk.objects.filter(project__company=company, status='OPEN', probability__gte=4, impact__gte=4).count(),
    }
    # Budget totals
    from django.db.models import Sum as _Sum
    budget_data = all_company_projects.aggregate(
        total_budget=_Sum('budget'),
        total_funded=_Sum('funding_amount'),
    )
    portfolio['total_budget'] = budget_data['total_budget'] or 0
    portfolio['total_funded'] = budget_data['total_funded'] or 0

    # By project type (for chart)
    from django.db.models import Count as _Count
    type_breakdown = list(
        all_company_projects.values('project_type')
        .annotate(n=_Count('id'))
        .order_by('-n')[:6]
    )
    # By sector
    sector_breakdown = list(
        all_company_projects.values('sector')
        .annotate(n=_Count('id'))
        .order_by('-n')[:6]
    )

    if is_admin:
        stats['company_total'] = portfolio['total']
        stats['company_active'] = portfolio['active'] + portfolio['in_progress']

    # My active projects (with progress)
    active_projects = my_projects.filter(
        status__in=['ACTIVE', 'PLANNING']
    ).order_by('-updated_at')[:6]
    
    # My overdue tasks
    overdue_tasks = my_tasks_qs.filter(
        due_date__lt=today
    ).exclude(status='COMPLETED').select_related('project').order_by('due_date')[:5]
    
    # My upcoming tasks (next 7 days)
    seven_days = today + timedelta(days=7)
    upcoming_tasks = my_tasks_qs.filter(
        due_date__gte=today,
        due_date__lte=seven_days
    ).exclude(status='COMPLETED').select_related('project').order_by('due_date')[:5]
    
    # My in-progress tasks
    in_progress_tasks = my_tasks_qs.filter(
        status='IN_PROGRESS'
    ).select_related('project').order_by('-updated_at')[:5]
    
    # Upcoming milestones (from my projects, next 30 days)
    thirty_days = today + timedelta(days=30)
    upcoming_milestones = ProjectMilestone.objects.filter(
        project__in=my_projects,
        due_date__lte=thirty_days,
        due_date__gte=today
    ).exclude(status='COMPLETED').select_related('project').order_by('due_date')[:5]
    
    # Recent activity (from my projects)
    recent_activities = ProjectActivity.objects.filter(
        project__in=my_projects
    ).select_related('project', 'user').order_by('-created_at')[:10]
    
    context = {
        'user': user,
        'company_name': company.name,
        'is_admin': is_admin,
        'stats': stats,
        'portfolio': portfolio,
        'type_breakdown': type_breakdown,
        'sector_breakdown': sector_breakdown,
        'active_projects': active_projects,
        'overdue_tasks': overdue_tasks,
        'upcoming_tasks': upcoming_tasks,
        'in_progress_tasks': in_progress_tasks,
        'upcoming_milestones': upcoming_milestones,
        'recent_activities': recent_activities,
    }

    return render(request, 'blu_projects/projects_home.html', context)


@login_required
def projects_list(request):
    """List projects - scoped to user's access level."""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    is_admin = _is_pms_admin(user)
    
    # Base queryset scoped by role
    projects = _get_user_projects(user, company)
    
    # Filters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    search = request.GET.get('search', '')
    
    if status_filter:
        projects = projects.filter(status=status_filter)
    if priority_filter:
        projects = projects.filter(priority=priority_filter)
    if search:
        projects = projects.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(description__icontains=search)
        )
    
    projects = projects.order_by('-updated_at')
    
    # Pagination
    paginator = Paginator(projects, 12)
    page = request.GET.get('page', 1)
    projects_page = paginator.get_page(page)
    
    # Statistics (scoped)
    base_qs = _get_user_projects(user, company)
    stats = {
        'total': base_qs.count(),
        'active': base_qs.filter(status='ACTIVE').count(),
        'completed': base_qs.filter(status='COMPLETED').count(),
        'on_hold': base_qs.filter(status='ON_HOLD').count(),
    }
    
    context = {
        'projects': projects_page,
        'stats': stats,
        'is_admin': is_admin,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search': search,
        'status_choices': Project.STATUS_CHOICES,
        'priority_choices': Project.PRIORITY_CHOICES,
    }
    
    return render(request, 'blu_projects/projects_list.html', context)


@login_required
def project_detail(request, project_id):
    """Project detail view with tasks, milestones, team, risks, and stakeholders"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)

    # Get related data
    milestones = project.milestones.all()
    tasks = project.tasks.filter(parent_task__isnull=True)  # top-level tasks only
    team_members = project.team_members.all()
    recent_activities = project.activities.all()[:15]
    documents = project.documents.all()[:10]
    risks = project.risks.all()
    stakeholders = project.stakeholders.all()

    # Task statistics
    all_tasks = project.tasks.all()
    task_stats = {
        'total': all_tasks.count(),
        'todo': all_tasks.filter(status='TODO').count(),
        'in_progress': all_tasks.filter(status='IN_PROGRESS').count(),
        'in_review': all_tasks.filter(status='IN_REVIEW').count(),
        'completed': all_tasks.filter(status='COMPLETED').count(),
        'blocked': all_tasks.filter(status='BLOCKED').count(),
    }

    # Kanban board data — list of (key, label, color, task_list) tuples
    kanban_data = [
        ('todo', 'To Do', '#94a3b8', list(tasks.filter(status='TODO').select_related('assigned_to'))),
        ('in_progress', 'In Progress', '#d97706', list(tasks.filter(status='IN_PROGRESS').select_related('assigned_to'))),
        ('in_review', 'In Review', '#7c3aed', list(tasks.filter(status='IN_REVIEW').select_related('assigned_to'))),
        ('completed', 'Completed', '#16a34a', list(tasks.filter(status='COMPLETED').select_related('assigned_to'))),
        ('blocked', 'Blocked', '#dc2626', list(tasks.filter(status='BLOCKED').select_related('assigned_to'))),
    ]

    # Time tracking
    time_entries = TimeEntry.objects.filter(task__project=project)
    total_hours = time_entries.aggregate(total=Sum('hours'))['total'] or 0
    billable_hours = time_entries.filter(is_billable=True).aggregate(total=Sum('hours'))['total'] or 0

    # Budget utilisation
    budget_pct = project.budget_utilisation_pct()

    # Risk summary
    risk_summary = {
        'total': risks.count(),
        'open': risks.filter(status='OPEN').count(),
        'critical': [r for r in risks if r.risk_level_label == 'CRITICAL'],
        'high': [r for r in risks if r.risk_level_label == 'HIGH'],
    }

    context = {
        'project': project,
        'milestones': milestones,
        'tasks': tasks,
        'all_tasks': all_tasks,
        'kanban_data': kanban_data,
        'team_members': team_members,
        'recent_activities': recent_activities,
        'documents': documents,
        'task_stats': task_stats,
        'total_hours': total_hours,
        'billable_hours': billable_hours,
        'budget_pct': budget_pct,
        'risks': risks,
        'risk_summary': risk_summary,
        'stakeholders': stakeholders,
        'is_admin': _is_pms_admin(request.user),
        'today': timezone.now().date(),
    }

    return render(request, 'blu_projects/project_detail.html', context)


@login_required
def project_create(request):
    """Create new project"""
    if request.method == 'POST':
        try:
            project = Project.objects.create(
                name=request.POST.get('name'),
                code=request.POST.get('code'),
                description=request.POST.get('description', ''),
                objectives=request.POST.get('objectives', ''),
                scope=request.POST.get('scope', ''),
                company=request.user.company,
                project_type=request.POST.get('project_type', 'INTERNAL'),
                sector=request.POST.get('sector', 'OTHER'),
                methodology=request.POST.get('methodology', 'WATERFALL'),
                tags=request.POST.get('tags', ''),
                status=request.POST.get('status', 'PLANNING'),
                priority=request.POST.get('priority', 'MEDIUM'),
                risk_level=request.POST.get('risk_level', 'LOW'),
                visibility=request.POST.get('visibility', 'INTERNAL'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                currency=request.POST.get('currency', 'USD'),
                budget=request.POST.get('budget') or None,
                estimated_hours=request.POST.get('estimated_hours') or None,
                funding_source=request.POST.get('funding_source', ''),
                grant_reference=request.POST.get('grant_reference', ''),
                funding_amount=request.POST.get('funding_amount') or None,
                client_name=request.POST.get('client_name', ''),
                client_organisation=request.POST.get('client_organisation', ''),
                client_contact=request.POST.get('client_contact', ''),
                client_email=request.POST.get('client_email', ''),
                client_phone=request.POST.get('client_phone', ''),
                beneficiary_count=request.POST.get('beneficiary_count') or None,
                project_manager_id=request.POST.get('project_manager') or None,
                is_template=request.POST.get('is_template') == 'on',
                created_by=request.user,
            )
            
            # Add team members
            team_member_ids = request.POST.getlist('team_members')
            if team_member_ids:
                project.team_members.set(team_member_ids)

                # Cross-suite notification for each team member
                try:
                    from ems_project.cross_suite_notifications import notify_project_member_added
                    AccUser = get_user_model()
                    for mid in team_member_ids:
                        try:
                            member = AccUser.objects.get(id=mid)
                            if member != request.user:
                                notify_project_member_added(project, member, added_by=request.user)
                        except AccUser.DoesNotExist:
                            pass
                except Exception:
                    pass
            
            # Log activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                action='CREATED',
                description=f"Project '{project.name}' created"
            )
            
            # Handle client invitations
            client_emails = request.POST.get('client_emails', '').strip()
            if client_emails:
                from django.core.mail import send_mail
                from django.conf import settings
                User = get_user_model()
                
                emails = [email.strip() for email in client_emails.split(',') if email.strip()]
                
                for email in emails:
                    # Check if user exists
                    try:
                        client_user = User.objects.get(email=email)
                    except User.DoesNotExist:
                        # Create invitation (user will be created when they accept)
                        client_user = None
                    
                    if client_user:
                        # Grant client access
                        ClientAccess.objects.get_or_create(
                            user=client_user,
                            project=project,
                            defaults={
                                'access_level': 'REPORT',
                                'granted_by': request.user
                            }
                        )
                    
                    # Send invitation email
                    try:
                        subject = f'Project Access Invitation: {project.name}'
                        message = f'''
Hello,

You have been invited to access the project "{project.name}" on BLU Projects.

Project Details:
- Name: {project.name}
- Code: {project.code}
- Description: {project.description}

To access the project portal, please log in at: {settings.SITE_URL}/projects/client-portal/

If you don't have an account, please contact your project manager.

Best regards,
{request.user.get_full_name()}
{request.user.company.name}
'''
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"Error sending email to {email}: {str(e)}")
            
            messages.success(request, f"Project '{project.name}' created successfully! Client invitations sent.")
            return redirect('blu_projects:project_detail', project_id=project.id)
            
        except Exception as e:
            messages.error(request, f"Error creating project: {str(e)}")
    
    User = get_user_model()
    team_members = User.objects.filter(company=request.user.company, is_active=True)

    context = {
        'user': request.user,
        'team_members': team_members,
        'status_choices': Project.STATUS_CHOICES,
        'priority_choices': Project.PRIORITY_CHOICES,
        'project_type_choices': Project.PROJECT_TYPE_CHOICES,
        'sector_choices': Project.SECTOR_CHOICES,
        'methodology_choices': Project.METHODOLOGY_CHOICES,
        'risk_level_choices': Project.RISK_LEVEL_CHOICES,
        'currency_choices': Project.CURRENCY_CHOICES,
        'visibility_choices': Project.VISIBILITY_CHOICES,
    }

    return render(request, 'blu_projects/project_form.html', context)


@login_required
def project_edit(request, project_id):
    """Edit existing project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    if request.method == 'POST':
        try:
            project.name = request.POST.get('name')
            project.description = request.POST.get('description', '')
            project.objectives = request.POST.get('objectives', '')
            project.scope = request.POST.get('scope', '')
            project.project_type = request.POST.get('project_type', project.project_type)
            project.sector = request.POST.get('sector', project.sector)
            project.methodology = request.POST.get('methodology', project.methodology)
            project.tags = request.POST.get('tags', '')
            project.status = request.POST.get('status')
            project.priority = request.POST.get('priority')
            project.risk_level = request.POST.get('risk_level', project.risk_level)
            project.visibility = request.POST.get('visibility', project.visibility)
            project.start_date = request.POST.get('start_date')
            project.end_date = request.POST.get('end_date')
            project.currency = request.POST.get('currency', project.currency)
            project.budget = request.POST.get('budget') or None
            project.estimated_hours = request.POST.get('estimated_hours') or None
            project.funding_source = request.POST.get('funding_source', '')
            project.grant_reference = request.POST.get('grant_reference', '')
            project.funding_amount = request.POST.get('funding_amount') or None
            project.client_name = request.POST.get('client_name', '')
            project.client_organisation = request.POST.get('client_organisation', '')
            project.client_contact = request.POST.get('client_contact', '')
            project.client_email = request.POST.get('client_email', '')
            project.client_phone = request.POST.get('client_phone', '')
            project.beneficiary_count = request.POST.get('beneficiary_count') or None
            project.project_manager_id = request.POST.get('project_manager') or None
            project.is_template = request.POST.get('is_template') == 'on'
            project.save()
            
            # Update team members - detect newly added ones
            team_member_ids = request.POST.getlist('team_members')
            old_member_ids = set(project.team_members.values_list('id', flat=True))
            project.team_members.set(team_member_ids)
            new_member_ids = set(int(mid) for mid in team_member_ids if mid) - old_member_ids

            # Cross-suite notification for newly added members
            if new_member_ids:
                try:
                    from ems_project.cross_suite_notifications import notify_project_member_added
                    User = get_user_model()
                    for mid in new_member_ids:
                        try:
                            member = User.objects.get(id=mid)
                            if member != request.user:
                                notify_project_member_added(project, member, added_by=request.user)
                        except User.DoesNotExist:
                            pass
                except Exception:
                    pass
            
            # Log activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                action='UPDATED',
                description=f"Project '{project.name}' updated"
            )
            
            messages.success(request, "Project updated successfully!")
            return redirect('blu_projects:project_detail', project_id=project.id)
            
        except Exception as e:
            messages.error(request, f"Error updating project: {str(e)}")
    
    User = get_user_model()
    team_members = User.objects.filter(company=request.user.company, is_active=True)

    context = {
        'user': request.user,
        'project': project,
        'team_members': team_members,
        'status_choices': Project.STATUS_CHOICES,
        'priority_choices': Project.PRIORITY_CHOICES,
        'project_type_choices': Project.PROJECT_TYPE_CHOICES,
        'sector_choices': Project.SECTOR_CHOICES,
        'methodology_choices': Project.METHODOLOGY_CHOICES,
        'risk_level_choices': Project.RISK_LEVEL_CHOICES,
        'currency_choices': Project.CURRENCY_CHOICES,
        'visibility_choices': Project.VISIBILITY_CHOICES,
        'is_edit': True,
    }

    return render(request, 'blu_projects/project_form.html', context)


@login_required
def task_create(request, project_id):
    """Create new task"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    if request.method == 'POST':
        try:
            task = Task.objects.create(
                project=project,
                milestone_id=request.POST.get('milestone') or None,
                title=request.POST.get('title'),
                description=request.POST.get('description', ''),
                status=request.POST.get('status', 'TODO'),
                priority=request.POST.get('priority', 'MEDIUM'),
                assigned_to_id=request.POST.get('assigned_to') or None,
                start_date=request.POST.get('start_date') or None,
                due_date=request.POST.get('due_date') or None,
                estimated_hours=request.POST.get('estimated_hours') or None,
                created_by=request.user,
            )
            
            # Log activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                action='TASK_ADDED',
                description=f"Task '{task.title}' added"
            )

            # Cross-suite notification
            if task.assigned_to:
                try:
                    from ems_project.cross_suite_notifications import notify_task_assigned
                    notify_task_assigned(task, assigned_by=request.user)
                except Exception:
                    pass
            
            messages.success(request, "Task created successfully!")
            return redirect('blu_projects:project_detail', project_id=project.id)
            
        except Exception as e:
            messages.error(request, f"Error creating task: {str(e)}")
    
    User = get_user_model()
    team_members = User.objects.filter(company=request.user.company, is_active=True)
    milestones = project.milestones.all()
    
    context = {
        'project': project,
        'team_members': team_members,
        'milestones': milestones,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
    }
    
    return render(request, 'blu_projects/task_form.html', context)


@login_required
def task_detail(request, task_id):
    """Task detail view with comments and time entries"""
    task = get_object_or_404(Task, id=task_id, project__company=request.user.company)
    
    comments = task.comments.all()
    time_entries = task.time_entries.all()
    
    context = {
        'task': task,
        'project': task.project,
        'comments': comments,
        'time_entries': time_entries,
    }
    
    return render(request, 'blu_projects/task_detail.html', context)


@login_required
def task_update_status(request, task_id):
    """Quick update task status"""
    if request.method == 'POST':
        task = get_object_or_404(Task, id=task_id, project__company=request.user.company)
        new_status = request.POST.get('status')
        
        if new_status in dict(Task.STATUS_CHOICES):
            old_status = task.status
            task.status = new_status
            
            if new_status == 'COMPLETED':
                task.completed_date = timezone.now()
            
            task.save()
            
            # Update project progress
            task.project.update_progress()
            
            # Log activity
            if new_status == 'COMPLETED':
                ProjectActivity.objects.create(
                    project=task.project,
                    user=request.user,
                    action='TASK_COMPLETED',
                    description=f"Task '{task.title}' completed"
                )
            
            messages.success(request, f"Task status updated to {task.get_status_display()}")
        else:
            messages.error(request, "Invalid status")
    
    # Redirect back to referring page if available, else project detail
    referer = request.META.get('HTTP_REFERER', '')
    if 'my_tasks' in referer or 'my-tasks' in referer:
        return redirect('blu_projects:my_tasks')
    return redirect('blu_projects:project_detail', project_id=task.project.id)


@login_required
def task_edit(request, task_id):
    """Edit existing task"""
    task = get_object_or_404(Task, id=task_id, project__company=request.user.company)
    project = task.project
    
    if request.method == 'POST':
        try:
            prev_assigned = task.assigned_to
            task.title = request.POST.get('title')
            task.description = request.POST.get('description', '')
            task.status = request.POST.get('status')
            task.priority = request.POST.get('priority')
            
            # Assigned to
            assigned_to_id = request.POST.get('assigned_to')
            if assigned_to_id:
                task.assigned_to = User.objects.get(id=assigned_to_id)
            else:
                task.assigned_to = None
            
            # Dates
            due_date = request.POST.get('due_date')
            task.due_date = due_date if due_date else None
            
            # Hours
            estimated_hours = request.POST.get('estimated_hours')
            task.estimated_hours = float(estimated_hours) if estimated_hours else None
            
            # Milestone
            milestone_id = request.POST.get('milestone')
            if milestone_id:
                task.milestone = ProjectMilestone.objects.get(id=milestone_id)
            else:
                task.milestone = None
            
            task.save()

            # Cross-suite notification if assignee changed
            if task.assigned_to and task.assigned_to != prev_assigned:
                try:
                    from ems_project.cross_suite_notifications import notify_task_assigned
                    notify_task_assigned(task, assigned_by=request.user)
                except Exception:
                    pass
            
            messages.success(request, f'Task "{task.title}" updated successfully!')
            return redirect('blu_projects:task_detail', task_id=task.id)
            
        except Exception as e:
            messages.error(request, f'Error updating task: {str(e)}')
    
    # Get team members for assignment
    team_members = project.team_members.all()
    milestones = project.milestones.all()
    
    context = {
        'task': task,
        'project': project,
        'team_members': team_members,
        'milestones': milestones,
        'edit_mode': True,
    }
    
    return render(request, 'blu_projects/task_form.html', context)


@login_required
def task_delete(request, task_id):
    """Delete task"""
    task = get_object_or_404(Task, id=task_id, project__company=request.user.company)
    project = task.project
    
    if request.method == 'POST':
        task_title = task.title
        task.delete()
        messages.success(request, f'Task "{task_title}" deleted successfully!')
        return redirect('blu_projects:project_detail', project_id=project.id)
    
    context = {
        'task': task,
        'project': project,
    }
    
    return render(request, 'blu_projects/task_confirm_delete.html', context)


@login_required
def time_entry_create(request, task_id):
    """Log time on a task"""
    task = get_object_or_404(Task, id=task_id, project__company=request.user.company)
    
    if request.method == 'POST':
        try:
            hours = Decimal(request.POST.get('hours'))
            time_entry = TimeEntry.objects.create(
                task=task,
                user=request.user,
                date=request.POST.get('date'),
                hours=hours,
                description=request.POST.get('description', ''),
                is_billable=request.POST.get('is_billable') == 'on',
                hourly_rate=request.POST.get('hourly_rate') or None,
            )
            
            # Update task actual hours
            task.actual_hours += hours
            task.save()
            
            messages.success(request, f"{hours} hours logged successfully!")
            return redirect('blu_projects:task_detail', task_id=task.id)
            
        except Exception as e:
            messages.error(request, f"Error logging time: {str(e)}")
    
    context = {
        'task': task,
    }
    
    return render(request, 'blu_projects/time_entry_form.html', context)


@login_required
def my_tasks(request):
    """View tasks assigned to current user - enhanced with filters, search, sorting."""
    user = request.user
    company = user.company
    today = timezone.now().date()
    
    # Base queryset
    base_tasks = Task.objects.filter(
        assigned_to=user,
        project__company=company
    ).select_related('project')
    
    tasks = base_tasks.all()
    
    # Filters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    project_filter = request.GET.get('project', '')
    search = request.GET.get('search', '')
    sort = request.GET.get('sort', 'due_date')
    
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if project_filter:
        tasks = tasks.filter(project_id=project_filter)
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(project__name__icontains=search)
        )
    
    # Sorting
    sort_map = {
        'due_date': 'due_date',
        '-due_date': '-due_date',
        'priority': '-priority',
        'status': 'status',
        'project': 'project__name',
        '-updated': '-updated_at',
    }
    tasks = tasks.order_by(sort_map.get(sort, 'due_date'))
    
    # Pagination
    paginator = Paginator(tasks, 20)
    page = request.GET.get('page', 1)
    tasks_page = paginator.get_page(page)
    
    # Statistics (from base, unfiltered)
    stats = {
        'total': base_tasks.count(),
        'todo': base_tasks.filter(status='TODO').count(),
        'in_progress': base_tasks.filter(status='IN_PROGRESS').count(),
        'in_review': base_tasks.filter(status='IN_REVIEW').count(),
        'completed': base_tasks.filter(status='COMPLETED').count(),
        'blocked': base_tasks.filter(status='BLOCKED').count(),
        'overdue': base_tasks.filter(due_date__lt=today).exclude(status='COMPLETED').count(),
    }
    
    # Projects for filter dropdown
    my_project_ids = base_tasks.values_list('project_id', flat=True).distinct()
    filter_projects = Project.objects.filter(id__in=my_project_ids).order_by('name')
    
    context = {
        'tasks': tasks_page,
        'stats': stats,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'project_filter': project_filter,
        'search': search,
        'sort': sort,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES if hasattr(Task, 'PRIORITY_CHOICES') else [],
        'filter_projects': filter_projects,
        'today': today,
    }
    
    return render(request, 'blu_projects/my_tasks.html', context)


@login_required
def project_gantt(request, project_id):
    """Gantt chart view for project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    tasks = project.tasks.all().select_related('assigned_to', 'milestone')
    milestones = project.milestones.all()
    
    context = {
        'project': project,
        'tasks': tasks,
        'milestones': milestones,
    }
    
    return render(request, 'blu_projects/project_gantt.html', context)


@login_required
def project_reports(request, project_id):
    """Project reports and analytics"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    # Task completion rate
    tasks = project.tasks.all()
    completed_tasks = tasks.filter(status='COMPLETED').count()
    completion_rate = (completed_tasks / tasks.count() * 100) if tasks.count() > 0 else 0
    
    # Time tracking
    time_entries = TimeEntry.objects.filter(task__project=project)
    total_hours = time_entries.aggregate(total=Sum('hours'))['total'] or 0
    billable_hours = time_entries.filter(is_billable=True).aggregate(total=Sum('hours'))['total'] or 0
    
    # Budget tracking
    budget_used_percentage = (float(project.actual_cost) / float(project.budget) * 100) if project.budget else 0
    
    # Team performance
    team_stats = []
    for member in project.team_members.all():
        member_tasks = tasks.filter(assigned_to=member)
        member_hours = time_entries.filter(user=member).aggregate(total=Sum('hours'))['total'] or 0
        team_stats.append({
            'member': member,
            'tasks_assigned': member_tasks.count(),
            'tasks_completed': member_tasks.filter(status='COMPLETED').count(),
            'hours_logged': member_hours,
        })
    
    context = {
        'project': project,
        'completion_rate': completion_rate,
        'total_hours': total_hours,
        'billable_hours': billable_hours,
        'budget_used_percentage': budget_used_percentage,
        'team_stats': team_stats,
    }
    
    return render(request, 'blu_projects/project_reports.html', context)


@login_required
def timeline_view(request):
    """Timeline view of all projects"""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    from django.db.models import Count, Q
    
    status_filter = request.GET.get('status', '')
    projects = Project.objects.filter(company=company).annotate(
        total_tasks=Count('tasks'),
        completed_tasks=Count('tasks', filter=Q(tasks__status='COMPLETED')),
        member_count=Count('team_members', distinct=True),
    ).order_by('start_date')
    
    if status_filter:
        projects = projects.filter(status=status_filter)
    
    # Summary stats
    all_projects = Project.objects.filter(company=company)
    total_projects = projects.count()
    active_projects = projects.filter(status='ACTIVE').count()
    completed_projects = projects.filter(status='COMPLETED').count()
    planning_projects = projects.filter(status='PLANNING').count()
    on_hold_projects = projects.filter(status='ON_HOLD').count()

    # Calculate global date range for Gantt bar positioning
    from datetime import date
    dated_projects = [p for p in projects if p.start_date and p.end_date]
    if dated_projects:
        gantt_start = min(p.start_date for p in dated_projects)
        gantt_end = max(p.end_date for p in dated_projects)
        gantt_total_days = max((gantt_end - gantt_start).days, 1)
    else:
        gantt_start = date.today()
        gantt_end = date.today()
        gantt_total_days = 1

    # Annotate each project with Gantt bar position/width percentages
    today = date.today()
    projects_gantt = []
    for p in projects:
        if p.start_date and p.end_date:
            left_days = max((p.start_date - gantt_start).days, 0)
            width_days = max((p.end_date - p.start_date).days, 1)
            left_pct = round(left_days / gantt_total_days * 100, 1)
            width_pct = min(round(width_days / gantt_total_days * 100, 1), 100 - left_pct)
            width_pct = max(width_pct, 2)
            overdue = p.end_date < today and p.status not in ('COMPLETED', 'CANCELLED')
        else:
            left_pct = 0
            width_pct = 100
            overdue = False
        projects_gantt.append({
            'project': p,
            'left_pct': left_pct,
            'width_pct': width_pct,
            'overdue': overdue,
        })

    context = {
        'projects': projects,
        'projects_gantt': projects_gantt,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'planning_projects': planning_projects,
        'on_hold_projects': on_hold_projects,
        'status_filter': status_filter,
        'gantt_start': gantt_start,
        'gantt_end': gantt_end,
        'today': today,
        'is_admin': _is_pms_admin(user),
    }

    return render(request, 'blu_projects/timeline_view.html', context)


@login_required
def calendar_view(request):
    """Calendar view of projects and tasks — full month grid"""
    user = request.user
    company = user.company

    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')

    import calendar as cal_mod
    from datetime import date

    today = date.today()
    is_admin = _is_pms_admin(user)

    # Month/year navigation
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if month < 1:
            month = 12; year -= 1
        if month > 12:
            month = 1; year += 1
    except (ValueError, TypeError):
        year, month = today.year, today.month

    # Prev / next month links
    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = (month % 12) + 1
    next_year = year + 1 if month == 12 else year

    # Date range for this month
    first_day = date(year, month, 1)
    last_day = date(year, month, cal_mod.monthrange(year, month)[1])

    # Project filter
    project_filter = request.GET.get('project', '')
    projects_qs = Project.objects.filter(company=company).order_by('name')
    if not is_admin:
        projects_qs = projects_qs.filter(team_members=user)

    tasks_qs = Task.objects.filter(
        project__company=company,
        due_date__gte=first_day,
        due_date__lte=last_day,
    ).select_related('project', 'assigned_to').exclude(status='COMPLETED')

    milestones_qs = ProjectMilestone.objects.filter(
        project__company=company,
        due_date__gte=first_day,
        due_date__lte=last_day,
    ).select_related('project').exclude(status='COMPLETED')

    if project_filter:
        tasks_qs = tasks_qs.filter(project_id=project_filter)
        milestones_qs = milestones_qs.filter(project_id=project_filter)

    # Build events dict keyed by day number
    events = {}  # {day: [{'type', 'label', 'color', 'url'}]}

    # Assign a colour per project (cycle through palette)
    PROJECT_COLOURS = ['#1d4ed8', '#7c3aed', '#059669', '#d97706', '#dc2626',
                       '#0891b2', '#be185d', '#65a30d', '#ea580c', '#6366f1']
    proj_colours = {}
    for i, p in enumerate(projects_qs):
        proj_colours[p.id] = PROJECT_COLOURS[i % len(PROJECT_COLOURS)]

    for task in tasks_qs:
        day = task.due_date.day
        events.setdefault(day, []).append({
            'type': 'task',
            'label': task.title,
            'project': task.project.name,
            'color': proj_colours.get(task.project_id, '#1d4ed8'),
            'url': f'/projects/tasks/{task.id}/',
            'priority': task.priority,
        })

    for ms in milestones_qs:
        day = ms.due_date.day
        events.setdefault(day, []).append({
            'type': 'milestone',
            'label': ms.name,
            'project': ms.project.name,
            'color': '#7c3aed',
            'url': f'/projects/{ms.project_id}/',
        })

    # Also mark project start/end dates
    for proj in projects_qs:
        if proj.start_date and proj.start_date.year == year and proj.start_date.month == month:
            d = proj.start_date.day
            events.setdefault(d, []).append({
                'type': 'project_start',
                'label': f'Start: {proj.name}',
                'project': proj.name,
                'color': proj_colours.get(proj.id, '#16a34a'),
                'url': f'/projects/{proj.id}/',
            })
        if proj.end_date and proj.end_date.year == year and proj.end_date.month == month:
            d = proj.end_date.day
            events.setdefault(d, []).append({
                'type': 'project_end',
                'label': f'End: {proj.name}',
                'project': proj.name,
                'color': proj_colours.get(proj.id, '#dc2626'),
                'url': f'/projects/{proj.id}/',
            })

    # Build calendar grid: list of weeks, each week is list of day numbers (0 = empty)
    cal_matrix = cal_mod.monthcalendar(year, month)

    # Overdue tasks (for alert banner)
    overdue_tasks = Task.objects.filter(
        project__company=company,
        due_date__lt=today,
    ).exclude(status='COMPLETED').select_related('project').order_by('due_date')[:8]

    # Month stats
    month_tasks_total = tasks_qs.count()
    month_milestones_total = milestones_qs.count()

    context = {
        'today': today,
        'year': year,
        'month': month,
        'month_name': first_day.strftime('%B %Y'),
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'cal_matrix': cal_matrix,
        'events': events,
        'projects': projects_qs,
        'project_filter': project_filter,
        'overdue_tasks': overdue_tasks,
        'month_tasks_total': month_tasks_total,
        'month_milestones_total': month_milestones_total,
        'proj_colours': proj_colours,
        'is_admin': is_admin,
        'DAY_NAMES': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    }

    return render(request, 'blu_projects/calendar_view.html', context)


@login_required
def reports_view(request):
    """Company-wide reports and analytics — comprehensive metrics"""
    user = request.user
    company = user.company

    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')

    from django.db.models import Count, Q, Avg
    from datetime import date

    today = date.today()
    projects = Project.objects.filter(company=company)
    all_tasks = Task.objects.filter(project__company=company)
    all_risks = ProjectRisk.objects.filter(project__company=company)

    # === PROJECT METRICS ===
    total_projects = projects.count()
    active_projects = projects.filter(status__in=['ACTIVE', 'IN_PROGRESS']).count()
    completed_projects = projects.filter(status='COMPLETED').count()
    on_hold_projects = projects.filter(status='ON_HOLD').count()
    planning_projects = projects.filter(status='PLANNING').count()
    overdue_projects = projects.filter(end_date__lt=today).exclude(
        status__in=['COMPLETED', 'CANCELLED']).count()

    # === TASK METRICS ===
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(status='COMPLETED').count()
    in_progress_tasks = all_tasks.filter(status='IN_PROGRESS').count()
    overdue_tasks = all_tasks.filter(due_date__lt=today).exclude(status='COMPLETED').count()
    task_completion_rate = round(completed_tasks / total_tasks * 100, 1) if total_tasks else 0

    # === TIME METRICS ===
    time_entries_qs = TimeEntry.objects.filter(task__project__company=company)
    total_hours = time_entries_qs.aggregate(total=Sum('hours'))['total'] or 0
    billable_hours = time_entries_qs.filter(is_billable=True).aggregate(total=Sum('hours'))['total'] or 0
    non_billable_hours = float(total_hours) - float(billable_hours)

    # === BUDGET METRICS ===
    budget_data = projects.aggregate(
        total_budget=Sum('budget'),
        total_funded=Sum('funding_amount'),
        total_actual=Sum('actual_cost'),
    )
    total_budget = budget_data['total_budget'] or 0
    total_funded = budget_data['total_funded'] or 0
    total_actual_cost = budget_data['total_actual'] or 0
    budget_utilisation = round(float(total_actual_cost) / float(total_budget) * 100, 1) if total_budget else 0

    # === RISK METRICS ===
    open_risks = all_risks.filter(status='OPEN').count()
    critical_risks = all_risks.filter(status='OPEN', probability__gte=4, impact__gte=4).count()
    high_risks = all_risks.filter(status='OPEN', probability__gte=3, impact__gte=3).count()
    closed_risks = all_risks.filter(status='CLOSED').count()

    # === STATUS BREAKDOWN ===
    status_breakdown = list(
        projects.values('status')
        .annotate(n=Count('id'))
        .order_by('-n')
    )
    type_breakdown = list(
        projects.values('project_type')
        .annotate(n=Count('id'))
        .order_by('-n')[:6]
    )
    sector_breakdown = list(
        projects.values('sector')
        .annotate(n=Count('id'))
        .order_by('-n')[:6]
    )

    # === PER-PROJECT TABLE ===
    project_table = []
    for p in projects.order_by('-updated_at')[:20]:
        p_tasks = all_tasks.filter(project=p)
        p_total = p_tasks.count()
        p_done = p_tasks.filter(status='COMPLETED').count()
        p_rate = round(p_done / p_total * 100) if p_total else 0
        p_hours = time_entries_qs.filter(task__project=p).aggregate(h=Sum('hours'))['h'] or 0
        p_overdue = p_tasks.filter(due_date__lt=today).exclude(status='COMPLETED').count()
        project_table.append({
            'project': p,
            'total_tasks': p_total,
            'completed_tasks': p_done,
            'completion_rate': p_rate,
            'hours_logged': round(float(p_hours), 1),
            'overdue_tasks': p_overdue,
            'is_overdue': p.end_date and p.end_date < today and p.status not in ('COMPLETED', 'CANCELLED'),
        })

    # === TEAM WORKLOAD ===
    User = get_user_model()
    team_workload = []
    for member in User.objects.filter(company=company, is_active=True)[:10]:
        m_tasks = all_tasks.filter(assigned_to=member)
        if m_tasks.count() == 0:
            continue
        m_done = m_tasks.filter(status='COMPLETED').count()
        m_hours = time_entries_qs.filter(user=member).aggregate(h=Sum('hours'))['h'] or 0
        team_workload.append({
            'member': member,
            'total_tasks': m_tasks.count(),
            'completed_tasks': m_done,
            'hours_logged': round(float(m_hours), 1),
            'completion_rate': round(m_done / m_tasks.count() * 100) if m_tasks.count() else 0,
        })

    context = {
        'today': today,
        'is_admin': _is_pms_admin(user),
        # Project metrics
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'on_hold_projects': on_hold_projects,
        'planning_projects': planning_projects,
        'overdue_projects': overdue_projects,
        # Task metrics
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'overdue_tasks': overdue_tasks,
        'task_completion_rate': task_completion_rate,
        # Time metrics
        'total_hours': total_hours,
        'billable_hours': billable_hours,
        'non_billable_hours': round(non_billable_hours, 1),
        # Budget metrics
        'total_budget': total_budget,
        'total_funded': total_funded,
        'total_actual_cost': total_actual_cost,
        'budget_utilisation': budget_utilisation,
        # Risk metrics
        'open_risks': open_risks,
        'critical_risks': critical_risks,
        'high_risks': high_risks,
        'closed_risks': closed_risks,
        # Breakdowns
        'status_breakdown': status_breakdown,
        'type_breakdown': type_breakdown,
        'sector_breakdown': sector_breakdown,
        # Tables
        'project_table': project_table,
        'team_workload': team_workload,
    }

    return render(request, 'blu_projects/reports_view.html', context)


@login_required
def team_management(request):
    """Team management — only shows members assigned to at least one project"""
    user = request.user
    company = user.company

    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')

    from django.db.models import Count
    _User = get_user_model()

    # Members who are on at least one project's team OR have tasks assigned
    member_ids_from_projects = Project.objects.filter(company=company).values_list(
        'team_members', flat=True).distinct()
    member_ids_from_tasks = Task.objects.filter(
        project__company=company).exclude(assigned_to=None).values_list(
        'assigned_to', flat=True).distinct()

    active_member_ids = set(list(member_ids_from_projects) + list(member_ids_from_tasks))
    # Always include project managers
    pm_ids = Project.objects.filter(company=company).exclude(
        project_manager=None).values_list('project_manager', flat=True).distinct()
    active_member_ids |= set(pm_ids)
    # Remove None
    active_member_ids.discard(None)

    team_members = _User.objects.filter(
        id__in=active_member_ids, company=company, is_active=True
    ).order_by('first_name', 'last_name')

    # Search / filter
    search = request.GET.get('search', '')
    if search:
        team_members = team_members.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )

    # Stats per member
    team_stats = []
    for member in team_members:
        member_projects = Project.objects.filter(company=company, team_members=member)
        tasks_qs = Task.objects.filter(assigned_to=member, project__company=company)
        hours = TimeEntry.objects.filter(
            user=member, task__project__company=company
        ).aggregate(total=Sum('hours'))['total'] or 0
        task_total = tasks_qs.count()
        task_done = tasks_qs.filter(status='COMPLETED').count()
        team_stats.append({
            'member': member,
            'projects': list(member_projects[:4]),
            'projects_count': member_projects.count(),
            'tasks_assigned': task_total,
            'tasks_completed': task_done,
            'completion_rate': round(task_done / task_total * 100) if task_total else 0,
            'hours_logged': round(float(hours), 1),
            'is_pm': Project.objects.filter(company=company, project_manager=member).exists(),
        })

    context = {
        'team_stats': team_stats,
        'search': search,
        'total_members': len(team_stats),
        'is_admin': _is_pms_admin(user),
    }

    return render(request, 'blu_projects/team_management.html', context)


@login_required
def project_settings(request):
    """Project module settings — supports POST save via session"""
    user = request.user
    company = user.company

    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')

    SESSION_KEY = f'pms_settings_{company.id}'

    # Load saved settings from session
    saved = request.session.get(SESSION_KEY, {})

    if request.method == 'POST':
        section = request.POST.get('section', 'general')
        # Persist all posted values for this section
        section_data = {}
        for key, val in request.POST.items():
            if key not in ('csrfmiddlewaretoken', 'section'):
                section_data[key] = val
        saved[section] = section_data
        request.session[SESSION_KEY] = saved
        request.session.modified = True
        messages.success(request, f'Settings saved for section: {section.replace("_", " ").title()}')
        return redirect(f'{request.path}?tab={section}')

    # Load active tab
    active_tab = request.GET.get('tab', 'general')

    _User = get_user_model()
    total_projects = Project.objects.filter(company=company).count()
    active_projects = Project.objects.filter(company=company, status__in=['ACTIVE', 'IN_PROGRESS']).count()
    total_tasks = Task.objects.filter(project__company=company).count()
    completed_tasks = Task.objects.filter(project__company=company, status='COMPLETED').count()
    total_members = _User.objects.filter(company=company, is_active=True).count()
    hours_logged = TimeEntry.objects.filter(task__project__company=company).aggregate(
        total=Sum('hours'))['total'] or 0

    # Default permissions matrix
    permission_rows = [
        {'label': 'Create Projects',     'admin': True,  'manager': True,  'member': False},
        {'label': 'Edit Projects',       'admin': True,  'manager': True,  'member': False},
        {'label': 'Delete Projects',     'admin': True,  'manager': False, 'member': False},
        {'label': 'Create Tasks',        'admin': True,  'manager': True,  'member': True},
        {'label': 'Assign Team Members', 'admin': True,  'manager': True,  'member': False},
        {'label': 'View All Projects',   'admin': True,  'manager': True,  'member': False},
        {'label': 'Log Time',            'admin': True,  'manager': True,  'member': True},
        {'label': 'View Reports',        'admin': True,  'manager': True,  'member': False},
        {'label': 'Manage Risks',        'admin': True,  'manager': True,  'member': False},
        {'label': 'Manage Settings',     'admin': True,  'manager': False, 'member': False},
    ]
    # Override with saved permissions if any
    saved_perms = saved.get('permissions', {})
    if saved_perms:
        for row in permission_rows:
            key = row['label'].lower().replace(' ', '_')
            if f'{key}_admin' in saved_perms:
                row['admin'] = saved_perms.get(f'{key}_admin') == 'on'
            if f'{key}_manager' in saved_perms:
                row['manager'] = saved_perms.get(f'{key}_manager') == 'on'
            if f'{key}_member' in saved_perms:
                row['member'] = saved_perms.get(f'{key}_member') == 'on'

    # Saved settings values for form pre-fill
    time_settings = saved.get('time', {})
    general_settings = saved.get('general', {})

    context = {
        'company': company,
        'user': user,
        'is_admin': _is_pms_admin(user),
        'active_tab': active_tab,
        'permission_rows': permission_rows,
        'time_settings': time_settings,
        'general_settings': general_settings,
        'saved_settings': saved,
        'stats': {
            'total_projects': total_projects,
            'active_projects': active_projects,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'total_members': total_members,
            'hours_logged': round(float(hours_logged), 1),
        },
    }

    return render(request, 'blu_projects/project_settings.html', context)


# ============================================================================
# TIME ENTRY EDIT & DELETE
# ============================================================================

@login_required
def time_entry_edit(request, entry_id):
    """Edit time entry"""
    entry = get_object_or_404(TimeEntry, id=entry_id, task__project__company=request.user.company)
    
    if request.method == 'POST':
        try:
            entry.hours = Decimal(request.POST.get('hours'))
            entry.date = request.POST.get('date')
            entry.description = request.POST.get('description', '')
            entry.is_billable = request.POST.get('is_billable') == 'on'
            
            hourly_rate = request.POST.get('hourly_rate')
            entry.hourly_rate = Decimal(hourly_rate) if hourly_rate else None
            
            entry.save()
            messages.success(request, 'Time entry updated successfully!')
            return redirect('blu_projects:task_detail', task_id=entry.task.id)
        except Exception as e:
            messages.error(request, f'Error updating time entry: {str(e)}')
    
    context = {
        'entry': entry,
        'task': entry.task,
    }
    
    return render(request, 'blu_projects/time_entry_form.html', context)


@login_required
def time_entry_delete(request, entry_id):
    """Delete time entry"""
    entry = get_object_or_404(TimeEntry, id=entry_id, task__project__company=request.user.company)
    task = entry.task
    
    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Time entry deleted successfully!')
        return redirect('blu_projects:task_detail', task_id=task.id)
    
    return redirect('blu_projects:task_detail', task_id=task.id)


# ============================================================================
# MILESTONE CRUD
# ============================================================================

@login_required
def milestone_create(request, project_id):
    """Create milestone"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    if request.method == 'POST':
        try:
            milestone = ProjectMilestone.objects.create(
                project=project,
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                due_date=request.POST.get('due_date'),
                status=request.POST.get('status', 'PENDING')
            )
            messages.success(request, f'Milestone "{milestone.name}" created successfully!')
            return redirect('blu_projects:project_detail', project_id=project.id)
        except Exception as e:
            messages.error(request, f'Error creating milestone: {str(e)}')
    
    context = {
        'project': project,
    }
    
    return render(request, 'blu_projects/milestone_form.html', context)


@login_required
def milestone_edit(request, milestone_id):
    """Edit milestone"""
    milestone = get_object_or_404(ProjectMilestone, id=milestone_id, project__company=request.user.company)
    
    if request.method == 'POST':
        try:
            milestone.name = request.POST.get('name')
            milestone.description = request.POST.get('description', '')
            milestone.due_date = request.POST.get('due_date')
            milestone.status = request.POST.get('status')
            milestone.save()
            
            messages.success(request, f'Milestone "{milestone.name}" updated successfully!')
            return redirect('blu_projects:project_detail', project_id=milestone.project.id)
        except Exception as e:
            messages.error(request, f'Error updating milestone: {str(e)}')
    
    context = {
        'milestone': milestone,
        'project': milestone.project,
        'edit_mode': True,
    }
    
    return render(request, 'blu_projects/milestone_form.html', context)


@login_required
def milestone_delete(request, milestone_id):
    """Delete milestone"""
    milestone = get_object_or_404(ProjectMilestone, id=milestone_id, project__company=request.user.company)
    project = milestone.project
    
    if request.method == 'POST':
        milestone_name = milestone.name
        milestone.delete()
        messages.success(request, f'Milestone "{milestone_name}" deleted successfully!')
        return redirect('blu_projects:project_detail', project_id=project.id)
    
    context = {
        'milestone': milestone,
        'project': project,
    }
    
    return render(request, 'blu_projects/milestone_confirm_delete.html', context)


# ============================================================================
# DOCUMENT MANAGEMENT
# ============================================================================

@login_required
def document_upload(request, project_id):
    """Upload document"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            uploaded_file = request.FILES['file']
            document = ProjectDocument.objects.create(
                project=project,
                uploaded_by=request.user,
                file=uploaded_file,
                name=request.POST.get('name', uploaded_file.name),
                description=request.POST.get('description', ''),
                category=request.POST.get('category', 'OTHER')
            )
            messages.success(request, f'Document "{document.name}" uploaded successfully!')
            return redirect('blu_projects:project_detail', project_id=project.id)
        except Exception as e:
            messages.error(request, f'Error uploading document: {str(e)}')
    
    context = {
        'project': project,
    }
    
    return render(request, 'blu_projects/document_upload.html', context)


@login_required
def document_delete(request, document_id):
    """Delete document"""
    document = get_object_or_404(ProjectDocument, id=document_id, project__company=request.user.company)
    project = document.project
    
    if request.method == 'POST':
        document_name = document.name
        document.file.delete()  # Delete the actual file
        document.delete()
        messages.success(request, f'Document "{document_name}" deleted successfully!')
        return redirect('blu_projects:project_detail', project_id=project.id)
    
    return redirect('blu_projects:project_detail', project_id=project.id)


# ============================================================================
# PROJECT DELETE & ARCHIVE
# ============================================================================

@login_required
def project_delete(request, project_id):
    """Delete project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    if request.method == 'POST':
        project_name = project.name
        project.delete()
        messages.success(request, f'Project "{project_name}" deleted successfully!')
        return redirect('blu_projects:projects_list')
    
    context = {
        'project': project,
    }
    
    return render(request, 'blu_projects/project_confirm_delete.html', context)


@login_required
def project_archive(request, project_id):
    """Archive project (set status to CANCELLED)"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    if request.method == 'POST':
        project.status = 'CANCELLED'
        project.save()
        messages.success(request, f'Project "{project.name}" archived successfully!')
        return redirect('blu_projects:project_detail', project_id=project.id)
    
    return redirect('blu_projects:project_detail', project_id=project.id)


# ============================================================================
# CLIENT PORTAL VIEWS
# ============================================================================

from .models import ClientAccess, ClientIssue, IssueComment, IssueAttachment, ProjectSLA


@login_required
def client_portal_home(request):
    """Client portal dashboard - shows projects client has access to"""
    user = request.user
    
    # Get projects where user is a client
    client_projects = ClientAccess.objects.filter(user=user).select_related('project')
    
    # Get issues reported by this client
    my_issues = ClientIssue.objects.filter(reported_by=user).order_by('-reported_at')[:10]
    
    # Statistics
    total_projects = client_projects.count()
    open_issues = ClientIssue.objects.filter(reported_by=user, status__in=['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS']).count()
    resolved_issues = ClientIssue.objects.filter(reported_by=user, status='RESOLVED').count()
    
    context = {
        'client_projects': client_projects,
        'my_issues': my_issues,
        'total_projects': total_projects,
        'open_issues': open_issues,
        'resolved_issues': resolved_issues,
    }
    
    return render(request, 'blu_projects/client_portal_home.html', context)


@login_required
def client_project_view(request, project_id):
    """Client view of a specific project"""
    project = get_object_or_404(Project, id=project_id)
    
    # Check if user has client access
    try:
        client_access = ClientAccess.objects.get(user=request.user, project=project)
    except ClientAccess.DoesNotExist:
        # If not a client, check if they're a team member
        if request.user not in project.team_members.all() and project.project_manager != request.user:
            messages.error(request, "You don't have access to this project.")
            return redirect('blu_projects:client_portal_home')
        client_access = None
    
    # Get project issues
    issues = project.client_issues.all()
    
    # Get SLA info
    sla = getattr(project, 'sla', None)
    
    # Statistics
    open_issues = issues.filter(status__in=['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS']).count()
    resolved_issues = issues.filter(status='RESOLVED').count()
    sla_breached = issues.filter(resolution_sla_breached=True).count()
    
    context = {
        'project': project,
        'client_access': client_access,
        'issues': issues[:20],
        'sla': sla,
        'open_issues': open_issues,
        'resolved_issues': resolved_issues,
        'sla_breached': sla_breached,
    }
    
    return render(request, 'blu_projects/client_project_view.html', context)


# ============================================================================
# ISSUE MANAGEMENT
# ============================================================================

@login_required
def issue_list(request, project_id):
    """List all issues for a project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    issues = project.client_issues.all()
    
    # Filters
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    
    if status_filter:
        issues = issues.filter(status=status_filter)
    if priority_filter:
        issues = issues.filter(priority=priority_filter)
    
    # Check for SLA breaches
    for issue in issues:
        if issue.status not in ['RESOLVED', 'CLOSED']:
            issue.check_sla_breach()
    
    context = {
        'project': project,
        'issues': issues,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
    }
    
    return render(request, 'blu_projects/issue_list.html', context)


@login_required
def issue_create(request, project_id):
    """Create new issue"""
    project = get_object_or_404(Project, id=project_id)
    
    # Check access
    try:
        client_access = ClientAccess.objects.get(user=request.user, project=project)
        if client_access.access_level == 'VIEW':
            messages.error(request, "You don't have permission to create issues.")
            return redirect('blu_projects:client_project_view', project_id=project.id)
    except ClientAccess.DoesNotExist:
        # Check if team member
        if request.user.company != project.company:
            messages.error(request, "You don't have access to this project.")
            return redirect('blu_projects:client_portal_home')
    
    if request.method == 'POST':
        try:
            # Check if project is in maintenance
            is_maintenance = False
            if hasattr(project, 'sla') and project.sla.is_maintenance_active():
                is_maintenance = True
            
            issue = ClientIssue.objects.create(
                project=project,
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                priority=request.POST.get('priority', 'MEDIUM'),
                category=request.POST.get('category', 'SUPPORT'),
                reported_by=request.user,
                is_maintenance_issue=is_maintenance
            )
            
            messages.success(request, f'Issue {issue.issue_number} created successfully!')
            return redirect('blu_projects:issue_detail', issue_id=issue.id)
        except Exception as e:
            messages.error(request, f'Error creating issue: {str(e)}')
    
    context = {
        'project': project,
    }
    
    return render(request, 'blu_projects/issue_form.html', context)


@login_required
def issue_detail(request, issue_id):
    """View issue details"""
    issue = get_object_or_404(ClientIssue, id=issue_id)
    project = issue.project
    
    # Check access
    can_view_internal = False
    try:
        client_access = ClientAccess.objects.get(user=request.user, project=project)
        can_view_internal = client_access.can_view_internal_notes
    except ClientAccess.DoesNotExist:
        # Team members can see internal notes
        if request.user.company == project.company:
            can_view_internal = True
        else:
            messages.error(request, "You don't have access to this issue.")
            return redirect('blu_projects:client_portal_home')
    
    # Get comments
    comments = issue.comments.all()
    if not can_view_internal:
        comments = comments.filter(is_internal=False)
    
    # Get attachments
    attachments = issue.attachments.all()
    
    # Check SLA
    issue.check_sla_breach()
    
    # Get SLA info
    sla = getattr(project, 'sla', None)
    sla_info = None
    if sla:
        response_times = {
            'CRITICAL': sla.critical_response_time,
            'HIGH': sla.high_response_time,
            'MEDIUM': sla.medium_response_time,
            'LOW': sla.low_response_time,
        }
        resolution_times = {
            'CRITICAL': sla.critical_resolution_time,
            'HIGH': sla.high_resolution_time,
            'MEDIUM': sla.medium_resolution_time,
            'LOW': sla.low_resolution_time,
        }
        sla_info = {
            'response_time': response_times.get(issue.priority, 24),
            'resolution_time': resolution_times.get(issue.priority, 72),
        }
    
    context = {
        'issue': issue,
        'project': project,
        'comments': comments,
        'attachments': attachments,
        'can_view_internal': can_view_internal,
        'sla_info': sla_info,
    }
    
    return render(request, 'blu_projects/issue_detail.html', context)


@login_required
def issue_add_comment(request, issue_id):
    """Add comment to issue"""
    issue = get_object_or_404(ClientIssue, id=issue_id)
    
    if request.method == 'POST':
        comment_text = request.POST.get('comment')
        is_internal = request.POST.get('is_internal') == 'on'
        is_resolution = request.POST.get('is_resolution') == 'on'
        
        IssueComment.objects.create(
            issue=issue,
            user=request.user,
            comment=comment_text,
            is_internal=is_internal,
            is_resolution=is_resolution
        )
        
        # If this is the first response, mark as acknowledged
        if not issue.acknowledged_at and request.user.company == issue.project.company:
            issue.acknowledged_at = timezone.now()
            issue.save()
        
        # If marked as resolution, update issue status
        if is_resolution:
            issue.status = 'RESOLVED'
            issue.resolved_at = timezone.now()
            issue.save()
        
        messages.success(request, 'Comment added successfully!')
    
    return redirect('blu_projects:issue_detail', issue_id=issue.id)


@login_required
def issue_update_status(request, issue_id):
    """Update issue status"""
    issue = get_object_or_404(ClientIssue, id=issue_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        old_status = issue.status
        issue.status = new_status
        
        # Update timestamps
        if new_status == 'ACKNOWLEDGED' and not issue.acknowledged_at:
            issue.acknowledged_at = timezone.now()
        elif new_status == 'RESOLVED' and not issue.resolved_at:
            issue.resolved_at = timezone.now()
        elif new_status == 'CLOSED' and not issue.closed_at:
            issue.closed_at = timezone.now()
        
        issue.save()
        
        messages.success(request, f'Issue status updated from {old_status} to {new_status}')
    
    return redirect('blu_projects:issue_detail', issue_id=issue.id)


@login_required
def issue_attach_file(request, issue_id):
    """Attach file to issue"""
    issue = get_object_or_404(ClientIssue, id=issue_id)
    
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        
        IssueAttachment.objects.create(
            issue=issue,
            uploaded_by=request.user,
            file=uploaded_file,
            filename=uploaded_file.name,
            file_size=uploaded_file.size
        )
        
        issue.attachments_count += 1
        issue.save()
        
        messages.success(request, 'File attached successfully!')
    
    return redirect('blu_projects:issue_detail', issue_id=issue.id)


# ============================================================================
# SLA MANAGEMENT
# ============================================================================

@login_required
def sla_view(request, project_id):
    """View SLA for a project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    sla = getattr(project, 'sla', None)
    
    context = {
        'project': project,
        'sla': sla,
    }
    
    return render(request, 'blu_projects/sla_view.html', context)


@login_required
def sla_create(request, project_id):
    """Create SLA for a project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    if hasattr(project, 'sla'):
        messages.error(request, 'SLA already exists for this project.')
        return redirect('blu_projects:sla_view', project_id=project.id)
    
    if request.method == 'POST':
        try:
            ProjectSLA.objects.create(
                project=project,
                critical_response_time=request.POST.get('critical_response_time', 2),
                high_response_time=request.POST.get('high_response_time', 8),
                medium_response_time=request.POST.get('medium_response_time', 24),
                low_response_time=request.POST.get('low_response_time', 48),
                critical_resolution_time=request.POST.get('critical_resolution_time', 8),
                high_resolution_time=request.POST.get('high_resolution_time', 24),
                medium_resolution_time=request.POST.get('medium_resolution_time', 72),
                low_resolution_time=request.POST.get('low_resolution_time', 120),
                support_hours=request.POST.get('support_hours', '9 AM - 5 PM, Mon-Fri'),
                support_email=request.POST.get('support_email', ''),
                support_phone=request.POST.get('support_phone', ''),
                maintenance_start_date=request.POST.get('maintenance_start_date') or None,
                maintenance_end_date=request.POST.get('maintenance_end_date') or None,
                maintenance_terms=request.POST.get('maintenance_terms', '')
            )
            messages.success(request, 'SLA created successfully!')
            return redirect('blu_projects:sla_view', project_id=project.id)
        except Exception as e:
            messages.error(request, f'Error creating SLA: {str(e)}')
    
    context = {
        'project': project,
    }
    
    return render(request, 'blu_projects/sla_form.html', context)


@login_required
def sla_edit(request, project_id):
    """Edit SLA for a project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    sla = get_object_or_404(ProjectSLA, project=project)
    
    if request.method == 'POST':
        try:
            sla.critical_response_time = request.POST.get('critical_response_time', 2)
            sla.high_response_time = request.POST.get('high_response_time', 8)
            sla.medium_response_time = request.POST.get('medium_response_time', 24)
            sla.low_response_time = request.POST.get('low_response_time', 48)
            sla.critical_resolution_time = request.POST.get('critical_resolution_time', 8)
            sla.high_resolution_time = request.POST.get('high_resolution_time', 24)
            sla.medium_resolution_time = request.POST.get('medium_resolution_time', 72)
            sla.low_resolution_time = request.POST.get('low_resolution_time', 120)
            sla.support_hours = request.POST.get('support_hours', '9 AM - 5 PM, Mon-Fri')
            sla.support_email = request.POST.get('support_email', '')
            sla.support_phone = request.POST.get('support_phone', '')
            sla.maintenance_start_date = request.POST.get('maintenance_start_date') or None
            sla.maintenance_end_date = request.POST.get('maintenance_end_date') or None
            sla.maintenance_terms = request.POST.get('maintenance_terms', '')
            sla.save()
            
            messages.success(request, 'SLA updated successfully!')
            return redirect('blu_projects:sla_view', project_id=project.id)
        except Exception as e:
            messages.error(request, f'Error updating SLA: {str(e)}')
    
    context = {
        'project': project,
        'sla': sla,
        'edit_mode': True,
    }
    
    return render(request, 'blu_projects/sla_form.html', context)


@login_required
def sla_dashboard(request):
    """SLA compliance dashboard"""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    # Get all projects with SLA
    projects_with_sla = Project.objects.filter(company=company, sla__isnull=False)
    
    # Get issues at risk
    at_risk_issues = ClientIssue.objects.filter(
        project__company=company,
        status__in=['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS']
    )
    
    # Check SLA for all open issues
    for issue in at_risk_issues:
        issue.check_sla_breach()
    
    # Statistics
    total_issues = ClientIssue.objects.filter(project__company=company).count()
    breached_issues = ClientIssue.objects.filter(project__company=company, resolution_sla_breached=True).count()
    open_issues = ClientIssue.objects.filter(project__company=company, status__in=['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS']).count()
    
    # Get issues breaching SLA
    sla_breached = at_risk_issues.filter(resolution_sla_breached=True)
    
    context = {
        'projects_with_sla': projects_with_sla,
        'total_issues': total_issues,
        'breached_issues': breached_issues,
        'open_issues': open_issues,
        'sla_breached': sla_breached,
        'at_risk_issues': at_risk_issues[:20],
    }
    
    return render(request, 'blu_projects/sla_dashboard.html', context)


# ============================================================================
# RISK REGISTER VIEWS
# ============================================================================

@login_required
def risk_create(request, project_id):
    """Create a risk entry for a project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    if request.method == 'POST':
        try:
            ProjectRisk.objects.create(
                project=project,
                title=request.POST.get('title'),
                description=request.POST.get('description', ''),
                category=request.POST.get('category', 'OTHER'),
                status=request.POST.get('status', 'OPEN'),
                probability=int(request.POST.get('probability', 2)),
                impact=int(request.POST.get('impact', 2)),
                mitigation_plan=request.POST.get('mitigation_plan', ''),
                contingency_plan=request.POST.get('contingency_plan', ''),
                risk_owner_id=request.POST.get('risk_owner') or None,
                review_date=request.POST.get('review_date') or None,
                created_by=request.user,
            )
            messages.success(request, 'Risk added to register.')
        except Exception as e:
            messages.error(request, f'Error adding risk: {e}')
    return redirect('blu_projects:project_detail', project_id=project_id)


@login_required
def risk_edit(request, risk_id):
    """Edit a risk entry"""
    risk = get_object_or_404(ProjectRisk, id=risk_id, project__company=request.user.company)
    if request.method == 'POST':
        try:
            risk.title = request.POST.get('title', risk.title)
            risk.description = request.POST.get('description', risk.description)
            risk.category = request.POST.get('category', risk.category)
            risk.status = request.POST.get('status', risk.status)
            risk.probability = int(request.POST.get('probability', risk.probability))
            risk.impact = int(request.POST.get('impact', risk.impact))
            risk.mitigation_plan = request.POST.get('mitigation_plan', risk.mitigation_plan)
            risk.contingency_plan = request.POST.get('contingency_plan', risk.contingency_plan)
            risk.risk_owner_id = request.POST.get('risk_owner') or None
            risk.review_date = request.POST.get('review_date') or None
            risk.save()
            messages.success(request, 'Risk updated.')
        except Exception as e:
            messages.error(request, f'Error updating risk: {e}')
    return redirect('blu_projects:project_detail', project_id=risk.project_id)


@login_required
def risk_delete(request, risk_id):
    """Delete a risk entry"""
    risk = get_object_or_404(ProjectRisk, id=risk_id, project__company=request.user.company)
    project_id = risk.project_id
    if request.method == 'POST':
        risk.delete()
        messages.success(request, 'Risk removed from register.')
    return redirect('blu_projects:project_detail', project_id=project_id)


# ============================================================================
# STAKEHOLDER REGISTER VIEWS
# ============================================================================

@login_required
def stakeholder_create(request, project_id):
    """Add a stakeholder to a project"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    if request.method == 'POST':
        try:
            ProjectStakeholder.objects.create(
                project=project,
                name=request.POST.get('name'),
                organisation=request.POST.get('organisation', ''),
                role=request.POST.get('role', 'OTHER'),
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
                influence=request.POST.get('influence', 'MEDIUM'),
                interest=request.POST.get('interest', 'MEDIUM'),
                engagement=request.POST.get('engagement', 'NEUTRAL'),
                notes=request.POST.get('notes', ''),
                engagement_strategy=request.POST.get('engagement_strategy', ''),
                created_by=request.user,
            )
            messages.success(request, 'Stakeholder added.')
        except Exception as e:
            messages.error(request, f'Error adding stakeholder: {e}')
    return redirect('blu_projects:project_detail', project_id=project_id)


@login_required
def stakeholder_edit(request, stakeholder_id):
    """Edit a stakeholder"""
    sh = get_object_or_404(ProjectStakeholder, id=stakeholder_id, project__company=request.user.company)
    if request.method == 'POST':
        try:
            sh.name = request.POST.get('name', sh.name)
            sh.organisation = request.POST.get('organisation', sh.organisation)
            sh.role = request.POST.get('role', sh.role)
            sh.email = request.POST.get('email', sh.email)
            sh.phone = request.POST.get('phone', sh.phone)
            sh.influence = request.POST.get('influence', sh.influence)
            sh.interest = request.POST.get('interest', sh.interest)
            sh.engagement = request.POST.get('engagement', sh.engagement)
            sh.notes = request.POST.get('notes', sh.notes)
            sh.engagement_strategy = request.POST.get('engagement_strategy', sh.engagement_strategy)
            sh.save()
            messages.success(request, 'Stakeholder updated.')
        except Exception as e:
            messages.error(request, f'Error updating stakeholder: {e}')
    return redirect('blu_projects:project_detail', project_id=sh.project_id)


@login_required
def stakeholder_delete(request, stakeholder_id):
    """Delete a stakeholder"""
    sh = get_object_or_404(ProjectStakeholder, id=stakeholder_id, project__company=request.user.company)
    project_id = sh.project_id
    if request.method == 'POST':
        sh.delete()
        messages.success(request, 'Stakeholder removed.')
    return redirect('blu_projects:project_detail', project_id=project_id)
