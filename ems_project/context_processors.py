"""
Context processors for EMS application
"""
from django.db.models import Q
from blu_staff.apps.accounts.models import SystemSettings


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
        'pending_asset_requests_count': 0,
        'pending_documents_count': 0,
        'expiring_contracts_count': 0,
        'pending_training_count': 0,
        'total_badge_count': 0,
        'new_feed_posts_count': 0,
    }

    if request.user.is_authenticated:
        user = request.user
        
        try:
            # Feed: new posts in last 24 hours for the user's company
            from datetime import timezone as _tz
            from ems_project.models import FeedPost
            _company = getattr(user, 'company', None)
            _tenant = getattr(_company, 'tenant', None) if _company else None
            if _tenant:
                _since = date.today() - timedelta(hours=24)
                context['new_feed_posts_count'] = FeedPost.objects.filter(
                    tenant=_tenant,
                    created_at__date__gte=_since,
                ).exclude(author=user).count()
        except Exception:
            pass

        try:
            # Get unread notifications count
            from blu_staff.apps.notifications.models import Notification
            unread_notifications = Notification.objects.filter(
                recipient=user,
                is_read=False
            ).count()
            context['unread_notifications_count'] = unread_notifications

            # Get unread messages count (direct messages)
            from blu_staff.apps.communication.models import DirectMessage
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
                from blu_staff.apps.attendance.models import LeaveRequest
                context['pending_leave_count'] = LeaveRequest.objects.filter(
                    employee__company=user.company,
                    status='PENDING'
                ).count()
            except:
                pass
            
            try:
                # Pending employee requests (petty cash, advances, etc.)
                from blu_staff.apps.requests.models import EmployeeRequest
                context['pending_requests_count'] = EmployeeRequest.objects.filter(
                    employee__company=user.company,
                    status='PENDING'
                ).count()
            except:
                pass
            
            try:
                # Pending documents
                from blu_staff.apps.documents.models import EmployeeDocument
                context['pending_documents_count'] = EmployeeDocument.objects.filter(
                    employee__company=user.company,
                    approval_status='PENDING'
                ).count()
            except:
                pass
            
            try:
                # Expiring contracts (next 30 days)
                from blu_staff.apps.accounts.models import EmployeeProfile
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
                from blu_staff.apps.training.models import TrainingRequest
                context['pending_training_count'] = TrainingRequest.objects.filter(
                    employee__company=user.company,
                    status='PENDING'
                ).count()
            except:
                pass
            
            try:
                # Pending asset requests (for AMS sidebar badge)
                from blu_assets.models import AssetRequest
                context['pending_asset_requests_count'] = AssetRequest.objects.filter(
                    department__company=user.company,
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


def company_settings_context(request):
    """Provide company settings and module visibility to all templates"""
    context = {
        'company_settings': None,
        'modules_enabled': {
            'attendance': True,
            'leave': True,
            'payroll': True,
            'performance': True,
            'training': True,
            'onboarding': True,
            'assets': True,
            'eforms': True,
            'benefits': True,
            'documents': True,
            'requests': True,
            'communication': True,
            'reports': True,
        }
    }
    
    if request.user.is_authenticated and hasattr(request.user, 'company') and request.user.company:
        try:
            from blu_staff.apps.accounts.models import CompanySettings
            settings = CompanySettings.get_for_company(request.user.company)
            context['company_settings'] = settings
            context['modules_enabled'] = {
                'attendance': settings.enable_attendance,
                'leave': settings.enable_leave,
                'payroll': settings.enable_payroll,
                'performance': settings.enable_performance,
                'training': settings.enable_training,
                'onboarding': settings.enable_onboarding,
                'assets': settings.enable_assets,
                'eforms': settings.enable_eforms,
                'benefits': settings.enable_benefits,
                'documents': settings.enable_documents,
                'requests': settings.enable_requests,
                'communication': settings.enable_communication,
                'reports': settings.enable_reports,
            }
        except Exception:
            pass
    
    # Expose sidebar visibility flags globally (every page needs these)
    modules = context['modules_enabled']
    context['show_attendance']     = modules.get('attendance', True)
    context['show_leave']          = modules.get('leave', True)
    context['show_payroll']        = modules.get('payroll', True)
    context['show_performance']    = modules.get('performance', True)
    context['show_documents']      = modules.get('documents', True)
    context['show_reports']        = modules.get('reports', True)
    context['show_analytics_suite']= True

    return context


CURRENCY_MAP = {
    'Zambia':         {'code': 'ZMW', 'symbol': 'ZMW', 'rate': 1},
    'Malawi':         {'code': 'MWK', 'symbol': 'MWK', 'rate': 25},
    'Kenya':          {'code': 'KES', 'symbol': 'KES', 'rate': 4},
    'Tanzania':       {'code': 'TZS', 'symbol': 'TZS', 'rate': 80},
    'Uganda':         {'code': 'UGX', 'symbol': 'UGX', 'rate': 120},
    'South Africa':   {'code': 'ZAR', 'symbol': 'R',   'rate': 0.6},
    'Nigeria':        {'code': 'NGN', 'symbol': 'NGN', 'rate': 50},
    'Ghana':          {'code': 'GHS', 'symbol': 'GHS', 'rate': 0.4},
    'Zimbabwe':       {'code': 'ZWL', 'symbol': 'ZWL', 'rate': 10},
    'Botswana':       {'code': 'BWP', 'symbol': 'BWP', 'rate': 0.4},
    'Mozambique':     {'code': 'MZN', 'symbol': 'MZN', 'rate': 2},
    'United States':  {'code': 'USD', 'symbol': '$',   'rate': 0.033},
    'United Kingdom': {'code': 'GBP', 'symbol': 'GBP', 'rate': 0.026},
}

DEFAULT_CURRENCY = {'code': 'ZMW', 'symbol': 'ZMW', 'rate': 1}


def get_company_currency(company):
    """Return the currency dict for a company based on its country."""
    country = getattr(company, 'country', '') or 'Zambia'
    return CURRENCY_MAP.get(country, DEFAULT_CURRENCY)


def currency_context(request):
    """Inject currency_symbol, currency_code, and currency_rate into every template."""
    currency = DEFAULT_CURRENCY
    if request.user.is_authenticated:
        company = getattr(request.user, 'company', None)
        if not company:
            company = getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        if not company:
            company = getattr(getattr(request.user, 'employee_profile', None), 'company', None)
        if company:
            currency = get_company_currency(company)
    return {
        'currency_symbol': currency['symbol'],
        'currency_code': currency['code'],
        'currency_rate': currency['rate'],
    }


def system_settings_context(request):
    system_settings = None
    maintenance_mode = False
    maintenance_message = 'The system is currently under maintenance. Please try again later.'
    feature_billing_enabled = True
    feature_support_enabled = True
    feature_analytics_enabled = True
    try:
        system_settings = SystemSettings.get_solo()
        maintenance_mode = bool(getattr(system_settings, 'maintenance_mode', False))
        maintenance_message = getattr(system_settings, 'maintenance_message', maintenance_message)
    except Exception:
        pass
    return {
        'system_settings': system_settings,
        'maintenance_mode': maintenance_mode,
        'maintenance_message': maintenance_message,
        'feature_billing_enabled': feature_billing_enabled if system_settings is None else bool(getattr(system_settings, 'enable_billing_module', True)),
        'feature_support_enabled': feature_support_enabled if system_settings is None else bool(getattr(system_settings, 'enable_support_module', True)),
        'feature_analytics_enabled': feature_analytics_enabled if system_settings is None else bool(getattr(system_settings, 'enable_analytics_module', True)),
    }
