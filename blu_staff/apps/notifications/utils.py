"""
Notification utility functions for creating and sending notifications across the EMS
"""
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Notification, NotificationPreference

User = get_user_model()


def create_notification(
    recipient,
    title,
    message,
    notification_type='INFO',
    category='OTHER',
    link='',
    sender=None,
    send_email=False,
    tenant=None
):
    """
    Create a notification for a user
    
    Args:
        recipient: User object who will receive the notification
        title: Notification title
        message: Notification message
        notification_type: Type of notification (INFO, WARNING, SUCCESS, ERROR, REMINDER)
        category: Category (ATTENDANCE, LEAVE, DOCUMENT, PERFORMANCE, PAYROLL, etc.)
        link: Optional link to related resource
        sender: User who triggered the notification
        send_email: Whether to send email notification
        tenant: Tenant object for multi-tenancy
    
    Returns:
        Notification object
    """
    notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        title=title,
        message=message,
        notification_type=notification_type,
        category=category,
        link=link,
        tenant=tenant
    )
    
    # Send email if requested and user preferences allow
    if send_email:
        try:
            prefs = NotificationPreference.objects.get(user=recipient)
            category_lower = category.lower()
            email_pref = getattr(prefs, f'email_{category_lower}', True)
            
            if email_pref:
                send_notification_email(recipient, title, message, link)
                notification.is_email_sent = True
                notification.save()
        except NotificationPreference.DoesNotExist:
            # Default to sending email if no preferences set
            send_notification_email(recipient, title, message, link)
            notification.is_email_sent = True
            notification.save()
    
    return notification


def send_notification_email(recipient, title, message, link=''):
    """Send email notification to user"""
    try:
        # Check if email notifications are enabled
        from blu_staff.apps.accounts.models import CompanyEmailSettings
        company = getattr(recipient, 'company', None)
        if company:
            email_settings = CompanyEmailSettings.objects.filter(company=company).first()
            if email_settings and not email_settings.enable_email_notifications:
                print(f"Email notifications disabled for company {company.name}")
                return
        
        subject = f"[EMS] {title}"
        
        context = {
            'recipient_name': recipient.get_full_name(),
            'title': title,
            'message': message,
            'link': link,
            'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000'
        }
        
        html_message = render_to_string('emails/notification.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            html_message=html_message,
            fail_silently=True
        )
    except Exception as e:
        # Don't let email errors break notification creation
        print(f"Error sending notification email (non-critical): {e}")
        import traceback
        print(traceback.format_exc())


def notify_leave_request(leave_request, tenant=None):
    """Notify relevant users about a leave request"""
    employee = leave_request.employee
    
    # Notify approvers (HR, Admin, Employer)
    approvers = User.objects.filter(
        company=employee.company,
        role__in=['EMPLOYER_ADMIN', 'ADMINISTRATOR', 'HR']
    )
    
    for approver in approvers:
        create_notification(
            recipient=approver,
            title=f"New Leave Request from {employee.get_full_name()}",
            message=f"{employee.get_full_name()} has requested {leave_request.leave_type} leave from {leave_request.start_date} to {leave_request.end_date}.",
            notification_type='INFO',
            category='LEAVE',
            link=f'/leave/',
            sender=employee,
            send_email=True,
            tenant=tenant
        )


def notify_leave_approval(leave_request, approved_by, tenant=None):
    """Notify employee about leave approval"""
    create_notification(
        recipient=leave_request.employee,
        title="Leave Request Approved",
        message=f"Your {leave_request.leave_type} leave request from {leave_request.start_date} to {leave_request.end_date} has been approved.",
        notification_type='SUCCESS',
        category='LEAVE',
        link='/employee/leave/',
        sender=approved_by,
        send_email=True,
        tenant=tenant
    )


def notify_leave_rejection(leave_request, rejected_by, reason='', tenant=None):
    """Notify employee about leave rejection"""
    message = f"Your {leave_request.leave_type} leave request from {leave_request.start_date} to {leave_request.end_date} has been rejected."
    if reason:
        message += f" Reason: {reason}"
    
    create_notification(
        recipient=leave_request.employee,
        title="Leave Request Rejected",
        message=message,
        notification_type='WARNING',
        category='LEAVE',
        link='/employee/leave/',
        sender=rejected_by,
        send_email=True,
        tenant=tenant
    )


