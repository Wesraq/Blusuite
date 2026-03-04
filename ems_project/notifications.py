import os
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


class EmailNotificationService:
    """Service for sending email notifications"""

    @staticmethod
    def send_welcome_email(user):
        """Send welcome email to new user"""
        subject = 'Welcome to Employee Management System'
        html_message = render_to_string('emails/welcome.html', {
            'user': user,
            'login_url': settings.SITE_URL + reverse('admin:login')
        })
        plain_message = strip_tags(html_message)

        EmailNotificationService._send_email(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            recipient_list=[user.email]
        )

    @staticmethod
    def send_leave_request_notification(leave_request, action='submitted'):
        """Send notification for leave request actions"""
        if action == 'submitted':
            subject = f'Leave Request Submitted - {leave_request.employee.get_full_name()}'
            template = 'emails/leave_submitted.html'
        elif action == 'approved':
            subject = f'Leave Request Approved - {leave_request.employee.get_full_name()}'
            template = 'emails/leave_approved.html'
        elif action == 'rejected':
            subject = f'Leave Request Rejected - {leave_request.employee.get_full_name()}'
            template = 'emails/leave_rejected.html'
        else:
            return

        # Send to employee
        html_message = render_to_string(template, {
            'leave_request': leave_request,
            'employee': leave_request.employee
        })
        plain_message = strip_tags(html_message)

        EmailNotificationService._send_email(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            recipient_list=[leave_request.employee.email]
        )

        # Notify admin/employer about new leave request
        if action == 'submitted':
            manager_roles = ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']
            manager_users = User.objects.filter(role__in=manager_roles)

            for manager in manager_users:
                EmailNotificationService._send_email(
                    subject=f'New Leave Request: {leave_request.employee.get_full_name()}',
                    message=f"A new leave request has been submitted by {leave_request.employee.get_full_name()}",
                    recipient_list=[manager.email]
                )

    @staticmethod
    def send_performance_review_notification(review, action='scheduled'):
        """Send notification for performance review actions"""
        if action == 'scheduled':
            subject = f'Performance Review Scheduled - {review.employee.get_full_name()}'
            template = 'emails/review_scheduled.html'
        elif action == 'completed':
            subject = f'Performance Review Completed - {review.employee.get_full_name()}'
            template = 'emails/review_completed.html'
        else:
            return

        html_message = render_to_string(template, {
            'review': review,
            'employee': review.employee,
            'reviewer': review.reviewer
        })
        plain_message = strip_tags(html_message)

        # Send to employee
        EmailNotificationService._send_email(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            recipient_list=[review.employee.email]
        )

        # Notify reviewer
        if review.reviewer and review.reviewer != review.employee:
            EmailNotificationService._send_email(
                subject=f'Performance Review to Complete - {review.employee.get_full_name()}',
                message=f"You have a performance review to complete for {review.employee.get_full_name()}",
                recipient_list=[review.reviewer.email]
            )

    @staticmethod
    def send_document_notification(document, action='uploaded'):
        """Send notification for document actions"""
        if action == 'uploaded':
            subject = f'Document Uploaded - {document.title}'
            template = 'emails/document_uploaded.html'
        elif action == 'approved':
            subject = f'Document Approved - {document.title}'
            template = 'emails/document_approved.html'
        elif action == 'rejected':
            subject = f'Document Rejected - {document.title}'
            template = 'emails/document_rejected.html'
        else:
            return

        html_message = render_to_string(template, {
            'document': document,
            'employee': document.employee
        })
        plain_message = strip_tags(html_message)

        # Send to employee
        EmailNotificationService._send_email(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            recipient_list=[document.employee.email]
        )

        # Notify approver
        if hasattr(document, 'approved_by') and document.approved_by:
            EmailNotificationService._send_email(
                subject=f'Document to Review - {document.employee.get_full_name()}',
                message=f"A document has been uploaded by {document.employee.get_full_name()} and requires your review",
                recipient_list=[document.approved_by.email]
            )

    @staticmethod
    def send_attendance_reminder(employee, date=None):
        """Send attendance reminder"""
        if date is None:
            date = timezone.now().date()

        subject = f'Attendance Reminder - {date.strftime("%Y-%m-%d")}'
        html_message = render_to_string('emails/attendance_reminder.html', {
            'employee': employee,
            'date': date
        })
        plain_message = strip_tags(html_message)

        EmailNotificationService._send_email(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            recipient_list=[employee.email]
        )

    @staticmethod
    def send_password_reset_email(user, reset_url):
        """Send password reset email"""
        subject = 'Password Reset Request'
        html_message = render_to_string('emails/password_reset.html', {
            'user': user,
            'reset_url': reset_url
        })
        plain_message = strip_tags(html_message)

        EmailNotificationService._send_email(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            recipient_list=[user.email]
        )

    @staticmethod
    def send_new_employee_credentials(employee, temporary_password, created_by=None):
        """Send login credentials to newly created employee"""
        subject = f'Welcome to {employee.company.company_name if employee.company else "Employee Management System"}'
        
        try:
            html_message = render_to_string('emails/new_employee_credentials.html', {
                'employee': employee,
                'password': temporary_password,
                'login_url': settings.SITE_URL or 'http://127.0.0.1:8000',
                'company': employee.company,
                'created_by': created_by
            })
        except Exception as e:
            # Fallback to plain text if template doesn't exist
            html_message = f"""
            <html>
            <body>
                <h2>Welcome to {employee.company.company_name if employee.company else "Employee Management System"}!</h2>
                <p>Dear {employee.get_full_name()},</p>
                <p>Your employee account has been created. Here are your login credentials:</p>
                <p><strong>Email:</strong> {employee.email}<br>
                <strong>Temporary Password:</strong> {temporary_password}</p>
                <p>Please login at: {settings.SITE_URL or 'http://127.0.0.1:8000'}</p>
                <p><strong>Important:</strong> Please change your password after your first login.</p>
            </body>
            </html>
            """
        
        plain_message = strip_tags(html_message)

        EmailNotificationService._send_email(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            recipient_list=[employee.email]
        )

    @staticmethod
    def send_password_changed_notification(employee, new_password, changed_by):
        """Send notification when password is reset by admin"""
        subject = f'Your Password Has Been Reset - {employee.company.company_name if employee.company else "EMS"}'
        
        try:
            html_message = render_to_string('emails/password_reset_by_admin.html', {
                'employee': employee,
                'password': new_password,
                'changed_by': changed_by,
                'login_url': settings.SITE_URL or 'http://127.0.0.1:8000',
                'company': employee.company
            })
        except Exception as e:
            # Fallback to plain text if template doesn't exist
            html_message = f"""
            <html>
            <body>
                <h2>Password Reset Notification</h2>
                <p>Dear {employee.get_full_name()},</p>
                <p>Your password has been reset by {changed_by.get_full_name() if changed_by else 'an administrator'}.</p>
                <p><strong>New Password:</strong> {new_password}</p>
                <p>Please login at: {settings.SITE_URL or 'http://127.0.0.1:8000'}</p>
                <p><strong>Important:</strong> Please change this password after logging in.</p>
            </body>
            </html>
            """
        
        plain_message = strip_tags(html_message)

        EmailNotificationService._send_email(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            recipient_list=[employee.email]
        )

    @staticmethod
    def _send_email(subject, message, html_message, recipient_list):
        """Internal method to send email"""
        try:
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings

            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipient_list
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to send email '{subject}' to {recipient_list}: {e}")


