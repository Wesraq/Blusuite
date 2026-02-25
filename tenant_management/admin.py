from django.contrib import admin

from .models import Tenant, TenantDomain, TenantUserRole


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
        'plan_name',
        'is_active',
        'is_trial',
        'plan_expires_at',
        'owner',
    )
    search_fields = ('name', 'slug', 'plan_name', 'owner__email')
    list_filter = ('is_active', 'is_trial', 'plan_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TenantDomain)
class TenantDomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary', 'created_at')
    list_filter = ('is_primary',)
    search_fields = ('domain', 'tenant__name')


@admin.register(TenantUserRole)
class TenantUserRoleAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'user', 'role', 'is_active', 'invited_at', 'accepted_at')
    list_filter = ('role', 'is_active')
    search_fields = ('tenant__name', 'user__email')
