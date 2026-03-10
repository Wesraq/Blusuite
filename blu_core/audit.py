"""
BLU Suite Audit Logging
=======================
Centralized audit trail for all critical business actions.
Logs: logins, salary edits, employee creation/deletion,
      asset assignments, document uploads, payroll changes,
      role changes, company settings changes.
"""

import json
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class AuditLog(models.Model):
    """Immutable audit trail record for every significant action."""

    class Action(models.TextChoices):
        # Auth
        LOGIN           = 'LOGIN',           'User Login'
        LOGOUT          = 'LOGOUT',          'User Logout'
        LOGIN_FAILED    = 'LOGIN_FAILED',    'Failed Login Attempt'
        PASSWORD_CHANGE = 'PASSWORD_CHANGE', 'Password Changed'
        # Employee lifecycle
        EMPLOYEE_CREATE = 'EMPLOYEE_CREATE', 'Employee Created'
        EMPLOYEE_UPDATE = 'EMPLOYEE_UPDATE', 'Employee Updated'
        EMPLOYEE_DELETE = 'EMPLOYEE_DELETE', 'Employee Deleted'
        ROLE_CHANGE     = 'ROLE_CHANGE',     'Role Changed'
        # Payroll / Salary
        SALARY_CREATE   = 'SALARY_CREATE',   'Salary Structure Created'
        SALARY_UPDATE   = 'SALARY_UPDATE',   'Salary Updated'
        PAYROLL_APPROVE = 'PAYROLL_APPROVE', 'Payroll Approved'
        PAYROLL_RUN     = 'PAYROLL_RUN',     'Payroll Run'
        # Assets
        ASSET_CREATE    = 'ASSET_CREATE',    'Asset Created'
        ASSET_ASSIGN    = 'ASSET_ASSIGN',    'Asset Assigned'
        ASSET_RETURN    = 'ASSET_RETURN',    'Asset Returned'
        ASSET_UPDATE    = 'ASSET_UPDATE',    'Asset Updated'
        ASSET_DELETE    = 'ASSET_DELETE',    'Asset Deleted'
        # Documents
        DOC_UPLOAD      = 'DOC_UPLOAD',      'Document Uploaded'
        DOC_DELETE      = 'DOC_DELETE',      'Document Deleted'
        DOC_APPROVE     = 'DOC_APPROVE',     'Document Approved'
        # Company
        COMPANY_UPDATE  = 'COMPANY_UPDATE',  'Company Settings Updated'
        # Generic
        CREATE          = 'CREATE',          'Record Created'
        UPDATE          = 'UPDATE',          'Record Updated'
        DELETE          = 'DELETE',          'Record Deleted'
        EXPORT          = 'EXPORT',          'Data Exported'
        VIEW_SENSITIVE  = 'VIEW_SENSITIVE',  'Sensitive Data Viewed'

    # Who did it
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
    )
    user_email = models.EmailField(blank=True, help_text="Snapshot of email at time of action")

    # What they did
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)

    # What object was affected
    model_name = models.CharField(max_length=100, blank=True, db_index=True)
    object_id = models.CharField(max_length=100, blank=True, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True, help_text="Human-readable name of the object")

    # What changed (JSON diff: {"field": {"old": ..., "new": ...}})
    changes = models.JSONField(null=True, blank=True)

    # Context
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    extra = models.JSONField(null=True, blank=True, help_text="Any extra contextual data")

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['company', 'timestamp']),
            models.Index(fields=['user', 'action']),
            models.Index(fields=['model_name', 'object_id']),
        ]

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user_email} — {self.action} {self.model_name} #{self.object_id}"

    def save(self, *args, **kwargs):
        # Snapshot user email so logs remain readable even if user is deleted
        if self.user and not self.user_email:
            self.user_email = self.user.email
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions used throughout the codebase
# ─────────────────────────────────────────────────────────────────────────────

def _get_ip(request):
    """Extract real client IP from request."""
    if not request:
        return None
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_user_agent(request):
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


def _get_company(user):
    """Return company from user, safely."""
    if not user or not user.pk:
        return None
    return getattr(user, 'company', None)


def log_action(
    action,
    *,
    user=None,
    request=None,
    obj=None,
    model_name='',
    object_id='',
    object_repr='',
    changes=None,
    company=None,
    extra=None,
):
    """
    Primary API for recording an audit event.

    Usage examples
    --------------
    # In a view after saving salary:
    log_action(AuditLog.Action.SALARY_UPDATE, user=request.user, request=request,
               obj=salary, changes={'base_salary': {'old': '5000', 'new': '6000'}})

    # On employee delete:
    log_action(AuditLog.Action.EMPLOYEE_DELETE, user=request.user, request=request,
               obj=employee, object_repr=str(employee))
    """
    if request and not user:
        user = getattr(request, 'user', None)
        if user and not user.is_authenticated:
            user = None

    if obj and not model_name:
        model_name = type(obj).__name__
    if obj and not object_id:
        object_id = str(getattr(obj, 'pk', '') or '')
    if obj and not object_repr:
        object_repr = str(obj)[:255]
    if user and not company:
        company = _get_company(user)

    try:
        AuditLog.objects.create(
            user=user,
            user_email=(user.email if user else ''),
            action=action,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes,
            company=company,
            ip_address=_get_ip(request),
            user_agent=_get_user_agent(request),
            extra=extra,
        )
    except Exception:
        # Audit logging must NEVER crash the main request
        import logging
        logging.getLogger('blu_audit').exception("Failed to write audit log entry")


def diff_changes(old_instance, new_instance, fields):
    """
    Build a changes dict comparing old vs new values for listed fields.

    Usage::
        changes = diff_changes(old_salary, new_salary, ['base_salary', 'currency'])
    """
    result = {}
    for field in fields:
        old_val = getattr(old_instance, field, None)
        new_val = getattr(new_instance, field, None)
        if str(old_val) != str(new_val):
            result[field] = {'old': str(old_val), 'new': str(new_val)}
    return result or None
