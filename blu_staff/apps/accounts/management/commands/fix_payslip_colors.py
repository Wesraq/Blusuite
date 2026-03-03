from django.core.management.base import BaseCommand
from blu_staff.apps.accounts.models import Company


class Command(BaseCommand):
    help = 'Update all companies to use brand crimson colors for payslips instead of blue'

    def handle(self, *args, **options):
        companies = Company.objects.all()
        updated_count = 0
        
        for company in companies:
            updated = False
            
            # Replace old blue header colors with brand crimson
            if company.payslip_header_color in ['#3b82f6', '#2563eb', '#1e3a8a', '#4472c4']:
                company.payslip_header_color = '#DC143C'
                updated = True
            
            # Replace old green/teal accent colors with brand crimson
            if company.payslip_accent_color in ['#10b981', '#059669', '#1a5f6b', '#0ea5e9']:
                company.payslip_accent_color = '#DC143C'
                updated = True
            
            # Replace old blue section colors with brand light pink
            if company.payslip_section_color in ['#C5D9F1', '#dce6f1', '#e8f5f7', '#eff6ff']:
                company.payslip_section_color = '#DC143C'
                updated = True
            
            if updated:
                company.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Updated {company.name} (ID: {company.id})')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nTotal companies updated: {updated_count}')
        )
