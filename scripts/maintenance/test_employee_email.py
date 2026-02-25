#!/usr/bin/env python
"""
Test script for employee email notifications
"""
import os
import sys
import django

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from ems_project.notifications import EmailNotificationService

User = get_user_model()

def test_new_employee_email():
    """Test new employee credentials email"""
    print("=" * 60)
    print("Testing New Employee Credentials Email")
    print("=" * 60)
    
    # Get a test employee
    employee = User.objects.filter(role='EMPLOYEE').first()
    admin = User.objects.filter(role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']).first()
    
    if not employee:
        print("❌ No employee found in database")
        return
    
    test_password = "Test123!@#"
    
    print(f"\n📧 Sending welcome email to: {employee.email}")
    print(f"   Employee: {employee.get_full_name()}")
    print(f"   Company: {employee.company.company_name if employee.company else 'N/A'}")
    print(f"   Test Password: {test_password}")
    
    try:
        EmailNotificationService.send_new_employee_credentials(
            employee=employee,
            temporary_password=test_password,
            created_by=admin
        )
        print("\n✅ Email sent successfully!")
        print(f"   Check inbox at: {employee.email}")
    except Exception as e:
        print(f"\n❌ Error sending email: {str(e)}")
        import traceback
        traceback.print_exc()


def test_password_reset_email():
    """Test password reset notification email"""
    print("\n" + "=" * 60)
    print("Testing Password Reset Notification Email")
    print("=" * 60)
    
    # Get a test employee
    employee = User.objects.filter(role='EMPLOYEE').first()
    admin = User.objects.filter(role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']).first()
    
    if not employee:
        print("❌ No employee found in database")
        return
    
    new_password = "NewPass456!@#"
    
    print(f"\n📧 Sending password reset email to: {employee.email}")
    print(f"   Employee: {employee.get_full_name()}")
    print(f"   Reset by: {admin.get_full_name() if admin else 'Administrator'}")
    print(f"   New Password: {new_password}")
    
    try:
        EmailNotificationService.send_password_changed_notification(
            employee=employee,
            new_password=new_password,
            changed_by=admin
        )
        print("\n✅ Email sent successfully!")
        print(f"   Check inbox at: {employee.email}")
    except Exception as e:
        print(f"\n❌ Error sending email: {str(e)}")
        import traceback
        traceback.print_exc()


def check_email_config():
    """Check email configuration"""
    print("\n" + "=" * 60)
    print("Email Configuration Status")
    print("=" * 60)
    
    from django.conf import settings
    
    config = {
        'EMAIL_BACKEND': settings.EMAIL_BACKEND,
        'EMAIL_HOST': settings.EMAIL_HOST,
        'EMAIL_PORT': settings.EMAIL_PORT,
        'EMAIL_USE_TLS': settings.EMAIL_USE_TLS,
        'EMAIL_HOST_USER': settings.EMAIL_HOST_USER,
        'DEFAULT_FROM_EMAIL': settings.DEFAULT_FROM_EMAIL,
    }
    
    for key, value in config.items():
        status = "✅" if value else "⚠️"
        if key == 'EMAIL_HOST_PASSWORD':
            value = "***" if value else "Not Set"
        print(f"{status} {key}: {value}")
    
    if not settings.EMAIL_HOST_USER or settings.EMAIL_HOST_PASSWORD == 'YOUR_GMAIL_APP_PASSWORD_HERE':
        print("\n⚠️  WARNING: Email credentials not configured!")
        print("   Update EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env file")


if __name__ == '__main__':
    print("\n🧪 Employee Email Notification Test Suite")
    print("=" * 60)
    
    check_email_config()
    
    print("\n\nSelect test to run:")
    print("1. Test New Employee Welcome Email")
    print("2. Test Password Reset Email")
    print("3. Run All Tests")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == '1':
        test_new_employee_email()
    elif choice == '2':
        test_password_reset_email()
    elif choice == '3':
        test_new_employee_email()
        test_password_reset_email()
    elif choice == '4':
        print("\n👋 Exiting...")
    else:
        print("\n❌ Invalid choice")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60 + "\n")
