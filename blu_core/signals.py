"""
BLU Suite Audit Signals
=======================
Django signal receivers that record critical business events into AuditLog.

Covers:
  - User login / logout / failed login
  - Employee create / update / delete / role change
  - Salary structure create / update
  - Payroll approval
  - Asset create / assign / return / delete
  - Document upload / delete / approve
  - Company settings update
"""

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .audit import AuditLog, log_action, _get_ip, _get_user_agent, _get_company

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Authentication Events
# ─────────────────────────────────────────────────────────────────────────────

@receiver(user_logged_in, dispatch_uid='blu_audit_login')
def on_login(sender, request, user, **kwargs):
    log_action(
        AuditLog.Action.LOGIN,
        user=user,
        request=request,
        model_name='User',
        object_id=str(user.pk),
        object_repr=user.email,
        extra={'role': user.role},
    )


@receiver(user_logged_out, dispatch_uid='blu_audit_logout')
def on_logout(sender, request, user, **kwargs):
    if user:
        log_action(
            AuditLog.Action.LOGOUT,
            user=user,
            request=request,
            model_name='User',
            object_id=str(user.pk),
            object_repr=user.email,
        )


@receiver(user_login_failed, dispatch_uid='blu_audit_login_failed')
def on_login_failed(sender, credentials, request, **kwargs):
    AuditLog.objects.create(
        user=None,
        user_email=credentials.get('username', credentials.get('email', '')),
        action=AuditLog.Action.LOGIN_FAILED,
        model_name='User',
        ip_address=_get_ip(request),
        user_agent=_get_user_agent(request),
        extra={'attempted_email': credentials.get('username', credentials.get('email', ''))},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Employee / User Events
# ─────────────────────────────────────────────────────────────────────────────

# Cache old user role before save to detect role changes
_old_user_roles = {}


@receiver(pre_save, sender=User, dispatch_uid='blu_audit_user_pre_save')
def capture_old_user_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = User.objects.get(pk=instance.pk)
            _old_user_roles[instance.pk] = {
                'role': old.role,
                'is_active': old.is_active,
                'email': old.email,
            }
        except User.DoesNotExist:
            pass


@receiver(post_save, sender=User, dispatch_uid='blu_audit_user_post_save')
def on_user_save(sender, instance, created, **kwargs):
    if created:
        log_action(
            AuditLog.Action.EMPLOYEE_CREATE,
            model_name='User',
            object_id=str(instance.pk),
            object_repr=instance.email,
            company=_get_company(instance),
            extra={'role': instance.role},
        )
    else:
        old = _old_user_roles.pop(instance.pk, {})
        if not old:
            return  # No prior state captured — skip
        changes = {}
        if old.get('role') and old['role'] != instance.role:
            changes['role'] = {'old': old['role'], 'new': instance.role}
        if old.get('is_active') is not None and old['is_active'] != instance.is_active:
            changes['is_active'] = {'old': str(old['is_active']), 'new': str(instance.is_active)}
        if not changes:
            return  # Nothing meaningful changed — skip

        action = AuditLog.Action.ROLE_CHANGE if 'role' in changes else AuditLog.Action.EMPLOYEE_UPDATE
        log_action(
            action,
            model_name='User',
            object_id=str(instance.pk),
            object_repr=instance.email,
            company=_get_company(instance),
            changes=changes,
        )


@receiver(post_delete, sender=User, dispatch_uid='blu_audit_user_post_delete')
def on_user_delete(sender, instance, **kwargs):
    log_action(
        AuditLog.Action.EMPLOYEE_DELETE,
        model_name='User',
        object_id=str(instance.pk),
        object_repr=instance.email,
        company=_get_company(instance),
        extra={'role': instance.role},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Salary / Payroll Events
# ─────────────────────────────────────────────────────────────────────────────

def _register_salary_signals():
    try:
        from blu_staff.apps.payroll.models import SalaryStructure, Payroll
        _old_salaries = {}

        @receiver(pre_save, sender=SalaryStructure, weak=False)
        def capture_old_salary(sender, instance, **kwargs):
            if instance.pk:
                try:
                    old = SalaryStructure.objects.get(pk=instance.pk)
                    _old_salaries[instance.pk] = {
                        'base_salary': str(old.base_salary),
                        'currency': old.currency,
                        'payment_frequency': old.payment_frequency,
                    }
                except SalaryStructure.DoesNotExist:
                    pass

        @receiver(post_save, sender=SalaryStructure, weak=False)
        def on_salary_save(sender, instance, created, **kwargs):
            action = AuditLog.Action.SALARY_CREATE if created else AuditLog.Action.SALARY_UPDATE
            old = _old_salaries.pop(instance.pk, {})
            changes = None
            if not created and old:
                changes = {}
                for field in ('base_salary', 'currency', 'payment_frequency'):
                    new_val = str(getattr(instance, field, ''))
                    if old.get(field) != new_val:
                        changes[field] = {'old': old[field], 'new': new_val}
                changes = changes or None

            log_action(
                action,
                model_name='SalaryStructure',
                object_id=str(instance.pk),
                object_repr=str(instance),
                company=_get_company(instance.employee) if instance.employee_id else None,
                changes=changes,
                extra={
                    'employee_id': instance.employee_id,
                    'base_salary': str(instance.base_salary),
                    'currency': instance.currency,
                },
            )

        @receiver(post_save, sender=Payroll, weak=False)
        def on_payroll_save(sender, instance, created, **kwargs):
            if instance.status == 'APPROVED':
                log_action(
                    AuditLog.Action.PAYROLL_APPROVE,
                    model_name='Payroll',
                    object_id=str(instance.pk),
                    object_repr=str(instance),
                    company=_get_company(instance.employee) if instance.employee_id else None,
                    extra={
                        'employee_id': instance.employee_id,
                        'net_pay': str(getattr(instance, 'net_pay', '')),
                        'period_start': str(instance.period_start),
                        'period_end': str(instance.period_end),
                    },
                )

    except ImportError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Asset Events
# ─────────────────────────────────────────────────────────────────────────────

def _register_asset_signals():
    try:
        from blu_assets.models import EmployeeAsset
        _old_asset_employees = {}

        @receiver(pre_save, sender=EmployeeAsset, weak=False)
        def capture_old_asset(sender, instance, **kwargs):
            if instance.pk:
                try:
                    old = EmployeeAsset.objects.get(pk=instance.pk)
                    _old_asset_employees[instance.pk] = {
                        'employee_id': old.employee_id,
                        'status': old.status,
                    }
                except EmployeeAsset.DoesNotExist:
                    pass

        @receiver(post_save, sender=EmployeeAsset, weak=False)
        def on_asset_save(sender, instance, created, **kwargs):
            if created:
                log_action(
                    AuditLog.Action.ASSET_CREATE,
                    model_name='EmployeeAsset',
                    object_id=str(instance.pk),
                    object_repr=f"{instance.asset_tag} — {instance.name}",
                    company=_get_company(instance.employee) if instance.employee_id else None,
                    extra={'asset_type': instance.asset_type, 'status': instance.status},
                )
            else:
                old = _old_asset_employees.pop(instance.pk, {})
                # Detect assignment change
                if old.get('employee_id') != instance.employee_id and instance.employee_id:
                    log_action(
                        AuditLog.Action.ASSET_ASSIGN,
                        model_name='EmployeeAsset',
                        object_id=str(instance.pk),
                        object_repr=f"{instance.asset_tag} — {instance.name}",
                        company=_get_company(instance.employee) if instance.employee_id else None,
                        changes={
                            'employee': {
                                'old': str(old.get('employee_id', 'Unassigned')),
                                'new': str(instance.employee_id),
                            }
                        },
                    )
                elif old.get('employee_id') and not instance.employee_id:
                    log_action(
                        AuditLog.Action.ASSET_RETURN,
                        model_name='EmployeeAsset',
                        object_id=str(instance.pk),
                        object_repr=f"{instance.asset_tag} — {instance.name}",
                        changes={'employee': {'old': str(old['employee_id']), 'new': 'Unassigned'}},
                    )
                else:
                    log_action(
                        AuditLog.Action.ASSET_UPDATE,
                        model_name='EmployeeAsset',
                        object_id=str(instance.pk),
                        object_repr=f"{instance.asset_tag} — {instance.name}",
                    )

        @receiver(post_delete, sender=EmployeeAsset, weak=False)
        def on_asset_delete(sender, instance, **kwargs):
            log_action(
                AuditLog.Action.ASSET_DELETE,
                model_name='EmployeeAsset',
                object_id=str(instance.pk),
                object_repr=f"{instance.asset_tag} — {instance.name}",
                extra={'asset_type': instance.asset_type},
            )

    except ImportError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Document Events
# ─────────────────────────────────────────────────────────────────────────────

def _register_document_signals():
    try:
        from blu_staff.apps.documents.models import EmployeeDocument

        @receiver(post_save, sender=EmployeeDocument, weak=False)
        def on_document_save(sender, instance, created, **kwargs):
            if created:
                log_action(
                    AuditLog.Action.DOC_UPLOAD,
                    model_name='EmployeeDocument',
                    object_id=str(instance.pk),
                    object_repr=str(instance),
                    extra={
                        'is_confidential': getattr(instance, 'is_confidential', False),
                    },
                )
            elif getattr(instance, 'status', None) == 'APPROVED':
                log_action(
                    AuditLog.Action.DOC_APPROVE,
                    model_name='EmployeeDocument',
                    object_id=str(instance.pk),
                    object_repr=str(instance),
                )

        @receiver(post_delete, sender=EmployeeDocument, weak=False)
        def on_document_delete(sender, instance, **kwargs):
            log_action(
                AuditLog.Action.DOC_DELETE,
                model_name='EmployeeDocument',
                object_id=str(instance.pk),
                object_repr=str(instance),
            )

    except ImportError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Register all signal groups — called from AppConfig.ready()
# ─────────────────────────────────────────────────────────────────────────────

def register_all():
    _register_salary_signals()
    _register_asset_signals()
    _register_document_signals()
