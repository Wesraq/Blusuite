"""
Enhanced notification signals for BluSuite
Automatically creates notifications for critical business events
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .utils import create_notification

User = get_user_model()

# Cache for tracking state changes
_payroll_state = {}
_salary_state = {}


# ─────────────────────────────────────────────────────────────────────────────
# Payroll Notifications
# ─────────────────────────────────────────────────────────────────────────────

@receiver(pre_save, sender='payroll.Payroll', dispatch_uid='notif_payroll_pre_save')
def capture_payroll_state(sender, instance, **kwargs):
    """Capture old payroll state before save"""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            _payroll_state[instance.pk] = {
                'status': old.status,
                'approved_by': old.approved_by,
            }
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='payroll.Payroll', dispatch_uid='notif_payroll_post_save')
def notify_payroll_events(sender, instance, created, **kwargs):
    """Notify on payroll generation and approval"""
    if created:
        # Notify employee: payroll generated
        create_notification(
            recipient=instance.employee,
            title='Payroll Generated',
            message=f'Your payroll for {instance.period_start} to {instance.period_end} has been generated. Net pay: {instance.currency} {instance.net_pay:,.2f}',
            notification_type='INFO',
            category='PAYROLL',
            link=f'/employee/payroll/{instance.id}/',
            send_email=True,
            tenant=instance.tenant
        )
        
        # Notify admins: new payroll pending approval
        admins = User.objects.filter(
            company=instance.employee.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        for admin in admins:
            create_notification(
                recipient=admin,
                title='Payroll Pending Approval',
                message=f'Payroll for {instance.employee.get_full_name()} ({instance.period_start} to {instance.period_end}) is pending approval.',
                notification_type='INFO',
                category='PAYROLL',
                link=f'/payroll/{instance.id}/',
                send_email=False,
                tenant=instance.tenant
            )
    else:
        old = _payroll_state.pop(instance.pk, {})
        if not old:
            return
        
        # Check if approved
        if instance.status == 'APPROVED' and old.get('status') != 'APPROVED':
            # Notify employee: payroll approved
            create_notification(
                recipient=instance.employee,
                title='Payroll Approved',
                message=f'Your payroll for {instance.period_start} to {instance.period_end} has been approved by {instance.approved_by.get_full_name() if instance.approved_by else "administrator"}.',
                notification_type='SUCCESS',
                category='PAYROLL',
                link=f'/employee/payroll/{instance.id}/',
                sender=instance.approved_by,
                send_email=True,
                tenant=instance.tenant
            )


# ─────────────────────────────────────────────────────────────────────────────
# Salary Structure Notifications
# ─────────────────────────────────────────────────────────────────────────────

@receiver(pre_save, sender='payroll.SalaryStructure', dispatch_uid='notif_salary_pre_save')
def capture_salary_state(sender, instance, **kwargs):
    """Capture old salary before save"""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            _salary_state[instance.pk] = {
                'base_salary': old.base_salary,
                'effective_date': old.effective_date,
            }
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='payroll.SalaryStructure', dispatch_uid='notif_salary_post_save')
def notify_salary_changes(sender, instance, created, **kwargs):
    """Notify employee when salary is created or changed"""
    if created:
        # Notify employee: salary structure created
        create_notification(
            recipient=instance.employee,
            title='Salary Structure Created',
            message=f'Your salary structure has been set up. Base salary: {instance.currency} {instance.base_salary:,.2f}. Effective from: {instance.effective_date}.',
            notification_type='SUCCESS',
            category='PAYROLL',
            link='/employee/salary/',
            send_email=True,
            tenant=instance.tenant
        )
    else:
        old = _salary_state.pop(instance.pk, {})
        if not old:
            return
        
        # Check if base salary changed
        if old.get('base_salary') and old['base_salary'] != instance.base_salary:
            change_type = 'increased' if instance.base_salary > old['base_salary'] else 'decreased'
            create_notification(
                recipient=instance.employee,
                title='Salary Updated',
                message=f'Your base salary has been {change_type} from {instance.currency} {old["base_salary"]:,.2f} to {instance.currency} {instance.base_salary:,.2f}. Effective from: {instance.effective_date}.',
                notification_type='INFO',
                category='PAYROLL',
                link='/employee/salary/',
                send_email=True,
                tenant=instance.tenant
            )


# ─────────────────────────────────────────────────────────────────────────────
# Asset Notifications (enhance existing)
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='assets.EmployeeAsset', dispatch_uid='notif_asset_post_save')
def notify_asset_assignment(sender, instance, created, **kwargs):
    """Notify on asset assignment/return"""
    if created and instance.employee:
        # Asset assigned
        create_notification(
            recipient=instance.employee,
            title='Asset Assigned',
            message=f'{instance.asset.get_asset_type_display()} "{instance.asset.name}" (Serial: {instance.asset.serial_number}) has been assigned to you.',
            notification_type='INFO',
            category='ASSET',
            link=f'/employee/assets/',
            send_email=True,
            tenant=instance.tenant
        )
    elif not created:
        # Check if returned
        if instance.return_date and instance.status == 'RETURNED':
            create_notification(
                recipient=instance.employee,
                title='Asset Return Confirmed',
                message=f'Return of {instance.asset.get_asset_type_display()} "{instance.asset.name}" has been confirmed.',
                notification_type='SUCCESS',
                category='ASSET',
                link='/employee/assets/',
                send_email=False,
                tenant=instance.tenant
            )


# ─────────────────────────────────────────────────────────────────────────────
# Project Notifications
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='projects.Project', dispatch_uid='notif_project_post_save')
def notify_project_creation(sender, instance, created, **kwargs):
    """Notify team members when project is created"""
    if created and instance.team_members.exists():
        for member in instance.team_members.all():
            create_notification(
                recipient=member,
                title='Added to New Project',
                message=f'You have been added to project "{instance.name}" ({instance.code}). Start date: {instance.start_date}.',
                notification_type='INFO',
                category='PROJECT',
                link=f'/projects/{instance.id}/',
                send_email=True,
                tenant=instance.tenant
            )


# ─────────────────────────────────────────────────────────────────────────────
# Leave Request Notifications (enhance existing)
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='attendance.LeaveRequest', dispatch_uid='notif_leave_post_save')
def notify_leave_request_events(sender, instance, created, **kwargs):
    """Notify on leave request submission and status changes"""
    if created:
        # Notify supervisors/admins
        approvers = User.objects.filter(
            company=instance.employee.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        for approver in approvers:
            create_notification(
                recipient=approver,
                title='New Leave Request',
                message=f'{instance.employee.get_full_name()} requested {instance.leave_type} leave from {instance.start_date} to {instance.end_date} ({instance.total_days} days).',
                notification_type='INFO',
                category='LEAVE',
                link=f'/leave/requests/{instance.id}/',
                sender=instance.employee,
                send_email=True,
                tenant=instance.tenant
            )
    else:
        # Status changed
        if instance.status == 'APPROVED':
            create_notification(
                recipient=instance.employee,
                title='Leave Request Approved',
                message=f'Your {instance.leave_type} leave from {instance.start_date} to {instance.end_date} has been approved.',
                notification_type='SUCCESS',
                category='LEAVE',
                link='/employee/leave/',
                sender=instance.approved_by,
                send_email=True,
                tenant=instance.tenant
            )
        elif instance.status == 'REJECTED':
            message = f'Your {instance.leave_type} leave from {instance.start_date} to {instance.end_date} has been rejected.'
            if instance.rejection_reason:
                message += f' Reason: {instance.rejection_reason}'
            create_notification(
                recipient=instance.employee,
                title='Leave Request Rejected',
                message=message,
                notification_type='WARNING',
                category='LEAVE',
                link='/employee/leave/',
                sender=instance.approved_by,
                send_email=True,
                tenant=instance.tenant
            )


# ─────────────────────────────────────────────────────────────────────────────
# Document Notifications (enhance existing)
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='documents.EmployeeDocument', dispatch_uid='notif_document_post_save')
def notify_document_events(sender, instance, created, **kwargs):
    """Notify on document upload and approval"""
    if created:
        # Notify HR/admins
        reviewers = User.objects.filter(
            company=instance.employee.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        for reviewer in reviewers:
            create_notification(
                recipient=reviewer,
                title='New Document Uploaded',
                message=f'{instance.employee.get_full_name()} uploaded "{instance.title}" ({instance.document_type}).',
                notification_type='INFO',
                category='DOCUMENT',
                link=f'/documents/{instance.id}/',
                sender=instance.employee,
                send_email=True,
                tenant=instance.tenant
            )
    else:
        # Status changed
        if instance.status == 'APPROVED':
            create_notification(
                recipient=instance.employee,
                title='Document Approved',
                message=f'Your document "{instance.title}" has been approved.',
                notification_type='SUCCESS',
                category='DOCUMENT',
                link='/employee/documents/',
                sender=instance.approved_by,
                send_email=True,
                tenant=instance.tenant
            )
        elif instance.status == 'REJECTED':
            message = f'Your document "{instance.title}" has been rejected.'
            if hasattr(instance, 'rejection_reason') and instance.rejection_reason:
                message += f' Reason: {instance.rejection_reason}'
            create_notification(
                recipient=instance.employee,
                title='Document Rejected',
                message=message,
                notification_type='WARNING',
                category='DOCUMENT',
                link='/employee/documents/',
                sender=instance.approved_by,
                send_email=True,
                tenant=instance.tenant
            )


def register_all():
    """
    Register all notification signals.
    Called from notifications.apps.NotificationsConfig.ready()
    """
    # Signals are auto-registered via @receiver decorator
    # This function exists for explicit registration if needed
    pass
