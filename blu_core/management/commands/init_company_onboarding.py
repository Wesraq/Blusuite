"""
Django management command to initialize company onboarding for existing companies
Usage: python manage.py init_company_onboarding
"""
from django.core.management.base import BaseCommand
from blu_staff.apps.accounts.models import Company
from blu_core.onboarding_automation import start_company_onboarding, create_default_onboarding_checklist


class Command(BaseCommand):
    help = 'Initialize company onboarding for existing companies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=str,
            help='Company name (omit to initialize all companies)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Initializing Company Onboarding ===\n'))
        
        if options['company']:
            try:
                companies = [Company.objects.get(name=options['company'])]
            except Company.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Company '{options['company']}' not found"))
                return
        else:
            companies = Company.objects.all()
        
        initialized = 0
        skipped = 0
        
        for company in companies:
            # Check if already has onboarding
            if hasattr(company, 'onboarding_progress'):
                self.stdout.write(f"  ⊘ {company.name} - Already initialized")
                skipped += 1
                continue
            
            # Get admin user
            admin = company.users.filter(role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']).first()
            if not admin:
                self.stdout.write(self.style.WARNING(f"  ⚠ {company.name} - No admin found"))
                continue
            
            # Initialize onboarding
            start_company_onboarding(company, admin)
            
            # Create default checklist if none exists
            from blu_staff.apps.onboarding.models import OnboardingChecklist
            if not OnboardingChecklist.objects.filter(tenant=company.tenant).exists():
                create_default_onboarding_checklist(company)
            
            self.stdout.write(self.style.SUCCESS(f"  ✓ {company.name} - Initialized"))
            initialized += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Complete ==='))
        self.stdout.write(f'Initialized: {initialized}')
        self.stdout.write(f'Skipped: {skipped}\n')
