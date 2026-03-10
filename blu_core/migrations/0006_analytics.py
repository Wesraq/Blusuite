# Generated migration for advanced analytics models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('blu_core', '0005_onboarding'),
        ('accounts', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyAnalytics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('snapshot_date', models.DateField(db_index=True)),
                ('total_employees', models.IntegerField(default=0)),
                ('active_employees', models.IntegerField(default=0)),
                ('new_hires_this_month', models.IntegerField(default=0)),
                ('terminations_this_month', models.IntegerField(default=0)),
                ('turnover_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('average_attendance_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('total_absences', models.IntegerField(default=0)),
                ('total_late_arrivals', models.IntegerField(default=0)),
                ('total_leave_requests', models.IntegerField(default=0)),
                ('approved_leaves', models.IntegerField(default=0)),
                ('pending_leaves', models.IntegerField(default=0)),
                ('total_leave_days_taken', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('total_payroll_cost', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('average_salary', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_overtime_hours', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_overtime_cost', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('average_performance_score', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('pending_performance_reviews', models.IntegerField(default=0)),
                ('completed_performance_reviews', models.IntegerField(default=0)),
                ('total_training_hours', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('employees_in_training', models.IntegerField(default=0)),
                ('training_completion_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('total_documents', models.IntegerField(default=0)),
                ('pending_document_approvals', models.IntegerField(default=0)),
                ('expired_documents', models.IntegerField(default=0)),
                ('active_onboardings', models.IntegerField(default=0)),
                ('completed_onboardings', models.IntegerField(default=0)),
                ('average_onboarding_days', models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ('total_storage_used_mb', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('active_users_last_30_days', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_snapshots', to='accounts.company')),
            ],
            options={
                'verbose_name': 'Company Analytics',
                'verbose_name_plural': 'Company Analytics',
                'ordering': ['-snapshot_date'],
            },
        ),
        migrations.CreateModel(
            name='MetricTrend',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric_name', models.CharField(db_index=True, max_length=100)),
                ('metric_category', models.CharField(max_length=50)),
                ('date', models.DateField(db_index=True)),
                ('value', models.DecimalField(decimal_places=2, max_digits=15)),
                ('previous_value', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('change_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('change_percentage', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='metric_trends', to='accounts.company')),
            ],
            options={
                'verbose_name': 'Metric Trend',
                'verbose_name_plural': 'Metric Trends',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='AnalyticsReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_type', models.CharField(choices=[('COMPANY_OVERVIEW', 'Company Overview'), ('HR_METRICS', 'HR Metrics'), ('PAYROLL_SUMMARY', 'Payroll Summary'), ('ATTENDANCE_REPORT', 'Attendance Report'), ('LEAVE_ANALYSIS', 'Leave Analysis'), ('PERFORMANCE_REVIEW', 'Performance Review'), ('TRAINING_REPORT', 'Training Report'), ('TURNOVER_ANALYSIS', 'Turnover Analysis'), ('CUSTOM', 'Custom Report')], max_length=30)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('date_from', models.DateField()),
                ('date_to', models.DateField()),
                ('filters_json', models.JSONField(blank=True, default=dict)),
                ('format', models.CharField(choices=[('PDF', 'PDF'), ('EXCEL', 'Excel'), ('CSV', 'CSV'), ('JSON', 'JSON')], default='PDF', max_length=10)),
                ('file_path', models.CharField(blank=True, max_length=500)),
                ('file_size_kb', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('GENERATING', 'Generating'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')], default='PENDING', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('generated_at', models.DateTimeField(blank=True, null=True)),
                ('is_scheduled', models.BooleanField(default=False)),
                ('schedule_frequency', models.CharField(blank=True, max_length=20)),
                ('next_run_date', models.DateTimeField(blank=True, null=True)),
                ('email_sent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_reports', to='accounts.company')),
                ('generated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_reports', to=settings.AUTH_USER_MODEL)),
                ('recipients', models.ManyToManyField(blank=True, related_name='received_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Analytics Report',
                'verbose_name_plural': 'Analytics Reports',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='companyanalytics',
            index=models.Index(fields=['company', '-snapshot_date'], name='blu_core_co_company_8a7f2d_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='companyanalytics',
            unique_together={('company', 'snapshot_date')},
        ),
        migrations.AddIndex(
            model_name='metrictrend',
            index=models.Index(fields=['company', 'metric_name', '-date'], name='blu_core_me_company_4e8a1f_idx'),
        ),
        migrations.AddIndex(
            model_name='metrictrend',
            index=models.Index(fields=['metric_category', '-date'], name='blu_core_me_metric__9d2c3a_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='metrictrend',
            unique_together={('company', 'metric_name', 'date')},
        ),
        migrations.AddIndex(
            model_name='analyticsreport',
            index=models.Index(fields=['company', '-created_at'], name='blu_core_an_company_7f3e4b_idx'),
        ),
        migrations.AddIndex(
            model_name='analyticsreport',
            index=models.Index(fields=['status', 'is_scheduled'], name='blu_core_an_status__2a9d5c_idx'),
        ),
    ]
