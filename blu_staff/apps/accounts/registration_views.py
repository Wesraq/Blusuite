from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import reverse
import json
import random
import string

from .models import CompanyRegistrationRequest, Company, User, EmployerProfile, SystemSettings
from .forms import CompanyRegistrationForm
from tenant_management.services import provision_tenant_for_company, assign_user_role


# Canonical plan pricing (USD/month base prices)
PLAN_PRICING = {
    'BASIC':        {'name': 'Starter',      'monthly': 29.99,  'max_employees': 25},
    'PROFESSIONAL': {'name': 'Professional', 'monthly': 79.99,  'max_employees': 100},
    'ENTERPRISE':   {'name': 'Enterprise',   'monthly': 199.99, 'max_employees': 99999},
}


def _provision_company(registration_request, admin_password=None, approved_by=None):
    """
    Provision a company from an approved registration request.
    Creates the company, employer user, profile, and tenant.
    Returns (company, employer_user, generated_password).
    """
    billing_pref = getattr(registration_request, 'billing_preference', None)
    today = timezone.now().date()

    company = Company.objects.create(
        name=registration_request.company_name,
        address=registration_request.company_address,
        phone=registration_request.company_phone,
        email=registration_request.company_email,
        website=registration_request.company_website,
        tax_id=registration_request.tax_id,
        city=getattr(registration_request, 'city', ''),
        country=getattr(registration_request, 'country', 'Zambia'),
        subscription_plan=registration_request.subscription_plan,
        max_employees=registration_request.number_of_employees,
        registration_request=registration_request,
        is_approved=True,
        approved_by=approved_by,
        approved_at=timezone.now(),
    )

    if billing_pref == CompanyRegistrationRequest.BillingPreference.TRIAL:
        company.is_trial = True
        company.trial_ends_at = timezone.now() + timedelta(days=30)
    elif billing_pref == CompanyRegistrationRequest.BillingPreference.MONTHLY:
        company.is_trial = False
        company.license_expiry = today + timedelta(days=30)
    elif billing_pref == CompanyRegistrationRequest.BillingPreference.YEARLY:
        company.is_trial = False
        company.license_expiry = today + timedelta(days=365)

    if billing_pref:
        company.save(update_fields=['is_trial', 'trial_ends_at', 'license_expiry'])

    final_password = admin_password or ''.join(
        random.choices(string.ascii_letters + string.digits + '!@#$%', k=12)
    )

    employer_user = User.objects.filter(email=registration_request.contact_email).first()
    if employer_user:
        employer_user.first_name = registration_request.contact_first_name
        employer_user.last_name = registration_request.contact_last_name
        employer_user.role = 'ADMINISTRATOR'
        employer_user.company = company
        employer_user.must_change_password = True
        employer_user.is_active = True
        employer_user.save()
        EmployerProfile.objects.update_or_create(
            user=employer_user,
            defaults={
                'company_name': registration_request.company_name,
                'company_address': registration_request.company_address,
                'company_phone': registration_request.company_phone,
                'company_email': registration_request.company_email,
                'tax_id': registration_request.tax_id,
                'company': company,
            }
        )
    else:
        employer_user = User.objects.create_user(
            email=registration_request.contact_email,
            password=final_password,
            first_name=registration_request.contact_first_name,
            last_name=registration_request.contact_last_name,
            role='ADMINISTRATOR',
            company=company,
            must_change_password=True,
            is_active=True,
        )
        EmployerProfile.objects.create(
            user=employer_user,
            company_name=registration_request.company_name,
            company_address=registration_request.company_address,
            company_phone=registration_request.company_phone,
            company_email=registration_request.company_email,
            tax_id=registration_request.tax_id,
            company=company,
        )

    tenant_result = provision_tenant_for_company(company=company, owner=employer_user)
    assign_user_role(tenant=tenant_result.tenant, user=employer_user, role='OWNER')

    registration_request.status = 'APPROVED'
    registration_request.reviewed_at = timezone.now()
    registration_request.save(update_fields=['status', 'reviewed_at'])

    try:
        subject = f'Welcome to BLU Suite - Your Company Account is Ready'
        message = render_to_string('emails/company_approved.html', {
            'company': company,
            'employer': employer_user,
            'password': final_password,
            'login_url': f"{getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')}/login/",
            'license_info': {
                'plan': company.subscription_plan,
                'license_key': company.license_key,
                'max_employees': company.max_employees,
                'expiry': company.license_expiry,
            }
        })
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
                  [registration_request.contact_email], html_message=message)
    except Exception:
        pass

    return company, employer_user, final_password


