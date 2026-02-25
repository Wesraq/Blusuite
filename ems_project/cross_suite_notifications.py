"""
Cross-Suite Notification Utility
Sends in-app notifications from AMS/PMS into the EMS notification center.
"""
from django.contrib.auth import get_user_model

User = get_user_model()


def notify_employee(recipient, title, message, category='OTHER', link='',
                    sender=None, notification_type='INFO'):
    """
    Create an in-app notification for an employee.

    Args:
        recipient: User instance (the employee)
        title: Short notification title
        message: Longer description
        category: One of Notification.Category choices
                  (ASSET, PROJECT, ATTENDANCE, LEAVE, etc.)
        link: Optional URL the notification links to
        sender: Optional User who triggered the action
        notification_type: INFO / SUCCESS / WARNING / ERROR / REMINDER
    """
    try:
        from notifications.models import Notification
        tenant = getattr(recipient, 'company', None)
        kwargs = {
            'recipient': recipient,
            'title': title,
            'message': message,
            'notification_type': notification_type,
            'category': category,
            'link': link,
            'is_read': False,
        }
        if sender:
            kwargs['sender'] = sender
        if tenant:
            kwargs['tenant'] = tenant
        Notification.objects.create(**kwargs)
    except Exception:
        pass


# ── AMS helpers ──────────────────────────────────────────────────────────

def notify_asset_assigned(asset, assigned_by=None):
    """Notify employee when an asset is assigned to them."""
    if not asset.employee:
        return
    notify_employee(
        recipient=asset.employee,
        title='Asset Assigned to You',
        message=f'{asset.get_asset_type_display()} "{asset.name}" has been assigned to you.',
        category='ASSET',
        link=f'/assets/{asset.id}/',
        sender=assigned_by,
        notification_type='INFO',
    )


def notify_asset_unassigned(asset, employee, unassigned_by=None):
    """Notify employee when an asset is unassigned from them."""
    notify_employee(
        recipient=employee,
        title='Asset Returned / Unassigned',
        message=f'{asset.get_asset_type_display()} "{asset.name}" has been unassigned from you.',
        category='ASSET',
        link=f'/assets/{asset.id}/',
        sender=unassigned_by,
        notification_type='INFO',
    )


def notify_asset_maintenance(asset, description=''):
    """Notify employee when their asset goes to maintenance."""
    if not asset.employee:
        return
    notify_employee(
        recipient=asset.employee,
        title='Asset Sent for Maintenance',
        message=f'Your {asset.get_asset_type_display()} "{asset.name}" has been sent for maintenance. {description}'.strip(),
        category='ASSET',
        link=f'/assets/{asset.id}/',
        notification_type='WARNING',
    )


# ── PMS helpers ──────────────────────────────────────────────────────────

def notify_project_member_added(project, member, added_by=None):
    """Notify employee when added to a project team."""
    notify_employee(
        recipient=member,
        title='Added to Project',
        message=f'You have been added to project "{project.name}" ({project.code}).',
        category='PROJECT',
        link=f'/projects/{project.id}/',
        sender=added_by,
        notification_type='INFO',
    )


def notify_task_assigned(task, assigned_by=None):
    """Notify employee when a task is assigned to them."""
    if not task.assigned_to:
        return
    notify_employee(
        recipient=task.assigned_to,
        title='Task Assigned to You',
        message=f'Task "{task.title}" in project "{task.project.name}" has been assigned to you.',
        category='PROJECT',
        link=f'/projects/{task.project.id}/tasks/{task.id}/',
        sender=assigned_by,
        notification_type='INFO',
    )


def notify_task_status_changed(task, old_status, changed_by=None):
    """Notify project manager when a task status changes."""
    pm = task.project.project_manager
    if not pm or pm == changed_by:
        return
    notify_employee(
        recipient=pm,
        title='Task Status Updated',
        message=f'Task "{task.title}" changed from {old_status} to {task.get_status_display()}.',
        category='PROJECT',
        link=f'/projects/{task.project.id}/tasks/{task.id}/',
        sender=changed_by,
        notification_type='INFO',
    )
