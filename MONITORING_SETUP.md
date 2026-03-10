# BluSuite System Monitoring Setup Guide

## Overview
Comprehensive system monitoring with metrics collection, health checks, alerting, and historical tracking.

---

## Components

### 1. Monitoring Models

**File:** `blu_core/monitoring.py`

**Models:**
- `SystemMetric` — CPU, memory, disk, response time, error rate tracking
- `HealthCheckResult` — Database, cache, application health status
- `AlertRule` — Configurable alerting thresholds
- `Alert` — Triggered alerts with acknowledgment tracking

### 2. Management Commands

**Collect Metrics:**
```bash
python manage.py collect_metrics
python manage.py collect_metrics --cleanup  # Also cleanup old data
```

**Setup Default Alerts:**
```bash
python manage.py setup_default_alerts
```

### 3. Automated Collection

**Cron Script:** `scripts/cron_monitoring.sh`

**Schedule:**
- Every 5 minutes: Collect metrics and run health checks
- Weekly (Sundays): Cleanup old data

---

## Deployment Steps

### Step 1: Run Migration

```bash
cd /opt/blusuite
source venv/bin/activate
python manage.py migrate blu_core --settings=ems_project.settings_production
```

### Step 2: Setup Default Alert Rules

```bash
python manage.py setup_default_alerts --settings=ems_project.settings_production
```

**Default Rules Created:**
- High CPU Usage (80%, WARNING)
- Critical CPU Usage (95%, CRITICAL)
- High Memory Usage (85%, WARNING)
- Critical Memory Usage (95%, CRITICAL)
- High Disk Usage (85%, WARNING)
- Critical Disk Usage (95%, CRITICAL)

### Step 3: Test Metric Collection

```bash
python manage.py collect_metrics --settings=ems_project.settings_production
```

**Expected Output:**
```
=== Metric Collection Started: 2026-03-10 14:00:00 ===

Collecting system metrics...
  ✓ Collected 4 metrics

Running health checks...
  ✓ Completed 3 checks (3 healthy)
    - Database: HEALTHY (15ms)
    - Cache: HEALTHY (2ms)
    - Application: HEALTHY (45ms)

Checking alert rules...
  ✓ No alerts triggered

=== Metric Collection Completed ===
```

### Step 4: Setup Cron Job

```bash
# Make script executable
chmod +x /opt/blusuite/scripts/cron_monitoring.sh

# Edit crontab
crontab -e

# Add this line (runs every 5 minutes)
*/5 * * * * /opt/blusuite/scripts/cron_monitoring.sh
```

### Step 5: Verify Cron Job

```bash
# Check cron is running
systemctl status cron

# View monitoring logs
tail -f /var/log/blusuite/monitoring.log

# Check metrics in database
python manage.py shell
>>> from blu_core.models import SystemMetric
>>> SystemMetric.objects.count()
>>> SystemMetric.objects.filter(metric_type='CPU').latest('timestamp')
```

---

## Monitoring Dashboard

### SuperAdmin Access

**URL:** `/system-health/`

**Features:**
- Real-time system metrics (CPU, memory, disk)
- Database statistics
- API endpoint health checks
- Recent system events
- Active alerts

### Admin Interface

**URL:** `/admin/blu_core/`

**Models:**
- `SystemMetric` — View historical metrics
- `HealthCheckResult` — View health check history
- `AlertRule` — Configure alert thresholds
- `Alert` — View and acknowledge alerts

---

## Alert Configuration

### Default Alert Rules

| Alert | Metric | Threshold | Duration | Severity | Cooldown |
|-------|--------|-----------|----------|----------|----------|
| High CPU Usage | CPU | 80% | 5 min | WARNING | 30 min |
| Critical CPU Usage | CPU | 95% | 2 min | CRITICAL | 15 min |
| High Memory Usage | MEMORY | 85% | 5 min | WARNING | 30 min |
| Critical Memory Usage | MEMORY | 95% | 2 min | CRITICAL | 15 min |
| High Disk Usage | DISK | 85% | 10 min | WARNING | 60 min |
| Critical Disk Usage | DISK | 95% | 5 min | CRITICAL | 30 min |

