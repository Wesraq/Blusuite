from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import uuid

class SubscriptionPlan(models.Model):
    """Subscription plans available for tenants"""
    
    class PlanType(models.TextChoices):
        BASIC = 'BASIC', 'Basic Plan'
        STANDARD = 'STANDARD', 'Standard Plan'
        PROFESSIONAL = 'PROFESSIONAL', 'Professional Plan'
        ENTERPRISE = 'ENTERPRISE', 'Enterprise Plan'
        
    class BillingCycle(models.TextChoices):
        MONTHLY = 'MONTHLY', 'Monthly'
        YEARLY = 'YEARLY', 'Yearly'
        
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PlanType.choices)
    description = models.TextField()
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2)
    max_users = models.PositiveIntegerField(default=10)
    max_storage_gb = models.PositiveIntegerField(default=10)
    features = models.JSONField(default=list)  # List of features
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['monthly_price']
        
    def __str__(self):
        return f"{self.name} - ${self.monthly_price}/month"
    
    def get_price_for_cycle(self, cycle):
        return self.yearly_price if cycle == self.BillingCycle.YEARLY else self.monthly_price

class CompanySubscription(models.Model):
    """Subscription information for each company"""
    
    class Status(models.TextChoices):
        TRIAL = 'TRIAL', 'Trial'
        ACTIVE = 'ACTIVE', 'Active'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        CANCELLED = 'CANCELLED', 'Cancelled'
        EXPIRED = 'EXPIRED', 'Expired'
        
    company = models.OneToOneField(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    billing_cycle = models.CharField(
        max_length=10, 
        choices=SubscriptionPlan.BillingCycle.choices,
        default=SubscriptionPlan.BillingCycle.MONTHLY
    )
    
    # Trial specific
    trial_started_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    
    # Active subscription
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    
    # Billing
    next_billing_date = models.DateTimeField(null=True, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)
    last_payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Usage tracking
    current_users = models.PositiveIntegerField(default=0)
    current_storage_gb = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    api_calls_this_month = models.PositiveIntegerField(default=0)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.company.name} - {self.plan.name}"
    
    @property
    def is_trial_active(self):
        return (
            self.status == self.Status.TRIAL and 
            self.trial_ends_at and 
            self.trial_ends_at > timezone.now()
        )
    
    @property
    def is_active(self):
        return (
            self.status == self.Status.ACTIVE and 
            self.current_period_end and 
            self.current_period_end > timezone.now()
        )
    
    @property
    def days_until_expiry(self):
        if self.trial_ends_at and self.status == self.Status.TRIAL:
            return (self.trial_ends_at - timezone.now()).days
        elif self.current_period_end:
            return (self.current_period_end - timezone.now()).days
        return 0
    
    @property
    def usage_percentage(self):
        """Calculate overall usage percentage"""
        user_usage = (self.current_users / self.plan.max_users) * 100 if self.plan.max_users > 0 else 0
        storage_usage = (self.current_storage_gb / self.plan.max_storage_gb) * 100 if self.plan.max_storage_gb > 0 else 0
        return max(user_usage, storage_usage)

class Invoice(models.Model):
    """Billing invoices for companies"""
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        OVERDUE = 'OVERDUE', 'Overdue'
        CANCELLED = 'CANCELLED', 'Cancelled'
        
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    subscription = models.ForeignKey(CompanySubscription, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    
    # Invoice details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Dates
    issue_date = models.DateTimeField()
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Payment details
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.company.name}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generate unique invoice number
            timestamp = timezone.now().strftime('%Y%m')
            count = Invoice.objects.filter(
                created_at__year=timezone.now().year,
                created_at__month=timezone.now().month
            ).count() + 1
            self.invoice_number = f"INV-{timestamp}-{count:04d}"
        super().save(*args, **kwargs)

class Payment(models.Model):
    """Payment records for invoices"""
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'
        
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    payment_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    payment_method = models.CharField(max_length=50)
    gateway = models.CharField(max_length=50)  # Stripe, PayPal, etc.
    gateway_transaction_id = models.CharField(max_length=100, blank=True)
    
    # Dates
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    def __str__(self):
        return f"Payment {self.payment_id} - ${self.amount}"

class UsageMetric(models.Model):
    """Track usage metrics for billing and monitoring"""
    
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='usage_metrics'
    )
    metric_type = models.CharField(max_length=50)  # 'users', 'storage', 'api_calls', etc.
    metric_value = models.DecimalField(max_digits=15, decimal_places=2)
    metric_date = models.DateField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['company', 'metric_type', 'metric_date']
        ordering = ['-metric_date']
        
    def __str__(self):
        return f"{self.company.name} - {self.metric_type}: {self.metric_value} on {self.metric_date}"
