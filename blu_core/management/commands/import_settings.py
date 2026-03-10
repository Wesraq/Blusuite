"""
Django management command to import settings from JSON
Usage: python manage.py import_settings --input settings.json --company "Company Name"
"""
from django.core.management.base import BaseCommand
from blu_core.settings_manager import import_settings
from blu_staff.apps.accounts.models import Company
from django.contrib.auth import get_user_model
import json


User = get_user_model()


class Command(BaseCommand):
    help = 'Import settings from JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            required=True,
            help='Input JSON file path',
        )
        parser.add_argument(
            '--company',
            type=str,
            help='Company name to import settings for (omit for system-wide)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing settings',
        )

    def handle(self, *args, **options):
        company = None
        if options['company']:
            try:
                company = Company.objects.get(name=options['company'])
                self.stdout.write(f"Importing settings for: {company.name}")
            except Company.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Company '{options['company']}' not found"))
                return
        else:
            self.stdout.write("Importing system-wide settings")
        
        # Read import file
        input_file = options['input']
        try:
            with open(input_file, 'r') as f:
                import_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"File '{input_file}' not found"))
            return
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f"Invalid JSON in '{input_file}'"))
            return
        
        # Import settings
        result = import_settings(
            import_data,
            company=company,
            user=None,
            overwrite=options['overwrite']
        )
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Import Complete ==='))
        self.stdout.write(self.style.SUCCESS(f"Imported: {result['imported']}"))
        self.stdout.write(f"Skipped: {result['skipped']}")
        
        if result['errors']:
            self.stdout.write(self.style.ERROR(f"\nErrors ({len(result['errors'])}):"))
            for error in result['errors']:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
        
        self.stdout.write('')
