"""
Script to identify employees with default/placeholder profile data
Run with: python manage.py shell < fix_employee_profiles.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from accounts.models import User, EmployeeProfile

print("=" * 60)
print("EMPLOYEE PROFILE AUDIT")
print("=" * 60)
print()

# Find all employees with default/placeholder values
employees_with_defaults = EmployeeProfile.objects.filter(
    job_title__in=['Employee', ''],
    department__in=['Unassigned', '']
).select_related('user')

print(f"Found {employees_with_defaults.count()} employees with default values:\n")

for profile in employees_with_defaults:
    print(f"ID: {profile.user.id}")
    print(f"  Name: {profile.user.get_full_name()}")
    print(f"  Email: {profile.user.email}")
    print(f"  Employee ID: {profile.employee_id}")
    print(f"  Job Title: {profile.job_title}")
    print(f"  Department: {profile.department}")
    print(f"  Salary: {profile.salary}")
    print(f"  Pay Grade: {profile.pay_grade or '(empty)'}")
    print(f"  Currency: {profile.currency}")
    print(f"  Date Hired: {profile.date_hired}")
    print(f"  Edit URL: http://127.0.0.1:8000/employer/employees/{profile.user.id}/edit/")
    print()

print("=" * 60)
print("RECOMMENDATIONS:")
print("=" * 60)
print()
print("These employees need their profiles updated. You have two options:")
print()
print("1. MANUAL UPDATE (Recommended):")
print("   - Visit each employee's edit URL above")
print("   - Fill in the correct Job Title, Department, Salary, Pay Grade")
print("   - Click 'Update Employee' to save")
print()
print("2. BULK UPDATE (Advanced):")
print("   - If you want to set default values for all at once")
print("   - Modify this script to set values and uncomment the save lines")
print()

# Uncomment below to bulk update with specific values
# WARNING: This will overwrite all employees with defaults!
"""
print("BULK UPDATE - DISABLED")
print("To enable bulk update, uncomment the code in this script")
print()

# Example: Update all to specific department
# for profile in employees_with_defaults:
#     profile.department = 'General'
#     profile.job_title = 'Staff Member'
#     profile.currency = 'ZMW'
#     profile.save()
#     print(f"Updated: {profile.user.get_full_name()}")
"""
