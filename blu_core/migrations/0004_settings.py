# Generated migration for settings management models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('blu_core', '0003_mfa'),
        ('accounts', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('SYSTEM', 'System Settings'), ('SECURITY', 'Security Settings'), ('ATTENDANCE', 'Attendance Settings'), ('LEAVE', 'Leave Management'), ('PAYROLL', 'Payroll Settings'), ('NOTIFICATIONS', 'Notification Settings'), ('BRANDING', 'Branding & Customization'), ('INTEGRATIONS', 'Third-party Integrations'), ('COMPLIANCE', 'Compliance & Audit')], db_index=True, max_length=20)),
                ('key', models.CharField(db_index=True, max_length=100, unique=True)),
                ('value', models.JSONField()),
                ('default_value', models.JSONField()),
                ('description', models.TextField()),
                ('data_type', models.CharField(choices=[('string', 'String'), ('integer', 'Integer'), ('float', 'Float'), ('boolean', 'Boolean'), ('json', 'JSON Object'), ('list', 'List')], default='string', max_length=20)),
                ('is_required', models.BooleanField(default=False)),
                ('is_sensitive', models.BooleanField(default=False, help_text='Mask value in UI')),
                ('validation_rules', models.JSONField(blank=True, default=dict, help_text='JSON schema for validation')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='system_settings_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['category', 'key'],
            },
        ),
        migrations.CreateModel(
            name='SettingsTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField()),
                ('category', models.CharField(choices=[('SYSTEM', 'System Settings'), ('SECURITY', 'Security Settings'), ('ATTENDANCE', 'Attendance Settings'), ('LEAVE', 'Leave Management'), ('PAYROLL', 'Payroll Settings'), ('NOTIFICATIONS', 'Notification Settings'), ('BRANDING', 'Branding & Customization'), ('INTEGRATIONS', 'Third-party Integrations'), ('COMPLIANCE', 'Compliance & Audit')], max_length=20)),
                ('settings_data', models.JSONField(help_text='Template settings configuration')),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['category', 'name'],
            },
        ),
        migrations.CreateModel(
            name='SettingsVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('SYSTEM', 'System Settings'), ('SECURITY', 'Security Settings'), ('ATTENDANCE', 'Attendance Settings'), ('LEAVE', 'Leave Management'), ('PAYROLL', 'Payroll Settings'), ('NOTIFICATIONS', 'Notification Settings'), ('BRANDING', 'Branding & Customization'), ('INTEGRATIONS', 'Third-party Integrations'), ('COMPLIANCE', 'Compliance & Audit')], max_length=20)),
                ('settings_snapshot', models.JSONField(help_text='Complete settings at this version')),
                ('changes', models.JSONField(help_text='What changed from previous version')),
                ('version_number', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('comment', models.TextField(blank=True)),
                ('company', models.ForeignKey(blank=True, help_text='Null for system-wide settings', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='settings_versions', to='accounts.company')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='settings_versions_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CompanySettingOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.JSONField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='setting_overrides', to='accounts.company')),
                ('system_setting', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='company_overrides', to='blu_core.systemsetting')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='company_setting_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['company', 'system_setting__category', 'system_setting__key'],
            },
        ),
        migrations.AddIndex(
            model_name='systemsetting',
            index=models.Index(fields=['category', 'key'], name='blu_core_sy_categor_8f2a1c_idx'),
        ),
        migrations.AddIndex(
            model_name='settingsversion',
            index=models.Index(fields=['company', 'category', '-version_number'], name='blu_core_se_company_4d8e2f_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='companysettingoverride',
            unique_together={('company', 'system_setting')},
        ),
    ]
