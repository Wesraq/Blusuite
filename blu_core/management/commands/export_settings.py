"""
Django management command to export settings to JSON
Usage: python manage.py export_settings --company "Company Name" --output settings.json
"""
from django.core.management.base import BaseCommand
from blu_core.settings_manager import export_settings
from blu_staff.apps.accounts.models import Company
import json


class Command(BaseCommand):
    help = 'Export settings to JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=str,
            help='Company name to export settings for (omit for system-wide)',
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Category to export (omit for all categories)',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='settings_export.json',
            help='Output file path',
        )

    def handle(self, *args, **options):
        company = None
        if options['company']:
            try:
                company = Company.objects.get(name=options['company'])
                self.stdout.write(f"Exporting settings for: {company.name}")
            except Company.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Company '{options['company']}' not found"))
                return
        else:
            self.stdout.write("Exporting system-wide settings")
        
        category = options['category']
        if category:
            self.stdout.write(f"Category: {category}")
        
        # Export settings
        export_data = export_settings(company, category)
        
        # Write to file
        output_file = options['output']
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        settings_count = len(export_data.get('settings', {}))
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Exported {settings_count} settings to {output_file}\n'))
