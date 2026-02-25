#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from blu_staff.apps.accounts.models import Company, CompanyRegistrationRequest
from django.utils import timezone

print("=== FIXING EXISTING APPROVED COMPANIES ===")
print()

# Find companies that might have been approved but not marked correctly
companies_to_fix = []

# Check for companies that have approved registration requests but aren't marked as approved
approved_requests = CompanyRegistrationRequest.objects.filter(status='APPROVED')
for request in approved_requests:
    if request.approved_company:
        company = request.approved_company
        if not company.is_approved or not company.is_active:
            companies_to_fix.append(company)
            print(f"Found company to fix: {company.name}")
            print(f"  Current: is_approved={company.is_approved}, is_active={company.is_active}")

print(f"\nFound {len(companies_to_fix)} companies to fix")

# Fix the companies
for company in companies_to_fix:
    print(f"\nFixing company: {company.name}")
    old_approved = company.is_approved
    old_active = company.is_active

    company.is_approved = True
    company.is_active = True
    company.approved_at = company.approved_at or timezone.now()
    company.save()

    print(f"  Before: is_approved={old_approved}, is_active={old_active}")
    print(f"  After:  is_approved={company.is_approved}, is_active={company.is_active}")

# Check for companies that are approved but don't have approved_at timestamp
companies_missing_timestamp = Company.objects.filter(is_approved=True, approved_at__isnull=True)
if companies_missing_timestamp:
    print(f"\nFound {companies_missing_timestamp.count()} companies missing approved_at timestamp")
    for company in companies_missing_timestamp:
        company.approved_at = timezone.now()
        company.save()
        print(f"  Fixed: {company.name}")

# Final check
print("\n=== FINAL CHECK ===")
approved_companies = Company.objects.filter(is_approved=True, is_active=True)
print(f"Total approved companies: {approved_companies.count()}")
for company in approved_companies:
    print(f"  - {company.name}: approved_at={company.approved_at}")

print("\n✅ Company fixing completed!")
