from django.db import models
from django.conf import settings
from django.utils import timezone


class PaymentPlan(models.Model):
    """Subscription plans for companies"""
    name = models.CharField(max_length=100)
    stripe_price_id = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='usd')
    max_employees = models.PositiveIntegerField()
    features = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Payment Plan"
        verbose_name_plural = "Payment Plans"
    
    def __str__(self):
        return f"{self.name} - ${self.price}"


class CompanySubscription(models.Model):
    """Track company subscriptions"""
    company = models.OneToOneField('accounts.Company', on_delete=models.CASCADE)
    plan = models.ForeignKey(PaymentPlan, on_delete=models.SET_NULL, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
    ], default='trial')
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Company Subscription"
        verbose_name_plural = "Company Subscriptions"
    
    def __str__(self):
        return f"{self.company.name} - {self.plan.name if self.plan else 'No Plan'}"
    
    def is_active(self):
        return self.status == 'active' and (
            self.current_period_end is None or 
            self.current_period_end > timezone.now()
        )


class Payment(models.Model):
    """Individual payment records"""
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    stripe_payment_intent_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='usd')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ], default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.stripe_payment_intent_id} - ${self.amount}"
