from django.db import models
from django.contrib.auth import get_user_model
from tenant_management.models import TenantScopedModel
from blu_staff.apps.accounts.models import Company

User = get_user_model()


class EmployeeContract(TenantScopedModel):
    """Employee contract management model"""
    
    class ContractType(models.TextChoices):
        PERMANENT = 'PERMANENT', 'Permanent Employment'
        FIXED_TERM = 'FIXED_TERM', 'Fixed-Term Contract'
        PROBATION = 'PROBATION', 'Probationary Contract'
        TEMPORARY = 'TEMPORARY', 'Temporary Contract'
        CONSULTANT = 'CONSULTANT', 'Consultant Agreement'
        PART_TIME = 'PART_TIME', 'Part-Time Contract'
        INTERNSHIP = 'INTERNSHIP', 'Internship Agreement'
    
    class ContractStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ACTIVE = 'ACTIVE', 'Active'
        PENDING_RENEWAL = 'PENDING_RENEWAL', 'Pending Renewal'
        RENEWED = 'RENEWED', 'Renewed'
        EXPIRED = 'EXPIRED', 'Expired'
        TERMINATED = 'TERMINATED', 'Terminated'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    # Basic Information
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contracts')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employee_contracts')
    contract_type = models.CharField(max_length=20, choices=ContractType.choices, default=ContractType.PERMANENT)
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.DRAFT)
    
    # Contract Details
    contract_number = models.CharField(max_length=50, unique=True, blank=True)
    job_title = models.CharField(max_length=200)
    department = models.CharField(max_length=200, blank=True)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for permanent contracts")
    signed_date = models.DateField(null=True, blank=True)
    
    # Renewal Information
    renewal_notice_period_days = models.PositiveIntegerField(default=30, help_text="Days before expiry to send renewal notice")
    auto_renew = models.BooleanField(default=False, help_text="Automatically renew contract")
    renewed_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='renewals')
    
    # Compensation
    salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='ZMW')
    salary_frequency = models.CharField(max_length=20, default='MONTHLY', choices=[
        ('HOURLY', 'Hourly'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('ANNUALLY', 'Annually'),
    ])
    
    # Work Details
    working_hours_per_week = models.DecimalField(max_digits=5, decimal_places=2, default=40.00)
    probation_period_months = models.PositiveIntegerField(null=True, blank=True)
    notice_period_days = models.PositiveIntegerField(default=30)
    
    # Documents
    contract_document = models.FileField(upload_to='contracts/documents/', null=True, blank=True)
    signed_contract_document = models.FileField(upload_to='contracts/signed/', null=True, blank=True)
    
    # Terms & Conditions
    terms_and_conditions = models.TextField(blank=True)
    special_clauses = models.TextField(blank=True, help_text="Any special terms or clauses")
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='contracts_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Notifications
    renewal_notification_sent = models.BooleanField(default=False)
    expiry_notification_sent = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'contracts'
        ordering = ['-created_at']
        verbose_name = 'Employee Contract'
        verbose_name_plural = 'Employee Contracts'
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.contract_type} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-generate contract number if not set
        if not self.contract_number:
            from datetime import datetime
            year = datetime.now().year
            count = EmployeeContract.objects.filter(company=self.company).count() + 1
            self.contract_number = f"CONT-{year}-{count:05d}"
        
        super().save(*args, **kwargs)
    
    @property
    def is_expiring_soon(self):
        """Check if contract is expiring within renewal notice period"""
        if not self.end_date or self.status != self.ContractStatus.ACTIVE:
            return False
        
        from datetime import date, timedelta
        days_until_expiry = (self.end_date - date.today()).days
        return 0 <= days_until_expiry <= self.renewal_notice_period_days
    
    @property
    def is_expired(self):
        """Check if contract has expired"""
        if not self.end_date:
            return False
        
        from datetime import date
        return date.today() > self.end_date
    
    @property
    def days_until_expiry(self):
        """Calculate days until contract expiry"""
        if not self.end_date:
            return None
        
        from datetime import date
        return (self.end_date - date.today()).days


class ContractAmendment(TenantScopedModel):
    """Track amendments/changes to contracts"""
    
    contract = models.ForeignKey(EmployeeContract, on_delete=models.CASCADE, related_name='amendments')
    amendment_number = models.CharField(max_length=50)
    amendment_date = models.DateField()
    effective_date = models.DateField()
    
    # What changed
    description = models.TextField(help_text="Description of changes made")
    previous_values = models.JSONField(default=dict, blank=True, help_text="Store previous values")
    new_values = models.JSONField(default=dict, blank=True, help_text="Store new values")
    
    # Document
    amendment_document = models.FileField(upload_to='contracts/amendments/', null=True, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'contracts'
        ordering = ['-amendment_date']
        verbose_name = 'Contract Amendment'
        verbose_name_plural = 'Contract Amendments'
    
    def __str__(self):
        return f"Amendment {self.amendment_number} - {self.contract.employee.get_full_name()}"


class ContractRenewal(TenantScopedModel):
    """Track contract renewal requests and approvals"""
    
    class RenewalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        COMPLETED = 'COMPLETED', 'Completed'
    
    original_contract = models.ForeignKey(EmployeeContract, on_delete=models.CASCADE, related_name='renewal_requests')
    new_contract = models.ForeignKey(EmployeeContract, on_delete=models.SET_NULL, null=True, blank=True, related_name='renewed_contract')
    
    status = models.CharField(max_length=20, choices=RenewalStatus.choices, default=RenewalStatus.PENDING)
    
    # Renewal Details
    proposed_start_date = models.DateField()
    proposed_end_date = models.DateField(null=True, blank=True)
    proposed_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    proposed_job_title = models.CharField(max_length=200, blank=True)
    proposed_terms = models.TextField(blank=True)
    
    # Notes
    renewal_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Tracking
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='renewal_requests_made')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='renewal_reviews')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'contracts'
        ordering = ['-requested_at']
        verbose_name = 'Contract Renewal'
        verbose_name_plural = 'Contract Renewals'
    
    def __str__(self):
        return f"Renewal Request - {self.original_contract.employee.get_full_name()} ({self.status})"


class ContractTemplate(TenantScopedModel):
    """Reusable contract templates"""
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contract_templates')
    name = models.CharField(max_length=200)
    contract_type = models.CharField(max_length=20, choices=EmployeeContract.ContractType.choices)
    
    # Template Content
    template_content = models.TextField(help_text="Contract template with placeholders like {{employee_name}}, {{job_title}}, etc.")
    terms_and_conditions = models.TextField(blank=True)
    
    # Default Values
    default_probation_months = models.PositiveIntegerField(null=True, blank=True)
    default_notice_period_days = models.PositiveIntegerField(default=30)
    default_working_hours = models.DecimalField(max_digits=5, decimal_places=2, default=40.00)
    
    # Tracking
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'contracts'
        ordering = ['name']
        verbose_name = 'Contract Template'
        verbose_name_plural = 'Contract Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_contract_type_display()})"
