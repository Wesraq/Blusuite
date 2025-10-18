"""
Slack Integration Module
Handles OAuth, message posting, and notifications
"""
import requests
import json
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class SlackIntegration:
    """
    Slack API integration handler
    """
    
    BASE_URL = "https://slack.com/api"
    OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
    OAUTH_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
    
    # Required OAuth scopes
    SCOPES = [
        'chat:write',
        'chat:write.public',
        'channels:read',
        'groups:read',
        'users:read',
        'users:read.email',
    ]
    
    def __init__(self, access_token=None):
        self.access_token = access_token
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def get_oauth_url(cls, redirect_uri, state):
        """
        Generate Slack OAuth authorization URL
        """
        from urllib.parse import urlencode
        
        params = {
            'client_id': getattr(settings, 'SLACK_CLIENT_ID', ''),
            'scope': ','.join(cls.SCOPES),
            'redirect_uri': redirect_uri,
            'state': state,
        }
        
        return f"{cls.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
    
    @classmethod
    def exchange_code_for_token(cls, code, redirect_uri):
        """
        Exchange OAuth code for access token
        
        Returns:
            dict: Token response with access_token, team_id, team_name, etc.
        """
        data = {
            'client_id': getattr(settings, 'SLACK_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'SLACK_CLIENT_SECRET', ''),
            'code': code,
            'redirect_uri': redirect_uri,
        }
        
        response = requests.post(cls.OAUTH_TOKEN_URL, data=data)
        return response.json()
    
    def test_connection(self):
        """
        Test if the connection is working
        
        Returns:
            dict: {'ok': True/False, 'user': user_info, 'team': team_info}
        """
        response = requests.post(
            f"{self.BASE_URL}/auth.test",
            headers=self.headers
        )
        return response.json()
    
    def get_channels(self):
        """
        Get list of channels
        
        Returns:
            list: List of channel dicts
        """
        response = requests.get(
            f"{self.BASE_URL}/conversations.list",
            headers=self.headers,
            params={'types': 'public_channel,private_channel'}
        )
        data = response.json()
        return data.get('channels', []) if data.get('ok') else []
    
    def get_users(self):
        """
        Get list of workspace users
        
        Returns:
            list: List of user dicts
        """
        response = requests.get(
            f"{self.BASE_URL}/users.list",
            headers=self.headers
        )
        data = response.json()
        return data.get('members', []) if data.get('ok') else []
    
    def post_message(self, channel, text=None, blocks=None, attachments=None):
        """
        Post a message to a Slack channel
        
        Args:
            channel (str): Channel ID or name
            text (str): Plain text message
            blocks (list): Block Kit formatted message
            attachments (list): Message attachments
        
        Returns:
            dict: Response with 'ok' status and message details
        """
        payload = {
            'channel': channel,
        }
        
        if text:
            payload['text'] = text
        if blocks:
            payload['blocks'] = blocks
        if attachments:
            payload['attachments'] = attachments
        
        response = requests.post(
            f"{self.BASE_URL}/chat.postMessage",
            headers=self.headers,
            json=payload
        )
        return response.json()
    
    def send_notification(self, channel, notification_type, data):
        """
        Send formatted notification to Slack
        
        Args:
            channel (str): Channel ID
            notification_type (str): Type of notification
            data (dict): Notification data
        
        Returns:
            dict: Response from Slack API
        """
        blocks = self._format_notification(notification_type, data)
        return self.post_message(channel, blocks=blocks)
    
    def _format_notification(self, notification_type, data):
        """
        Format notification into Slack Block Kit format
        """
        if notification_type == 'leave_request':
            return self._format_leave_request(data)
        elif notification_type == 'employee_request':
            return self._format_employee_request(data)
        elif notification_type == 'document_approval':
            return self._format_document_approval(data)
        elif notification_type == 'attendance_alert':
            return self._format_attendance_alert(data)
        elif notification_type == 'payroll_generated':
            return self._format_payroll_notification(data)
        else:
            return self._format_generic_notification(data)
    
    def _format_leave_request(self, data):
        """Format leave request notification"""
        employee = data.get('employee', 'Unknown Employee')
        leave_type = data.get('leave_type', 'Leave')
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')
        reason = data.get('reason', '')
        
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🏖️ New Leave Request",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Employee:*\n{employee}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Leave Type:*\n{leave_type}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Start Date:*\n{start_date}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*End Date:*\n{end_date}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Reason:*\n{reason}"
                }
            },
            {
                "type": "divider"
            }
        ]
    
    def _format_employee_request(self, data):
        """Format employee request notification"""
        employee = data.get('employee', 'Unknown Employee')
        request_type = data.get('request_type', 'Request')
        description = data.get('description', '')
        amount = data.get('amount', '')
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📋 New {request_type}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Employee:*\n{employee}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Type:*\n{request_type}"
                    }
                ]
            }
        ]
        
        if amount:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Amount:*\n${amount}"
                }
            })
        
        if description:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:*\n{description}"
                }
            })
        
        blocks.append({"type": "divider"})
        return blocks
    
    def _format_document_approval(self, data):
        """Format document approval notification"""
        employee = data.get('employee', 'Unknown Employee')
        document_type = data.get('document_type', 'Document')
        status = data.get('status', '')
        
        emoji = "✅" if status == "Approved" else "❌"
        
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Document {status}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Employee:*\n{employee}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Document:*\n{document_type}"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
    
    def _format_attendance_alert(self, data):
        """Format attendance alert"""
        employee = data.get('employee', 'Unknown Employee')
        alert_type = data.get('alert_type', 'Alert')
        message = data.get('message', '')
        
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⏰ Attendance Alert",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Employee:*\n{employee}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Alert:*\n{alert_type}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            },
            {
                "type": "divider"
            }
        ]
    
    def _format_payroll_notification(self, data):
        """Format payroll notification"""
        period = data.get('period', 'Current Period')
        total_amount = data.get('total_amount', '0')
        employee_count = data.get('employee_count', 0)
        
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "💰 Payroll Generated",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Period:*\n{period}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Employees:*\n{employee_count}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Amount:*\n${total_amount}"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
    
    def _format_generic_notification(self, data):
        """Format generic notification"""
        title = data.get('title', 'Notification')
        message = data.get('message', '')
        
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title,
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            },
            {
                "type": "divider"
            }
        ]


def send_slack_notification(company_integration, notification_type, data):
    """
    Helper function to send Slack notification for a company
    
    Args:
        company_integration: CompanyIntegration instance
        notification_type: Type of notification
        data: Notification data
    
    Returns:
        bool: Success status
    """
    try:
        if not company_integration.is_token_valid():
            return False
        
        slack = SlackIntegration(company_integration.access_token)
        
        # Get default channel from config or use general
        channel = company_integration.config_json.get('default_channel', 'general')
        
        response = slack.send_notification(channel, notification_type, data)
        
        # Log the activity
        from accounts.integration_models import IntegrationLog
        IntegrationLog.objects.create(
            company_integration=company_integration,
            action='SYNC',
            description=f'Slack notification sent: {notification_type}',
            request_data={'notification_type': notification_type, 'channel': channel},
            response_data=response,
            success=response.get('ok', False)
        )
        
        if not response.get('ok'):
            company_integration.mark_error(f"Slack error: {response.get('error', 'Unknown error')}")
            return False
        
        company_integration.last_synced_at = timezone.now()
        company_integration.save(update_fields=['last_synced_at'])
        
        return True
    
    except Exception as e:
        company_integration.mark_error(str(e))
        return False