@csrf_exempt
def company_registration_request(request):
    """Handle company registration requests from potential employers"""
    try:
        system_settings = SystemSettings.get_solo()
    except Exception:
        system_settings = None

    if system_settings and not system_settings.allow_public_company_registration:
        message_text = 'Public company registration is currently disabled. Please contact support to create an account.'
        if getattr(system_settings, 'maintenance_mode', False) and getattr(system_settings, 'maintenance_message', ''):
            message_text = system_settings.maintenance_message
        messages.error(request, message_text)
        return render(request, 'ems/unauthorized.html', status=403)

    if request.method == 'POST':
        form = CompanyRegistrationForm(request.POST)
        if form.is_valid():
            registration_request = form.save()
            billing_pref = registration_request.billing_preference

            # Send notification to admin
            try:
                admin_email = getattr(settings, 'ADMIN_EMAIL', None) or 'admin@eiscomtech.com'
                subject = f'New Company Registration Request - {registration_request.company_name}'
                message = render_to_string('emails/company_registration_request.html', {
                    'request': registration_request,
                })
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [admin_email], html_message=message)
            except Exception:
                pass

            # For paid plans: redirect to Stripe checkout
            if billing_pref in ('MONTHLY', 'YEARLY'):
                try:
                    import stripe
                    stripe.api_key = settings.STRIPE_SECRET_KEY

                    plan_key = registration_request.subscription_plan
                    plan_info = PLAN_PRICING.get(plan_key, PLAN_PRICING['BASIC'])

                    if billing_pref == 'YEARLY':
                        unit_price = plan_info['monthly'] * 12 * 0.80  # 20% yearly discount
                        label = f"{plan_info['name']} Plan - Yearly (20% off)"
                    else:
                        unit_price = plan_info['monthly']
                        label = f"{plan_info['name']} Plan - Monthly"

                    success_url = request.build_absolute_uri(
                        reverse('payments:registration_success')
                    ) + '?session_id={CHECKOUT_SESSION_ID}'
                    cancel_url = request.build_absolute_uri(reverse('company_registration'))

                    session = stripe.checkout.Session.create(
                        payment_method_types=['card'],
                        line_items=[{
                            'price_data': {
                                'currency': 'usd',
                                'product_data': {
                                    'name': label,
                                    'description': f'BLU Suite EMS for {registration_request.company_name}',
                                },
                                'unit_amount': int(unit_price * 100),
                            },
                            'quantity': 1,
                        }],
                        mode='payment',
                        success_url=success_url,
                        cancel_url=cancel_url,
                        customer_email=registration_request.contact_email,
                        metadata={
                            'request_number': registration_request.request_number,
                            'plan_type': plan_key,
                            'billing_preference': billing_pref,
                            'company_name': registration_request.company_name[:100],
                        },
                    )
                    return redirect(session.url)

                except Exception as e:
                    messages.warning(
                        request,
                        'Payment gateway error. Your registration was saved - our team will contact you to complete payment.'
                    )
                    return redirect('registration_success', request_id=registration_request.request_number)

            # TRIAL: existing approval-pending flow
            messages.success(
                request,
                f'Thank you! Your trial registration (#{registration_request.request_number}) has been submitted. '
                'You will receive an email once your account is activated.'
            )
            return redirect('registration_success', request_id=registration_request.request_number)
        else:
            for field, errors in form.errors.items():
                pass
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CompanyRegistrationForm()

    return render(request, 'ems/company_registration.html', {
        'form': form,
        'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
        'plan_pricing': PLAN_PRICING,
    })


def registration_success(request, request_id):
    """Show success page after registration request"""
    registration_request = get_object_or_404(CompanyRegistrationRequest, request_number=request_id)
    return render(request, 'ems/registration_success.html', {'request': registration_request})


