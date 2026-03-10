# BluSuite Secure File Storage Setup Guide

## Overview
Enterprise-grade secure file storage with encryption at rest, virus scanning, signed URLs, and cloud storage integration.

---

## Security Features Implemented

### 1. File Encryption at Rest

**Implementation:** `blu_core/secure_storage.py` - `SecureFileStorage`

**Features:**
- AES-256 encryption using Fernet (symmetric encryption)
- PBKDF2 key derivation from secret key
- Transparent encryption/decryption on save/read
- No application code changes required

**Configuration:**
```python
# settings_production.py
ENABLE_FILE_ENCRYPTION = True
FILE_ENCRYPTION_KEY = env('FILE_ENCRYPTION_KEY')  # Store in .env
```

### 2. Virus Scanning

**Implementation:** `blu_core/secure_storage.py` - `scan_file_for_viruses()`

**Features:**
- ClamAV integration via pyclamd
- Real-time scanning on upload
- Quarantine infected files
- Scheduled batch scanning

**Configuration:**
```python
# settings_production.py
ENABLE_VIRUS_SCANNING = True
```

### 3. File Type Validation

**Implementation:** `blu_core/secure_storage.py` - `validate_file_type()`

**Features:**
- Magic byte validation (not just extension)
- Prevents file type spoofing
- Configurable allowed types
- MIME type verification

### 4. Secure Download URLs

**Implementation:** `blu_core/secure_storage.py` - `create_signed_url()`

**Features:**
- Time-limited signed URLs
- Token-based authentication
- Prevents direct file access
- Configurable expiry (default 1 hour)

### 5. Storage Quota Management

**Implementation:** `blu_core/secure_storage.py` - `check_storage_quota()`

**Features:**
- Per-company storage limits
- Real-time usage tracking
- Quota enforcement on upload
- Usage reporting

### 6. File Integrity

**Implementation:** `blu_core/secure_storage.py` - `calculate_file_hash()`

**Features:**
- SHA-256 hash calculation
- Tamper detection
- Integrity verification
- Audit trail

---

## Deployment Steps

### Step 1: Install Dependencies

```bash
cd /opt/blusuite
source venv/bin/activate
pip install cryptography python-magic pyclamd
```

### Step 2: Install ClamAV (Virus Scanner)

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install clamav clamav-daemon
sudo systemctl start clamav-daemon
sudo systemctl enable clamav-daemon

# Update virus definitions
sudo freshclam
```

**CentOS/RHEL:**
```bash
sudo yum install clamav clamav-update
sudo systemctl start clamd@scan
sudo systemctl enable clamd@scan
sudo freshclam
```

**Verify ClamAV:**
```bash
clamdscan --version
systemctl status clamav-daemon
```

### Step 3: Configure Settings

**Add to `.env`:**
```env
# File Storage Security
ENABLE_FILE_ENCRYPTION=True
FILE_ENCRYPTION_KEY=your-secure-random-key-here
ENABLE_VIRUS_SCANNING=True

# Storage Quotas (bytes)
DEFAULT_STORAGE_QUOTA=10737418240  # 10GB

# File Upload Limits
MAX_FILE_SIZE=10485760  # 10MB
```

**Generate Encryption Key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Update `settings_production.py`:**
```python
from decouple import config

# File Storage Security
ENABLE_FILE_ENCRYPTION = config('ENABLE_FILE_ENCRYPTION', default=False, cast=bool)
FILE_ENCRYPTION_KEY = config('FILE_ENCRYPTION_KEY', default=SECRET_KEY)
ENABLE_VIRUS_SCANNING = config('ENABLE_VIRUS_SCANNING', default=False, cast=bool)

# Storage Backend
FILE_STORAGE_BACKEND = config('FILE_STORAGE_BACKEND', default='local')  # 'local', 's3', 'azure'

# Storage Quotas
DEFAULT_STORAGE_QUOTA = config('DEFAULT_STORAGE_QUOTA', default=10737418240, cast=int)

