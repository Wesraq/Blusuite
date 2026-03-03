import stripe
import json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from blu_billing.models import SubscriptionPlan, CompanySubscription
from .models import Payment


stripe.api_key = settings.STRIPE_SECRET_KEY


def payment_plans(request):
    """Redirect to landing page since payment plans are already there"""
    return redirect('landing_page')


def create_checkout_session(request):
    """Create Stripe checkout session for registration payment"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        plan_type = data.get('plan_type')  # BASIC, STANDARD, PROFESSIONAL, ENTERPRISE
        employee_count = data.get('employee_count', '25')
        company_name = data.get('company_name', '')
        contact_email = data.get('contact_email', '')
        
        if not plan_type:
            return JsonResponse({'error': 'Plan type required'}, status=400)
        
        # Canonical 3-plan flat-rate pricing (USD)
        plan_pricing = {
            'BASIC': {'price': 29.99, 'name': 'Starter Plan'},
            'PROFESSIONAL': {'price': 79.99, 'name': 'Professional Plan'},
            'ENTERPRISE': {'price': 199.99, 'name': 'Enterprise Plan'},
            # Legacy alias kept for backward compat
            'STANDARD': {'price': 79.99, 'name': 'Professional Plan'},
        }
        
        if plan_type not in plan_pricing:
            return JsonResponse({'error': 'Invalid plan type'}, status=400)
        
        plan_info = plan_pricing[plan_type]
        
        # Check if this is for registration
        is_registration = data.get('for_registration', False)
        
        # Prepare metadata
        metadata = {
            'plan_type': plan_type,
            'employee_count': str(employee_count),
            'registration_type': 'company_registration'
        }
        
        # Add registration data
        metadata.update({
            'company_name': company_name,
            'contact_email': contact_email,
            'employee_count': str(employee_count),
        })
        
        # Set success URL to redirect to registration after payment
        success_url = request.build_absolute_uri(reverse('registration_success')) + '?session_id={CHECKOUT_SESSION_ID}'
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'USD',
                    'product_data': {
                        'name': plan_info['name'],
                        'description': f'{plan_info["name"]} for {company_name or "Your Company"}',
                    },
                    'unit_amount': int(plan_info['price'] * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=request.build_absolute_uri('/'),
            metadata=metadata,
            customer_email=contact_email,
        )
        
        return JsonResponse({'id': session.id})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def payment_success(request):
    """Handle successful payment"""
    session_id = request.GET.get('session_id')
    
    if not session_id:
        messages.error(request, 'Payment session not found')
        return redirect('payment_plans')
    
    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            # Create payment record
            payment = Payment.objects.create(
                company=None,  # Set this based on logged-in user
                stripe_payment_intent_id=session.payment_intent,
                amount=session.amount_total / 100,  # Convert from cents
                currency=session.currency,
                status='succeeded',
                payment_method='card',
                paid_at=timezone.now(),
            )
            
            messages.success(request, f'Payment successful! Amount: ${payment.amount}')
            return redirect('dashboard')
        else:
            messages.error(request, 'Payment was not completed')
            return redirect('payment_plans')
            
    except Exception as e:
        messages.error(request, f'Error verifying payment: {str(e)}')
        return redirect('payment_plans')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhooks"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    if not sig_header:
        return HttpResponse(status=400)
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Update payment record
        if session.payment_status == 'paid':
            try:
                payment = Payment.objects.get(
                    stripe_payment_intent_id=session.payment_intent
                )
                payment.status = 'succeeded'
                payment.paid_at = timezone.now()
                payment.save()
            except Payment.DoesNotExist:
                # Create payment record if it doesn't exist
                plan_id = session.metadata.get('plan_id')
                if plan_id:
                    plan = PaymentPlan.objects.get(id=plan_id)
                    Payment.objects.create(
                        company=None,  # Set based on your user system
                        stripe_payment_intent_id=session.payment_intent,
                        amount=session.amount_total / 100,
                        currency=session.currency,
                        status='succeeded',
                        payment_method='card',
                        paid_at=timezone.now(),
                    )
    
    elif event['type'] == 'payment_intent.payment_failed':
        # Handle failed payment
        payment_intent = event['data']['object']
        try:
            payment = Payment.objects.get(
                stripe_payment_intent_id=payment_intent.id
            )
            payment.status = 'failed'
            payment.save()
        except Payment.DoesNotExist:
            pass
    
    return HttpResponse(status=200)


def registration_success(request):
    """Handle successful Stripe payment → auto-provision company"""
    session_id = request.GET.get('session_id')

    if not session_id:
        messages.error(request, 'Payment session not found.')
        return redirect('/')

    try:
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status != 'paid':
            messages.error(request, 'Payment was not completed. Please try again.')
            return redirect('company_registration')

        request_number = session.metadata.get('request_number')

        if not request_number:
            messages.error(request, 'Registration reference not found. Please contact support.')
            return redirect('/')

        # Import lazily to avoid circular imports
        from blu_staff.apps.accounts.models import CompanyRegistrationRequest, Company
        from blu_staff.apps.accounts.registration_views import _provision_company

        try:
            reg_request = CompanyRegistrationRequest.objects.get(request_number=request_number)
        except CompanyRegistrationRequest.DoesNotExist:
            messages.error(request, f'Registration #{request_number} not found. Please contact support.')
            return redirect('/')

        # Check if company was already provisioned (idempotency)
        existing_company = Company.objects.filter(registration_request=reg_request).first()

        if not existing_company:
            company, employer_user, generated_password = _provision_company(reg_request)
            # Record the payment
            Payment.objects.create(
                company=company,
                stripe_payment_intent_id=session.payment_intent,
                amount=session.amount_total / 100,
                currency=session.currency,
                status='succeeded',
                payment_method='card',
                paid_at=timezone.now(),
            )
        else:
            company = existing_company

        return render(request, 'ems/payment_registration_success.html', {
            'company': company,
            'plan': session.metadata.get('plan_type', ''),
            'billing': session.metadata.get('billing_preference', ''),
            'amount': session.amount_total / 100,
            'currency': session.currency.upper(),
            'login_url': '/login/',
        })

    except Exception as e:
        messages.error(request, f'Error processing payment: {str(e)}')
        return redirect('/')


def company_billing(request):
    """Display company billing information"""
    # This would be for logged-in companies to see their billing
    return render(request, 'payments/billing.html')
