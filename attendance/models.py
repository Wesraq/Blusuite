from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Attendance(models.Model):
    """Model to track employee attendance"""
    
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', _('Present')
        LATE = 'LATE', _('Late')
        HALF_DAY = 'HALF_DAY', _('Half Day')
        ABSENT = 'ABSENT', _('Absent')
        ON_LEAVE = 'ON_LEAVE', _('On Leave')
    
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendances',
        limit_choices_to={'role': 'EMPLOYEE'}
    )
    date = models.DateField(_('attendance date'), default=timezone.now)
    check_in = models.DateTimeField(_('check in time'), null=True, blank=True)
    check_out = models.DateTimeField(_('check out time'), null=True, blank=True)
    status = models.CharField(
        _('attendance status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PRESENT
    )
    notes = models.TextField(_('additional notes'), blank=True)
    location = models.CharField(_('check-in location'), max_length=255, blank=True)
    latitude = models.DecimalField(
        _('latitude'), 
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True
    )
    longitude = models.DecimalField(
        _('longitude'), 
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('attendance')
        verbose_name_plural = _('attendances')
        ordering = ['-date', '-check_in']
        unique_together = ['employee', 'date']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.date} - {self.status}"
    
    @property
    def working_hours(self):
        """Calculate working hours in hours"""
        if self.check_in and self.check_out:
            duration = self.check_out - self.check_in
            return round(duration.total_seconds() / 3600, 2)  # Convert to hours
        return 0
    
    def save(self, *args, **kwargs):
        # Auto-set status based on check-in/check-out times
        if self.check_in:
            # Check if check-in is after 9:30 AM (for example)
            late_time = self.check_in.replace(hour=9, minute=30, second=0, microsecond=0)
            if self.check_in > late_time and not self.status == self.Status.ON_LEAVE:
                self.status = self.Status.LATE
        super().save(*args, **kwargs)


class LeaveRequest(models.Model):
    """Model to track employee leave requests"""
    
    class LeaveType(models.TextChoices):
        SICK = 'SICK', _('Sick Leave')
        VACATION = 'VACATION', _('Vacation Leave')
        PERSONAL = 'PERSONAL', _('Personal Leave')
        MATERNITY = 'MATERNITY', _('Maternity Leave')
        PATERNITY = 'PATERNITY', _('Paternity Leave')
        BEREAVEMENT = 'BEREAVEMENT', _('Bereavement Leave')
        OTHER = 'OTHER', _('Other')
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='leave_requests',
        limit_choices_to={'role': 'EMPLOYEE'}
    )
    leave_type = models.CharField(
        _('leave type'),
        max_length=20,
        choices=LeaveType.choices,
        default=LeaveType.VACATION
    )
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'))
    reason = models.TextField(_('reason for leave'))
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
        related_name='approved_leaves',
        limit_choices_to={'role__in': ['ADMIN', 'EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN']}
    )
    approved_at = models.DateTimeField(_('approved at'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('leave request')
        verbose_name_plural = _('leave requests')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"
    
    @property
    def duration(self):
        """Calculate leave duration in days"""
        return (self.end_date - self.start_date).days + 1  # Inclusive of both start and end dates
    
    def save(self, *args, **kwargs):
        # If status is being updated to APPROVED, set approved_by and approved_at
        if self.pk:
            old_instance = LeaveRequest.objects.get(pk=self.pk)
            if self.status == self.Status.APPROVED and old_instance.status != self.Status.APPROVED:
                self.approved_at = timezone.now()
        super().save(*args, **kwargs)
