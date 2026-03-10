# BluSuite Advanced Reporting & Analytics Setup Guide

## Overview
Comprehensive business intelligence with company-wide analytics, metric tracking, trend analysis, and automated reporting.

---

## Features Implemented

### 1. Company Analytics

**Model:** `CompanyAnalytics` (`blu_core/advanced_analytics.py`)

**Metrics Tracked:**

**Employee Metrics:**
- Total employees
- Active employees
- New hires this month
- Terminations this month
- Turnover rate (%)

**Attendance Metrics:**
- Average attendance rate (%)
- Total absences
- Total late arrivals

**Leave Metrics:**
- Total leave requests
- Approved leaves
- Pending leaves
- Total leave days taken

**Payroll Metrics:**
- Total payroll cost
- Average salary
- Total overtime hours
- Total overtime cost

**Performance Metrics:**
- Average performance score
- Pending reviews
- Completed reviews

**Training Metrics:**
- Total training hours
- Employees in training
- Training completion rate (%)

**Document Metrics:**
- Total documents
- Pending approvals
- Expired documents

**Onboarding Metrics:**
- Active onboardings
- Completed onboardings
- Average onboarding days

**System Metrics:**
- Total storage used (MB)
- Active users (last 30 days)

### 2. Analytics Reports

**Model:** `AnalyticsReport`

**Report Types:**
- Company Overview
- HR Metrics
- Payroll Summary
- Attendance Report
- Leave Analysis
- Performance Review
- Training Report
- Turnover Analysis
- Custom Reports

**Export Formats:**
- PDF
- Excel
- CSV
- JSON

**Features:**
- Date range filtering
- Custom filters (JSON)
- Scheduled generation (daily, weekly, monthly)
- Email distribution
- Status tracking

### 3. Metric Trends

**Model:** `MetricTrend`

**Features:**
- Track any metric over time
- Automatic change calculation
- Percentage change tracking
- Trend analysis
- Historical data

---

## Deployment Steps

### Step 1: Run Migration

```bash
cd /opt/blusuite
source venv/bin/activate
python manage.py migrate blu_core --settings=ems_project.settings_production
```

**Creates:**
- `blu_core_companyanalytics` table
- `blu_core_analyticsreport` table
- `blu_core_metrictrend` table

### Step 2: Calculate Initial Analytics

```bash
# Calculate for all companies
python manage.py calculate_analytics --settings=ems_project.settings_production

# Calculate for specific company
python manage.py calculate_analytics --company "Acme Corp" --settings=ems_project.settings_production

# Calculate for specific date
python manage.py calculate_analytics --date 2026-03-01 --settings=ems_project.settings_production
```

### Step 3: Setup Automated Analytics

**Create Cron Script:**
```bash
#!/bin/bash
# /opt/blusuite/scripts/cron_analytics.sh

cd /opt/blusuite
source venv/bin/activate

python manage.py calculate_analytics --settings=ems_project.settings_production >> /var/log/blusuite/analytics.log 2>&1

deactivate
```

**Make Executable:**
```bash
chmod +x /opt/blusuite/scripts/cron_analytics.sh
```

**Add to Crontab:**
```bash
crontab -e

# Calculate analytics daily at midnight
0 0 * * * /opt/blusuite/scripts/cron_analytics.sh
```

---

## Usage Examples

### Calculate Company Analytics

```python
from blu_core.advanced_analytics import calculate_company_analytics
from datetime import date

# Calculate for today
analytics = calculate_company_analytics(company)

# Calculate for specific date
analytics = calculate_company_analytics(company, date(2026, 3, 1))

# Access metrics
print(f"Total Employees: {analytics.total_employees}")
print(f"Turnover Rate: {analytics.turnover_rate}%")
print(f"Attendance Rate: {analytics.average_attendance_rate}%")
print(f"Total Payroll: ${analytics.total_payroll_cost}")
```

### Track Metric Trends

```python
from blu_core.advanced_analytics import track_metric_trend

# Track a metric
track_metric_trend(
    company=company,
    metric_name='employee_count',
    metric_category='HR',
    value=150
)

# Track with specific date
track_metric_trend(
    company=company,
    metric_name='turnover_rate',
    metric_category='HR',
    value=5.2,
    date=date(2026, 3, 1)
)
```

