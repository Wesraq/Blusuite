from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import Tenant, TenantDomain, TenantUserRole


@dataclass
class TenantProvisionResult:
    tenant: Tenant
    created: bool


@transaction.atomic
def provision_tenant_for_company(*, company, owner=None, domain: Optional[str] = None) -> TenantProvisionResult:
    """Create or update a tenant for the supplied company.

    Args:
        company: `accounts.Company` instance the tenant should represent.
        owner: Optional user instance to assign as tenant owner.
        domain: Optional domain string to associate with the tenant.
    Returns:
        TenantProvisionResult describing the tenant and whether it was newly created.
    """

    slug = slugify(company.name)
    defaults = {
        "name": company.name,
        "slug": slug,
        "description": getattr(company, "description", ""),
        "plan_name": company.subscription_plan,
        "plan_expires_at": company.license_expiry,
        "is_trial": company.is_trial,
        "trial_ends_at": company.trial_ends_at,
        "max_employees": company.max_employees or 25,
        "storage_quota_gb": getattr(company, "storage_quota_gb", 5.0),
        "primary_color": company.primary_color,
        "secondary_color": company.secondary_color,
        "accent_color": company.button_color,
        "company": company,
    }

    tenant, created = Tenant.objects.get_or_create(
        company=company,
        defaults=defaults,
    )

    if not created:
        updated = False
        for field, value in defaults.items():
            if getattr(tenant, field) != value and value is not None:
                setattr(tenant, field, value)
                updated = True
        if owner and tenant.owner != owner:
            tenant.owner = owner
            updated = True
        if tenant.is_trial and not tenant.trial_ends_at:
            tenant.trial_ends_at = timezone.now() + timezone.timedelta(days=14)
            updated = True
        if updated:
            tenant.save()
    else:
        if owner:
            tenant.owner = owner
        if tenant.is_trial and not tenant.trial_ends_at:
            tenant.trial_ends_at = timezone.now() + timezone.timedelta(days=14)
        tenant.save()

    if owner:
        TenantUserRole.objects.update_or_create(
            tenant=tenant,
            user=owner,
            defaults={
                "role": TenantUserRole.Roles.OWNER,
                "accepted_at": timezone.now(),
                "is_active": True,
            },
        )

    if domain and settings.TENANT_ROUTING_STRATEGY == "subdomain":
        TenantDomain.objects.update_or_create(
            tenant=tenant,
            domain=domain.lower(),
            defaults={"is_primary": True},
        )

    return TenantProvisionResult(tenant=tenant, created=created)


def assign_user_role(*, tenant: Tenant, user, role: str) -> TenantUserRole:
    return TenantUserRole.objects.update_or_create(
        tenant=tenant,
        user=user,
        defaults={
            "role": role,
            "is_active": True,
            "accepted_at": timezone.now(),
        },
    )[0]
