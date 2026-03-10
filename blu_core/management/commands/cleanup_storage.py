"""
Django management command to cleanup old files and free storage space
Usage: python manage.py cleanup_storage
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from blu_core.secure_storage import cleanup_old_files


class Command(BaseCommand):
    help = 'Cleanup old expired documents and temporary files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete files older than this many days (default: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        days = options['days']
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Storage Cleanup Started: {timestamp} ===\n'))
        self.stdout.write(f'Cleaning up files older than {days} days...\n')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be deleted\n'))
        
        # Cleanup old files
        deleted_count, freed_space = cleanup_old_files(days=days)
        
        # Format freed space
        freed_mb = freed_space / (1024 * 1024)
        freed_gb = freed_space / (1024 * 1024 * 1024)
        
        if freed_gb >= 1:
            freed_str = f'{freed_gb:.2f} GB'
        else:
            freed_str = f'{freed_mb:.2f} MB'
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Cleanup Complete ==='))
        self.stdout.write(f'Files deleted: {deleted_count}')
        self.stdout.write(f'Space freed: {freed_str}\n')
