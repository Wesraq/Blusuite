"""
System Monitoring and Health Checks for BluSuite
Tracks system metrics, performance, and sends alerts when thresholds are exceeded
"""
from django.db import models
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import psutil
import time


class SystemMetric(models.Model):
    """Store system performance metrics over time"""
    
    class MetricType(models.TextChoices):
        CPU = 'CPU', 'CPU Usage'
        MEMORY = 'MEMORY', 'Memory Usage'
        DISK = 'DISK', 'Disk Usage'
        RESPONSE_TIME = 'RESPONSE_TIME', 'Response Time'
        ERROR_RATE = 'ERROR_RATE', 'Error Rate'
        ACTIVE_SESSIONS = 'ACTIVE_SESSIONS', 'Active Sessions'
        DB_CONNECTIONS = 'DB_CONNECTIONS', 'Database Connections'
        QUEUE_SIZE = 'QUEUE_SIZE', 'Queue Size'
    
    metric_type = models.CharField(max_length=20, choices=MetricType.choices, db_index=True)
    value = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['metric_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.metric_type}: {self.value} at {self.timestamp}"


class HealthCheckResult(models.Model):
    """Store health check results for monitoring"""
    
    class Status(models.TextChoices):
        HEALTHY = 'HEALTHY', 'Healthy'
        DEGRADED = 'DEGRADED', 'Degraded'
        UNHEALTHY = 'UNHEALTHY', 'Unhealthy'
    
    check_name = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    response_time_ms = models.IntegerField()
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['check_name', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.check_name}: {self.status} ({self.response_time_ms}ms)"


class AlertRule(models.Model):
    """Define alerting rules for system metrics"""
    
    class Severity(models.TextChoices):
        INFO = 'INFO', 'Info'
        WARNING = 'WARNING', 'Warning'
        CRITICAL = 'CRITICAL', 'Critical'
    
    name = models.CharField(max_length=200)
    metric_type = models.CharField(max_length=20, choices=SystemMetric.MetricType.choices)
    threshold = models.FloatField(help_text="Alert when metric exceeds this value")
    duration_minutes = models.IntegerField(default=5, help_text="Alert only if threshold exceeded for this duration")
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
    is_active = models.BooleanField(default=True)
    cooldown_minutes = models.IntegerField(default=60, help_text="Minimum time between alerts")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.severity})"


class Alert(models.Model):
    """Store triggered alerts"""
    
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='alerts')
    metric_value = models.FloatField()
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=AlertRule.Severity.choices)
    triggered_at = models.DateTimeField(default=timezone.now, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['-triggered_at', 'severity']),
        ]
    
    def __str__(self):
        return f"{self.rule.name}: {self.metric_value} at {self.triggered_at}"
    
    @property
    def is_active(self):
        return self.resolved_at is None


# ─────────────────────────────────────────────────────────────────────────────
# Metric Collection Functions
# ─────────────────────────────────────────────────────────────────────────────

