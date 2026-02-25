# BLU Suite EMS - Functionality Verification Checklist

## Overview
This document provides a comprehensive checklist to verify all EMS functionality across all user roles with mock data before production deployment.

## Test Environment Setup

### 1. Create Test Database
```bash
python manage.py migrate
```

### 2. Create Test Companies
```python
# Run in Django shell: python manage.py shell
from tenant_management.models import Company

# Test Company 1
company1 = Company.objects.create(
    name="Acme Corporation",
    email="admin@acme.com",
    phone="260-XXX-XXXX",
    address="123 Business St, Lusaka",
    is_active=True
)

# Test Company 2
company2 = Company.objects.create(
    name="TechStart Ltd",
    email="admin@techstart.com",
    phone="260-YYY-YYYY",
    address="456 Innovation Ave, Lusaka",
    is_active=True
)
```

### 3. Create Test Users (All Roles)
```python
from ems_project.models import User, EmployeeProfile, Department
from datetime import date

# Create Department
dept = Department.objects.create(
    name="Engineering",
    company=company1,
    description="Engineering Department"
)

# 1. EMPLOYER_ADMIN
admin = User.objects.create_user(
    username="admin@acme.com",
    email="admin@acme.com",
    password="Test123!",
    first_name="Admin",
    last_name="User",
    role="EMPLOYER_ADMIN",
    company=company1
)

# 2. ADMINISTRATOR
administrator = User.objects.create_user(
    username="administrator@acme.com",
    email="administrator@acme.com",
    password="Test123!",
    first_name="System",
    last_name="Administrator",
    role="ADMINISTRATOR",
    company=company1
)

# 3. HR Manager
hr_user = User.objects.create_user(
    username="hr@acme.com",
    email="hr@acme.com",
    password="Test123!",
    first_name="HR",
    last_name="Manager",
    role="HR",
    company=company1
)

# 4. ACCOUNTANT
accountant = User.objects.create_user(
    username="accountant@acme.com",
    email="accountant@acme.com",
    password="Test123!",
    first_name="Finance",
    last_name="Manager",
    role="ACCOUNTANT",
    company=company1
)

# 5. SUPERVISOR
supervisor = User.objects.create_user(
    username="supervisor@acme.com",
    email="supervisor@acme.com",
    password="Test123!",
    first_name="Team",
    last_name="Lead",
    role="SUPERVISOR",
    company=company1
)

# 6. EMPLOYEE (with profile)
employee = User.objects.create_user(
    username="employee@acme.com",
    email="employee@acme.com",
    password="Test123!",
    first_name="John",
    last_name="Doe",
    role="EMPLOYEE",
    company=company1
)

# Create Employee Profile
profile = EmployeeProfile.objects.create(
    user=employee,
    employee_id="EMP001",
    job_title="Software Engineer",
    department=dept,
    date_hired=date(2024, 1, 1),
    salary=15000.00,
    bank_name="Zanaco",
    account_number="1234567890",
    supervisor=supervisor
)

# 7. EMPLOYEE 2 (for team testing)
employee2 = User.objects.create_user(
    username="employee2@acme.com",
    email="employee2@acme.com",
    password="Test123!",
    first_name="Jane",
    last_name="Smith",
    role="EMPLOYEE",
    company=company1
)

profile2 = EmployeeProfile.objects.create(
    user=employee2,
    employee_id="EMP002",
    job_title="Senior Developer",
    department=dept,
    date_hired=date(2024, 1, 15),
    salary=18000.00,
    bank_name="FNB",
    account_number="0987654321",
    supervisor=supervisor
)
```

### 4. Create Mock Data
```python
from ems_project.models import Attendance, LeaveRequest, PerformanceReview
from datetime import datetime, timedelta

# Attendance Records
for i in range(20):
    day = date.today() - timedelta(days=i)
    Attendance.objects.create(
        employee=employee,
        date=day,
        clock_in=datetime.combine(day, datetime.min.time().replace(hour=8, minute=0)),
        clock_out=datetime.combine(day, datetime.min.time().replace(hour=17, minute=0)),
        status='PRESENT'
    )

# Leave Requests
LeaveRequest.objects.create(
    employee=employee,
    leave_type='ANNUAL',
    start_date=date.today() + timedelta(days=30),
    end_date=date.today() + timedelta(days=35),
    reason='Family vacation',
    status='PENDING'
)

LeaveRequest.objects.create(
    employee=employee2,
    leave_type='SICK',
    start_date=date.today() + timedelta(days=5),
    end_date=date.today() + timedelta(days=7),
    reason='Medical appointment',
    status='PENDING'
)

# Performance Review
PerformanceReview.objects.create(
    employee=employee,
    reviewer=supervisor,
    review_date=date.today() + timedelta(days=60),
    review_type='ANNUAL',
    status='SCHEDULED'
)
```

