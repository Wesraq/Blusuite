from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class TenantScopedQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)


class TenantScopedManager(models.Manager):
    def get_queryset(self):
        return TenantScopedQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant):
        return self.get_queryset().for_tenant(tenant)


class TenantScopedModel(models.Model):
    tenant = models.ForeignKey(
        'tenant_management.Tenant',
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_items',
        null=True,
        blank=True
    )

    objects = TenantScopedManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.tenant_id:
            tenant = self._infer_tenant()
            if tenant:
                self.tenant = tenant
        super().save(*args, **kwargs)

    def _infer_tenant(self):
        direct_tenant = getattr(self, 'tenant', None)
        if isinstance(direct_tenant, Tenant):
            return direct_tenant

        company = getattr(self, 'company', None)
        if company and getattr(company, 'tenant', None):
            return company.tenant

        potential_attrs = (
            'employee',
            'user',
            'document',
            'category',
            'template',
            'branch',
            'request',
            'owner',
            'review',
            'performance_review',
            'goal',
            'metric',
            'feedback',
        )
        for attr in potential_attrs:
            related = getattr(self, attr, None)
            if not related:
                continue
            tenant = getattr(related, 'tenant', None)
            if tenant:
                return tenant
            related_company = getattr(related, 'company', None)
            if related_company and getattr(related_company, 'tenant', None):
                return related_company.tenant
        return None


class Tenant(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    company = models.OneToOneField(
        "accounts.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tenant'
    )

    owner = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='owned_tenants'
    )

    plan_name = models.CharField(max_length=50, default='BASIC')
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    is_trial = models.BooleanField(default=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    max_employees = models.PositiveIntegerField(default=25)
    max_projects = models.PositiveIntegerField(default=10)
    storage_quota_gb = models.FloatField(default=5.0)

    primary_color = models.CharField(max_length=7, default='#1F2A44')
    secondary_color = models.CharField(max_length=7, default='#0099FF')
    accent_color = models.CharField(max_length=7, default='#38BDF8')
    logo = models.ImageField(upload_to='tenant_logos/', null=True, blank=True)

    is_active = models.BooleanField(default=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        if self.is_trial and not self.trial_ends_at:
            self.trial_ends_at = timezone.now() + timezone.timedelta(days=14)

        super().save(*args, **kwargs)

    @property
    def default_domain(self):
        return self.domains.filter(is_primary=True).first()

    @property
    def is_trial_active(self) -> bool:
        if not self.is_trial or not self.trial_ends_at:
            return False
        return self.trial_ends_at >= timezone.now()

    @property
    def is_subscription_active(self) -> bool:
        if self.plan_expires_at:
            return self.plan_expires_at >= timezone.now()
        return True

    def users_with_role(self, role: str):
        company = getattr(self, 'company', None)
        if not company:
            return []
        return company.users.filter(role=role)


class TenantDomain(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='domains'
    )
    domain = models.CharField(max_length=253, unique=True)
    is_primary = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-is_primary', 'domain')

    def __str__(self) -> str:
        return self.domain


class TenantUserRole(models.Model):
    class Roles(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        ADMIN = 'ADMIN', 'Administrator'
        STAFF = 'STAFF', 'Staff Member'
        VIEWER = 'VIEWER', 'Viewer'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='user_roles')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='tenant_roles')
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.STAFF)
    invited_by = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL, related_name='tenant_invites')
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tenant', 'user')
        verbose_name = 'Tenant User Role'
        verbose_name_plural = 'Tenant User Roles'

    def __str__(self) -> str:
        return f"{self.user} @ {self.tenant} ({self.role})"