def collect_system_metrics():
    """Collect current system metrics and store them"""
    metrics = []
    
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics.append(SystemMetric(
            metric_type=SystemMetric.MetricType.CPU,
            value=cpu_percent
        ))
        
        # Memory usage
        memory = psutil.virtual_memory()
        metrics.append(SystemMetric(
            metric_type=SystemMetric.MetricType.MEMORY,
            value=memory.percent,
            metadata={'available_mb': memory.available // (1024 * 1024)}
        ))
        
        # Disk usage
        disk = psutil.disk_usage('/')
        metrics.append(SystemMetric(
            metric_type=SystemMetric.MetricType.DISK,
            value=disk.percent,
            metadata={'free_gb': disk.free // (1024 * 1024 * 1024)}
        ))
        
        # Active sessions (approximate)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        active_users = User.objects.filter(is_active=True).count()
        metrics.append(SystemMetric(
            metric_type=SystemMetric.MetricType.ACTIVE_SESSIONS,
            value=active_users
        ))
        
    except Exception as e:
        # Log error but don't fail
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error collecting system metrics: {e}")
    
    # Bulk create metrics
    if metrics:
        SystemMetric.objects.bulk_create(metrics)
    
    return len(metrics)


def run_health_checks():
    """Run all health checks and store results"""
    from django.contrib.auth import get_user_model
    from blu_staff.apps.accounts.models import Company
    
    User = get_user_model()
    checks = []
    
    # Database check
    start = time.time()
    try:
        User.objects.count()
        checks.append(HealthCheckResult(
            check_name='Database',
            status=HealthCheckResult.Status.HEALTHY,
            response_time_ms=int((time.time() - start) * 1000)
        ))
    except Exception as e:
        checks.append(HealthCheckResult(
            check_name='Database',
            status=HealthCheckResult.Status.UNHEALTHY,
            response_time_ms=int((time.time() - start) * 1000),
            error_message=str(e)
        ))
    
    # Cache check
    start = time.time()
    try:
        cache.set('health_check', 'ok', 10)
        cache.get('health_check')
        checks.append(HealthCheckResult(
            check_name='Cache',
            status=HealthCheckResult.Status.HEALTHY,
            response_time_ms=int((time.time() - start) * 1000)
        ))
    except Exception as e:
        checks.append(HealthCheckResult(
            check_name='Cache',
            status=HealthCheckResult.Status.UNHEALTHY,
            response_time_ms=int((time.time() - start) * 1000),
            error_message=str(e)
        ))
    
    # Application check (query performance)
    start = time.time()
    try:
        Company.objects.count()
        response_time = int((time.time() - start) * 1000)
        status = HealthCheckResult.Status.HEALTHY if response_time < 100 else HealthCheckResult.Status.DEGRADED
        checks.append(HealthCheckResult(
            check_name='Application',
            status=status,
            response_time_ms=response_time
        ))
    except Exception as e:
        checks.append(HealthCheckResult(
            check_name='Application',
            status=HealthCheckResult.Status.UNHEALTHY,
            response_time_ms=int((time.time() - start) * 1000),
            error_message=str(e)
        ))
    
    if checks:
        HealthCheckResult.objects.bulk_create(checks)
    
    return checks


def check_alert_rules():
    """Check all active alert rules and trigger alerts if needed"""
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    active_rules = AlertRule.objects.filter(is_active=True)
    triggered_alerts = []
    
    for rule in active_rules:
        # Get recent metrics for this type
        cutoff_time = timezone.now() - timedelta(minutes=rule.duration_minutes)
        recent_metrics = SystemMetric.objects.filter(
            metric_type=rule.metric_type,
            timestamp__gte=cutoff_time
        )
        
        if not recent_metrics.exists():
            continue
        
        # Check if all recent metrics exceed threshold
        avg_value = sum(m.value for m in recent_metrics) / len(recent_metrics)
        
        if avg_value > rule.threshold:
            # Check cooldown
            last_alert = Alert.objects.filter(
                rule=rule,
                triggered_at__gte=timezone.now() - timedelta(minutes=rule.cooldown_minutes)
            ).first()
            
            if last_alert:
                continue  # Still in cooldown
            
            # Trigger alert
            alert = Alert.objects.create(
                rule=rule,
                metric_value=avg_value,
                message=f"{rule.name}: {rule.metric_type} at {avg_value:.1f}% (threshold: {rule.threshold}%)",
                severity=rule.severity
            )
            triggered_alerts.append(alert)
            
            # Send notification
            _send_alert_notification(alert)
    
    return triggered_alerts


def _send_alert_notification(alert):
    """Send notification for triggered alert"""
    try:
        from blu_staff.apps.notifications.utils import bulk_notify
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        superadmins = User.objects.filter(role='SUPERADMIN')
        
        notification_type = {
            'INFO': 'INFO',
            'WARNING': 'WARNING',
            'CRITICAL': 'ERROR'
        }.get(alert.severity, 'WARNING')
        
        bulk_notify(
            recipients=superadmins,
            title=f'System Alert: {alert.rule.name}',
            message=alert.message,
            notification_type=notification_type,
            category='SYSTEM',
            link='/system-health/',
            send_email=(alert.severity == 'CRITICAL')
        )
    except Exception:
        pass  # Don't fail if notification fails


def cleanup_old_metrics(days=30):
    """Delete metrics older than specified days"""
    cutoff = timezone.now() - timedelta(days=days)
    deleted_count = SystemMetric.objects.filter(timestamp__lt=cutoff).delete()[0]
    return deleted_count


def cleanup_old_health_checks(days=7):
    """Delete health check results older than specified days"""
    cutoff = timezone.now() - timedelta(days=days)
    deleted_count = HealthCheckResult.objects.filter(timestamp__lt=cutoff).delete()[0]
    return deleted_count


def get_system_status():
    """Get current system status summary"""
    # Get latest metrics
    latest_metrics = {}
    for metric_type in SystemMetric.MetricType:
        latest = SystemMetric.objects.filter(metric_type=metric_type.value).first()
        if latest:
            latest_metrics[metric_type.value] = latest.value
    
    # Get latest health checks
    latest_checks = {}
    for check_name in ['Database', 'Cache', 'Application']:
        latest = HealthCheckResult.objects.filter(check_name=check_name).first()
        if latest:
            latest_checks[check_name] = {
                'status': latest.status,
                'response_time_ms': latest.response_time_ms
            }
    
    # Get active alerts
    active_alerts = Alert.objects.filter(resolved_at__isnull=True).count()
    
    # Determine overall status
    if active_alerts > 0:
        overall_status = 'DEGRADED'
    elif any(c.get('status') == 'UNHEALTHY' for c in latest_checks.values()):
        overall_status = 'UNHEALTHY'
    else:
        overall_status = 'HEALTHY'
    
    return {
        'overall_status': overall_status,
        'metrics': latest_metrics,
        'health_checks': latest_checks,
        'active_alerts': active_alerts,
        'timestamp': timezone.now()
    }
