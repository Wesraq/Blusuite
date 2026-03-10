# BluSuite Centralized Settings Management Setup Guide

## Overview
Enterprise-grade settings management with versioning, validation, inheritance, export/import, and templates.

---

## Features Implemented

### 1. Settings Models

**File:** `blu_core/settings_manager.py`

**Models:**
- `SystemSetting` — System-wide default settings with validation
- `CompanySettingOverride` — Company-specific overrides
- `SettingsVersion` — Change history and rollback capability
- `SettingsTemplate` — Pre-configured settings for different company types

### 2. Settings Inheritance

**Hierarchy:**
```
Company Override > System Default > Provided Default
```

**Example:**
- System: `session_timeout_minutes = 60`
- Company A Override: `session_timeout_minutes = 30`
- Company B: Uses system default (60)

### 3. Settings Categories

- `SYSTEM` — System-wide configuration
- `SECURITY` — Password policy, session, MFA
- `ATTENDANCE` — Work hours, grace periods
- `LEAVE` — Annual leave, sick leave
- `PAYROLL` — Frequency, processing day
- `NOTIFICATIONS` — Email, in-app notifications
- `BRANDING` — Logo, colors, customization
- `INTEGRATIONS` — Third-party APIs
- `COMPLIANCE` — Audit, retention policies

### 4. Validation

**Data Types:**
- `string` — Text values
- `integer` — Whole numbers
- `float` — Decimal numbers
- `boolean` — True/false
- `json` — JSON objects
- `list` — Arrays

**Validation Rules:**
- Min/max for numbers
- Min/max length for strings
- Allowed values (enum)
- Custom JSON schema

### 5. Versioning

**Features:**
- Automatic version snapshots on change
- Track what changed (old → new)
- Rollback to previous versions
- Change comments/notes
- Per-category versioning

---

## Deployment Steps

### Step 1: Run Migration

```bash
cd /opt/blusuite
source venv/bin/activate
python manage.py migrate blu_core --settings=ems_project.settings_production
```

**Creates:**
- `blu_core_systemsetting` table
- `blu_core_companysettingoverride` table
- `blu_core_settingsversion` table
- `blu_core_settingstemplate` table

### Step 2: Initialize Default Settings

```bash
python manage.py init_settings --settings=ems_project.settings_production
```

**Creates 10 default settings:**
- Security: password_min_length, password_require_uppercase, session_timeout_minutes, max_failed_login_attempts
- Attendance: work_hours_per_day, grace_period_minutes
- Leave: annual_leave_days, sick_leave_days
- Payroll: payroll_frequency
- Notifications: email_notifications_enabled

### Step 3: Verify Settings

```bash
python manage.py shell --settings=ems_project.settings_production
```

```python
from blu_core.settings_manager import get_all_settings

# Get all system settings
settings = get_all_settings()
for key, data in settings.items():
    print(f"{key}: {data['value']}")
```

---

## Usage Examples

### Get Setting Value

```python
from blu_core.settings_manager import get_setting

# System-wide default
timeout = get_setting('session_timeout_minutes')  # 60

# Company-specific (with override)
timeout = get_setting('session_timeout_minutes', company=company)  # 30 or 60
```

### Set Setting Value

```python
from blu_core.settings_manager import set_setting

# Set system-wide default
set_setting(
    'session_timeout_minutes',
    value=90,
    user=request.user,
    comment='Increased for better UX'
)

# Set company override
set_setting(
    'session_timeout_minutes',
    value=30,
    company=company,
    user=request.user,
    comment='Stricter security for this company'
)
```

### Get All Settings

```python
from blu_core.settings_manager import get_all_settings

# All settings for company
settings = get_all_settings(company=company)

# Only security settings
security_settings = get_all_settings(company=company, category='SECURITY')

# Check if overridden
for key, data in settings.items():
    if data['is_overridden']:
        print(f"{key} is customized for this company")
```

### Export Settings

```python
from blu_core.settings_manager import export_settings

# Export all company settings
export_data = export_settings(company=company)

# Export only security settings
export_data = export_settings(company=company, category='SECURITY')

# Save to file
import json
with open('company_settings.json', 'w') as f:
    json.dump(export_data, f, indent=2)
```

**Via Command:**
```bash
# Export company settings
python manage.py export_settings --company "Acme Corp" --output acme_settings.json

# Export system settings
python manage.py export_settings --output system_settings.json

# Export specific category
python manage.py export_settings --company "Acme Corp" --category SECURITY --output security.json
```

### Import Settings

