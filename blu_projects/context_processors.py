"""
BLU Projects - Context Processors
Provides PMS-specific context variables to all templates.
"""


def pms_context(request):
    """Add PMS admin flag to all templates that use base_projects.html."""
    user = request.user
    if not user.is_authenticated:
        return {}

    role = (getattr(user, 'role', '') or '').upper()
    is_admin = role in ('ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN')
    if not is_admin and hasattr(user, 'employee_profile'):
        emp_role = (user.employee_profile.employee_role or '').upper()
        if emp_role in ('HR', 'SUPERVISOR'):
            is_admin = True

    return {
        'is_admin': is_admin,
    }