### Get Metric Trends

```python
from blu_core.advanced_analytics import get_metric_trends

# Get last 30 days
trends = get_metric_trends(company, 'employee_count', days=30)

for trend in trends:
    print(f"{trend['date']}: {trend['value']} ({trend['change_percentage']:+.2f}%)")
```

**Output:**
```
2026-02-10: 145 (+2.11%)
2026-02-11: 145 (0.00%)
2026-02-12: 147 (+1.38%)
...
2026-03-10: 150 (+0.67%)
```

### Generate Company Overview Report

```python
from blu_core.advanced_analytics import generate_company_overview_report
from datetime import date

report_data = generate_company_overview_report(
    company=company,
    date_from=date(2026, 2, 1),
    date_to=date(2026, 2, 28)
)

print(report_data['summary'])
# {
#     'total_employees': 150,
#     'active_employees': 148,
#     'turnover_rate': 5.2,
#     'attendance_rate': 96.5,
#     'total_payroll': 450000.00,
#     'average_salary': 3000.00
# }

print(report_data['changes'])
# {
#     'employee_growth': 5,
#     'new_hires': 8,
#     'terminations': 3
# }
```

### Predictive Analytics

```python
from blu_core.advanced_analytics import calculate_predictive_metrics

predictions = calculate_predictive_metrics(company)

print(f"Predicted Turnover Next Month: {predictions['turnover_forecast_next_month']:.2f}%")
```

---

## Viewing Analytics

### Django Admin

**Company Analytics:**
1. Go to `/admin/blu_core/companyanalytics/`
2. Filter by company or date
3. View all metrics in organized fieldsets

**Analytics Reports:**
1. Go to `/admin/blu_core/analyticsreport/`
2. View generated reports
3. Download files
4. Check status and errors

**Metric Trends:**
1. Go to `/admin/blu_core/metrictrend/`
2. Filter by metric name or category
3. View trends and changes

### Programmatic Access

```python
from blu_core.models import CompanyAnalytics, MetricTrend

# Get latest analytics
latest = CompanyAnalytics.objects.filter(company=company).first()

# Get all analytics for a month
from datetime import date
month_analytics = CompanyAnalytics.objects.filter(
    company=company,
    snapshot_date__year=2026,
    snapshot_date__month=3
)

# Get metric trends
trends = MetricTrend.objects.filter(
    company=company,
    metric_name='employee_count'
).order_by('-date')[:30]
```

---

## Dashboard Integration

### Display Key Metrics

```python
# views.py
from blu_core.models import CompanyAnalytics

@login_required
def dashboard(request):
    company = request.user.company
    
    # Get latest analytics
    analytics = CompanyAnalytics.objects.filter(company=company).first()
    
    context = {
        'analytics': analytics,
    }
    
    return render(request, 'dashboard.html', context)
```

**Template:**
```html
{% if analytics %}
<div class="analytics-dashboard">
    <div class="metric-card">
        <h3>Employees</h3>
        <div class="value">{{ analytics.total_employees }}</div>
        <div class="sub">{{ analytics.active_employees }} active</div>
    </div>
    
    <div class="metric-card">
        <h3>Turnover Rate</h3>
        <div class="value">{{ analytics.turnover_rate }}%</div>
        <div class="sub">{{ analytics.new_hires_this_month }} hires, {{ analytics.terminations_this_month }} exits</div>
    </div>
    
    <div class="metric-card">
        <h3>Attendance</h3>
        <div class="value">{{ analytics.average_attendance_rate }}%</div>
        <div class="sub">{{ analytics.total_absences }} absences</div>
    </div>
    
    <div class="metric-card">
        <h3>Payroll</h3>
        <div class="value">${{ analytics.total_payroll_cost|floatformat:2 }}</div>
        <div class="sub">Avg: ${{ analytics.average_salary|floatformat:2 }}</div>
    </div>
</div>
{% endif %}
```

### Display Trends Chart

