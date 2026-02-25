"""
BLU Suite - Test Data Creation Script
Creates comprehensive mock data for testing all EMS functionality across all user roles.
Run: python manage.py shell < scripts/create_test_data.py
"""

import os
import django
from datetime import date, datetime, timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blu_staff.settings')
django.setup()

from django.contrib.auth import get_user_model
from ems_project.models import (
    EmployeeProfile, Department, Branch, Attendance, 
    LeaveRequest, PerformanceReview
)
from tenant_management.models import Company

User = get_user_model()

print("=" * 80)
print("BLU SUITE - TEST DATA CREATION")
print("=" * 80)

# Clean up existing test data
print("\n[1/10] Cleaning up existing test data...")
Company.objects.filter(name__in=["Acme Corporation", "TechStart Ltd"]).delete()
print("✓ Cleanup complete")

# Create Test Companies
print("\n[2/10] Creating test companies...")
company1 = Company.objects.create(
    name="Acme Corporation",
    email="admin@acme.com",
    phone="260-211-123456",
    address="123 Business Street, Lusaka, Zambia",
    is_active=True
)
print(f"✓ Created company: {company1.name}")

company2 = Company.objects.create(
    name="TechStart Ltd",
    email="admin@techstart.com",
    phone="260-211-654321",
    address="456 Innovation Avenue, Lusaka, Zambia",
    is_active=True
)
print(f"✓ Created company: {company2.name}")

# Create Departments
print("\n[3/10] Creating departments...")
dept_engineering = Department.objects.create(
    name="Engineering",
    company=company1,
    description="Software Development and Engineering"
)
dept_hr = Department.objects.create(
    name="Human Resources",
    company=company1,
    description="HR and People Operations"
)
dept_finance = Department.objects.create(
    name="Finance",
    company=company1,
    description="Finance and Accounting"
)
print(f"✓ Created {Department.objects.filter(company=company1).count()} departments")

# Create Branch
print("\n[4/10] Creating branch...")
branch = Branch.objects.create(
    name="Lusaka HQ",
    company=company1,
    address="123 Business Street, Lusaka",
    phone="260-211-123456",
    email="lusaka@acme.com"
)
print(f"✓ Created branch: {branch.name}")

# Create Test Users
print("\n[5/10] Creating test users...")

# 1. EMPLOYER_ADMIN
admin = User.objects.create_user(
    username="admin@acme.com",
    email="admin@acme.com",
    password="Test123!",
    first_name="Admin",
    last_name="User",
    role="EMPLOYER_ADMIN",
    company=company1,
    phone_number="260-977-111111"
)
print(f"✓ Created EMPLOYER_ADMIN: {admin.email}")

# 2. ADMINISTRATOR
administrator = User.objects.create_user(
    username="administrator@acme.com",
    email="administrator@acme.com",
    password="Test123!",
    first_name="System",
    last_name="Administrator",
    role="ADMINISTRATOR",
    company=company1,
    phone_number="260-977-222222"
)
print(f"✓ Created ADMINISTRATOR: {administrator.email}")

# 3. HR Manager
hr_user = User.objects.create_user(
    username="hr@acme.com",
    email="hr@acme.com",
    password="Test123!",
    first_name="Sarah",
    last_name="Johnson",
    role="HR",
    company=company1,
    phone_number="260-977-333333"
)
hr_profile = EmployeeProfile.objects.create(
    user=hr_user,
    employee_id="EMP-HR-001",
    job_title="HR Manager",
    department=dept_hr,
    date_hired=date(2023, 1, 1),
    salary=Decimal("20000.00"),
    bank_name="Zanaco",
    account_number="1001234567",
    branch=branch
)
print(f"✓ Created HR: {hr_user.email}")

# 4. ACCOUNTANT
accountant = User.objects.create_user(
    username="accountant@acme.com",
    email="accountant@acme.com",
    password="Test123!",
    first_name="Michael",
    last_name="Chen",
    role="ACCOUNTANT",
    company=company1,
    phone_number="260-977-444444"
)
accountant_profile = EmployeeProfile.objects.create(
    user=accountant,
    employee_id="EMP-FIN-001",
    job_title="Senior Accountant",
    department=dept_finance,
    date_hired=date(2023, 2, 1),
    salary=Decimal("18000.00"),
    bank_name="FNB",
    account_number="2001234567",
    branch=branch
)
print(f"✓ Created ACCOUNTANT: {accountant.email}")

