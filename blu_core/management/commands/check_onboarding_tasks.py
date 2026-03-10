"""
Django management command to check overdue onboarding tasks and send reminders
Usage: python manage.py check_onboarding_tasks
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from blu_core.onboarding_automation import check_overdue_onboarding_tasks


class Command(BaseCommand):
    help = 'Check for overdue onboarding tasks and send reminders'

    def handle(self, *args, **options):
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Onboarding Task Check: {timestamp} ===\n'))
        
        overdue_count = check_overdue_onboarding_tasks()
        
        if overdue_count > 0:
            self.stdout.write(self.style.WARNING(f'Found {overdue_count} overdue tasks'))
            self.stdout.write('Reminders sent to employees')
        else:
            self.stdout.write(self.style.SUCCESS('No overdue tasks found'))
        
        self.stdout.write(self.style.SUCCESS('\n=== Check Complete ===\n'))
