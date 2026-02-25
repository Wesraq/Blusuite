from django.core.management.base import BaseCommand
from django.utils import timezone
from blu_staff.apps.accounts.models import Company, CompanyRegistrationRequest, User, EmployerProfile

class Command(BaseCommand):
    help = 'Reset all approved companies to unapproved status for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm the reset operation',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This will reset ALL approved companies to unapproved status.\n'
                    'Use --confirm to proceed.'
                )
            )
            return

        # Get all approved companies
        approved_companies = Company.objects.filter(is_approved=True)

        if not approved_companies.exists():
            self.stdout.write(
                self.style.WARNING('No approved companies found.')
            )
            return

        count = approved_companies.count()
        self.stdout.write(
            self.style.WARNING(f'Found {count} approved companies to reset.')
        )

        # Reset each company
        for company in approved_companies:
            company.is_approved = False
            company.is_active = False
            company.approved_by = None
            company.approved_at = None
            company.save()

            # Also reset the associated registration request if it exists
            if hasattr(company, 'registration_request') and company.registration_request:
                reg_request = company.registration_request
                reg_request.status = 'PENDING'
                reg_request.reviewed_by = None
                reg_request.reviewed_at = None
                reg_request.review_notes = ''
                reg_request.save()

        # Delete employer user accounts for these companies
        employer_users = User.objects.filter(
            company__in=approved_companies,
            role='ADMINISTRATOR'
        )

        employer_count = employer_users.count()
        if employer_count > 0:
            employer_users.delete()

        # Delete employer profiles
        EmployerProfile.objects.filter(
            company__in=approved_companies
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully reset {count} companies to unapproved status.\n'
                f'Deleted {employer_count} employer accounts.'
            )
        )
