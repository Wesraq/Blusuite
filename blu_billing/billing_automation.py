"""
Billing Automation for BluSuite
Handles automatic invoice generation, subscription renewals, trial expiry, and payment processing
"""
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from datetime import timedelta
from decimal import Decimal

from .models import CompanySubscription, Invoice, SubscriptionPlan, UsageMetric
from blu_staff.apps.accounts.models import Company

User = get_user_model()


def generate_monthly_invoices():
    """
    Generate invoices for all active subscriptions due for billing.
    Should be run daily via cron/celery.
    """
    today = timezone.now()
    results = {
        'generated': 0,
        'skipped': 0,
        'errors': [],
    }
    
    # Find subscriptions due for billing
    due_subscriptions = CompanySubscription.objects.filter(
        status=CompanySubscription.Status.ACTIVE,
        next_billing_date__lte=today
    ).select_related('company', 'plan')
    
    for subscription in due_subscriptions:
        try:
            with transaction.atomic():
                # Calculate amount based on billing cycle
                amount = subscription.plan.get_price_for_cycle(subscription.billing_cycle)
                tax_amount = amount * Decimal('0.10')  # 10% tax (adjust per region)
                total_amount = amount + tax_amount
                
                # Create invoice
                invoice = Invoice.objects.create(
                    company=subscription.company,
                    subscription=subscription,
                    amount=amount,
                    tax_amount=tax_amount,
                    total_amount=total_amount,
                    issue_date=today,
                    due_date=today + timedelta(days=30),
                    status=Invoice.Status.PENDING,
                    currency='USD'
                )
                
                # Update subscription billing dates
                if subscription.billing_cycle == SubscriptionPlan.BillingCycle.MONTHLY:
                    subscription.next_billing_date = today + timedelta(days=30)
                else:  # YEARLY
                    subscription.next_billing_date = today + timedelta(days=365)
                
                subscription.save(update_fields=['next_billing_date'])
                
                # Send notification
                _notify_invoice_generated(invoice)
                
                results['generated'] += 1
                
        except Exception as e:
            results['errors'].append({
                'company': subscription.company.name,
                'error': str(e)
            })
    
    return results


def process_trial_expirations():
    """
    Handle trial subscriptions that have expired.
    Convert to paid or suspend based on payment method.
    """
    today = timezone.now()
    results = {
        'converted': 0,
        'suspended': 0,
        'errors': [],
    }
    
    # Find expired trials
    expired_trials = CompanySubscription.objects.filter(
        status=CompanySubscription.Status.TRIAL,
        trial_ends_at__lte=today
    ).select_related('company', 'plan')
    
    for subscription in expired_trials:
        try:
            with transaction.atomic():
                # Check if company has payment method
                has_payment = _has_valid_payment_method(subscription.company)
                
                if has_payment:
                    # Convert to active subscription
                    subscription.status = CompanySubscription.Status.ACTIVE
                    subscription.current_period_start = today
                    
                    if subscription.billing_cycle == SubscriptionPlan.BillingCycle.MONTHLY:
                        subscription.current_period_end = today + timedelta(days=30)
                    else:
                        subscription.current_period_end = today + timedelta(days=365)
                    
                    subscription.next_billing_date = subscription.current_period_end
                    subscription.save()
                    
                    # Generate first invoice
                    amount = subscription.plan.get_price_for_cycle(subscription.billing_cycle)
                    tax_amount = amount * Decimal('0.10')
                    
                    Invoice.objects.create(
                        company=subscription.company,
                        subscription=subscription,
                        amount=amount,
                        tax_amount=tax_amount,
                        total_amount=amount + tax_amount,
                        issue_date=today,
                        due_date=today + timedelta(days=30),
                        status=Invoice.Status.PENDING,
                        currency='USD'
                    )
                    
                    _notify_trial_converted(subscription)
                    results['converted'] += 1
                else:
                    # Suspend subscription
                    subscription.status = CompanySubscription.Status.SUSPENDED
                    subscription.save(update_fields=['status'])
                    
                    _notify_trial_expired_no_payment(subscription)
                    results['suspended'] += 1
                    
        except Exception as e:
            results['errors'].append({
                'company': subscription.company.name,
                'error': str(e)
            })
    
    return results


