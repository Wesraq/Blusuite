#!/usr/bin/env python3
"""
Test script to verify login API role response
"""

import requests
import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

# Test login API response
def test_login_api():
    """Test that login API returns correct role information"""

    # Create test client
    client = Client()

    # Create a test user
    User = get_user_model()

    # Test with different roles
    test_users = [
        {
            'email': 'testsuperadmin@company.com',
            'password': 'testpass123',
            'role': 'SUPERADMIN',
            'expected_response': {
                'role': 'SUPERADMIN',
                'userId': 'should_be_number',
                'token': 'should_be_string'
            }
        },
        {
            'email': 'testemployer@company.com',
            'password': 'testpass123',
            'role': 'ADMINISTRATOR',
            'expected_response': {
                'role': 'ADMINISTRATOR',
                'userId': 'should_be_number',
                'companyId': 'should_be_number',
                'token': 'should_be_string'
            }
        },
        {
            'email': 'testemployee@company.com',
            'password': 'testpass123',
            'role': 'EMPLOYEE',
            'expected_response': {
                'role': 'EMPLOYEE',
                'userId': 'should_be_number',
                'employeeId': 'should_be_string',
                'token': 'should_be_string'
            }
        }
    ]

    print("=== TESTING LOGIN API ROLE RESPONSE ===")

    for user_data in test_users:
        print(f"\n--- Testing {user_data['role']} login ---")

        # Create test user if doesn't exist
        try:
            user = User.objects.get(email=user_data['email'])
            print(f"Using existing user: {user.email}")
        except User.DoesNotExist:
            user = User.objects.create_user(
                email=user_data['email'],
                password=user_data['password'],
                first_name='Test',
                last_name=user_data['role'].title(),
                role=user_data['role']
            )
            print(f"Created new user: {user.email}")

        # Test login
        login_data = {
            'email': user_data['email'],
            'password': user_data['password']
        }

        try:
            response = client.post('/api/v1/auth/login/', login_data, format='json')
            print(f"Login status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("Response data:")
                for key, value in data.items():
                    print(f"  {key}: {value} ({type(value).__name__})")

                # Validate expected fields
                expected = user_data['expected_response']
                for field, expected_type in expected.items():
                    if field in data:
                        if expected_type == 'should_be_number':
                            if not isinstance(data[field], int):
                                print(f"❌ ERROR: {field} should be number, got {type(data[field])}")
                            else:
                                print(f"✅ {field}: {data[field]} (number)")
                        elif expected_type == 'should_be_string':
                            if not isinstance(data[field], str):
                                print(f"❌ ERROR: {field} should be string, got {type(data[field])}")
                            else:
                                print(f"✅ {field}: {data[field]} (string)")
                        elif expected_type == data[field]:
                            print(f"✅ {field}: {data[field]} (matches expected: {expected_type})")
                        else:
                            print(f"❌ ERROR: {field} is {data[field]}, expected {expected_type}")
                    else:
                        print(f"❌ ERROR: Missing field {field} in response")

                # Check role specifically
                if data.get('role') != user_data['role']:
                    print(f"❌ ERROR: Role mismatch! Expected {user_data['role']}, got {data.get('role')}")
                else:
                    print(f"✅ Role correct: {data.get('role')}")

            else:
                print(f"❌ ERROR: Login failed with status {response.status_code}")
                print(f"Response: {response.content}")

        except Exception as e:
            print(f"❌ ERROR: Exception during login test: {e}")

    print("\n=== LOGIN API TEST COMPLETE ===")

if __name__ == '__main__':
    import os
    import django

    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
    django.setup()

    test_login_api()
