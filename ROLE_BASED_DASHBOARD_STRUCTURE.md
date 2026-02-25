# Role-Based Dashboard Structure - BLU Suite EMS

## User Roles & Access Matrix

### Primary Roles (User.Role)
1. **SUPERADMIN** - System administrator (platform level)
2. **ADMINISTRATOR** - Company owner/admin (full company access)
3. **EMPLOYER_ADMIN** - Branch/Company admin (branch level access)
4. **EMPLOYEE** - Regular employee (self-service only)

### Employee Sub-Roles (EmployeeProfile.EmployeeRole)
1. **EMPLOYEE** - Regular employee
2. **SUPERVISOR** - Team supervisor
3. **HR** - HR personnel
4. **ACCOUNTANT** - Finance/Payroll personnel

---

## Dashboard Access by Role

### 1. EMPLOYEE Dashboard
**Access Level:** Self-service only

**Modules:**
- ✅ My Profile (view/edit personal info)
- ✅ My Attendance (view own attendance, clock in/out)
- ✅ My Leave Requests (create, view own leaves)
- ✅ My Documents (upload, view own documents)
- ✅ My Payslips (view own payslips)
- ✅ My Performance Reviews (view own reviews)
- ✅ My Training (view assigned training, certificates)
- ✅ My Benefits (view enrolled benefits)
- ✅ My Assets (view assigned assets)
- ✅ Notifications (own notifications)
- ✅ Company Announcements (read-only)

**Restrictions:**
- ❌ Cannot view other employees' data
- ❌ Cannot approve/reject anything
- ❌ Cannot access analytics
- ❌ Cannot manage company settings

---

### 2. SUPERVISOR Dashboard
**Access Level:** Team management + Employee access

**Additional Modules (beyond Employee):**
- ✅ My Team Overview (supervised employees)
- ✅ Team Attendance (view/approve team attendance)
- ✅ Team Leave Requests (approve/reject team leaves)
- ✅ Team Performance (conduct reviews for team)
- ✅ Team Reports (basic team analytics)

**Restrictions:**
- ❌ Cannot access other teams' data
- ❌ Cannot manage payroll
- ❌ Cannot manage company settings
- ❌ Limited to assigned team members only

---

### 3. HR Dashboard
**Access Level:** HR operations + Employee access

**Additional Modules (beyond Employee):**
- ✅ Employee Management (add/edit/view all employees)
- ✅ Attendance Management (view/edit all attendance)
- ✅ Leave Management (approve/reject all leaves)
- ✅ Document Management (approve/reject all documents)
- ✅ Performance Management (create/view all reviews)
- ✅ Onboarding Management (manage onboarding workflows)
- ✅ Offboarding Management (manage offboarding workflows)
- ✅ Training Management (assign training, track progress)
- ✅ Benefits Management (enroll employees in benefits)
- ✅ HR Analytics (employee metrics, trends)
- ✅ Announcements (create/manage announcements)

**Restrictions:**
- ❌ Cannot manage payroll (view only)
- ❌ Cannot manage company financial settings
- ❌ Cannot delete company data

---

### 4. ACCOUNTANT Dashboard
**Access Level:** Finance/Payroll operations + Employee access

**Additional Modules (beyond Employee):**
- ✅ Payroll Management (create/process payroll)
- ✅ Salary Management (view/edit salary structures)
- ✅ Benefits Management (manage benefit costs)
- ✅ Deductions Management (manage deductions)
- ✅ Payslip Generation (generate/distribute payslips)
- ✅ Financial Reports (payroll analytics, costs)
- ✅ Tax Management (manage tax calculations)
- ✅ Employee Financial Data (view salary info)

**Restrictions:**
- ❌ Cannot manage attendance (view only)
- ❌ Cannot manage leave (view only)
- ❌ Cannot manage HR operations
- ❌ Cannot manage company settings

---

### 5. EMPLOYER_ADMIN Dashboard
**Access Level:** Branch/Company management (all modules except system settings)

**All Modules:**
- ✅ Dashboard Overview (comprehensive analytics)
- ✅ Employee Management (full CRUD)
- ✅ Attendance Management (full control)
- ✅ Leave Management (full control)
- ✅ Document Management (full control)
- ✅ Performance Management (full control)
- ✅ Payroll Management (full control)
- ✅ Benefits Management (full control)
- ✅ Training Management (full control)
- ✅ Onboarding/Offboarding (full control)
- ✅ Assets Management (full control)
- ✅ Analytics & Reports (all reports)
- ✅ Company Settings (branch settings)
- ✅ Announcements (create/manage)
- ✅ Support Tickets (create/view)

**Restrictions:**
- ❌ Cannot access system-level settings
- ❌ Cannot manage other companies

---

### 6. ADMINISTRATOR Dashboard
**Access Level:** Full company access (all modules)

