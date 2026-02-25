"""
Email Integration Settings Views
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
import json


@login_required
def email_integration_settings(request):
    """Email integration configuration page"""
    # Check permissions
    is_admin = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    has_hr_access = False
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_hr_access = request.user.employee_profile.employee_role == 'HR'
    
    if not (is_admin or has_hr_access):
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(request.user, 'company', None)
    if not company:
        messages.error(request, 'No company associated with your account.')
        return redirect('employer_dashboard')
    
    # Get or create email settings
    from blu_staff.apps.accounts.models import CompanyEmailSettings
    email_settings, created = CompanyEmailSettings.objects.get_or_create(company=company)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save_settings':
            # Update email settings
            email_settings.smtp_host = request.POST.get('smtp_host', '')
            email_settings.smtp_port = int(request.POST.get('smtp_port', 587))
            email_settings.smtp_username = request.POST.get('smtp_username', '')
            email_settings.smtp_use_tls = request.POST.get('smtp_use_tls') == 'on'
            email_settings.smtp_use_ssl = request.POST.get('smtp_use_ssl') == 'on'
            email_settings.from_email = request.POST.get('from_email', '')
            email_settings.from_name = request.POST.get('from_name', '')
            
            # Only update password if provided
            smtp_password = request.POST.get('smtp_password', '')
            if smtp_password:
                email_settings.smtp_password = smtp_password
            
            # Email notification toggles
            email_settings.enable_email_notifications = request.POST.get('enable_email_notifications') == 'on'
            email_settings.enable_performance_emails = request.POST.get('enable_performance_emails') == 'on'
            email_settings.enable_leave_emails = request.POST.get('enable_leave_emails') == 'on'
            email_settings.enable_attendance_emails = request.POST.get('enable_attendance_emails') == 'on'
            email_settings.enable_payroll_emails = request.POST.get('enable_payroll_emails') == 'on'
            email_settings.enable_training_emails = request.POST.get('enable_training_emails') == 'on'
            email_settings.enable_document_emails = request.POST.get('enable_document_emails') == 'on'
            
            email_settings.save()
            messages.success(request, 'Email settings saved successfully!')
            return redirect('email_integration_settings')
        
        elif action == 'test_email':
            # Send test email
            test_recipient = request.POST.get('test_email_address', request.user.email)
            
            try:
                # Temporarily override Django email settings
                from django.core.mail import get_connection
                
                connection = get_connection(
                    host=email_settings.smtp_host,
                    port=email_settings.smtp_port,
                    username=email_settings.smtp_username,
                    password=email_settings.smtp_password,
                    use_tls=email_settings.smtp_use_tls,
                    use_ssl=email_settings.smtp_use_ssl,
                    fail_silently=False,
                )
                
                send_mail(
                    subject='Test Email from BluSuite EMS',
                    message='This is a test email to verify your SMTP configuration is working correctly.',
                    from_email=f'{email_settings.from_name} <{email_settings.from_email}>',
                    recipient_list=[test_recipient],
                    connection=connection,
                    fail_silently=False,
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Test email sent successfully to {test_recipient}'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=400)
    
    context = {
        'email_settings': email_settings,
        'has_password': bool(email_settings.smtp_password),
    }
    
    return render(request, 'integrations/email_settings.html', context)


@login_required
def toggle_email_notifications(request):
    """Quick toggle for email notifications"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)
    
    company = getattr(request.user, 'company', None)
    if not company:
        return JsonResponse({'success': False, 'error': 'No company'}, status=400)
    
    from blu_staff.apps.accounts.models import CompanyEmailSettings
    email_settings, _ = CompanyEmailSettings.objects.get_or_create(company=company)
    
    # Toggle the main switch
    email_settings.enable_email_notifications = not email_settings.enable_email_notifications
    email_settings.save()
    
    return JsonResponse({
        'success': True,
        'enabled': email_settings.enable_email_notifications
    })
