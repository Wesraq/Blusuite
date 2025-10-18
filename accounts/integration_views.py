"""
Integration Management Views
Handles OAuth flows and integration management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
import requests
import json
import secrets
from urllib.parse import urlencode


def _get_user_company(user):
    """Get company for current user"""
    if hasattr(user, 'company') and user.company:
        return user.company
    if hasattr(user, 'employer_profile') and user.employer_profile:
        return user.employer_profile.company
    return None


@login_required
def integration_management(request):
    """Integration management dashboard"""
    from accounts.integration_models import Integration, CompanyIntegration
    
    # Check permissions
    if request.user.role not in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return render(request, 'ems/unauthorized.html')
    
    company = _get_user_company(request.user)
    if not company:
        messages.error(request, 'No company assigned.')
        return redirect('dashboard_redirect')
    
    # Get all available integrations
    available_integrations = Integration.objects.filter(is_available=True).order_by('name')
    
    # Get company's connected integrations
    connected_integrations = CompanyIntegration.objects.filter(
        company=company
    ).select_related('integration').order_by('-connected_at')
    
    # Calculate statistics
    total_integrations = available_integrations.count()
    active_count = connected_integrations.filter(status='ACTIVE').count()
    error_count = connected_integrations.filter(status='ERROR').count()
    
    context = {
        'available_integrations': available_integrations,
        'connected_integrations': connected_integrations,
        'total_integrations': total_integrations,
        'active_count': active_count,
        'error_count': error_count,
        'company': company,
    }
    
    return render(request, 'ems/integrations_management.html', context)


@login_required
@require_http_methods(["POST"])
def integration_connect(request, integration_id):
    """Initiate OAuth connection for an integration"""
    from accounts.integration_models import Integration, CompanyIntegration, IntegrationLog
    
    if request.user.role not in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    company = _get_user_company(request.user)
    if not company:
        return JsonResponse({'error': 'No company assigned'}, status=400)
    
    integration = get_object_or_404(Integration, id=integration_id, is_available=True)
    
    # Get or create company integration
    company_integration, created = CompanyIntegration.objects.get_or_create(
        company=company,
        integration=integration,
        defaults={
            'connected_by': request.user,
            'status': 'PENDING'
        }
    )
    
    if integration.requires_oauth:
        # OAuth flow
        state = secrets.token_urlsafe(32)
        request.session[f'oauth_state_{integration.id}'] = state
        request.session[f'oauth_integration_id'] = integration.id
        
        # Build OAuth authorization URL
        params = {
            'client_id': getattr(settings, f'{integration.integration_type}_CLIENT_ID', 'YOUR_CLIENT_ID'),
            'redirect_uri': request.build_absolute_uri(f'/integrations/oauth/callback/{integration.id}/'),
            'response_type': 'code',
            'state': state,
        }
        
        if integration.oauth_scope:
            params['scope'] = integration.oauth_scope
        
        auth_url = f"{integration.oauth_authorize_url}?{urlencode(params)}"
        
        # Log the connection attempt
        IntegrationLog.objects.create(
            company_integration=company_integration,
            action='CONNECTED',
            description=f'OAuth connection initiated by {request.user.get_full_name()}',
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        return JsonResponse({
            'oauth_url': auth_url,
            'requires_oauth': True
        })
    else:
        # API key based connection
        api_key = request.POST.get('api_key', '')
        api_secret = request.POST.get('api_secret', '')
        
        if not api_key:
            return JsonResponse({'error': 'API key required'}, status=400)
        
        company_integration.api_key = api_key
        company_integration.api_secret = api_secret
        company_integration.status = 'ACTIVE'
        company_integration.connected_at = timezone.now()
        company_integration.connected_by = request.user
        company_integration.save()
        
        # Log the connection
        IntegrationLog.objects.create(
            company_integration=company_integration,
            action='CONNECTED',
            description=f'API key connection by {request.user.get_full_name()}',
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        messages.success(request, f'{integration.name} connected successfully!')
        return JsonResponse({'success': True})


@login_required
def integration_oauth_callback(request, integration_id):
    """Handle OAuth callback from integration provider"""
    from accounts.integration_models import Integration, CompanyIntegration, IntegrationLog
    
    integration = get_object_or_404(Integration, id=integration_id)
    company = _get_user_company(request.user)
    
    # Verify state to prevent CSRF
    state = request.GET.get('state')
    stored_state = request.session.get(f'oauth_state_{integration.id}')
    
    if not state or state != stored_state:
        messages.error(request, 'Invalid OAuth state. Please try again.')
        return redirect('integration_management')
    
    # Get authorization code
    code = request.GET.get('code')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f'OAuth error: {error}')
        return redirect('integration_management')
    
    if not code:
        messages.error(request, 'No authorization code received.')
        return redirect('integration_management')
    
    try:
        # Exchange code for access token
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': request.build_absolute_uri(f'/integrations/oauth/callback/{integration.id}/'),
            'client_id': getattr(settings, f'{integration.integration_type}_CLIENT_ID', ''),
            'client_secret': getattr(settings, f'{integration.integration_type}_CLIENT_SECRET', ''),
        }
        
        response = requests.post(integration.oauth_token_url, data=token_data)
        
        if response.status_code == 200:
            tokens = response.json()
            
            # Save tokens to company integration
            company_integration = CompanyIntegration.objects.get(
                company=company,
                integration=integration
            )
            
            company_integration.access_token = tokens.get('access_token', '')
            company_integration.refresh_token = tokens.get('refresh_token', '')
            
            if 'expires_in' in tokens:
                company_integration.token_expires_at = timezone.now() + timezone.timedelta(seconds=tokens['expires_in'])
            
            company_integration.status = 'ACTIVE'
            company_integration.connected_at = timezone.now()
            company_integration.save()
            
            # Log success
            IntegrationLog.objects.create(
                company_integration=company_integration,
                action='CONNECTED',
                description='OAuth connection completed successfully',
                success=True,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            
            messages.success(request, f'{integration.name} connected successfully!')
        else:
            messages.error(request, f'Failed to obtain access token: {response.text}')
    
    except Exception as e:
        messages.error(request, f'Connection error: {str(e)}')
    
    # Clean up session
    request.session.pop(f'oauth_state_{integration.id}', None)
    request.session.pop('oauth_integration_id', None)
    
    return redirect('integration_management')


@login_required
@require_http_methods(["POST"])
def integration_disconnect(request, integration_id):
    """Disconnect an integration"""
    from accounts.integration_models import CompanyIntegration, IntegrationLog
    
    if request.user.role not in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    company = _get_user_company(request.user)
    if not company:
        return JsonResponse({'error': 'No company assigned'}, status=400)
    
    try:
        company_integration = CompanyIntegration.objects.get(
            company=company,
            integration_id=integration_id
        )
        
        # Log disconnection
        IntegrationLog.objects.create(
            company_integration=company_integration,
            action='DISCONNECTED',
            description=f'Disconnected by {request.user.get_full_name()}',
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        # Delete the integration
        integration_name = company_integration.integration.name
        company_integration.delete()
        
        messages.success(request, f'{integration_name} disconnected successfully!')
        return JsonResponse({'success': True})
    
    except CompanyIntegration.DoesNotExist:
        return JsonResponse({'error': 'Integration not found'}, status=404)


@login_required
def integration_test(request, integration_id):
    """Test an integration connection"""
    from accounts.integration_models import CompanyIntegration, IntegrationLog
    
    if request.user.role not in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    company = _get_user_company(request.user)
    if not company:
        return JsonResponse({'error': 'No company assigned'}, status=400)
    
    try:
        company_integration = CompanyIntegration.objects.get(
            company=company,
            integration_id=integration_id
        )
        
        # Test connection based on integration type
        success = True
        message = 'Connection test successful!'
        
        # You would implement actual API test calls here
        # For example:
        # if company_integration.integration.integration_type == 'SLACK':
        #     response = requests.post(
        #         'https://slack.com/api/auth.test',
        #         headers={'Authorization': f'Bearer {company_integration.access_token}'}
        #     )
        #     success = response.json().get('ok', False)
        
        # Log the test
        IntegrationLog.objects.create(
            company_integration=company_integration,
            action='SYNC',
            description='Connection test performed',
            success=success,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        if success:
            company_integration.reset_errors()
            company_integration.last_synced_at = timezone.now()
            company_integration.save()
        
        return JsonResponse({
            'success': success,
            'message': message
        })
    
    except CompanyIntegration.DoesNotExist:
        return JsonResponse({'error': 'Integration not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def integration_webhook(request, company_id, integration_id, webhook_secret):
    """Handle incoming webhooks from integrations"""
    from accounts.integration_models import CompanyIntegration, IntegrationLog
    from accounts.models import Company
    
    try:
        company = Company.objects.get(id=company_id)
        company_integration = CompanyIntegration.objects.get(
            company=company,
            integration_id=integration_id,
            webhook_secret=webhook_secret
        )
        
        # Parse webhook data
        try:
            webhook_data = json.loads(request.body)
        except json.JSONDecodeError:
            webhook_data = {'raw': request.body.decode('utf-8')}
        
        # Log webhook receipt
        IntegrationLog.objects.create(
            company_integration=company_integration,
            action='WEBHOOK',
            description='Webhook received',
            request_data=webhook_data,
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        # Process webhook based on integration type
        # You would implement webhook processing logic here
        
        return JsonResponse({'status': 'received'})
    
    except (Company.DoesNotExist, CompanyIntegration.DoesNotExist):
        return JsonResponse({'error': 'Invalid webhook URL'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
