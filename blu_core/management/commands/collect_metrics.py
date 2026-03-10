"""
Django management command to collect system metrics and run health checks
Usage: python manage.py collect_metrics
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from blu_core.monitoring import (
    collect_system_metrics,
    run_health_checks,
    check_alert_rules,
    cleanup_old_metrics,
    cleanup_old_health_checks,
)


class Command(BaseCommand):
    help = 'Collect system metrics, run health checks, and check alert rules'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Also cleanup old metrics and health checks',
        )

    def handle(self, *args, **options):
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Metric Collection Started: {timestamp} ===\n'))
        
        # Collect system metrics
        self.stdout.write('Collecting system metrics...')
        metrics_count = collect_system_metrics()
        self.stdout.write(self.style.SUCCESS(f'  ✓ Collected {metrics_count} metrics'))
        
        # Run health checks
        self.stdout.write('\nRunning health checks...')
        health_checks = run_health_checks()
        healthy = sum(1 for c in health_checks if c.status == 'HEALTHY')
        self.stdout.write(self.style.SUCCESS(f'  ✓ Completed {len(health_checks)} checks ({healthy} healthy)'))
        
        for check in health_checks:
            status_style = self.style.SUCCESS if check.status == 'HEALTHY' else self.style.ERROR
            self.stdout.write(f'    - {check.check_name}: {status_style(check.status)} ({check.response_time_ms}ms)')
        
        # Check alert rules
        self.stdout.write('\nChecking alert rules...')
        alerts = check_alert_rules()
        if alerts:
            self.stdout.write(self.style.WARNING(f'  ⚠ Triggered {len(alerts)} alert(s)'))
            for alert in alerts:
                self.stdout.write(f'    - {alert.severity}: {alert.message}')
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ No alerts triggered'))
        
        # Cleanup if requested
        if options['cleanup']:
            self.stdout.write('\nCleaning up old data...')
            deleted_metrics = cleanup_old_metrics(days=30)
            deleted_checks = cleanup_old_health_checks(days=7)
            self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted {deleted_metrics} old metrics'))
            self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted {deleted_checks} old health checks'))
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Metric Collection Completed ===\n'))
