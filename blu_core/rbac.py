"""
BLU Suite — Centralized Role-Based Access Control
==================================================
Single source of truth for all permission rules.

Usage in views
--------------
    from blu_core.rbac import require_role, ADMIN_ROLES

    @require_role(ADMIN_ROLES)
    def company_settings(request):
        ...

    @require_role('ADMINISTRATOR')
    def delete_employee(request, pk):
        ...

Usage in class-based views
--------------------------
    from blu_core.rbac import RoleRequiredMixin

    class PayrollView(RoleRequiredMixin):
        allowed_roles = PAYROLL_ROLES
        ...
"""

from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

# ─────────────────────────────────────────────────────────────────────────────
# Role constants — one place, no magic strings scattered across 178 views
# ─────────────────────────────────────────────────────────────────────────────

SUPERADMIN = 'SUPERADMIN'
ADMINISTRATOR = 'ADMINISTRATOR'
EMPLOYER_ADMIN = 'EMPLOYER_ADMIN'
EMPLOYEE = 'EMPLOYEE'

# Grouped sets used as shorthand
SUPERADMIN_ONLY   = [SUPERADMIN]
ADMIN_ROLES       = [SUPERADMIN, ADMINISTRATOR]
MANAGEMENT_ROLES  = [SUPERADMIN, ADMINISTRATOR, EMPLOYER_ADMIN]
ALL_ROLES         = [SUPERADMIN, ADMINISTRATOR, EMPLOYER_ADMIN, EMPLOYEE]

# Domain-specific shorthands
PAYROLL_ROLES     = ADMIN_ROLES          # Only admins touch payroll
HR_ROLES          = MANAGEMENT_ROLES    # HR managers (EMPLOYER_ADMIN) can do HR tasks
ASSET_ROLES       = MANAGEMENT_ROLES    # Asset management
SETTINGS_ROLES    = ADMIN_ROLES         # Company settings


# ─────────────────────────────────────────────────────────────────────────────
# Permission check helper
# ─────────────────────────────────────────────────────────────────────────────

def has_role(user, roles):
    """
    Return True if the authenticated user has one of the given roles.
    Accepts a single role string or a list.
    """
    if not user or not user.is_authenticated:
        return False
    if isinstance(roles, str):
        roles = [roles]
    return getattr(user, 'role', None) in roles


def user_can(user, permission):
    """
    Named-permission check.  Maps permission keys to role sets.
    Avoids having roles leak into templates and non-view code.

    Example::
        if user_can(request.user, 'edit_salary'):
            ...
    """
    permission_map = {
        'view_payroll':         PAYROLL_ROLES,
        'edit_salary':          PAYROLL_ROLES,
        'approve_payroll':      ADMIN_ROLES,
        'manage_employees':     MANAGEMENT_ROLES,
        'delete_employee':      ADMIN_ROLES,
        'change_employee_role': ADMIN_ROLES,
        'manage_assets':        ASSET_ROLES,
        'assign_asset':         MANAGEMENT_ROLES,
        'view_company_settings':ADMIN_ROLES,
        'edit_company_settings':ADMIN_ROLES,
        'manage_documents':     MANAGEMENT_ROLES,
        'approve_documents':    MANAGEMENT_ROLES,
        'view_analytics':       MANAGEMENT_ROLES,
        'manage_announcements': MANAGEMENT_ROLES,
        'manage_projects':      MANAGEMENT_ROLES,
        'approve_requests':     MANAGEMENT_ROLES,
        'manage_training':      MANAGEMENT_ROLES,
        'view_audit_logs':      ADMIN_ROLES,
        'superadmin_panel':     SUPERADMIN_ONLY,
    }
    allowed = permission_map.get(permission, SUPERADMIN_ONLY)
    return has_role(user, allowed)


# ─────────────────────────────────────────────────────────────────────────────
# Decorator for function-based views
# ─────────────────────────────────────────────────────────────────────────────

def require_role(roles, redirect_url=None):
    """
    Decorator that enforces role-based access on a view.
    Unauthenticated users are redirected to login.
    Authenticated but unauthorized users get a 403.

    @require_role(ADMIN_ROLES)
    def my_view(request): ...

    @require_role('ADMINISTRATOR')
    def admin_only(request): ...
    """
    if isinstance(roles, str):
        roles = [roles]

    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url='/login/')
        def _wrapped(request, *args, **kwargs):
            if not has_role(request.user, roles):
                return _forbidden_response(request)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def _forbidden_response(request):
    """Return a styled 403 or redirect depending on context."""
    from django.shortcuts import render
    try:
        return render(request, 'ems/403.html', status=403)
    except Exception:
        return HttpResponseForbidden(
            "<h1>403 — Access Denied</h1>"
            "<p>You do not have permission to access this page.</p>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Mixin for class-based views
# ─────────────────────────────────────────────────────────────────────────────

class RoleRequiredMixin:
    """
    CBV mixin enforcing role-based access.

    class PayrollView(RoleRequiredMixin, TemplateView):
        allowed_roles = PAYROLL_ROLES
        template_name = 'payroll/list.html'
    """
    allowed_roles = ALL_ROLES

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        if not has_role(request.user, self.allowed_roles):
            return _forbidden_response(request)
        return super().dispatch(request, *args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Company ownership guard — prevents cross-tenant object access
# ─────────────────────────────────────────────────────────────────────────────

def assert_same_company(user, obj, company_attr='company'):
    """
    Raise PermissionError if obj doesn't belong to the user's company.
    Use this inside views that accept a PK from the URL.

    Usage::
        def edit_employee(request, pk):
            employee = get_object_or_404(User, pk=pk)
            assert_same_company(request.user, employee)
            ...
    """
    user_company = getattr(user, 'company', None)
    if not user_company:
        raise PermissionError("User has no company assigned.")
    obj_company = getattr(obj, company_attr, None)
    if not obj_company:
        # Try nested: obj.employee.company, obj.user.company …
        for attr in ('employee', 'user', 'owner'):
            nested = getattr(obj, attr, None)
            if nested:
                obj_company = getattr(nested, 'company', None)
                if obj_company:
                    break
    if obj_company != user_company:
        raise PermissionError(
            f"Cross-company access attempt: user from {user_company} tried to access "
            f"object belonging to {obj_company}."
        )