# File Upload
MAX_FILE_SIZE = config('MAX_FILE_SIZE', default=10485760, cast=int)
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_FILE_SIZE
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_FILE_SIZE
```

### Step 4: Update Document Model

**Add to `blu_staff/apps/documents/models.py`:**
```python
class EmployeeDocument(TenantScopedModel):
    # ... existing fields ...
    
    # Add security fields
    file_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 hash")
    virus_scanned = models.BooleanField(default=False)
    virus_scan_result = models.CharField(max_length=100, blank=True)
    is_encrypted = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if self.file:
            from blu_core.secure_storage import calculate_file_hash, scan_file_for_viruses
            
            # Calculate hash
            self.file_hash = calculate_file_hash(self.file)
            
            # Scan for viruses
            is_safe, threat_name = scan_file_for_viruses(self.file)
            self.virus_scanned = True
            self.virus_scan_result = threat_name or 'Clean'
            
            if not is_safe:
                raise ValidationError(f"Virus detected: {threat_name}")
            
            # Mark as encrypted if enabled
            from django.conf import settings
            self.is_encrypted = getattr(settings, 'ENABLE_FILE_ENCRYPTION', False)
        
        super().save(*args, **kwargs)
```

**Create Migration:**
```bash
python manage.py makemigrations documents
python manage.py migrate documents --settings=ems_project.settings_production
```

### Step 5: Test File Upload

**Test Encryption:**
```python
from django.core.files.base import ContentFile
from blu_staff.apps.documents.models import EmployeeDocument
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.filter(role='EMPLOYEE').first()

# Upload test file
doc = EmployeeDocument.objects.create(
    employee=user,
    title='Test Document',
    document_type='OTHER',
    file=ContentFile(b'Test content', name='test.txt')
)

print(f"File hash: {doc.file_hash}")
print(f"Virus scanned: {doc.virus_scanned}")
print(f"Encrypted: {doc.is_encrypted}")
```

### Step 6: Setup Scheduled Scanning

**Create Cron Script:**
```bash
#!/bin/bash
# /opt/blusuite/scripts/cron_file_scanning.sh

cd /opt/blusuite
source venv/bin/activate

# Scan all uploaded files
python manage.py scan_uploaded_files --quarantine --settings=ems_project.settings_production >> /var/log/blusuite/file_scanning.log 2>&1

deactivate
```

**Make Executable:**
```bash
chmod +x /opt/blusuite/scripts/cron_file_scanning.sh
```

**Add to Crontab:**
```bash
crontab -e

# Scan files daily at 2 AM
0 2 * * * /opt/blusuite/scripts/cron_file_scanning.sh
```

### Step 7: Setup Storage Cleanup

**Add to Crontab:**
```bash
# Cleanup old files weekly (Sundays at 3 AM)
0 3 * * 0 /opt/blusuite/scripts/cron_storage_cleanup.sh
```

**Create Cleanup Script:**
```bash
#!/bin/bash
# /opt/blusuite/scripts/cron_storage_cleanup.sh

cd /opt/blusuite
source venv/bin/activate

python manage.py cleanup_storage --days=90 --settings=ems_project.settings_production >> /var/log/blusuite/storage_cleanup.log 2>&1

deactivate
```

---

## Cloud Storage Integration

### AWS S3 Setup

**Install boto3:**
```bash
pip install boto3 django-storages
```

**Configure `.env`:**
```env
FILE_STORAGE_BACKEND=s3
AWS_STORAGE_BUCKET_NAME=blusuite-documents
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_REGION_NAME=us-east-1
```

**Update `settings_production.py`:**
```python
if FILE_STORAGE_BACKEND == 's3':
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = 'private'
    AWS_S3_ENCRYPTION = True  # Server-side encryption
```

**S3 Bucket Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:user/blusuite"
      },
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::blusuite-documents/*"
    }
  ]
}
```

### Azure Blob Storage Setup

**Install azure-storage:**
```bash
pip install django-storages[azure]
```

**Configure `.env`:**
```env
FILE_STORAGE_BACKEND=azure
AZURE_ACCOUNT_NAME=blusuite
AZURE_ACCOUNT_KEY=your_account_key
AZURE_CONTAINER=documents
```

