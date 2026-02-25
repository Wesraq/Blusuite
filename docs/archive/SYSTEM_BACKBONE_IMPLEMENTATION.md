# EMS System Backbone Implementation

**Date:** February 2, 2026  
**Status:** In Progress

---

## Objectives

1. **Administrator Settings Backbone** - Wire comprehensive settings management for Administrators
2. **UI Theme Standardization** - Ensure consistent theme across all pages
3. **Icon Standardization** - Use Feather Icons (SVG) consistently, no emojis
4. **Configuration Management** - Centralized app configuration control

---

## Current State Analysis

### ✅ What's Already Working

1. **Universal CSS Theme System**
   - File: `static/css/universal.css`
   - HSL-based design system with CSS custom properties
   - Light/Dark mode support
   - Responsive design
   - Consistent across all pages

2. **Company Theme Customization**
   - Dynamic company colors in `base.html`
   - Primary, secondary, button, card header colors
   - Text and background customization
   - Theme toggle for administrators

3. **Icon Library**
   - Currently using Feather Icons (SVG inline)
   - Consistent across navigation
   - No emojis in templates (verified)

4. **Settings Models**
   - `SystemSettings` - Platform-wide settings (SuperAdmin)
   - `PayrollDeductionSettings` - Company payroll config
   - Company model has theme fields

### ⚠️ What Needs Enhancement

1. **Administrator Settings UI**
   - Need comprehensive settings dashboard
   - Centralized configuration management
   - Module enable/disable controls
   - Company branding management

2. **Settings Model Expansion**
   - Need `CompanySettings` model for admin-level configs
   - Module visibility controls
   - Feature flags
   - Integration settings

3. **Theme Consistency**
   - Ensure all base templates load `universal.css`
   - Verify icon consistency across all modules
   - Remove Font Awesome dependency (if any)

---

## Implementation Plan

### Phase 1: Settings Model Enhancement ✅

Create comprehensive `CompanySettings` model:

```python
class CompanySettings(TenantScopedModel):
    """Company-level settings managed by Administrator"""
    
    # Module Visibility
    enable_attendance = models.BooleanField(default=True)
    enable_leave = models.BooleanField(default=True)
    enable_payroll = models.BooleanField(default=True)
    enable_performance = models.BooleanField(default=True)
    enable_training = models.BooleanField(default=True)
    enable_onboarding = models.BooleanField(default=True)
    enable_assets = models.BooleanField(default=True)
    enable_eforms = models.BooleanField(default=True)
    enable_benefits = models.BooleanField(default=True)
    enable_documents = models.BooleanField(default=True)
    enable_requests = models.BooleanField(default=True)
    enable_communication = models.BooleanField(default=True)
    enable_reports = models.BooleanField(default=True)
    
    # Feature Flags
    enable_biometric_integration = models.BooleanField(default=False)
    enable_email_notifications = models.BooleanField(default=True)
    enable_sms_notifications = models.BooleanField(default=False)
    enable_slack_integration = models.BooleanField(default=False)
    
    # Workflow Settings
    require_leave_approval = models.BooleanField(default=True)
    require_document_approval = models.BooleanField(default=True)
    require_request_approval = models.BooleanField(default=True)
    
    # Attendance Settings
    allow_manual_attendance = models.BooleanField(default=True)
    require_attendance_photo = models.BooleanField(default=False)
    attendance_grace_period_minutes = models.IntegerField(default=15)
    
    # Leave Settings
    max_leave_days_per_year = models.IntegerField(default=30)
    allow_negative_leave_balance = models.BooleanField(default=False)
    
    # Payroll Settings
    payroll_frequency = models.CharField(
        max_length=20,
        choices=[
            ('WEEKLY', 'Weekly'),
            ('BIWEEKLY', 'Bi-Weekly'),
            ('MONTHLY', 'Monthly'),
        ],
        default='MONTHLY'
    )
    payroll_day_of_month = models.IntegerField(default=25)
    
    # Security Settings
    require_password_change_days = models.IntegerField(default=90)
    session_timeout_minutes = models.IntegerField(default=60)
    enable_two_factor_auth = models.BooleanField(default=False)
    
    # Branding
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    company_stamp = models.ImageField(upload_to='company_stamps/', blank=True, null=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
```

### Phase 2: Administrator Settings Dashboard

Create comprehensive settings UI at `/settings/`:

**Sections:**
1. **General Settings**
   - Company information
   - Branding (logo, colors, stamp)
   - Time zone, currency

2. **Module Management**
   - Enable/disable modules
   - Module-specific configurations
   - Access control

3. **Workflow Configuration**
   - Approval workflows
   - Notification settings
   - Automation rules

4. **Integration Settings**
   - Biometric devices
   - Email/SMS providers
   - Slack/Teams integration
   - API keys

5. **Security & Access**
   - Password policies
   - Session management
   - Two-factor authentication
   - IP whitelisting

6. **Payroll Configuration**
   - Tax settings
   - Deduction rules
   - Pay schedules
   - Bank integration

7. **Attendance & Leave**
   - Working hours
   - Holiday calendar
   - Leave types
   - Attendance rules

