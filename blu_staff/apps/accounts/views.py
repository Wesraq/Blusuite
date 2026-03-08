from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Q, Count, F
from datetime import date, timedelta
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.http import HttpResponse
import csv

User = get_user_model()

from .models import User, EmployeeProfile, EmployerProfile, Company, CompanyRegistrationRequest
from .serializers import (
    UserRegisterSerializer,
    UserLoginSerializer,
    UserSerializer,
    EmployeeProfileSerializer,
    EmployerProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)

@login_required
def company_list(request):
    """List all companies with approval workflow"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('/')

    # Filters and search
    search_query = request.GET.get('search', '').strip()
    plan_filter = request.GET.get('plan', '')
    billing_filter = request.GET.get('billing', '')
    license_filter = request.GET.get('license', '')
    export_type = request.GET.get('export', '')

    # Get pending registration requests (not approved companies)
    pending_requests = CompanyRegistrationRequest.objects.filter(status='PENDING').order_by('-created_at')

    # Base queryset for approved companies
    approved_companies = Company.objects.filter(is_approved=True, is_active=True).order_by('-created_at')

    # Apply search filter
    if search_query:
        approved_companies = approved_companies.filter(
            Q(name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(website__icontains=search_query)
        )

    # Apply subscription plan filter
    if plan_filter:
        approved_companies = approved_companies.filter(subscription_plan=plan_filter)

    # Apply billing preference filter (via registration request)
    if billing_filter:
        approved_companies = approved_companies.filter(
            registration_request__billing_preference=billing_filter
        )

    today = date.today()
    window_end = today + timedelta(days=30)

    # Apply license status filter
    if license_filter:
        if license_filter == 'trial':
            approved_companies = approved_companies.filter(is_trial=True)
        elif license_filter == 'active':
            approved_companies = approved_companies.filter(
                Q(is_trial=False)
                & (Q(license_expiry__isnull=True) | Q(license_expiry__gt=today))
            )
        elif license_filter == 'expired':
            approved_companies = approved_companies.filter(
                Q(is_trial=True, trial_ends_at__isnull=False, trial_ends_at__date__lt=today)
                | Q(
                    is_trial=False,
                    license_expiry__isnull=False,
                    license_expiry__lt=today,
                )
            )
        elif license_filter == 'expiring_30':
            approved_companies = approved_companies.filter(
                Q(
                    is_trial=True,
                    trial_ends_at__isnull=False,
                    trial_ends_at__date__gt=today,
                    trial_ends_at__date__lte=window_end,
                )
                | Q(
                    is_trial=False,
                    license_expiry__isnull=False,
                    license_expiry__gt=today,
                    license_expiry__lte=window_end,
                )
            )

    # Rejected companies (for information only)
    rejected_companies = Company.objects.filter(
        is_approved=False, is_active=False
    ).exclude(created_at__date=date.today()).order_by('-created_at')

    # Identify at-risk companies for highlighting
    expiring_soon_ids = list(
        approved_companies.filter(
            Q(
                is_trial=True,
                trial_ends_at__isnull=False,
                trial_ends_at__date__gt=today,
                trial_ends_at__date__lte=window_end,
            )
            | Q(
                is_trial=False,
                license_expiry__isnull=False,
                license_expiry__gt=today,
                license_expiry__lte=window_end,
            )
        ).values_list('id', flat=True)
    )

    expired_ids = list(
        approved_companies.filter(
            Q(is_trial=True, trial_ends_at__isnull=False, trial_ends_at__date__lt=today)
            | Q(
                is_trial=False,
                license_expiry__isnull=False,
                license_expiry__lt=today,
            )
        ).values_list('id', flat=True)
    )

    trial_ids = list(
        approved_companies.filter(is_trial=True).values_list('id', flat=True)
    )

    # CSV export for approved companies (respecting filters)
    if export_type == 'companies':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="companies_summary.csv"'
        writer = csv.writer(response)

        writer.writerow([
            'Company Name',
            'Email',
            'Phone',
            'Subscription Plan',
            'Billing Preference',
            'Is Trial',
            'Trial Ends',
            'License Expiry',
            'Approved At',
        ])

        for company in approved_companies:
            billing_pref = (
                company.registration_request.get_billing_preference_display()
                if company.registration_request
                else ''
            )

            writer.writerow(
                [
                    company.name,
                    company.email,
                    company.phone,
                    company.get_subscription_plan_display(),
                    billing_pref,
                    'Yes' if company.is_trial else 'No',
                    company.trial_ends_at.strftime('%Y-%m-%d')
                    if company.trial_ends_at
                    else '',
                    company.license_expiry.strftime('%Y-%m-%d')
                    if company.license_expiry
                    else '',
                    company.approved_at.strftime('%Y-%m-%d %H:%M')
                    if company.approved_at
                    else '',
                ]
            )

        return response

    context = {
        'user': request.user,  # Add user to context for navigation
        'pending_companies': pending_requests,
        'approved_companies': approved_companies,
        'rejected_companies': rejected_companies,
        'total_pending': pending_requests.count(),
        'total_approved': approved_companies.count(),
        'total_rejected': rejected_companies.count(),
        # Filters
        'search_query': search_query,
        'plan_filter': plan_filter,
        'billing_filter': billing_filter,
        'license_filter': license_filter,
        'plan_choices': CompanyRegistrationRequest.SubscriptionPlan.choices,
        'billing_choices': CompanyRegistrationRequest.BillingPreference.choices,
        # Highlighting helpers
        'expiring_soon_ids': expiring_soon_ids,
        'expired_ids': expired_ids,
        'trial_ids': trial_ids,
    }
    return render(request, 'ems/company_list.html', context)


@login_required
def approve_company(request, request_id):
    """Approve a company registration request"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    # Get the registration request
    registration_request = get_object_or_404(CompanyRegistrationRequest, id=request_id, status='PENDING')

    if request.method == 'POST':
        try:
            # Check if this registration request is already linked to a company
            existing_company = Company.objects.filter(registration_request=registration_request).first()

            if existing_company:
                # Registration request already processed, just update status and send email
                messages.info(request, f'Company registration request {registration_request.id} has already been processed. Company "{existing_company.name}" already exists.')

                # Update registration request status if not already approved
                if registration_request.status != 'APPROVED':
                    registration_request.status = 'APPROVED'
                    registration_request.reviewed_by = request.user
                    registration_request.reviewed_at = timezone.now()
                    registration_request.review_notes = request.POST.get('review_notes', '')
                    registration_request.save()

                # Find the employer user account for this company
                employer_user = User.objects.filter(
                    company=existing_company,
                    role='ADMINISTRATOR'
                ).first()

                if employer_user:
                    # Send approval email to employer
                    try:
                        subject = f'Company Registration Approved - {existing_company.name}'
                        message = render_to_string('emails/company_approved.html', {
                            'company': existing_company,
                            'employer': employer_user,
                            'login_url': f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/",
                            'license_info': {
                                'plan': existing_company.subscription_plan,
                                'license_key': existing_company.license_key,
                                'max_employees': existing_company.max_employees,
                                'expiry': existing_company.license_expiry,
                            }
                        })

                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [registration_request.contact_email],
                            html_message=message
                        )
                    except Exception:
                        pass

                    messages.success(
                        request,
                        f'Company registration already approved! Login credentials resent to {registration_request.contact_email}'
                    )
                else:
                    messages.warning(request, 'Company exists but no administrator account found. Please contact support.')

                return redirect('company_list')

            # Get password from form or generate new one
            admin_password = request.POST.get('admin_password')
            if admin_password:
                # Use admin-provided password
                final_password = admin_password
            else:
                # Generate new password
                import random, string
                final_password = ''.join(random.choices(string.ascii_letters + string.digits + '!@#$%', k=12))

            # Create company from registration request
            company = Company.objects.create(
                name=registration_request.company_name,
                address=registration_request.company_address,
                phone=registration_request.company_phone,
                email=registration_request.company_email,
                website=registration_request.company_website,
                tax_id=registration_request.tax_id,
                subscription_plan=registration_request.subscription_plan,
                max_employees=registration_request.number_of_employees,
                registration_request=registration_request,
                is_approved=True,
                is_active=True,  # Explicitly set to True
                approved_by=request.user,
                approved_at=timezone.now()
            )

            # Create employer user account
            # First check if user already exists with this email
            employer_user = User.objects.filter(email=registration_request.contact_email).first()

            if employer_user:
                # User already exists, update their information
                employer_user.first_name = registration_request.contact_first_name
                employer_user.last_name = registration_request.contact_last_name
                employer_user.role = 'ADMINISTRATOR'
                employer_user.company = company
                employer_user.must_change_password = True
                employer_user.is_active = True
                employer_user.save()

                # Update or create employer profile
                employer_profile, created = EmployerProfile.objects.get_or_create(
                    user=employer_user,
                    defaults={
                        'company_name': registration_request.company_name,
                        'company_address': registration_request.company_address,
                        'company_phone': registration_request.company_phone,
                        'company_email': registration_request.company_email,
                        'tax_id': registration_request.tax_id,
                        'company': company
                    }
                )

                if not created:
                    # Update existing profile
                    employer_profile.company_name = registration_request.company_name
                    employer_profile.company_address = registration_request.company_address
                    employer_profile.company_phone = registration_request.company_phone
                    employer_profile.company_email = registration_request.company_email
                    employer_profile.tax_id = registration_request.tax_id
                    employer_profile.company = company
                    employer_profile.save()

                messages.info(request, f'Updated existing user account for {registration_request.contact_email}')
            else:
                # Create new employer user account
                employer_user = User.objects.create_user(
                    email=registration_request.contact_email,
                    password=final_password,
                    first_name=registration_request.contact_first_name,
                    last_name=registration_request.contact_last_name,
                    role='ADMINISTRATOR',
                    company=company,
                    must_change_password=True,  # Force password change on first login
                    is_active=True
                )

                # Create employer profile
                EmployerProfile.objects.create(
                    user=employer_user,
                    company_name=registration_request.company_name,
                    company_address=registration_request.company_address,
                    company_phone=registration_request.company_phone,
                    company_email=registration_request.company_email,
                    tax_id=registration_request.tax_id,
                    company=company
                )

            # Update registration request status
            registration_request.status = 'APPROVED'
            registration_request.reviewed_by = request.user
            registration_request.reviewed_at = timezone.now()
            registration_request.review_notes = request.POST.get('review_notes', '')
            registration_request.save()

            # Debug: Check company status

            # Send approval email to employer
            try:
                subject = f'Company Registration Approved - {company.name}'
                message = render_to_string('emails/company_approved.html', {
                    'company': company,
                    'employer': employer_user,
                    'password': final_password,
                    'login_url': f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/",
                    'license_info': {
                        'plan': company.subscription_plan,
                        'license_key': company.license_key,
                        'max_employees': company.max_employees,
                        'expiry': company.license_expiry,
                    }
                })

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [registration_request.contact_email],
                    html_message=message
                )
            except Exception:                pass
            messages.success(
                request,
                f'Company registration approved! Login credentials sent to {registration_request.contact_email}'
            )
            return redirect('company_list')

        except Exception as e:
            messages.error(request, f'Error approving company registration: {str(e)}')
            return redirect('company_list')

    # GET request - show approval form
    context = {
        'registration_request': registration_request
    }
    return render(request, 'ems/approve_company_registration.html', context)


