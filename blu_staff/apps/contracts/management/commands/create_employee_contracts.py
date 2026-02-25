from django.core.management.base import BaseCommand
from django.utils import timezone
from blu_staff.apps.accounts.models import User, EmployeeProfile
from blu_staff.apps.contracts.models import EmployeeContract


class Command(BaseCommand):
    help = 'Create contracts for all existing employees who do not have one'

    def handle(self, *args, **options):
        employees = User.objects.filter(role='EMPLOYEE')
        created_count = 0
        skipped_count = 0
        
        for employee in employees:
            # Skip if contract already exists
            if EmployeeContract.objects.filter(employee=employee).exists():
                skipped_count += 1
                continue
            
            # Get employee profile
            try:
                profile = employee.employee_profile
            except (AttributeError, EmployeeProfile.DoesNotExist):
                self.stdout.write(self.style.WARNING(f'No profile for {employee.email}, skipping'))
                skipped_count += 1
                continue
            
            if not profile.company:
                self.stdout.write(self.style.WARNING(f'No company for {employee.email}, skipping'))
                skipped_count += 1
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
                company=company,
                created_at__year=year
            ).count()
            contract_number = f"CONT-{year}-{existing_count + 1:04d}"
            
            # Create contract
            try:
                contract = EmployeeContract.objects.create(
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
                    created_by=employee,
                    terms_and_conditions='Standard employment contract terms apply.',
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created contract {contract_number} for {employee.get_full_name()}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating contract for {employee.email}: {str(e)}'))
                skipped_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\nSummary: Created {created_count} contracts, skipped {skipped_count}'))
