"""
Context processors for EMS application
"""
from django.db.models import Q


def user_role_context(request):
    """
    Add user role information to all templates
    """
    context = {}

    if request.user.is_authenticated:
        context['current_user_role'] = request.user.role
        context['is_superadmin'] = request.user.role == 'SUPERADMIN'
        context['is_admin'] = request.user.role == 'SUPERADMIN'  # Fixed: was 'ADMIN' but model defines 'SUPERADMIN'
        context['is_administrator'] = request.user.role == 'ADMINISTRATOR'
        context['is_employer_admin'] = request.user.role == 'EMPLOYER_ADMIN'
        context['is_employee'] = request.user.role == 'EMPLOYEE'
        context['is_employer'] = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        context['can_manage_company'] = request.user.role in ['SUPERADMIN', 'ADMINISTRATOR']
        context['can_manage_employees'] = request.user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']
        context['can_approve_companies'] = request.user.role == 'SUPERADMIN'

        # User session info
        context['user_id'] = request.session.get('user_id')
        context['user_email'] = request.session.get('user_email')
        context['user_role_session'] = request.session.get('user_role')

    return context


def unread_counts(request):
    """
    Add unread message and notification counts + comprehensive badge system to template context
    """
    from datetime import date, timedelta
    
    context = {
        'unread_messages_count': 0,
        'unread_notifications_count': 0,
        'pending_leave_count': 0,
        'pending_requests_count': 0,
        'pending_documents_count': 0,
        'expiring_contracts_count': 0,
        'pending_training_count': 0,
        'total_badge_count': 0,
    }

    if request.user.is_authenticated:
        user = request.user
        
        try:
            # Get unread notifications count
            from notifications.models import Notification
            unread_notifications = Notification.objects.filter(
                recipient=user,
                is_read=False
            ).count()
            context['unread_notifications_count'] = unread_notifications

            # Get unread messages count (direct messages)
            from communication.models import DirectMessage
            unread_messages = DirectMessage.objects.filter(
                recipient=user,
                is_read=False
            ).count()
            context['unread_messages_count'] = unread_messages

        except Exception:
            pass
        
        # For HR and Admins - pending approval counts
        is_hr = False
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or user.is_employer_admin:
            is_hr = True
        elif hasattr(user, 'employee_profile') and user.employee_profile:
            if user.employee_profile.employee_role == 'HR':
                is_hr = True
        
        if is_hr and hasattr(user, 'company') and user.company:
            try:
                # Pending leave requests
                from attendance.models import LeaveRequest
                context['pending_leave_count'] = LeaveRequest.objects.filter(
                    employee__company=user.company,
                    status='PENDING'
                ).count()
            except:
                pass
            
            try:
                # Pending employee requests (petty cash, advances, etc.)
                from requests.models import EmployeeRequest
                context['pending_requests_count'] = EmployeeRequest.objects.filter(
                    employee__company=user.company,
                    status='PENDING'
                ).count()
            except:
                pass
            
            try:
                # Pending documents
                from documents.models import EmployeeDocument
                context['pending_documents_count'] = EmployeeDocument.objects.filter(
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
                
                context['expiring_contracts_count'] = EmployeeProfile.objects.filter(
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
                context['pending_training_count'] = TrainingRequest.objects.filter(
                    employee__company=user.company,
                    status='PENDING'
                ).count()
            except:
                pass
        
        # Calculate total badge count
        context['total_badge_count'] = sum([
            context['unread_notifications_count'],
            context['pending_leave_count'],
            context['pending_requests_count'],
            context['pending_documents_count'],
            context['pending_training_count'],
        ])

    return context
