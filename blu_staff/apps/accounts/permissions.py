from rest_framework import permissions
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

from tenant_management.permissions import IsTenantMember, HasTenantRole

User = get_user_model()


# Feature mapping for each subscription plan
PLAN_FEATURES = {
    'BASIC': {
        'max_employees': 25,
        'features': [
            'basic_attendance',
            'leave_management',
            'payroll_processing',
            'email_support',
            'mobile_app',
            'blusuite_hub',  # All plans have BluSuite Hub access
        ]
    },
    'STANDARD': {
        'max_employees': 100,
        'features': [
            'basic_attendance',
            'leave_management',
            'payroll_processing',
            'email_support',
            'mobile_app',
            'blusuite_hub',  # All plans have BluSuite Hub access
            'advanced_attendance',
            'gps_tracking',
            'leave_approvals',
            'automated_payroll',
            'performance_reviews',
            'document_management',
            'custom_reports',
            'priority_support',
        ]
    },
    'PROFESSIONAL': {
        'max_employees': 999999,  # Unlimited
        'features': [
            'basic_attendance',
            'leave_management',
            'payroll_processing',
            'email_support',
            'mobile_app',
            'blusuite_hub',  # All plans have BluSuite Hub access
            'advanced_attendance',
            'gps_tracking',
            'leave_approvals',
            'automated_payroll',
            'performance_reviews',
            'document_management',
            'custom_reports',
            'priority_support',
            'advanced_analytics',
            'custom_integrations',
            'dedicated_account_manager',
            'phone_support_24_7',
            'custom_training',
            'sla_guarantee',
            'bulk_import',
            'advanced_reports',
            'api_access',
        ]
    },
}

# URL patterns that require specific features
FEATURE_URL_MAPPING = {
    'performance_reviews': [
        '/performance/',
        '/performance/create/',
    ],
    'document_management': [
        '/documents/',
        '/documents/upload/',
    ],
    'custom_reports': [
        '/reports/custom/',
    ],
    'advanced_analytics': [
        '/analytics/dashboard/',
        '/analytics/',
    ],
    'bulk_import': [
        '/bulk-import/',
    ],
    'gps_tracking': [
        '/attendance/gps/',
    ],
    'advanced_reports': [
        '/reports/export/',
    ],
}


def get_company_plan(user):
    """Get the subscription plan for the user's company"""
    if hasattr(user, 'company') and user.company:
        return user.company.subscription_plan
    elif hasattr(user, 'employer_profile') and user.employer_profile and user.employer_profile.company:
        return user.employer_profile.company.subscription_plan
    elif hasattr(user, 'employee_profile') and user.employee_profile and user.employee_profile.company:
        return user.employee_profile.company.subscription_plan
    return 'BASIC'  # Default to basic if no company found


def has_feature_access(user, feature_name):
    """Check if user's company plan has access to a specific feature"""
    plan = get_company_plan(user)
    plan_config = PLAN_FEATURES.get(plan, PLAN_FEATURES['BASIC'])
    return feature_name in plan_config['features']


def get_plan_features(plan):
    """Get all features for a specific plan"""
    return PLAN_FEATURES.get(plan, PLAN_FEATURES['BASIC'])['features']


def require_feature(feature_name, redirect_url='/employer-admin/'):
    """
    Decorator to require a specific feature for a view
    Usage: @require_feature('performance_reviews')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Superadmins have access to everything
            if hasattr(request.user, 'role') and request.user.role == 'SUPERADMIN':
                return view_func(request, *args, **kwargs)
            
            if not has_feature_access(request.user, feature_name):
                plan = get_company_plan(request.user)
                messages.error(
                    request,
                    f'This feature is not available in your {plan} plan. Please upgrade to access this feature.'
                )
                return redirect(redirect_url)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_employee_limit(company):
    """Check if company has reached its employee limit"""
    plan_config = PLAN_FEATURES.get(company.subscription_plan, PLAN_FEATURES['BASIC'])
    max_employees = plan_config['max_employees']
    
    # Count active employees
    from .models import EmployeeProfile
    current_count = EmployeeProfile.objects.filter(
        company=company,
        user__is_active=True
    ).count()
    
    return current_count < max_employees, current_count, max_employees


class IsEmployerOrAdmin(HasTenantRole):
    """Allow tenant administrators and employer admins."""

    allowed_roles = ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']


class IsEmployeeOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow employees to edit their own data.
    Read only is allowed for unauthenticated users.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to authenticated employees within the tenant.
        return bool(
            request.user and
            request.user.is_authenticated and
            IsTenantMember().has_permission(request, view) and
            request.user.role == 'EMPLOYEE'
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to edit it.
    Assumes the model instance has an `employee` attribute.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to the owner of the object or tenant admin.
        is_owner = False
        if hasattr(obj, 'employee'):
            is_owner = obj.employee == request.user
        elif hasattr(obj, 'user'):
            is_owner = obj.user == request.user

        is_tenant_admin = HasTenantRole.allowed_roles.__contains__ if False else request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']

        return bool(
            request.user and
            request.user.is_authenticated and
            IsTenantMember().has_permission(request, view) and
            (is_owner or is_tenant_admin)
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    Read only is allowed for unauthenticated users.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to tenant admins or superadmins.
        return bool(
            request.user and
            request.user.is_authenticated and
            IsTenantMember().has_permission(request, view) and
            request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']
        )