def reject_company(request, request_id):
    """Reject a company registration request"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    # Get the registration request instead of company
    registration_request = get_object_or_404(CompanyRegistrationRequest, id=request_id, status='PENDING')

    if request.method == 'POST':
        try:
            registration_request.status = 'REJECTED'
            registration_request.reviewed_by = request.user
            registration_request.reviewed_at = timezone.now()
            registration_request.rejection_reason = request.POST.get('rejection_reason', '')
            registration_request.save()

            # Send rejection email
            try:
                subject = f'Company Registration Update - {registration_request.company_name}'
                message = render_to_string('emails/company_rejected.html', {
                    'request': registration_request,
                    'rejection_reason': registration_request.rejection_reason
                })

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [registration_request.contact_email],
                    html_message=message
                )
            except Exception:                pass
            messages.success(request, 'Company registration rejected.')
            return redirect('company_list')

        except Exception as e:
            messages.error(request, f'Error rejecting company registration: {str(e)}')
            return redirect('company_list')

    # GET request - show rejection form
    context = {
        'registration_request': registration_request
    }
    return render(request, 'ems/reject_company_registration.html', context)


@login_required
def company_create(request):
    """Create new company request (public access)"""
    # Anyone can create a company request, but it needs approval

    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        website = request.POST.get('website')
        tax_id = request.POST.get('tax_id')

        if name and address and email:
            try:
                # Check if company with this name or email already exists
                existing_company = Company.objects.filter(
                    models.Q(name=name) | models.Q(email=email)
                ).first()

                if existing_company:
                    if existing_company.is_approved:
                        messages.error(request, 'A company with this name or email already exists.')
                    else:
                        messages.info(request, 'Your company request is already pending approval.')
                    return redirect('company_create')

                # Create company request (not approved yet)
                company = Company.objects.create(
                    name=name,
                    address=address,
                    phone=phone,
                    email=email,
                    website=website,
                    tax_id=tax_id,
                    is_active=False,  # Requires approval
                    is_approved=False
                )

                messages.success(request, 'Company request submitted successfully! You will receive an email when approved.')
                return redirect('/')
            except Exception as e:
                messages.error(request, f'Error creating company request: {str(e)}')
        else:
            messages.error(request, 'Company name, address, and email are required.')

    return render(request, 'ems/company_request_form.html', {'action': 'Request Company'})


@login_required
def company_edit(request, company_id):
    """Edit existing company"""
    # Permit SuperAdmin and Employer roles to edit company profile from employer portal
    if request.user.role not in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        messages.error(request, 'Access denied.')
        try:
            return redirect('employer_dashboard')
        except Exception:
            return redirect('/')

    company = get_object_or_404(Company, id=company_id)

    if request.method == 'POST':
        # Check which form is being submitted
        form_type = request.POST.get('form_type', '')
        
        # Handle documents form submission
        if form_type == 'basic_info':
            # Explicit basic info form submission - fall through to name/address handler
            pass  # handled below

        elif form_type == 'documents':
            try:
                # Handle company documents
                if 'tax_certificate' in request.FILES:
                    company.tax_certificate = request.FILES['tax_certificate']
                if 'business_registration' in request.FILES:
                    company.business_registration = request.FILES['business_registration']
                if 'trade_license' in request.FILES:
                    company.trade_license = request.FILES['trade_license']
                if 'napsa_certificate' in request.FILES:
                    company.napsa_certificate = request.FILES['napsa_certificate']
                if 'nhima_certificate' in request.FILES:
                    company.nhima_certificate = request.FILES['nhima_certificate']
                if 'workers_compensation' in request.FILES:
                    company.workers_compensation = request.FILES['workers_compensation']
                
                # Handle stamp upload
                if 'company_stamp' in request.FILES:
                    company.company_stamp = request.FILES['company_stamp']
                
                # Handle signature uploads with user assignments
                if 'signature' in request.FILES:
                    company.signature = request.FILES['signature']
                
                # Handle authorized signatures for specific users
                for key in request.FILES:
                    if key.startswith('authorized_signature_'):
                        user_id = key.replace('authorized_signature_', '')
                        try:
                            user = User.objects.get(id=user_id, company=company)
                            user.signature = request.FILES[key]
                            user.save()
                        except User.DoesNotExist:
                            pass
                # Handle stamp rotation
                if 'stamp_rotation' in request.POST:
                    try:
                        rotation = int(request.POST.get('stamp_rotation', 0))
                        company.stamp_rotation = rotation % 360  # Normalize to 0-360
                    except (ValueError, TypeError):
                        company.stamp_rotation = 0

                
                company.save()
                messages.success(request, '✅ Documents, stamps, and signatures saved successfully!')
                return redirect(request.path)
            except Exception as e:
                messages.error(request, f'Error saving documents: {str(e)}')
                return redirect(request.path)
        
        # Check if this is a color-only update (from Colors & Theme tab)
        elif 'primary_color' in request.POST and 'name' not in request.POST:
            try:
                # Handle corporate colors only
                if 'primary_color' in request.POST:
                    company.primary_color = request.POST.get('primary_color', '#3b82f6')
                if 'secondary_color' in request.POST:
                    company.secondary_color = request.POST.get('secondary_color', '#10b981')
                if 'text_color' in request.POST:
                    company.text_color = request.POST.get('text_color', '#1e293b')
                if 'background_color' in request.POST:
                    company.background_color = request.POST.get('background_color', '#ffffff')
                if 'card_header_color' in request.POST:
                    company.card_header_color = request.POST.get('card_header_color', '#10b981')
                if 'button_color' in request.POST:
                    company.button_color = request.POST.get('button_color', '#3b82f6')
                
                company.save()
                
                # Refresh the company in the session
                if request.user.company and request.user.company.id == company.id:
                    request.user.company.refresh_from_db()
                
                # For AJAX requests, just return success
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'success': True, 'message': 'Colors updated successfully'})
                
                messages.success(request, 'Colors updated successfully!')
                return redirect(request.path)  # Stay on same page
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'success': False, 'error': str(e)}, status=400)
                messages.error(request, f'Error updating colors: {str(e)}')
        
        # Handle branding / logo-only upload
        elif request.POST.get('action') == 'company_profile' or (
            'logo' in request.FILES and not request.POST.get('name')
        ):
            try:
                if 'logo' in request.FILES:
                    company.logo = request.FILES['logo']
                messages.success(request, 'Logo saved successfully!')
                company.save()
            except Exception as e:
                messages.error(request, f'Error saving logo: {str(e)}')
            return redirect(request.path)

        # Regular form submission (Basic Info)
        name = request.POST.get('name')
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        website = request.POST.get('website')
        tax_id = request.POST.get('tax_id')
        city = request.POST.get('city')
        country = request.POST.get('country')
        admin_password = request.POST.get('admin_password')

        if name and address:
            try:
                company.name = name
                company.address = address
                company.phone = phone or ''
                company.email = email or ''
                company.website = website or ''
                company.tax_id = tax_id or ''
                company.city = city or ''
                company.country = country or 'Zambia'
                
                # Handle logo upload
                if 'logo' in request.FILES:
                    company.logo = request.FILES['logo']
                
                # Handle stamp upload
                if 'company_stamp' in request.FILES:
                    company.company_stamp = request.FILES['company_stamp']
                
                # Handle signature uploads with user assignments
                if 'signature' in request.FILES:
                    company.signature = request.FILES['signature']
                
                # Handle authorized signatures for specific users
                for key in request.FILES:
                    if key.startswith('authorized_signature_'):
                        user_id = key.replace('authorized_signature_', '')
                        try:
                            user = User.objects.get(id=user_id, company=company)
                            # Store signature with user reference (you may need to create a model for this)
                            # For now, storing in a simple way
                            signature_file = request.FILES[key]
                            # Save signature associated with user
                            user.signature = signature_file
                            user.save()
                        except User.DoesNotExist:
                            pass
                
                # Handle company documents
                if 'tax_certificate' in request.FILES:
                    company.tax_certificate = request.FILES['tax_certificate']
                if 'business_registration' in request.FILES:
                    company.business_registration = request.FILES['business_registration']
                if 'trade_license' in request.FILES:
                    company.trade_license = request.FILES['trade_license']
                if 'napsa_certificate' in request.FILES:
                    company.napsa_certificate = request.FILES['napsa_certificate']
                if 'nhima_certificate' in request.FILES:
                    company.nhima_certificate = request.FILES['nhima_certificate']
                if 'workers_compensation' in request.FILES:
                    company.workers_compensation = request.FILES['workers_compensation']
                
                # Handle corporate colors
                if 'primary_color' in request.POST:
                    company.primary_color = request.POST.get('primary_color', '#3b82f6')
                if 'secondary_color' in request.POST:
                    company.secondary_color = request.POST.get('secondary_color', '#10b981')
                if 'text_color' in request.POST:
                    company.text_color = request.POST.get('text_color', '#1e293b')
                if 'background_color' in request.POST:
                    company.background_color = request.POST.get('background_color', '#ffffff')
                
                company.save()
                
                # Refresh the company in the session to ensure updated colors are loaded
                if request.user.company and request.user.company.id == company.id:
                    request.user.company.refresh_from_db()

                # Update administrator password if provided
                if admin_password and admin_password.strip():
                    # Find the administrator user for this company
                    admin_user = User.objects.filter(
                        company=company,
                        role='ADMINISTRATOR'
                    ).first()

                    if admin_user:
                        admin_user.set_password(admin_password)
                        admin_user.must_change_password = True  # Force password change on next login
                        admin_user.save()

                        # Send email notification about password change
                        try:
                            subject = f'Password Updated - {company.name}'
                            message = render_to_string('emails/password_updated.html', {
                                'company': company,
                                'user': admin_user,
                                'login_url': f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/",
                            })

                            send_mail(
                                subject,
                                message,
                                settings.DEFAULT_FROM_EMAIL,
                                [admin_user.email],
                                html_message=message
                            )
                            messages.success(request, f'Company updated and new password set for administrator!')
                        except Exception as e:
                            messages.success(request, f'Company updated successfully!')
                    else:
                        messages.success(request, f'Company updated successfully! (No administrator account found to update password)')
                else:
                    messages.success(request, f'Company "{company.name}" updated successfully!')

                # Redirect based on user role
                if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
                    # For employers, stay on the edit page or go to dashboard
                    return redirect('employer_dashboard')
                else:
                    # For superadmins, go to company list
                    return redirect('company_list')
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                messages.error(request, f'Error updating company: {str(e)}')
                # Stay on the same page to show error
                context = {
                    'company': company,
                    'action': 'Edit'
                }
                template_name = 'ems/company_form_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/company_form.html'
                return render(request, template_name, context)
        else:
            messages.error(request, 'Company name and address are required.')

    context = {
        'company': company,
        'action': 'Edit'
    }
    # Choose template based on role to keep correct sidebar/base
    template_name = 'ems/company_form_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/company_form.html'
    return render(request, template_name, context)


@login_required
def company_delete(request, company_id):
    """Delete company"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('/')

    company = get_object_or_404(Company, id=company_id)

    if request.method == 'POST':
        try:
            company_name = company.name
            company.delete()
            messages.success(request, f'Company "{company_name}" deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting company: {str(e)}')

