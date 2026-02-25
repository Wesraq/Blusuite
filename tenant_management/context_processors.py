from __future__ import annotations

from typing import Any, Dict


def tenant_theme(request) -> Dict[str, Any]:
    """Expose tenant theme values to templates."""
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return {
            "tenant_has_context": False,
        }

    return {
        "tenant_has_context": True,
        "tenant_name": tenant.name,
        "tenant_primary_color": tenant.primary_color,
        "tenant_secondary_color": tenant.secondary_color,
        "tenant_accent_color": tenant.accent_color,
        "tenant_logo": tenant.logo.url if tenant.logo else None,
    }
