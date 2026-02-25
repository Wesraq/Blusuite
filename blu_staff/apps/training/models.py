from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from tenant_management.models import TenantScopedModel
from blu_staff.apps.accounts.models import CompanyDepartment

User = get_user_model()


class TrainingProgram(TenantScopedModel):
    """Model for training programs"""
    
    class ProgramType(models.TextChoices):
        ONBOARDING = 'ONBOARDING', _('Onboarding')
        TECHNICAL = 'TECHNICAL', _('Technical Skills')
        SOFT_SKILLS = 'SOFT_SKILLS', _('Soft Skills')
        LEADERSHIP = 'LEADERSHIP', _('Leadership')
        COMPLIANCE = 'COMPLIANCE', _('Compliance')
        SAFETY = 'SAFETY', _('Safety')
        OTHER = 'OTHER', _('Other')
    
    # Department-based training (null = company-wide)
    department = models.ForeignKey(
        CompanyDepartment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_programs',
        verbose_name=_('department'),
        help_text=_('Leave blank for company-wide training')
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_training_programs',
        verbose_name=_('created by')
    )
    title = models.CharField(_('title'), max_length=200)
    description = models.TextField(_('description'))
    program_type = models.CharField(
        _('program type'),
        max_length=20,
        choices=ProgramType.choices,
        default=ProgramType.OTHER
    )
    duration_hours = models.DecimalField(_('duration (hours)'), max_digits=6, decimal_places=2)
    is_mandatory = models.BooleanField(_('mandatory'), default=False)
    cost = models.DecimalField(_('cost'), max_digits=10, decimal_places=2, default=0)
    provider = models.CharField(_('provider'), max_length=200, blank=True)
    instructor = models.CharField(_('instructor'), max_length=200, blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    requires_approval = models.BooleanField(_('requires admin approval'), default=False, help_text=_('Department programs may require admin approval'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('training program')
        verbose_name_plural = _('training programs')
        ordering = ['title']
    
    def __str__(self):
        return self.title


class TrainingEnrollment(TenantScopedModel):
    """Model for employee training enrollments"""
    
    class Status(models.TextChoices):
        ENROLLED = 'ENROLLED', _('Enrolled')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='training_enrollments'
    )
    program = models.ForeignKey(
        TrainingProgram,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    enrollment_date = models.DateField(_('enrollment date'))
    start_date = models.DateField(_('start date'), null=True, blank=True)
    completion_date = models.DateField(_('completion date'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.ENROLLED
    )
    score = models.DecimalField(_('score'), max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(_('feedback'), blank=True)
    certificate_url = models.URLField(_('certificate URL'), blank=True)
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('training enrollment')
        verbose_name_plural = _('training enrollments')
        ordering = ['-enrollment_date']
        unique_together = ['tenant', 'employee', 'program', 'enrollment_date']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.program.title}"


class Certification(TenantScopedModel):
    """Model for employee certifications"""
    
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        EXPIRED = 'EXPIRED', _('Expired')
        PENDING = 'PENDING', _('Pending')
    
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='certifications'
    )
    name = models.CharField(_('certification name'), max_length=200)
    issuing_organization = models.CharField(_('issuing organization'), max_length=200)
    issue_date = models.DateField(_('issue date'))
    expiry_date = models.DateField(_('expiry date'), null=True, blank=True)
    credential_id = models.CharField(_('credential ID'), max_length=100, blank=True)
    credential_url = models.URLField(_('credential URL'), blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('certification')
        verbose_name_plural = _('certifications')
        ordering = ['-issue_date']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.name}"


class TrainingRequest(TenantScopedModel):
    """Model for department managers to request new training programs"""
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending Approval')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        COMPLETED = 'COMPLETED', _('Completed')
    
    class Priority(models.TextChoices):
        LOW = 'LOW', _('Low')
        MEDIUM = 'MEDIUM', _('Medium')
        HIGH = 'HIGH', _('High')
        URGENT = 'URGENT', _('Urgent')
    
    department = models.ForeignKey(
        CompanyDepartment,
        on_delete=models.CASCADE,
        related_name='training_requests',
        verbose_name=_('department')
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='training_requests_made',
        verbose_name=_('requested by')
    )
    training_title = models.CharField(_('training title'), max_length=200)
    program_type = models.CharField(
        _('program type'),
        max_length=20,
        choices=TrainingProgram.ProgramType.choices,
        default=TrainingProgram.ProgramType.OTHER
    )
    description = models.TextField(_('description/justification'))
    target_employees = models.PositiveIntegerField(_('number of employees'), default=1, help_text=_('How many employees will attend'))
    duration_hours = models.DecimalField(_('estimated duration (hours)'), max_digits=6, decimal_places=2)
    estimated_cost = models.DecimalField(_('estimated cost'), max_digits=10, decimal_places=2, null=True, blank=True)
    preferred_provider = models.CharField(_('preferred provider'), max_length=200, blank=True)
    priority = models.CharField(
        _('priority'),
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    business_justification = models.TextField(_('business justification'), help_text=_('Explain the business need and expected benefits'))
    urgency_reason = models.TextField(_('urgency reason'), blank=True, help_text=_('Explain why this is urgent'))
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_requests_approved',
        verbose_name=_('approved by')
    )
    approval_date = models.DateTimeField(_('approval date'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    admin_notes = models.TextField(_('admin notes'), blank=True)
    created_training = models.ForeignKey(
        TrainingProgram,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_request',
        verbose_name=_('created training program'),
        help_text=_('Training program created from this request')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('training request')
        verbose_name_plural = _('training requests')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.department.name} - {self.training_title} ({self.get_status_display()})"