# 5. SUPERVISOR
supervisor = User.objects.create_user(
    username="supervisor@acme.com",
    email="supervisor@acme.com",
    password="Test123!",
    first_name="David",
    last_name="Martinez",
    role="SUPERVISOR",
    company=company1,
    phone_number="260-977-555555"
)
supervisor_profile = EmployeeProfile.objects.create(
    user=supervisor,
    employee_id="EMP-ENG-001",
    job_title="Engineering Team Lead",
    department=dept_engineering,
    date_hired=date(2023, 3, 1),
    salary=Decimal("22000.00"),
    bank_name="Stanbic",
    account_number="3001234567",
    branch=branch
)
print(f"✓ Created SUPERVISOR: {supervisor.email}")

# 6. EMPLOYEE 1
employee1 = User.objects.create_user(
    username="employee@acme.com",
    email="employee@acme.com",
    password="Test123!",
    first_name="John",
    last_name="Doe",
    role="EMPLOYEE",
    company=company1,
    phone_number="260-977-666666"
)
profile1 = EmployeeProfile.objects.create(
    user=employee1,
    employee_id="EMP-ENG-002",
    job_title="Software Engineer",
    department=dept_engineering,
    date_hired=date(2024, 1, 1),
    salary=Decimal("15000.00"),
    bank_name="Zanaco",
    account_number="4001234567",
    supervisor=supervisor,
    branch=branch,
    emergency_contact_name="Jane Doe",
    emergency_contact_phone="260-977-777777",
    emergency_contact_email="jane.doe@email.com"
)
print(f"✓ Created EMPLOYEE: {employee1.email}")

# 7. EMPLOYEE 2
employee2 = User.objects.create_user(
    username="employee2@acme.com",
    email="employee2@acme.com",
    password="Test123!",
    first_name="Jane",
    last_name="Smith",
    role="EMPLOYEE",
    company=company1,
    phone_number="260-977-888888"
)
profile2 = EmployeeProfile.objects.create(
    user=employee2,
    employee_id="EMP-ENG-003",
    job_title="Senior Developer",
    department=dept_engineering,
    date_hired=date(2024, 1, 15),
    salary=Decimal("18000.00"),
    bank_name="FNB",
    account_number="5001234567",
    supervisor=supervisor,
    branch=branch,
    emergency_contact_name="Bob Smith",
    emergency_contact_phone="260-977-999999"
)
print(f"✓ Created EMPLOYEE: {employee2.email}")

# 8. EMPLOYEE 3 (No projects/assets - for access control testing)
employee3 = User.objects.create_user(
    username="employee3@acme.com",
    email="employee3@acme.com",
    password="Test123!",
    first_name="Alice",
    last_name="Brown",
    role="EMPLOYEE",
    company=company1,
    phone_number="260-966-111111"
)
profile3 = EmployeeProfile.objects.create(
    user=employee3,
    employee_id="EMP-ENG-004",
    job_title="Junior Developer",
    department=dept_engineering,
    date_hired=date(2024, 2, 1),
    salary=Decimal("12000.00"),
    bank_name="Zanaco",
    account_number="6001234567",
    supervisor=supervisor,
    branch=branch
)
print(f"✓ Created EMPLOYEE (no access): {employee3.email}")

# Create Attendance Records
print("\n[6/10] Creating attendance records...")
attendance_count = 0
for i in range(30):
    day = date.today() - timedelta(days=i)
    # Skip weekends
    if day.weekday() >= 5:
        continue
    
    for emp in [employee1, employee2, employee3]:
        Attendance.objects.create(
            employee=emp,
            date=day,
            clock_in=datetime.combine(day, datetime.min.time().replace(hour=8, minute=0)),
            clock_out=datetime.combine(day, datetime.min.time().replace(hour=17, minute=0)),
            status='PRESENT',
            company=company1
        )
        attendance_count += 1

print(f"✓ Created {attendance_count} attendance records")

# Create Leave Requests
print("\n[7/10] Creating leave requests...")