8. **Reports & Analytics**
   - Custom report templates
   - Data export settings
   - Analytics preferences

### Phase 3: Theme Standardization

**Ensure all base templates use universal.css:**

1. `base.html` ✅ - Already uses universal.css
2. `base_employee.html` - Verify
3. `base_employer.html` - Verify
4. `base_superadmin.html` ✅ - Already uses universal.css
5. `base_projects.html` - Verify
6. `base_performance.html` - Verify

**Icon Standardization:**
- All icons must be Feather Icons (SVG inline)
- No Font Awesome
- No emojis
- Consistent sizing (18x18 for nav, 20x20 for buttons)

### Phase 4: Context Processor Enhancement

Update `context_processors.py` to include:

```python
def company_settings(request):
    """Provide company settings to all templates"""
    if request.user.is_authenticated and hasattr(request.user, 'company'):
        settings = CompanySettings.objects.filter(
            company=request.user.company
        ).first()
        
        if not settings:
            # Create default settings
            settings = CompanySettings.objects.create(
                company=request.user.company
            )
        
        return {
            'company_settings': settings,
            'modules_enabled': {
                'attendance': settings.enable_attendance,
                'leave': settings.enable_leave,
                'payroll': settings.enable_payroll,
                'performance': settings.enable_performance,
                'training': settings.enable_training,
                'onboarding': settings.enable_onboarding,
                'assets': settings.enable_assets,
                'eforms': settings.enable_eforms,
                'benefits': settings.enable_benefits,
                'documents': settings.enable_documents,
                'requests': settings.enable_requests,
                'communication': settings.enable_communication,
                'reports': settings.enable_reports,
            }
        }
    return {}
```

### Phase 5: Navigation Dynamic Visibility

Update navigation templates to respect module settings:

```django
{% if modules_enabled.attendance %}
<li class="nav-item">
    <a href="{% url 'attendance_dashboard' %}" class="nav-link">
        <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
        </span>
        <span class="nav-text">Attendance</span>
    </a>
</li>
{% endif %}
```

---

## Icon Library Reference

### Feather Icons (SVG) - Standard Set

All icons are 18x18 for navigation, 20x20 for buttons, 24x24 for headers.

**Core Icons:**
- Dashboard: Grid (4 squares)
- Users/Employees: User icon
- Attendance: Clock
- Leave: Calendar
- Documents: File
- Performance: Star
- Onboarding: User-plus
- Training: Book
- Payroll: Dollar-sign
- Benefits: Heart
- Requests: Clipboard
- Assets: Package
- E-Forms: File-text
- Reports: Bar-chart
- Analytics: Pie-chart
- Messages: Message-square
- Groups: Users
- Announcements: Megaphone
- Notifications: Bell
- Settings: Settings (gear)
- Logout: Log-out
- Approvals: Check-circle

**No emojis, no Font Awesome, only Feather Icons SVG.**

---

## Files to Create/Modify

### New Files:
1. `blu_staff/apps/accounts/migrations/XXXX_add_company_settings.py`
2. `ems_project/templates/ems/settings/dashboard.html`
3. `ems_project/templates/ems/settings/modules.html`
4. `ems_project/templates/ems/settings/branding.html`
5. `ems_project/templates/ems/settings/integrations.html`
6. `ems_project/templates/ems/settings/security.html`
7. `ems_project/templates/ems/settings/payroll_config.html`

### Files to Modify:
1. `blu_staff/apps/accounts/models.py` - Add CompanySettings model
2. `ems_project/context_processors.py` - Add company_settings
3. `ems_project/frontend_views.py` - Add settings views
4. `ems_project/urls.py` - Add settings routes
5. `ems_project/templates/ems/partials/sidebar_employer.html` - Dynamic visibility
6. `ems_project/templates/ems/base_employee.html` - Verify universal.css
7. `ems_project/templates/ems/base_employer.html` - Verify universal.css

---

## Testing Checklist

### Theme Consistency:
- [ ] All pages use universal.css
- [ ] Company colors apply consistently
- [ ] Light/dark mode works everywhere
- [ ] No style conflicts

### Icon Consistency:
- [ ] All icons are Feather Icons (SVG)
- [ ] No emojis anywhere
- [ ] Consistent sizing
- [ ] Proper stroke width

### Settings Management:
- [ ] Administrator can access settings
- [ ] All modules can be toggled
- [ ] Changes save correctly
- [ ] Navigation updates dynamically
- [ ] Settings persist across sessions

### Security:
- [ ] Only Administrators can access settings
- [ ] Audit log tracks changes
- [ ] Validation prevents invalid configs
- [ ] Changes require confirmation

---

## Next Steps

1. Create CompanySettings model
2. Run migrations
3. Create settings dashboard UI
4. Wire up settings views
5. Update context processor
6. Make navigation dynamic
7. Test across all roles
8. Document for users

---

## Benefits

1. **Centralized Control** - All app configs in one place
2. **Flexibility** - Enable/disable features per company
3. **Consistency** - Standardized UI and icons
4. **Maintainability** - Easy to add new settings
5. **User Experience** - Clean, professional interface
6. **Scalability** - Ready for multi-tenant growth
