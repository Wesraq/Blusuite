"""
Context processor for notification badges
Adds notification counts to all templates
"""
from django.utils import timezone
from datetime import timedelta, date


def notification_badges(request):
    """
    Add notification badge counts to template context
    """
    if not request.user.is_authenticated:
        return {}
    
    user = request.user
    badges = {
        'unread_notifications': 0,
        'pending_requests': 0,
        'pending_leave': 0,
        'expiring_contracts': 0,
        'training_pending': 0,
        'document_pending': 0,
        'total_notifications': 0,
    }
    
    try:
        # Unread notifications
        from notifications.models import Notification
        badges['unread_notifications'] = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).count()
    except:
        pass
    
    # For HR and Admins - approval counts
    if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or user.is_employer_admin:
        try:
            # Pending leave requests
            from attendance.models import LeaveRequest
            badges['pending_leave'] = LeaveRequest.objects.filter(
                employee__company=user.company,
                status='PENDING'
            ).count()
        except:
            pass
        
        try:
            # Pending employee requests (petty cash, advances, etc.)
            from requests.models import EmployeeRequest
            badges['pending_requests'] = EmployeeRequest.objects.filter(
                employee__company=user.company,
                status='PENDING'
            ).count()
        except:
            pass
        
        try:
            # Pending documents
            from documents.models import EmployeeDocument
            badges['document_pending'] = EmployeeDocument.objects.filter(
                employee__company=user.company,
                approval_status='PENDING'
            ).count()
        except:
            pass
        
        try:
            # Expiring contracts (next 30 days)
            from accounts.models import EmployeeProfile
            today = date.today()
            thirty_days = today + timedelta(days=30)
            
            badges['expiring_contracts'] = EmployeeProfile.objects.filter(
                user__company=user.company,
                employment_type='CONTRACT',
                contract_end_date__gte=today,
                contract_end_date__lte=thirty_days
            ).count()
        except:
            pass
        
        try:
            # Pending training requests
            from training.models import TrainingRequest
            badges['training_pending'] = TrainingRequest.objects.filter(
                employee__company=user.company,
                status='PENDING'
            ).count()
        except:
            pass
    
    # For HR employees with employee_profile
    elif hasattr(user, 'employee_profile') and user.employee_profile:
        if user.employee_profile.employee_role == 'HR':
            try:
                from attendance.models import LeaveRequest
                badges['pending_leave'] = LeaveRequest.objects.filter(
                    employee__company=user.company,
                    status='PENDING'
                ).count()
            except:
                pass
            
            try:
                from requests.models import EmployeeRequest
                badges['pending_requests'] = EmployeeRequest.objects.filter(
                    employee__company=user.company,
                    status='PENDING'
                ).count()
            except:
                pass
            
            try:
                from documents.models import EmployeeDocument
                badges['document_pending'] = EmployeeDocument.objects.filter(
                    employee__company=user.company,
                    approval_status='PENDING'
                ).count()
            except:
                pass
            
            try:
                from accounts.models import EmployeeProfile
                today = date.today()
                thirty_days = today + timedelta(days=30)
                
                badges['expiring_contracts'] = EmployeeProfile.objects.filter(
                    user__company=user.company,
                    employment_type='CONTRACT',
                    contract_end_date__gte=today,
                    contract_end_date__lte=thirty_days
                ).count()
            except:
                pass
    
    # Calculate total
    badges['total_notifications'] = sum([
        badges['unread_notifications'],
        badges['pending_requests'],
        badges['pending_leave'],
        badges['document_pending'],
        badges['training_pending'],
    ])
    
    return {'badges': badges}
