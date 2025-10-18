# Generated migration for PayrollDeductionSettings updates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0027_payrolldeductionsettings'),
    ]

    operations = [
        # Remove old NHIMA fixed amount fields
        migrations.RemoveField(
            model_name='payrolldeductionsettings',
            name='nhima_employee_amount',
        ),
        migrations.RemoveField(
            model_name='payrolldeductionsettings',
            name='nhima_employer_amount',
        ),
        
        # Add new NHIMA percentage fields
        migrations.AddField(
            model_name='payrolldeductionsettings',
            name='nhima_employee_percentage',
            field=models.DecimalField(decimal_places=2, default=1.0, help_text='Employee contribution percentage', max_digits=5),
        ),
        migrations.AddField(
            model_name='payrolldeductionsettings',
            name='nhima_employer_percentage',
            field=models.DecimalField(decimal_places=2, default=1.0, help_text='Employer contribution percentage', max_digits=5),
        ),
        
        # Remove old late/absent deduction fields
        migrations.RemoveField(
            model_name='payrolldeductionsettings',
            name='late_deduction_per_occurrence',
        ),
        migrations.RemoveField(
            model_name='payrolldeductionsettings',
            name='absent_deduction_per_day',
        ),
        
        # Add new late deduction fields
        migrations.AddField(
            model_name='payrolldeductionsettings',
            name='late_deduction_type',
            field=models.CharField(choices=[('PERCENTAGE', 'Percentage of Daily Rate'), ('HOURLY_RATE', 'Hourly Rate')], default='PERCENTAGE', help_text='How to calculate late deduction', max_length=20),
        ),
        migrations.AddField(
            model_name='payrolldeductionsettings',
            name='late_deduction_percentage',
            field=models.DecimalField(decimal_places=2, default=5.0, help_text='Percentage of daily rate deducted per late occurrence', max_digits=5),
        ),
        
        # Update absent deduction type field
        migrations.AlterField(
            model_name='payrolldeductionsettings',
            name='absent_deduction_type',
            field=models.CharField(choices=[('DAILY_RATE', 'Full Daily Rate'), ('PERCENTAGE', 'Percentage of Daily Rate')], default='DAILY_RATE', help_text='How to calculate absence deduction', max_length=20),
        ),
        
        # Add new absent deduction percentage field
        migrations.AddField(
            model_name='payrolldeductionsettings',
            name='absent_deduction_percentage',
            field=models.DecimalField(decimal_places=2, default=100.0, help_text="Percentage of daily rate deducted per absence (100 = full day's pay)", max_digits=5),
        ),
        
        # Add working days per month field
        migrations.AddField(
            model_name='payrolldeductionsettings',
            name='working_days_per_month',
            field=models.IntegerField(default=22, help_text='Number of working days per month for daily rate calculation'),
        ),
    ]
