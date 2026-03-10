"""
Centralized Settings Management for BluSuite
Handles settings versioning, validation, export/import, and inheritance
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
import json
from datetime import datetime


User = get_user_model()


class SettingsCategory(models.TextChoices):
    """Categories for organizing settings"""
    SYSTEM = 'SYSTEM', 'System Settings'
    SECURITY = 'SECURITY', 'Security Settings'
    ATTENDANCE = 'ATTENDANCE', 'Attendance Settings'
    LEAVE = 'LEAVE', 'Leave Management'
    PAYROLL = 'PAYROLL', 'Payroll Settings'
    NOTIFICATIONS = 'NOTIFICATIONS', 'Notification Settings'
    BRANDING = 'BRANDING', 'Branding & Customization'
    INTEGRATIONS = 'INTEGRATIONS', 'Third-party Integrations'
    COMPLIANCE = 'COMPLIANCE', 'Compliance & Audit'


class SystemSetting(models.Model):
    """
    System-wide default settings that apply to all companies
    Can be overridden at company level
    """
    category = models.CharField(max_length=20, choices=SettingsCategory.choices, db_index=True)
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.JSONField()
    default_value = models.JSONField()
    description = models.TextField()
    data_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON Object'),
            ('list', 'List'),
        ],
        default='string'
    )
    is_required = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False, help_text="Mask value in UI")
    validation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON schema for validation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_settings_updates'
    )
    
    class Meta:
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category', 'key']),
        ]
    
    def __str__(self):
        return f"{self.category}: {self.key}"
    
    def validate_value(self, value):
        """Validate value against data type and rules"""
        # Type validation
        if self.data_type == 'integer':
            if not isinstance(value, int):
                raise ValidationError(f"{self.key} must be an integer")
        elif self.data_type == 'float':
            if not isinstance(value, (int, float)):
                raise ValidationError(f"{self.key} must be a number")
        elif self.data_type == 'boolean':
            if not isinstance(value, bool):
                raise ValidationError(f"{self.key} must be true or false")
        elif self.data_type == 'list':
            if not isinstance(value, list):
                raise ValidationError(f"{self.key} must be a list")
        elif self.data_type == 'json':
            if not isinstance(value, dict):
                raise ValidationError(f"{self.key} must be a JSON object")
        
        # Custom validation rules
        if self.validation_rules:
            rules = self.validation_rules
            
            # Min/max for numbers
            if 'min' in rules and value < rules['min']:
                raise ValidationError(f"{self.key} must be at least {rules['min']}")
            if 'max' in rules and value > rules['max']:
                raise ValidationError(f"{self.key} must be at most {rules['max']}")
            
            # Min/max length for strings
            if 'min_length' in rules and len(str(value)) < rules['min_length']:
                raise ValidationError(f"{self.key} must be at least {rules['min_length']} characters")
            if 'max_length' in rules and len(str(value)) > rules['max_length']:
                raise ValidationError(f"{self.key} must be at most {rules['max_length']} characters")
            
            # Allowed values
            if 'allowed_values' in rules and value not in rules['allowed_values']:
                raise ValidationError(f"{self.key} must be one of: {', '.join(map(str, rules['allowed_values']))}")
        
        return True


class CompanySettingOverride(models.Model):
    """
    Company-specific setting overrides
    Inherits from SystemSetting defaults
    """
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='setting_overrides'
    )
    system_setting = models.ForeignKey(
        SystemSetting,
        on_delete=models.CASCADE,
        related_name='company_overrides'
    )
    value = models.JSONField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='company_setting_updates'
    )
    
    class Meta:
        unique_together = [('company', 'system_setting')]
        ordering = ['company', 'system_setting__category', 'system_setting__key']
    
    def __str__(self):
        return f"{self.company.name}: {self.system_setting.key}"
    
    def clean(self):
        """Validate override value"""
        if self.system_setting:
            self.system_setting.validate_value(self.value)


class SettingsVersion(models.Model):
    """
    Track settings changes for audit and rollback
    """
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='settings_versions',
        null=True,
        blank=True,
        help_text="Null for system-wide settings"
    )
    category = models.CharField(max_length=20, choices=SettingsCategory.choices)
    settings_snapshot = models.JSONField(help_text="Complete settings at this version")
    changes = models.JSONField(help_text="What changed from previous version")
    version_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='settings_versions_created'
    )
    comment = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'category', '-version_number']),
        ]
    
    def __str__(self):
        company_name = self.company.name if self.company else 'System'
        return f"{company_name} - {self.category} v{self.version_number}"


class SettingsTemplate(models.Model):
    """
    Pre-configured settings templates for different company types
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=SettingsCategory.choices)
    settings_data = models.JSONField(help_text="Template settings configuration")
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.category})"


