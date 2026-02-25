#!/usr/bin/env python
"""
Simple Email Test for BCAM Cubed Server
"""
import os
import sys
import django
from django.core.mail import send_mail
from django.conf import settings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_simple_email():
    """Send a simple test email"""
    print("📧 Testing Simple Email Send...")
    print("=" * 40)

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
        ]
    )

    django.setup()

    try:
        # Send simple test email
        subject = "Test Email from EicomTech EMS"
        message = "This is a simple test email to verify that your BCAM Cubed email server is working correctly."

        send_mail(
            subject,
            message,
            'noreply@eiscomtech.com',
            ['e.simwanza@bcamcubed.co.zm'],
            fail_silently=False
        )

        print("✅ Test email sent successfully!")
        print("📧 Email sent to: e.simwanza@bcamcubed.co.zm")
        print("📝 Subject: Test Email from EicomTech EMS")
        print("
📋 Next Steps:"        print("1. Check your email inbox at e.simwanza@bcamcubed.co.zm")
        print("2. If you receive the email, your configuration is working!")
        print("3. Company approval emails will now be sent automatically")

        return True

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print("
🔧 Troubleshooting:"        print("- Check if your email server allows SMTP connections")
        print("- Verify your email credentials are correct")
        print("- Make sure your email account allows external connections")
        print("- Check if there are any firewall restrictions")

        return False

if __name__ == "__main__":
    test_simple_email()
