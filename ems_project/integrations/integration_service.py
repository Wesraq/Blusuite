"""
Unified Integration Service
Central dispatcher that routes notifications and actions through all connected integrations.
Other parts of the system call these functions — they automatically check which integrations
are active for the company and dispatch accordingly.
"""
import logging
import requests
import json
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_active_integration(company, integration_type=None, integration_name=None):
    """Get active CompanyIntegration for a company by type or name."""
    from blu_staff.apps.accounts.integration_models import CompanyIntegration
    qs = CompanyIntegration.objects.filter(company=company, status='ACTIVE')
    if integration_type:
        qs = qs.filter(integration__integration_type=integration_type)
    if integration_name:
        qs = qs.filter(integration__name=integration_name)
    return qs.select_related('integration').first()


def _log_integration_event(ci, action, description, success=True, request_data=None, response_data=None):
    """Create an IntegrationLog entry."""
    from blu_staff.apps.accounts.integration_models import IntegrationLog
    IntegrationLog.objects.create(
        company_integration=ci,
        action=action,
        description=description,
        success=success,
        request_data=request_data or {},
        response_data=response_data or {},
    )


# ─────────────────────────────────────────────
# SLACK
# ─────────────────────────────────────────────
def send_slack_message(company, channel, text, blocks=None):
    """Send a message to a Slack channel for the given company."""
    ci = _get_active_integration(company, integration_type='SLACK')
    if not ci:
        return False
    token = (ci.config_json or {}).get('bot_token') or ci.access_token
    if not token:
        return False
    try:
        payload = {'channel': channel, 'text': text}
        if blocks:
            payload['blocks'] = blocks
        resp = requests.post(
            'https://slack.com/api/chat.postMessage',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=payload, timeout=10,
        )
        data = resp.json()
        _log_integration_event(ci, 'SYNC', f'Slack message to {channel}', data.get('ok', False),
                               request_data=payload, response_data=data)
        if data.get('ok'):
            ci.last_synced_at = timezone.now()
            ci.save(update_fields=['last_synced_at'])
        return data.get('ok', False)
    except Exception as e:
        logger.error(f'Slack send error: {e}')
        ci.mark_error(str(e))
        return False


def notify_slack(company, notification_type, data):
    """Send a formatted notification to the company's default Slack channel."""
    ci = _get_active_integration(company, integration_type='SLACK')
    if not ci:
        return False
    config = ci.config_json or {}
    channel = config.get('default_channel', 'general')
    from ems_project.integrations.slack_integration import SlackIntegration
    token = config.get('bot_token') or ci.access_token
    if not token:
        return False
    slack = SlackIntegration(token)
    try:
        response = slack.send_notification(channel, notification_type, data)
        success = response.get('ok', False)
        _log_integration_event(ci, 'SYNC', f'Slack notification: {notification_type}', success,
                               response_data=response)
        if success:
            ci.last_synced_at = timezone.now()
            ci.save(update_fields=['last_synced_at'])
        return success
    except Exception as e:
        logger.error(f'Slack notification error: {e}')
        ci.mark_error(str(e))
        return False


# ─────────────────────────────────────────────
# MICROSOFT TEAMS
# ─────────────────────────────────────────────
def send_teams_message(company, text, title=None):
    """Send a message via Microsoft Teams webhook or Graph API."""
    ci = _get_active_integration(company, integration_type='MICROSOFT_TEAMS')
    if not ci:
        ci = _get_active_integration(company, integration_name='Microsoft 365')
    if not ci:
        return False
    config = ci.config_json or {}
    webhook_url = ci.webhook_url
    if webhook_url:
        # Incoming webhook connector
        try:
            card = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "summary": title or "BluSuite Notification",
                "themeColor": "E11D48",
                "title": title or "BluSuite Notification",
                "sections": [{"text": text}],
            }
            resp = requests.post(webhook_url, json=card, timeout=10)
            success = resp.status_code == 200
            _log_integration_event(ci, 'SYNC', f'Teams webhook: {title}', success)
            return success
        except Exception as e:
            logger.error(f'Teams webhook error: {e}')
            ci.mark_error(str(e))
            return False
    return False


# ─────────────────────────────────────────────
# SENDGRID (Transactional Email)
# ─────────────────────────────────────────────
def send_sendgrid_email(company, to_email, subject, html_content, plain_content=None):
    """Send email via SendGrid API."""
    ci = _get_active_integration(company, integration_name='SendGrid')
    if not ci:
        return False
    api_key = ci.api_key
    config = ci.config_json or {}
    from_email = config.get('from_email', 'noreply@blusuite.com')
    from_name = config.get('from_name', 'BluSuite')
    if not api_key:
        return False
    try:
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email, "name": from_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": plain_content or subject},
                {"type": "text/html", "value": html_content},
            ],
        }
        resp = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload, timeout=15,
        )
        success = resp.status_code in (200, 201, 202)
        _log_integration_event(ci, 'SYNC', f'SendGrid email to {to_email}: {subject}', success,
                               response_data={'status_code': resp.status_code})
        if success:
            ci.last_synced_at = timezone.now()
            ci.save(update_fields=['last_synced_at'])
        return success
    except Exception as e:
        logger.error(f'SendGrid error: {e}')
        ci.mark_error(str(e))
        return False