```python
from blu_core.settings_manager import import_settings

# Import settings
with open('company_settings.json', 'r') as f:
    import_data = json.load(f)

result = import_settings(
    import_data,
    company=company,
    user=request.user,
    overwrite=True  # Overwrite existing
)

print(f"Imported: {result['imported']}")
print(f"Skipped: {result['skipped']}")
print(f"Errors: {result['errors']}")
```

**Via Command:**
```bash
# Import to company
python manage.py import_settings --input settings.json --company "Acme Corp" --overwrite

# Import to system
python manage.py import_settings --input settings.json
```

### Apply Template

```python
from blu_core.settings_manager import apply_template

# Apply pre-configured template
count = apply_template('Small Business', company=company, user=request.user)
print(f"Applied {count} settings")
```

### Rollback Settings

```python
from blu_core.settings_manager import rollback_settings

# Rollback to version 5
count = rollback_settings(
    company=company,
    category='SECURITY',
    version_number=5
)
print(f"Restored {count} settings")
```

---

## Creating Custom Settings

### Via Django Admin

1. Go to `/admin/blu_core/systemsetting/`
2. Click "Add System Setting"
3. Fill in:
   - **Category:** SECURITY
   - **Key:** `password_min_special_chars`
   - **Value:** `1`
   - **Default Value:** `1`
   - **Description:** "Minimum special characters in password"
   - **Data Type:** integer
   - **Validation Rules:** `{"min": 0, "max": 10}`
4. Save

### Programmatically

```python
from blu_core.models import SystemSetting

SystemSetting.objects.create(
    category='SECURITY',
    key='password_min_special_chars',
    value=1,
    default_value=1,
    description='Minimum special characters in password',
    data_type='integer',
    validation_rules={'min': 0, 'max': 10},
    is_required=False,
    is_sensitive=False
)
```

---

## Creating Settings Templates

### Via Django Admin

1. Go to `/admin/blu_core/settingstemplate/`
2. Click "Add Settings Template"
3. Fill in:
   - **Name:** "Small Business"
   - **Description:** "Optimized for small businesses (< 50 employees)"
   - **Category:** SECURITY
   - **Settings Data:**
     ```json
     {
       "session_timeout_minutes": 120,
       "max_failed_login_attempts": 5,
       "password_min_length": 8
     }
     ```
   - **Is Active:** ✓
   - **Is Default:** (optional)
4. Save

### Apply to Company

```python
from blu_core.settings_manager import apply_template

apply_template('Small Business', company=company, user=request.user)
```

---

## Settings Versioning

### View Version History

**Django Admin:**
1. Go to `/admin/blu_core/settingsversion/`
2. Filter by company and category
3. See version number, changes, timestamp

**Programmatically:**
```python
from blu_core.models import SettingsVersion

# Get all versions for company
versions = SettingsVersion.objects.filter(
    company=company,
    category='SECURITY'
).order_by('-version_number')

for version in versions:
    print(f"v{version.version_number} - {version.created_at}")
    print(f"Changes: {version.changes}")
    print(f"Comment: {version.comment}")
```

### Compare Versions

```python
# Get two versions
v1 = SettingsVersion.objects.get(company=company, category='SECURITY', version_number=1)
v2 = SettingsVersion.objects.get(company=company, category='SECURITY', version_number=2)

# Compare
for key in v2.changes:
    old = v2.changes[key]['old']
    new = v2.changes[key]['new']
    print(f"{key}: {old} → {new}")
```

---

## Company Override Management

### View Overrides

```python
from blu_core.models import CompanySettingOverride

# Get all overrides for company
overrides = CompanySettingOverride.objects.filter(
    company=company,
    is_active=True
)

for override in overrides:
    print(f"{override.system_setting.key}: {override.value}")
```

### Disable Override (Revert to Default)

```python
# Disable override
override = CompanySettingOverride.objects.get(
    company=company,
    system_setting__key='session_timeout_minutes'
)
override.is_active = False
override.save()

# Now company uses system default
```

### Bulk Override

```python
from blu_core.settings_manager import set_setting

settings_to_override = {
    'session_timeout_minutes': 30,
    'max_failed_login_attempts': 3,
    'password_min_length': 12
}

for key, value in settings_to_override.items():
    set_setting(key, value, company=company, user=request.user)
```

---

## Integration with Existing Code

### Replace Hardcoded Values

**Before:**
```python
SESSION_TIMEOUT = 60  # Hardcoded
```

**After:**
```python
from blu_core.settings_manager import get_setting

SESSION_TIMEOUT = get_setting('session_timeout_minutes', company=request.user.company, default=60)
```

### Migrate from CompanySettings Model

