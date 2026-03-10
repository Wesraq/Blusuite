# BluSuite User Onboarding Automation Setup Guide

## Overview
Comprehensive onboarding automation for companies and employees with progress tracking, automated notifications, and task management.

---

## Features Implemented

### 1. Company Onboarding

**Model:** `CompanyOnboarding` (`blu_core/onboarding_automation.py`)

**10-Step Setup Process:**
1. ✓ Company Information
2. ✓ Admin Account Setup
3. ✓ Settings Configuration
4. ✓ Add First Employee
5. ✓ Create Department
6. ✓ Configure Attendance
7. ✓ Set Leave Policies
8. ✓ Configure Payroll
9. ✓ Upload Documents
10. ✓ Setup Integrations

**Features:**
- Automatic progress tracking
- Completion percentage calculation
- Welcome emails to admins
- Completion notifications
- Step-by-step guidance

### 2. Employee Onboarding

**Existing Models:** `EmployeeOnboarding`, `OnboardingTask`, `OnboardingTaskCompletion`

**New Automation:**
- Auto-create onboarding on employee creation
- Welcome emails to new employees
- Task due date reminders
- Overdue task notifications
- Completion celebrations
- Buddy system support

### 3. Onboarding Reminders

**Model:** `OnboardingReminder`

**Reminder Types:**
- `WELCOME` — Welcome message
- `TASK_DUE` — Task due tomorrow
- `TASK_OVERDUE` — Task overdue
- `PROGRESS` — Progress updates
- `COMPLETION` — Onboarding complete

---

## Deployment Steps

### Step 1: Run Migration

```bash
cd /opt/blusuite
source venv/bin/activate
python manage.py migrate blu_core --settings=ems_project.settings_production
```

**Creates:**
- `blu_core_companyonboarding` table
- `blu_core_onboardingreminder` table

### Step 2: Initialize Company Onboarding

```bash
# Initialize all companies
python manage.py init_company_onboarding --settings=ems_project.settings_production

# Initialize specific company
python manage.py init_company_onboarding --company "Acme Corp" --settings=ems_project.settings_production
```

**Creates:**
- Company onboarding record for each company
- Default onboarding checklist if none exists
- Sends welcome emails to admins

### Step 3: Setup Automated Task Checking

**Create Cron Script:**
```bash
#!/bin/bash
# /opt/blusuite/scripts/cron_onboarding_check.sh

cd /opt/blusuite
source venv/bin/activate

python manage.py check_onboarding_tasks --settings=ems_project.settings_production >> /var/log/blusuite/onboarding_check.log 2>&1

deactivate
```

**Make Executable:**
```bash
chmod +x /opt/blusuite/scripts/cron_onboarding_check.sh
```

**Add to Crontab:**
```bash
crontab -e

# Check onboarding tasks daily at 9 AM
0 9 * * * /opt/blusuite/scripts/cron_onboarding_check.sh
```

---

## Usage Examples

### Company Onboarding

#### Start Company Onboarding

```python
from blu_core.onboarding_automation import start_company_onboarding

# On company registration
company = Company.objects.create(name='Acme Corp')
admin = User.objects.create(email='admin@acme.com', role='ADMINISTRATOR', company=company)

# Initialize onboarding
onboarding = start_company_onboarding(company, admin)
# Sends welcome email to admin
```

#### Update Onboarding Steps

```python
from blu_core.onboarding_automation import update_onboarding_step

# Mark step as complete
update_onboarding_step(company, 'company_info_complete', True)
update_onboarding_step(company, 'admin_account_complete', True)
update_onboarding_step(company, 'first_employee_added', True)

# When all steps complete, sends completion notification
```

#### Get Onboarding Progress

```python
from blu_core.onboarding_automation import get_onboarding_progress

progress = get_onboarding_progress(company)

print(f"Status: {progress['status']}")
print(f"Completion: {progress['percentage']}%")
print(f"Current Step: {progress['current_step']}")

for step in progress['steps']:
    status = '✓' if step['complete'] else '○'
    print(f"{status} {step['name']}")
```

**Output:**
```
Status: IN_PROGRESS
Completion: 40%
Current Step: 5
✓ Company Information
✓ Admin Account
✓ Settings Configuration
✓ Add First Employee
○ Create Department
○ Configure Attendance
○ Set Leave Policies
○ Configure Payroll
○ Upload Documents
○ Setup Integrations
```

### Employee Onboarding

#### Auto-Create on Employee Creation

```python
from blu_core.onboarding_automation import auto_create_employee_onboarding

# Create employee
employee = User.objects.create(
    email='john@acme.com',
    role='EMPLOYEE',
    company=company,
    date_hired=date.today()
)

# Auto-create onboarding
onboarding = auto_create_employee_onboarding(employee)
# Creates onboarding record
# Creates task completions
# Sends welcome email
```

#### Complete Onboarding Task

```python
from blu_core.onboarding_automation import complete_onboarding_task

task_completion = employee.onboarding.task_completions.first()

complete_onboarding_task(
    task_completion,
    completed_by=employee,
    notes='Completed personal information form'
)

# Marks task as complete
# If all tasks done, marks onboarding complete
# Sends completion notification
```