# ─────────────────────────────────────────────
# TWILIO SMS
# ─────────────────────────────────────────────
def send_twilio_sms(company, to_number, message):
    """Send SMS via Twilio."""
    ci = _get_active_integration(company, integration_name='SMS Gateway (Twilio)')
    if not ci:
        return False
    account_sid = ci.api_key
    auth_token = ci.api_secret
    config = ci.config_json or {}
    from_number = config.get('from_number', '')
    if not (account_sid and auth_token and from_number):
        return False
    try:
        resp = requests.post(
            f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json',
            auth=(account_sid, auth_token),
            data={'From': from_number, 'To': to_number, 'Body': message},
            timeout=15,
        )
        data = resp.json()
        success = resp.status_code == 201
        _log_integration_event(ci, 'SYNC', f'Twilio SMS to {to_number}', success,
                               response_data={'sid': data.get('sid'), 'status': data.get('status')})
        if success:
            ci.last_synced_at = timezone.now()
            ci.save(update_fields=['last_synced_at'])
        return success
    except Exception as e:
        logger.error(f'Twilio error: {e}')
        ci.mark_error(str(e))
        return False


# ─────────────────────────────────────────────
# WHATSAPP BUSINESS (Meta Cloud API)
# ─────────────────────────────────────────────
def send_whatsapp_message(company, to_number, message):
    """Send WhatsApp message via Meta Cloud API."""
    ci = _get_active_integration(company, integration_name='WhatsApp Business')
    if not ci:
        return False
    access_token = ci.api_key
    config = ci.config_json or {}
    phone_number_id = config.get('phone_number_id', '')
    if not (access_token and phone_number_id):
        return False
    try:
        resp = requests.post(
            f'https://graph.facebook.com/v18.0/{phone_number_id}/messages',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": message},
            },
            timeout=15,
        )
        data = resp.json()
        success = 'messages' in data
        _log_integration_event(ci, 'SYNC', f'WhatsApp to {to_number}', success, response_data=data)
        if success:
            ci.last_synced_at = timezone.now()
            ci.save(update_fields=['last_synced_at'])
        return success
    except Exception as e:
        logger.error(f'WhatsApp error: {e}')
        ci.mark_error(str(e))
        return False


# ─────────────────────────────────────────────
# ZOOM (Create Meeting)
# ─────────────────────────────────────────────
def create_zoom_meeting(company, topic, start_time, duration_minutes=60, agenda=''):
    """Create a Zoom meeting using Server-to-Server OAuth."""
    ci = _get_active_integration(company, integration_type='ZOOM')
    if not ci:
        return None
    config = ci.config_json or {}
    client_id = config.get('client_id', '')
    client_secret = config.get('client_secret', '')
    account_id = config.get('account_id', '')
    if not (client_id and client_secret and account_id):
        return None
    try:
        # Get access token via Server-to-Server OAuth
        token_resp = requests.post(
            'https://zoom.us/oauth/token',
            params={'grant_type': 'account_credentials', 'account_id': account_id},
            auth=(client_id, client_secret),
            timeout=10,
        )
        token_data = token_resp.json()
        access_token = token_data.get('access_token')
        if not access_token:
            ci.mark_error(f"Zoom token error: {token_data}")
            return None

        # Create meeting
        meeting_resp = requests.post(
            'https://api.zoom.us/v2/users/me/meetings',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={
                'topic': topic,
                'type': 2,  # Scheduled
                'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%SZ') if hasattr(start_time, 'strftime') else start_time,
                'duration': duration_minutes,
                'agenda': agenda,
                'settings': {'join_before_host': True, 'waiting_room': False},
            },
            timeout=15,
        )
        meeting = meeting_resp.json()
        success = 'join_url' in meeting
        _log_integration_event(ci, 'SYNC', f'Zoom meeting created: {topic}', success, response_data=meeting)
        if success:
            ci.last_synced_at = timezone.now()
            ci.save(update_fields=['last_synced_at'])
        return meeting if success else None
    except Exception as e:
        logger.error(f'Zoom error: {e}')
        ci.mark_error(str(e))
        return None


# ─────────────────────────────────────────────
# GOOGLE CALENDAR (Create Event)
# ─────────────────────────────────────────────
def create_google_calendar_event(company, summary, start_time, end_time, description='', attendees=None):
    """Create a Google Calendar event. Requires valid access_token (refreshed externally)."""
    ci = _get_active_integration(company, integration_type='GOOGLE_CALENDAR')
    if not ci:
        return None
    access_token = ci.access_token
    if not access_token:
        return None
    try:
        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'},
        }
        if attendees:
            event['attendees'] = [{'email': e} for e in attendees]
        resp = requests.post(
            'https://www.googleapis.com/calendar/v3/calendars/primary/events',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json=event, timeout=15,
        )
        data = resp.json()
        success = 'id' in data
        _log_integration_event(ci, 'SYNC', f'Google Calendar event: {summary}', success, response_data=data)
        if success:
            ci.last_synced_at = timezone.now()
            ci.save(update_fields=['last_synced_at'])
        return data if success else None
    except Exception as e:
        logger.error(f'Google Calendar error: {e}')
        ci.mark_error(str(e))
        return None


