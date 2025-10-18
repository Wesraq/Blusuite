#!/usr/bin/env python
"""
Comprehensive Email System Test
"""
import os
import sys
import django
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_email_system():
    """Test the complete email system"""
    print("🚀 EicomTech EMS - Complete Email System Test")
    print("=" * 55)

    # Configure Django settings
    settings.configure(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST='mail.bcamcubed.co.zm',
        EMAIL_PORT=465,
        EMAIL_USE_TLS=False,
        EMAIL_USE_SSL=True,
        EMAIL_HOST_USER='e.simwanza@bcamcubed.co.zm',
        EMAIL_HOST_PASSWORD='M0t0r0!@',
        DEFAULT_FROM_EMAIL='noreply@eiscomtech.com',
        SECRET_KEY='test-key-for-email',
        DEBUG=True,
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
        ],
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': ['templates'],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }]
    )

    django.setup()

    # Test 1: Simple email
    print("📧 Test 1: Simple Email Send")
    print("-" * 30)

    try:
        send_mail(
            "EicomTech EMS - Email System Test",
            "This is a test email to verify that your email system is working correctly.",
            'noreply@eiscomtech.com',
            ['e.simwanza@bcamcubed.co.zm'],
            fail_silently=False
        )
        print("✅ Simple email sent successfully!")
    except Exception as e:
        print(f"❌ Simple email failed: {e}")
        return False

    # Test 2: Company approval email template
    print("
📧 Test 2: Company Approval Email Template"    print("-" * 45)

    try:
        context = {
            'company': type('Company', (), {
                'name': 'Test Company Ltd',
                'id': 1,
                'subscription_plan': 'STANDARD',
                'license_key': 'TEST123456789',
                'max_employees': 25,
                'license_expiry': None
            })(),
            'employer': type('User', (), {
                'email': 'test@company.com',
                'user': type('UserProfile', (), {
                    'get_generated_password': lambda: 'TempPass123!'
                })()
            })(),
            'login_url': 'http://127.0.0.1:8000/login/',
            'license_info': {
                'plan': 'STANDARD',
                'license_key': 'TEST123456789',
                'max_employees': 25,
                'expiry': None
            }
        }

        html_content = render_to_string('emails/company_approved.html', context)
        print("✅ Company approval template renders successfully! ({len(html_content)} chars)")

        # Test 3: Send actual company approval email
        print("📧 Test 3: Company Approval Email with Template")
        print("-" * 50)

        send_mail(
            "Company Registration Approved - Test Company Ltd",
            "Company approval email with HTML template",
            'noreply@eiscomtech.com',
            ['e.simwanza@bcamcubed.co.zm'],
            html_message=html_content,
            fail_silently=False
        )
        print("✅ Company approval email sent successfully!")

    except Exception as e:
        print(f"❌ Company approval email failed: {e}")
        return False

    # Test 4: Company rejection email
    print("
📧 Test 4: Company Rejection Email"    print("-" * 40)

    try:
        rejection_context = {
            'request': type('Request', (), {
                'company_name': 'Rejected Company Ltd',
                'contact_email': 'contact@rejectedcompany.com'
            })(),
            'rejection_reason': 'Company information incomplete'
        }

        rejection_html = render_to_string('emails/company_rejected.html', rejection_context)
        print(f"✅ Company rejection template renders successfully! ({len(rejection_html)} chars)")

        send_mail(
            "Company Registration Update - Rejected Company Ltd",
            "Company rejection notification",
            'noreply@eiscomtech.com',
            ['e.simwanza@bcamcubed.co.zm'],
            html_message=rejection_html,
            fail_silently=False
        )
        print("✅ Company rejection email sent successfully!")

    except Exception as e:
        print(f"❌ Company rejection email failed: {e}")
        return False

    return True

if __name__ == "__main__":
    success = test_email_system()

    if success:
        print("
🎉 ALL EMAIL TESTS PASSED!"        print("
📋 Your Email System is Ready:"        print("✅ Simple emails: Working")
        print("✅ Company approval emails: Working")
        print("✅ Company rejection emails: Working")
        print("✅ Email templates: All available")
        print("✅ SMTP server connection: Working")
        print("
📧 What happens now:"        print("• Company registrations will send admin notifications")
        print("• Company approvals will send welcome emails")
        print("• Company rejections will send rejection notifications")
        print("• All emails will be sent through your BCAM Cubed server")
        print("
📬 Check your inbox at e.simwanza@bcamcubed.co.zm for test emails!"    else:
        print("
❌ Some email tests failed"        print("
🔧 Troubleshooting:"        print("• Check your email server settings")
        print("• Verify your email credentials")
        print("• Make sure your email account allows SMTP")
        print("• Check firewall and network settings")