#### Get Employee Progress

```python
from blu_core.onboarding_automation import get_employee_onboarding_progress

progress = get_employee_onboarding_progress(employee)

print(f"Status: {progress['status']}")
print(f"Progress: {progress['completed_tasks']}/{progress['total_tasks']} tasks")
print(f"Percentage: {progress['percentage']}%")
print(f"Start Date: {progress['start_date']}")
print(f"Expected Completion: {progress['expected_completion']}")
if progress['buddy']:
    print(f"Buddy: {progress['buddy'].get_full_name()}")
```

### Create Default Checklist

```python
from blu_core.onboarding_automation import create_default_onboarding_checklist

# Create default checklist for company
checklist = create_default_onboarding_checklist(company)

# Creates 6 default tasks:
# 1. Complete personal information (1 day, HIGH)
# 2. Review company policies (3 days, HIGH)
# 3. Setup email and accounts (1 day, CRITICAL)
# 4. Meet your team (5 days, MEDIUM)
# 5. Complete training modules (14 days, HIGH)
# 6. Submit required documents (7 days, CRITICAL)
```

---

## Integration with Existing Code

### Signal Integration

**Auto-create onboarding on employee creation:**

```python
# blu_core/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from blu_core.onboarding_automation import auto_create_employee_onboarding

@receiver(post_save, sender=User)
def create_employee_onboarding(sender, instance, created, **kwargs):
    """Auto-create onboarding for new employees"""
    if created and instance.role == 'EMPLOYEE':
        auto_create_employee_onboarding(instance)
```

### View Integration

**Update company onboarding steps in views:**

```python
# ems_project/frontend_views.py

from blu_core.onboarding_automation import update_onboarding_step

@login_required
def add_employee(request):
    if request.method == 'POST':
        # Create employee
        employee = User.objects.create(...)
        
        # Update onboarding
        update_onboarding_step(request.user.company, 'first_employee_added', True)
        
        return redirect('employees_list')
```

### Dashboard Integration

**Show onboarding progress on dashboard:**

```python
# ems_project/frontend_views.py

from blu_core.onboarding_automation import get_onboarding_progress

@login_required
def dashboard(request):
    company = request.user.company
    
    # Get onboarding progress
    onboarding_progress = get_onboarding_progress(company)
    
    context = {
        'onboarding': onboarding_progress,
    }
    
    return render(request, 'dashboard.html', context)
```

**Template:**
```html
{% if onboarding and onboarding.status != 'COMPLETED' %}
<div class="onboarding-widget">
    <h3>Company Setup Progress</h3>
    <div class="progress-bar">
        <div class="progress" style="width: {{ onboarding.percentage }}%"></div>
    </div>
    <p>{{ onboarding.percentage }}% Complete</p>
    
    <h4>Next Steps:</h4>
    <ul>
        {% for step in onboarding.steps %}
            {% if not step.complete %}
                <li>{{ step.name }}</li>
            {% endif %}
        {% endfor %}
    </ul>
</div>
{% endif %}
```

---

## Automated Notifications

### Welcome Emails

**Company Welcome:**
- Sent when company onboarding starts
- Includes setup guide link
- Encourages completion

**Employee Welcome:**
- Sent when employee is created
- Includes onboarding checklist
- Introduces buddy (if assigned)

### Task Reminders

**Due Tomorrow:**
- Sent at 9 AM daily
- Lists tasks due tomorrow
- In-app notification only

**Overdue:**
- Sent at 9 AM daily
- Lists overdue tasks
- Email + in-app notification
- Only one reminder per day per task

### Completion Notifications

**Employee Onboarding Complete:**
- Sent when all tasks done
- Congratulations message
- Next steps guidance

**Company Onboarding Complete:**
- Sent when all setup steps done
- Sent to all admins
- Unlocks advanced features

---

## Customization

### Custom Onboarding Checklist

**Via Django Admin:**
1. Go to `/admin/onboarding/onboardingchecklist/`
2. Click "Add Onboarding Checklist"
3. Fill in:
   - Name: "Engineering Onboarding"
   - Description: "For software engineers"
   - Is Default: ✓ (if default for all employees)
   - Is Active: ✓
4. Save

**Add Tasks:**
1. Go to `/admin/onboarding/onboardingtask/`
2. Click "Add Onboarding Task"
3. Fill in:
   - Checklist: Select your checklist
   - Title: "Setup development environment"
   - Description: "Install IDE, Git, Docker"
   - Priority: HIGH
   - Order: 1
   - Days to Complete: 2
   - Assigned to Role: EMPLOYEE
4. Save

### Custom Company Onboarding Steps

**Add custom steps to CompanyOnboarding model:**

```python
# blu_core/onboarding_automation.py

class CompanyOnboarding(models.Model):
    # ... existing fields ...
    
    # Add custom step
    custom_integration_setup = models.BooleanField(default=False)
    
    @property
    def completion_percentage(self):
        steps = [
            # ... existing steps ...
            self.custom_integration_setup,
        ]
        completed = sum(steps)
        total = len(steps)
        return int((completed / total) * 100)
```