@login_required
def approve_existing_company(request, company_id):
    """Approve an existing company or resend credentials"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    company = get_object_or_404(Company, id=company_id)

    if request.method == 'POST':
        # Get password from form or generate new one
        admin_password = request.POST.get('admin_password')
        if admin_password:
            # Use admin-provided password
            final_password = admin_password
        else:
            # Generate new password
            import random, string
            final_password = ''.join(random.choices(string.ascii_letters + string.digits + '!@#$%', k=12))

        # Check if company is already approved
        if company.is_approved:
            # Company already approved - just resend credentials
            employer_user = User.objects.filter(
                company=company,
                role='ADMINISTRATOR'
            ).first()

            if not employer_user:
                messages.error(request, f'No employer account found for {company.name}')
                return redirect('company_list')
        else:
            # Approve the company
            company.is_approved = True
            company.is_active = True  # Explicitly set to True
            company.approved_by = request.user
            company.approved_at = timezone.now()
            company.save()

            # Debug: Check company status after approval

            # Create employer user account
            # First check if user already exists with this email
            employer_user = User.objects.filter(email=company.email).first()

            if employer_user:
                # User already exists, update their information
                employer_user.first_name = company.contact_first_name if hasattr(company, 'contact_first_name') else 'Company'
                employer_user.last_name = company.contact_last_name if hasattr(company, 'contact_last_name') else 'Admin'
                employer_user.role = 'ADMINISTRATOR'
                employer_user.company = company
                employer_user.must_change_password = True
                employer_user.is_active = True
                employer_user.save()

                # Update or create employer profile
                employer_profile, created = EmployerProfile.objects.get_or_create(
                    user=employer_user,
                    defaults={
                        'company_name': company.name,
                        'company_address': company.address,
                        'company_phone': company.phone,
                        'company_email': company.email,
                        'tax_id': company.tax_id,
                        'company': company
                    }
                )

                if not created:
                    # Update existing profile
                    employer_profile.company_name = company.name
                    employer_profile.company_address = company.address
                    employer_profile.company_phone = company.phone
                    employer_profile.company_email = company.email
                    employer_profile.tax_id = company.tax_id
                    employer_profile.company = company
                    employer_profile.save()

                messages.info(request, f'Updated existing user account for {company.email}')
            else:
                # Create new employer user account
                employer_user = User.objects.create_user(
                    email=company.email,
                    password=final_password,
                    first_name=company.contact_first_name if hasattr(company, 'contact_first_name') else 'Company',
                    last_name=company.contact_last_name if hasattr(company, 'contact_last_name') else 'Admin',
                    role='ADMINISTRATOR',
                    company=company,
                    must_change_password=True,
                    is_active=True
                )

                # Create employer profile
                EmployerProfile.objects.create(
                    user=employer_user,
                    company_name=company.name,
                    company_address=company.address,
                    company_phone=company.phone,
                    company_email=company.email,
                    tax_id=company.tax_id,
                    company=company
                )

        # Send approval email
        try:
            subject = f'Company Registration Approved - {company.name}'
            message = render_to_string('emails/company_approved.html', {
                'company': company,
                'employer': employer_user,
                'password': final_password,
                'login_url': f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/",
                'license_info': {
                    'plan': company.subscription_plan,
                    'license_key': company.license_key,
                    'max_employees': company.max_employees,
                    'expiry': company.license_expiry,
                }
            })

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [company.email],
                html_message=message
            )
        except Exception:            pass
        if company.is_approved:
            messages.success(
                request,
                f'Login credentials resent for {company.name}! Email sent to {company.email}'
            )
        else:
            messages.success(
                request,
                f'Company "{company.name}" approved! Login credentials sent to {company.email}'
            )
        return redirect('company_list')

    return render(request, 'ems/approve_company_registration.html', {
        'company': company
    })

@login_required
def resend_credentials(request, company_id):
    """Resend login credentials for an approved company"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    company = get_object_or_404(Company, id=company_id, is_approved=True)

    if request.method == 'POST':
        try:
            # Find the employer user account for this company
            employer_user = User.objects.filter(
                company=company,
                role='ADMINISTRATOR'
            ).first()

            if not employer_user:
                messages.error(request, f'No employer account found for {company.name}')
                return redirect('company_list')

            # Send credentials email
            try:
                subject = f'Company Registration Approved - {company.name}'
                message = render_to_string('emails/company_approved.html', {
                    'company': company,
                    'employer': employer_user,
                    'login_url': f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/",
                    'license_info': {
                        'plan': company.subscription_plan,
                        'license_key': company.license_key,
                        'max_employees': company.max_employees,
                        'expiry': company.license_expiry,
                    }
                })

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [company.email],  # Send to company email
                    html_message=message
                )
            except Exception:                pass
            messages.success(
                request,
                f'Login credentials resent for {company.name}! Email sent to {company.email}'
            )
            return redirect('company_list')

        except Exception as e:
            messages.error(request, f'Error resending credentials: {str(e)}')
            return redirect('company_list')

    return redirect('company_list')