# ─────────────────────────────────────────────────────────────────────────────
# Settings Management Functions
# ─────────────────────────────────────────────────────────────────────────────

def get_setting(key, company=None, default=None):
    """
    Get setting value with inheritance
    Company override > System default > Provided default
    """
    try:
        system_setting = SystemSetting.objects.get(key=key)
        
        # Check for company override
        if company:
            try:
                override = CompanySettingOverride.objects.get(
                    company=company,
                    system_setting=system_setting,
                    is_active=True
                )
                return override.value
            except CompanySettingOverride.DoesNotExist:
                pass
        
        # Return system default
        return system_setting.value
    
    except SystemSetting.DoesNotExist:
        return default


def set_setting(key, value, company=None, user=None, comment=''):
    """
    Set setting value with validation and versioning
    """
    try:
        system_setting = SystemSetting.objects.get(key=key)
    except SystemSetting.DoesNotExist:
        raise ValueError(f"Setting '{key}' does not exist")
    
    # Validate value
    system_setting.validate_value(value)
    
    if company:
        # Create or update company override
        override, created = CompanySettingOverride.objects.update_or_create(
            company=company,
            system_setting=system_setting,
            defaults={
                'value': value,
                'updated_by': user,
            }
        )
        
        # Create version snapshot
        _create_settings_version(company, system_setting.category, user, comment)
        
        return override
    else:
        # Update system setting
        old_value = system_setting.value
        system_setting.value = value
        system_setting.updated_by = user
        system_setting.save()
        
        # Create version snapshot
        _create_settings_version(None, system_setting.category, user, comment)
        
        return system_setting


def get_all_settings(company=None, category=None):
    """
    Get all settings for a company or system-wide
    Returns dict with inheritance applied
    """
    settings = {}
    
    # Get system settings
    queryset = SystemSetting.objects.all()
    if category:
        queryset = queryset.filter(category=category)
    
    for system_setting in queryset:
        # Check for company override
        value = system_setting.value
        
        if company:
            try:
                override = CompanySettingOverride.objects.get(
                    company=company,
                    system_setting=system_setting,
                    is_active=True
                )
                value = override.value
            except CompanySettingOverride.DoesNotExist:
                pass
        
        settings[system_setting.key] = {
            'value': value,
            'category': system_setting.category,
            'description': system_setting.description,
            'data_type': system_setting.data_type,
            'is_overridden': company and CompanySettingOverride.objects.filter(
                company=company,
                system_setting=system_setting,
                is_active=True
            ).exists()
        }
    
    return settings


def export_settings(company=None, category=None):
    """
    Export settings to JSON for backup or migration
    """
    settings = get_all_settings(company, category)
    
    export_data = {
        'exported_at': timezone.now().isoformat(),
        'company': company.name if company else 'System',
        'category': category or 'All',
        'settings': {}
    }
    
    for key, data in settings.items():
        export_data['settings'][key] = {
            'value': data['value'],
            'category': data['category'],
        }
    
    return export_data


def import_settings(import_data, company=None, user=None, overwrite=False):
    """
    Import settings from JSON
    """
    imported_count = 0
    skipped_count = 0
    errors = []
    
    for key, data in import_data.get('settings', {}).items():
        try:
            # Check if setting exists
            system_setting = SystemSetting.objects.get(key=key)
            
            # Check if already overridden
            if company and not overwrite:
                if CompanySettingOverride.objects.filter(
                    company=company,
                    system_setting=system_setting,
                    is_active=True
                ).exists():
                    skipped_count += 1
                    continue
            
            # Set value
            set_setting(key, data['value'], company, user, comment='Imported from backup')
            imported_count += 1
        
        except Exception as e:
            errors.append(f"{key}: {str(e)}")
    
    return {
        'imported': imported_count,
        'skipped': skipped_count,
        'errors': errors
    }


def apply_template(template_name, company, user=None):
    """
    Apply settings template to company
    """
    try:
        template = SettingsTemplate.objects.get(name=template_name, is_active=True)
    except SettingsTemplate.DoesNotExist:
        raise ValueError(f"Template '{template_name}' not found")
    
    applied_count = 0
    
    for key, value in template.settings_data.items():
        try:
            set_setting(key, value, company, user, comment=f'Applied template: {template_name}')
            applied_count += 1
        except Exception:
            pass
    
    return applied_count


