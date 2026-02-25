from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0046_systemsettings_enable_analytics_module_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeeprofile',
            name='on_payroll',
            field=models.BooleanField(default=True, help_text='Include employee in payroll generation and selection.'),
        ),
    ]
