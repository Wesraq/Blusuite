from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from tenant_management.models import TenantScopedModel

User = get_user_model()


class OnboardingChecklist(TenantScopedModel):
    """Model for onboarding checklist templates"""
    
    name = models.CharField(_('checklist name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    is_default = models.BooleanField(_('default checklist'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('onboarding checklist')
        verbose_name_plural = _('onboarding checklists')
        ordering = ['name']
        unique_together = ['tenant', 'name']
    
    def __str__(self):
        return self.name


class OnboardingTask(TenantScopedModel):
    """Model for onboarding checklist tasks"""
    
    class Priority(models.TextChoices):
        LOW = 'LOW', _('Low')
        MEDIUM = 'MEDIUM', _('Medium')
        HIGH = 'HIGH', _('High')
        CRITICAL = 'CRITICAL', _('Critical')
    
    checklist = models.ForeignKey(
        OnboardingChecklist,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    title = models.CharField(_('task title'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    priority = models.CharField(
        _('priority'),
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    order = models.PositiveIntegerField(_('order'), default=0)
    days_to_complete = models.PositiveIntegerField(_('days to complete'), default=1)
    assigned_to_role = models.CharField(_('assigned to role'), max_length=50, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('onboarding task')
        verbose_name_plural = _('onboarding tasks')
        ordering = ['checklist', 'order']
    
    def __str__(self):
        return f"{self.checklist.name} - {self.title}"


class EmployeeOnboarding(TenantScopedModel):
    """Model for employee onboarding process"""
    
    class Status(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', _('Not Started')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        ON_HOLD = 'ON_HOLD', _('On Hold')
    
    employee = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='onboarding'
    )
    checklist = models.ForeignKey(
        OnboardingChecklist,
        on_delete=models.SET_NULL,
        null=True
    )
    start_date = models.DateField(_('start date'))
    expected_completion_date = models.DateField(_('expected completion date'))
    actual_completion_date = models.DateField(_('actual completion date'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED
    )
    buddy = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onboarding_buddies'
    )
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('employee onboarding')
        verbose_name_plural = _('employee onboardings')
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - Onboarding"


class OnboardingTaskCompletion(TenantScopedModel):
    """Model for tracking onboarding task completion"""
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        SKIPPED = 'SKIPPED', _('Skipped')
    
    employee_onboarding = models.ForeignKey(
        EmployeeOnboarding,
        on_delete=models.CASCADE,
        related_name='task_completions'
    )
    task = models.ForeignKey(
        OnboardingTask,
        on_delete=models.CASCADE
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_onboarding_tasks'
    )
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('onboarding task completion')
        verbose_name_plural = _('onboarding task completions')
        ordering = ['task__order']
        unique_together = ['tenant', 'employee_onboarding', 'task']
    
    def __str__(self):
        return f"{self.employee_onboarding.employee.get_full_name()} - {self.task.title}"


class OffboardingChecklist(TenantScopedModel):
    """Model for offboarding checklist templates"""
    
    name = models.CharField(_('checklist name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    is_default = models.BooleanField(_('default checklist'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('offboarding checklist')
        verbose_name_plural = _('offboarding checklists')
        ordering = ['name']
        unique_together = ['tenant', 'name']
    
    def __str__(self):
        return self.name


class EmployeeOffboarding(TenantScopedModel):
    """Model for employee offboarding process"""
    
    class Status(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', _('Not Started')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
    
    class Reason(models.TextChoices):
        RESIGNATION = 'RESIGNATION', _('Resignation')
        TERMINATION = 'TERMINATION', _('Termination')
        RETIREMENT = 'RETIREMENT', _('Retirement')
        CONTRACT_END = 'CONTRACT_END', _('Contract End')
        OTHER = 'OTHER', _('Other')
    
    employee = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='offboarding'
    )
    checklist = models.ForeignKey(
        OffboardingChecklist,
        on_delete=models.SET_NULL,
        null=True
    )
    last_working_date = models.DateField(_('last working date'))
    reason = models.CharField(
        _('reason'),
        max_length=20,
        choices=Reason.choices,
        default=Reason.RESIGNATION
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED
    )
    exit_interview_completed = models.BooleanField(_('exit interview completed'), default=False)
    exit_interview_notes = models.TextField(_('exit interview notes'), blank=True)
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('employee offboarding')
        verbose_name_plural = _('employee offboardings')
        ordering = ['-last_working_date']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - Offboarding"
