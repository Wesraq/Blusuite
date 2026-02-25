#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from blu_staff.apps.accounts.models import User, Company
from django.contrib.auth import authenticate

print("=== FIXING USER ACCOUNTS ===")
print()

# Check all approved companies
approved_companies = Company.objects.filter(is_approved=True, is_active=True)
print(f"Found {approved_companies.count()} approved companies")

for company in approved_companies:
    print(f"\nChecking company: {company.name} ({company.email})")

    # Check if user exists
    user = User.objects.filter(email=company.email).first()

    if not user:
        print(f"  ❌ No user found for {company.email}")
        print("     Creating user account...")

        # Create user account
        user = User.objects.create_user(
            email=company.email,
            password='TempPass123!',
            first_name=company.name,
            last_name='Administrator',
            role='ADMINISTRATOR',
            company=company,
            must_change_password=True,
            is_active=True
        )

        print(f"  ✅ Created user: {user.email} (role: {user.role})")
    else:
        print(f"  ✅ User exists: {user.email} (role: {user.role}, active: {user.is_active})")

        # Check if user has usable password
        if not user.has_usable_password():
            print("  ❌ User has unusable password - setting temporary password")
            user.set_password('TempPass123!')
            user.must_change_password = True
            user.save()
            print("  ✅ Password set to 'TempPass123!' (user must change on login)")

        # Check if user is active
        if not user.is_active:
            print("  ❌ User is inactive - activating user")
            user.is_active = True
            user.save()
            print("  ✅ User activated")

# Test authentication
print()
print("=== TESTING AUTHENTICATION ===")
for company in approved_companies:
    user = User.objects.filter(email=company.email).first()
    if user:
        print(f"Testing {company.email}...")
        auth_user = authenticate(username=company.email, password='TempPass123!')
        if auth_user:
            print(f"  ✅ Login successful for {company.email}")
        else:
            print(f"  ❌ Login failed for {company.email}")

print()
print("=== INSTRUCTIONS ===")
print("1. Try logging in with your company email and password: 'TempPass123!'")
print("2. You will be required to change the password on first login")
print("3. After changing password, you can use the new password for future logins")
print("4. The generated password feature should work for new approvals")