# Pending leave request
leave1 = LeaveRequest.objects.create(
    employee=employee1,
    leave_type='ANNUAL',
    start_date=date.today() + timedelta(days=30),
    end_date=date.today() + timedelta(days=35),
    reason='Family vacation',
    status='PENDING',
    company=company1
)

# Approved leave request
leave2 = LeaveRequest.objects.create(
    employee=employee2,
    leave_type='SICK',
    start_date=date.today() + timedelta(days=5),
    end_date=date.today() + timedelta(days=7),
    reason='Medical appointment',
    status='APPROVED',
    company=company1
)

# Rejected leave request
leave3 = LeaveRequest.objects.create(
    employee=employee3,
    leave_type='ANNUAL',
    start_date=date.today() + timedelta(days=10),
    end_date=date.today() + timedelta(days=12),
    reason='Personal matters',
    status='REJECTED',
    company=company1
)

print(f"✓ Created {LeaveRequest.objects.filter(company=company1).count()} leave requests")

# Create Performance Reviews
print("\n[8/10] Creating performance reviews...")

review1 = PerformanceReview.objects.create(
    employee=employee1,
    reviewer=supervisor,
    review_date=date.today() + timedelta(days=60),
    review_type='ANNUAL',
    status='SCHEDULED',
    company=company1
)

review2 = PerformanceReview.objects.create(
    employee=employee2,
    reviewer=supervisor,
    review_date=date.today() - timedelta(days=30),
    review_type='QUARTERLY',
    status='COMPLETED',
    overall_rating=4,
    comments='Excellent performance. Consistently delivers high-quality work.',
    company=company1
)

print(f"✓ Created {PerformanceReview.objects.filter(company=company1).count()} performance reviews")

# Create Projects (if blu_projects is available)
print("\n[9/10] Creating projects and tasks...")
try:
    from blu_projects.models import Project, Task
    
    project1 = Project.objects.create(
        name="Website Redesign",
        code="WEB-2024-001",
        description="Complete website redesign project with modern UI/UX",
        company=company1,
        project_manager=supervisor,
        status='ACTIVE',
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=60),
        budget=Decimal("50000.00"),
        progress_percentage=35
    )
    project1.team_members.add(employee1, employee2)
    
    project2 = Project.objects.create(
        name="Mobile App Development",
        code="MOB-2024-001",
        description="Native mobile app for iOS and Android",
        company=company1,
        project_manager=supervisor,
        status='PLANNING',
        start_date=date.today() + timedelta(days=15),
        end_date=date.today() + timedelta(days=120),
        budget=Decimal("75000.00"),
        progress_percentage=5
    )
    project2.team_members.add(employee1)
    
    # Tasks for project 1
    task1 = Task.objects.create(
        project=project1,
        title="Design UI mockups",
        description="Create comprehensive UI/UX mockups for all pages",
        assigned_to=employee1,
        status='IN_PROGRESS',
        priority='HIGH',
        due_date=date.today() + timedelta(days=14)
    )
    
    task2 = Task.objects.create(
        project=project1,
        title="Frontend development",
        description="Implement responsive frontend components",
        assigned_to=employee2,
        status='TODO',
        priority='MEDIUM',
        due_date=date.today() + timedelta(days=30)
    )
    
    task3 = Task.objects.create(
        project=project1,
        title="Backend API integration",
        description="Integrate with existing backend APIs",
        assigned_to=employee1,
        status='TODO',
        priority='HIGH',
        due_date=date.today() + timedelta(days=45)
    )
    
    print(f"✓ Created {Project.objects.filter(company=company1).count()} projects")
    print(f"✓ Created {Task.objects.filter(project__company=company1).count()} tasks")
except ImportError:
    print("⚠ blu_projects not available, skipping project creation")

