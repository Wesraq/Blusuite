"""
Onboarding Automation for BluSuite
Handles automated onboarding flows, notifications, and company setup
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date


User = get_user_model()


class CompanyOnboarding(models.Model):
    """Track company onboarding progress"""
    
    class Status(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', 'Not Started'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
    
    company = models.OneToOneField(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='onboarding_progress'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    current_step = models.IntegerField(default=1)
    
    # Step completion flags
    company_info_complete = models.BooleanField(default=False)
    admin_account_complete = models.BooleanField(default=False)
    settings_configured = models.BooleanField(default=False)
    first_employee_added = models.BooleanField(default=False)
    first_department_created = models.BooleanField(default=False)
    attendance_configured = models.BooleanField(default=False)
    leave_policies_set = models.BooleanField(default=False)
    payroll_configured = models.BooleanField(default=False)
    documents_uploaded = models.BooleanField(default=False)
    integrations_setup = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Company Onboarding'
        verbose_name_plural = 'Company Onboardings'
    
    def __str__(self):
        return f"{self.company.name} - Onboarding"
    
    @property
    def completion_percentage(self):
        """Calculate onboarding completion percentage"""
        steps = [
            self.company_info_complete,
            self.admin_account_complete,
            self.settings_configured,
            self.first_employee_added,
            self.first_department_created,
            self.attendance_configured,
            self.leave_policies_set,
            self.payroll_configured,
            self.documents_uploaded,
            self.integrations_setup,
        ]
        completed = sum(steps)
        total = len(steps)
        return int((completed / total) * 100)
    
    @property
    def is_complete(self):
        """Check if onboarding is complete"""
        return self.completion_percentage == 100


class OnboardingReminder(models.Model):
    """Track onboarding reminders sent"""
    
    class ReminderType(models.TextChoices):
        TASK_DUE = 'TASK_DUE', 'Task Due Soon'
        TASK_OVERDUE = 'TASK_OVERDUE', 'Task Overdue'
        WELCOME = 'WELCOME', 'Welcome Message'
        PROGRESS = 'PROGRESS', 'Progress Update'
        COMPLETION = 'COMPLETION', 'Onboarding Complete'
    
    employee_onboarding = models.ForeignKey(
        'onboarding.EmployeeOnboarding',
        on_delete=models.CASCADE,
        related_name='reminders',
        null=True,
        blank=True
    )
    company_onboarding = models.ForeignKey(
        CompanyOnboarding,
        on_delete=models.CASCADE,
        related_name='reminders',
        null=True,
        blank=True
    )
    reminder_type = models.CharField(max_length=20, choices=ReminderType.choices)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_to = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.reminder_type} - {self.sent_to.email}"


# ─────────────────────────────────────────────────────────────────────────────
# Company Onboarding Functions
# ─────────────────────────────────────────────────────────────────────────────

def start_company_onboarding(company, admin_user):
    """Initialize company onboarding process"""
    onboarding, created = CompanyOnboarding.objects.get_or_create(
        company=company,
        defaults={
            'status': CompanyOnboarding.Status.IN_PROGRESS,
            'started_at': timezone.now(),
        }
    )
    
    if created:
        # Send welcome email
        _send_company_welcome_email(company, admin_user)
    
    return onboarding


def update_onboarding_step(company, step_name, completed=True):
    """Update company onboarding step"""
    try:
        onboarding = CompanyOnboarding.objects.get(company=company)
        setattr(onboarding, step_name, completed)
        onboarding.save()
        
        # Check if all steps complete
        if onboarding.is_complete and not onboarding.completed_at:
            onboarding.status = CompanyOnboarding.Status.COMPLETED
            onboarding.completed_at = timezone.now()
            onboarding.save()
            
            # Send completion notification
            _send_company_onboarding_complete(company)
        
        return onboarding
    except CompanyOnboarding.DoesNotExist:
        return None


def get_onboarding_progress(company):
    """Get company onboarding progress"""
    try:
        onboarding = CompanyOnboarding.objects.get(company=company)
        
        steps = [
            {'name': 'Company Information', 'complete': onboarding.company_info_complete, 'order': 1},
            {'name': 'Admin Account', 'complete': onboarding.admin_account_complete, 'order': 2},
            {'name': 'Settings Configuration', 'complete': onboarding.settings_configured, 'order': 3},
            {'name': 'Add First Employee', 'complete': onboarding.first_employee_added, 'order': 4},
            {'name': 'Create Department', 'complete': onboarding.first_department_created, 'order': 5},
            {'name': 'Configure Attendance', 'complete': onboarding.attendance_configured, 'order': 6},
            {'name': 'Set Leave Policies', 'complete': onboarding.leave_policies_set, 'order': 7},
            {'name': 'Configure Payroll', 'complete': onboarding.payroll_configured, 'order': 8},
            {'name': 'Upload Documents', 'complete': onboarding.documents_uploaded, 'order': 9},
            {'name': 'Setup Integrations', 'complete': onboarding.integrations_setup, 'order': 10},
        ]
        
        return {
            'status': onboarding.status,
            'percentage': onboarding.completion_percentage,
            'steps': steps,
            'current_step': onboarding.current_step,
            'started_at': onboarding.started_at,
            'completed_at': onboarding.completed_at,
        }
    except CompanyOnboarding.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Employee Onboarding Automation
# ─────────────────────────────────────────────────────────────────────────────

def auto_create_employee_onboarding(employee):
    """Automatically create onboarding for new employee"""
    from blu_staff.apps.onboarding.models import (
        EmployeeOnboarding, OnboardingChecklist, OnboardingTaskCompletion
    )
    
    # Check if onboarding already exists
    if hasattr(employee, 'onboarding'):
        return employee.onboarding
    
    # Get default checklist
    try:
        checklist = OnboardingChecklist.objects.filter(
            tenant=employee.company.tenant,
            is_default=True,
            is_active=True
        ).first()
        
        if not checklist:
            # Get any active checklist
            checklist = OnboardingChecklist.objects.filter(
                tenant=employee.company.tenant,
                is_active=True
            ).first()
    except Exception:
        checklist = None
    
    # Create onboarding
    start_date = employee.date_hired or date.today()
    expected_completion = start_date + timedelta(days=30)
    
    onboarding = EmployeeOnboarding.objects.create(
        employee=employee,
        checklist=checklist,
        start_date=start_date,
        expected_completion_date=expected_completion,
        status=EmployeeOnboarding.Status.IN_PROGRESS,
        tenant=employee.company.tenant
    )
    
    # Create task completions
    if checklist:
        for task in checklist.tasks.all():
            OnboardingTaskCompletion.objects.create(
                employee_onboarding=onboarding,
                task=task,
                status=OnboardingTaskCompletion.Status.PENDING,
                tenant=employee.company.tenant
            )
    
    # Send welcome email
    _send_employee_welcome_email(employee)
    
    return onboarding


def check_overdue_onboarding_tasks():
    """Check for overdue onboarding tasks and send reminders"""
    from blu_staff.apps.onboarding.models import OnboardingTaskCompletion
    
    # Get pending tasks
    pending_tasks = OnboardingTaskCompletion.objects.filter(
        status__in=['PENDING', 'IN_PROGRESS']
    ).select_related('employee_onboarding', 'task')
    
    overdue_count = 0
    
    for task_completion in pending_tasks:
        onboarding = task_completion.employee_onboarding
        task = task_completion.task
        
        # Calculate due date
        due_date = onboarding.start_date + timedelta(days=task.days_to_complete)
        
        if date.today() > due_date:
            # Task is overdue
            _send_task_overdue_reminder(task_completion)
            overdue_count += 1
        elif date.today() == due_date - timedelta(days=1):
            # Task due tomorrow
            _send_task_due_reminder(task_completion)
    
    return overdue_count


def complete_onboarding_task(task_completion, completed_by, notes=''):
    """Mark onboarding task as complete"""
    task_completion.status = 'COMPLETED'
    task_completion.completed_by = completed_by
    task_completion.completed_at = timezone.now()
    task_completion.notes = notes
    task_completion.save()
    
    # Check if all tasks complete
    onboarding = task_completion.employee_onboarding
    all_complete = not onboarding.task_completions.filter(
        status__in=['PENDING', 'IN_PROGRESS']
    ).exists()
    
    if all_complete:
        onboarding.status = 'COMPLETED'
        onboarding.actual_completion_date = date.today()
        onboarding.save()
        
        # Send completion notification
        _send_employee_onboarding_complete(onboarding.employee)


def get_employee_onboarding_progress(employee):
    """Get employee onboarding progress"""
    try:
        onboarding = employee.onboarding
        
        total_tasks = onboarding.task_completions.count()
        completed_tasks = onboarding.task_completions.filter(status='COMPLETED').count()
        
        percentage = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        
        return {
            'status': onboarding.status,
            'percentage': percentage,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'start_date': onboarding.start_date,
            'expected_completion': onboarding.expected_completion_date,
            'actual_completion': onboarding.actual_completion_date,
            'buddy': onboarding.buddy,
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Notification Functions
# ─────────────────────────────────────────────────────────────────────────────

def _send_company_welcome_email(company, admin_user):
    """Send welcome email to company admin"""
    try:
        from blu_staff.apps.notifications.utils import bulk_notify
        
        bulk_notify(
            recipients=[admin_user],
            title='Welcome to BluSuite!',
            message=f'Welcome to BluSuite, {company.name}! Let\'s get you set up.',
            notification_type='INFO',
            category='ONBOARDING',
            link='/onboarding/company/',
            send_email=True
        )
        
        OnboardingReminder.objects.create(
            company_onboarding=company.onboarding_progress,
            reminder_type='WELCOME',
            sent_to=admin_user
        )
    except Exception:
        pass


def _send_company_onboarding_complete(company):
    """Send onboarding completion notification"""
    try:
        from blu_staff.apps.notifications.utils import bulk_notify
        
        admins = User.objects.filter(
            company=company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        
        bulk_notify(
            recipients=admins,
            title='Company Onboarding Complete!',
            message='Congratulations! You\'ve completed the company setup.',
            notification_type='SUCCESS',
            category='ONBOARDING',
            link='/dashboard/',
            send_email=True
        )
    except Exception:
        pass


def _send_employee_welcome_email(employee):
    """Send welcome email to new employee"""
    try:
        from blu_staff.apps.notifications.utils import bulk_notify
        
        bulk_notify(
            recipients=[employee],
            title=f'Welcome to {employee.company.name}!',
            message='Welcome aboard! We\'ve prepared an onboarding checklist to help you get started.',
            notification_type='INFO',
            category='ONBOARDING',
            link='/onboarding/employee/',
            send_email=True
        )
        
        if hasattr(employee, 'onboarding'):
            OnboardingReminder.objects.create(
                employee_onboarding=employee.onboarding,
                reminder_type='WELCOME',
                sent_to=employee
            )
    except Exception:
        pass


def _send_employee_onboarding_complete(employee):
    """Send onboarding completion notification"""
    try:
        from blu_staff.apps.notifications.utils import bulk_notify
        
        bulk_notify(
            recipients=[employee],
            title='Onboarding Complete!',
            message='Congratulations! You\'ve completed your onboarding.',
            notification_type='SUCCESS',
            category='ONBOARDING',
            link='/dashboard/',
            send_email=True
        )
    except Exception:
        pass


def _send_task_due_reminder(task_completion):
    """Send reminder for task due soon"""
    try:
        from blu_staff.apps.notifications.utils import bulk_notify
        
        employee = task_completion.employee_onboarding.employee
        task = task_completion.task
        
        bulk_notify(
            recipients=[employee],
            title='Onboarding Task Due Tomorrow',
            message=f'Reminder: "{task.title}" is due tomorrow.',
            notification_type='WARNING',
            category='ONBOARDING',
            link='/onboarding/employee/',
            send_email=False
        )
    except Exception:
        pass


def _send_task_overdue_reminder(task_completion):
    """Send reminder for overdue task"""
    try:
        from blu_staff.apps.notifications.utils import bulk_notify
        
        employee = task_completion.employee_onboarding.employee
        task = task_completion.task
        
        # Check if reminder already sent today
        today_reminders = OnboardingReminder.objects.filter(
            employee_onboarding=task_completion.employee_onboarding,
            reminder_type='TASK_OVERDUE',
            sent_at__date=date.today()
        )
        
        if today_reminders.exists():
            return  # Don't spam
        
        bulk_notify(
            recipients=[employee],
            title='Overdue Onboarding Task',
            message=f'"{task.title}" is overdue. Please complete it as soon as possible.',
            notification_type='ERROR',
            category='ONBOARDING',
            link='/onboarding/employee/',
            send_email=True
        )
        
        OnboardingReminder.objects.create(
            employee_onboarding=task_completion.employee_onboarding,
            reminder_type='TASK_OVERDUE',
            sent_to=employee
        )
    except Exception:
        pass


def create_default_onboarding_checklist(company):
    """Create default onboarding checklist for company"""
    from blu_staff.apps.onboarding.models import OnboardingChecklist, OnboardingTask
    
    checklist = OnboardingChecklist.objects.create(
        name='Standard Employee Onboarding',
        description='Default onboarding checklist for new employees',
        is_default=True,
        is_active=True,
        tenant=company.tenant
    )
    
    tasks = [
        {
            'title': 'Complete personal information',
            'description': 'Fill in your personal details and contact information',
            'priority': 'HIGH',
            'order': 1,
            'days_to_complete': 1,
        },
        {
            'title': 'Review company policies',
            'description': 'Read and acknowledge company policies and procedures',
            'priority': 'HIGH',
            'order': 2,
            'days_to_complete': 3,
        },
        {
            'title': 'Setup email and accounts',
            'description': 'Configure your email and access to company systems',
            'priority': 'CRITICAL',
            'order': 3,
            'days_to_complete': 1,
        },
        {
            'title': 'Meet your team',
            'description': 'Schedule meetings with team members',
            'priority': 'MEDIUM',
            'order': 4,
            'days_to_complete': 5,
        },
        {
            'title': 'Complete training modules',
            'description': 'Complete required training courses',
            'priority': 'HIGH',
            'order': 5,
            'days_to_complete': 14,
        },
        {
            'title': 'Submit required documents',
            'description': 'Upload ID, certificates, and other required documents',
            'priority': 'CRITICAL',
            'order': 6,
            'days_to_complete': 7,
        },
    ]
    
    for task_data in tasks:
        OnboardingTask.objects.create(
            checklist=checklist,
            tenant=company.tenant,
            **task_data
        )
    
    return checklist
