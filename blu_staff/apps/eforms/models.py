from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

from tenant_management.models import TenantScopedModel

User = get_user_model()


class FormTemplate(TenantScopedModel):
    """Digital form template builder"""
    
    class FormCategory(models.TextChoices):
        HR = 'HR', 'HR Forms'
        FINANCE = 'FINANCE', 'Finance Forms'
        GENERAL = 'GENERAL', 'General Forms'
        COMPLIANCE = 'COMPLIANCE', 'Compliance Forms'
        CUSTOM = 'CUSTOM', 'Custom Forms'
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ACTIVE = 'ACTIVE', 'Active'
        ARCHIVED = 'ARCHIVED', 'Archived'
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=FormCategory.choices, default=FormCategory.GENERAL)
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='form_templates')
    
    # Form structure stored as JSON
    form_fields = models.JSONField(default=dict, help_text="JSON structure of form fields")
    
    # Settings
    requires_signature = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    approver_role = models.CharField(max_length=50, blank=True, help_text="Role required to approve (e.g., SUPERVISOR, HR)")
    
    # Document header layout
    header_style = models.CharField(
        max_length=20, default='logo_left',
        choices=[
            ('logo_left', 'Logo Left'),
            ('logo_center', 'Logo Center'),
            ('logo_right', 'Logo Right'),
            ('full_width', 'Full Width'),
        ],
        help_text="Letterhead layout for this form"
    )
    
    # Status and metadata
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_forms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['tenant', 'title']
        
    def __str__(self):
        return f"{self.title} ({self.category})"


class FormSubmission(TenantScopedModel):
    """Submitted form instance"""
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        COMPLETED = 'COMPLETED', 'Completed'
    
    template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='submissions')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='form_submissions')
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='form_submissions')
    
    # Form data stored as JSON
    form_data = models.JSONField(default=dict, help_text="Submitted form data")
    
    # Status tracking
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Approval workflow
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_forms')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.template.title} - {self.submitted_by.get_full_name()} ({self.status})"
    
    def submit(self):
        """Submit the form"""
        if self.status == 'DRAFT':
            self.status = 'SUBMITTED' if not self.template.requires_approval else 'PENDING_APPROVAL'
            self.submitted_at = timezone.now()
            self.save()


class FormField(TenantScopedModel):
    """Individual form field definition (for template building)"""
    
    class FieldType(models.TextChoices):
        TEXT = 'TEXT', 'Text Input'
        TEXTAREA = 'TEXTAREA', 'Text Area'
        NUMBER = 'NUMBER', 'Number'
        EMAIL = 'EMAIL', 'Email'
        DATE = 'DATE', 'Date'
        CHECKBOX = 'CHECKBOX', 'Checkbox'
        RADIO = 'RADIO', 'Radio Button'
        SELECT = 'SELECT', 'Dropdown'
        FILE = 'FILE', 'File Upload'
        SIGNATURE = 'SIGNATURE', 'Signature'
    
    template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='fields')
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    label = models.CharField(max_length=200)
    placeholder = models.CharField(max_length=200, blank=True)
    help_text = models.TextField(blank=True)
    
    # Validation
    required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True, help_text="Options for select/radio fields")
    
    # Layout
    order = models.IntegerField(default=0)
    width = models.CharField(max_length=20, default='full', help_text="full, half, third")
    
    class Meta:
        ordering = ['order']
        
    def __str__(self):
        return f"{self.label} ({self.field_type})"


class ESignature(TenantScopedModel):
    """Electronic signature for form submissions"""
    
    class SignatureType(models.TextChoices):
        DRAWN = 'DRAWN', 'Drawn Signature'
        TYPED = 'TYPED', 'Typed Signature'
        UPLOADED = 'UPLOADED', 'Uploaded Image'
    
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='signatures')
    signer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='signatures')
    
    # Signature data
    signature_type = models.CharField(max_length=20, choices=SignatureType.choices)
    signature_data = models.TextField(help_text="Base64 encoded signature or typed text")
    signature_image = models.ImageField(upload_to='signatures/', null=True, blank=True)
    
    # Verification
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    signed_at = models.DateTimeField(auto_now_add=True)
    
    # Legal consent
    consent_text = models.TextField(help_text="Text that user agreed to when signing")
    consented = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-signed_at']
        
    def __str__(self):
        return f"Signature by {self.signer.get_full_name()} on {self.signed_at.strftime('%Y-%m-%d %H:%M')}"


class SignatureAuditLog(TenantScopedModel):
    """Audit trail for signature events"""
    
    class Action(models.TextChoices):
        CREATED = 'CREATED', 'Signature Created'
        VERIFIED = 'VERIFIED', 'Signature Verified'
        INVALIDATED = 'INVALIDATED', 'Signature Invalidated'
        VIEWED = 'VIEWED', 'Signature Viewed'
    
    signature = models.ForeignKey(ESignature, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=Action.choices)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Audit details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.action} - {self.signature} at {self.timestamp}"


class FormApproval(TenantScopedModel):
    """Approval workflow for form submissions"""
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
    
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='form_approvals')
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    comments = models.TextField(blank=True)
    
    assigned_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-assigned_at']
        
    def __str__(self):
        return f"Approval for {self.submission} by {self.approver.get_full_name()} - {self.status}"