def send_trial_expiry_warnings():
    """
    Send notifications to companies whose trials are expiring soon.
    Run daily.
    """
    today = timezone.now()
    warning_dates = [
        today + timedelta(days=7),
        today + timedelta(days=3),
        today + timedelta(days=1),
    ]
    
    results = {'notified': 0}
    
    for warning_date in warning_dates:
        trials_expiring = CompanySubscription.objects.filter(
            status=CompanySubscription.Status.TRIAL,
            trial_ends_at__date=warning_date.date()
        ).select_related('company')
        
        for subscription in trials_expiring:
            days_left = (subscription.trial_ends_at - today).days
            _notify_trial_expiring(subscription, days_left)
            results['notified'] += 1
    
    return results


def process_overdue_invoices():
    """
    Mark invoices as overdue and suspend subscriptions if payment is late.
    Run daily.
    """
    today = timezone.now()
    grace_period = timedelta(days=7)
    
    results = {
        'marked_overdue': 0,
        'suspended': 0,
    }
    
    # Mark overdue invoices
    overdue_invoices = Invoice.objects.filter(
        status=Invoice.Status.PENDING,
        due_date__lt=today
    )
    
    for invoice in overdue_invoices:
        invoice.status = Invoice.Status.OVERDUE
        invoice.save(update_fields=['status'])
        _notify_invoice_overdue(invoice)
        results['marked_overdue'] += 1
    
    # Suspend subscriptions with severely overdue invoices
    suspension_date = today - grace_period
    severely_overdue = Invoice.objects.filter(
        status=Invoice.Status.OVERDUE,
        due_date__lt=suspension_date
    ).select_related('subscription')
    
    for invoice in severely_overdue:
        subscription = invoice.subscription
        if subscription.status == CompanySubscription.Status.ACTIVE:
            subscription.status = CompanySubscription.Status.SUSPENDED
            subscription.save(update_fields=['status'])
            _notify_subscription_suspended(subscription, invoice)
            results['suspended'] += 1
    
    return results


def update_usage_metrics():
    """
    Update usage metrics for all active subscriptions.
    Run daily.
    """
    today = timezone.now().date()
    
    active_subscriptions = CompanySubscription.objects.filter(
        status__in=[CompanySubscription.Status.ACTIVE, CompanySubscription.Status.TRIAL]
    ).select_related('company')
    
    for subscription in active_subscriptions:
        # Count active users
        user_count = User.objects.filter(
            company=subscription.company,
            is_active=True
        ).count()
        
        subscription.current_users = user_count
        subscription.save(update_fields=['current_users'])
        
        # Create usage metric record
        UsageMetric.objects.create(
            company=subscription.company,
            metric_type='users',
            metric_value=user_count,
            metric_date=today
        )
        
        # Check if over limit
        if user_count > subscription.plan.max_users:
            _notify_usage_exceeded(subscription, 'users', user_count, subscription.plan.max_users)
    
    return {'updated': active_subscriptions.count()}


