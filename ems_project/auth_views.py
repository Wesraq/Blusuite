from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.conf import settings


def finalize_login_session(request, user):
    """Establish a clean session for the authenticated user and persist context data."""

    # Reset any prior session data before logging the user in
    request.session.flush()

    # Login and bind user to the new session
    auth_login(request, user)

    # Provide API token access when DRF authtoken is installed
    try:
        from rest_framework.authtoken.models import Token  # type: ignore
    except ImportError:
        token_key = None
    else:
        token, _ = Token.objects.get_or_create(user=user)
        token_key = token.key
        request.session['auth_token'] = token.key

    # Store lightweight user context for UI usage
    request.session['user_role'] = getattr(user, 'role', None)
    request.session['user_id'] = user.id
    request.session['user_email'] = user.email
    request.session['last_login'] = str(user.last_login)

    # Expire session when browser closes
    request.session.set_expiry(0)

    # Maintain tenant binding only when an active company and tenant exist
    tenant_session_key = getattr(settings, 'TENANT_SESSION_KEY', None)
    company = getattr(user, 'company', None)
    tenant = None
    if company and getattr(company, 'is_active', True):
        tenant = getattr(company, 'tenant', None)

    if tenant_session_key and tenant:
        request.session[tenant_session_key] = tenant.pk
    elif tenant_session_key:
        request.session.pop(tenant_session_key, None)

    return token_key


def ems_admin_login(request):
    """EMS SuperAdmin login - clean interface"""
    if request.method == 'GET':
        if request.user.is_authenticated and request.user.role == 'SUPERADMIN':
            return redirect('/dashboard/')
        
        # Clear any existing messages before showing login page
        storage = messages.get_messages(request)
        storage.used = True
        
        return render(request, 'ems/login.html')

    elif request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')

        if not email or not password:
            messages.error(request, 'Please enter both email and password')
            return redirect('/login/')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if user.is_active and user.role == 'SUPERADMIN':  # Only allow SuperAdmins
                # Clear any existing session data before login
                request.session.flush()

                # Re-fetch user from database to ensure we have latest data
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user.id)

                # Login with fresh user data
                auth_login(request, user)

                # Store user info in session for easy access
                request.session['user_role'] = user.role
                request.session['user_id'] = user.id
                request.session['user_email'] = user.email
                request.session['last_login'] = str(user.last_login)

                # Set session to expire when browser closes for security
                request.session.set_expiry(0)

                tenant = getattr(getattr(user, 'company', None), 'tenant', None)
                if tenant:
                    request.session[settings.TENANT_SESSION_KEY] = tenant.pk
                else:
                    request.session.pop(settings.TENANT_SESSION_KEY, None)

                return redirect('/dashboard/')
            else:
                messages.error(request, 'Access denied. SuperAdmin privileges required.')
        else:
            messages.error(request, 'Invalid login credentials')

        return redirect('/login/')


def django_admin_login(request):
    """Django admin login - for staff users only"""
    if request.method == 'GET':
        if request.user.is_authenticated and request.user.is_staff and request.user.role != 'SUPERADMIN':
            return redirect('/admin/')
        return render(request, 'admin/login.html')

    # Let Django handle the actual authentication for staff users
    return LoginView.as_view(template_name='admin/login.html')(request)


def ems_logout(request):
    """Logout from EMS admin - properly clear all session data"""
    # Call Django's logout to clear authentication first
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    
    # Clear Django session data
    request.session.flush()  # This clears all session data, not just auth

    # Clear any user-specific session keys
    keys_to_clear = [
        'user_role', 'user_id', 'user_email', 'company_id',
        'dashboard_data', 'user_permissions', 'last_login', 'is_superadmin'
    ]

    for key in keys_to_clear:
        if key in request.session:
            del request.session[key]

    # Clear all messages to prevent them from showing on login page
    storage = messages.get_messages(request)
    storage.used = True

    return redirect('/login/')


def login_redirect(request):
    """Redirect users based on their model type and role"""
    if not request.user.is_authenticated:
        return redirect('/login/')

    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return redirect('/dashboard/')

    # Check if user is regular User (from User model)
    if hasattr(request.user, 'role'):
        if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
            return redirect('/employer/')
        elif request.user.role == 'EMPLOYEE':
            return redirect('/employee/')

    return redirect('/')


from django.views.decorators.csrf import csrf_protect

@csrf_protect
def general_user_login(request):
    """General login for employees and other users"""
    if request.method == 'GET':
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        # Clear any existing messages before showing login page
        storage = messages.get_messages(request)
        storage.used = True
        
        return render(request, 'ems/login.html')

    elif request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')

        if not email or not password:
            messages.error(request, 'Please enter both email and password')
            return redirect('/login/')

        user = authenticate(request, username=email, password=password)

        if not user or not user.is_active:
            messages.error(request, 'Invalid login credentials or account is disabled.')
            return redirect('/login/')

        finalize_login_session(request, user)

        # Redirect based on role (includes platform roles via dashboard_redirect)
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
            return redirect('/employer/')
        if user.role == 'EMPLOYEE':
            return redirect('/employee/')
        # SUPERADMIN and platform_role users go to dashboard_redirect to reach their portal
        return redirect('/dashboard/')