@login_required
def company_users(request, company_id):
    """Manage users for a specific company"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    company = get_object_or_404(Company, id=company_id)
    users = User.objects.filter(company=company).order_by('role', 'email')

    # Group users by role
    hr_users = users.filter(role='HR')
    payroll_users = users.filter(role='PAYROLL')
    payslip_users = users.filter(role='PAYSLIP')
    employees = users.filter(role='EMPLOYEE')

    context = {
        'company': company,
        'hr_users': hr_users,
        'payroll_users': payroll_users,
        'payslip_users': payslip_users,
        'employees': employees,
    }
    return render(request, 'ems/company_users.html', context)


@login_required
def create_company_user(request, company_id, role):
    """Create user for a specific company with specific role"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('/')

    company = get_object_or_404(Company, id=company_id)

    # Validate role
    valid_roles = ['EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN', 'HR', 'PAYROLL', 'PAYSLIP', 'EMPLOYEE']
    if role not in valid_roles:
        messages.error(request, 'Invalid user role.')
        return redirect('company_users', company_id=company_id)

    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        password = request.POST.get('password')

        if email and first_name and password:
            try:
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    role=role,
                    company=company
                )

                # Create appropriate profile
                if role == 'EMPLOYEE':
                    EmployeeProfile.objects.create(user=user)
                elif role in ['EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN', 'HR', 'PAYROLL', 'PAYSLIP']:
                    EmployerProfile.objects.create(user=user)

                messages.success(request, f'User "{user.email}" created successfully!')
                return redirect('company_users', company_id=company_id)
            except Exception as e:
                messages.error(request, f'Error creating user: {str(e)}')
        else:
            messages.error(request, 'Email, first name, and password are required.')

    context = {
        'company': company,
        'role': role,
        'role_display': dict(User.Role.choices)[role]
    }
    return render(request, 'ems/company_user_form.html', context)


