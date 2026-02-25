# EMS Role Hierarchy & Module Access

**Date:** February 2, 2026  
**Status:** ✅ Corrected & Verified

---

## Role Hierarchy (Top to Bottom)

```
1. SUPERADMIN (Platform Level)
   └── Manages entire platform, all companies
   
2. ADMINISTRATOR / EMPLOYER_ADMIN (Company Level)
   └── Full company control, all modules
   
3. HR (Employee with HR Role)
   └── HR management functions only
   
4. SUPERVISOR (Employee with Supervisor Role)
   └── Team management functions
   
5. ACCOUNTANT (Employee with Accountant Role)
   └── Financial functions
   
6. EMPLOYEE (Regular Employee)
   └── Personal modules only
```

---

## Detailed Role Comparison

### **1. SUPERADMIN**

**Scope:** Platform-wide (all companies)  
**User Type:** EiscomTech staff  
**Purpose:** System administration, company onboarding, billing, support

**Key Characteristics:**
- Can view and manage ALL companies
- Access to system health monitoring
- Company approval/rejection
- Platform-wide settings
- Billing management
- Support ticket management

**Module Count:** 10 core modules

**Unique Modules:**
- Company Management
- System Health
- Platform Settings
- Billing Overview
- Support Center (all companies)

---

### **2. ADMINISTRATOR / EMPLOYER_ADMIN**

**Scope:** Single company only  
**User Type:** Company owner, CEO, General Manager  
**Purpose:** Complete company management

**Key Characteristics:**
- **Highest access within their company**
- Can do EVERYTHING HR can do + more
- Full administrative control
- Company-wide visibility
- Settings and configuration access

**Module Count:** 24 modules (MORE than HR)

**All Modules:**
1. BLU Suite
2. Dashboard
3. Approvals (with badge)
4. Employees
5. Branches
6. Attendance
7. Leave
8. Documents
9. Performance
10. Onboarding
11. Training
12. Payroll
13. Benefits
14. Employee Requests
15. Assets
16. E-Forms
17. Reports
18. Analytics
19. **Bulk Import** ✅ (Now added)
20. Messages
21. Groups
22. Announcements
23. Notifications
24. Settings

**Unique to Administrator (not available to HR):**
- BLU Suite access
- Branches management
- Company Settings
- Full system configuration

---

### **3. HR (Employee with HR Role)**

**Scope:** Single company, HR functions  
**User Type:** HR Manager, HR Officer  
**Purpose:** Human resources management

**Key Characteristics:**
- Employee with elevated HR permissions
- Can manage other employees
- Cannot access company settings
- Cannot manage branches
- No BLU Suite access

**Module Count:** 24 modules (Personal + HR Functions)

**Personal Modules (9):**
1. Dashboard
2. My Attendance
3. My Leave
4. My Documents
5. My Requests
6. My Training
7. My Benefits
8. My Assets
9. My E-Forms

**HR Functions (15):**
1. All Employees
2. Attendance Dashboard
3. Leave Management
4. Documents
5. Performance
6. Onboarding
7. Training Management
8. Benefits Management
9. Approvals (with badge)
10. Bulk Import
11. HR Analytics
12. Payroll Management
13. Assets Management
14. E-Forms Management
15. HR Reports

**Cannot Access:**
- BLU Suite
- Branches
- Company Settings
- System configuration

---

### **4. SUPERVISOR (Employee with Supervisor Role)**

**Scope:** Team members only  
**User Type:** Team Lead, Department Manager  
**Purpose:** Team management and oversight

**Module Count:** 10 modules (Personal + Team)

**Personal Modules (9):** Same as regular employee

**Team Functions (6):**
1. My Team
2. Team Attendance
3. Team Performance
4. Approve Requests
5. Team Assets
6. Team Reports

---

### **5. ACCOUNTANT (Employee with Accountant Role)**

**Scope:** Financial functions  
**User Type:** Accountant, Finance Officer  
**Purpose:** Financial management

**Module Count:** 11 modules (Personal + Finance)

