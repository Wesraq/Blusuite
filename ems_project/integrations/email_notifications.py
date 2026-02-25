"""
Email Notification System
Handles email notifications for various EMS events
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Service for sending email notifications
    """
    
    FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ems.com')
    
    @classmethod
    def send_leave_request_notification(cls, leave_request, recipient_email):
        """
        Send email notification for new leave request
        """
        subject = f'New Leave Request from {leave_request.employee.get_full_name()}'
        
        context = {
            'employee': leave_request.employee,
            'leave_type': leave_request.get_leave_type_display(),
            'start_date': leave_request.start_date,
            'end_date': leave_request.end_date,
            'duration': leave_request.duration,
            'reason': leave_request.reason,
        }
        
        html_message = render_to_string('emails/leave_request.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, recipient_email, html_message)
    
    @classmethod
    def send_leave_approval_notification(cls, leave_request):
        """
        Send email notification when leave is approved/rejected
        """
        status = leave_request.get_status_display()
        subject = f'Leave Request {status}'
        
        context = {
            'employee': leave_request.employee,
            'leave_type': leave_request.get_leave_type_display(),
            'start_date': leave_request.start_date,
            'end_date': leave_request.end_date,
            'status': status,
            'approved_by': leave_request.approved_by,
            'rejection_reason': leave_request.rejection_reason,
        }
        
        html_message = render_to_string('emails/leave_approval.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, leave_request.employee.email, html_message)
    
    @classmethod
    def send_employee_request_notification(cls, employee_request, recipient_emails):
        """
        Send email notification for new employee request
        """
        subject = f'New {employee_request.request_type.name} Request'
        
        context = {
            'employee': employee_request.employee,
            'request_type': employee_request.request_type.name,
            'description': employee_request.description,
            'amount': employee_request.amount,
            'created_at': employee_request.created_at,
        }
        
        html_message = render_to_string('emails/employee_request.html', context)
        plain_message = strip_tags(html_message)
        
        for email in recipient_emails:
            cls._send_email(subject, plain_message, email, html_message)
        
        return True
    
    @classmethod
    def send_request_approval_notification(cls, employee_request):
        """
        Send email notification when request is approved/rejected
        """
        status = employee_request.get_status_display()
        subject = f'Request {status}: {employee_request.request_type.name}'
        
        context = {
            'employee': employee_request.employee,
            'request_type': employee_request.request_type.name,
            'status': status,
            'approved_by': employee_request.approved_by,
            'approval_notes': employee_request.approval_notes,
        }
        
        html_message = render_to_string('emails/request_approval.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, employee_request.employee.email, html_message)
    
    @classmethod
    def send_document_approval_notification(cls, document):
        """
        Send email notification for document approval/rejection
        """
        status = document.get_verification_status_display()
        subject = f'Document {status}: {document.document_type}'
        
        context = {
            'employee': document.employee,
            'document_type': document.document_type,
            'status': status,
            'verified_by': document.verified_by,
        }
        
        html_message = render_to_string('emails/document_approval.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, document.employee.email, html_message)
    
    @classmethod
    def send_attendance_alert(cls, employee, alert_type, message):
        """
        Send email alert for attendance issues
        """
        subject = f'Attendance Alert: {alert_type}'
        
        context = {
            'employee': employee,
            'alert_type': alert_type,
            'message': message,
            'date': timezone.now().date(),
        }
        
        html_message = render_to_string('emails/attendance_alert.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, employee.email, html_message)
    
    @classmethod
    def send_payroll_notification(cls, payroll):
        """
        Send email notification for payroll generation
        """
        subject = f'Payroll Generated - {payroll.period_start} to {payroll.period_end}'
        
        context = {
            'employee': payroll.employee,
            'period_start': payroll.period_start,
            'period_end': payroll.period_end,
            'gross_salary': payroll.gross_salary,
            'total_deductions': payroll.total_deductions,
            'net_salary': payroll.net_salary,
        }
        
        html_message = render_to_string('emails/payroll_notification.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, payroll.employee.email, html_message)
    
    @classmethod
    def send_contract_expiry_alert(cls, employee, days_remaining):
        """
        Send email alert for contract expiry
        """
        subject = f'Contract Expiry Alert - {days_remaining} days remaining'
        
        context = {
            'employee': employee,
            'days_remaining': days_remaining,
            'contract_end_date': employee.employee_profile.contract_end_date,
        }
        
        html_message = render_to_string('emails/contract_expiry.html', context)
        plain_message = strip_tags(html_message)
        
        # Send to both employee and HR
        cls._send_email(subject, plain_message, employee.email, html_message)
        
        # Send to HR team
        hr_emails = cls._get_hr_emails(employee.company)
        for hr_email in hr_emails:
            cls._send_email(subject, plain_message, hr_email, html_message)
        
        return True
    
    @classmethod
    def send_onboarding_welcome(cls, employee):
        """
        Send welcome email for new employee onboarding
        """
        subject = 'Welcome to the Team!'
        
        context = {
            'employee': employee,
            'company': employee.company,
            'start_date': employee.employee_profile.date_hired if hasattr(employee, 'employee_profile') else None,
        }
        
        html_message = render_to_string('emails/onboarding_welcome.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, employee.email, html_message)
    
    @classmethod
    def send_training_enrollment_notification(cls, enrollment):
        """
        Send email notification for training enrollment
        """
        subject = f'Enrolled in Training: {enrollment.program.name}'
        
        context = {
            'employee': enrollment.employee,
            'program': enrollment.program,
            'start_date': enrollment.program.start_date,
            'end_date': enrollment.program.end_date,
        }
        
        html_message = render_to_string('emails/training_enrollment.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, enrollment.employee.email, html_message)
    
    @classmethod
    def send_benefit_enrollment_confirmation(cls, benefit_enrollment):
        """
        Send email confirmation for benefit enrollment
        """
        subject = f'Benefit Enrollment Confirmed: {benefit_enrollment.benefit.name}'
        
        context = {
            'employee': benefit_enrollment.employee,
            'benefit': benefit_enrollment.benefit,
            'enrollment_date': benefit_enrollment.enrollment_date,
            'effective_date': benefit_enrollment.effective_date,
        }
        
        html_message = render_to_string('emails/benefit_enrollment.html', context)
        plain_message = strip_tags(html_message)
        
        return cls._send_email(subject, plain_message, benefit_enrollment.employee.email, html_message)
    
    @classmethod
    def _send_email(cls, subject, plain_message, recipient_email, html_message=None):
        """
        Internal method to send email
        """
        try:
            if html_message:
                msg = EmailMultiAlternatives(
                    subject,
                    plain_message,
                    cls.FROM_EMAIL,
                    [recipient_email]
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send()
            else:
                send_mail(
                    subject,
                    plain_message,
                    cls.FROM_EMAIL,
                    [recipient_email],
                    fail_silently=False,
                )
            
            logger.info(f"Email sent to {recipient_email}: {subject}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
            return False
    
    @classmethod
    def _get_hr_emails(cls, company):
        """
        Get list of HR email addresses for a company
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        hr_users = User.objects.filter(
            company=company,
            employee_profile__employee_role='HR'
        ).values_list('email', flat=True)
        
        return list(hr_users)


# Convenience functions for easy use
def notify_leave_request(leave_request):
    """Send notifications for new leave request"""
    # Get HR emails
    hr_emails = EmailNotificationService._get_hr_emails(leave_request.employee.company)
    for email in hr_emails:
        EmailNotificationService.send_leave_request_notification(leave_request, email)
    
    # Send Slack notification if configured
    try:
        from accounts.integration_models import CompanyIntegration
        slack_integration = CompanyIntegration.objects.filter(
            company=leave_request.employee.company,
            integration__integration_type='SLACK',
            status='ACTIVE'
        ).first()
        
        if slack_integration:
            from integrations.slack_integration import send_slack_notification
            send_slack_notification(
                slack_integration,
                'leave_request',
                {
                    'employee': leave_request.employee.get_full_name(),
                    'leave_type': leave_request.get_leave_type_display(),
                    'start_date': str(leave_request.start_date),
                    'end_date': str(leave_request.end_date),
                    'reason': leave_request.reason,
                }
            )
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {str(e)}")


def notify_employee_request(employee_request):
    """Send notifications for new employee request"""
    # Get HR and manager emails
    hr_emails = EmailNotificationService._get_hr_emails(employee_request.employee.company)
    EmailNotificationService.send_employee_request_notification(employee_request, hr_emails)
    
    # Send Slack notification if configured
    try:
        from accounts.integration_models import CompanyIntegration
        slack_integration = CompanyIntegration.objects.filter(
            company=employee_request.employee.company,
            integration__integration_type='SLACK',
            status='ACTIVE'
        ).first()
        
        if slack_integration:
            from integrations.slack_integration import send_slack_notification
            send_slack_notification(
                slack_integration,
                'employee_request',
                {
                    'employee': employee_request.employee.get_full_name(),
                    'request_type': employee_request.request_type.name,
                    'description': employee_request.description,
                    'amount': str(employee_request.amount) if employee_request.amount else '',
                }
            )
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {str(e)}")
