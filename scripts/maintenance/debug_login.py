#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from blu_staff.apps.accounts.models import User, Company
from django.contrib.auth import authenticate

print("=== DEBUGGING LOGIN ISSUE ===")
print()

# Check all users
print("ALL USERS:")
users = User.objects.all()
for user in users:
    print(f"  ID: {user.id}")
    print(f"  Email: {user.email}")
    print(f"  Role: {user.role}")
    print(f"  Is Active: {user.is_active}")
    print(f"  Must Change Password: {user.must_change_password}")
    print(f"  Company: {user.company.name if user.company else 'None'}")
    print()

# Check companies
print("COMPANIES:")
companies = Company.objects.all()
for company in companies:
    print(f"  ID: {company.id}")
    print(f"  Name: {company.name}")
    print(f"  Email: {company.email}")
    print(f"  Is Approved: {company.is_approved}")
    print(f"  Is Active: {company.is_active}")
    print()

# Test authentication with a company email
print("TESTING AUTHENTICATION:")
for company in companies:
    if company.email:
        # Try to find user with this email
        user = User.objects.filter(email=company.email).first()
        if user:
            print(f"Testing login for {company.email} (role: {user.role})")
            # Try to authenticate (this will fail if password is wrong, but will tell us if user exists)
            try:
                auth_user = authenticate(username=company.email, password='test_password')
                if auth_user:
                    print(f"  ✅ Authentication successful for {company.email}")
                else:
                    print(f"  ❌ Authentication failed for {company.email}")
                    print(f"     User exists but password is incorrect")
            except Exception as e:
                print(f"  ⚠️  Error testing authentication: {e}")
        else:
            print(f"  ❌ No user found for {company.email}")

print("\n=== SUMMARY ===")
print("If you're getting 'Invalid credentials', check:")
print("1. Is there a user with the company email?")
print("2. Is the user's role 'ADMINISTRATOR'?")
print("3. Is the user active?")
print("4. Is the password correct?")
print("5. Does the login view allow 'ADMINISTRATOR' role?")