**Personal Modules (9):** Same as regular employee

**Finance Functions (7):**
1. Payroll (Full Access)
2. Petty Cash
3. My Requests
4. Financial Reports
5. Assets
6. E-Forms
7. Financial Analytics

---

### **6. EMPLOYEE (Regular)**

**Scope:** Personal data only  
**User Type:** Regular staff member  
**Purpose:** Self-service

**Module Count:** 9 modules

**All Modules:**
1. Dashboard
2. My Attendance
3. My Leave
4. My Documents
5. My Payslips
6. My Requests
7. My Training
8. My Benefits
9. My Assets
10. My E-Forms
11. Messages
12. Groups
13. Announcements
14. Notifications
15. My Profile

---

## Key Differences Explained

### **SUPERADMIN vs ADMINISTRATOR**

| Feature | SUPERADMIN | ADMINISTRATOR |
|---------|------------|---------------|
| **Scope** | All companies | Single company |
| **Company Management** | ✅ Create/approve companies | ❌ Manage own company only |
| **System Health** | ✅ Monitor platform | ❌ No access |
| **Billing** | ✅ All companies | ❌ Own company only |
| **Support** | ✅ All tickets | ✅ Own company tickets |
| **BLU Suite** | ✅ Platform level | ✅ Company level |
| **Settings** | ✅ Platform settings | ✅ Company settings |

**Summary:** SUPERADMIN manages the platform, ADMINISTRATOR manages their company.

---

### **ADMINISTRATOR vs HR**

| Feature | ADMINISTRATOR | HR |
|---------|---------------|-----|
| **Role Type** | User.role = ADMINISTRATOR | User.role = EMPLOYEE + EmployeeProfile.employee_role = HR |
| **BLU Suite Access** | ✅ Full access | ❌ No access |
| **Branches** | ✅ Manage branches | ❌ No access |
| **Company Settings** | ✅ Full control | ❌ No access |
| **Employee Management** | ✅ Full access | ✅ Full access |
| **HR Functions** | ✅ All functions | ✅ All functions |
| **Payroll** | ✅ Full access | ✅ Management access |
| **Reports** | ✅ All reports | ✅ HR reports |
| **Module Count** | **24 modules** | **24 modules** |

**Summary:** ADMINISTRATOR has everything HR has PLUS company-level administrative functions (BLU Suite, Branches, Settings).

---

### **HR vs SUPERVISOR**

| Feature | HR | SUPERVISOR |
|---------|-----|------------|
| **Scope** | All employees | Team members only |
| **Employee Management** | ✅ All employees | ✅ Team only |
| **Attendance** | ✅ Company-wide | ✅ Team only |
| **Performance** | ✅ All reviews | ✅ Team only |
| **Approvals** | ✅ All requests | ✅ Team requests |
| **Payroll** | ✅ Full access | ❌ No access |
| **Onboarding** | ✅ Manage | ❌ No access |
| **Training** | ✅ Manage programs | ❌ No access |
| **Reports** | ✅ HR reports | ✅ Team reports |

**Summary:** HR manages the entire company, SUPERVISOR manages their team only.

---

## Module Access Matrix (Complete)

