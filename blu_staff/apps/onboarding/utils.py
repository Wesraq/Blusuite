"""
Onboarding and Offboarding utility functions for workflow management
"""
from django.utils import timezone
from datetime import timedelta


def create_onboarding_checklist(employee, onboarding_template=None, tenant=None):
    """
    Create an onboarding checklist for a new employee
    
    Args:
        employee: User object with role='EMPLOYEE'
        onboarding_template: Optional template to use
        tenant: Tenant object for multi-tenancy
    
    Returns:
        EmployeeOnboarding object
    """
    from onboarding.models import EmployeeOnboarding, OnboardingTask
    
    # Create onboarding record
    onboarding = EmployeeOnboarding.objects.create(
        employee=employee,
        start_date=timezone.now().date(),
        expected_completion_date=timezone.now().date() + timedelta(days=30),
        status='IN_PROGRESS',
        tenant=tenant
    )
    
    # Default onboarding tasks
    default_tasks = [
        {
            'title': 'Complete Employee Information Form',
            'description': 'Fill out personal details, emergency contacts, and banking information',
            'category': 'DOCUMENTATION',
            'priority': 'HIGH',
            'due_days': 1
        },
        {
            'title': 'Review and Sign Employment Contract',
            'description': 'Read through employment contract and sign',
            'category': 'DOCUMENTATION',
            'priority': 'HIGH',
            'due_days': 2
        },
        {
            'title': 'Upload Required Documents',
            'description': 'Upload ID, certificates, and other required documents',
            'category': 'DOCUMENTATION',
            'priority': 'HIGH',
            'due_days': 3
        },
        {
            'title': 'IT Setup - Email and System Access',
            'description': 'Receive email credentials and system access',
            'category': 'IT_SETUP',
            'priority': 'HIGH',
            'due_days': 1
        },
        {
            'title': 'IT Setup - Hardware Assignment',
            'description': 'Receive laptop, phone, and other equipment',
            'category': 'IT_SETUP',
            'priority': 'MEDIUM',
            'due_days': 3
        },
        {
            'title': 'Company Orientation',
            'description': 'Attend company orientation session',
            'category': 'TRAINING',
            'priority': 'HIGH',
            'due_days': 5
        },
        {
            'title': 'Department Introduction',
            'description': 'Meet team members and department head',
            'category': 'TRAINING',
            'priority': 'MEDIUM',
            'due_days': 5
        },
        {
            'title': 'Review Company Policies',
            'description': 'Read and acknowledge company policies and procedures',
            'category': 'COMPLIANCE',
            'priority': 'HIGH',
            'due_days': 7
        },
        {
            'title': 'Health and Safety Training',
            'description': 'Complete health and safety orientation',
            'category': 'COMPLIANCE',
            'priority': 'HIGH',
            'due_days': 7
        },
        {
            'title': 'Benefits Enrollment',
            'description': 'Review and enroll in company benefits',
            'category': 'HR',
            'priority': 'MEDIUM',
            'due_days': 14
        },
        {
            'title': 'Set Performance Goals',
            'description': 'Meet with manager to set initial performance goals',
            'category': 'HR',
            'priority': 'MEDIUM',
            'due_days': 14
        },
        {
            'title': '30-Day Check-in',
            'description': 'Complete 30-day onboarding review with HR',
            'category': 'HR',
            'priority': 'LOW',
            'due_days': 30
        }
    ]
    
    # Create tasks
    for task_data in default_tasks:
        OnboardingTask.objects.create(
            onboarding=onboarding,
            title=task_data['title'],
            description=task_data['description'],
            category=task_data['category'],
            priority=task_data['priority'],
            due_date=onboarding.start_date + timedelta(days=task_data['due_days']),
            status='PENDING',
            tenant=tenant
        )
    
    # Send notification
    from notifications.utils import notify_onboarding_assigned
    notify_onboarding_assigned(onboarding, tenant=tenant)
    
    return onboarding


