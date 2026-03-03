"""
Centralized plan-based feature enforcement for BLU Suite.

Each plan tier defines:
  - employee_limit: max employees allowed
  - features: set of feature keys the plan grants access to
  - price: base monthly price in ZMW

Feature keys map to specific modules/capabilities in the system.
Higher plans inherit all features from lower plans.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

# ── Feature key constants ──────────────────────────────────────────────
# Basic features
FEAT_ATTENDANCE_BASIC = 'attendance_basic'
FEAT_LEAVE_MANAGEMENT = 'leave_management'
FEAT_PAYROLL_BASIC = 'payroll_basic'
FEAT_EMAIL_SUPPORT = 'email_support'
FEAT_RESPONSIVE_WEB = 'responsive_web'

# Standard features (adds to Basic)
FEAT_ATTENDANCE_GPS = 'attendance_gps'
FEAT_LEAVE_APPROVALS = 'leave_approvals'
FEAT_PAYROLL_AUTOMATED = 'payroll_automated'
FEAT_PERFORMANCE_REVIEWS = 'performance_reviews'
FEAT_DOCUMENT_MANAGEMENT = 'document_management'
FEAT_CUSTOM_REPORTS = 'custom_reports'
FEAT_PRIORITY_SUPPORT = 'priority_support'

# Professional features (adds to Standard)
FEAT_ADVANCED_ANALYTICS = 'advanced_analytics'
FEAT_CUSTOM_INTEGRATIONS = 'custom_integrations'
FEAT_API_ACCESS = 'api_access'
FEAT_DEDICATED_MANAGER = 'dedicated_manager'
FEAT_PHONE_SUPPORT = 'phone_support'
FEAT_CUSTOM_TRAINING = 'custom_training'

# Enterprise features (adds to Professional)
FEAT_WHITE_LABEL = 'white_label'
FEAT_CUSTOM_SLA = 'custom_sla'
FEAT_ON_PREMISE = 'on_premise'
FEAT_SUPPORT_247 = 'support_247'
FEAT_CUSTOM_DEV = 'custom_dev'
FEAT_DATA_MIGRATION = 'data_migration'


# ── Plan definitions ───────────────────────────────────────────────────
BASIC_FEATURES = {
    FEAT_ATTENDANCE_BASIC,
    FEAT_LEAVE_MANAGEMENT,
    FEAT_PAYROLL_BASIC,
    FEAT_EMAIL_SUPPORT,
    FEAT_RESPONSIVE_WEB,
}

STANDARD_FEATURES = BASIC_FEATURES | {
    FEAT_ATTENDANCE_GPS,
    FEAT_LEAVE_APPROVALS,
    FEAT_PAYROLL_AUTOMATED,
    FEAT_PERFORMANCE_REVIEWS,
    FEAT_DOCUMENT_MANAGEMENT,
    FEAT_CUSTOM_REPORTS,
    FEAT_PRIORITY_SUPPORT,
    FEAT_CUSTOM_INTEGRATIONS,
}

PROFESSIONAL_FEATURES = STANDARD_FEATURES | {
    FEAT_ADVANCED_ANALYTICS,
    FEAT_API_ACCESS,
    FEAT_DEDICATED_MANAGER,
    FEAT_PHONE_SUPPORT,
    FEAT_CUSTOM_TRAINING,
}

ENTERPRISE_FEATURES = PROFESSIONAL_FEATURES | {
    FEAT_WHITE_LABEL,
    FEAT_CUSTOM_SLA,
    FEAT_ON_PREMISE,
    FEAT_SUPPORT_247,
    FEAT_CUSTOM_DEV,
    FEAT_DATA_MIGRATION,
}

PLAN_DEFINITIONS = {
    'BASIC': {
        'name': 'Starter',
        'employee_limit': 25,
        'price': 29.99,
        'features': BASIC_FEATURES,
    },
    # STANDARD kept for backward compat — treated as Professional tier
    'STANDARD': {
        'name': 'Professional',
        'employee_limit': 100,
        'price': 79.99,
        'features': PROFESSIONAL_FEATURES,
    },
    'PROFESSIONAL': {
        'name': 'Professional',
        'employee_limit': 100,
        'price': 79.99,
        'features': PROFESSIONAL_FEATURES,
    },
    'ENTERPRISE': {
        'name': 'Enterprise',
        'employee_limit': 99999,
        'price': 199.99,
        'features': ENTERPRISE_FEATURES,
    },
}

# Plan hierarchy for comparisons (higher index = higher tier)
PLAN_HIERARCHY = ['BASIC', 'STANDARD', 'PROFESSIONAL', 'ENTERPRISE']


# ── Helper functions ───────────────────────────────────────────────────

def get_company_plan(company):
    """Return the subscription plan key for a company (defaults to BASIC)."""
    if not company:
        return 'BASIC'
    plan = getattr(company, 'subscription_plan', 'BASIC') or 'BASIC'
    return plan.upper() if plan.upper() in PLAN_DEFINITIONS else 'BASIC'


def get_plan_features(plan_key):
    """Return the set of feature keys for a given plan."""
    plan_key = plan_key.upper() if plan_key else 'BASIC'
    defn = PLAN_DEFINITIONS.get(plan_key, PLAN_DEFINITIONS['BASIC'])
    return defn['features']


def get_employee_limit(plan_key):
    """Return the employee limit for a given plan."""
    plan_key = plan_key.upper() if plan_key else 'BASIC'
    defn = PLAN_DEFINITIONS.get(plan_key, PLAN_DEFINITIONS['BASIC'])
    return defn['employee_limit']


def company_has_feature(company, feature_key):
    """Check if a company's plan includes a specific feature."""
    plan_key = get_company_plan(company)
    return feature_key in get_plan_features(plan_key)