@login_required
def company_profile(request, company_id):
    """Enhanced company profile with comprehensive statistics and analytics"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    company = get_object_or_404(Company, id=company_id)
    
    from django.db.models import Q, Count, Avg
    from datetime import date, timedelta
    import csv
    from django.http import HttpResponse
    
    # License status helper
    today = date.today()
    window_end = today + timedelta(days=30)
    license_status = 'active'
    license_status_label = 'Active'
    license_days_remaining = None

    if company.is_trial:
        if company.trial_ends_at:
            trial_end_date = company.trial_ends_at.date()
            if trial_end_date < today:
                license_status = 'expired'
                license_status_label = 'Trial expired'
                license_days_remaining = 0
            else:
                license_days_remaining = (trial_end_date - today).days
                if trial_end_date <= window_end:
                    license_status = 'expiring_30'
                    license_status_label = 'Trial ending soon'
                else:
                    license_status = 'trial'
                    license_status_label = 'Active trial'
        else:
            license_status = 'trial'
            license_status_label = 'Active trial'
    else:
        if company.license_expiry:
            if company.license_expiry < today:
                license_status = 'expired'
                license_status_label = 'License expired'
                license_days_remaining = 0
            else:
                license_days_remaining = (company.license_expiry - today).days
                if company.license_expiry <= window_end:
                    license_status = 'expiring_30'
                    license_status_label = 'License expiring soon'
                else:
                    license_status = 'active'
                    license_status_label = 'Active license'
        else:
            license_status = 'active'
            license_status_label = 'Active (no expiry)'
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    export_type = request.GET.get('export', '')
    
    # Get company users with filtering
    company_users = User.objects.filter(company=company)
    
    if search_query:
        company_users = company_users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if role_filter:
        company_users = company_users.filter(role=role_filter)
    
    if status_filter == 'active':
        company_users = company_users.filter(is_active=True)
    elif status_filter == 'inactive':
        company_users = company_users.filter(is_active=False)
    
    company_users = company_users.order_by('role', 'email')

    # Get branches (sub-companies)
    branches = Company.objects.filter(parent_company=company)
    
    # Comprehensive Statistics
    total_users = User.objects.filter(company=company).count()
    active_users = User.objects.filter(company=company, is_active=True).count()
    inactive_users = User.objects.filter(company=company, is_active=False).count()
    employee_users = User.objects.filter(company=company, role='EMPLOYEE').count()
    admin_users = User.objects.filter(company=company, role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']).count()
    
    branches_count = branches.count()
    
    # Department & Position statistics
    from accounts.models import CompanyDepartment, CompanyPosition
    departments_count = CompanyDepartment.objects.filter(company=company).count()
    positions_count = CompanyPosition.objects.filter(company=company).count()
    
    # Attendance statistics (today)
    try:
        from attendance.models import Attendance
        present_today = Attendance.objects.filter(
            employee__company=company,
            date=today,
            status__in=['PRESENT', 'LATE', 'HALF_DAY']
        ).count()
        absent_today = Attendance.objects.filter(
            employee__company=company,
            date=today,
            status='ABSENT'
        ).count()
    except:
        present_today = 0
        absent_today = 0
    
    # Leave statistics
    try:
        from attendance.models import LeaveRequest
        pending_leaves = LeaveRequest.objects.filter(
            employee__company=company,
            status='PENDING'
        ).count()
        approved_leaves_this_month = LeaveRequest.objects.filter(
            employee__company=company,
            status='APPROVED',
            start_date__month=today.month,
            start_date__year=today.year
        ).count()
    except:
        pending_leaves = 0
        approved_leaves_this_month = 0
    
    # Document statistics
    try:
        from documents.models import EmployeeDocument
        total_documents = EmployeeDocument.objects.filter(employee__company=company).count()
        pending_documents = EmployeeDocument.objects.filter(
            employee__company=company,
            status='PENDING'
        ).count()
    except:
        total_documents = 0
        pending_documents = 0
    
    # Performance statistics
    try:
        from performance.models import PerformanceReview
        total_reviews = PerformanceReview.objects.filter(employee__company=company).count()
        avg_rating = PerformanceReview.objects.filter(
            employee__company=company
        ).aggregate(avg=Avg('overall_rating'))['avg'] or 0
    except:
        total_reviews = 0
        avg_rating = 0
    
    # Training statistics
    try:
        from training.models import TrainingEnrollment
        total_trainings = TrainingEnrollment.objects.filter(employee__company=company).count()
        completed_trainings = TrainingEnrollment.objects.filter(
            employee__company=company,
            status='COMPLETED'
        ).count()
    except:
        total_trainings = 0
        completed_trainings = 0
    
    # Recent activities - Real data from system
    recent_activities = []
    
    # Recent user logins
    recent_logins = User.objects.filter(
        company=company,
        last_login__isnull=False
    ).order_by('-last_login')[:3]
    
    for user in recent_logins:
        recent_activities.append({
            'title': 'User Login',
            'description': f'{user.get_full_name()} logged in',
            'timestamp': user.last_login,
            'type': 'login',
            'icon': '👤'
        })
    
    # Recent user registrations
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_users = User.objects.filter(
        company=company,
        date_joined__gte=thirty_days_ago
    ).order_by('-date_joined')[:3]
    
    for user in recent_users:
        recent_activities.append({
            'title': 'New User',
            'description': f'{user.get_full_name()} joined as {user.get_role_display()}',
            'timestamp': user.date_joined,
            'type': 'user',
            'icon': '➕'
        })
    
    # Recent documents
    try:
        recent_docs = EmployeeDocument.objects.filter(
            employee__company=company
        ).order_by('-created_at')[:3]
        
        for doc in recent_docs:
            recent_activities.append({
                'title': 'Document Uploaded',
                'description': f'{doc.document_name} by {doc.employee.get_full_name()}',
                'timestamp': doc.created_at,
                'type': 'document',
                'icon': '📄'
            })
    except:
        pass
    
    # Recent leave requests
    try:
        recent_leaves = LeaveRequest.objects.filter(
            employee__company=company
        ).order_by('-created_at')[:3]
        
        for leave in recent_leaves:
            recent_activities.append({
                'title': 'Leave Request',
                'description': f'{leave.employee.get_full_name()} - {leave.get_leave_type_display()}',
                'timestamp': leave.created_at,
                'type': 'leave',
                'icon': '🏖️'
            })
    except:
        pass
    
    # Sort all activities by timestamp and limit
    recent_activities = sorted(recent_activities, key=lambda x: x['timestamp'], reverse=True)[:10]
    
    # CSV Export
    if export_type == 'users':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{company.name}_users.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Role', 'Status', 'Last Login', 'Date Joined'])
        
        for user in company_users:
            writer.writerow([
                user.get_full_name(),
                user.email,
                user.get_role_display(),
                'Active' if user.is_active else 'Inactive',
                user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never',
                user.date_joined.strftime('%Y-%m-%d')
            ])
        return response
    
    elif export_type == 'summary':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{company.name}_summary.csv"'
        writer = csv.writer(response)
        writer.writerow(['Company Summary Report', company.name])
        writer.writerow([])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Users', total_users])
        writer.writerow(['Active Users', active_users])
        writer.writerow(['Inactive Users', inactive_users])
        writer.writerow(['Employees', employee_users])
        writer.writerow(['Administrators', admin_users])
        writer.writerow(['Branches', branches_count])
        writer.writerow(['Departments', departments_count])
        writer.writerow(['Positions', positions_count])
        writer.writerow(['Present Today', present_today])
        writer.writerow(['Absent Today', absent_today])
        writer.writerow(['Pending Leave Requests', pending_leaves])
        writer.writerow(['Total Documents', total_documents])
        writer.writerow(['Pending Documents', pending_documents])
        writer.writerow(['Performance Reviews', total_reviews])
        writer.writerow(['Average Rating', f'{avg_rating:.2f}'])
        writer.writerow(['Training Enrollments', total_trainings])
        writer.writerow(['Completed Trainings', completed_trainings])
        return response

    context = {
        'company': company,
        'company_users': company_users,
        'branches': branches,
        
        # User Statistics
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'employee_users': employee_users,
        'admin_users': admin_users,
        
        # Organization Statistics
        'branches_count': branches_count,
        'departments_count': departments_count,
        'positions_count': positions_count,
        
        # Module Statistics
        'present_today': present_today,
        'absent_today': absent_today,
        'pending_leaves': pending_leaves,
        'approved_leaves_this_month': approved_leaves_this_month,
        'total_documents': total_documents,
        'pending_documents': pending_documents,
        'total_reviews': total_reviews,
        'avg_rating': round(avg_rating, 1),
        'total_trainings': total_trainings,
        'completed_trainings': completed_trainings,
        
        # Activity
        'recent_activities': recent_activities,
        'activity_logs': recent_activities,  # For template compatibility
        
        # Filters
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'role_choices': User.Role.choices,
        # License helper
        'license_status': license_status,
        'license_status_label': license_status_label,
        'license_days_remaining': license_days_remaining,
    }
    return render(request, 'ems/company_profile.html', context)


# Dashboard redirect based on user role
@login_required
def dashboard_redirect(request):
    """Redirect users to appropriate dashboard based on their role"""
    if request.user.is_admin:
        # Get dashboard statistics for Superuser Admin
        companies = Company.objects.filter(is_approved=True, is_active=True)
        users = User.objects.all()

        context = {
            'user': request.user,
            'total_companies': companies.count(),
            'total_users': users.count(),
            'employer_superusers': users.filter(role='EMPLOYER_SUPERUSER').count(),
            'employer_admins': users.filter(role='EMPLOYER_ADMIN').count(),
            'employees': users.filter(role='EMPLOYEE').count(),
        }
        return render(request, 'ems/superadmin_dashboard.html', context)
    elif request.user.is_employer_superuser:
        return render(request, 'ems/employer_superuser_dashboard.html')
    elif request.user.is_employer_admin:
        return render(request, 'ems/employer_admin_dashboard.html')
    elif request.user.is_employee:
        return render(request, 'ems/employee_dashboard.html')
    else:
        messages.error(request, 'Invalid user role. Please contact administrator.')
        return redirect('/')

@login_required
def employer_superuser_dashboard(request):
    """Dashboard for Employer Superuser (Company Owner)"""
    if not request.user.is_employer_superuser:
        messages.error(request, 'Access denied. Employer Superuser privileges required.')
        return redirect('/')

    # Get the company this user owns
    try:
        company = request.user.employer_profile.company
    except:
        messages.error(request, 'Company profile not found. Please contact support.')
        return redirect('/')

    from attendance.models import Attendance
    from datetime import date, timedelta

    today = date.today()

    # Get all sub-companies/branches
    branches = Company.objects.filter(parent_company=company)

    # Get all users in this company and its branches
    company_users = User.objects.filter(
        company__in=[company] + list(branches)
    )

    # Statistics
    total_employees = company_users.filter(role='EMPLOYEE').count()
    total_branches = branches.count()
    total_admins = company_users.filter(
        role__in=['EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN']
    ).count()

    # Today's attendance
    active_today = Attendance.objects.filter(
        date=today,
        user__company__in=[company] + list(branches)
    ).count()

    # Recent activities (placeholder - would be from activity log)
    recent_activities = [
        {
            'title': 'New employee joined',
            'description': 'John Doe joined Marketing department',
            'timestamp': timezone.now() - timedelta(hours=2),
            'type': 'employee'
        },
        {
            'title': 'Branch created',
            'description': 'New branch "Downtown Office" was created',
            'timestamp': timezone.now() - timedelta(days=1),
            'type': 'branch'
        },
        {
            'title': 'Payroll processed',
            'description': 'Monthly payroll for 25 employees processed',
            'timestamp': timezone.now() - timedelta(days=2),
            'type': 'payroll'
        }
    ][:5]  # Show only last 5

    # Admin users (other employer superusers and admins)
    admin_users = company_users.filter(
        role__in=['EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN']
    ).exclude(id=request.user.id)[:5]  # Exclude current user, limit to 5

    context = {
        'user': request.user,
        'company': company,
        'total_employees': total_employees,
        'total_branches': total_branches,
        'total_admins': total_admins,
        'active_today': active_today,
        'recent_activities': recent_activities,
        'branches': branches[:5],  # Show only first 5 branches
        'admin_users': admin_users,
    }
    
    return render(request, 'ems/employer_superuser_dashboard.html', context)

@login_required
def employee_list(request):
    """
    View to list all employees with their basic information.
    Accessible to admin and employer users.
    """
    # Check if user has permission to view employees
    if not request.user.is_authenticated or not (request.user.is_staff or hasattr(request.user, 'employerprofile')):
        messages.error(request, "You don't have permission to view this page.")
        return redirect('dashboard_redirect')
    
    # Get the company for employer users
    company = None
    if hasattr(request.user, 'employerprofile'):
        company = request.user.employerprofile.company
        employees = User.objects.filter(
            employee_profile__company=company,
            is_active=True
        ).select_related('employee_profile')
    else:
        # Admin can see all employees
        employees = User.objects.filter(
            employee_profile__isnull=False,
            is_active=True
        ).select_related('employee_profile')
    
    context = {
        'employees': employees,
        'company': company,
        'page_title': 'Employee Directory',
    }
    
    return render(request, 'ems/employee_list.html', context)


@login_required
def create_employee(request):
    """
    View to create a new employee.
    Accessible to admin and employer users.
    """
    # Check if user has permission to create employees
    if not request.user.is_authenticated or not (request.user.is_staff or hasattr(request.user, 'employerprofile')):
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard_redirect')
    
    # Get the company for employer users
    company = None
    if hasattr(request.user, 'employerprofile'):
        company = request.user.employerprofile.company
    
    if request.method == 'POST':
        form = EmployeeRegistrationForm(request.POST, company=company)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_employee = True
            user.save()
            
            # Create employee profile
            EmployeeProfile.objects.create(
                user=user,
                company=company,
                position=form.cleaned_data.get('position', ''),
                department=form.cleaned_data.get('department', ''),
                phone_number=form.cleaned_data.get('phone_number', '')
            )
            
            messages.success(request, f'Employee {user.get_full_name()} has been created successfully.')
            return redirect('employee_list')
    else:
        form = EmployeeRegistrationForm(company=company)
    
    context = {
        'form': form,
        'page_title': 'Add New Employee',
        'company': company,
    }
    
    return render(request, 'ems/employee_form.html', context)


def employee_dashboard(request):
    # Dashboard for Employee (Self-service portal)"
    if not request.user.is_employee:
        messages.error(request, 'Access denied. Employee access required.')
        return redirect('/')
    from leave.models import LeaveRequest
    from datetime import date, timedelta

    today = date.today()
    current_month = today.replace(day=1)

    # Get employee profile
    try:
        profile = request.user.employee_profile
    except:
        messages.error(request, 'Employee profile not found. Please contact HR.')
        return redirect('/')

    # Statistics
    present_days = Attendance.objects.filter(
        user=request.user,
        status='PRESENT',
        date__gte=current_month
    ).count()

    pending_leaves = LeaveRequest.objects.filter(
        user=request.user,
        status='PENDING'
    ).count()

    working_days = 22  # Standard working days in a month

    # Recent activities (placeholder)
    recent_activities = [
        {
            'title': 'Profile updated',
            'description': 'Your profile information was updated',
            'timestamp': timezone.now() - timedelta(hours=2),
            'status': 'completed'
        },
        {
            'title': 'Payslip generated',
            'description': f'Monthly payslip for {today.strftime("%B %Y")} is available',
            'timestamp': timezone.now() - timedelta(days=1),
            'status': 'completed'
        }
    ][:3]

    # Today's schedule (placeholder)
    today_schedule = [
        {
            'title': 'Regular Work Day',
            'time': '9:00 AM - 5:00 PM',
            'location': 'Office',
            'status': 'active'
        }
    ]

    # Upcoming approved leave
    upcoming_leave = LeaveRequest.objects.filter(
        user=request.user,
        status='APPROVED',
        start_date__gte=today
    ).order_by('start_date')[:3]

    # Total payslips (placeholder - would be from payroll app)
    total_payslips = 12  # Example number

    context = {
        'user': request.user,
        'profile': profile,
        'present_days': present_days,
        'pending_leaves': pending_leaves,
        'working_days': working_days,
        'total_payslips': total_payslips,
        'recent_activities': recent_activities,
        'today_schedule': today_schedule,
        'upcoming_leave': upcoming_leave,
        'today_date': today.strftime('%B %d, %Y'),
    }

    return render(request, 'ems/employee_dashboard.html', context)

@login_required
def employer_admin_dashboard(request):
    """Dashboard for Employer Admin (Branch/Company Admin)"""
    if not request.user.is_employer_admin:
        messages.error(request, 'Access denied. Employer Admin privileges required.')
        return redirect('/')

    # Get the company this admin manages
    try:
        company = request.user.company
    except:
        messages.error(request, 'Company not assigned. Please contact your Employer Superuser.')
        return redirect('/')

    from attendance.models import Attendance
    from leave.models import LeaveRequest
    from datetime import date, timedelta

    today = date.today()

    # Get employees in this company
    employees = User.objects.filter(company=company, role='EMPLOYEE')

    # Statistics
    total_employees = employees.count()

    # Today's attendance
    present_today = Attendance.objects.filter(
        date=today,
        user__company=company,
        status='PRESENT'
    ).count()

    late_today = Attendance.objects.filter(
        date=today,
        user__company=company,
        status='LATE'
    ).count()

    absent_today = total_employees - present_today - late_today

    # Pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        user__company=company,
        status='PENDING'
    ).count()

    # Today's attendance records (limit to 10 for display)
    today_attendance = Attendance.objects.filter(
        date=today,
        user__company=company
    ).select_related('user').order_by('-created_at')[:10]

    # Pending leave requests (limit to 5 for display)
    pending_leave_requests = LeaveRequest.objects.filter(
        user__company=company,
        status='PENDING'
    ).select_related('user').order_by('start_date')[:5]

    # Recent activities (placeholder)
    recent_activities = [
        {
            'title': 'Attendance marked',
            'description': f'{today_attendance.count()} employees marked attendance today',
            'timestamp': timezone.now() - timedelta(hours=1),
            'type': 'attendance'
        },
        {
            'title': 'Leave request submitted',
            'description': 'New leave request from Marketing department',
            'timestamp': timezone.now() - timedelta(hours=3),
            'type': 'leave'
        },
        {
            'title': 'Payroll processed',
            'description': f'Payroll processed for {total_employees} employees',
            'timestamp': timezone.now() - timedelta(days=1),
            'type': 'payroll'
        }
    ][:5]

    context = {
        'user': request.user,
        'company': company,
        'total_employees': total_employees,
        'present_today': present_today,
        'late_today': late_today,
        'absent_today': absent_today,
        'pending_leaves': pending_leaves,
        'today_attendance': today_attendance,
        'pending_leave_requests': pending_leave_requests,
        'recent_activities': recent_activities,
    }

    return render(request, 'ems/employer_admin_dashboard.html', context)


# API Views for Authentication
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status
from .serializers import UserLoginSerializer


class CustomLoginView(APIView):
    """Custom login view that returns user role and company information"""

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        # Delete any existing tokens for this user
        Token.objects.filter(user=user).delete()

        # Create new token
        token, created = Token.objects.get_or_create(user=user)

        # Get additional user information
        user_data = {
            'userId': user.id,
            'email': user.email,
            'firstName': user.first_name,
            'lastName': user.last_name,
            'role': user.role,
            'isActive': user.is_active,
            'token': token.key,
        }

        # Add company information if user has a company
        if hasattr(user, 'company') and user.company:
            user_data['companyId'] = user.company.id
            user_data['companyName'] = user.company.name
            user_data['companyEmail'] = user.company.email

        # Add profile information based on role
        if user.role == 'EMPLOYEE' and hasattr(user, 'employee_profile'):
            profile = user.employee_profile
            user_data['employeeId'] = profile.employee_id
            user_data['jobTitle'] = profile.job_title
            user_data['department'] = profile.department

        elif user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] and hasattr(user, 'employer_profile'):
            profile = user.employer_profile
            user_data['companyName'] = profile.company_name
            user_data['companyAddress'] = profile.company_address
            user_data['companyPhone'] = profile.company_phone

        # Debug logging

        return Response(user_data, status=status.HTTP_200_OK)