**All Modules:** (Same as EMPLOYER_ADMIN plus)
- ✅ Company Settings (full control)
- ✅ Branch Management (create/manage branches)
- ✅ User Management (create/manage all users)
- ✅ Integration Settings (API integrations)
- ✅ Billing Management (subscription, invoices)
- ✅ Advanced Analytics (company-wide insights)

---

### 7. SUPERADMIN Dashboard
**Access Level:** System-wide access (platform level)

**System Modules:**
- ✅ System Dashboard (all companies overview)
- ✅ Company Management (approve/manage companies)
- ✅ User Management (all users across companies)
- ✅ System Settings (platform configuration)
- ✅ Billing Overview (all subscriptions)
- ✅ Support Center (all tickets)
- ✅ Knowledge Base (manage articles)
- ✅ System Analytics (platform metrics)
- ✅ Audit Logs (system-wide logs)

---

## Unified UI Design System

### Color Palette
- **Primary (Teal):** `#008080` - Main actions, active states
- **Primary Dark:** `#006666` - Hover states, gradients
- **Primary Light:** `#66b2b2` - Backgrounds, subtle accents
- **Success:** `#22c55e` - Approvals, completed states
- **Warning:** `#f59e0b` - Pending, attention needed
- **Error:** `#dc2626` - Rejections, alerts
- **Dark:** `#0f172a` - Text, headers
- **Gray:** `#64748b` - Secondary text, borders
- **Light Gray:** `#f8fafc` - Backgrounds, cards

### Component Standards

#### Dashboard Cards
```css
background: white;
border: 1px solid #e2e8f0;
border-radius: 12px;
padding: 20px;
box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
```

#### Stat Cards
```css
background: white;
border: 1px solid #e2e8f0;
border-radius: 10px;
padding: 16px;
```

#### Primary Buttons
```css
background: linear-gradient(135deg, #008080 0%, #006666 100%);
color: white;
padding: 10px 20px;
border-radius: 8px;
font-weight: 600;
```

#### Secondary Buttons
```css
background: white;
border: 1px solid #e2e8f0;
color: #0f172a;
padding: 10px 20px;
border-radius: 8px;
font-weight: 600;
```

#### Status Badges
- **Active/Approved:** Green background `#d1fae5`, text `#065f46`
- **Pending:** Yellow background `#fef3c7`, text `#92400e`
- **Rejected/Inactive:** Red background `#fee2e2`, text `#991b1b`

### Navigation Structure

#### Employee Navigation
- Dashboard
- My Profile
- Attendance
- Leave Requests
- Documents
- Payslips
- Training
- Notifications

#### Supervisor Navigation
- Dashboard
- My Team
- Team Attendance
- Team Leave
- Team Performance
- My Profile
- Notifications

#### HR Navigation
- Dashboard
- Employees
- Attendance
- Leave Management
- Documents
- Performance
- Onboarding
- Training
- Benefits
- Analytics
- Notifications

#### Accountant Navigation
- Dashboard
- Payroll
- Salary Management
- Benefits
- Deductions
- Reports
- Notifications

#### Admin Navigation
- Dashboard
- Employees
- Attendance
- Leave
- Documents
- Performance
- Payroll
- Benefits
- Training
- Onboarding
- Assets
- Analytics
- Settings
- Support

---

## Implementation Priority

### Phase 1: Core Dashboards (High Priority)
1. ✅ Employee Dashboard - Self-service portal
2. ✅ Admin Dashboard - Full management interface

### Phase 2: Specialized Dashboards (Medium Priority)
3. ✅ HR Dashboard - HR operations
4. ✅ Accountant Dashboard - Finance operations
5. ✅ Supervisor Dashboard - Team management

### Phase 3: Integration & Testing (High Priority)
6. ✅ Role-based navigation
7. ✅ Access control middleware
8. ✅ UI consistency across all modules
9. ✅ Testing all role permissions

---

## Module Access Control Matrix

| Module | Employee | Supervisor | HR | Accountant | Admin |
|--------|----------|------------|-----|------------|-------|
| Dashboard | Own | Team | All | Finance | All |
| Profile | Own | Own | All | View | All |
| Attendance | Own | Team | All | View | All |
| Leave | Own | Team | All | View | All |
| Documents | Own | Own | All | View | All |
| Performance | Own | Team | All | View | All |
| Payroll | Own | Own | View | All | All |
| Benefits | Own | Own | Manage | Manage | All |
| Training | Own | Team | All | View | All |
| Onboarding | Own | View | All | View | All |
| Assets | Own | View | View | View | All |
| Analytics | None | Team | HR | Finance | All |
| Settings | None | None | None | None | All |

---

## Next Steps

1. Create unified base templates for each role
2. Build role-specific dashboard views
3. Implement navigation based on role
4. Apply consistent UI across all modules
5. Add role-based access control decorators
6. Test all permission boundaries
7. Document user flows for each role