```python
# views.py
from blu_core.advanced_analytics import get_metric_trends
import json

@login_required
def analytics_dashboard(request):
    company = request.user.company
    
    # Get employee count trend
    employee_trends = get_metric_trends(company, 'employee_count', days=30)
    
    context = {
        'employee_trends_json': json.dumps(employee_trends),
    }
    
    return render(request, 'analytics.html', context)
```

**Template (with Chart.js):**
```html
<canvas id="employeeTrendChart"></canvas>

<script>
const trends = {{ employee_trends_json|safe }};
const dates = trends.map(t => t.date);
const values = trends.map(t => t.value);

new Chart(document.getElementById('employeeTrendChart'), {
    type: 'line',
    data: {
        labels: dates,
        datasets: [{
            label: 'Employee Count',
            data: values,
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
        }]
    }
});
</script>
```

---

## Scheduled Reports

### Create Scheduled Report

```python
from blu_core.models import AnalyticsReport
from datetime import date, timedelta

# Create monthly payroll report
report = AnalyticsReport.objects.create(
    company=company,
    report_type='PAYROLL_SUMMARY',
    title='Monthly Payroll Report',
    description='Comprehensive payroll summary',
    date_from=date(2026, 3, 1),
    date_to=date(2026, 3, 31),
    format='PDF',
    is_scheduled=True,
    schedule_frequency='MONTHLY',
    next_run_date=date(2026, 4, 1),
    generated_by=user
)

# Add recipients
report.recipients.add(hr_manager, finance_manager)
```

### Generate Report

```python
from blu_core.advanced_analytics import generate_company_overview_report
import json

# Generate report data
report_data = generate_company_overview_report(
    company=report.company,
    date_from=report.date_from,
    date_to=report.date_to
)

# Update report
report.status = 'COMPLETED'
report.generated_at = timezone.now()

# Save data
if report.format == 'JSON':
    report.file_path = f'/reports/{report.id}.json'
    with open(report.file_path, 'w') as f:
        json.dump(report_data, f, indent=2)

report.save()

# Send email to recipients
if report.recipients.exists():
    send_report_email(report)
```

---

## Custom Metrics

### Track Custom Metrics

```python
from blu_core.advanced_analytics import track_metric_trend

# Track customer satisfaction
track_metric_trend(
    company=company,
    metric_name='customer_satisfaction',
    metric_category='QUALITY',
    value=4.5
)

# Track project completion rate
track_metric_trend(
    company=company,
    metric_name='project_completion_rate',
    metric_category='PROJECTS',
    value=92.3
)

# Track revenue
track_metric_trend(
    company=company,
    metric_name='monthly_revenue',
    metric_category='FINANCIAL',
    value=125000.50
)
```

### Query Custom Metrics

```python
from blu_core.models import MetricTrend

# Get all financial metrics
financial_metrics = MetricTrend.objects.filter(
    company=company,
    metric_category='FINANCIAL'
).order_by('-date')

# Get specific metric
revenue_trends = MetricTrend.objects.filter(
    company=company,
    metric_name='monthly_revenue'
).order_by('-date')[:12]  # Last 12 months
```

---

## Analytics API

### Create Analytics Endpoint

```python
# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from blu_core.models import CompanyAnalytics
from blu_core.advanced_analytics import get_metric_trends

@api_view(['GET'])
def company_analytics_api(request):
    company = request.user.company
    
    # Get latest analytics
    analytics = CompanyAnalytics.objects.filter(company=company).first()
    
    if not analytics:
        return Response({'error': 'No analytics data'}, status=404)
    
    data = {
        'snapshot_date': analytics.snapshot_date,
        'employees': {
            'total': analytics.total_employees,
            'active': analytics.active_employees,
            'new_hires': analytics.new_hires_this_month,
            'terminations': analytics.terminations_this_month,
            'turnover_rate': float(analytics.turnover_rate),
        },
        'attendance': {
            'rate': float(analytics.average_attendance_rate),
            'absences': analytics.total_absences,
            'late_arrivals': analytics.total_late_arrivals,
        },
        'payroll': {
            'total_cost': float(analytics.total_payroll_cost),
            'average_salary': float(analytics.average_salary),
            'overtime_hours': float(analytics.total_overtime_hours),
            'overtime_cost': float(analytics.total_overtime_cost),
        },
    }
    
    return Response(data)


@api_view(['GET'])
def metric_trends_api(request, metric_name):
    company = request.user.company
    days = int(request.GET.get('days', 30))
    
    trends = get_metric_trends(company, metric_name, days)
    
    return Response(trends)
```

