"""
Template tags for subscription plan feature access control
"""
from django import template
from blu_staff.apps.accounts.permissions import has_feature_access, get_company_plan, get_plan_features, PLAN_FEATURES

register = template.Library()


@register.simple_tag(takes_context=True)
def has_feature(context, feature_name):
    """
    Check if the current user has access to a feature
    Usage: {% has_feature 'performance_reviews' as has_access %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    
    # Superadmins have access to everything
    if hasattr(request.user, 'role') and request.user.role == 'SUPERADMIN':
        return True
    
    return has_feature_access(request.user, feature_name)


@register.simple_tag(takes_context=True)
def user_plan(context):
    """
    Get the current user's subscription plan
    Usage: {% user_plan as plan %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return 'BASIC'
    
    return get_company_plan(request.user)


@register.simple_tag
def plan_features(plan_name):
    """
    Get all features for a specific plan
    Usage: {% plan_features 'PROFESSIONAL' as features %}
    """
    return get_plan_features(plan_name)


@register.simple_tag(takes_context=True)
def user_plan_features(context):
    """
    Get all features for the current user's plan
    Usage: {% user_plan_features as features %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return get_plan_features('BASIC')
    
    plan = get_company_plan(request.user)
    return get_plan_features(plan)


@register.filter
def plan_display_name(plan):
    """
    Convert plan code to display name
    Usage: {{ plan|plan_display_name }}
    """
    display_names = {
        'BASIC': 'Basic',
        'STANDARD': 'Standard',
        'PROFESSIONAL': 'Professional',
    }
    return display_names.get(plan, plan)


@register.simple_tag(takes_context=True)
def employee_limit_info(context):
    """
    Get employee limit information for the current user's company
    Usage: {% employee_limit_info as limit_info %}
    Returns: dict with 'current', 'max', 'percentage', 'can_add'
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return {'current': 0, 'max': 0, 'percentage': 0, 'can_add': False}
    
    # Get company
    company = None
    if hasattr(request.user, 'company') and request.user.company:
        company = request.user.company
    elif hasattr(request.user, 'employer_profile') and request.user.employer_profile:
        company = request.user.employer_profile.company
    elif hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        company = request.user.employee_profile.company
    
    if not company:
        return {'current': 0, 'max': 0, 'percentage': 0, 'can_add': False}
    
    plan_config = PLAN_FEATURES.get(company.subscription_plan, PLAN_FEATURES['BASIC'])
    max_employees = plan_config['max_employees']
    
    # Count active employees
    from blu_staff.apps.accounts.models import EmployeeProfile
    current_count = EmployeeProfile.objects.filter(
        company=company,
        user__is_active=True
    ).count()
    
    percentage = (current_count / max_employees * 100) if max_employees > 0 else 0
    can_add = current_count < max_employees
    
    return {
        'current': current_count,
        'max': max_employees,
        'percentage': round(percentage, 1),
        'can_add': can_add,
        'plan': company.subscription_plan
    }


@register.inclusion_tag('accounts/upgrade_prompt.html', takes_context=True)
def upgrade_prompt(context, feature_name, feature_display_name=None):
    """
    Show an upgrade prompt for a restricted feature
    Usage: {% upgrade_prompt 'performance_reviews' 'Performance Reviews' %}
    """
    request = context.get('request')
    has_access = False
    user_plan_name = 'BASIC'
    
    if request and request.user.is_authenticated:
        has_access = has_feature_access(request.user, feature_name)
        user_plan_name = get_company_plan(request.user)
    
    # Find which plan includes this feature
    required_plan = None
    for plan, config in PLAN_FEATURES.items():
        if feature_name in config['features']:
            if plan in ['PROFESSIONAL', 'STANDARD']:
                required_plan = 'Professional'
                break
            elif plan in ['ENTERPRISE', 'PREMIUM']:
                required_plan = 'Enterprise'
                break
    
    return {
        'has_access': has_access,
        'feature_name': feature_display_name or feature_name.replace('_', ' ').title(),
        'current_plan': user_plan_name,
        'required_plan': required_plan or 'Professional',
    }
