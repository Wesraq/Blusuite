"""
BLU Projects - Views
Comprehensive project management views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from decimal import Decimal
from datetime import timedelta

from .models import (
    Project, ProjectMilestone, Task, TimeEntry,
    TaskComment, ProjectDocument, ProjectActivity
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
    if is_admin:
        stats['company_total'] = Project.objects.filter(company=company).count()
        stats['company_active'] = Project.objects.filter(company=company, status='ACTIVE').count()
    
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
    """Project detail view with tasks, milestones, and team"""
    project = get_object_or_404(Project, id=project_id, company=request.user.company)
    
    # Get related data
    milestones = project.milestones.all()
    tasks = project.tasks.all()
    team_members = project.team_members.all()
    recent_activities = project.activities.all()[:10]
    documents = project.documents.all()[:5]
    
    # Task statistics
    task_stats = {
        'total': tasks.count(),
        'todo': tasks.filter(status='TODO').count(),
        'in_progress': tasks.filter(status='IN_PROGRESS').count(),
        'completed': tasks.filter(status='COMPLETED').count(),
        'blocked': tasks.filter(status='BLOCKED').count(),
    }
    
    # Time tracking
    time_entries = TimeEntry.objects.filter(task__project=project)
    total_hours = time_entries.aggregate(total=Sum('hours'))['total'] or 0
    
    context = {
        'project': project,
        'milestones': milestones,
        'tasks': tasks,
        'team_members': team_members,
        'recent_activities': recent_activities,
        'documents': documents,
        'task_stats': task_stats,
        'total_hours': total_hours,
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
                company=request.user.company,
                status=request.POST.get('status', 'PLANNING'),
                priority=request.POST.get('priority', 'MEDIUM'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                budget=request.POST.get('budget') or None,
                client_name=request.POST.get('client_name', ''),
                client_contact=request.POST.get('client_contact', ''),
                client_email=request.POST.get('client_email', ''),
                project_manager_id=request.POST.get('project_manager') or None,
                created_by=request.user,
            )
            
            # Add team members
            team_member_ids = request.POST.getlist('team_members')
            if team_member_ids:
                project.team_members.set(team_member_ids)

                # Cross-suite notification for each team member
                try:
                    from ems_project.cross_suite_notifications import notify_project_member_added
                    from accounts.models import User as AccUser
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
                from accounts.models import User
                
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
    
    # Get potential team members and managers
    from accounts.models import User
    team_members = User.objects.filter(company=request.user.company, is_active=True)
    
    context = {
        'team_members': team_members,
        'status_choices': Project.STATUS_CHOICES,
        'priority_choices': Project.PRIORITY_CHOICES,
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
            project.status = request.POST.get('status')
            project.priority = request.POST.get('priority')
            project.start_date = request.POST.get('start_date')
            project.end_date = request.POST.get('end_date')
            project.budget = request.POST.get('budget') or None
            project.client_name = request.POST.get('client_name', '')
            project.client_contact = request.POST.get('client_contact', '')
            project.client_email = request.POST.get('client_email', '')
            project.project_manager_id = request.POST.get('project_manager') or None
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
                    from accounts.models import User as AccUser
                    for mid in new_member_ids:
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
                action='UPDATED',
                description=f"Project '{project.name}' updated"
            )
            
            messages.success(request, "Project updated successfully!")
            return redirect('blu_projects:project_detail', project_id=project.id)
            
        except Exception as e:
            messages.error(request, f"Error updating project: {str(e)}")
    
    from accounts.models import User
    team_members = User.objects.filter(company=request.user.company, is_active=True)
    
    context = {
        'project': project,
        'team_members': team_members,
        'status_choices': Project.STATUS_CHOICES,
        'priority_choices': Project.PRIORITY_CHOICES,
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
    
    from accounts.models import User
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
    total_projects = projects.count()
    active_projects = projects.filter(status='ACTIVE').count()
    completed_projects = projects.filter(status='COMPLETED').count()
    
    context = {
        'projects': projects,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'status_filter': status_filter,
    }
    
    return render(request, 'blu_projects/timeline_view.html', context)


@login_required
def calendar_view(request):
    """Calendar view of projects and tasks"""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    from django.db.models import Q
    from datetime import date, timedelta
    
    today = date.today()
    next_30 = today + timedelta(days=30)
    
    projects = Project.objects.filter(company=company).order_by('start_date')
    tasks = Task.objects.filter(project__company=company).order_by('due_date')
    
    upcoming_projects = projects.filter(
        Q(start_date__gte=today, start_date__lte=next_30) |
        Q(end_date__gte=today, end_date__lte=next_30)
    ).order_by('start_date')[:10]
    
    upcoming_tasks = tasks.filter(
        due_date__gte=today, due_date__lte=next_30
    ).exclude(status='COMPLETED').order_by('due_date')[:15]
    
    overdue_tasks = tasks.filter(
        due_date__lt=today
    ).exclude(status='COMPLETED').order_by('due_date')[:10]
    
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='COMPLETED').count()
    in_progress_tasks = tasks.filter(status='IN_PROGRESS').count()
    
    context = {
        'projects': projects,
        'tasks': tasks,
        'upcoming_projects': upcoming_projects,
        'upcoming_tasks': upcoming_tasks,
        'overdue_tasks': overdue_tasks,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'overdue_count': overdue_tasks.count() if overdue_tasks else 0,
        'today': today,
    }
    
    return render(request, 'blu_projects/calendar_view.html', context)


@login_required
def reports_view(request):
    """Company-wide reports and analytics"""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    projects = Project.objects.filter(company=company)
    
    # Overall statistics
    total_projects = projects.count()
    active_projects = projects.filter(status='ACTIVE').count()
    completed_projects = projects.filter(status='COMPLETED').count()
    
    total_tasks = Task.objects.filter(project__company=company).count()
    completed_tasks = Task.objects.filter(project__company=company, status='COMPLETED').count()
    
    total_hours = TimeEntry.objects.filter(task__project__company=company).aggregate(total=Sum('hours'))['total'] or 0
    billable_hours = TimeEntry.objects.filter(task__project__company=company, is_billable=True).aggregate(total=Sum('hours'))['total'] or 0
    
    context = {
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'total_hours': total_hours,
        'billable_hours': billable_hours,
        'projects': projects,
    }
    
    return render(request, 'blu_projects/reports_view.html', context)


@login_required
def team_management(request):
    """Team management and assignments"""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    from accounts.models import User
    team_members = User.objects.filter(company=company, is_active=True)
    
    # Get stats for each team member
    team_stats = []
    for member in team_members:
        projects_count = Project.objects.filter(company=company, team_members=member).count()
        tasks_assigned = Task.objects.filter(assigned_to=member, project__company=company).count()
        tasks_completed = Task.objects.filter(assigned_to=member, project__company=company, status='COMPLETED').count()
        hours_logged = TimeEntry.objects.filter(user=member, task__project__company=company).aggregate(total=Sum('hours'))['total'] or 0
        
        team_stats.append({
            'member': member,
            'projects_count': projects_count,
            'tasks_assigned': tasks_assigned,
            'tasks_completed': tasks_completed,
            'hours_logged': hours_logged,
        })
    
    context = {
        'team_stats': team_stats,
    }
    
    return render(request, 'blu_projects/team_management.html', context)


@login_required
def project_settings(request):
    """Project module settings"""
    user = request.user
    company = user.company
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('dashboard_redirect')
    
    context = {
        'company': company,
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
