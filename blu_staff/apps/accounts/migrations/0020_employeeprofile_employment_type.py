from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0019_alter_employeeprofile_employee_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeprofile",
            name="employment_type",
            field=models.CharField(
                choices=[
                    ("PERMANENT", "Permanent"),
                    ("CONTRACT", "Contract"),
                    ("PROBATION", "Probation"),
                    ("TEMPORARY", "Temporary"),
                    ("INTERN", "Intern"),
                    ("PART_TIME", "Part-time"),
                ],
                blank=True,
                default="",
                max_length=20,
            ),
        ),
    ]
