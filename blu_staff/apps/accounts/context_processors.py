"""
Context processors for subscription plan features
"""
from .permissions import get_company_plan, has_feature_access, get_plan_features


def subscription_context(request):
    """
    Add subscription plan information to all template contexts
    """
    if not request.user.is_authenticated:
        return {
            'user_subscription_plan': 'BASIC',
            'user_plan_features': [],
            'is_superadmin': False,
        }
    
    # Check if superadmin
    is_superadmin = hasattr(request.user, 'role') and request.user.role == 'SUPERADMIN'
    
    # Get user's plan
    plan = get_company_plan(request.user)
    features = get_plan_features(plan)
    
    return {
        'user_subscription_plan': plan,
        'user_plan_features': features,
        'is_superadmin': is_superadmin,
        'has_feature': lambda feature: is_superadmin or has_feature_access(request.user, feature),
    }
