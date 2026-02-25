from django.core.management.base import BaseCommand
from blu_billing.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Create default subscription plans'

    def handle(self, *args, **options):
        plans_data = [
            {
                'name': 'Starter',
                'plan_type': 'BASIC',
                'description': 'Perfect for small businesses getting started with HR management',
                'monthly_price': 19.99,
                'yearly_price': 199.99,
                'max_users': 50,
                'max_storage_gb': 10,
                'features': [
                    'Core HR Management',
                    'Employee Database',
                    'Basic Reporting',
                    'Email Support'
                ]
            },
            {
                'name': 'Professional',
                'plan_type': 'PROFESSIONAL',
                'description': 'Advanced features for growing businesses with comprehensive HR tools',
                'monthly_price': 29.99,
                'yearly_price': 299.99,
                'max_users': 500,
                'max_storage_gb': 50,
                'features': [
                    'Everything in Starter',
                    'Advanced Analytics',
                    'Performance Management',
                    'Asset Management',
                    'E-Forms & Signatures',
                    'Priority Support'
                ]
            },
            {
                'name': 'Enterprise',
                'plan_type': 'ENTERPRISE',
                'description': 'Complete solution for large organizations with custom workflows',
                'monthly_price': 99.99,
                'yearly_price': 999.99,
                'max_users': 5000,
                'max_storage_gb': 500,
                'features': [
                    'Everything in Professional',
                    'Custom Workflows',
                    'API Access',
                    'Dedicated Account Manager',
                    'Custom Integrations',
                    '24/7 Phone Support'
                ]
            }
        ]

        created_count = 0
        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.get_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created plan: {plan.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Plan already exists: {plan.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} new subscription plans')
        )