def notify_document_upload(document, tenant=None):
    """Notify relevant users about document upload"""
    employee = document.employee
    
    # Notify HR and Admin
    reviewers = User.objects.filter(
        company=employee.company,
        role__in=['EMPLOYER_ADMIN', 'ADMINISTRATOR', 'HR']
    )
    
    for reviewer in reviewers:
        create_notification(
            recipient=reviewer,
            title=f"New Document Uploaded by {employee.get_full_name()}",
            message=f"{employee.get_full_name()} has uploaded a new document: {document.title}",
            notification_type='INFO',
            category='DOCUMENT',
            link='/documents/',
            sender=employee,
            send_email=True,
            tenant=tenant
        )


def notify_document_approval(document, approved_by, tenant=None):
    """Notify employee about document approval"""
    create_notification(
        recipient=document.employee,
        title="Document Approved",
        message=f"Your document '{document.title}' has been approved.",
        notification_type='SUCCESS',
        category='DOCUMENT',
        link='/employee/',
        sender=approved_by,
        send_email=True,
        tenant=tenant
    )


def notify_document_rejection(document, rejected_by, reason='', tenant=None):
    """Notify employee about document rejection"""
    message = f"Your document '{document.title}' has been rejected."
    if reason:
        message += f" Reason: {reason}"
    
    create_notification(
        recipient=document.employee,
        title="Document Rejected",
        message=message,
        notification_type='WARNING',
        category='DOCUMENT',
        link='/employee/',
        sender=rejected_by,
        send_email=True,
        tenant=tenant
    )


def notify_payroll_generated(payroll, tenant=None):
    """Notify employee about payroll generation"""
    create_notification(
        recipient=payroll.employee,
        title="Payroll Generated",
        message=f"Your payroll for {payroll.period_start} to {payroll.period_end} has been generated. Net pay: {payroll.currency} {payroll.net_pay}",
        notification_type='INFO',
        category='PAYROLL',
        link='/payroll/',
        send_email=True,
        tenant=tenant
    )


def notify_performance_review(review, tenant=None):
    """Notify employee about performance review"""
    create_notification(
        recipient=review.employee,
        title="New Performance Review",
        message=f"A new performance review has been created for the period {review.review_period_start} to {review.review_period_end}.",
        notification_type='INFO',
        category='PERFORMANCE',
        link=f'/performance/{review.id}/',
        sender=review.reviewer,
        send_email=True,
        tenant=tenant
    )


def notify_training_enrollment(enrollment, tenant=None):
    """Notify employee about training enrollment"""
    create_notification(
        recipient=enrollment.employee,
        title="Training Enrollment",
        message=f"You have been enrolled in the training program: {enrollment.program.name}",
        notification_type='INFO',
        category='TRAINING',
        link='/training/',
        send_email=True,
        tenant=tenant
    )


def notify_onboarding_assigned(onboarding, tenant=None):
    """Notify employee about onboarding assignment"""
    create_notification(
        recipient=onboarding.employee,
        title="Welcome! Onboarding Process Started",
        message=f"Your onboarding process has been initiated. Please complete all required tasks.",
        notification_type='INFO',
        category='ONBOARDING',
        link='/onboarding/',
        send_email=True,
        tenant=tenant
    )


def notify_attendance_missing(employee, date, tenant=None):
    """Notify employee about missing attendance"""
    create_notification(
        recipient=employee,
        title="Missing Attendance Record",
        message=f"Your attendance record for {date} is missing. Please update it.",
        notification_type='WARNING',
        category='ATTENDANCE',
        link='/employee/attendance/',
        send_email=True,
        tenant=tenant
    )


def notify_benefit_enrollment(enrollment, tenant=None):
    """Notify employee about benefit enrollment"""
    create_notification(
        recipient=enrollment.employee,
        title="Benefit Enrollment Confirmed",
        message=f"You have been enrolled in {enrollment.benefit.name}. Effective date: {enrollment.effective_date}",
        notification_type='SUCCESS',
        category='PAYROLL',
        link='/benefits/',
        send_email=True,
        tenant=tenant
    )


def bulk_notify(recipients, title, message, notification_type='INFO', category='SYSTEM', link='', sender=None, send_email=False, tenant=None):
    """Send notification to multiple recipients"""
    notifications = []
    for recipient in recipients:
        notification = create_notification(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            category=category,
            link=link,
            sender=sender,
            send_email=send_email,
            tenant=tenant
        )
        notifications.append(notification)
    return notifications
