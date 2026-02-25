"""
Request Management Models
Handles various employee requests: Petty Cash, Advance, Reimbursement, etc.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

from tenant_management.models import TenantScopedModel

User = get_user_model()


class RequestType(TenantScopedModel):
    """Types of requests that can be made"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    requires_approval = models.BooleanField(default=True)
    approval_levels = models.PositiveIntegerField(default=1, help_text="Number of approval levels required")
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=20, blank=True, help_text="Emoji or icon code")
    
    # Request configuration
    requires_amount = models.BooleanField(default=False)
    requires_attachment = models.BooleanField(default=False)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'code']
    
    def __str__(self):
        return self.name


class EmployeeRequest(TenantScopedModel):
    """Base model for all employee requests"""
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        CANCELLED = 'CANCELLED', 'Cancelled'
        COMPLETED = 'COMPLETED', 'Completed'
    
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'
    
    # Request identification
    request_number = models.CharField(max_length=50)
    request_type = models.ForeignKey(RequestType, on_delete=models.PROTECT)
    
    # Requester information
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_requests')
    department = models.CharField(max_length=100, blank=True)
    
    # Request details
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='ZMW')
    
    # Status and priority
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    
    # Dates
    request_date = models.DateTimeField(default=timezone.now)
    required_by = models.DateField(null=True, blank=True, help_text="Date when request is needed")
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Attachments
    attachment = models.FileField(upload_to='request_attachments/', null=True, blank=True)
    
    # Approval tracking
    current_approval_level = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['tenant', 'request_number']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['request_type', 'status']),
            models.Index(fields=['request_number']),
        ]
    
    def __str__(self):
        return f"{self.request_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.request_number:
            # Generate request number
            import datetime
            date_str = datetime.datetime.now().strftime('%Y%m%d')
            queryset = EmployeeRequest.objects.filter(
                request_number__startswith=f'REQ-{date_str}'
            )
            if self.tenant_id:
                queryset = queryset.filter(tenant=self.tenant)
            last_request = queryset.order_by('-request_number').first()
            
            if last_request:
                last_num = int(last_request.request_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.request_number = f'REQ-{date_str}-{new_num:04d}'
        
        super().save(*args, **kwargs)


class RequestApproval(TenantScopedModel):
    """Approval workflow for requests"""
    
    class Action(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
    
    request = models.ForeignKey(EmployeeRequest, on_delete=models.CASCADE, related_name='approvals')
    approval_level = models.PositiveIntegerField()
    approver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='request_approvals')
    
    # Approval details
    action = models.CharField(max_length=20, choices=Action.choices, default=Action.PENDING)
    comments = models.TextField(blank=True)
    
    # Timestamps
    assigned_date = models.DateTimeField(auto_now_add=True)
    action_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['approval_level', 'assigned_date']
        unique_together = [['tenant', 'request', 'approval_level', 'approver']]
    
    def __str__(self):
        return f"{self.request.request_number} - Level {self.approval_level} - {self.approver.get_full_name()}"


class RequestComment(TenantScopedModel):
    """Comments/notes on requests"""
    request = models.ForeignKey(EmployeeRequest, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Internal notes not visible to requester")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment on {self.request.request_number} by {self.user.get_full_name()}"


class PettyCashRequest(TenantScopedModel):
    """Specific model for Petty Cash requests"""
    request = models.OneToOneField(EmployeeRequest, on_delete=models.CASCADE, related_name='petty_cash_details')
    
    # Petty cash specific fields
    purpose = models.CharField(max_length=255)
    expense_category = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=50, choices=[
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('MOBILE_MONEY', 'Mobile Money'),
    ], default='CASH')
    
    # Disbursement tracking
    disbursed = models.BooleanField(default=False)
    disbursed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='disbursed_petty_cash')
    disbursed_date = models.DateTimeField(null=True, blank=True)
    disbursed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Receipt tracking
    receipt_submitted = models.BooleanField(default=False)
    receipt_file = models.FileField(upload_to='petty_cash_receipts/', null=True, blank=True)
    
    def __str__(self):
        return f"Petty Cash: {self.request.request_number}"


class AdvanceRequest(TenantScopedModel):
    """Salary advance requests"""
    request = models.OneToOneField(EmployeeRequest, on_delete=models.CASCADE, related_name='advance_details')
    
    # Advance specific fields
    reason = models.TextField()
    repayment_plan = models.TextField(help_text="How the advance will be repaid")
    installments = models.PositiveIntegerField(default=1, help_text="Number of months for repayment")
    
    # Approval
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Disbursement
    disbursed = models.BooleanField(default=False)
    disbursement_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Advance: {self.request.request_number}"


class ReimbursementRequest(TenantScopedModel):
    """Expense reimbursement requests"""
    request = models.OneToOneField(EmployeeRequest, on_delete=models.CASCADE, related_name='reimbursement_details')
    
    # Reimbursement specific fields
    expense_date = models.DateField()
    expense_category = models.CharField(max_length=100)
    vendor_name = models.CharField(max_length=255, blank=True)
    
    # Supporting documents
    receipt_required = models.BooleanField(default=True)
    receipts = models.FileField(upload_to='reimbursement_receipts/', null=True, blank=True)
    
    # Payment
    paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"Reimbursement: {self.request.request_number}"
