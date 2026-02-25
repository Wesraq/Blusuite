# Role-Based Dashboard Routing - Implementation Guide

## Problem Identified

**Current Issue:** All employees see the same employee dashboard regardless of their role (HR, Accountant, Supervisor). They only get different navigation sections in the sidebar, but the dashboard content is identical.

**Required Solution:** Different employees should see completely different dashboard views based on their `employee_role`:
- HR employees → HR Dashboard (HR operations, approvals, onboarding)
- Accountant employees → Accountant Dashboard (payroll, finance, benefits)
- Supervisor employees → Supervisor Dashboard (team management, team metrics)
- Regular employees → Employee Dashboard (self-service portal)

---

## Implementation Steps

### ✅ Step 1: Update Dashboard Routing (COMPLETED)

**File:** `frontend_views.py` - `dashboard_redirect()` function (Line ~1203)

**Changes Made:**
```python
# For EMPLOYEE role, check employee_role (HR, Accountant, Supervisor)
if role == 'EMPLOYEE':
    if hasattr(user, 'employee_profile') and user.employee_profile:
        employee_role = user.employee_profile.employee_role
        
        # Route to specific dashboard based on employee_role
        if employee_role == 'HR':
            return redirect('hr_dashboard')
        elif employee_role == 'ACCOUNTANT':
            return redirect('accountant_dashboard')
        elif employee_role == 'SUPERVISOR':
            return redirect('supervisor_dashboard')
    
    # Regular employee (no special role)
    return redirect('employee_dashboard')
```

---

### 🔄 Step 2: Add View Functions (IN PROGRESS)

#### A. HR Dashboard View
**Add to:** `frontend_views.py`

```python
@login_required
def hr_dashboard(request):
    """HR Dashboard - HR-specific operations and metrics"""
    # Check if user has HR role
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'HR':
            messages.error(request, 'Access denied. HR role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # HR-specific data queries...
    # (See hr_dashboard_view.py for complete implementation)
    
    return render(request, 'ems/hr_dashboard.html', context)
```

#### B. Accountant Dashboard View
**Add to:** `frontend_views.py`

```python
@login_required
def accountant_dashboard(request):
    """Accountant Dashboard - Finance and payroll operations"""
    # Check if user has Accountant role
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'ACCOUNTANT':
            messages.error(request, 'Access denied. Accountant role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Finance-specific data queries...
    # (See hr_dashboard_view.py for complete implementation)
    
    return render(request, 'ems/accountant_dashboard.html', context)
```

#### C. Update Supervisor Dashboard View
**Update existing:** `supervisor_dashboard()` function (Line ~10971)

**Current Status:** Already exists but needs to use new template `supervisor_dashboard_new.html`

---

### ⏳ Step 3: Add URL Routes

**File:** `ems_project/urls.py`

**Add these routes:**
```python
# Role-specific dashboards
path('hr/dashboard/', frontend_views.hr_dashboard, name='hr_dashboard'),
path('accountant/dashboard/', frontend_views.accountant_dashboard, name='accountant_dashboard'),
# supervisor_dashboard already exists
```

---

### ⏳ Step 4: Update Template References

**Update supervisor_dashboard view to use new template:**
```python
# Change from:
return render(request, 'ems/supervisor_dashboard.html', context)

# To:
return render(request, 'ems/supervisor_dashboard_new.html', context)
```

---

## Testing Checklist

### Test User: Christopher Tembo (Accountant)
- [x] User has `employee_role = 'ACCOUNTANT'`
- [ ] Clicking Dashboard redirects to `/accountant/dashboard/`
- [ ] Sees Accountant Dashboard with finance metrics
- [ ] Can access payroll, benefits, financial reports
- [ ] Cannot access HR-only functions

### Test User: Bright Muchindu (HR)
- [x] User has `employee_role = 'HR'`
- [ ] Clicking Dashboard redirects to `/hr/dashboard/`
- [ ] Sees HR Dashboard with HR metrics
- [ ] Can access employee management, approvals, onboarding
- [ ] Cannot access payroll processing

### Test User: Regular Employee
- [x] User has `employee_role = 'EMPLOYEE'` or None
- [ ] Clicking Dashboard redirects to `/employee/`
- [ ] Sees Employee Dashboard (self-service)
- [ ] Can only access own data
- [ ] Cannot access management functions

### Test User: Supervisor
- [x] User has `employee_role = 'SUPERVISOR'`
- [ ] Clicking Dashboard redirects to `/supervisor/dashboard/`
- [ ] Sees Supervisor Dashboard with team metrics
- [ ] Can access team data only
- [ ] Cannot access other teams or company-wide data

---

## Files Modified/Created

### Modified:
1. ✅ `frontend_views.py` - Updated `dashboard_redirect()` function

### To Add:
2. ⏳ `frontend_views.py` - Add `hr_dashboard()` function
3. ⏳ `frontend_views.py` - Add `accountant_dashboard()` function
4. ⏳ `frontend_views.py` - Update `supervisor_dashboard()` template reference
5. ⏳ `urls.py` - Add new URL routes

### Templates (Already Created):
- ✅ `employee_dashboard_new.html`
- ✅ `admin_dashboard_new.html`
- ✅ `hr_dashboard.html`
- ✅ `accountant_dashboard.html`
- ✅ `supervisor_dashboard_new.html`

---

## Next Actions

1. **Copy view functions** from `hr_dashboard_view.py` into `frontend_views.py`
2. **Add URL routes** in `urls.py`
3. **Update supervisor template reference**
4. **Test with different employee roles**
5. **Verify access control** is working

---

## Expected Behavior After Implementation

| User Role | employee_role | Dashboard URL | Dashboard View |
|-----------|---------------|---------------|----------------|
| EMPLOYEE | None/EMPLOYEE | `/employee/` | Employee Dashboard (self-service) |
| EMPLOYEE | HR | `/hr/dashboard/` | HR Dashboard (HR operations) |
| EMPLOYEE | ACCOUNTANT | `/accountant/dashboard/` | Accountant Dashboard (finance) |
| EMPLOYEE | SUPERVISOR | `/supervisor/dashboard/` | Supervisor Dashboard (team mgmt) |
| EMPLOYER_ADMIN | N/A | `/employer/` | Admin Dashboard (full access) |
| ADMINISTRATOR | N/A | `/employer/` | Admin Dashboard (full access) |

---

## Security Notes

Each dashboard view includes role verification:
```python
try:
    profile = request.user.employee_profile
    if profile.employee_role != 'EXPECTED_ROLE':
        messages.error(request, 'Access denied.')
        return redirect('employee_dashboard')
except:
    messages.error(request, 'Employee profile not found.')
    return redirect('employee_dashboard')
```

This ensures users cannot access dashboards they're not authorized for, even if they know the URL.
