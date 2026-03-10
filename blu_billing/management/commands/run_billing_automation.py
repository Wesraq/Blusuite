"""
Django management command to run billing automation tasks
Usage: python manage.py run_billing_automation [--task=TASK_NAME]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from blu_billing.billing_automation import (
    generate_monthly_invoices,
    process_trial_expirations,
    send_trial_expiry_warnings,
    process_overdue_invoices,
    update_usage_metrics,
)


class Command(BaseCommand):
    help = 'Run billing automation tasks (invoices, trials, usage tracking)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            help='Specific task to run: invoices, trials, warnings, overdue, usage, or all (default)',
            default='all'
        )

    def handle(self, *args, **options):
        task = options['task']
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Billing Automation Started: {timestamp} ===\n'))
        
        if task in ['all', 'invoices']:
            self.stdout.write('Running: Generate Monthly Invoices...')
            results = generate_monthly_invoices()
            self.stdout.write(self.style.SUCCESS(
                f'  ✓ Generated: {results["generated"]}, Skipped: {results["skipped"]}, Errors: {len(results["errors"])}'
            ))
            if results['errors']:
                for error in results['errors']:
                    self.stdout.write(self.style.ERROR(f'    - {error["company"]}: {error["error"]}'))
        
        if task in ['all', 'trials']:
            self.stdout.write('\nRunning: Process Trial Expirations...')
            results = process_trial_expirations()
            self.stdout.write(self.style.SUCCESS(
                f'  ✓ Converted: {results["converted"]}, Suspended: {results["suspended"]}, Errors: {len(results["errors"])}'
            ))
            if results['errors']:
                for error in results['errors']:
                    self.stdout.write(self.style.ERROR(f'    - {error["company"]}: {error["error"]}'))
        
        if task in ['all', 'warnings']:
            self.stdout.write('\nRunning: Send Trial Expiry Warnings...')
            results = send_trial_expiry_warnings()
            self.stdout.write(self.style.SUCCESS(f'  ✓ Notified: {results["notified"]} companies'))
        
        if task in ['all', 'overdue']:
            self.stdout.write('\nRunning: Process Overdue Invoices...')
            results = process_overdue_invoices()
            self.stdout.write(self.style.SUCCESS(
                f'  ✓ Marked Overdue: {results["marked_overdue"]}, Suspended: {results["suspended"]}'
            ))
        
        if task in ['all', 'usage']:
            self.stdout.write('\nRunning: Update Usage Metrics...')
            results = update_usage_metrics()
            self.stdout.write(self.style.SUCCESS(f'  ✓ Updated: {results["updated"]} subscriptions'))
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Billing Automation Completed ===\n'))