**Update `settings_production.py`:**
```python
if FILE_STORAGE_BACKEND == 'azure':
    DEFAULT_FILE_STORAGE = 'storages.backends.azure_storage.AzureStorage'
    AZURE_ACCOUNT_NAME = config('AZURE_ACCOUNT_NAME')
    AZURE_ACCOUNT_KEY = config('AZURE_ACCOUNT_KEY')
    AZURE_CONTAINER = config('AZURE_CONTAINER')
```

---

## Usage Examples

### Upload File with Security Checks

```python
from blu_core.secure_storage import (
    validate_file_type,
    scan_file_for_viruses,
    check_storage_quota,
    generate_secure_filename,
    calculate_file_hash
)

def upload_document(request):
    file = request.FILES.get('file')
    user = request.user
    company = user.company
    
    # 1. Validate file type
    is_valid, error = validate_file_type(file)
    if not is_valid:
        return JsonResponse({'error': error}, status=400)
    
    # 2. Check storage quota
    has_quota, current_usage, quota_limit = check_storage_quota(company, file.size)
    if not has_quota:
        return JsonResponse({
            'error': 'Storage quota exceeded',
            'current_usage': current_usage,
            'quota_limit': quota_limit
        }, status=400)
    
    # 3. Scan for viruses
    is_safe, threat_name = scan_file_for_viruses(file)
    if not is_safe:
        return JsonResponse({'error': f'Virus detected: {threat_name}'}, status=400)
    
    # 4. Generate secure filename
    secure_name = generate_secure_filename(file.name, user.id, company.id)
    
    # 5. Calculate hash
    file_hash = calculate_file_hash(file)
    
    # 6. Save document
    doc = EmployeeDocument.objects.create(
        employee=user,
        title=request.POST.get('title'),
        file=file,
        file_hash=file_hash,
        virus_scanned=True,
        virus_scan_result='Clean'
    )
    
    return JsonResponse({'id': doc.id, 'message': 'Upload successful'})
```

### Download File with Signed URL

```python
from blu_core.secure_storage import create_signed_url, verify_signed_url
from django.http import FileResponse

def generate_download_link(request, document_id):
    """Generate secure download link"""
    doc = EmployeeDocument.objects.get(id=document_id)
    
    # Check permissions
    if not can_access_document(request.user, doc):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Create signed URL
    token, expires_at = create_signed_url(doc.file.name, expires_in_seconds=3600)
    
    download_url = f"/documents/download/{token}/"
    
    return JsonResponse({
        'download_url': download_url,
        'expires_at': expires_at.isoformat()
    })


def download_file(request, token):
    """Download file using signed URL"""
    # Verify token
    is_valid, file_path = verify_signed_url(token, max_age=3600)
    
    if not is_valid:
        return JsonResponse({'error': file_path}, status=403)
    
    # Get document
    doc = EmployeeDocument.objects.get(file=file_path)
    
    # Log access
    DocumentAccessLog.objects.create(
        document=doc,
        user=request.user,
        access_type='DOWNLOAD',
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Return file
    return FileResponse(doc.file.open('rb'), as_attachment=True, filename=doc.original_filename)
```

---

## Monitoring & Maintenance

### Check Storage Usage

```python
from blu_staff.apps.documents.models import EmployeeDocument
from django.db.models import Sum

# Per company
company_usage = EmployeeDocument.objects.filter(
    employee__company=company
).aggregate(
    total_size=Sum('file_size'),
    total_files=Count('id')
)

print(f"Total files: {company_usage['total_files']}")
print(f"Total size: {company_usage['total_size'] / (1024**3):.2f} GB")

# System-wide
total_usage = EmployeeDocument.objects.aggregate(
    total_size=Sum('file_size')
)['total_size']

print(f"System-wide: {total_usage / (1024**3):.2f} GB")
```

### Scan All Files

```bash
# Scan all files
python manage.py scan_uploaded_files --rescan-all --settings=ems_project.settings_production

# Scan and quarantine
python manage.py scan_uploaded_files --quarantine --settings=ems_project.settings_production
```

### Cleanup Old Files

