# Subscription Feature Access Control System

## Overview
This system enforces feature-based access control based on subscription plans (STARTER, PROFESSIONAL, ENTERPRISE). Users can only access features included in their company's subscription plan.

---

## Subscription Plans & Features

### STARTER Plan (ZMW 29/month)
- **Max Employees:** 25
- **Features:**
  - Basic attendance tracking
  - Leave management
  - Payroll processing
  - Email support
  - Mobile app access

### PROFESSIONAL Plan (ZMW 79/month)
- **Max Employees:** 100
- **Features:** All STARTER features plus:
  - Advanced attendance & GPS tracking
  - Leave management & approvals
  - Automated payroll processing
  - Performance reviews
  - Document management
  - Custom reports
  - Priority support

### ENTERPRISE Plan (Custom pricing)
- **Max Employees:** Unlimited
- **Features:** All PROFESSIONAL features plus:
  - Advanced analytics & insights
  - Custom integrations
  - Dedicated account manager
  - 24/7 phone support
  - Custom training
  - SLA guarantee
  - Bulk import
  - Advanced reports
  - API access

---

## Implementation Components

### 1. Permission System (`accounts/permissions.py`)
- **`PLAN_FEATURES`**: Dictionary mapping plans to features
- **`get_company_plan(user)`**: Get user's subscription plan
- **`has_feature_access(user, feature_name)`**: Check if user has access to a feature
- **`require_feature(feature_name)`**: Decorator to protect views
- **`check_employee_limit(company)`**: Check if company can add more employees

### 2. Middleware (`accounts/middleware.py`)
- **`SubscriptionFeatureMiddleware`**: Automatically blocks access to restricted URLs
- Add to `MIDDLEWARE` in settings.py:
```python
MIDDLEWARE = [
    # ... other middleware
    'accounts.middleware.SubscriptionFeatureMiddleware',
]
```

### 3. Template Tags (`accounts/templatetags/subscription_tags.py`)
Load in templates: `{% load subscription_tags %}`

**Available Tags:**
- `{% has_feature 'feature_name' as has_access %}` - Check feature access
- `{% user_plan as plan %}` - Get current user's plan
- `{% user_plan_features as features %}` - Get all features for user's plan
- `{{ plan|plan_display_name }}` - Convert plan code to display name
- `{% employee_limit_info as limit_info %}` - Get employee limit info
- `{% upgrade_prompt 'feature_name' 'Display Name' %}` - Show upgrade prompt

### 4. Context Processor (`accounts/context_processors.py`)
Add to `TEMPLATES` context_processors in settings.py:
```python
'context_processors': [
    # ... other processors
    'accounts.context_processors.subscription_context',
]
```

**Available in all templates:**
- `user_subscription_plan` - Current user's plan
- `user_plan_features` - List of features for user's plan
- `is_superadmin` - Boolean if user is superadmin
- `has_feature` - Function to check feature access

---

## Usage Examples

### Protecting Views with Decorator

```python
from accounts.permissions import require_feature

@require_feature('performance_reviews')
def performance_review_list(request):
    # Only accessible to PROFESSIONAL and ENTERPRISE plans
    reviews = PerformanceReview.objects.filter(company=request.user.company)
    return render(request, 'performance/list.html', {'reviews': reviews})

@require_feature('advanced_analytics')
def analytics_dashboard(request):
    # Only accessible to ENTERPRISE plan
    return render(request, 'analytics/dashboard.html')
```

### Checking Access in Views

```python
from accounts.permissions import has_feature_access, get_company_plan

def my_view(request):
    if has_feature_access(request.user, 'document_management'):
        # User has access to document management
        documents = Document.objects.filter(company=request.user.company)
    else:
        # Show upgrade prompt
        plan = get_company_plan(request.user)
        messages.warning(request, f'Document management is not available in your {plan} plan.')
        documents = []
    
    return render(request, 'documents/list.html', {'documents': documents})
```

### Conditional UI in Templates

```django
{% load subscription_tags %}

<!-- Check if user has access to a feature -->
{% has_feature 'performance_reviews' as has_perf_reviews %}
{% if has_perf_reviews %}
    <a href="{% url 'performance_reviews_list' %}">Performance Reviews</a>
{% else %}
    <span class="disabled-link" title="Upgrade to Professional plan">
        Performance Reviews (Locked)
    </span>
{% endif %}

<!-- Show upgrade prompt for restricted features -->
{% has_feature 'advanced_analytics' as has_analytics %}
{% if not has_analytics %}
    {% upgrade_prompt 'advanced_analytics' 'Advanced Analytics' %}
{% endif %}

<!-- Display current plan -->
{% user_plan as current_plan %}
<p>Your current plan: {{ current_plan|plan_display_name }}</p>

<!-- Check employee limit -->
{% employee_limit_info as limit %}
<div class="employee-limit">
    <p>Employees: {{ limit.current }} / {{ limit.max }}</p>
    {% if not limit.can_add %}
        <p class="warning">You've reached your employee limit. Upgrade to add more employees.</p>
    {% endif %}
</div>
```

### Navigation Menu with Feature Checks

