"""
Django management command to setup default alert rules
Usage: python manage.py setup_default_alerts
"""
from django.core.management.base import BaseCommand
from blu_core.monitoring import AlertRule, SystemMetric


class Command(BaseCommand):
    help = 'Setup default alert rules for system monitoring'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Setting Up Default Alert Rules ===\n'))
        
        default_rules = [
            {
                'name': 'High CPU Usage',
                'metric_type': SystemMetric.MetricType.CPU,
                'threshold': 80.0,
                'duration_minutes': 5,
                'severity': AlertRule.Severity.WARNING,
                'cooldown_minutes': 30,
            },
            {
                'name': 'Critical CPU Usage',
                'metric_type': SystemMetric.MetricType.CPU,
                'threshold': 95.0,
                'duration_minutes': 2,
                'severity': AlertRule.Severity.CRITICAL,
                'cooldown_minutes': 15,
            },
            {
                'name': 'High Memory Usage',
                'metric_type': SystemMetric.MetricType.MEMORY,
                'threshold': 85.0,
                'duration_minutes': 5,
                'severity': AlertRule.Severity.WARNING,
                'cooldown_minutes': 30,
            },
            {
                'name': 'Critical Memory Usage',
                'metric_type': SystemMetric.MetricType.MEMORY,
                'threshold': 95.0,
                'duration_minutes': 2,
                'severity': AlertRule.Severity.CRITICAL,
                'cooldown_minutes': 15,
            },
            {
                'name': 'High Disk Usage',
                'metric_type': SystemMetric.MetricType.DISK,
                'threshold': 85.0,
                'duration_minutes': 10,
                'severity': AlertRule.Severity.WARNING,
                'cooldown_minutes': 60,
            },
            {
                'name': 'Critical Disk Usage',
                'metric_type': SystemMetric.MetricType.DISK,
                'threshold': 95.0,
                'duration_minutes': 5,
                'severity': AlertRule.Severity.CRITICAL,
                'cooldown_minutes': 30,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for rule_data in default_rules:
            rule, created = AlertRule.objects.get_or_create(
                name=rule_data['name'],
                defaults=rule_data
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {rule.name}'))
                created_count += 1
            else:
                # Update existing rule
                for key, value in rule_data.items():
                    setattr(rule, key, value)
                rule.save()
                self.stdout.write(f'  - Updated: {rule.name}')
                updated_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Summary ==='))
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count} rules'))
        self.stdout.write(f'Updated: {updated_count} rules')
        self.stdout.write(self.style.SUCCESS(f'Total: {AlertRule.objects.count()} active rules\n'))
