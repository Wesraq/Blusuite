# Generated migration for onboarding automation models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('blu_core', '0004_settings'),
        ('accounts', '0002_initial'),
        ('onboarding', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyOnboarding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('NOT_STARTED', 'Not Started'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed')], default='NOT_STARTED', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('current_step', models.IntegerField(default=1)),
                ('company_info_complete', models.BooleanField(default=False)),
                ('admin_account_complete', models.BooleanField(default=False)),
                ('settings_configured', models.BooleanField(default=False)),
                ('first_employee_added', models.BooleanField(default=False)),
                ('first_department_created', models.BooleanField(default=False)),
                ('attendance_configured', models.BooleanField(default=False)),
                ('leave_policies_set', models.BooleanField(default=False)),
                ('payroll_configured', models.BooleanField(default=False)),
                ('documents_uploaded', models.BooleanField(default=False)),
                ('integrations_setup', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='onboarding_progress', to='accounts.company')),
            ],
            options={
                'verbose_name': 'Company Onboarding',
                'verbose_name_plural': 'Company Onboardings',
            },
        ),
        migrations.CreateModel(
            name='OnboardingReminder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reminder_type', models.CharField(choices=[('TASK_DUE', 'Task Due Soon'), ('TASK_OVERDUE', 'Task Overdue'), ('WELCOME', 'Welcome Message'), ('PROGRESS', 'Progress Update'), ('COMPLETION', 'Onboarding Complete')], max_length=20)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('company_onboarding', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reminders', to='blu_core.companyonboarding')),
                ('employee_onboarding', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reminders', to='onboarding.employeeonboarding')),
                ('sent_to', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-sent_at'],
            },
        ),
    ]
