# Generated migration for monitoring models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('blu_core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric_type', models.CharField(choices=[('CPU', 'CPU Usage'), ('MEMORY', 'Memory Usage'), ('DISK', 'Disk Usage'), ('RESPONSE_TIME', 'Response Time'), ('ERROR_RATE', 'Error Rate'), ('ACTIVE_SESSIONS', 'Active Sessions'), ('DB_CONNECTIONS', 'Database Connections'), ('QUEUE_SIZE', 'Queue Size')], db_index=True, max_length=20)),
                ('value', models.FloatField()),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='HealthCheckResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('check_name', models.CharField(db_index=True, max_length=100)),
                ('status', models.CharField(choices=[('HEALTHY', 'Healthy'), ('DEGRADED', 'Degraded'), ('UNHEALTHY', 'Unhealthy')], max_length=20)),
                ('response_time_ms', models.IntegerField()),
                ('error_message', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='AlertRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('metric_type', models.CharField(choices=[('CPU', 'CPU Usage'), ('MEMORY', 'Memory Usage'), ('DISK', 'Disk Usage'), ('RESPONSE_TIME', 'Response Time'), ('ERROR_RATE', 'Error Rate'), ('ACTIVE_SESSIONS', 'Active Sessions'), ('DB_CONNECTIONS', 'Database Connections'), ('QUEUE_SIZE', 'Queue Size')], max_length=20)),
                ('threshold', models.FloatField(help_text='Alert when metric exceeds this value')),
                ('duration_minutes', models.IntegerField(default=5, help_text='Alert only if threshold exceeded for this duration')),
                ('severity', models.CharField(choices=[('INFO', 'Info'), ('WARNING', 'Warning'), ('CRITICAL', 'Critical')], default='WARNING', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('cooldown_minutes', models.IntegerField(default=60, help_text='Minimum time between alerts')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric_value', models.FloatField()),
                ('message', models.TextField()),
                ('severity', models.CharField(choices=[('INFO', 'Info'), ('WARNING', 'Warning'), ('CRITICAL', 'Critical')], max_length=20)),
                ('triggered_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='blu_core.alertrule')),
            ],
            options={
                'ordering': ['-triggered_at'],
            },
        ),
        migrations.AddIndex(
            model_name='systemmetric',
            index=models.Index(fields=['metric_type', '-timestamp'], name='blu_core_sy_metric__b8e9a2_idx'),
        ),
        migrations.AddIndex(
            model_name='healthcheckresult',
            index=models.Index(fields=['check_name', '-timestamp'], name='blu_core_he_check_n_8f3c1a_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['-triggered_at', 'severity'], name='blu_core_al_trigger_4d2e8f_idx'),
        ),
    ]
