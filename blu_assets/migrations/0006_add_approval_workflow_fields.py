# Generated manually for multi-level approval workflow

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('blu_assets', '0005_assetcollectionrecord'),
    ]

    operations = [
        migrations.AddField(
            model_name='assetrequest',
            name='current_approval_level',
            field=models.CharField(
                choices=[
                    ('SUPERVISOR', 'Supervisor Review'),
                    ('MANAGER', 'Department Manager'),
                    ('HR', 'HR Review'),
                    ('ADMIN', 'Admin/Procurement')
                ],
                default='SUPERVISOR',
                help_text='Current stage in approval workflow',
                max_length=20,
                verbose_name='current approval level'
            ),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='supervisor_approved',
            field=models.BooleanField(default=False, verbose_name='supervisor approved'),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='supervisor_approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='asset_requests_supervisor_approved',
                to=settings.AUTH_USER_MODEL,
                verbose_name='supervisor'
            ),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='supervisor_approval_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='supervisor approval date'),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='manager_approved',
            field=models.BooleanField(default=False, verbose_name='manager approved'),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='manager_approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='asset_requests_manager_approved',
                to=settings.AUTH_USER_MODEL,
                verbose_name='department manager'
            ),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='manager_approval_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='manager approval date'),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='hr_approved',
            field=models.BooleanField(default=False, verbose_name='HR approved'),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='hr_approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='asset_requests_hr_approved',
                to=settings.AUTH_USER_MODEL,
                verbose_name='HR reviewer'
            ),
        ),
        migrations.AddField(
            model_name='assetrequest',
            name='hr_approval_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='HR approval date'),
        ),
        migrations.AlterField(
            model_name='assetrequest',
            name='approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='asset_requests_approved',
                to=settings.AUTH_USER_MODEL,
                verbose_name='final approved by'
            ),
        ),
        migrations.AlterField(
            model_name='assetrequest',
            name='approval_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='final approval date'),
        ),
    ]
