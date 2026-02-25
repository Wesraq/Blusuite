"""
Integration Management Models
Handles OAuth integrations with third-party services
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import secrets

User = get_user_model()


class Integration(models.Model):
    """Model for available integrations"""
    
    class IntegrationType(models.TextChoices):
        SLACK = 'SLACK', _('Slack')
        GOOGLE_CALENDAR = 'GOOGLE_CALENDAR', _('Google Calendar')
        MICROSOFT_TEAMS = 'MICROSOFT_TEAMS', _('Microsoft Teams')
        ZOOM = 'ZOOM', _('Zoom')
        PAYROLL_API = 'PAYROLL_API', _('Payroll System')
        SMS_GATEWAY = 'SMS_GATEWAY', _('SMS Gateway')
        EMAIL_SERVICE = 'EMAIL_SERVICE', _('Email Service')
        HR_SYSTEM = 'HR_SYSTEM', _('HR System')
        ACCOUNTING = 'ACCOUNTING', _('Accounting System')
        OTHER = 'OTHER', _('Other')
    
    name = models.CharField(_('integration name'), max_length=200)
    integration_type = models.CharField(
        _('type'),
        max_length=30,
        choices=IntegrationType.choices
    )
    description = models.TextField(_('description'), blank=True)
    icon_emoji = models.CharField(_('icon emoji'), max_length=10, blank=True)
    
    # OAuth Configuration
    requires_oauth = models.BooleanField(_('requires OAuth'), default=True)
    oauth_authorize_url = models.URLField(_('OAuth authorize URL'), blank=True)
    oauth_token_url = models.URLField(_('OAuth token URL'), blank=True)
    oauth_scope = models.TextField(_('OAuth scope'), blank=True, help_text=_('Space-separated scopes'))
    
    # API Configuration
    api_base_url = models.URLField(_('API base URL'), blank=True)
    documentation_url = models.URLField(_('documentation URL'), blank=True)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    is_available = models.BooleanField(_('available'), default=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('integration')
        verbose_name_plural = _('integrations')
        ordering = ['name']
        db_table = 'accounts_integration'
    
    def __str__(self):
        return self.name


class CompanyIntegration(models.Model):
    """Model for company-specific integration connections"""
    
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        INACTIVE = 'INACTIVE', _('Inactive')
        ERROR = 'ERROR', _('Error')
        PENDING = 'PENDING', _('Pending Authorization')
    
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='integrations'
    )
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='company_connections',
        null=True,
        blank=True,
    )
    
    # Connection Details
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # OAuth Tokens (encrypted in production)
    access_token = models.TextField(_('access token'), blank=True)
    refresh_token = models.TextField(_('refresh token'), blank=True)
    token_expires_at = models.DateTimeField(_('token expires at'), null=True, blank=True)
    
    # API Credentials
    api_key = models.CharField(_('API key'), max_length=500, blank=True)
    api_secret = models.CharField(_('API secret'), max_length=500, blank=True)
    
    # Configuration
    config_json = models.JSONField(_('configuration'), default=dict, blank=True)
    webhook_url = models.URLField(_('webhook URL'), blank=True)
    webhook_secret = models.CharField(_('webhook secret'), max_length=100, blank=True)
    
    # Connection Info
    connected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='connected_integrations'
    )
    connected_at = models.DateTimeField(_('connected at'), null=True, blank=True)
    last_synced_at = models.DateTimeField(_('last synced at'), null=True, blank=True)
    
    # Error Tracking
    last_error = models.TextField(_('last error'), blank=True)
    error_count = models.PositiveIntegerField(_('error count'), default=0)
    
    # Metadata
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('company integration')
        verbose_name_plural = _('company integrations')
        unique_together = ['company', 'integration']
        ordering = ['-created_at']
        db_table = 'accounts_companyintegration'
    
    def __str__(self):
        return f"{self.company.name} - {self.integration.name}"
    
    def generate_webhook_secret(self):
        """Generate a secure webhook secret"""
        self.webhook_secret = secrets.token_urlsafe(32)
        self.save(update_fields=['webhook_secret'])
        return self.webhook_secret
    
    def is_token_valid(self):
        """Check if OAuth token is still valid"""
        if not self.token_expires_at:
            return bool(self.access_token)
        return timezone.now() < self.token_expires_at
    
    def mark_error(self, error_message):
        """Record an integration error"""
        self.last_error = error_message
        self.error_count += 1
        self.status = self.Status.ERROR
        self.save(update_fields=['last_error', 'error_count', 'status', 'updated_at'])
    
    def reset_errors(self):
        """Reset error tracking"""
        self.last_error = ''
        self.error_count = 0
        if self.status == self.Status.ERROR:
            self.status = self.Status.ACTIVE
        self.save(update_fields=['last_error', 'error_count', 'status', 'updated_at'])


class IntegrationLog(models.Model):
    """Model for tracking integration activity"""
    
    class Action(models.TextChoices):
        CONNECTED = 'CONNECTED', _('Connected')
        DISCONNECTED = 'DISCONNECTED', _('Disconnected')
        SYNC = 'SYNC', _('Data Sync')
        WEBHOOK = 'WEBHOOK', _('Webhook Received')
        ERROR = 'ERROR', _('Error')
        TOKEN_REFRESH = 'TOKEN_REFRESH', _('Token Refreshed')
    
    company_integration = models.ForeignKey(
        CompanyIntegration,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    action = models.CharField(
        _('action'),
        max_length=30,
        choices=Action.choices
    )
    description = models.TextField(_('description'), blank=True)
    request_data = models.JSONField(_('request data'), default=dict, blank=True)
    response_data = models.JSONField(_('response data'), default=dict, blank=True)
    success = models.BooleanField(_('success'), default=True)
    error_message = models.TextField(_('error message'), blank=True)
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.CharField(_('user agent'), max_length=500, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('integration log')
        verbose_name_plural = _('integration logs')
        ordering = ['-created_at']
        db_table = 'accounts_integrationlog'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['company_integration', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.company_integration} - {self.action} ({self.created_at})"