**Update in views:**
```python
update_onboarding_step(company, 'custom_integration_setup', True)
```

---

## Monitoring & Analytics

### Onboarding Metrics

```python
from blu_core.models import CompanyOnboarding
from blu_staff.apps.onboarding.models import EmployeeOnboarding
from django.db.models import Avg, Count

# Company onboarding stats
company_stats = CompanyOnboarding.objects.aggregate(
    total=Count('id'),
    completed=Count('id', filter=Q(status='COMPLETED')),
    avg_completion=Avg('completion_percentage')
)

print(f"Companies: {company_stats['total']}")
print(f"Completed: {company_stats['completed']}")
print(f"Avg Completion: {company_stats['avg_completion']:.1f}%")

# Employee onboarding stats
employee_stats = EmployeeOnboarding.objects.aggregate(
    total=Count('id'),
    completed=Count('id', filter=Q(status='COMPLETED')),
    in_progress=Count('id', filter=Q(status='IN_PROGRESS'))
)

print(f"Employees: {employee_stats['total']}")
print(f"Completed: {employee_stats['completed']}")
print(f"In Progress: {employee_stats['in_progress']}")
```

### Time to Completion

```python
from django.db.models import F, ExpressionWrapper, DurationField
from datetime import timedelta

# Average time to complete onboarding
completed = EmployeeOnboarding.objects.filter(
    status='COMPLETED',
    actual_completion_date__isnull=False
).annotate(
    duration=ExpressionWrapper(
        F('actual_completion_date') - F('start_date'),
        output_field=DurationField()
    )
)

avg_days = completed.aggregate(
    avg_duration=Avg('duration')
)['avg_duration']

if avg_days:
    print(f"Average time to complete: {avg_days.days} days")
```

### Bottleneck Identification

```python
from blu_staff.apps.onboarding.models import OnboardingTaskCompletion

# Find tasks with low completion rate
task_stats = OnboardingTaskCompletion.objects.values(
    'task__title'
).annotate(
    total=Count('id'),
    completed=Count('id', filter=Q(status='COMPLETED')),
    completion_rate=Count('id', filter=Q(status='COMPLETED')) * 100.0 / Count('id')
).order_by('completion_rate')

print("Tasks with lowest completion rates:")
for stat in task_stats[:5]:
    print(f"{stat['task__title']}: {stat['completion_rate']:.1f}%")
```

---

## Troubleshooting

### Onboarding Not Created

**Problem:** Employee created but no onboarding

**Solution:**
```python
# Manually create onboarding
from blu_core.onboarding_automation import auto_create_employee_onboarding

employee = User.objects.get(email='john@acme.com')
onboarding = auto_create_employee_onboarding(employee)
```

### Reminders Not Sending

**Problem:** No reminder emails

**Solution:**
```bash
# Check cron is running
crontab -l

# Run manually
python manage.py check_onboarding_tasks

# Check email settings
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test', 'from@example.com', ['to@example.com'])
```

### Progress Not Updating

**Problem:** Onboarding percentage stuck

**Solution:**
```python
# Recalculate progress
onboarding = CompanyOnboarding.objects.get(company=company)
print(f"Current: {onboarding.completion_percentage}%")

# Check individual steps
print(f"Company Info: {onboarding.company_info_complete}")
print(f"Admin Account: {onboarding.admin_account_complete}")
# ... etc

# Update manually if needed
onboarding.first_employee_added = True
onboarding.save()
```

---

## Best Practices

### 1. Assign Buddies

```python
# Assign experienced employee as buddy
buddy = User.objects.filter(
    company=company,
    role='EMPLOYEE',
    date_hired__lt=date.today() - timedelta(days=90)
).first()

employee.onboarding.buddy = buddy
employee.onboarding.save()
```

### 2. Customize Checklists by Role

```python
# Different checklists for different roles
if employee.role == 'ENGINEER':
    checklist = OnboardingChecklist.objects.get(name='Engineering Onboarding')
elif employee.role == 'SALES':
    checklist = OnboardingChecklist.objects.get(name='Sales Onboarding')
else:
    checklist = OnboardingChecklist.objects.get(is_default=True)

employee.onboarding.checklist = checklist
employee.onboarding.save()
```

### 3. Track Completion Time

```python
# Set realistic expectations
if employee.role == 'SENIOR':
    days = 14  # Shorter for experienced
else:
    days = 30  # Standard for new hires

employee.onboarding.expected_completion_date = employee.date_hired + timedelta(days=days)
employee.onboarding.save()
```

### 4. Regular Progress Reviews

```python
# Weekly review of onboarding progress
incomplete = EmployeeOnboarding.objects.filter(
    status='IN_PROGRESS',
    start_date__lt=date.today() - timedelta(days=7)
)

for onboarding in incomplete:
    progress = get_employee_onboarding_progress(onboarding.employee)
    if progress['percentage'] < 50:
        # Alert manager
        notify_manager(onboarding.employee, progress)
```

---

**Document Version:** 1.0  
**Last Updated:** March 10, 2026  
**Next Review:** June 10, 2026
