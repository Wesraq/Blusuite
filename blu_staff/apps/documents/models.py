from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import os

from tenant_management.models import TenantScopedModel

User = get_user_model()


class DocumentCategory(TenantScopedModel):
    """Categories for organizing documents"""
    name = models.CharField(_('category name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    default_document_type = models.CharField(
        _('default document type'),
        max_length=20,
        blank=True,
        default='',
        help_text=_('Optional default document type value used when uploading documents automatically.'),
    )
    is_required = models.BooleanField(_('is required'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('document category')
        verbose_name_plural = _('document categories')
        ordering = ['name']
        unique_together = [('tenant', 'name')]

    def __str__(self):
        return self.name


class EmployeeDocument(TenantScopedModel):
    """Model for storing employee documents"""

    class DocumentType(models.TextChoices):
        CONTRACT = 'CONTRACT', _('Employment Contract')
        CERTIFICATE = 'CERTIFICATE', _('Certificate')
        ID = 'ID', _('Identification Document')
        LICENSE = 'LICENSE', _('Professional License')
        MEDICAL = 'MEDICAL', _('Medical Record')
        TRAINING = 'TRAINING', _('Training Record')
        PERFORMANCE = 'PERFORMANCE', _('Performance Review')
        POLICY = 'POLICY', _('Company Policy')
        OTHER = 'OTHER', _('Other')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending Review')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        EXPIRED = 'EXPIRED', _('Expired')

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='documents',
        limit_choices_to={'role': 'EMPLOYEE'}
    )
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    document_type = models.CharField(
        _('document type'),
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.OTHER
    )
    title = models.CharField(_('document title'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    file = models.FileField(_('file'), upload_to='employee_documents/')
    original_filename = models.CharField(_('original filename'), max_length=255)
    file_size = models.PositiveIntegerField(_('file size'), help_text=_('Size in bytes'))
    mime_type = models.CharField(_('MIME type'), max_length=100)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    expiry_date = models.DateField(_('expiry date'), null=True, blank=True)
    version = models.PositiveIntegerField(_('version'), default=1)
    is_confidential = models.BooleanField(_('confidential'), default=False)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_documents',
        limit_choices_to={'role__in': ['ADMIN', 'EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN']}
    )
    approved_at = models.DateTimeField(_('approved at'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('employee document')
        verbose_name_plural = _('employee documents')
        ordering = ['-created_at']
        unique_together = [('tenant', 'employee', 'title', 'version')]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.title} (v{self.version})"

    def clean(self):
        """Validate the document"""
        if self.file:
            # Check file size (max 10MB)
            if self.file.size > 10 * 1024 * 1024:
                raise ValidationError(_("File size cannot exceed 10MB"))

            # Check file extension
            allowed_extensions = [
                '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png',
                '.xls', '.xlsx', '.txt', '.rtf'
            ]
            ext = os.path.splitext(self.file.name)[1].lower()
            if ext not in allowed_extensions:
                raise ValidationError(_("File type not allowed"))

    def save(self, *args, **kwargs):
        if self.file:
            self.original_filename = self.file.name
            self.file_size = self.file.size
            self.mime_type = getattr(self.file, 'content_type', 'application/octet-stream')
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if document is expired"""
        if self.expiry_date:
            from django.utils import timezone
            return self.expiry_date < timezone.now().date()
        return False

    def get_file_extension(self):
        """Get file extension"""
        return os.path.splitext(self.original_filename)[1]


class DocumentTemplate(TenantScopedModel):
    """Model for document templates"""

    name = models.CharField(_('template name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.CASCADE,
        related_name='templates'
    )
    template_file = models.FileField(_('template file'), upload_to='document_templates/')
    is_active = models.BooleanField(_('active'), default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('document template')
        verbose_name_plural = _('document templates')
        ordering = ['-created_at']
        unique_together = [('tenant', 'name')]

    def __str__(self):
        return self.name


class DocumentAccessLog(TenantScopedModel):
    """Model to track document access"""

    class AccessType(models.TextChoices):
        VIEW = 'VIEW', _('View')
        DOWNLOAD = 'DOWNLOAD', _('Download')
        UPLOAD = 'UPLOAD', _('Upload')
        APPROVE = 'APPROVE', _('Approve')
        REJECT = 'REJECT', _('Reject')

    document = models.ForeignKey(
        EmployeeDocument,
        on_delete=models.CASCADE,
        related_name='access_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_access_logs'
    )
    access_type = models.CharField(
        _('access type'),
        max_length=20,
        choices=AccessType.choices
    )
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True)
    accessed_at = models.DateTimeField(_('accessed at'), auto_now_add=True)

    class Meta:
        verbose_name = _('document access log')
        verbose_name_plural = _('document access logs')
        ordering = ['-accessed_at']

    def __str__(self):
        return f"{self.user} - {self.document} - {self.access_type}"
