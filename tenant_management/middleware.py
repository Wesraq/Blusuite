from __future__ import annotations

from typing import Optional, Tuple

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from .models import Tenant, TenantDomain


class TenantContextMiddleware(MiddlewareMixin):
    """Attach the active tenant to every request.

    Supports path-based routing using a configurable prefix (default: `/workspace/<slug>/...`)
    and subdomain-based routing via `TenantDomain` entries. Falls back to the tenant stored in
    session when routing data is not present.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.strategy = getattr(settings, "TENANT_ROUTING_STRATEGY", "path")
        raw_prefix = getattr(settings, "TENANT_PATH_PREFIX", "workspace")
        self.path_prefix = f"/{raw_prefix.strip('/')}/"
        excluded = getattr(settings, "TENANT_EXCLUDED_PATH_PREFIXES", tuple())
        self.excluded_prefixes: Tuple[str, ...] = tuple(
            self._normalise_prefix(p) for p in excluded if p
        )
        self.session_key = getattr(settings, "TENANT_SESSION_KEY", "active_tenant_id")

    def process_request(self, request):
        request.tenant = None
        tenant = self._tenant_from_session(request)

        resolved = False
        if not tenant and not self._is_excluded(request.path_info):
            tenant = self._tenant_from_request(request)
            resolved = tenant is not None

        if tenant:
            request.tenant = tenant
            request.session[self.session_key] = tenant.pk
        elif resolved or self.session_key in request.session:
            request.session.pop(self.session_key, None)

    def _tenant_from_session(self, request) -> Optional[Tenant]:
        tenant_id = request.session.get(self.session_key)
        if tenant_id:
            return Tenant.objects.filter(pk=tenant_id, is_active=True).select_related("owner", "company").first()
        return None

    def _tenant_from_request(self, request) -> Optional[Tenant]:
        if self.strategy == "subdomain":
            host = request.get_host().split(":")[0]
            domain = TenantDomain.objects.filter(domain__iexact=host).select_related("tenant", "tenant__owner", "tenant__company").first()
            if domain and domain.tenant.is_active:
                return domain.tenant
            return None

        # Default to path-based routing
        path = request.path_info or "/"
        if not path.startswith(self.path_prefix):
            return None

        relative = path[len(self.path_prefix):]
        if not relative:
            return None

        components = relative.split("/", 1)
        slug = components[0]
        if not slug:
            return None

        tenant = Tenant.objects.filter(slug=slug, is_active=True).select_related("owner", "company").first()
        if not tenant:
            return None

        # Trim tenant slug from PATH_INFO so downstream routing hits the correct URL patterns
        new_path = "/" + components[1] if len(components) > 1 else "/"
        request.path_info = new_path
        request.META["PATH_INFO"] = new_path
        request.tenant_slug = slug
        return tenant

    def _is_excluded(self, path: str) -> bool:
        if not self.excluded_prefixes:
            return False
        return any(path.startswith(prefix) for prefix in self.excluded_prefixes)

    @staticmethod
    def _normalise_prefix(prefix: str) -> str:
        if not prefix:
            return prefix
        prefix = prefix.strip()
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix
