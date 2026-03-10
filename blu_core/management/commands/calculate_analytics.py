"""
Django management command to calculate company analytics
Usage: python manage.py calculate_analytics
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from blu_staff.apps.accounts.models import Company
from blu_core.advanced_analytics import calculate_company_analytics
from datetime import date


class Command(BaseCommand):
    help = 'Calculate and store company analytics snapshots'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=str,
            help='Company name (omit to calculate for all companies)',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Snapshot date (YYYY-MM-DD, default: today)',
        )

    def handle(self, *args, **options):
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Analytics Calculation: {timestamp} ===\n'))
        
        # Get snapshot date
        if options['date']:
            snapshot_date = date.fromisoformat(options['date'])
        else:
            snapshot_date = date.today()
        
        self.stdout.write(f'Snapshot Date: {snapshot_date}\n')
        
        # Get companies
        if options['company']:
            try:
                companies = [Company.objects.get(name=options['company'])]
            except Company.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Company '{options['company']}' not found"))
                return
        else:
            companies = Company.objects.all()
        
        calculated = 0
        errors = 0
        
        for company in companies:
            try:
                analytics = calculate_company_analytics(company, snapshot_date)
                
                self.stdout.write(self.style.SUCCESS(f'  ✓ {company.name}'))
                self.stdout.write(f'    Employees: {analytics.total_employees}')
                self.stdout.write(f'    Turnover: {analytics.turnover_rate}%')
                self.stdout.write(f'    Attendance: {analytics.average_attendance_rate}%')
                
                calculated += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {company.name} - Error: {str(e)}'))
                errors += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Calculation Complete ==='))
        self.stdout.write(f'Calculated: {calculated}')
        self.stdout.write(f'Errors: {errors}\n')