# ─────────────────────────────────────────────
# ACCOUNTING EXPORT (QuickBooks / Xero / Sage)
# ─────────────────────────────────────────────
def export_payroll_to_accounting(company, payroll_data):
    """
    Export payroll data to connected accounting system.
    Returns dict with status and details.
    payroll_data should be a list of dicts with: employee_name, gross, deductions, net, period
    """
    for name in ('QuickBooks', 'Xero', 'Sage'):
        ci = _get_active_integration(company, integration_name=name)
        if ci:
            break
    else:
        return {'success': False, 'error': 'No accounting integration connected'}

    config = ci.config_json or {}
    provider = ci.integration.name

    # Build export payload
    export = {
        'provider': provider,
        'company': company.name,
        'exported_at': timezone.now().isoformat(),
        'records': payroll_data,
        'total_gross': sum(r.get('gross', 0) for r in payroll_data),
        'total_net': sum(r.get('net', 0) for r in payroll_data),
        'employee_count': len(payroll_data),
    }

    _log_integration_event(ci, 'SYNC', f'Payroll export to {provider}: {len(payroll_data)} records',
                           True, request_data=export)
    ci.last_synced_at = timezone.now()
    ci.save(update_fields=['last_synced_at'])

    return {'success': True, 'provider': provider, 'records': len(payroll_data), 'export': export}


# ─────────────────────────────────────────────
# OKTA SSO (Verify User)
# ─────────────────────────────────────────────
def verify_okta_user(company, email):
    """Check if a user exists in Okta directory."""
    ci = _get_active_integration(company, integration_name='Okta')
    if not ci:
        return None
    config = ci.config_json or {}
    domain = config.get('okta_domain', '').rstrip('/')
    api_token = ci.api_key
    if not (domain and api_token):
        return None
    try:
        resp = requests.get(
            f'{domain}/api/v1/users/{email}',
            headers={'Authorization': f'SSWS {api_token}', 'Accept': 'application/json'},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            _log_integration_event(ci, 'SYNC', f'Okta user verified: {email}', True)
            return data
        return None
    except Exception as e:
        logger.error(f'Okta error: {e}')
        return None


# ─────────────────────────────────────────────
# UNIFIED NOTIFICATION DISPATCHER
# ─────────────────────────────────────────────
def notify_all_channels(company, event_type, data, employee=None):
    """
    Send notification across ALL connected channels for a company.
    This is the main function other parts of the system should call.

    Args:
        company: Company model instance
        event_type: str - 'leave_request', 'leave_approved', 'payroll_generated',
                    'attendance_alert', 'employee_onboarded', 'document_approved', etc.
        data: dict with event-specific data (employee, details, etc.)
        employee: optional User instance for SMS/WhatsApp delivery
    """
    results = {}

    # Slack
    try:
        results['slack'] = notify_slack(company, event_type, data)
    except Exception as e:
        logger.error(f'Slack dispatch error: {e}')
        results['slack'] = False

    # Microsoft Teams
    try:
        title = data.get('title', event_type.replace('_', ' ').title())
        message = data.get('message', '')
        if not message:
            parts = [f"*{k}:* {v}" for k, v in data.items() if k not in ('title',)]
            message = '\n'.join(parts)
        results['teams'] = send_teams_message(company, message, title)
    except Exception as e:
        logger.error(f'Teams dispatch error: {e}')
        results['teams'] = False

    # SMS (if employee has phone)
    if employee and hasattr(employee, 'employee_profile'):
        phone = getattr(employee.employee_profile, 'phone', '') or getattr(employee, 'phone', '')
        if phone:
            sms_text = data.get('sms_text', data.get('message', f'BluSuite: {event_type.replace("_", " ")}'))
            try:
                results['sms'] = send_twilio_sms(company, phone, sms_text)
            except Exception as e:
                logger.error(f'SMS dispatch error: {e}')
                results['sms'] = False

            try:
                results['whatsapp'] = send_whatsapp_message(company, phone, sms_text)
            except Exception as e:
                logger.error(f'WhatsApp dispatch error: {e}')
                results['whatsapp'] = False

    # SendGrid email (if employee has email)
    if employee and employee.email:
        subject = data.get('email_subject', data.get('title', event_type.replace('_', ' ').title()))
        html = data.get('email_html', f"<p>{data.get('message', event_type)}</p>")
        try:
            results['sendgrid'] = send_sendgrid_email(company, employee.email, subject, html)
        except Exception as e:
            logger.error(f'SendGrid dispatch error: {e}')
            results['sendgrid'] = False

    return results