### Creating Custom Alert Rules

**Via Django Admin:**
1. Go to `/admin/blu_core/alertrule/`
2. Click "Add Alert Rule"
3. Configure:
   - Name: Descriptive name
   - Metric Type: CPU, MEMORY, DISK, etc.
   - Threshold: Value to trigger alert
   - Duration: How long threshold must be exceeded
   - Severity: INFO, WARNING, or CRITICAL
   - Cooldown: Minimum time between alerts

**Via Django Shell:**
```python
from blu_core.models import AlertRule, SystemMetric

AlertRule.objects.create(
    name='Very High Memory Usage',
    metric_type=SystemMetric.MetricType.MEMORY,
    threshold=90.0,
    duration_minutes=3,
    severity=AlertRule.Severity.CRITICAL,
    cooldown_minutes=20
)
```

---

## Alert Notifications

### Notification Behavior

**WARNING Alerts:**
- In-app notification to all superadmins
- No email sent

**CRITICAL Alerts:**
- In-app notification to all superadmins
- Email sent to all superadmins
- Immediate attention required

### Acknowledging Alerts

**Via Django Admin:**
1. Go to `/admin/blu_core/alert/`
2. Select alert
3. Set "Acknowledged at" to current time
4. Set "Acknowledged by" to your user
5. Save

**Via Django Shell:**
```python
from blu_core.models import Alert
from django.utils import timezone

alert = Alert.objects.filter(resolved_at__isnull=True).first()
alert.acknowledged_at = timezone.now()
alert.acknowledged_by = request.user
alert.save()
```

### Resolving Alerts

```python
alert.resolved_at = timezone.now()
alert.save()
```

---

## Metrics Collected

### System Metrics (Every 5 Minutes)

| Metric | Description | Unit |
|--------|-------------|------|
| CPU | CPU usage percentage | % |
| MEMORY | Memory usage percentage | % |
| DISK | Disk usage percentage | % |
| ACTIVE_SESSIONS | Number of active users | count |

### Health Checks (Every 5 Minutes)

| Check | Description | Threshold |
|-------|-------------|-----------|
| Database | PostgreSQL connection and query | < 100ms = HEALTHY |
| Cache | Redis/Cache availability | < 50ms = HEALTHY |
| Application | Django application response | < 100ms = HEALTHY |

---

## Data Retention

### Automatic Cleanup

**Metrics:**
- Retention: 30 days
- Cleanup: Weekly (Sundays)

**Health Checks:**
- Retention: 7 days
- Cleanup: Weekly (Sundays)

**Alerts:**
- Never deleted automatically
- Manual cleanup recommended quarterly

### Manual Cleanup

```bash
# Cleanup old metrics (30 days)
python manage.py shell
>>> from blu_core.monitoring import cleanup_old_metrics
>>> cleanup_old_metrics(days=30)

# Cleanup old health checks (7 days)
>>> from blu_core.monitoring import cleanup_old_health_checks
>>> cleanup_old_health_checks(days=7)
```

---

## Monitoring API

### Get System Status

```python
from blu_core.monitoring import get_system_status

status = get_system_status()
print(status)
# {
#     'overall_status': 'HEALTHY',
#     'metrics': {'CPU': 45.2, 'MEMORY': 62.1, 'DISK': 38.5},
#     'health_checks': {
#         'Database': {'status': 'HEALTHY', 'response_time_ms': 15},
#         'Cache': {'status': 'HEALTHY', 'response_time_ms': 2}
#     },
#     'active_alerts': 0,
#     'timestamp': datetime(2026, 3, 10, 14, 0, 0)
# }
```

### Collect Metrics Programmatically

```python
from blu_core.monitoring import collect_system_metrics, run_health_checks

# Collect metrics
metrics_count = collect_system_metrics()

# Run health checks
health_checks = run_health_checks()

# Check alert rules
from blu_core.monitoring import check_alert_rules
alerts = check_alert_rules()
```

---

## Integration with External Monitoring

### Sentry (Error Tracking)

Already configured in `settings_production.py`:

```python
# Set in .env
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

### Uptime Monitoring (UptimeRobot, Pingdom)

**Health Check Endpoint:**
```
https://161.35.192.144/health/
```

**Expected Response:**
```json
{
  "DatabaseBackend": "working",
  "CacheBackend": "working",
  "StorageHealthCheck": "working"
}
```

### Prometheus (Optional)

Install `django-prometheus`:
```bash
pip install django-prometheus
```

Add to `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    'django_prometheus',
    # ... other apps
]
```

Add to `urls.py`:
```python
urlpatterns = [
    path('', include('django_prometheus.urls')),
    # ... other urls
]
```

Metrics endpoint: `/metrics`

---

## Troubleshooting

### No Metrics Being Collected

```bash
# Check cron job is running
crontab -l

# Check cron logs
grep CRON /var/log/syslog

# Manually run collection
python manage.py collect_metrics --settings=ems_project.settings_production

# Check for errors
tail -f /var/log/blusuite/monitoring.log
```

### psutil Not Installed

```bash
source venv/bin/activate
pip install psutil
```

### Alerts Not Triggering

```bash
# Check alert rules are active
python manage.py shell
>>> from blu_core.models import AlertRule
>>> AlertRule.objects.filter(is_active=True)

# Check recent metrics
>>> from blu_core.models import SystemMetric
>>> SystemMetric.objects.filter(metric_type='CPU').order_by('-timestamp')[:10]

# Manually check rules
>>> from blu_core.monitoring import check_alert_rules
>>> check_alert_rules()
```

### High Disk Usage from Metrics

```bash
# Check database size
sudo -u postgres psql -c "SELECT pg_size_pretty(pg_database_size('blusuite_db'));"

# Cleanup old metrics
python manage.py collect_metrics --cleanup --settings=ems_project.settings_production
```

---

## Performance Impact

### Resource Usage

**Metric Collection (every 5 minutes):**
- CPU: < 1% for ~2 seconds
- Memory: ~10MB temporary
- Disk I/O: ~1KB per metric
- Database: 4-6 INSERT queries

**Storage Growth:**
- ~1,700 metrics/day (4 metrics × 12 times/hour × 24 hours)
- ~50KB/day uncompressed
- ~1.5MB/month
- ~18MB/year (with 30-day retention, ~1.5MB steady state)

### Optimization Tips

1. **Reduce Collection Frequency:**
   ```bash
   # Change from */5 to */10 (every 10 minutes)
   */10 * * * * /opt/blusuite/scripts/cron_monitoring.sh
   ```

2. **Reduce Retention Period:**
   ```python
   # In monitoring.py, change cleanup_old_metrics(days=30) to days=7
   ```

3. **Disable Unused Metrics:**
   ```python
   # Comment out metrics you don't need in collect_system_metrics()
   ```

---

## Best Practices

### 1. Regular Review
- Check `/system-health/` dashboard daily
- Review alerts weekly
- Analyze trends monthly

### 2. Alert Tuning
- Adjust thresholds based on actual usage patterns
- Increase cooldown for noisy alerts
- Add custom alerts for business-critical metrics

### 3. Capacity Planning
- Monitor disk usage trends
- Plan upgrades when consistently above 70%
- Review memory usage for optimization opportunities

### 4. Incident Response
- Acknowledge alerts promptly
- Document resolution steps
- Update alert rules based on false positives

### 5. Integration
- Connect to external monitoring (UptimeRobot, Pingdom)
- Setup Sentry for error tracking
- Consider APM tools (New Relic, DataDog) for production

---

## Future Enhancements

1. **Application Performance Monitoring:**
   - Slow query detection
   - Endpoint performance tracking
   - N+1 query detection

2. **Business Metrics:**
   - User login rate
   - Payroll processing time
   - Document upload success rate

3. **Predictive Alerting:**
   - Trend-based alerts
   - Anomaly detection
   - Capacity forecasting

4. **Advanced Visualization:**
   - Grafana dashboards
   - Real-time charts
   - Historical trend analysis

---

**Document Version:** 1.0  
**Last Updated:** March 10, 2026  
**Next Review:** June 10, 2026