# Create Assets (if blu_assets is available)
print("\n[10/10] Creating assets...")
try:
    from blu_assets.models import Asset, EmployeeAsset
    
    # Laptops
    laptop1 = Asset.objects.create(
        name="Dell Latitude 5420",
        asset_type='IT_EQUIPMENT',
        serial_number="DL-2024-001",
        company=company1,
        status='ASSIGNED',
        purchase_date=date(2024, 1, 1),
        purchase_cost=Decimal("5000.00"),
        description="15-inch business laptop"
    )
    
    laptop2 = Asset.objects.create(
        name="MacBook Pro 16",
        asset_type='IT_EQUIPMENT',
        serial_number="MBP-2024-001",
        company=company1,
        status='ASSIGNED',
        purchase_date=date(2024, 1, 1),
        purchase_cost=Decimal("12000.00"),
        description="16-inch MacBook Pro M3"
    )
    
    # Office furniture
    desk = Asset.objects.create(
        name="Standing Desk",
        asset_type='FURNITURE',
        serial_number="DESK-2024-001",
        company=company1,
        status='AVAILABLE',
        purchase_date=date(2024, 1, 1),
        purchase_cost=Decimal("2500.00")
    )
    
    # Assign assets to employees
    emp_asset1 = EmployeeAsset.objects.create(
        asset=laptop1,
        employee=employee1,
        name="Dell Latitude 5420",
        asset_type='IT_EQUIPMENT',
        status='ASSIGNED',
        assigned_date=date(2024, 1, 15),
        serial_number="DL-2024-001"
    )
    
    emp_asset2 = EmployeeAsset.objects.create(
        asset=laptop2,
        employee=employee2,
        name="MacBook Pro 16",
        asset_type='IT_EQUIPMENT',
        status='ASSIGNED',
        assigned_date=date(2024, 1, 20),
        serial_number="MBP-2024-001"
    )
    
    print(f"✓ Created {Asset.objects.filter(company=company1).count()} assets")
    print(f"✓ Created {EmployeeAsset.objects.filter(employee__company=company1).count()} employee asset assignments")
except ImportError:
    print("⚠ blu_assets not available, skipping asset creation")

# Summary
print("\n" + "=" * 80)
print("TEST DATA CREATION COMPLETE")
print("=" * 80)
print("\nTest Credentials:")
print("-" * 80)
print(f"{'Role':<20} {'Email':<30} {'Password':<15}")
print("-" * 80)
print(f"{'EMPLOYER_ADMIN':<20} {'admin@acme.com':<30} {'Test123!':<15}")
print(f"{'ADMINISTRATOR':<20} {'administrator@acme.com':<30} {'Test123!':<15}")
print(f"{'HR':<20} {'hr@acme.com':<30} {'Test123!':<15}")
print(f"{'ACCOUNTANT':<20} {'accountant@acme.com':<30} {'Test123!':<15}")
print(f"{'SUPERVISOR':<20} {'supervisor@acme.com':<30} {'Test123!':<15}")
print(f"{'EMPLOYEE':<20} {'employee@acme.com':<30} {'Test123!':<15}")
print(f"{'EMPLOYEE 2':<20} {'employee2@acme.com':<30} {'Test123!':<15}")
print(f"{'EMPLOYEE 3 (No Access)':<20} {'employee3@acme.com':<30} {'Test123!':<15}")
print("-" * 80)

print("\nData Summary:")
print("-" * 80)
print(f"Companies: {Company.objects.count()}")
print(f"Departments: {Department.objects.filter(company=company1).count()}")
print(f"Branches: {Branch.objects.filter(company=company1).count()}")
print(f"Users: {User.objects.filter(company=company1).count()}")
print(f"Employee Profiles: {EmployeeProfile.objects.filter(user__company=company1).count()}")
print(f"Attendance Records: {Attendance.objects.filter(company=company1).count()}")
print(f"Leave Requests: {LeaveRequest.objects.filter(company=company1).count()}")
print(f"Performance Reviews: {PerformanceReview.objects.filter(company=company1).count()}")

try:
    from blu_projects.models import Project, Task
    print(f"Projects: {Project.objects.filter(company=company1).count()}")
    print(f"Tasks: {Task.objects.filter(project__company=company1).count()}")
except:
    pass

try:
    from blu_assets.models import Asset, EmployeeAsset
    print(f"Assets: {Asset.objects.filter(company=company1).count()}")
    print(f"Employee Assets: {EmployeeAsset.objects.filter(employee__company=company1).count()}")
except:
    pass

print("-" * 80)
print("\n✓ You can now test all EMS functionality with these accounts!")
print("✓ Run the development server: python manage.py runserver")
print("✓ Access the application at: http://127.0.0.1:8000/")
print("\n" + "=" * 80)