def create_offboarding_checklist(employee, last_working_day, reason='', tenant=None):
    """
    Create an offboarding checklist for a departing employee
    
    Args:
        employee: User object
        last_working_day: Date of last working day
        reason: Reason for departure
        tenant: Tenant object for multi-tenancy
    
    Returns:
        EmployeeOffboarding object
    """
    from onboarding.models import EmployeeOffboarding, OffboardingTask
    
    # Create offboarding record
    offboarding = EmployeeOffboarding.objects.create(
        employee=employee,
        initiated_date=timezone.now().date(),
        last_working_day=last_working_day,
        reason=reason,
        status='IN_PROGRESS',
        tenant=tenant
    )
    
    # Default offboarding tasks
    default_tasks = [
        {
            'title': 'Exit Interview',
            'description': 'Conduct exit interview with HR',
            'category': 'HR',
            'priority': 'HIGH',
            'due_days': -5  # 5 days before last day
        },
        {
            'title': 'Knowledge Transfer',
            'description': 'Document and transfer knowledge to team',
            'category': 'HANDOVER',
            'priority': 'HIGH',
            'due_days': -7
        },
        {
            'title': 'Project Handover',
            'description': 'Complete handover of ongoing projects',
            'category': 'HANDOVER',
            'priority': 'HIGH',
            'due_days': -3
        },
        {
            'title': 'Return Company Assets',
            'description': 'Return laptop, phone, ID card, and other company property',
            'category': 'IT_ASSETS',
            'priority': 'HIGH',
            'due_days': 0
        },
        {
            'title': 'Revoke System Access',
            'description': 'Disable email, system access, and credentials',
            'category': 'IT_ASSETS',
            'priority': 'HIGH',
            'due_days': 0
        },
        {
            'title': 'Final Payroll Processing',
            'description': 'Process final salary, benefits, and settlements',
            'category': 'FINANCE',
            'priority': 'HIGH',
            'due_days': 7
        },
        {
            'title': 'Benefits Termination',
            'description': 'Process termination of benefits and insurance',
            'category': 'FINANCE',
            'priority': 'MEDIUM',
            'due_days': 7
        },
        {
            'title': 'Issue Service Certificate',
            'description': 'Prepare and issue service/experience certificate',
            'category': 'DOCUMENTATION',
            'priority': 'MEDIUM',
            'due_days': 14
        },
        {
            'title': 'Clear Outstanding Dues',
            'description': 'Settle any outstanding loans or advances',
            'category': 'FINANCE',
            'priority': 'HIGH',
            'due_days': 0
        },
        {
            'title': 'Update Records',
            'description': 'Update employee status in all systems',
            'category': 'DOCUMENTATION',
            'priority': 'MEDIUM',
            'due_days': 1
        }
    ]
    
    # Create tasks
    for task_data in default_tasks:
        due_date = last_working_day + timedelta(days=task_data['due_days'])
        OffboardingTask.objects.create(
            offboarding=offboarding,
            title=task_data['title'],
            description=task_data['description'],
            category=task_data['category'],
            priority=task_data['priority'],
            due_date=due_date,
            status='PENDING',
            tenant=tenant
        )
    
    return offboarding


def complete_onboarding_task(task, completed_by, notes=''):
    """Mark an onboarding task as complete"""
    task.status = 'COMPLETED'
    task.completed_date = timezone.now().date()
    task.completed_by = completed_by
    task.notes = notes
    task.save()
    
    # Check if all tasks are complete
    onboarding = task.onboarding
    all_tasks = onboarding.tasks.all()
    completed_tasks = all_tasks.filter(status='COMPLETED').count()
    
    if completed_tasks == all_tasks.count():
        onboarding.status = 'COMPLETED'
        onboarding.completion_date = timezone.now().date()
        onboarding.save()
    
    return True


def complete_offboarding_task(task, completed_by, notes=''):
    """Mark an offboarding task as complete"""
    task.status = 'COMPLETED'
    task.completed_date = timezone.now().date()
    task.completed_by = completed_by
    task.notes = notes
    task.save()
    
    # Check if all tasks are complete
    offboarding = task.offboarding
    all_tasks = offboarding.tasks.all()
    completed_tasks = all_tasks.filter(status='COMPLETED').count()
    
    if completed_tasks == all_tasks.count():
        offboarding.status = 'COMPLETED'
        offboarding.completion_date = timezone.now().date()
        offboarding.save()
    
    return True


def get_onboarding_progress(onboarding):
    """Get progress statistics for an onboarding"""
    all_tasks = onboarding.tasks.all()
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(status='COMPLETED').count()
    pending_tasks = all_tasks.filter(status='PENDING').count()
    overdue_tasks = all_tasks.filter(
        status='PENDING',
        due_date__lt=timezone.now().date()
    ).count()
    
    progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'overdue_tasks': overdue_tasks,
        'progress_percentage': round(progress_percentage, 2)
    }


def get_offboarding_progress(offboarding):
    """Get progress statistics for an offboarding"""
    all_tasks = offboarding.tasks.all()
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(status='COMPLETED').count()
    pending_tasks = all_tasks.filter(status='PENDING').count()
    overdue_tasks = all_tasks.filter(
        status='PENDING',
        due_date__lt=timezone.now().date()
    ).count()
    
    progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'overdue_tasks': overdue_tasks,
        'progress_percentage': round(progress_percentage, 2)
    }


def get_upcoming_onboarding_tasks(company, days=7, tenant=None):
    """Get onboarding tasks due in the next N days"""
    from onboarding.models import OnboardingTask
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    end_date = timezone.now().date() + timedelta(days=days)
    
    tasks = OnboardingTask.objects.filter(
        onboarding__employee__company=company,
        status='PENDING',
        due_date__lte=end_date,
        due_date__gte=timezone.now().date()
    ).select_related('onboarding__employee').order_by('due_date')
    
    if tenant:
        tasks = tasks.filter(tenant=tenant)
    
    return tasks


def get_upcoming_offboarding_tasks(company, days=7, tenant=None):
    """Get offboarding tasks due in the next N days"""
    from onboarding.models import OffboardingTask
    
    end_date = timezone.now().date() + timedelta(days=days)
    
    tasks = OffboardingTask.objects.filter(
        offboarding__employee__company=company,
        status='PENDING',
        due_date__lte=end_date,
        due_date__gte=timezone.now().date()
    ).select_related('offboarding__employee').order_by('due_date')
    
    if tenant:
        tasks = tasks.filter(tenant=tenant)
    
    return tasks