```django
{% load subscription_tags %}

<nav>
    <!-- Always visible -->
    <a href="{% url 'attendance_dashboard' %}">Attendance</a>
    <a href="{% url 'leave_management' %}">Leave</a>
    <a href="{% url 'payroll_list' %}">Payroll</a>
    
    <!-- Professional+ only -->
    {% has_feature 'performance_reviews' as has_perf %}
    {% if has_perf %}
        <a href="{% url 'performance_reviews_list' %}">Performance</a>
    {% endif %}
    
    {% has_feature 'document_management' as has_docs %}
    {% if has_docs %}
        <a href="{% url 'documents_list' %}">Documents</a>
    {% endif %}
    
    <!-- Enterprise only -->
    {% has_feature 'advanced_analytics' as has_analytics %}
    {% if has_analytics %}
        <a href="{% url 'analytics_dashboard' %}">Analytics</a>
    {% endif %}
    
    {% has_feature 'bulk_import' as has_bulk %}
    {% if has_bulk %}
        <a href="{% url 'bulk_employee_import' %}">Bulk Import</a>
    {% endif %}
</nav>
```

### Checking Employee Limit Before Adding

```python
from accounts.permissions import check_employee_limit

def add_employee_view(request):
    company = request.user.company
    can_add, current, max_employees = check_employee_limit(company)
    
    if not can_add:
        messages.error(
            request,
            f'You have reached your employee limit ({max_employees}). '
            f'Please upgrade your plan to add more employees.'
        )
        return redirect('employer_employee_management')
    
    # Proceed with adding employee
    form = EmployeeForm(request.POST or None)
    if form.is_valid():
        employee = form.save(commit=False)
        employee.company = company
        employee.save()
        messages.success(request, 'Employee added successfully!')
        return redirect('employer_employee_management')
    
    return render(request, 'employees/add.html', {'form': form})
```

---

## Feature Names Reference

Use these exact feature names in your code:

**Basic Features (STARTER+):**
- `basic_attendance`
- `leave_management`
- `payroll_processing`
- `email_support`
- `mobile_app`

**Professional Features (PROFESSIONAL+):**
- `advanced_attendance`
- `gps_tracking`
- `leave_approvals`
- `automated_payroll`
- `performance_reviews`
- `document_management`
- `custom_reports`
- `priority_support`

**Enterprise Features (ENTERPRISE only):**
- `advanced_analytics`
- `custom_integrations`
- `dedicated_account_manager`
- `phone_support_24_7`
- `custom_training`
- `sla_guarantee`
- `bulk_import`
- `advanced_reports`
- `api_access`

---

## Middleware Protected URLs

These URLs are automatically protected by the middleware:

- `/performance/` → Requires `performance_reviews`
- `/documents/` → Requires `document_management`
- `/reports/custom/` → Requires `custom_reports`
- `/analytics/` → Requires `advanced_analytics`
- `/bulk-import/` → Requires `bulk_import`

**Note:** Superadmins bypass all restrictions.

---

## Testing Feature Access

```python
# In Django shell
from django.contrib.auth import get_user_model
from accounts.permissions import get_company_plan, has_feature_access, get_plan_features

User = get_user_model()
user = User.objects.get(email='test@company.com')

# Check user's plan
plan = get_company_plan(user)
print(f"User's plan: {plan}")

# Check specific feature access
has_perf = has_feature_access(user, 'performance_reviews')
print(f"Has performance reviews: {has_perf}")

# Get all features for plan
features = get_plan_features(plan)
print(f"Available features: {features}")
```

---

## Upgrade Flow

When a user tries to access a restricted feature:

1. **Middleware/Decorator** blocks access
2. **Error message** shows: "This feature is not available in your [PLAN] plan"
3. **Redirect** to dashboard or upgrade page
4. **Upgrade prompt** displays required plan and "View Plans & Upgrade" button
5. User clicks button → Redirected to `/pricing/` page
6. User can compare plans and contact sales or upgrade

---

## Best Practices

1. **Always check feature access** before showing UI elements
2. **Use decorators** for view-level protection
3. **Use template tags** for conditional UI rendering
4. **Show upgrade prompts** instead of hiding features completely
5. **Test with different plans** to ensure proper access control
6. **Update PLAN_FEATURES** when adding new features
7. **Document feature requirements** in view docstrings

---

## Migration Notes

If you need to migrate existing companies from old plan names (BASIC, STANDARD, PREMIUM) to new names (STARTER, PROFESSIONAL, ENTERPRISE):

```python
# Migration script
from accounts.models import Company

# Map old plans to new plans
PLAN_MIGRATION = {
    'BASIC': 'STARTER',
    'STANDARD': 'PROFESSIONAL',
    'PREMIUM': 'ENTERPRISE',
}

for company in Company.objects.all():
    if company.subscription_plan in PLAN_MIGRATION:
        old_plan = company.subscription_plan
        new_plan = PLAN_MIGRATION[old_plan]
        company.subscription_plan = new_plan
        company.save()
        print(f"Migrated {company.name} from {old_plan} to {new_plan}")
```

---

## Summary

This system provides comprehensive subscription-based feature access control with:
- ✅ Automatic URL protection via middleware
- ✅ View-level protection via decorators
- ✅ Template-level UI control via tags
- ✅ Employee limit enforcement
- ✅ Upgrade prompts for restricted features
- ✅ Superadmin bypass for all restrictions
- ✅ Easy to extend with new features

**All features are now properly gated based on subscription plans!**
