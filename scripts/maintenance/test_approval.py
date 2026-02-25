#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from blu_staff.apps.accounts.models import Company, CompanyRegistrationRequest, User
from django.utils import timezone

print("=== TESTING COMPANY APPROVAL ===")
print()

# Create a test registration request
print("1. Creating test registration request...")
test_request = CompanyRegistrationRequest.objects.create(
    company_name="Test Company ABC",
    company_address="123 Test Street",
    company_phone="123-456-7890",
    company_email="test@example.com",
    company_website="https://test.com",
    tax_id="123456789",
    contact_first_name="John",
    contact_last_name="Doe",
    contact_email="john@test.com",
    contact_phone="987-654-3210",
    subscription_plan="BASIC",
    number_of_employees=5,
    business_type="Technology",
    company_size="Small",
    status="PENDING"
)
print(f"Created request: {test_request.company_name} (ID: {test_request.id})")
print()

# Simulate the approval process
print("2. Simulating approval process...")
try:
    # Create company from registration request (like in the view)
    company = Company.objects.create(
        name=test_request.company_name,
        address=test_request.company_address,
        phone=test_request.company_phone,
        email=test_request.company_email,
        website=test_request.company_website,
        tax_id=test_request.tax_id,
        subscription_plan=test_request.subscription_plan,
        max_employees=test_request.number_of_employees,
        registration_request=test_request,
        is_approved=True,
        is_active=True,
        approved_at=timezone.now()
    )

    print(f"Created company: {company.name} (ID: {company.id})")
    print(f"Company is_approved: {company.is_approved}")
    print(f"Company is_active: {company.is_active}")
    print(f"Company approved_at: {company.approved_at}")
    print()

    # Update registration request status
    test_request.status = 'APPROVED'
    test_request.reviewed_at = timezone.now()
    test_request.save()

    print(f"Updated request status to: {test_request.status}")
    print()

    # Check what the company_list view would return
    print("3. Checking what company_list view would return...")
    approved_companies = Company.objects.filter(is_approved=True, is_active=True)
    print(f"Approved companies count: {approved_companies.count()}")
    for comp in approved_companies:
        print(f"  - {comp.name}: approved={comp.is_approved}, active={comp.is_active}")

    print()
    print("✅ Test completed successfully!")

except Exception as e:
    print(f"❌ Error during test: {e}")
    import traceback
    traceback.print_exc()