```python
from blu_staff.apps.accounts.models import CompanySettings
from blu_core.settings_manager import set_setting

# Migrate existing settings
for company_settings in CompanySettings.objects.all():
    company = company_settings.tenant.company
    
    # Migrate attendance settings
    set_setting('work_hours_per_day', company_settings.work_hours_per_day, company)
    set_setting('grace_period_minutes', company_settings.grace_period_minutes, company)
    
    # Migrate leave settings
    set_setting('annual_leave_days', company_settings.annual_leave_days, company)
    set_setting('sick_leave_days', company_settings.sick_leave_days, company)
    
    # Migrate payroll settings
    set_setting('payroll_frequency', company_settings.payroll_frequency, company)
```

---

## Best Practices

### 1. Use Descriptive Keys

**Good:**
```python
'password_min_length'
'session_timeout_minutes'
'email_notifications_enabled'
```

**Bad:**
```python
'pwd_len'
'timeout'
'email'
```

### 2. Always Provide Defaults

```python
timeout = get_setting('session_timeout_minutes', company, default=60)
```

### 3. Validate Before Setting

```python
try:
    set_setting('session_timeout_minutes', 999, company)
except ValidationError as e:
    print(f"Invalid value: {e}")
```

### 4. Add Comments on Changes

```python
set_setting(
    'max_failed_login_attempts',
    3,
    company,
    user=request.user,
    comment='Increased security after breach attempt'
)
```

### 5. Use Templates for New Companies

```python
# On company creation
def create_company(name, company_type):
    company = Company.objects.create(name=name)
    
    # Apply template based on type
    if company_type == 'small':
        apply_template('Small Business', company)
    elif company_type == 'enterprise':
        apply_template('Enterprise', company)
    
    return company
```

---

## Monitoring & Audit

### Track Setting Changes

```python
from blu_core.models import SettingsVersion

# Recent changes
recent_changes = SettingsVersion.objects.filter(
    created_at__gte=timezone.now() - timedelta(days=7)
).select_related('company', 'created_by')

for version in recent_changes:
    print(f"{version.company.name} - {version.category}")
    print(f"Changed by: {version.created_by.email}")
    print(f"Changes: {len(version.changes)}")
```

### Alert on Critical Changes

```python
# Monitor security setting changes
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=CompanySettingOverride)
def alert_security_change(sender, instance, created, **kwargs):
    if instance.system_setting.category == 'SECURITY':
        # Send alert to admins
        notify_admins(
            f"Security setting changed: {instance.system_setting.key}",
            f"Company: {instance.company.name}\n"
            f"New value: {instance.value}\n"
            f"Changed by: {instance.updated_by.email}"
        )
```

---

## Troubleshooting

### Setting Not Found

**Problem:** `ValueError: Setting 'xyz' does not exist`

**Solution:**
```python
# Create the setting first
from blu_core.models import SystemSetting

SystemSetting.objects.create(
    category='SYSTEM',
    key='xyz',
    value='default',
    default_value='default',
    description='Description',
    data_type='string'
)
```

### Validation Error

**Problem:** `ValidationError: session_timeout_minutes must be at least 5`

**Solution:**
```python
# Check validation rules
setting = SystemSetting.objects.get(key='session_timeout_minutes')
print(setting.validation_rules)  # {'min': 5, 'max': 1440}

# Use valid value
set_setting('session_timeout_minutes', 30, company)  # ✓
```

### Override Not Working

**Problem:** Company still using system default

**Solution:**
```python
# Check if override is active
override = CompanySettingOverride.objects.get(
    company=company,
    system_setting__key='session_timeout_minutes'
)
print(override.is_active)  # Should be True

# Activate if needed
override.is_active = True
override.save()
```

### Version Rollback Failed

**Problem:** Some settings not restored

**Solution:**
```python
# Check version exists
version = SettingsVersion.objects.filter(
    company=company,
    category='SECURITY',
    version_number=5
).first()

if not version:
    print("Version 5 not found")
else:
    # Manual restore
    for key, value in version.settings_snapshot.items():
        try:
            set_setting(key, value, company)
        except Exception as e:
            print(f"Failed to restore {key}: {e}")
```

---

## Future Enhancements

1. **Settings UI:**
   - Web interface for managing settings
   - Visual diff for version comparison
   - Bulk edit capabilities

2. **Advanced Validation:**
   - Cross-setting dependencies
   - Conditional validation
   - Custom validators

3. **Settings Sync:**
   - Sync settings across environments
   - Multi-region replication
   - Conflict resolution

4. **Settings API:**
   - RESTful API for settings management
   - Real-time updates via WebSocket
   - API key authentication

5. **Settings Analytics:**
   - Usage statistics
   - Popular overrides
   - Optimization recommendations

---

**Document Version:** 1.0  
**Last Updated:** March 10, 2026  
**Next Review:** June 10, 2026
