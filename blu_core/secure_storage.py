"""
Secure File Storage for BluSuite
Handles file encryption, virus scanning, secure URLs, and cloud storage integration
"""
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import hashlib
import os
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
import base64


class SecureFileStorage(FileSystemStorage):
    """
    Custom file storage backend with encryption at rest
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption_key = self._get_encryption_key()
    
    def _get_encryption_key(self):
        """Get or generate encryption key"""
        # In production, store this in environment variable or secrets manager
        secret_key = getattr(settings, 'FILE_ENCRYPTION_KEY', settings.SECRET_KEY)
        
        # Derive encryption key from secret
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'blusuite_file_encryption',  # Use unique salt per deployment
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return key
    
    def _encrypt_content(self, content):
        """Encrypt file content"""
        if not getattr(settings, 'ENABLE_FILE_ENCRYPTION', False):
            return content
        
        fernet = Fernet(self.encryption_key)
        
        # Read content
        if hasattr(content, 'read'):
            data = content.read()
            content.seek(0)
        else:
            data = content
        
        # Encrypt
        encrypted_data = fernet.encrypt(data)
        return ContentFile(encrypted_data)
    
    def _decrypt_content(self, content):
        """Decrypt file content"""
        if not getattr(settings, 'ENABLE_FILE_ENCRYPTION', False):
            return content
        
        fernet = Fernet(self.encryption_key)
        
        # Read encrypted content
        if hasattr(content, 'read'):
            encrypted_data = content.read()
            content.seek(0)
        else:
            encrypted_data = content
        
        # Decrypt
        decrypted_data = fernet.decrypt(encrypted_data)
        return ContentFile(decrypted_data)
    
    def _save(self, name, content):
        """Save file with encryption"""
        encrypted_content = self._encrypt_content(content)
        return super()._save(name, encrypted_content)
    
    def _open(self, name, mode='rb'):
        """Open file with decryption"""
        file = super()._open(name, mode)
        if 'r' in mode:
            return self._decrypt_content(file)
        return file


def calculate_file_hash(file):
    """Calculate SHA256 hash of file"""
    sha256 = hashlib.sha256()
    
    # Read file in chunks
    if hasattr(file, 'read'):
        file.seek(0)
        for chunk in iter(lambda: file.read(4096), b''):
            sha256.update(chunk)
        file.seek(0)
    else:
        sha256.update(file)
    
    return sha256.hexdigest()


def scan_file_for_viruses(file):
    """
    Scan file for viruses using ClamAV or similar
    Returns: (is_safe, threat_name)
    """
    # Check if virus scanning is enabled
    if not getattr(settings, 'ENABLE_VIRUS_SCANNING', False):
        return True, None
    
    try:
        import pyclamd
        
        # Connect to ClamAV daemon
        cd = pyclamd.ClamdUnixSocket()
        
        # Scan file
        if hasattr(file, 'read'):
            file.seek(0)
            result = cd.scan_stream(file.read())
            file.seek(0)
        else:
            result = cd.scan_stream(file)
        
        if result is None:
            # No virus found
            return True, None
        else:
            # Virus found
            threat_name = list(result.values())[0][1] if result else 'Unknown'
            return False, threat_name
    
    except ImportError:
        # pyclamd not installed, skip scanning
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("pyclamd not installed, virus scanning disabled")
        return True, None
    
    except Exception as e:
        # Error during scanning, log and allow (fail open)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Virus scanning error: {e}")
        return True, None


def validate_file_type(file, allowed_extensions=None):
    """
    Validate file type based on content (magic bytes) not just extension
    """
    if allowed_extensions is None:
        allowed_extensions = [
            '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png',
            '.xls', '.xlsx', '.txt', '.rtf', '.csv'
        ]
    
    # Check extension
    filename = getattr(file, 'name', '')
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in allowed_extensions:
        return False, f"File type {ext} not allowed"
    
    # Check magic bytes (file signature)
    try:
        import magic
        
        if hasattr(file, 'read'):
            file.seek(0)
            mime_type = magic.from_buffer(file.read(2048), mime=True)
            file.seek(0)
        else:
            mime_type = magic.from_buffer(file[:2048], mime=True)
        
        # Map extensions to expected MIME types
        allowed_mimes = {
            '.pdf': ['application/pdf'],
            '.doc': ['application/msword'],
            '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            '.jpg': ['image/jpeg'],
            '.jpeg': ['image/jpeg'],
            '.png': ['image/png'],
            '.xls': ['application/vnd.ms-excel'],
            '.xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
            '.txt': ['text/plain'],
            '.rtf': ['application/rtf', 'text/rtf'],
            '.csv': ['text/csv', 'text/plain'],
        }
        
        expected_mimes = allowed_mimes.get(ext, [])
        if expected_mimes and mime_type not in expected_mimes:
            return False, f"File content does not match extension {ext}"
    
    except ImportError:
        # python-magic not installed, skip content validation
        pass
    
    return True, None


def generate_secure_filename(original_filename, user_id, company_id):
    """
    Generate secure filename to prevent path traversal and collisions
    """
    # Extract extension
    ext = os.path.splitext(original_filename)[1].lower()
    
    # Generate unique identifier
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = secrets.token_hex(8)
    
    # Create secure filename
    secure_name = f"company_{company_id}/user_{user_id}/{timestamp}_{random_suffix}{ext}"
    
    return secure_name


def create_signed_url(file_path, expires_in_seconds=3600):
    """
    Create signed URL for secure file download
    Returns: (token, expires_at)
    """
    from django.core.signing import TimestampSigner
    
    signer = TimestampSigner()
    
    # Sign the file path
    token = signer.sign(file_path)
    
    # Calculate expiry
    expires_at = timezone.now() + timedelta(seconds=expires_in_seconds)
    
    return token, expires_at


def verify_signed_url(token, max_age=3600):
    """
    Verify signed URL token
    Returns: (is_valid, file_path)
    """
    from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
    
    signer = TimestampSigner()
    
    try:
        file_path = signer.unsign(token, max_age=max_age)
        return True, file_path
    except SignatureExpired:
        return False, "Link expired"
    except BadSignature:
        return False, "Invalid link"


def get_file_storage_backend():
    """
    Get configured file storage backend (local, S3, etc.)
    """
    storage_backend = getattr(settings, 'FILE_STORAGE_BACKEND', 'local')
    
    if storage_backend == 's3':
        from storages.backends.s3boto3 import S3Boto3Storage
        return S3Boto3Storage(
            bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
            access_key=settings.AWS_ACCESS_KEY_ID,
            secret_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            file_overwrite=False,
            default_acl='private',
        )
    elif storage_backend == 'azure':
        from storages.backends.azure_storage import AzureStorage
        return AzureStorage(
            account_name=settings.AZURE_ACCOUNT_NAME,
            account_key=settings.AZURE_ACCOUNT_KEY,
            azure_container=settings.AZURE_CONTAINER,
        )
    else:
        # Local encrypted storage
        return SecureFileStorage(
            location=settings.MEDIA_ROOT,
            base_url=settings.MEDIA_URL
        )


def sanitize_filename(filename):
    """
    Sanitize filename to prevent path traversal and other attacks
    """
    # Remove path components
    filename = os.path.basename(filename)
    
    # Remove dangerous characters
    dangerous_chars = ['..', '/', '\\', '\x00', '<', '>', ':', '"', '|', '?', '*']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    
    return name + ext


def check_storage_quota(company, file_size):
    """
    Check if company has enough storage quota
    Returns: (has_quota, current_usage, quota_limit)
    """
    from blu_staff.apps.documents.models import EmployeeDocument
    from django.db.models import Sum
    
    # Get current usage
    current_usage = EmployeeDocument.objects.filter(
        employee__company=company
    ).aggregate(
        total=Sum('file_size')
    )['total'] or 0
    
    # Get quota limit from subscription plan
    quota_limit = getattr(company, 'storage_quota_bytes', 10 * 1024 * 1024 * 1024)  # Default 10GB
    
    # Check if adding this file would exceed quota
    has_quota = (current_usage + file_size) <= quota_limit
    
    return has_quota, current_usage, quota_limit


def cleanup_old_files(days=90):
    """
    Cleanup old temporary files and expired documents
    """
    from blu_staff.apps.documents.models import EmployeeDocument
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Find expired documents
    expired_docs = EmployeeDocument.objects.filter(
        status='EXPIRED',
        updated_at__lt=cutoff_date
    )
    
    deleted_count = 0
    freed_space = 0
    
    for doc in expired_docs:
        if doc.file:
            try:
                file_size = doc.file.size
                doc.file.delete()
                freed_space += file_size
                deleted_count += 1
            except Exception:
                pass
    
    return deleted_count, freed_space


def create_file_thumbnail(file, max_size=(200, 200)):
    """
    Create thumbnail for image files
    """
    from PIL import Image
    import io
    
    try:
        # Check if file is an image
        if hasattr(file, 'read'):
            file.seek(0)
            image = Image.open(file)
            file.seek(0)
        else:
            image = Image.open(io.BytesIO(file))
        
        # Create thumbnail
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save to bytes
        thumb_io = io.BytesIO()
        image.save(thumb_io, format='PNG')
        thumb_io.seek(0)
        
        return ContentFile(thumb_io.read())
    
    except Exception:
        return None


def get_file_metadata(file):
    """
    Extract metadata from file
    """
    metadata = {
        'filename': getattr(file, 'name', 'unknown'),
        'size': getattr(file, 'size', 0),
        'content_type': getattr(file, 'content_type', 'application/octet-stream'),
        'hash': calculate_file_hash(file),
    }
    
    # Try to extract additional metadata
    try:
        from PIL import Image
        
        if hasattr(file, 'read'):
            file.seek(0)
            image = Image.open(file)
            file.seek(0)
            
            metadata['width'] = image.width
            metadata['height'] = image.height
            metadata['format'] = image.format
    except Exception:
        pass
    
    return metadata
