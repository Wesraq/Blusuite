# Generated migration to create contracts for existing employees

from django.db import migrations
from django.utils import timezone


def create_contracts_for_existing_employees(apps, schema_editor):
    """
    Create EmployeeContract records for all existing employees who don't have one.
    Uses data from EmployeeProfile to populate contract details.
    """
    User = apps.get_model('accounts', 'User')
    EmployeeProfile = apps.get_model('accounts', 'EmployeeProfile')
    EmployeeContract = apps.get_model('contracts', 'EmployeeContract')
    
    # Get all employees
    employees = User.objects.filter(role='EMPLOYEE')
    
    created_count = 0
    for employee in employees:
        # Skip if contract already exists
        if EmployeeContract.objects.filter(employee=employee).exists():
            continue
        
        # Get employee profile
        try:
            profile = EmployeeProfile.objects.get(user=employee)
        except EmployeeProfile.DoesNotExist:
            continue
        
        # Determine contract type from employment_type
        contract_type_mapping = {
            'PERMANENT': 'PERMANENT',
            'CONTRACT': 'FIXED_TERM',
            'PROBATION': 'PROBATION',
            'PART_TIME': 'PART_TIME',
            'CONSULTANT': 'CONSULTANT',
            'INTERN': 'INTERNSHIP',
        }
        contract_type = contract_type_mapping.get(profile.employment_type, 'PERMANENT')
        
        # Generate contract number
        company = profile.company
        year = timezone.now().year
        existing_count = EmployeeContract.objects.filter(
            employee__company=company,
            created_at__year=year
        ).count()
        contract_number = f"CONT-{year}-{existing_count + 1:04d}"
        
        # Create contract
        EmployeeContract.objects.create(
            employee=employee,
            company=company,
            contract_number=contract_number,
            contract_type=contract_type,
            job_title=profile.job_title or 'Employee',
            department=profile.department or '',
            start_date=profile.date_hired or timezone.now().date(),
            end_date=profile.contract_end_date,
            salary=profile.salary,
            currency='ZMW',
            salary_frequency='MONTHLY',
            working_hours_per_week=40.00,
            probation_period_months=3 if contract_type == 'PROBATION' else None,
            notice_period_days=30,
            status='ACTIVE',
            created_by=employee,  # Will be updated by admin later if needed
            terms_and_conditions='Standard employment contract terms apply.',
        )
        created_count += 1
    
    print(f"Created {created_count} contracts for existing employees")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - delete auto-created contracts.
    Note: This will only delete contracts created by this migration.
    """
    # We don't actually reverse this as it would delete legitimate data
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0001_initial'),
        ('accounts', '0058_add_office_location_name'),
    ]

    operations = [
        migrations.RunPython(create_contracts_for_existing_employees, reverse_migration),
    ]
