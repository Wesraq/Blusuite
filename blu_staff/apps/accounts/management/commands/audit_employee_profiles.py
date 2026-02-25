from django.core.management.base import BaseCommand
from blu_staff.apps.accounts.models import User, EmployeeProfile


class Command(BaseCommand):
    help = 'Audit employee profiles to find those with default/placeholder values'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("EMPLOYEE PROFILE AUDIT"))
        self.stdout.write("=" * 60)
        self.stdout.write("")

        # Find all employees with default/placeholder values
        employees_with_defaults = EmployeeProfile.objects.filter(
            job_title__in=['Employee', ''],
            department__in=['Unassigned', '']
        ).select_related('user')

        count = employees_with_defaults.count()
        self.stdout.write(f"Found {count} employees with default values:\n")

        if count == 0:
            self.stdout.write(self.style.SUCCESS("✓ All employee profiles are properly configured!"))
            return

        for profile in employees_with_defaults:
            self.stdout.write(f"ID: {profile.user.id}")
            self.stdout.write(f"  Name: {profile.user.get_full_name()}")
            self.stdout.write(f"  Email: {profile.user.email}")
            self.stdout.write(f"  Employee ID: {profile.employee_id}")
            self.stdout.write(f"  Job Title: {profile.job_title}")
            self.stdout.write(f"  Department: {profile.department}")
            self.stdout.write(f"  Salary: {profile.salary}")
            self.stdout.write(f"  Pay Grade: {profile.pay_grade or '(empty)'}")
            self.stdout.write(f"  Currency: {profile.currency}")
            self.stdout.write(f"  Date Hired: {profile.date_hired}")
            self.stdout.write(self.style.WARNING(
                f"  Edit URL: http://127.0.0.1:8000/employer/employees/{profile.user.id}/edit/"
            ))
            self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("RECOMMENDATIONS:"))
        self.stdout.write("=" * 60)
        self.stdout.write("")
        self.stdout.write("These employees need their profiles updated:")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("OPTION 1 - Manual Update (Recommended):"))
        self.stdout.write("  - Visit each employee's Edit URL above")
        self.stdout.write("  - Fill in correct Job Title, Department, Salary, Pay Grade")
        self.stdout.write("  - Click 'Update Employee' to save")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("OPTION 2 - Now working correctly:"))
        self.stdout.write("  - New employees created will save all data properly")
        self.stdout.write("  - The bug has been fixed in the create employee form")
        self.stdout.write("")
