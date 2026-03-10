"""
Django management command to initialize default system settings
Usage: python manage.py init_settings
"""
from django.core.management.base import BaseCommand
from blu_core.settings_manager import initialize_default_settings


class Command(BaseCommand):
    help = 'Initialize default system settings'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Initializing System Settings ===\n'))
        
        created_count = initialize_default_settings()
        
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'✓ Created {created_count} default settings'))
        else:
            self.stdout.write('All default settings already exist')
        
        self.stdout.write(self.style.SUCCESS('\n=== Initialization Complete ===\n'))
