"""
Django management command to create comprehensive test data for EMS
Run: python manage.py create_test_data
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import date, datetime, timedelta
from decimal import Decimal

# Import models from the correct locations
User = get_user_model()

# These will be imported dynamically to avoid circular imports
from django.apps import apps

def get_model(app_label, model_name):
    return apps.get_model(app_label, model_name)


class Command(BaseCommand):
    help = 'Creates comprehensive test data for EMS functionality testing'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("BLU SUITE - TEST DATA CREATION")
        self.stdout.write("=" * 80)

        # Clean up existing test data
        self.stdout.write("\n[1/10] Cleaning up existing test data...")
        Company.objects.filter(name__in=["Acme Corporation", "TechStart Ltd"]).delete()
        self.stdout.write(self.style.SUCCESS("✓ Cleanup complete"))

        # Create Test Companies
        self.stdout.write("\n[2/10] Creating test companies...")
        company1 = Company.objects.create(
            name="Acme Corporation",
            email="admin@acme.com",
            phone="260-211-123456",
            address="123 Business Street, Lusaka, Zambia",
            is_active=True
        )
        self.stdout.write(self.style.SUCCESS(f"✓ Created company: {company1.name}"))

        # Create Departments
        self.stdout.write("\n[3/10] Creating departments...")
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
        self.stdout.write(self.style.SUCCESS(f"✓ Created 3 departments"))

        # Create Branch
        self.stdout.write("\n[4/10] Creating branch...")
        branch = Branch.objects.create(
            name="Lusaka HQ",
            company=company1,
            address="123 Business Street, Lusaka",
            phone="260-211-123456",
            email="lusaka@acme.com"
        )
        self.stdout.write(self.style.SUCCESS(f"✓ Created branch: {branch.name}"))

        # Create Test Users
        self.stdout.write("\n[5/10] Creating test users...")

        # EMPLOYER_ADMIN
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
        self.stdout.write(self.style.SUCCESS(f"✓ EMPLOYER_ADMIN: {admin.email}"))

        # ADMINISTRATOR
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
        self.stdout.write(self.style.SUCCESS(f"✓ ADMINISTRATOR: {administrator.email}"))

        # HR Manager
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
        EmployeeProfile.objects.create(
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
        self.stdout.write(self.style.SUCCESS(f"✓ HR: {hr_user.email}"))

        # ACCOUNTANT
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
        EmployeeProfile.objects.create(
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
        self.stdout.write(self.style.SUCCESS(f"✓ ACCOUNTANT: {accountant.email}"))

        # SUPERVISOR
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
        EmployeeProfile.objects.create(
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
        self.stdout.write(self.style.SUCCESS(f"✓ SUPERVISOR: {supervisor.email}"))

        # EMPLOYEE 1
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
        EmployeeProfile.objects.create(
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
        self.stdout.write(self.style.SUCCESS(f"✓ EMPLOYEE: {employee1.email}"))

        # EMPLOYEE 2
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
        EmployeeProfile.objects.create(
            user=employee2,
            employee_id="EMP-ENG-003",
            job_title="Senior Developer",
            department=dept_engineering,
            date_hired=date(2024, 1, 15),
            salary=Decimal("18000.00"),
            bank_name="FNB",
            account_number="5001234567",
            supervisor=supervisor,
            branch=branch
        )
        self.stdout.write(self.style.SUCCESS(f"✓ EMPLOYEE: {employee2.email}"))

        # EMPLOYEE 3 (No projects/assets)
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
        EmployeeProfile.objects.create(
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
        self.stdout.write(self.style.SUCCESS(f"✓ EMPLOYEE (no access): {employee3.email}"))

        # Create Attendance Records
        self.stdout.write("\n[6/10] Creating attendance records...")
        attendance_count = 0
        for i in range(30):
            day = date.today() - timedelta(days=i)
            if day.weekday() >= 5:  # Skip weekends
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

        self.stdout.write(self.style.SUCCESS(f"✓ Created {attendance_count} attendance records"))

        # Create Leave Requests
        self.stdout.write("\n[7/10] Creating leave requests...")
        LeaveRequest.objects.create(
            employee=employee1,
            leave_type='ANNUAL',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=35),
            reason='Family vacation',
            status='PENDING',
            company=company1
        )
        LeaveRequest.objects.create(
            employee=employee2,
            leave_type='SICK',
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=7),
            reason='Medical appointment',
            status='APPROVED',
            company=company1
        )
        self.stdout.write(self.style.SUCCESS(f"✓ Created 2 leave requests"))

        # Create Performance Reviews
        self.stdout.write("\n[8/10] Creating performance reviews...")
        PerformanceReview.objects.create(
            employee=employee1,
            reviewer=supervisor,
            review_date=date.today() + timedelta(days=60),
            review_type='ANNUAL',
            status='SCHEDULED',
            company=company1
        )
        self.stdout.write(self.style.SUCCESS(f"✓ Created 1 performance review"))

        # Create Projects
        self.stdout.write("\n[9/10] Creating projects and tasks...")
        try:
            from blu_projects.models import Project, Task
            
            project1 = Project.objects.create(
                name="Website Redesign",
                code="WEB-2024-001",
                description="Complete website redesign project",
                company=company1,
                project_manager=supervisor,
                status='ACTIVE',
                start_date=date.today() - timedelta(days=30),
                end_date=date.today() + timedelta(days=60),
                budget=Decimal("50000.00"),
                progress_percentage=35
            )
            project1.team_members.add(employee1, employee2)
            
            Task.objects.create(
                project=project1,
                title="Design UI mockups",
                description="Create UI/UX mockups",
                assigned_to=employee1,
                status='IN_PROGRESS',
                priority='HIGH',
                due_date=date.today() + timedelta(days=14)
            )
            Task.objects.create(
                project=project1,
                title="Frontend development",
                description="Implement frontend",
                assigned_to=employee2,
                status='TODO',
                priority='MEDIUM',
                due_date=date.today() + timedelta(days=30)
            )
            self.stdout.write(self.style.SUCCESS(f"✓ Created 1 project with 2 tasks"))
        except ImportError:
            self.stdout.write(self.style.WARNING("⚠ blu_projects not available"))

        # Create Assets
        self.stdout.write("\n[10/10] Creating assets...")
        try:
            from blu_assets.models import Asset, EmployeeAsset
            
            laptop1 = Asset.objects.create(
                name="Dell Latitude 5420",
                asset_type='IT_EQUIPMENT',
                serial_number="DL-2024-001",
                company=company1,
                status='ASSIGNED',
                purchase_date=date(2024, 1, 1),
                purchase_cost=Decimal("5000.00")
            )
            
            EmployeeAsset.objects.create(
                asset=laptop1,
                employee=employee1,
                name="Dell Latitude 5420",
                asset_type='IT_EQUIPMENT',
                status='ASSIGNED',
                assigned_date=date(2024, 1, 15),
                serial_number="DL-2024-001"
            )
            self.stdout.write(self.style.SUCCESS(f"✓ Created 1 asset assignment"))
        except ImportError:
            self.stdout.write(self.style.WARNING("⚠ blu_assets not available"))

        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("TEST DATA CREATION COMPLETE"))
        self.stdout.write("=" * 80)
        self.stdout.write("\nTest Credentials (all passwords: Test123!):")
        self.stdout.write("-" * 80)
        for role, email in [
            ("EMPLOYER_ADMIN", "admin@acme.com"),
            ("ADMINISTRATOR", "administrator@acme.com"),
            ("HR", "hr@acme.com"),
            ("ACCOUNTANT", "accountant@acme.com"),
            ("SUPERVISOR", "supervisor@acme.com"),
            ("EMPLOYEE", "employee@acme.com"),
            ("EMPLOYEE 2", "employee2@acme.com"),
            ("EMPLOYEE 3", "employee3@acme.com"),
        ]:
            self.stdout.write(f"{role:<20} {email}")
        self.stdout.write("-" * 80)
        self.stdout.write("\n✓ Run: python manage.py runserver")
        self.stdout.write("✓ Access: http://127.0.0.1:8000/")
        self.stdout.write("=" * 80)