### 5. Create Project & Asset Mock Data
```python
# Projects
from blu_projects.models import Project, Task

project = Project.objects.create(
    name="Website Redesign",
    code="WEB-2024-001",
    description="Complete website redesign project",
    company=company1,
    project_manager=supervisor,
    status='ACTIVE',
    start_date=date.today(),
    end_date=date.today() + timedelta(days=90),
    budget=50000.00
)
project.team_members.add(employee, employee2)

# Tasks
Task.objects.create(
    project=project,
    title="Design mockups",
    description="Create UI/UX mockups",
    assigned_to=employee,
    status='IN_PROGRESS',
    priority='HIGH',
    due_date=date.today() + timedelta(days=14)
)

Task.objects.create(
    project=project,
    title="Frontend development",
    description="Implement frontend components",
    assigned_to=employee2,
    status='TODO',
    priority='MEDIUM',
    due_date=date.today() + timedelta(days=30)
)

# Assets
from blu_assets.models import Asset, EmployeeAsset

laptop = Asset.objects.create(
    name="Dell Latitude 5420",
    asset_type='IT_EQUIPMENT',
    serial_number="DL123456",
    company=company1,
    status='ASSIGNED',
    purchase_date=date(2024, 1, 1),
    purchase_cost=5000.00
)

EmployeeAsset.objects.create(
    asset=laptop,
    employee=employee,
    name="Dell Latitude 5420",
    asset_type='IT_EQUIPMENT',
    status='ASSIGNED',
    assigned_date=date(2024, 1, 15)
)
```

## Verification Checklist

### A. Authentication & Authorization

#### Test Login
- [ ] EMPLOYER_ADMIN can login (admin@acme.com / Test123!)
- [ ] ADMINISTRATOR can login (administrator@acme.com / Test123!)
- [ ] HR can login (hr@acme.com / Test123!)
- [ ] ACCOUNTANT can login (accountant@acme.com / Test123!)
- [ ] SUPERVISOR can login (supervisor@acme.com / Test123!)
- [ ] EMPLOYEE can login (employee@acme.com / Test123!)

#### Test Dashboard Redirect
- [ ] EMPLOYER_ADMIN → `/employer/dashboard/`
- [ ] ADMINISTRATOR → `/admin/dashboard/`
- [ ] HR → `/hr/dashboard/`
- [ ] ACCOUNTANT → `/accountant/dashboard/`
- [ ] SUPERVISOR → `/supervisor/dashboard/`
- [ ] EMPLOYEE → `/employee/`

#### Test Access Control
- [ ] EMPLOYEE cannot access HR dashboard
- [ ] EMPLOYEE cannot access payroll generation
- [ ] SUPERVISOR can view team data only
- [ ] HR can view all employees
- [ ] ACCOUNTANT can access payroll
- [ ] ADMINISTRATOR has full access

### B. Employee Dashboard (EMPLOYEE Role)

#### Dashboard Load
- [ ] Dashboard loads without errors
- [ ] Profile information displays correctly
- [ ] Attendance stats show correct data
- [ ] Leave balance displays
- [ ] Recent activities populate

#### Quick Actions
- [ ] Clock In button works
- [ ] Clock Out button works
- [ ] Request Leave link works
- [ ] View Payslips link works
- [ ] View Profile link works

#### My Suites Access Control
- [ ] Employee WITH project assignment can access My Suites
- [ ] Employee WITH asset assignment can access My Suites
- [ ] Employee WITHOUT projects/assets sees unauthorized message
- [ ] My Suites shows assigned projects
- [ ] My Suites shows assigned assets
- [ ] My Suites shows pending tasks

#### Profile Management
- [ ] Can view own profile
- [ ] Can edit personal information
- [ ] Can update emergency contact
- [ ] Can upload profile picture
- [ ] Can upload documents
- [ ] Cannot edit salary/employment details

### C. Supervisor Dashboard (SUPERVISOR Role)

#### Dashboard Load
- [ ] Dashboard loads without errors
- [ ] Team overview displays
- [ ] Pending approvals count correct
- [ ] Team attendance summary shows

#### Team Management
- [ ] Can view team members list
- [ ] Can view team attendance
- [ ] Can view team performance
- [ ] Cannot edit team salaries

#### Approval Workflow
- [ ] Can view pending leave requests
- [ ] Can approve leave requests
- [ ] Can reject leave requests
- [ ] Approval updates request status
- [ ] Employee receives notification

#### Request Management
- [ ] Can view all team requests
- [ ] Can expand request details
- [ ] Can approve/reject requests
- [ ] Status updates correctly

### D. HR Dashboard (HR Role)

#### Dashboard Load
- [ ] Dashboard loads without errors
- [ ] Employee count displays
- [ ] Department stats show
- [ ] Recent activities populate