# ─────────────────────────────────────────────────────────────────────────────
# Notification Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _notify_invoice_generated(invoice):
    """Notify company admins when invoice is generated"""
    try:
        from blu_staff.apps.notifications.utils import create_notification
        
        admins = User.objects.filter(
            company=invoice.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        
        for admin in admins:
            create_notification(
                recipient=admin,
                title='New Invoice Generated',
                message=f'Invoice {invoice.invoice_number} for {invoice.currency} {invoice.total_amount} has been generated. Due date: {invoice.due_date.strftime("%Y-%m-%d")}.',
                notification_type='INFO',
                category='SYSTEM',
                link='/billing/',
                send_email=True,
                tenant=getattr(invoice.company, 'tenant', None)
            )
    except Exception:
        pass


def _notify_trial_converted(subscription):
    """Notify when trial converts to paid subscription"""
    try:
        from blu_staff.apps.notifications.utils import create_notification
        
        admins = User.objects.filter(
            company=subscription.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        
        for admin in admins:
            create_notification(
                recipient=admin,
                title='Trial Converted to Paid Subscription',
                message=f'Your trial has ended and your subscription is now active. Your first invoice has been generated.',
                notification_type='SUCCESS',
                category='SYSTEM',
                link='/billing/',
                send_email=True,
                tenant=getattr(subscription.company, 'tenant', None)
            )
    except Exception:
        pass


def _notify_trial_expired_no_payment(subscription):
    """Notify when trial expires without payment method"""
    try:
        from blu_staff.apps.notifications.utils import create_notification
        
        admins = User.objects.filter(
            company=subscription.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        
        for admin in admins:
            create_notification(
                recipient=admin,
                title='Trial Expired - Action Required',
                message='Your trial has expired. Please add a payment method to continue using BluSuite.',
                notification_type='WARNING',
                category='SYSTEM',
                link='/billing/',
                send_email=True,
                tenant=getattr(subscription.company, 'tenant', None)
            )
    except Exception:
        pass


def _notify_trial_expiring(subscription, days_left):
    """Notify when trial is expiring soon"""
    try:
        from blu_staff.apps.notifications.utils import create_notification
        
        admins = User.objects.filter(
            company=subscription.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        
        for admin in admins:
            create_notification(
                recipient=admin,
                title=f'Trial Expiring in {days_left} Day{"s" if days_left != 1 else ""}',
                message=f'Your trial will expire in {days_left} day{"s" if days_left != 1 else ""}. Add a payment method to continue uninterrupted service.',
                notification_type='REMINDER',
                category='SYSTEM',
                link='/billing/',
                send_email=True,
                tenant=getattr(subscription.company, 'tenant', None)
            )
    except Exception:
        pass


def _notify_invoice_overdue(invoice):
    """Notify when invoice becomes overdue"""
    try:
        from blu_staff.apps.notifications.utils import create_notification
        
        admins = User.objects.filter(
            company=invoice.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        
        for admin in admins:
            create_notification(
                recipient=admin,
                title='Invoice Overdue',
                message=f'Invoice {invoice.invoice_number} is overdue. Please make payment to avoid service interruption.',
                notification_type='WARNING',
                category='SYSTEM',
                link='/billing/',
                send_email=True,
                tenant=getattr(invoice.company, 'tenant', None)
            )
    except Exception:
        pass


def _notify_subscription_suspended(subscription, invoice):
    """Notify when subscription is suspended due to non-payment"""
    try:
        from blu_staff.apps.notifications.utils import create_notification
        
        admins = User.objects.filter(
            company=subscription.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        
        for admin in admins:
            create_notification(
                recipient=admin,
                title='Subscription Suspended',
                message=f'Your subscription has been suspended due to unpaid invoice {invoice.invoice_number}. Please make payment immediately to restore service.',
                notification_type='ERROR',
                category='SYSTEM',
                link='/billing/',
                send_email=True,
                tenant=getattr(subscription.company, 'tenant', None)
            )
    except Exception:
        pass


def _notify_usage_exceeded(subscription, metric_type, current, limit):
    """Notify when usage exceeds plan limits"""
    try:
        from blu_staff.apps.notifications.utils import create_notification
        
        admins = User.objects.filter(
            company=subscription.company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        )
        
        for admin in admins:
            create_notification(
                recipient=admin,
                title='Usage Limit Exceeded',
                message=f'Your {metric_type} count ({current}) has exceeded your plan limit ({limit}). Consider upgrading your plan.',
                notification_type='WARNING',
                category='SYSTEM',
                link='/billing/',
                send_email=True,
                tenant=getattr(subscription.company, 'tenant', None)
            )
    except Exception:
        pass


def _has_valid_payment_method(company):
    """Check if company has a valid payment method on file"""
    if not hasattr(company, 'security_settings') or not company.security_settings:
        return False
    
    payment_method = company.security_settings.get('payment_method', {})
    return bool(payment_method.get('type'))
