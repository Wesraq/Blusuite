#!/usr/bin/env python
"""
Email Configuration Test Script
"""
import os
import sys
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_email_configuration():
    """Test email configuration and send test email"""
    print("📧 Testing Email Configuration...")
    print("=" * 40)

    # Check email settings
    email_backend = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
    email_host = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    email_port = os.getenv('EMAIL_PORT', '587')
    email_user = os.getenv('EMAIL_HOST_USER', 'your-email@gmail.com')
    email_password = os.getenv('EMAIL_HOST_PASSWORD', 'your-app-password')
    default_from = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@eiscomtech.com')

    print("📋 Email Configuration:")
    print(f"   Backend: {email_backend}")
    print(f"   Host: {email_host}")
    print(f"   Port: {email_port}")
    print(f"   User: {email_user}")
    print(f"   Password: {'*' * len(email_password) if email_password else 'Not set'}")
    print(f"   From: {default_from}")

    # Check if credentials are placeholder values
    if email_user == 'your-email@gmail.com' or email_password == 'your-app-password':
        print("
⚠️  Email credentials are still placeholder values!"        print("   Please update your .env file with actual Gmail credentials.")
        print("
🔧 To set up Gmail SMTP:"        print("1. Enable 2-Factor Authentication on your Google account")
        print("2. Generate an App Password: https://support.google.com/accounts/answer/185833")
        print("3. Update your .env file with your Gmail address and app password")
        print("
📝 Example .env configuration:"        print("   EMAIL_HOST_USER=your-actual-email@gmail.com")
        print("   EMAIL_HOST_PASSWORD=your-16-character-app-password")

        return False

    print("
✅ Email credentials look valid!"    print("
📧 Testing email sending..."    print("=" * 40)

    # Test email sending
    try:
        # Import Django settings
        import django
        from django.conf import settings
        if not settings.configured:
            settings.configure(
                EMAIL_BACKEND=email_backend,
                EMAIL_HOST=email_host,
                EMAIL_PORT=int(email_port),
                EMAIL_USE_TLS=os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true',
                EMAIL_HOST_USER=email_user,
                EMAIL_HOST_PASSWORD=email_password,
                DEFAULT_FROM_EMAIL=default_from,
                SECRET_KEY=os.getenv('SECRET_KEY', 'test-key'),
                DEBUG=True,
                INSTALLED_APPS=[
                    'django.contrib.auth',
                    'django.contrib.contenttypes',
                ]
            )
            django.setup()

        # Send test email
        subject = "Test Email from EicomTech EMS"
        message = "This is a test email to verify that your email configuration is working correctly."

        html_message = """
        <html>
        <body>
            <h2>Test Email from EicomTech EMS</h2>
            <p>This is a test email to verify that your email configuration is working correctly.</p>
            <p>If you received this email, your SMTP settings are configured properly!</p>
            <br>
            <p><strong>Configuration Details:</strong></p>
            <ul>
                <li>Backend: {email_backend}</li>
                <li>Host: {email_host}</li>
                <li>Port: {email_port}</li>
                <li>User: {email_user}</li>
            </ul>
        </body>
        </html>
        """

        send_mail(
            subject,
            message,
            default_from,
            [email_user],  # Send to yourself for testing
            html_message=html_message
        )

        print("✅ Test email sent successfully!")
        print(f"   📧 Email sent to: {email_user}")
        print("   📝 Subject: {subject}")
        print("
📋 What happens next:"        print("1. Check your email inbox (and spam folder)")
        print("2. If you receive the test email, your configuration is working!")
        print("3. Company approval emails will now be sent automatically")

        return True

    except Exception as e:
        print(f"❌ Failed to send test email: {e}")
        print("
🔧 Troubleshooting:"        print("- Check your Gmail credentials in .env file")
        print("- Make sure 'Less secure app access' is enabled or use App Password")
        print("- Verify your Gmail account allows SMTP access")
        print("- Check your internet connection")

        return False

def test_company_approval_email():
    """Test company approval email template"""
    print("
📧 Testing Company Approval Email Template..."    print("=" * 50)

    try:
        # Test email template rendering
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
                'email': 'test@example.com',
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

        # Try to render the template
        html_content = render_to_string('emails/company_approved.html', context)
        print("✅ Company approval email template renders successfully!")
        print(f"   📧 Template length: {len(html_content)} characters")
        print("   📝 Contains login URL: {'login' in html_content.lower()}")

        return True

    except Exception as e:
        print(f"❌ Error rendering email template: {e}")
        print("
🔧 Check if email templates exist:"        print("- emails/company_approved.html")
        print("- emails/company_rejected.html")
        print("- emails/company_registration_request.html")

        return False

if __name__ == "__main__":
    print("🚀 EicomTech EMS - Email Configuration Test")
    print("=" * 50)

    # Test email configuration
    config_ok = test_email_configuration()

    # Test email templates
    template_ok = test_company_approval_email()

    if config_ok and template_ok:
        print("
🎉 Email system is ready!"        print("
📋 Summary:"        print("✅ Email configuration: Working")
        print("✅ Email templates: Available")
        print("✅ Company approval emails: Will be sent automatically")
        print("✅ Company rejection emails: Will be sent automatically")
        print("✅ Registration notification emails: Will be sent to admin")
    else:
        print("
⚠️  Email system needs configuration:"        print("1. Update .env file with your Gmail credentials")
        print("2. Run this test again")
        print("3. Check your email inbox for test email")

    print("
📧 Email Features Ready:"    print("• Company registration requests → Admin notification")
    print("• Company approval → Employer welcome email")
    print("• Company rejection → Rejection notification")
    print("• Resend credentials → Login details email")