#### Employee Management
- [ ] Can view all employees list
- [ ] Can add new employee
- [ ] Can edit employee details
- [ ] Can view employee profile
- [ ] Can assign departments
- [ ] Can assign supervisors
- [ ] Cannot edit salaries (accountant only)

#### Attendance Management
- [ ] Can view all attendance records
- [ ] Can mark attendance manually
- [ ] Can view attendance reports
- [ ] Can export attendance data

#### Leave Management
- [ ] Can view all leave requests
- [ ] Can approve/reject leaves
- [ ] Can view leave balances
- [ ] Can configure leave types
- [ ] Can view leave calendar

#### Performance Reviews
- [ ] Can schedule reviews
- [ ] Can view review history
- [ ] Can assign reviewers
- [ ] Can view review reports

#### Document Management
- [ ] Can view all employee documents
- [ ] Can approve/reject documents
- [ ] Can upload company documents
- [ ] Can download documents

### E. Accountant Dashboard (ACCOUNTANT Role)

#### Dashboard Load
- [ ] Dashboard loads without errors
- [ ] Payroll summary displays
- [ ] Financial stats show
- [ ] Recent payroll activities

#### Payroll Management
- [ ] Can view payroll list
- [ ] Can generate payroll
- [ ] Can select employees for payroll
- [ ] Payroll calculations correct (base + benefits - deductions)
- [ ] NAPSA deduction calculated (5% employee + 5% employer)
- [ ] NHIMA deduction calculated (1% employee)
- [ ] Tax calculated correctly
- [ ] Can view payroll details
- [ ] Can download payslips

#### Salary Management
- [ ] Can view salary structures
- [ ] Can edit employee salaries
- [ ] Can configure salary components
- [ ] Can view salary history

#### Deduction Settings
- [ ] Can configure NAPSA rates
- [ ] Can configure NHIMA rates
- [ ] Can configure tax brackets
- [ ] Can add custom deductions

#### Financial Reports
- [ ] Can view payroll reports
- [ ] Can export financial data
- [ ] Can view cost analysis

### F. Administrator Dashboard (ADMINISTRATOR Role)

#### Dashboard Load
- [ ] Dashboard loads without errors
- [ ] System overview displays
- [ ] All modules accessible

#### Company Management
- [ ] Can view company details
- [ ] Can edit company information
- [ ] Can manage branches
- [ ] Can manage departments

#### User Management
- [ ] Can view all users
- [ ] Can create users (all roles)
- [ ] Can edit user roles
- [ ] Can deactivate users
- [ ] Can reset passwords

#### System Configuration
- [ ] Can configure system settings
- [ ] Can manage permissions
- [ ] Can view audit logs
- [ ] Can configure notifications

#### Module Access
- [ ] Can access all EMS modules
- [ ] Can access Projects (PMS)
- [ ] Can access Assets (AMS)
- [ ] Can access Analytics
- [ ] Can access Support

### G. Employer Admin Dashboard (EMPLOYER_ADMIN Role)

#### Full System Access
- [ ] Dashboard loads without errors
- [ ] Has access to all features
- [ ] Can perform all admin functions
- [ ] Can manage company settings
- [ ] Can view all reports
- [ ] Can access billing/subscription

### H. Cross-Suite Integration

#### Projects Integration (PMS)
- [ ] Employee can view assigned projects
- [ ] Employee can view project tasks
- [ ] Task status updates work
- [ ] Project timeline loads
- [ ] Project calendar loads
- [ ] Project analytics display

#### Assets Integration (AMS)
- [ ] Employee can view assigned assets
- [ ] Asset request workflow works
- [ ] Asset maintenance tracking works
- [ ] Asset inventory displays
- [ ] Asset analytics display

#### Analytics Integration
- [ ] Employee analytics load
- [ ] Project analytics load
- [ ] Financial analytics load
- [ ] Custom reports work
- [ ] Data exports work

### I. Workflows & Processes

#### Leave Request Workflow
1. [ ] Employee submits leave request
2. [ ] Supervisor receives notification
3. [ ] Supervisor approves/rejects
4. [ ] HR receives approved request
5. [ ] HR final approval
6. [ ] Employee receives notification
7. [ ] Leave balance updates

#### Attendance Workflow
1. [ ] Employee clocks in
2. [ ] System records time
3. [ ] Employee clocks out
4. [ ] System calculates hours
5. [ ] Supervisor can view
6. [ ] HR can generate reports

#### Payroll Workflow
1. [ ] Accountant selects period
2. [ ] System fetches attendance
3. [ ] System calculates base pay
4. [ ] System applies deductions
5. [ ] System adds benefits
6. [ ] Payroll generated
7. [ ] Payslips available to employees

