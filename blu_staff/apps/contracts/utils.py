"""
Utility functions for contract management
"""
from django.utils import timezone
from blu_staff.apps.contracts.models import EmployeeContract


def create_or_update_employee_contract(employee, employee_profile, created_by=None):
    """
    Create or update an employee contract based on employee profile data.
    This ensures contracts stay in sync with employee employment details.
    
    Args:
        employee: User instance (employee)
        employee_profile: EmployeeProfile instance
        created_by: User who created/updated the contract (optional)
    
    Returns:
        EmployeeContract instance
    """
    if not employee_profile.company:
        return None
    
    # Contract type mapping
    contract_type_mapping = {
        'PERMANENT': 'PERMANENT',
        'CONTRACT': 'FIXED_TERM',
        'PROBATION': 'PROBATION',
        'PART_TIME': 'PART_TIME',
        'CONSULTANT': 'CONSULTANT',
        'INTERN': 'INTERNSHIP',
    }
    contract_type = contract_type_mapping.get(employee_profile.employment_type, 'PERMANENT')
    
    # Try to get existing contract
    contract = EmployeeContract.objects.filter(employee=employee).first()
    
    if contract:
        # Update existing contract
        contract.job_title = employee_profile.job_title or 'Employee'
        contract.department = employee_profile.department or ''
        contract.start_date = employee_profile.date_hired or timezone.now().date()
        contract.end_date = employee_profile.contract_end_date
        contract.salary = employee_profile.salary
        contract.contract_type = contract_type
        contract.save()
        return contract
    
    # Generate contract number
    company = employee_profile.company
    year = timezone.now().year
    existing_count = EmployeeContract.objects.filter(
        company=company,
        created_at__year=year
    ).count()
    contract_number = f"CONT-{year}-{existing_count + 1:04d}"
    
    # Create new contract
    contract = EmployeeContract.objects.create(
        employee=employee,
        company=company,
        contract_number=contract_number,
        contract_type=contract_type,
        job_title=employee_profile.job_title or 'Employee',
        department=employee_profile.department or '',
        start_date=employee_profile.date_hired or timezone.now().date(),
        end_date=employee_profile.contract_end_date,
        salary=employee_profile.salary,
        currency='ZMW',
        salary_frequency='MONTHLY',
        working_hours_per_week=40.00,
        probation_period_months=3 if contract_type == 'PROBATION' else None,
        notice_period_days=30,
        status='ACTIVE' if contract_type != 'DRAFT' else 'DRAFT',
        created_by=created_by or employee,
        terms_and_conditions='Standard employment contract terms apply.',
    )
    
    return contract


def sync_contract_with_profile(employee_profile):
    """
    Sync contract dates and details with employee profile.
    Called when employee profile is updated.
    """
    try:
        contract = EmployeeContract.objects.filter(employee=employee_profile.user).first()
        if contract:
            contract.start_date = employee_profile.date_hired or contract.start_date
            contract.end_date = employee_profile.contract_end_date
            contract.job_title = employee_profile.job_title or contract.job_title
            contract.department = employee_profile.department or contract.department
            contract.salary = employee_profile.salary or contract.salary
            contract.save()
    except Exception:
        pass  # Silently fail if sync fails
