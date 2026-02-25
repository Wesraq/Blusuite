"""
Middleware for subscription plan feature access control
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve
from .permissions import has_feature_access, FEATURE_URL_MAPPING, get_company_plan


class SubscriptionFeatureMiddleware:
    """
    Middleware to check if user has access to requested features based on their subscription plan
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip for unauthenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Skip for superadmins
        if hasattr(request.user, 'role') and request.user.role == 'SUPERADMIN':
            return self.get_response(request)
        
        # Skip for public pages and auth pages
        public_paths = [
            '/login/', '/logout/', '/register/', '/accounts/login/',
            '/static/', '/media/', '/admin/', '/api/docs/',
            '/', '/about/', '/features/', '/solutions/', '/pricing/',
            '/help/', '/contact/', '/status/', '/docs/',
            '/careers/', '/blog/', '/press/',
            '/blusuite/',  # BluSuite Hub accessible to all plans
        ]
        
        if any(request.path.startswith(path) for path in public_paths):
            return self.get_response(request)
        
        # Check if the requested URL requires a specific feature
        for feature, url_patterns in FEATURE_URL_MAPPING.items():
            for pattern in url_patterns:
                if request.path.startswith(pattern):
                    if not has_feature_access(request.user, feature):
                        plan = get_company_plan(request.user)
                        messages.warning(
                            request,
                            f'⚠️ This feature is not available in your {plan} plan. '
                            f'Upgrade to Professional or Enterprise to access this feature.'
                        )
                        return redirect('employer_admin_dashboard')
        
        response = self.get_response(request)
        return response
