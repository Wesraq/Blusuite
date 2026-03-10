"""
BLU Core views — Audit Log browser for Administrators + custom error handlers.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .audit import AuditLog
from .rbac import require_role, ADMIN_ROLES


def handle_403(request, exception=None):
    """Custom 403 handler — renders the styled access-denied page."""
    return render(request, 'ems/403.html', status=403)


@require_role(ADMIN_ROLES)
def audit_log_view(request):
    """Display audit trail. Administrators see their company. SuperAdmins see all."""
    qs = AuditLog.objects.select_related('user', 'company').order_by('-timestamp')

    if request.user.role != 'SUPERADMIN':
        qs = qs.filter(company=request.user.company)

    # Filters
    action_filter = request.GET.get('action', '')
    model_filter = request.GET.get('model', '')
    search = request.GET.get('q', '').strip()

    if action_filter:
        qs = qs.filter(action=action_filter)
    if model_filter:
        qs = qs.filter(model_name__icontains=model_filter)
    if search:
        qs = qs.filter(user_email__icontains=search) | qs.filter(object_repr__icontains=search)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    action_choices = AuditLog.Action.choices
    base_template = (
        'ems/base_employer.html'
        if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        else 'ems/base_superadmin.html'
    )

    return render(request, 'ems/audit_log.html', {
        'page_obj': page_obj,
        'action_choices': action_choices,
        'action_filter': action_filter,
        'model_filter': model_filter,
        'search': search,
        'base_template': base_template,
        'total_count': qs.count(),
    })
