from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0005_benefitclaim'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayrollSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('advance_max_percentage', models.DecimalField(decimal_places=2, default=Decimal('40.00'), help_text='Maximum salary advance as % of gross salary', max_digits=5, verbose_name='max salary advance (%)')),
                ('max_petty_cash_amount', models.DecimalField(decimal_places=2, default=Decimal('500.00'), help_text='Maximum single petty cash request amount', max_digits=12, verbose_name='max petty cash per request')),
                ('max_reimbursement_amount', models.DecimalField(decimal_places=2, default=Decimal('2000.00'), max_digits=12, verbose_name='max reimbursement per request')),
                ('advance_repayment_months', models.PositiveSmallIntegerField(default=3, help_text='Default number of months to repay a salary advance', verbose_name='advance repayment period (months)')),
                ('overtime_rate_multiplier', models.DecimalField(decimal_places=2, default=Decimal('1.50'), help_text='e.g. 1.5 = 150% of normal hourly rate', max_digits=4, verbose_name='overtime rate multiplier')),
                ('paye_rate', models.DecimalField(decimal_places=2, default=Decimal('25.00'), max_digits=5, verbose_name='PAYE / income-tax rate (%)')),
                ('napsa_rate', models.DecimalField(decimal_places=2, default=Decimal('5.00'), max_digits=5, verbose_name='NAPSA / social-security rate (%)')),
                ('nhima_rate', models.DecimalField(decimal_places=2, default=Decimal('1.00'), max_digits=5, verbose_name='NHIMA / health-insurance rate (%)')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='payroll_settings', to='accounts.company')),
            ],
            options={
                'verbose_name': 'payroll settings',
                'verbose_name_plural': 'payroll settings',
            },
        ),
    ]