def company_can_add_employee(company):
    """Check if a company can add more employees under their plan limit."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    plan_key = get_company_plan(company)
    limit = get_employee_limit(plan_key)
    current_count = User.objects.filter(company=company, is_active=True).count()
    return current_count < limit, limit, current_count


def get_minimum_plan_for_feature(feature_key):
    """Return the lowest plan that includes a given feature."""
    for plan_key in PLAN_HIERARCHY:
        if feature_key in PLAN_DEFINITIONS[plan_key]['features']:
            return plan_key
    return 'ENTERPRISE'


def get_plan_context(company):
    """Build a template context dict with plan info and feature flags."""
    plan_key = get_company_plan(company)
    features = get_plan_features(plan_key)
    plan_def = PLAN_DEFINITIONS.get(plan_key, PLAN_DEFINITIONS['BASIC'])

    return {
        'plan_key': plan_key,
        'plan_name': plan_def['name'],
        'plan_employee_limit': plan_def['employee_limit'],
        'plan_features': features,
        # Convenience booleans for templates
        'has_attendance_basic': FEAT_ATTENDANCE_BASIC in features,
        'has_leave_management': FEAT_LEAVE_MANAGEMENT in features,
        'has_payroll_basic': FEAT_PAYROLL_BASIC in features,
        'has_email_support': FEAT_EMAIL_SUPPORT in features,
        'has_responsive_web': FEAT_RESPONSIVE_WEB in features,
        'has_attendance_gps': FEAT_ATTENDANCE_GPS in features,
        'has_leave_approvals': FEAT_LEAVE_APPROVALS in features,
        'has_payroll_automated': FEAT_PAYROLL_AUTOMATED in features,
        'has_performance_reviews': FEAT_PERFORMANCE_REVIEWS in features,
        'has_document_management': FEAT_DOCUMENT_MANAGEMENT in features,
        'has_custom_reports': FEAT_CUSTOM_REPORTS in features,
        'has_priority_support': FEAT_PRIORITY_SUPPORT in features,
        'has_advanced_analytics': FEAT_ADVANCED_ANALYTICS in features,
        'has_custom_integrations': FEAT_CUSTOM_INTEGRATIONS in features,
        'has_api_access': FEAT_API_ACCESS in features,
        'has_phone_support': FEAT_PHONE_SUPPORT in features,
        'has_custom_training': FEAT_CUSTOM_TRAINING in features,
        'has_white_label': FEAT_WHITE_LABEL in features,
        'has_custom_sla': FEAT_CUSTOM_SLA in features,
        'has_on_premise': FEAT_ON_PREMISE in features,
        'has_support_247': FEAT_SUPPORT_247 in features,
        'has_custom_dev': FEAT_CUSTOM_DEV in features,
        'has_data_migration': FEAT_DATA_MIGRATION in features,
        # Plan tier checks
        'is_standard_or_above': plan_key in PLAN_HIERARCHY[1:],
        'is_professional_or_above': plan_key in PLAN_HIERARCHY[2:],
        'is_enterprise': plan_key == 'ENTERPRISE',
    }


# ── View decorator ─────────────────────────────────────────────────────

def require_feature(feature_key, redirect_url='blu_billing_home'):
    """
    Decorator that blocks access if the user's company plan lacks a feature.
    Shows an upgrade message and redirects to the billing page.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                company = getattr(getattr(user, 'employer_profile', None), 'company', None)
            if not company:
                company = getattr(getattr(user, 'employee_profile', None), 'company', None)

            if company and not company_has_feature(company, feature_key):
                min_plan = get_minimum_plan_for_feature(feature_key)
                plan_name = PLAN_DEFINITIONS.get(min_plan, {}).get('name', min_plan)
                messages.warning(
                    request,
                    f'This feature requires the {plan_name} plan or higher. '
                    f'Please upgrade your subscription to access it.'
                )
                return redirect(redirect_url)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def require_employee_limit(redirect_url='blu_billing_home'):
    """
    Decorator that blocks adding employees if the plan limit is reached.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                company = getattr(getattr(user, 'employer_profile', None), 'company', None)

            if company:
                can_add, limit, current = company_can_add_employee(company)
                if not can_add:
                    plan_key = get_company_plan(company)
                    plan_name = PLAN_DEFINITIONS.get(plan_key, {}).get('name', plan_key)
                    messages.warning(
                        request,
                        f'Your {plan_name} plan allows up to {limit} employees. '
                        f'You currently have {current}. Please upgrade to add more.'
                    )
                    return redirect(redirect_url)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
