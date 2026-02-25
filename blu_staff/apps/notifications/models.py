from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from tenant_management.models import TenantScopedModel

User = get_user_model()


class Notification(TenantScopedModel):
    """Model for user notifications"""
    
    class NotificationType(models.TextChoices):
        INFO = 'INFO', _('Information')
        WARNING = 'WARNING', _('Warning')
        SUCCESS = 'SUCCESS', _('Success')
        ERROR = 'ERROR', _('Error')
        REMINDER = 'REMINDER', _('Reminder')
    
    class Category(models.TextChoices):
        ATTENDANCE = 'ATTENDANCE', _('Attendance')
        LEAVE = 'LEAVE', _('Leave')
        DOCUMENT = 'DOCUMENT', _('Document')
        PERFORMANCE = 'PERFORMANCE', _('Performance')
        PAYROLL = 'PAYROLL', _('Payroll')
        TRAINING = 'TRAINING', _('Training')
        ONBOARDING = 'ONBOARDING', _('Onboarding')
        ASSET = 'ASSET', _('Asset')
        PROJECT = 'PROJECT', _('Project')
        SYSTEM = 'SYSTEM', _('System')
        OTHER = 'OTHER', _('Other')
    
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications'
    )
    title = models.CharField(_('title'), max_length=200)
    message = models.TextField(_('message'))
    notification_type = models.CharField(
        _('type'),
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.INFO
    )
    category = models.CharField(
        _('category'),
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER
    )
    link = models.CharField(_('link'), max_length=500, blank=True)
    is_read = models.BooleanField(_('read'), default=False)
    read_at = models.DateTimeField(_('read at'), null=True, blank=True)
    is_email_sent = models.BooleanField(_('email sent'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class NotificationPreference(TenantScopedModel):
    """Model for user notification preferences"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Email notifications
    email_attendance = models.BooleanField(_('attendance emails'), default=True)
    email_leave = models.BooleanField(_('leave emails'), default=True)
    email_document = models.BooleanField(_('document emails'), default=True)
    email_performance = models.BooleanField(_('performance emails'), default=True)
    email_payroll = models.BooleanField(_('payroll emails'), default=True)
    email_training = models.BooleanField(_('training emails'), default=True)
    
    # In-app notifications
    inapp_attendance = models.BooleanField(_('attendance notifications'), default=True)
    inapp_leave = models.BooleanField(_('leave notifications'), default=True)
    inapp_document = models.BooleanField(_('document notifications'), default=True)
    inapp_performance = models.BooleanField(_('performance notifications'), default=True)
    inapp_payroll = models.BooleanField(_('payroll notifications'), default=True)
    inapp_training = models.BooleanField(_('training notifications'), default=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('notification preference')
        verbose_name_plural = _('notification preferences')
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Notification Preferences"
