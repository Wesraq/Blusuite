from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_email', models.EmailField(blank=True, help_text='Snapshot of email at time of action', max_length=254)),
                ('action', models.CharField(
                    choices=[
                        ('LOGIN', 'User Login'),
                        ('LOGOUT', 'User Logout'),
                        ('LOGIN_FAILED', 'Failed Login Attempt'),
                        ('PASSWORD_CHANGE', 'Password Changed'),
                        ('EMPLOYEE_CREATE', 'Employee Created'),
                        ('EMPLOYEE_UPDATE', 'Employee Updated'),
                        ('EMPLOYEE_DELETE', 'Employee Deleted'),
                        ('ROLE_CHANGE', 'Role Changed'),
                        ('SALARY_CREATE', 'Salary Structure Created'),
                        ('SALARY_UPDATE', 'Salary Updated'),
                        ('PAYROLL_APPROVE', 'Payroll Approved'),
                        ('PAYROLL_RUN', 'Payroll Run'),
                        ('ASSET_CREATE', 'Asset Created'),
                        ('ASSET_ASSIGN', 'Asset Assigned'),
                        ('ASSET_RETURN', 'Asset Returned'),
                        ('ASSET_UPDATE', 'Asset Updated'),
                        ('ASSET_DELETE', 'Asset Deleted'),
                        ('DOC_UPLOAD', 'Document Uploaded'),
                        ('DOC_DELETE', 'Document Deleted'),
                        ('DOC_APPROVE', 'Document Approved'),
                        ('COMPANY_UPDATE', 'Company Settings Updated'),
                        ('CREATE', 'Record Created'),
                        ('UPDATE', 'Record Updated'),
                        ('DELETE', 'Record Deleted'),
                        ('EXPORT', 'Data Exported'),
                        ('VIEW_SENSITIVE', 'Sensitive Data Viewed'),
                    ],
                    db_index=True,
                    max_length=30,
                )),
                ('model_name', models.CharField(blank=True, db_index=True, max_length=100)),
                ('object_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('object_repr', models.CharField(blank=True, help_text='Human-readable name of the object', max_length=255)),
                ('changes', models.JSONField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('extra', models.JSONField(blank=True, help_text='Any extra contextual data', null=True)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('company', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_logs',
                    to='accounts.company',
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Audit Log',
                'verbose_name_plural': 'Audit Logs',
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['company', 'timestamp'], name='audit_company_ts_idx'),
                    models.Index(fields=['user', 'action'], name='audit_user_action_idx'),
                    models.Index(fields=['model_name', 'object_id'], name='audit_model_obj_idx'),
                ],
            },
        ),
    ]