```bash
# Dry run (see what would be deleted)
python manage.py cleanup_storage --days=90 --dry-run --settings=ems_project.settings_production

# Actually delete
python manage.py cleanup_storage --days=90 --settings=ems_project.settings_production
```

### Monitor ClamAV

```bash
# Check status
systemctl status clamav-daemon

# View logs
tail -f /var/log/clamav/clamav.log

# Update virus definitions
sudo freshclam

# Test scanning
clamdscan /path/to/test/file
```

---

## Security Best Practices

### 1. Encryption Key Management

**DO:**
- Store encryption key in environment variable
- Use different keys for dev/staging/production
- Rotate keys periodically (with re-encryption)
- Use secrets manager (AWS Secrets Manager, Azure Key Vault)

**DON'T:**
- Hardcode keys in settings.py
- Commit keys to version control
- Share keys via email/chat

### 2. Virus Scanning

**DO:**
- Update virus definitions daily
- Scan files on upload AND periodically
- Quarantine infected files immediately
- Alert admins of infections

**DON'T:**
- Skip scanning for "trusted" users
- Allow uploads if ClamAV is down
- Delete infected files without logging

### 3. Access Control

**DO:**
- Use signed URLs for downloads
- Log all file access
- Implement per-document permissions
- Expire download links

**DON'T:**
- Serve files directly from media folder
- Allow directory listing
- Use predictable file paths

### 4. Storage Quotas

**DO:**
- Enforce quotas per company
- Monitor usage trends
- Alert when approaching limits
- Provide usage reports

**DON'T:**
- Allow unlimited uploads
- Ignore quota violations
- Delete files without warning

---

## Troubleshooting

### Encryption Issues

**Problem:** Files not encrypting

**Solution:**
```bash
# Check settings
python manage.py shell
>>> from django.conf import settings
>>> settings.ENABLE_FILE_ENCRYPTION
True

# Verify encryption key
>>> settings.FILE_ENCRYPTION_KEY
'your-key-here'
```

### ClamAV Not Working

**Problem:** Virus scanning fails

**Solution:**
```bash
# Check ClamAV is running
systemctl status clamav-daemon

# Test connection
python -c "import pyclamd; cd = pyclamd.ClamdUnixSocket(); print(cd.ping())"

# Update definitions
sudo freshclam

# Restart daemon
sudo systemctl restart clamav-daemon
```

### Storage Quota Exceeded

**Problem:** Users can't upload files

**Solution:**
```python
# Check current usage
from blu_core.secure_storage import check_storage_quota

has_quota, current, limit = check_storage_quota(company, 0)
print(f"Used: {current / (1024**3):.2f} GB / {limit / (1024**3):.2f} GB")

# Increase quota
company.storage_quota_bytes = 20 * 1024 * 1024 * 1024  # 20GB
company.save()

# Or cleanup old files
python manage.py cleanup_storage --days=30
```

### File Download Fails

**Problem:** Signed URL expired or invalid

**Solution:**
```python
# Regenerate link
from blu_core.secure_storage import create_signed_url

token, expires_at = create_signed_url(doc.file.name, expires_in_seconds=7200)  # 2 hours
```

---

## Migration from Unencrypted Storage

### Step 1: Backup All Files

```bash
# Backup media folder
tar -czf media_backup_$(date +%Y%m%d).tar.gz /opt/blusuite/media/
```

### Step 2: Enable Encryption

```env
ENABLE_FILE_ENCRYPTION=True
FILE_ENCRYPTION_KEY=your-new-key
```

### Step 3: Re-encrypt Existing Files

```python
from blu_staff.apps.documents.models import EmployeeDocument
from blu_core.secure_storage import SecureFileStorage

storage = SecureFileStorage()

for doc in EmployeeDocument.objects.all():
    if doc.file and not doc.is_encrypted:
        # Read unencrypted file
        old_file = doc.file.read()
        
        # Save with encryption
        doc.file.save(doc.file.name, ContentFile(old_file), save=False)
        doc.is_encrypted = True
        doc.save()
        
        print(f"Encrypted: {doc.title}")
```

---

**Document Version:** 1.0  
**Last Updated:** March 10, 2026  
**Next Review:** June 10, 2026
