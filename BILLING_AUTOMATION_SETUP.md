# BluSuite Billing Automation Setup Guide

## Overview
Automated billing system for subscription management, invoice generation, trial handling, and usage tracking.

## Components Created

### 1. Billing Automation Engine
**File:** `blu_billing/billing_automation.py`

**Functions:**
- `generate_monthly_invoices()` — Auto-generate invoices for active subscriptions
- `process_trial_expirations()` — Convert trials to paid or suspend
- `send_trial_expiry_warnings()` — Notify 7, 3, 1 days before trial ends
- `process_overdue_invoices()` — Mark overdue, suspend after grace period
- `update_usage_metrics()` — Track user counts, storage, API calls

### 2. Management Command
**File:** `blu_billing/management/commands/run_billing_automation.py`

**Usage:**
```bash
# Run all tasks
python manage.py run_billing_automation

# Run specific task
python manage.py run_billing_automation --task=invoices
python manage.py run_billing_automation --task=trials
python manage.py run_billing_automation --task=warnings
python manage.py run_billing_automation --task=overdue
python manage.py run_billing_automation --task=usage
```

### 3. Cron Script
**File:** `blu_billing/cron_billing.sh`

## Deployment Steps

### Step 1: Upload Files to Server
```bash
# On server console or via scp
cd /opt/blusuite

# Create directories
mkdir -p blu_billing/management/commands

# Upload files (if using wget from GitHub after commit)
wget https://raw.githubusercontent.com/Wesraq/Blusuite/master/blu_billing/billing_automation.py -O blu_billing/billing_automation.py
wget https://raw.githubusercontent.com/Wesraq/Blusuite/master/blu_billing/management/commands/run_billing_automation.py -O blu_billing/management/commands/run_billing_automation.py
wget https://raw.githubusercontent.com/Wesraq/Blusuite/master/blu_billing/cron_billing.sh -O blu_billing/cron_billing.sh

# Create __init__.py files
touch blu_billing/management/__init__.py
touch blu_billing/management/commands/__init__.py

# Make cron script executable
chmod +x blu_billing/cron_billing.sh
```

### Step 2: Test Management Command
```bash
source venv/bin/activate
python manage.py run_billing_automation --settings=ems_project.settings_production
```

### Step 3: Setup Cron Job
```bash
# Create log directory
mkdir -p /var/log/blusuite

# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM UTC)
0 2 * * * /opt/blusuite/blu_billing/cron_billing.sh

# Verify cron job
crontab -l
```

### Step 4: Monitor Logs
```bash
# View billing automation logs
tail -f /var/log/blusuite/billing_automation.log

# Check for errors
grep -i error /var/log/blusuite/billing_automation.log
```

## Automation Schedule

| Task | Frequency | Time (UTC) | Purpose |
|------|-----------|------------|---------|
| Generate Invoices | Daily | 2:00 AM | Bill active subscriptions |
| Process Trials | Daily | 2:00 AM | Convert or suspend expired trials |
| Trial Warnings | Daily | 2:00 AM | Notify 7, 3, 1 days before expiry |
| Overdue Invoices | Daily | 2:00 AM | Mark overdue, suspend after grace period |
| Usage Metrics | Daily | 2:00 AM | Track user counts, storage, API calls |

## Notifications Sent

### Trial Expiring
- **Recipients:** Company admins
- **Timing:** 7, 3, 1 days before expiry
- **Action:** Prompt to add payment method

### Trial Converted
- **Recipients:** Company admins
- **Timing:** When trial ends with payment method
- **Action:** Confirm active subscription, first invoice generated

### Trial Expired (No Payment)
- **Recipients:** Company admins
- **Timing:** When trial ends without payment method
- **Action:** Subscription suspended, prompt to add payment

### Invoice Generated
- **Recipients:** Company admins
- **Timing:** When monthly/yearly invoice is created
- **Action:** View invoice, make payment

### Invoice Overdue
- **Recipients:** Company admins
- **Timing:** When invoice passes due date
- **Action:** Urgent payment request

### Subscription Suspended
- **Recipients:** Company admins
- **Timing:** 7 days after invoice overdue
- **Action:** Service suspended, immediate payment required

### Usage Exceeded
- **Recipients:** Company admins
- **Timing:** When user count exceeds plan limit
- **Action:** Suggest plan upgrade

## Grace Period Policy

- **Trial Period:** 14 days (configurable in Company model)
- **Invoice Due:** 30 days from issue date
- **Grace Period:** 7 days after due date before suspension
- **Total Time:** 37 days from invoice generation to suspension

## Manual Operations

### Manually Generate Invoice
```python
from blu_billing.models import CompanySubscription, Invoice
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

subscription = CompanySubscription.objects.get(company__name="Example Corp")
amount = subscription.plan.get_price_for_cycle(subscription.billing_cycle)
tax_amount = amount * Decimal('0.10')

Invoice.objects.create(
    company=subscription.company,
    subscription=subscription,
    amount=amount,
    tax_amount=tax_amount,
    total_amount=amount + tax_amount,
    issue_date=timezone.now(),
    due_date=timezone.now() + timedelta(days=30),
    status='PENDING'
)
```

### Manually Suspend Subscription
```python
subscription = CompanySubscription.objects.get(company__name="Example Corp")
subscription.status = 'SUSPENDED'
subscription.save()
```

### Manually Reactivate Subscription
```python
subscription = CompanySubscription.objects.get(company__name="Example Corp")
subscription.status = 'ACTIVE'
subscription.current_period_start = timezone.now()
subscription.current_period_end = timezone.now() + timedelta(days=30)
subscription.next_billing_date = subscription.current_period_end
subscription.save()
```

## Troubleshooting

### Cron Job Not Running
```bash
# Check cron service
systemctl status cron

# Check cron logs
grep CRON /var/log/syslog

# Verify script permissions
ls -la /opt/blusuite/blu_billing/cron_billing.sh
```

### No Invoices Generated
```bash
# Check for subscriptions due for billing
python manage.py shell
>>> from blu_billing.models import CompanySubscription
>>> from django.utils import timezone
>>> CompanySubscription.objects.filter(status='ACTIVE', next_billing_date__lte=timezone.now())
```

### Notifications Not Sending
```bash
# Check notification app is installed
python manage.py shell
>>> from blu_staff.apps.notifications.utils import create_notification
>>> # If ImportError, check INSTALLED_APPS in settings.py
```

## Future Enhancements

1. **Stripe Recurring Billing Integration**
   - Auto-charge cards on file
   - Handle webhook events (payment_succeeded, payment_failed)
   - Update invoice status automatically

2. **Usage-Based Billing**
   - Charge overage fees for exceeding limits
   - Tiered pricing based on usage

3. **Dunning Management**
   - Retry failed payments
   - Escalating notification sequence
   - Automatic downgrade to lower plan

4. **Revenue Recognition**
   - Deferred revenue tracking
   - Proration for mid-cycle upgrades/downgrades

5. **Multi-Currency Support**
   - Regional pricing
   - Currency conversion
   - Local payment methods

## Compliance Notes

- All billing actions are logged in AuditLog (Muscle 3)
- Invoice numbers are auto-generated and unique
- Payment records are immutable once created
- Subscription status changes are tracked with timestamps
- Usage metrics provide audit trail for billing disputes