#### Document Approval Workflow
1. [ ] Employee uploads document
2. [ ] Document marked pending
3. [ ] HR receives notification
4. [ ] HR reviews document
5. [ ] HR approves/rejects
6. [ ] Employee receives notification

#### Performance Review Workflow
1. [ ] HR schedules review
2. [ ] Reviewer receives notification
3. [ ] Reviewer completes review
4. [ ] Employee views feedback
5. [ ] HR archives review

### J. Data Integrity & Security

#### Multi-tenancy
- [ ] Company 1 users cannot see Company 2 data
- [ ] Data properly isolated by company
- [ ] Queries filtered by company

#### Data Validation
- [ ] Email validation works
- [ ] Phone number validation works
- [ ] Date validation works
- [ ] File upload validation works
- [ ] Required fields enforced

#### Security
- [ ] Passwords hashed
- [ ] CSRF protection active
- [ ] XSS protection active
- [ ] SQL injection protected
- [ ] Unauthorized access blocked

### K. UI/UX Verification

#### Consistent Styling
- [ ] Blue accent color (#1d4ed8) used consistently
- [ ] No teal colors (#008080) remaining
- [ ] Buttons styled consistently
- [ ] Forms styled consistently
- [ ] Tables styled consistently

#### Responsive Design
- [ ] Desktop view works (1920x1080)
- [ ] Tablet view works (768x1024)
- [ ] Mobile view works (375x667)

#### Navigation
- [ ] All menu links work
- [ ] Breadcrumbs display correctly
- [ ] Back buttons work
- [ ] Dashboard links work

#### Messages & Notifications
- [ ] Success messages display
- [ ] Error messages display
- [ ] Warning messages display
- [ ] Info messages display

### L. Performance Testing

#### Page Load Times
- [ ] Dashboard loads < 2 seconds
- [ ] Employee list loads < 3 seconds
- [ ] Reports generate < 5 seconds
- [ ] Large tables paginated

#### Database Queries
- [ ] No N+1 query issues
- [ ] Queries optimized with select_related
- [ ] Queries optimized with prefetch_related
- [ ] Indexes on frequently queried fields

### M. Error Handling

#### 404 Pages
- [ ] Custom 404 page displays
- [ ] Navigation available on 404

#### 500 Errors
- [ ] Custom 500 page displays
- [ ] Errors logged properly

#### Form Errors
- [ ] Validation errors display
- [ ] Field-specific errors show
- [ ] Error messages clear

### N. Export & Reports

#### CSV Exports
- [ ] Employee list exports
- [ ] Attendance exports
- [ ] Payroll exports
- [ ] Leave reports export

#### PDF Generation
- [ ] Payslips generate correctly
- [ ] Employee profiles print correctly
- [ ] Reports generate as PDF

### O. Email Notifications

#### Email Configuration
- [ ] SMTP settings configured
- [ ] Test email sends successfully

#### Notification Triggers
- [ ] Leave request approval email
- [ ] Leave request rejection email
- [ ] Payslip ready email
- [ ] Document approval email
- [ ] Performance review email

## Test Credentials Summary

| Role | Username | Password | Purpose |
|------|----------|----------|---------|
| EMPLOYER_ADMIN | admin@acme.com | Test123! | Full system access |
| ADMINISTRATOR | administrator@acme.com | Test123! | System administration |
| HR | hr@acme.com | Test123! | HR management |
| ACCOUNTANT | accountant@acme.com | Test123! | Payroll & finance |
| SUPERVISOR | supervisor@acme.com | Test123! | Team management |
| EMPLOYEE | employee@acme.com | Test123! | Standard employee |
| EMPLOYEE 2 | employee2@acme.com | Test123! | Team member |

## Automated Testing Script

```python
# Run: python manage.py test
# Or create custom test file: tests/test_ems_functionality.py

from django.test import TestCase, Client
from django.urls import reverse
from ems_project.models import User

class EMSFunctionalityTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create test users
        self.employee = User.objects.create_user(
            username='test@test.com',
            password='test123',
            role='EMPLOYEE'
        )
    
    def test_employee_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'test@test.com',
            'password': 'test123'
        })
        self.assertEqual(response.status_code, 302)
    
    def test_employee_dashboard_access(self):
        self.client.login(username='test@test.com', password='test123')
        response = self.client.get(reverse('employee_dashboard'))
        self.assertEqual(response.status_code, 200)
    
    # Add more tests...
```

## Sign-Off

### Tested By
- [ ] Developer: _________________ Date: _______
- [ ] QA Lead: __________________ Date: _______
- [ ] Product Owner: _____________ Date: _______

### Approved For Production
- [ ] Technical Lead: ____________ Date: _______
- [ ] Project Manager: ___________ Date: _______

---

**Last Updated**: February 14, 2026
**Version**: 1.0
**Status**: Ready for Testing