@login_required
def company_registration_list(request):
    """Legacy route: redirect SuperAdmins to the unified Company Management view"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('/')

    # New System Owner experience lives at /companies/
    return redirect('company_list')


@login_required
def approve_company_registration(request, request_id):
    """Approve a company registration request"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('/')

    registration_request = get_object_or_404(CompanyRegistrationRequest, id=request_id)

    if request.method == 'POST':
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

            tenant_result = provision_tenant_for_company(
                company=existing_company,
                owner=employer_user
            )
            if employer_user:
                assign_user_role(
                    tenant=tenant_result.tenant,
                    user=employer_user,
                    role='OWNER'
                )

            if employer_user:
                # Send approval email to employer
                try:
                    subject = f'Company Registration Approved - {existing_company.name}'
                    message = render_to_string('emails/company_approved.html', {
                        'company': existing_company,
                        'employer': employer_user,
                        'password': 'N/A (already set up)',  # Include the password in email
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

            return redirect('company_registration_list')

        # Create company
        company = Company.objects.create(
            name=registration_request.company_name,
            address=registration_request.company_address,
            phone=registration_request.company_phone,
            email=registration_request.company_email,
            website=registration_request.company_website,
            tax_id=registration_request.tax_id,
            city=getattr(registration_request, 'city', ''),
            country=getattr(registration_request, 'country', 'Zambia'),
            subscription_plan=registration_request.subscription_plan,
            max_employees=registration_request.number_of_employees,
            registration_request=registration_request,
            is_approved=True,
            approved_by=request.user,
            approved_at=timezone.now()
        )

        # Apply billing preference (trial / monthly / yearly) to license dates
        billing_pref = getattr(registration_request, 'billing_preference', None)
        today = timezone.now().date()

        if billing_pref == CompanyRegistrationRequest.BillingPreference.TRIAL:
            company.is_trial = True
            company.trial_ends_at = timezone.now() + timedelta(days=30)
        elif billing_pref == CompanyRegistrationRequest.BillingPreference.MONTHLY:
            company.is_trial = False
            company.license_expiry = today + timedelta(days=30)
        elif billing_pref == CompanyRegistrationRequest.BillingPreference.YEARLY:
            company.is_trial = False
            company.license_expiry = today + timedelta(days=365)

        if billing_pref:
            company.save(update_fields=['is_trial', 'trial_ends_at', 'license_expiry'])

        # Get password from form or generate new one
        admin_password = request.POST.get('admin_password')
        if admin_password:
            # Use admin-provided password
            final_password = admin_password
        else:
            # Generate new password
            import random, string
            final_password = ''.join(random.choices(string.ascii_letters + string.digits + '!@#$%', k=12))

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

        tenant_result = provision_tenant_for_company(
            company=company,
            owner=employer_user
        )
        assign_user_role(
            tenant=tenant_result.tenant,
            user=employer_user,
            role='OWNER'
        )

        # Update registration request status
        registration_request.status = 'APPROVED'
        registration_request.reviewed_by = request.user
        registration_request.reviewed_at = timezone.now()
        registration_request.review_notes = request.POST.get('review_notes', '')
        registration_request.save()

        # Send approval email to employer
        try:
            subject = f'Company Registration Approved - {company.name}'
            message = render_to_string('emails/company_approved.html', {
                'company': company,
                'employer': employer_user,
                'password': final_password,  # Include the password in email
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
        except Exception:
            pass

        messages.success(
            request,
            f'Company registration approved! Login credentials sent to {registration_request.contact_email}'
        )
        return redirect('company_registration_list')

    return render(request, 'ems/approve_company_registration.html', {
        'registration_request': registration_request
    })


@login_required
def reject_company_registration(request, request_id):
    """Reject a company registration request"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('/')

    registration_request = get_object_or_404(CompanyRegistrationRequest, id=request_id)

    if request.method == 'POST':
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
        except Exception:
            pass

        messages.success(request, 'Company registration rejected.')
        return redirect('company_registration_list')

    return render(request, 'ems/reject_company_registration.html', {
        'registration_request': registration_request
    })


@require_POST
@csrf_exempt
def api_company_registration(request):
    """API endpoint for company registration (for external forms)"""
    try:
        data = json.loads(request.body)

        registration_request = CompanyRegistrationRequest.objects.create(
            company_name=data['company_name'],
            company_address=data['company_address'],
            company_phone=data.get('company_phone', ''),
            company_email=data['company_email'],
            company_website=data.get('company_website', ''),
            tax_id=data.get('tax_id', ''),
            city=data.get('city', ''),
            country=data.get('country', 'Zambia'),
            contact_first_name=data['contact_first_name'],
            contact_last_name=data['contact_last_name'],
            contact_email=data['contact_email'],
            contact_phone=data['contact_phone'],
            contact_position=data.get('contact_position', ''),
            subscription_plan=data.get('subscription_plan', 'BASIC'),
            number_of_employees=data.get('number_of_employees', 1),
            business_type=data.get('business_type', ''),
            company_size=data.get('company_size', '')
        )

        return JsonResponse({
            'success': True,
            'request_number': registration_request.request_number,
            'message': 'Registration request submitted successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)