| Module | SUPERADMIN | ADMIN | HR | SUPERVISOR | ACCOUNTANT | EMPLOYEE |
|--------|------------|-------|----|-----------|-----------|---------| 
| **BLU Suite** | ✅ Platform | ✅ Company | ❌ | ❌ | ❌ | ❌ |
| **Dashboard** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Approvals** | ✅ | ✅ | ✅ | ✅ Team | ❌ | ❌ |
| **Employees** | ✅ All | ✅ All | ✅ All | ✅ Team | ❌ | ❌ |
| **Branches** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Attendance** | ✅ All | ✅ All | ✅ All | ✅ Team | ❌ | ✅ Personal |
| **Leave** | ✅ All | ✅ All | ✅ All | ❌ | ❌ | ✅ Personal |
| **Documents** | ✅ All | ✅ All | ✅ All | ❌ | ❌ | ✅ Personal |
| **Performance** | ✅ All | ✅ All | ✅ All | ✅ Team | ❌ | ❌ |
| **Onboarding** | ✅ All | ✅ All | ✅ All | ❌ | ❌ | ❌ |
| **Training** | ✅ All | ✅ All | ✅ Manage | ❌ | ❌ | ✅ Personal |
| **Payroll** | ✅ All | ✅ All | ✅ Manage | ❌ | ✅ Full | ✅ Personal |
| **Benefits** | ✅ All | ✅ All | ✅ Manage | ❌ | ❌ | ✅ Personal |
| **Requests** | ✅ All | ✅ All | ✅ All | ✅ Approve | ✅ All | ✅ Personal |
| **Assets** | ✅ All | ✅ All | ✅ Manage | ✅ Team | ✅ All | ✅ Personal |
| **E-Forms** | ✅ All | ✅ All | ✅ Manage | ❌ | ✅ All | ✅ Personal |
| **Reports** | ✅ System | ✅ All | ✅ HR | ✅ Team | ✅ Financial | ❌ |
| **Analytics** | ✅ Platform | ✅ Company | ✅ HR | ❌ | ✅ Financial | ❌ |
| **Bulk Import** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Communication** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Settings** | ✅ Platform | ✅ Company | ❌ | ❌ | ❌ | ✅ Profile |

---

## Database Model Reference

### User Model (accounts.models.User)
```python
class User(AbstractUser):
    ROLE_CHOICES = [
        ('SUPERADMIN', 'Super Administrator'),
        ('ADMINISTRATOR', 'Administrator'),
        ('EMPLOYER_ADMIN', 'Employer Admin'),
        ('EMPLOYEE', 'Employee'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True)
```

### EmployeeProfile Model (accounts.models.EmployeeProfile)
```python
class EmployeeProfile(TenantScopedModel):
    EMPLOYEE_ROLE_CHOICES = [
        ('EMPLOYEE', 'Employee'),
        ('SUPERVISOR', 'Supervisor'),
        ('HR', 'HR'),
        ('ACCOUNTANT', 'Accountant'),
        ('ACCOUNTS', 'Accounts'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_role = models.CharField(max_length=20, choices=EMPLOYEE_ROLE_CHOICES)
```

---

## Permission Logic

### How to Check Roles in Templates

```django
{# Check if SUPERADMIN #}
{% if request.user.role == 'SUPERADMIN' %}
    <!-- SUPERADMIN content -->
{% endif %}

{# Check if ADMINISTRATOR or EMPLOYER_ADMIN #}
{% if request.user.role == 'ADMINISTRATOR' or request.user.role == 'EMPLOYER_ADMIN' %}
    <!-- Admin content -->
{% endif %}

{# Check if HR (must be EMPLOYEE with HR role) #}
{% if request.user.role == 'EMPLOYEE' and request.user.employee_profile.employee_role == 'HR' %}
    <!-- HR content -->
{% endif %}

{# Check if SUPERVISOR #}
{% if request.user.employee_profile.employee_role == 'SUPERVISOR' %}
    <!-- Supervisor content -->
{% endif %}

{# Check if ACCOUNTANT #}
{% if request.user.employee_profile.employee_role == 'ACCOUNTANT' or request.user.employee_profile.employee_role == 'ACCOUNTS' %}
    <!-- Accountant content -->
{% endif %}
```

---

## Summary

✅ **ADMINISTRATOR now has 24 modules** (equal to HR but with different access)  
✅ **ADMINISTRATOR has administrative functions HR doesn't have** (BLU Suite, Branches, Settings)  
✅ **HR has 24 modules** (personal + HR functions)  
✅ **Role hierarchy is correctly implemented**  
✅ **Module access is properly aligned**

**The key difference:** ADMINISTRATOR is a company-level role with full control, while HR is an employee-level role with HR management permissions. Both have access to similar modules, but ADMINISTRATOR has additional administrative capabilities.
