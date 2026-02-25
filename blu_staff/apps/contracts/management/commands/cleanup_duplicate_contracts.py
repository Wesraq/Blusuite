from django.core.management.base import BaseCommand
from blu_staff.apps.contracts.models import EmployeeContract
from django.db.models import Count


class Command(BaseCommand):
    help = 'Clean up duplicate active contracts - keep only the latest one per employee'

    def handle(self, *args, **options):
        self.stdout.write('Starting duplicate contract cleanup...\n')
        
        # Find employees with multiple active contracts
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        employees_with_duplicates = []
        
        for employee in User.objects.all():
            active_contracts = EmployeeContract.objects.filter(
                employee=employee,
                status='ACTIVE'
            ).order_by('-created_at')
            
            if active_contracts.count() > 1:
                employees_with_duplicates.append({
                    'employee': employee,
                    'contracts': list(active_contracts)
                })
        
        if not employees_with_duplicates:
            self.stdout.write(self.style.SUCCESS('No duplicate contracts found!'))
            return
        
        self.stdout.write(f'Found {len(employees_with_duplicates)} employees with duplicate active contracts\n')
        
        for item in employees_with_duplicates:
            employee = item['employee']
            contracts = item['contracts']
            
            # Keep the latest contract (first in list due to ordering)
            latest_contract = contracts[0]
            older_contracts = contracts[1:]
            
            self.stdout.write(f'\nEmployee: {employee.get_full_name()}')
            self.stdout.write(f'  Keeping: {latest_contract.contract_number} (ID: {latest_contract.id}) - Created: {latest_contract.created_at}')
            
            # Mark older contracts as EXPIRED
            for old_contract in older_contracts:
                old_contract.status = 'EXPIRED'
                old_contract.save()
                self.stdout.write(f'  Expired: {old_contract.contract_number} (ID: {old_contract.id}) - Created: {old_contract.created_at}')
        
        self.stdout.write(self.style.SUCCESS(f'\nCleanup complete! Processed {len(employees_with_duplicates)} employees'))
