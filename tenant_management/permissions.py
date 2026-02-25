from rest_framework.permissions import BasePermission


class IsTenantMember(BasePermission):
    """Allow access only to authenticated users bound to the current tenant."""

    def has_permission(self, request, view):
        user = request.user
        tenant = getattr(request, 'tenant', None)
        if not user or not user.is_authenticated or not tenant:
            return False
        if user.role == 'SUPERADMIN':
            return True
        company = getattr(user, 'company', None)
        if not company or not getattr(company, 'tenant', None):
            return False
        return company.tenant_id == tenant.id


class HasTenantRole(BasePermission):
    """Allow tenant members with specific roles."""

    allowed_roles = []

    def has_permission(self, request, view):
        if not IsTenantMember().has_permission(request, view):
            return False
        user = request.user
        if not self.allowed_roles:
            return True
        return user.role in self.allowed_roles


class IsTenantAdmin(HasTenantRole):
    allowed_roles = ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']


class IsTenantOwner(HasTenantRole):
    allowed_roles = ['SUPERADMIN', 'ADMINISTRATOR']
