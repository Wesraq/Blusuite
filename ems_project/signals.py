from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from ems_project.notifications import NotificationManager

User = get_user_model()


class UserProfile(models.Model):
    """Abstract base model for user profiles"""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self._send_notification()

    def _send_notification(self):
        """Send notification for new profile creation"""
        pass


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """Send notification when user is created"""
    if created:
        NotificationManager.notify_user_registration(instance)


@receiver(post_save, sender='attendance.LeaveRequest')
def leave_request_post_save(sender, instance, created, **kwargs):
    """Send notification for leave request actions"""
    if created:
        NotificationManager.notify_leave_request(instance, 'submitted')
    else:
        # Check if status changed
        if instance.status in ['APPROVED', 'REJECTED']:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                NotificationManager.notify_leave_request(instance, instance.status.lower())


@receiver(post_save, sender='performance.PerformanceReview')
def performance_review_post_save(sender, instance, created, **kwargs):
    """Send notification for performance review actions"""
    if created:
        NotificationManager.notify_performance_review(instance, 'scheduled')
    else:
        # Check if status changed to completed
        if instance.status == 'COMPLETED':
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                NotificationManager.notify_performance_review(instance, 'completed')


@receiver(post_save, sender='documents.EmployeeDocument')
def document_post_save(sender, instance, created, **kwargs):
    """Send notification for document actions"""
    if created:
        NotificationManager.notify_document_upload(instance, 'uploaded')
    else:
        # Check if status changed
        if instance.status in ['APPROVED', 'REJECTED']:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                NotificationManager.notify_document_upload(instance, instance.status.lower())
