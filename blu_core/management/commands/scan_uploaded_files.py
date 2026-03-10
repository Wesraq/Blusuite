"""
Django management command to scan uploaded files for viruses and validate integrity
Usage: python manage.py scan_uploaded_files
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from blu_staff.apps.documents.models import EmployeeDocument
from blu_core.secure_storage import scan_file_for_viruses, calculate_file_hash


class Command(BaseCommand):
    help = 'Scan uploaded files for viruses and validate integrity'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rescan-all',
            action='store_true',
            help='Rescan all files, not just unscanned ones',
        )
        parser.add_argument(
            '--quarantine',
            action='store_true',
            help='Quarantine infected files',
        )

    def handle(self, *args, **options):
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== File Scanning Started: {timestamp} ===\n'))
        
        # Get documents to scan
        if options['rescan_all']:
            documents = EmployeeDocument.objects.all()
            self.stdout.write(f'Scanning all {documents.count()} documents...\n')
        else:
            documents = EmployeeDocument.objects.filter(
                status__in=['PENDING', 'APPROVED']
            )
            self.stdout.write(f'Scanning {documents.count()} active documents...\n')
        
        scanned = 0
        infected = 0
        errors = 0
        
        for doc in documents:
            try:
                if not doc.file:
                    continue
                
                # Scan for viruses
                is_safe, threat_name = scan_file_for_viruses(doc.file)
                
                if is_safe:
                    self.stdout.write(f'  ✓ {doc.title} - Clean')
                    scanned += 1
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ {doc.title} - INFECTED: {threat_name}'))
                    infected += 1
                    
                    if options['quarantine']:
                        # Mark as rejected
                        doc.status = 'REJECTED'
                        doc.rejection_reason = f'Virus detected: {threat_name}'
                        doc.save()
                        self.stdout.write(self.style.WARNING(f'    → Quarantined'))
                
                # Validate file hash
                current_hash = calculate_file_hash(doc.file)
                if hasattr(doc, 'file_hash') and doc.file_hash and doc.file_hash != current_hash:
                    self.stdout.write(self.style.WARNING(f'  ⚠ {doc.title} - Hash mismatch (file modified)'))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {doc.title} - Error: {str(e)}'))
                errors += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Scanning Complete ==='))
        self.stdout.write(f'Scanned: {scanned}')
        self.stdout.write(self.style.ERROR(f'Infected: {infected}'))
        self.stdout.write(f'Errors: {errors}\n')