class NotificationManager:
    """Manager for handling various system notifications"""

    @staticmethod
    def notify_user_registration(user):
        """Notify admin about new user registration"""
        EmailNotificationService.send_welcome_email(user)

        # Notify administrative users
        manager_roles = ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']
        admin_users = User.objects.filter(role__in=manager_roles)
        for manager in admin_users:
            message = f'A new user has registered: {user.email} ({user.get_full_name()}) with role {user.role}'
            EmailNotificationService._send_email(
                subject='New User Registration',
                message=message,
                html_message=f'<p>{message}</p>',
                recipient_list=[manager.email]
            )

    @staticmethod
    def notify_leave_request(leave_request, action='submitted'):
        """Handle leave request notifications"""
        EmailNotificationService.send_leave_request_notification(leave_request, action)

    @staticmethod
    def notify_performance_review(review, action='scheduled'):
        """Handle performance review notifications"""
        EmailNotificationService.send_performance_review_notification(review, action)

    @staticmethod
    def notify_document_upload(document, action='uploaded'):
        """Handle document upload notifications"""
        EmailNotificationService.send_document_notification(document, action)

    @staticmethod
    def send_daily_attendance_report():
        """Send daily attendance report to managers"""
        today = timezone.now().date()

        # Get employer users
        employers = User.objects.filter(role='EMPLOYER')

        for employer in employers:
            # Get employees under this employer
            employees = User.objects.filter(
                employee_profile__user__employer_profile__user=employer
            )

            present_count = 0
            absent_count = 0

            for employee in employees:
                attendance = Attendance.objects.filter(
                    employee=employee,
                    date=today
                ).first()

                if attendance and attendance.status == 'PRESENT':
                    present_count += 1
                else:
                    absent_count += 1

            subject = f'Daily Attendance Report - {today.strftime("%Y-%m-%d")}'
            message = f"""
Daily Attendance Report for {employer.company_name}

Total Employees: {employees.count()}
Present Today: {present_count}
Absent Today: {absent_count}

Please check the admin panel for detailed attendance records.
"""

            EmailNotificationService._send_email(
                subject=subject,
                message=message,
                recipient_list=[employer.email]
            )