---

## Best Practices

### 1. Regular Snapshots

```bash
# Daily snapshots at midnight
0 0 * * * /opt/blusuite/scripts/cron_analytics.sh

# Weekly deep analysis on Sundays
0 1 * * 0 /opt/blusuite/scripts/weekly_analytics.sh
```

### 2. Trend Tracking

```python
# Track key metrics daily
from blu_core.advanced_analytics import track_metric_trend, calculate_company_analytics

# Calculate analytics
analytics = calculate_company_analytics(company)

# Track important trends
track_metric_trend(company, 'employee_count', 'HR', analytics.total_employees)
track_metric_trend(company, 'turnover_rate', 'HR', analytics.turnover_rate)
track_metric_trend(company, 'attendance_rate', 'ATTENDANCE', analytics.average_attendance_rate)
```

### 3. Alert on Anomalies

```python
from blu_core.models import MetricTrend

# Check for significant changes
recent_turnover = MetricTrend.objects.filter(
    company=company,
    metric_name='turnover_rate'
).order_by('-date').first()

if recent_turnover and recent_turnover.change_percentage > 20:
    # Alert management
    send_alert(f"Turnover rate increased by {recent_turnover.change_percentage}%")
```

### 4. Data Retention

```python
# Cleanup old analytics (keep 2 years)
from datetime import date, timedelta
from blu_core.models import CompanyAnalytics

cutoff_date = date.today() - timedelta(days=730)

CompanyAnalytics.objects.filter(
    snapshot_date__lt=cutoff_date
).delete()
```

---

## Troubleshooting

### Analytics Not Calculating

**Problem:** No analytics data

**Solution:**
```bash
# Run manually
python manage.py calculate_analytics --company "Your Company"

# Check for errors
python manage.py calculate_analytics --company "Your Company" --verbosity 2
```

### Missing Metrics

**Problem:** Some metrics are 0

**Solution:**
```python
# Check if related data exists
from blu_staff.apps.attendance.models import Attendance

attendance_count = Attendance.objects.filter(
    employee__company=company
).count()

if attendance_count == 0:
    print("No attendance data - metrics will be 0")
```

### Trends Not Updating

**Problem:** Metric trends not showing changes

**Solution:**
```python
# Manually track metric
from blu_core.advanced_analytics import track_metric_trend

track_metric_trend(
    company=company,
    metric_name='employee_count',
    metric_category='HR',
    value=150
)

# Verify
from blu_core.models import MetricTrend
trends = MetricTrend.objects.filter(
    company=company,
    metric_name='employee_count'
)
print(f"Found {trends.count()} trend records")
```

---

## Performance Optimization

### 1. Index Usage

All analytics models have proper indexes for fast queries:
- Company + date indexes
- Metric name + date indexes
- Status + scheduling indexes

### 2. Batch Processing

```python
# Calculate for multiple companies efficiently
from blu_staff.apps.accounts.models import Company
from blu_core.advanced_analytics import calculate_company_analytics

companies = Company.objects.all()

for company in companies:
    try:
        calculate_company_analytics(company)
    except Exception as e:
        print(f"Error for {company.name}: {e}")
```

### 3. Caching

```python
from django.core.cache import cache

def get_cached_analytics(company):
    cache_key = f'analytics_{company.id}_{date.today()}'
    
    analytics = cache.get(cache_key)
    
    if not analytics:
        analytics = CompanyAnalytics.objects.filter(
            company=company
        ).first()
        cache.set(cache_key, analytics, 3600)  # Cache for 1 hour
    
    return analytics
```

---

**Document Version:** 1.0  
**Last Updated:** March 10, 2026  
**Next Review:** June 10, 2026