def rollback_settings(company, category, version_number):
    """
    Rollback settings to a previous version
    """
    try:
        version = SettingsVersion.objects.get(
            company=company,
            category=category,
            version_number=version_number
        )
    except SettingsVersion.DoesNotExist:
        raise ValueError(f"Version {version_number} not found")
    
    # Apply snapshot
    restored_count = 0
    
    for key, value in version.settings_snapshot.items():
        try:
            set_setting(key, value, company, comment=f'Rollback to v{version_number}')
            restored_count += 1
        except Exception:
            pass
    
    return restored_count


def _create_settings_version(company, category, user, comment=''):
    """
    Create settings version snapshot
    """
    # Get current settings
    current_settings = get_all_settings(company, category)
    
    # Get previous version
    previous_version = SettingsVersion.objects.filter(
        company=company,
        category=category
    ).first()
    
    # Calculate changes
    changes = {}
    if previous_version:
        for key, data in current_settings.items():
            old_value = previous_version.settings_snapshot.get(key, {}).get('value')
            new_value = data['value']
            if old_value != new_value:
                changes[key] = {
                    'old': old_value,
                    'new': new_value
                }
    
    # Get next version number
    version_number = (previous_version.version_number + 1) if previous_version else 1
    
    # Create snapshot
    snapshot_data = {key: data['value'] for key, data in current_settings.items()}
    
    SettingsVersion.objects.create(
        company=company,
        category=category,
        settings_snapshot=snapshot_data,
        changes=changes,
        version_number=version_number,
        created_by=user,
        comment=comment
    )


def initialize_default_settings():
    """
    Initialize system with default settings
    """
    defaults = [
        # Security Settings
        {
            'category': 'SECURITY',
            'key': 'password_min_length',
            'value': 8,
            'default_value': 8,
            'description': 'Minimum password length',
            'data_type': 'integer',
            'validation_rules': {'min': 6, 'max': 128}
        },
        {
            'category': 'SECURITY',
            'key': 'password_require_uppercase',
            'value': True,
            'default_value': True,
            'description': 'Require uppercase letters in password',
            'data_type': 'boolean'
        },
        {
            'category': 'SECURITY',
            'key': 'session_timeout_minutes',
            'value': 60,
            'default_value': 60,
            'description': 'Session timeout in minutes',
            'data_type': 'integer',
            'validation_rules': {'min': 5, 'max': 1440}
        },
        {
            'category': 'SECURITY',
            'key': 'max_failed_login_attempts',
            'value': 5,
            'default_value': 5,
            'description': 'Maximum failed login attempts before lockout',
            'data_type': 'integer',
            'validation_rules': {'min': 3, 'max': 10}
        },
        
        # Attendance Settings
        {
            'category': 'ATTENDANCE',
            'key': 'work_hours_per_day',
            'value': 8,
            'default_value': 8,
            'description': 'Standard work hours per day',
            'data_type': 'integer',
            'validation_rules': {'min': 1, 'max': 24}
        },
        {
            'category': 'ATTENDANCE',
            'key': 'grace_period_minutes',
            'value': 15,
            'default_value': 15,
            'description': 'Grace period for late arrival (minutes)',
            'data_type': 'integer',
            'validation_rules': {'min': 0, 'max': 60}
        },
        
        # Leave Settings
        {
            'category': 'LEAVE',
            'key': 'annual_leave_days',
            'value': 21,
            'default_value': 21,
            'description': 'Annual leave days per year',
            'data_type': 'integer',
            'validation_rules': {'min': 0, 'max': 365}
        },
        {
            'category': 'LEAVE',
            'key': 'sick_leave_days',
            'value': 10,
            'default_value': 10,
            'description': 'Sick leave days per year',
            'data_type': 'integer',
            'validation_rules': {'min': 0, 'max': 365}
        },
        
        # Payroll Settings
        {
            'category': 'PAYROLL',
            'key': 'payroll_frequency',
            'value': 'MONTHLY',
            'default_value': 'MONTHLY',
            'description': 'Payroll processing frequency',
            'data_type': 'string',
            'validation_rules': {'allowed_values': ['WEEKLY', 'BIWEEKLY', 'MONTHLY']}
        },
        
        # Notification Settings
        {
            'category': 'NOTIFICATIONS',
            'key': 'email_notifications_enabled',
            'value': True,
            'default_value': True,
            'description': 'Enable email notifications',
            'data_type': 'boolean'
        },
    ]
    
    created_count = 0
    
    for setting_data in defaults:
        _, created = SystemSetting.objects.get_or_create(
            key=setting_data['key'],
            defaults=setting_data
        )
        if created:
            created_count += 1
    
    return created_count
