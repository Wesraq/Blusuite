from django.core.management.base import BaseCommand
from blu_assets.models import EmployeeAsset


class Command(BaseCommand):
    help = "Normalize asset statuses: set AVAILABLE where employee is null but status is ASSIGNED; clear assigned/return dates accordingly."

    def handle(self, *args, **options):
        updated = EmployeeAsset.objects.filter(employee__isnull=True, status='ASSIGNED').update(
            status='AVAILABLE', assigned_date=None, return_date=None
        )
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} assets to AVAILABLE where employee was null."))
