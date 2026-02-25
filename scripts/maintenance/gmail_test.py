#!/usr/bin/env python
"""
Gmail SMTP Test Script
"""
import os
import sys
import django
from django.core.mail import send_mail
from django.conf import settings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_gmail_smtp():
    """Test Gmail SMTP configuration"""
    print("🚀 Testing Gmail SMTP Configuration...")
    print("=" * 50)

    # Check configuration
    email_host = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    email_port = os.getenv('EMAIL_PORT', '587')
    email_user = os.getenv('EMAIL_HOST_USER', 'emmanuelsimwanza2@gmail.com')
    email_password = os.getenv('EMAIL_HOST_PASSWORD', 'YOUR_GMAIL_APP_PASSWORD_HERE')

    print("📋 Gmail Configuration:")
    print(f"   Host: {email_host}")
    print(f"   Port: {email_port}")
    print(f"   User: {email_user}")
    print(f"   Password: {'*' * len(email_password) if email_password != 'YOUR_GMAIL_APP_PASSWORD_HERE' else '❌ NOT SET'}")
    print(f"   TLS: {os.getenv('EMAIL_USE_TLS', 'True')}")
    print(f"   SSL: {os.getenv('EMAIL_USE_SSL', 'False')}")

    if email_password == 'YOUR_GMAIL_APP_PASSWORD_HERE':
        print("
❌ Please update your .env file with your Gmail App Password!"        print("
🔧 Steps:"        print("1. Get Gmail App Password: https://support.google.com/accounts/answer/185833")
        print("2. Replace 'YOUR_GMAIL_APP_PASSWORD_HERE' in .env file")
        print("3. Run this test again")

        return False

    print("
✅ Configuration looks good!"    print("📧 Testing email sending..."    print("=" * 30)

    # Configure Django
    settings.configure(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST=email_host,
        EMAIL_PORT=int(email_port),
        EMAIL_USE_TLS=os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true',
        EMAIL_USE_SSL=os.getenv('EMAIL_USE_SSL', 'False').lower() == 'true',
        EMAIL_HOST_USER=email_user,
        EMAIL_HOST_PASSWORD=email_password,
        DEFAULT_FROM_EMAIL='noreply@eiscomtech.com',
        SECRET_KEY='test-key-for-email',
        DEBUG=True,
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
        ]
    )

    django.setup()

    try:
        # Test 1: Simple email
        print("📧 Test 1: Simple Email")
        send_mail(
            'EicomTech EMS - Gmail Test',
            'This is a test email to verify Gmail SMTP is working correctly.',
            'noreply@eiscomtech.com',
            [email_user],
            fail_silently=False
        )
        print("✅ Simple email sent successfully!")

        # Test 2: HTML email with template
        print("
📧 Test 2: Company Approval Email Template"        from django.template.loader import render_to_string

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
                'first_name': 'Test',
                'last_name': 'User'
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
        print(f"✅ Email template rendered successfully! ({len(html_content)} characters)")

        # Test 3: Send HTML email
        print("
📧 Test 3: HTML Email with Template"        send_mail(
            'Company Registration Approved - Test Company Ltd',
            'Company approval email with HTML template',
            'noreply@eiscomtech.com',
            [email_user],
            html_message=html_content,
            fail_silently=False
        )
        print("✅ HTML approval email sent successfully!")

        print("
🎉 ALL TESTS PASSED!"        print("
📧 Check your Gmail inbox at:"        print(f"   📬 {email_user}")
        print("
📋 You should receive:"        print("   ✅ Simple test email")
        print("   ✅ Company approval email with HTML formatting")
        print("
⏱️  Expected delivery time: 1-2 minutes"        print("
📂 Check spam folder if not in inbox"        return True

    except Exception as e:
        print(f"❌ Email test failed: {e}")
        print("
🔧 Troubleshooting:"        print("- Verify your Gmail App Password is correct")
        print("- Check if 2-Factor Authentication is enabled")
        print("- Make sure 'Less secure app access' is disabled")
        print("- Try regenerating the App Password")

        return False

if __name__ == "__main__":
    print("🚀 EicomTech EMS - Gmail SMTP Test")
    print("=" * 50)

    success = test_gmail_smtp()

    if success:
        print("
🎉 Gmail SMTP is working perfectly!"        print("
📧 Your email system is ready!"        print("✅ Simple emails: Working")
        print("✅ HTML templates: Working")
        print("✅ Company approval emails: Ready")
        print("✅ Professional formatting: Ready")
        print("
📬 Check your inbox for test emails!"    else:
        print("
❌ Gmail SMTP needs configuration"        print("
🔧 Please:"        print("1. Get Gmail App Password: https://support.google.com/accounts/answer/185833")
        print("2. Update your .env file with the 16-character App Password")
        print("3. Run this test again")
