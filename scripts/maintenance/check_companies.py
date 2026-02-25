#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from blu_staff.apps.accounts.models import Company, CompanyRegistrationRequest

print("=== DATABASE CHECK ===")
print()

# Check all companies
print("ALL COMPANIES:")
all_companies = Company.objects.all()
for company in all_companies:
    print(f"  - {company.name}: is_approved={company.is_approved}, is_active={company.is_active}, approved_at={company.approved_at}")
print()

# Check approved companies
print("APPROVED COMPANIES (is_approved=True, is_active=True):")
approved_companies = Company.objects.filter(is_approved=True, is_active=True)
for company in approved_companies:
    print(f"  - {company.name}: approved_at={company.approved_at}")
print(f"Total approved companies: {approved_companies.count()}")
print()

# Check pending registration requests
print("PENDING REGISTRATION REQUESTS:")
pending_requests = CompanyRegistrationRequest.objects.filter(status='PENDING')
for request in pending_requests:
    print(f"  - {request.company_name}: status={request.status}")
print(f"Total pending requests: {pending_requests.count()}")
print()

# Check approved registration requests
print("APPROVED REGISTRATION REQUESTS:")
approved_requests = CompanyRegistrationRequest.objects.filter(status='APPROVED')
for request in approved_requests:
    print(f"  - {request.company_name}: status={request.status}, reviewed_at={request.reviewed_at}")
print(f"Total approved requests: {approved_requests.count()}")
