from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Count, Avg, Sum, Q, F, ExpressionWrapper, DurationField, Max, Subquery, OuterRef
from django.db.models.functions import TruncDate, ExtractWeek, ExtractMonth, ExtractYear
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.conf import settings
from django.db import connection, IntegrityError, DatabaseError, OperationalError
from decimal import Decimal
from collections import defaultdict
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.hashers import make_password
import calendar
from django.core.mail import EmailMessage
import json
import os
import math

from ems_project.plan_features import (
    require_feature, require_employee_limit, get_plan_context,
    company_has_feature, company_can_add_employee, get_company_plan,
    FEAT_ATTENDANCE_BASIC, FEAT_ATTENDANCE_GPS,
    FEAT_LEAVE_MANAGEMENT, FEAT_LEAVE_APPROVALS,
    FEAT_PAYROLL_BASIC, FEAT_PAYROLL_AUTOMATED,
    FEAT_PERFORMANCE_REVIEWS, FEAT_DOCUMENT_MANAGEMENT,
    FEAT_CUSTOM_REPORTS, FEAT_ADVANCED_ANALYTICS,
    FEAT_CUSTOM_INTEGRATIONS, FEAT_API_ACCESS,
)

# Local imports
from blu_staff.apps.accounts.models import (
    Company,
    CompanyBranch,
    CompanyAPIKey,
    CompanyAttendanceSettings,
    CompanyBiometricSettings,
    CompanyDepartment,
    CompanyEmailSettings,
    CompanyHoliday,
    CompanyNotificationSettings,
    CompanyPayGrade,
    CompanyPosition,
    EmployeeIdConfiguration,
    EmployeeProfile,
    EmployerProfile,
    SystemSettings,
    SystemSettingsAudit,
    CompanyRegistrationRequest,
    User,
)
from blu_staff.apps.accounts.integration_models import (
    CompanyIntegration as IntegrationConnection,
    Integration as IntegrationDefinition,
    IntegrationLog,
)
from blu_staff.apps.accounts.forms import (
    CompanyRegistrationRequestForm,
    CompanyDepartmentForm,
    CompanyProfileForm,
    CompanyBiometricSettingsForm,
    CompanyEmailSettingsForm,
    CompanyPayGradeForm,
    CompanyPositionForm,
    EmployeeIdConfigurationForm,
    CompanyNotificationSettingsForm,
    CompanyAPIKeyForm,
    SystemSettingsForm,
)
from blu_staff.apps.attendance.models import Attendance, LeaveRequest
from blu_staff.apps.documents.models import EmployeeDocument, DocumentCategory, DocumentAccessLog
from tenant_management.models import Tenant, TenantDomain, TenantUserRole
from django.urls import reverse, NoReverseMatch
# PERFORMANCE MODULE DISABLED
# from blu_staff.apps.performance.models import PerformanceReview
from blu_support.models import SupportTicket, KnowledgeArticle
from blu_support.forms import KnowledgeArticleForm, SupportTicketForm
from blu_staff.apps.payroll.models import Payroll

# PERFORMANCE MODULE DISABLED - Import performance cycle management views
# from blu_staff.apps.performance.cycle_views import (
#     review_cycles_list, review_cycle_create, review_cycle_detail,
#     bulk_assign_employees, initiate_cycle_reviews, performance_analytics_dashboard
# )


def _is_superadmin(user):
    """Helper function to check if user is SuperAdmin"""
    return hasattr(user, 'is_superadmin') and user.is_superadmin


def calculate_distance_meters(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two GPS coordinates using Haversine formula.
    Returns distance in meters.
    """
    # Convert to float if Decimal
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    
    # Earth's radius in meters
    R = 6371000
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(delta_lat/2) * math.sin(delta_lat/2) + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * \
        math.sin(delta_lon/2) * math.sin(delta_lon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance


def tenant_metadata_available():
    from blu_staff.apps.payroll.models import Benefit, EmployeeBenefit
    from django.db import connection

    if connection.vendor != 'sqlite':
        return True

    try:
        # SECURITY: Use Django's schema inspection instead of raw SQL
        enrollment_columns = [field.name for field in EmployeeBenefit._meta.get_fields()]
        benefit_columns = [field.name for field in Benefit._meta.get_fields()]
        return 'tenant_id' in enrollment_columns and 'tenant_id' in benefit_columns
    except Exception:
        return False


def _generate_employee_identifier(employee, company):
    """Generate a unique employee ID using configuration when available."""
    config = EmployeeIdConfiguration.objects.filter(company=company).first()
    base_identifier = None
    if config:
        base_identifier = config.generate_employee_id()

    if not base_identifier:
        company_part = company.pk if company and company.pk else 'EMP'
        base_identifier = f"{company_part}-{employee.pk}"

    unique_identifier = base_identifier
    counter = 1
    while EmployeeProfile.objects.filter(employee_id=unique_identifier).exists():
        unique_identifier = f"{base_identifier}-{counter}"
        counter += 1

    return unique_identifier, config


def ensure_employee_profile(employee, company):
    """Guarantee that every employee has an associated profile."""
    if hasattr(employee, 'employee_profile') and employee.employee_profile:
        return employee.employee_profile, False

    identifier, config = _generate_employee_identifier(employee, company)
    hire_date = None
    if getattr(employee, 'date_joined', None):
        hire_date = employee.date_joined.date()

    defaults = {
        'company': company,
        'employee_id': identifier,
        'job_title': 'Employee',
        'department': 'Unassigned',
        'date_hired': hire_date or timezone.now().date(),
        'salary': None,
        'pay_grade': '',
        'bank_name': '',
        'account_number': '',
        'bank_branch': '',
        'emergency_contact_name': '',
        'emergency_contact_phone': '',
        'emergency_contact_email': '',
        'emergency_contact_address': '',
        'employment_type': '',
        'employee_role': EmployeeProfile.EmployeeRole.EMPLOYEE,
    }


def _parse_security_settings(raw):
    """Extract security config sub-keys from company.security_settings JSON."""
    pp = raw.get('password_policy', {})
    ss = raw.get('session', {})
    tfa = raw.get('twofa', {})
    lr = raw.get('login_restrictions', {})
    return {
        'min_password_length': pp.get('min_length', 8),
        'password_expiry_days': pp.get('expiry_days', 90),
        'require_uppercase': pp.get('require_uppercase', True),
        'require_lowercase': pp.get('require_lowercase', True),
        'require_number': pp.get('require_number', True),
        'require_special': pp.get('require_special', False),
        'prevent_reuse': pp.get('prevent_reuse', True),
        'session_timeout_minutes': ss.get('timeout_minutes', 30),
        'max_session_hours': ss.get('max_hours', 12),
        'single_session': ss.get('single_session', False),
        'logout_on_close': ss.get('logout_on_close', False),
        'twofa_enforcement': tfa.get('enforcement', 'disabled'),
        'twofa_method': tfa.get('method', 'email'),
        'max_failed_attempts': lr.get('max_failed_attempts', 5),
        'lockout_duration_minutes': lr.get('lockout_duration_minutes', 15),
        'notify_admin_lockout': lr.get('notify_admin_lockout', False),
        'log_failed_attempts': lr.get('log_failed_attempts', True),
    }


def _collect_company_settings_context(user, nav_flags):
    today = timezone.now().date()
    company = _get_user_company(user)
    if not company:
        return {
            'company_id': None,
            'company_name': '',
            'plan': {
                'name': '',
                'expires_at': None,
                'is_trial': False,
                'trial_ends_at': None,
            },
            'tenant': None,
            'domains': [],
            'statistics': {
                'total_users': 0,
                'active_users': 0,
                'pending_invites': 0,
                'role_breakdown': [],
                'active_modules': 0,
                'api_keys_active': 0,
            },
            'branding': {
                'logo_url': '',
                'stamp_url': '',
            },
            'employee_id_preview': '',
            'module_access': [],
            'communication': {
                'email_configured': False,
                'biometric_configured': False,
                'notification_digest': '',
            },
            'compliance': {
                'attendance': {},
                'upcoming_holidays': [],
            },
            'integrations': [],
            'api_keys': [],
            'support_requests': [],
            'activity_log': [],
            'cards': {
                'administrative_tools': [],
                'hr_management': [],
                'blusuite_administration': [],
            },
            'forms': {},
        }

    tenant = getattr(company, 'tenant', None)

    branding = {
        'logo_url': company.logo.url if getattr(company, 'logo', None) else '',
        'stamp_url': company.company_stamp.url if getattr(company, 'company_stamp', None) else '',
    }

    company_users = User.objects.filter(company=company)
    total_users = company_users.count()
    active_users = company_users.filter(is_active=True).count()

    role_counts = list(
        company_users.values('role')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    role_lookup = dict(User.Role.choices)
    for entry in role_counts:
        entry['label'] = role_lookup.get(entry['role'], entry['role'].replace('_', ' ').title())

    pending_invites = 0
    tenant_domains = []
    tenant_owner = None
    if tenant:
        pending_invites = TenantUserRole.objects.filter(
            tenant=tenant,
            accepted_at__isnull=True,
        ).count()
        tenant_domains = list(
            tenant.domains.order_by('-is_primary', 'domain')
            .values('domain', 'is_primary')
        )
        tenant_owner = tenant.owner.get_full_name() if tenant.owner else None

    module_catalogue = [
        {
            'name': 'Staff (EMS)',
            'key': 'show_staff_suite',
            'description': 'HR, payroll and employee lifecycle controls.',
            'manage_url': _safe_reverse('blu_staff_home'),
            'settings_url': _safe_reverse('settings_dashboard'),
        },
        {
            'name': 'Projects (PMS)',
            'key': 'show_projects_suite',
            'description': 'Project governance, delivery and reporting.',
            'manage_url': _safe_reverse('blu_projects_home'),
            'settings_url': '#',
        },
        {
            'name': 'Assets (AMS)',
            'key': 'show_assets_suite',
            'description': 'Asset lifecycle, assignments and audits.',
            'manage_url': _safe_reverse('blu_assets_home'),
            'settings_url': '#',
        },
        {
            'name': 'Analytics Studio',
            'key': 'show_analytics_suite',
            'description': 'Cross-suite dashboards and KPIs.',
            'manage_url': _safe_reverse('blu_analytics_home'),
            'settings_url': '#',
        },
        {
            'name': 'Integrations',
            'key': 'show_integrations_suite',
            'description': 'APIs, webhooks and marketplace connectors.',
            'manage_url': _safe_reverse('blu_integrations_home'),
            'settings_url': _safe_reverse('blu_integrations_home'),
        },
    ]

    module_access = []
    for item in module_catalogue:
        module_access.append({
            'name': item['name'],
            'enabled': bool(nav_flags.get(item['key'])),
            'description': item['description'],
            'manage_url': item['manage_url'],
            'settings_url': item['settings_url'],
        })
    active_modules = sum(1 for m in module_access if m['enabled'])

    departments_qs = CompanyDepartment.objects.filter(company=company).order_by('name')
    positions_qs = CompanyPosition.objects.filter(company=company).select_related('department').order_by('name')
    pay_grades_qs = CompanyPayGrade.objects.filter(company=company).order_by('name')

    orientation_key = getattr(company, 'payslip_orientation', '') or 'portrait'
    orientation_label = orientation_key.replace('_', ' ').title()
    layout_key = getattr(company, 'payslip_layout', '') or 'modern'
    header_style_key = getattr(company, 'payslip_header_style', '') or 'logo_left'
    logo_position_key = getattr(company, 'payslip_logo_position', '') or 'top-left'
    stamp_position_key = getattr(company, 'payslip_stamp_position', '') or 'bottom-right'
    address_position_key = getattr(company, 'payslip_address_position', '') or 'top-right'
    header_color = getattr(company, 'payslip_header_color', '') or '#3b82f6'
    accent_color = getattr(company, 'payslip_accent_color', '') or '#10b981'
    section_color = getattr(company, 'payslip_section_color', '') or '#C5D9F1'
    footer_text = getattr(company, 'payslip_footer_content', '') or ''
    header_content = getattr(company, 'payslip_header_content', '') or ''

    default_section_order = ['employee_info', 'salary_info', 'deductions', 'summary']
    section_order = company.payslip_section_order or default_section_order
    field_positions = company.payslip_field_positions or {}

    available_sections = [
        {'id': 'employee_info', 'name': 'Employee Information', 'icon': ''},
        {'id': 'salary_info', 'name': 'Salary Information', 'icon': ''},
        {'id': 'deductions', 'name': 'Deductions', 'icon': ''},
        {'id': 'allowances', 'name': 'Allowances', 'icon': ''},
        {'id': 'summary', 'name': 'Summary', 'icon': ''},
        {'id': 'tax_breakdown', 'name': 'Tax Breakdown', 'icon': ''},
        {'id': 'ytd_summary', 'name': 'YTD Summary', 'icon': ''},
    ]

    position_options = [
        {'value': 'top-left', 'label': 'Top Left'},
        {'value': 'top-center', 'label': 'Top Center'},
        {'value': 'top-right', 'label': 'Top Right'},
        {'value': 'bottom-left', 'label': 'Bottom Left'},
        {'value': 'bottom-center', 'label': 'Bottom Center'},
        {'value': 'bottom-right', 'label': 'Bottom Right'},
    ]

    payslip_config_payload = {
        'orientation': orientation_key,
        'layout': layout_key,
        'headerStyle': header_style_key,
        'logoPosition': logo_position_key,
        'stampPosition': stamp_position_key,
        'addressPosition': address_position_key,
        'sectionOrder': section_order,
        'fieldPositions': field_positions,
        'headerContent': header_content,
        'footerContent': footer_text,
        'headerColor': header_color,
        'accentColor': accent_color,
        'sectionColor': section_color,
        'showLogo': bool(getattr(company, 'show_company_logo', True)),
        'showStamp': bool(getattr(company, 'show_company_stamp', True)),
        'showSignature': bool(getattr(company, 'show_signature', True)),
        'showTaxBreakdown': bool(getattr(company, 'show_tax_breakdown', True)),
        'showConfidentialityNotice': bool(getattr(company, 'show_confidentiality_notice', False)),
        'company': {
            'name': company.name,
            'address': company.address,
            'phone': company.phone,
            'email': company.email,
            'taxId': company.tax_id,
            'country': company.country,
            'logoUrl': company.logo.url if getattr(company, 'logo', None) else '',
            'stampUrl': company.company_stamp.url if getattr(company, 'company_stamp', None) else '',
        },
    }

    config_json = json.dumps(payslip_config_payload)

    # Get or create settings objects
    from blu_staff.apps.accounts.models import (
        CompanyEmailSettings, CompanyBiometricSettings, 
        CompanyNotificationSettings, EmployeeIdConfiguration,
        CompanySettings as CS,
    )
    config, _ = EmployeeIdConfiguration.objects.get_or_create(company=company)
    email_settings, _ = CompanyEmailSettings.objects.get_or_create(company=company)
    biometric_settings, _ = CompanyBiometricSettings.objects.get_or_create(company=company)
    notification_settings, _ = CompanyNotificationSettings.objects.get_or_create(company=company)

    # Module toggles from CompanySettings
    company_settings = CS.get_for_company(company)
    module_toggles = {
        'enable_attendance': company_settings.enable_attendance,
        'enable_leave': company_settings.enable_leave,
        'enable_payroll': company_settings.enable_payroll,
        'enable_performance': company_settings.enable_performance,
        'enable_training': company_settings.enable_training,
        'enable_onboarding': company_settings.enable_onboarding,
        'enable_assets': company_settings.enable_assets,
        'enable_eforms': company_settings.enable_eforms,
        'enable_benefits': company_settings.enable_benefits,
        'enable_documents': company_settings.enable_documents,
        'enable_requests': company_settings.enable_requests,
        'enable_communication': company_settings.enable_communication,
        'enable_reports': company_settings.enable_reports,
    }

    # Real company users for Users & Roles section
    company_users_list = list(
        company_users.filter(is_active=True)
        .order_by('role', 'first_name')
        .values('id', 'first_name', 'last_name', 'email', 'role', 'is_active', 'date_joined')[:50]
    )
    role_lookup_full = dict(User.Role.choices)
    for u in company_users_list:
        u['full_name'] = f"{u['first_name']} {u['last_name']}".strip() or u['email']
        u['role_display'] = role_lookup_full.get(u['role'], u['role'])

    profile_form = CompanyProfileForm(instance=company)
    email_form = CompanyEmailSettingsForm(instance=email_settings)
    biometric_form = CompanyBiometricSettingsForm(instance=biometric_settings)
    notification_form = CompanyNotificationSettingsForm(instance=notification_settings)
    api_key_form = CompanyAPIKeyForm()
    employee_id_form = EmployeeIdConfigurationForm(instance=config)
    department_form = CompanyDepartmentForm(company=company)
    position_form = CompanyPositionForm(company=company)
    pay_grade_form = CompanyPayGradeForm(company=company)

    forms_payload = {
        'profile': {
            'form': profile_form,
            'action': _safe_reverse('blu_settings_home'),
            'action_key': 'company_profile',
            'enctype': 'multipart/form-data',
        },
        'email': {
            'form': email_form,
            'action': _safe_reverse('blu_settings_home'),
            'action_key': 'email_smtp',
        },
        'biometric': {
            'form': biometric_form,
            'action': _safe_reverse('blu_settings_home'),
            'action_key': 'biometric',
        },
        'notifications': {
            'form': notification_form,
            'action': _safe_reverse('blu_settings_home'),
            'action_key': 'notifications',
        },
        'api_keys': {
            'form': api_key_form,
            'action': _safe_reverse('blu_settings_home'),
            'action_key': 'api_key',
        },
    }

    # API keys
    api_keys_qs = CompanyAPIKey.objects.filter(company=company, is_active=True)
    api_keys = [
        {
            'name': k.name,
            'key': k.key,
            'created_at': k.created_at,
            'is_active': k.is_active,
        }
        for k in api_keys_qs.order_by('-created_at')[:10]
    ]

    # Communication state
    communication_state = {
        'email_configured': bool(email_settings.smtp_host),
        'biometric_configured': bool(biometric_settings.device_ip or biometric_settings.endpoint),
        'notification_digest': getattr(notification_settings, 'digest_frequency', ''),
    }

    # Compliance state
    upcoming_holidays = list(
        CompanyHoliday.objects.filter(company=company, date__gte=today)
        .order_by('date')
        .values('name', 'date')[:5]
    )
    compliance_state = {
        'attendance': {},
        'upcoming_holidays': upcoming_holidays,
    }

    # Integrations
    integrations = []
    try:
        from blu_staff.apps.accounts.integration_models import Integration as IntegrationDefinition, CompanyIntegration as IntegrationConnection
        for defn in IntegrationDefinition.objects.filter(is_active=True):
            conn = IntegrationConnection.objects.filter(company=company, integration=defn).first()
            integrations.append({
                'name': defn.name,
                'description': defn.description,
                'icon': getattr(defn, 'icon', ''),
                'enabled': conn.is_active if conn else False,
                'status': 'Connected' if (conn and conn.is_active) else 'Not connected',
                'cta': 'Configure' if (conn and conn.is_active) else 'Connect',
                'cta_action': f'configure-{defn.slug}' if hasattr(defn, 'slug') else f'configure-{defn.id}',
            })
    except Exception:
        pass

    # Dashboard cards
    cards = {
        'administrative_tools': [
            {'icon': 'U', 'title': 'User Management', 'description': 'Manage users, roles and permissions.', 'url': _safe_reverse('user_management')},
            {'icon': 'S', 'title': 'Security', 'description': 'Password policies and access controls.', 'url': '#security'},
        ],
        'hr_management': [
            {'icon': 'E', 'title': 'Employee Directory', 'description': 'View and manage all employees.', 'url': _safe_reverse('employee_list')},
            {'icon': 'P', 'title': 'Payroll', 'description': 'Salary processing and payslips.', 'url': _safe_reverse('payroll_dashboard')},
        ],
        'blusuite_administration': [
            {'icon': 'B', 'title': 'Billing', 'description': 'Subscription and payment management.', 'url': _safe_reverse('blu_billing_home')},
            {'icon': 'I', 'title': 'Integrations', 'description': 'Third-party connections and APIs.', 'url': _safe_reverse('blu_integrations_home')},
        ],
        'employee_configuration': {
            'statistics': {
                'total_departments': departments_qs.count(),
                'total_positions': positions_qs.count(),
                'total_pay_grades': pay_grades_qs.count(),
            },
            'departments': list(departments_qs.values('id', 'name')),
            'positions': list(positions_qs.values('id', 'name', 'department__name')),
            'pay_grades': list(pay_grades_qs.values('id', 'name')),
            'position_by_department': list(
                positions_qs.values('department__name')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
        },
        'integrations': {
            'available': [
                {
                    'name': i['name'],
                    'description': i['description'],
                    'icon': i.get('icon', ''),
                    'status': i['status'],
                    'cta': i['cta'],
                    'cta_action': i.get('cta_action', ''),
                }
                for i in integrations
            ],
        },
    }

    support_requests = []
    activity_log = []

    try:
        from blu_staff.apps.requests.models import EmployeeRequest
    except ImportError:
        EmployeeRequest = None

    if EmployeeRequest is not None:
        try:
            support_qs = EmployeeRequest.objects.select_related('request_type', 'employee')
            if tenant is not None:
                support_qs = support_qs.filter(tenant=tenant)
            else:
                support_qs = support_qs.filter(employee__company=company)
            support_qs = support_qs.filter(
                employee__role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
            ).order_by('-request_date')[:6]

            support_requests = [
                {
                    'title': request.title,
                    'module': request.request_type.name if request.request_type else 'Request',
                    'submitted_by': request.employee.get_full_name(),
                    'status': request.get_status_display(),
                    'submitted_at': request.request_date,
                    'priority': request.get_priority_display(),
                    'url': _safe_reverse('employee_request_detail', request.id),
                }
                for request in support_qs
            ]
        except DatabaseError:
            support_requests = []
        except Exception:
            support_requests = []

    if tenant:
        for invite in TenantUserRole.objects.filter(tenant=tenant).select_related('user', 'invited_by').order_by('-invited_at')[:5]:
            activity_log.append({
                'label': 'User invitation' if invite.accepted_at is None else 'Role update',
                'primary': invite.user.get_full_name(),
                'secondary': f"Role: {invite.get_role_display()}" + (f" · Invited by {invite.invited_by.get_full_name()}" if invite.invited_by else ''),
                'timestamp': invite.accepted_at or invite.invited_at,
            })

    try:
        document_logs = DocumentAccessLog.objects.filter(
            document__employee__company=company
        ).select_related('document', 'user').order_by('-accessed_at')[:5]
        for log in document_logs:
            activity_log.append({
                'label': 'Document activity',
                'primary': log.document.title if log.document else 'Document',
                'secondary': f"{log.user.get_full_name() if log.user else 'System'} · {log.action}",
                'timestamp': log.accessed_at,
            })
    except DatabaseError:
        pass
    except Exception:
        pass

    if EmployeeRequest is not None:
        try:
            recent_requests = EmployeeRequest.objects.select_related('employee', 'request_type')
            if tenant is not None:
                recent_requests = recent_requests.filter(tenant=tenant)
            else:
                recent_requests = recent_requests.filter(employee__company=company)
            for req in recent_requests.order_by('-updated_at')[:5]:
                activity_log.append({
                    'label': 'Request update',
                    'primary': req.title,
                    'secondary': f"{req.get_status_display()} · {req.employee.get_full_name()}",
                    'timestamp': req.updated_at,
                })
        except DatabaseError:
            pass
        except Exception:
            pass

    activity_log = [item for item in activity_log if item['timestamp']]
    activity_log.sort(key=lambda item: item['timestamp'], reverse=True)
    activity_log = activity_log[:10]

    plan_name = ''
    plan_expires_at = None
    plan_is_trial = False
    plan_trial_ends = None

    if tenant:
        plan_name = tenant.plan_name or plan_name
        plan_expires_at = tenant.plan_expires_at or plan_expires_at
        plan_is_trial = tenant.is_trial and (tenant.trial_ends_at is None or tenant.trial_ends_at >= timezone.now())
        plan_trial_ends = tenant.trial_ends_at or plan_trial_ends

    if company.subscription_plan:
        plan_name = plan_name or company.subscription_plan
    if company.license_expiry:
        plan_expires_at = plan_expires_at or company.license_expiry
    if company.is_trial:
        plan_is_trial = True
    if company.trial_ends_at:
        plan_trial_ends = plan_trial_ends or company.trial_ends_at

    orientation_value = getattr(company, 'payslip_orientation', '') or 'portrait'
    logo_position_value = getattr(company, 'payslip_logo_position', '') or 'top-left'
    accent_color_value = getattr(company, 'payslip_accent_color', '') or '#2563eb'

    payslip_state = {
        'orientation': orientation_label,
        'layout': layout_key.replace('_', ' ').title(),
        'header_style': header_style_key.replace('_', ' ').title(),
        'logo_position': logo_position_value.replace('-', ' ').title(),
        'stamp_position': stamp_position_key.replace('-', ' ').title(),
        'accent_color': accent_color_value,
        'manage_url': _safe_reverse('payslip_designer'),
        'designer': {
            'config': payslip_config_payload,
            'config_json': config_json,
            'available_sections': available_sections,
            'position_options': position_options,
        },
    }

    blu_settings_url = _safe_reverse('blu_settings_home')

    return {
        'company_id': company.id,
        'company_name': company.name,
        'plan': {
            'name': plan_name,
            'expires_at': plan_expires_at,
            'is_trial': plan_is_trial,
            'trial_ends_at': plan_trial_ends,
        },
        'tenant': {
            'name': tenant.name if tenant else None,
            'owner': tenant_owner,
        } if tenant else None,
        'domains': tenant_domains,
        'profile_edit_url': f"{blu_settings_url}#company-profile" if blu_settings_url != '#' else '#company-profile',
        'statistics': {
            'total_users': total_users,
            'active_users': active_users,
            'pending_invites': pending_invites,
            'role_breakdown': role_counts,
            'active_modules': active_modules,
            'api_keys_active': api_keys_qs.count(),
        },
        'branding': branding,
        'employee_id_preview': config.generate_employee_id(),
        'module_access': module_access,
        'communication': communication_state,
        'compliance': compliance_state,
        'integrations': integrations,
        'api_keys': api_keys,
        'api_key_manage_url': f"{blu_settings_url}#api-keys" if blu_settings_url != '#' else '#api-keys',
        'support_requests': support_requests,
        'activity_log': activity_log,
        'holidays_total': CompanyHoliday.objects.filter(company=company).count(),
        'integrations_connected': sum(1 for integration in integrations if integration['enabled']),
        'payslip': payslip_state,
        'module_toggles': module_toggles,
        'company_users_list': company_users_list,
        'branches': list(CompanyBranch.objects.filter(company=company).order_by('-is_head_office', 'name')),
        'forms': {
            **forms_payload,
            'employee_configuration': {
                'employee_id': {
                    'form': employee_id_form,
                    'action': _safe_reverse('blu_settings_home'),
                    'action_key': 'employee_id',
                },
                'department': {
                    'form': department_form,
                    'action': _safe_reverse('blu_settings_home'),
                    'action_key': 'department',
                },
                'position': {
                    'form': position_form,
                    'action': _safe_reverse('blu_settings_home'),
                    'action_key': 'position',
                },
                'pay_grade': {
                    'form': pay_grade_form,
                    'action': _safe_reverse('blu_settings_home'),
                    'action_key': 'pay_grade',
                },
            },
            'payslip': {
                'form': None,
                'action': _safe_reverse('blu_settings_home'),
                'action_key': 'payslip_design',
            },
        },
        'employee_config_lists': {
            'departments': [
                {
                    'id': department.id,
                    'name': department.name,
                }
                for department in departments_qs
            ],
            'positions': [
                {
                    'id': position.id,
                    'name': position.name,
                    'department': position.department.name if position.department else '',
                    'department_id': position.department.id if position.department else '',
                }
                for position in positions_qs
            ],
            'pay_grades': list(pay_grades_qs.values('id', 'name', 'description')),
            'employee_id_preview': config.generate_employee_id(),
        },
        'integration_cards': cards['integrations']['available'],
        'payslip_designer': payslip_state['designer'],
        'security': _parse_security_settings(company.security_settings or {}),
    }


def _collect_staff_suite_overview(user):
    # ... (rest of the code remains the same)
    today = timezone.now().date()
    company = _get_user_company(user)
    if not company:
        return {
            'tenant_name': '',
            'role': getattr(user, 'role', '').upper(),
            'total_employees': 0,
            'active_employees': 0,
            'attendance': {
                'present': 0,
                'late': 0,
                'absent': 0,
                'rate': 0,
            },
            'pending': {
                'leaves': 0,
                'requests': 0,
                'documents': 0,
            },
            'upcoming': {
                'leaves': [],
                'expiring_contracts': [],
                'anniversaries': [],
            },
            'recent_documents': [],
            'pending_requests': [],
            'team_activity': [],
        }

    tenant = getattr(company, 'tenant', None)

    def _scoped(queryset):
        if tenant is not None and hasattr(queryset.model, 'tenant_id'):
            return queryset.filter(tenant=tenant)
        return queryset

    employees_qs = User.objects.filter(company=company, role='EMPLOYEE').select_related('employee_profile')

    total_employees = employees_qs.count()
    active_employees = employees_qs.filter(is_active=True).count()

    attendance_qs = _scoped(Attendance.objects.all())
    leaves_qs = _scoped(LeaveRequest.objects.select_related('employee'))
    documents_qs = _scoped(EmployeeDocument.objects.select_related('employee', 'category'))
    # PERFORMANCE MODULE DISABLED
    # reviews_qs = _scoped(PerformanceReview.objects.select_related('employee', 'reviewer'))
    reviews_qs = []

    if tenant is None:
        attendance_qs = attendance_qs.filter(employee__company=company)
        leaves_qs = leaves_qs.filter(employee__company=company)
        documents_qs = documents_qs.filter(employee__company=company)
        reviews_qs = reviews_qs.filter(employee__company=company)

    today_attendance = attendance_qs.filter(date=today)
    present_today = today_attendance.filter(status=Attendance.Status.PRESENT).count()
    late_today = today_attendance.filter(status=Attendance.Status.LATE).count()
    absent_today = max(total_employees - (present_today + late_today), 0)
    attendance_rate = round((present_today / total_employees * 100) if total_employees else 0, 1)

    pending_leaves = leaves_qs.filter(status=LeaveRequest.Status.PENDING).count()
    upcoming_leaves = [
        {
            'employee': leave.employee.get_full_name(),
            'start_date': leave.start_date,
            'end_date': leave.end_date,
            'status': leave.get_status_display(),
        }
        for leave in leaves_qs.filter(
            status=LeaveRequest.Status.APPROVED,
            start_date__gte=today
        ).order_by('start_date')[:5]
    ]

    from blu_staff.apps.requests.models import EmployeeRequest

    requests_qs = _scoped(EmployeeRequest.objects.select_related('employee', 'request_type'))
    if tenant is None:
        requests_qs = requests_qs.filter(employee__company=company)

    pending_requests = requests_qs.filter(status=EmployeeRequest.Status.PENDING)
    pending_requests_count = pending_requests.count()
    pending_requests_preview = [
        {
            'number': req.request_number,
            'title': req.title,
            'employee': req.employee.get_full_name(),
            'type': req.request_type.name,
            'submitted': req.request_date,
        }
        for req in pending_requests.order_by('-request_date')[:5]
    ]

    pending_documents = documents_qs.filter(status=EmployeeDocument.Status.PENDING).count()
    recent_documents = [
        {
            'title': doc.title,
            'employee': doc.employee.get_full_name(),
            'category': getattr(doc.category, 'name', 'Document'),
            'uploaded_at': doc.created_at,
        }
        for doc in documents_qs.order_by('-created_at')[:5]
    ]

    today_plus_90 = today + timedelta(days=90)
    expiring_contracts = []
    anniversaries = []
    for employee in employees_qs[:200]:  # limit to avoid heavy loops
        profile = getattr(employee, 'employee_profile', None)
        if not profile:
            continue

        employment_type = getattr(profile, 'employment_type', '')
        contract_end = None
        if employment_type == 'CONTRACT' and profile.contract_end_date:
            contract_end = profile.contract_end_date
        elif employment_type == 'PROBATION' and profile.probation_end_date:
            contract_end = profile.probation_end_date
        elif employment_type == 'TEMPORARY' and profile.temporary_end_date:
            contract_end = profile.temporary_end_date

        if contract_end and today <= contract_end <= today_plus_90:
            expiring_contracts.append({
                'employee': employee.get_full_name(),
                'type': employment_type.title() or 'Contract',
                'end_date': contract_end,
                'days_remaining': (contract_end - today).days,
            })

        hire_date = getattr(profile, 'date_hired', None)
        if hire_date and hire_date.month == today.month:
            years = today.year - hire_date.year
            if years > 0:
                anniversaries.append({
                    'employee': employee.get_full_name(),
                    'date': date(today.year, hire_date.month, hire_date.day),
                    'years': years,
                })

    expiring_contracts.sort(key=lambda item: item['days_remaining'])
    anniversaries.sort(key=lambda item: item['date'])

    recent_reviews = [
        {
            'employee': review.employee.get_full_name() if review.employee else 'Employee',
            'reviewer': review.reviewer.get_full_name() if review.reviewer else 'Reviewer',
            'created_at': review.created_at,
            'summary': getattr(review, 'summary', '')[:120],
        }
        for review in reviews_qs.order_by('-created_at')[:5]
    ]

    team_activity = []
    for leave in upcoming_leaves:
        team_activity.append({
            'label': 'Upcoming leave',
            'primary': leave['employee'],
            'secondary': f"{leave['start_date']} → {leave['end_date']}",
            'timestamp': leave['start_date'],
        })
    for doc in recent_documents:
        team_activity.append({
            'label': 'Document upload',
            'primary': doc['title'],
            'secondary': f"{doc['employee']} · {doc['category']}",
            'timestamp': doc['uploaded_at'],
        })
    for review in recent_reviews:
        team_activity.append({
            'label': 'Performance review',
            'primary': review['employee'],
            'secondary': f"Reviewer: {review['reviewer']}",
            'timestamp': review['created_at'],
        })

    team_activity.sort(key=lambda item: item['timestamp'], reverse=True)

    return {
        'tenant_name': getattr(company, 'name', ''),
        'role': getattr(user, 'role', '').upper(),
        'total_employees': total_employees,
        'active_employees': active_employees,
        'attendance': {
            'present': present_today,
            'late': late_today,
            'absent': absent_today,
            'rate': attendance_rate,
        },
        'pending': {
            'leaves': pending_leaves,
            'requests': pending_requests_count,
            'documents': pending_documents,
        },
        'upcoming': {
            'leaves': upcoming_leaves,
            'expiring_contracts': expiring_contracts[:5],
            'anniversaries': anniversaries[:5],
        },
        'recent_documents': recent_documents,
        'pending_requests': pending_requests_preview,
        'team_activity': team_activity[:8],
    }

    profile, created = EmployeeProfile.objects.get_or_create(user=employee, defaults=defaults)

    if created and config:
        try:
            config.increment()
        except Exception:
            pass

    return profile, created

User = get_user_model()


def landing_page(request):
    """Main landing page for Eicomtech EMS"""
    return render(request, 'ems/landing.html')


def about_page(request):
    """About page"""
    return render(request, 'ems/about.html')


def features_page(request):
    """Features page"""
    return render(request, 'ems/features.html')


def feature_attendance_page(request):
    """Smart Attendance feature detail page"""
    context = {
        'feature_slug': 'attendance',
        'feature_name': 'Smart Attendance',
        'feature_image': 'https://images.unsplash.com/photo-1521737711867-e3b97375f902?w=1920&q=80',
        'feature_tagline': 'Track every clock-in, every day — automatically.',
        'feature_description': 'Real-time attendance tracking with biometric integration, GPS verification, and automated reporting. Know who is present, late, or absent without lifting a finger.',
        'highlights': [
            {'icon': 'clock', 'title': 'Real-Time Tracking', 'desc': 'Live dashboards showing who is in, out, or on break at any moment.'},
            {'icon': 'map-pin', 'title': 'GPS Verification', 'desc': 'Confirm employees are physically at the work site before clocking in.'},
            {'icon': 'fingerprint', 'title': 'Biometric Integration', 'desc': 'Sync with fingerprint and face recognition devices seamlessly.'},
            {'icon': 'bell', 'title': 'Automated Alerts', 'desc': 'Instant notifications for late arrivals, early departures, and absences.'},
            {'icon': 'file-text', 'title': 'Automated Reports', 'desc': 'Daily, weekly and monthly attendance reports generated automatically.'},
            {'icon': 'settings', 'title': 'Flexible Shifts', 'desc': 'Configure multiple shift schedules, overtime rules, and break policies.'},
        ],
        'how_it_works': [
            {'step': '1', 'title': 'Set Up Shifts', 'desc': 'Define your work schedules, shift patterns, and overtime rules.'},
            {'step': '2', 'title': 'Employees Clock In', 'desc': 'Staff clock in via mobile app, biometric device, or web portal.'},
            {'step': '3', 'title': 'Monitor Live', 'desc': 'Watch real-time attendance status on your dashboard.'},
            {'step': '4', 'title': 'Review Reports', 'desc': 'Get automated summaries and export reports for payroll.'},
        ],
        'other_features': [
            {'name': 'Leave Management', 'url': '/features/leave/'},
            {'name': 'Payroll Processing', 'url': '/features/payroll/'},
            {'name': 'Advanced Analytics', 'url': '/features/analytics/'},
        ],
    }
    return render(request, 'ems/feature_detail.html', context)


def feature_leave_page(request):
    """Leave Management feature detail page"""
    context = {
        'feature_slug': 'leave',
        'feature_name': 'Leave Management',
        'feature_image': 'https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=1920&q=80',
        'feature_tagline': 'Make time off effortless for everyone.',
        'feature_description': 'Streamlined leave requests, automated multi-level approvals, and intelligent balance tracking. Employees apply in seconds, managers approve with one click.',
        'highlights': [
            {'icon': 'send', 'title': 'Easy Requests', 'desc': 'Employees submit leave requests from mobile or desktop in under 30 seconds.'},
            {'icon': 'check-circle', 'title': 'Auto Approvals', 'desc': 'Set rules for automatic approval of routine leave types with policy thresholds.'},
            {'icon': 'layers', 'title': 'Multi-Level Workflow', 'desc': 'Route approvals through HR, manager, and department heads as needed.'},
            {'icon': 'bar-chart-2', 'title': 'Balance Tracking', 'desc': 'Real-time leave balances per employee with accrual and carry-over rules.'},
            {'icon': 'calendar', 'title': 'Leave Calendar', 'desc': 'Team calendar showing who is away so managers can plan coverage.'},
            {'icon': 'clipboard', 'title': 'Leave Policies', 'desc': 'Configure annual, sick, maternity, and custom leave types per company policy.'},
        ],
        'how_it_works': [
            {'step': '1', 'title': 'Configure Leave Types', 'desc': 'Set up annual, sick, emergency, and custom leave types with rules.'},
            {'step': '2', 'title': 'Employee Applies', 'desc': 'Staff submit requests with dates, reason, and supporting documents.'},
            {'step': '3', 'title': 'Approval Flow', 'desc': 'Request routes through configured approvers with email notifications.'},
            {'step': '4', 'title': 'Balances Update', 'desc': 'Leave balances auto-update on approval and integrate with payroll.'},
        ],
        'other_features': [
            {'name': 'Smart Attendance', 'url': '/features/attendance/'},
            {'name': 'Payroll Processing', 'url': '/features/payroll/'},
            {'name': 'Document Management', 'url': '/features/documents/'},
        ],
    }
    return render(request, 'ems/feature_detail.html', context)


def feature_payroll_page(request):
    """Payroll Processing feature detail page"""
    context = {
        'feature_slug': 'payroll',
        'feature_name': 'Payroll Processing',
        'feature_image': 'https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1920&q=80',
        'feature_tagline': 'Pay your team accurately, every time.',
        'feature_description': 'Automated payroll calculations, tax compliance, and instant payslip generation. Eliminate manual errors and ensure your team is paid correctly and on time.',
        'highlights': [
            {'icon': 'cpu', 'title': 'Auto Calculations', 'desc': 'Gross pay, deductions, taxes, and net pay calculated automatically every cycle.'},
            {'icon': 'shield', 'title': 'Tax Compliance', 'desc': 'Built-in tax tables and PAYE calculations keep you legally compliant.'},
            {'icon': 'file', 'title': 'Instant Payslips', 'desc': 'Professional PDF payslips generated and emailed to employees automatically.'},
            {'icon': 'link', 'title': 'Attendance Integration', 'desc': 'Automatically imports attendance data to calculate overtime and deductions.'},
            {'icon': 'dollar-sign', 'title': 'Multiple Pay Structures', 'desc': 'Support for hourly, salaried, commission, and custom pay structures.'},
            {'icon': 'download', 'title': 'Bank Export', 'desc': 'Export payment files in formats compatible with all major banks.'},
        ],
        'how_it_works': [
            {'step': '1', 'title': 'Configure Pay Structure', 'desc': 'Set up salary bands, allowances, deductions, and tax brackets.'},
            {'step': '2', 'title': 'Import Attendance', 'desc': 'Attendance and leave data flows in automatically for each pay period.'},
            {'step': '3', 'title': 'Review & Approve', 'desc': 'Review the payroll run, make adjustments, and approve for payment.'},
            {'step': '4', 'title': 'Distribute Payslips', 'desc': 'Payslips are emailed and bank files exported for payment processing.'},
        ],
        'other_features': [
            {'name': 'Smart Attendance', 'url': '/features/attendance/'},
            {'name': 'Leave Management', 'url': '/features/leave/'},
            {'name': 'Advanced Analytics', 'url': '/features/analytics/'},
        ],
    }
    return render(request, 'ems/feature_detail.html', context)


def feature_performance_page(request):
    """Performance Reviews feature detail page"""
    context = {
        'feature_slug': 'performance',
        'feature_name': 'Performance Reviews',
        'feature_image': 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=1920&q=80',
        'feature_tagline': 'Develop your team with data-driven insights.',
        'feature_description': 'Structured performance evaluations, goal tracking, and 360° feedback systems. Build a culture of continuous improvement with clear, objective assessments.',
        'highlights': [
            {'icon': 'target', 'title': 'Goal Setting', 'desc': 'Set SMART goals for individuals, teams, and departments with deadlines.'},
            {'icon': 'users', 'title': '360° Feedback', 'desc': 'Collect feedback from peers, managers, subordinates, and self-assessments.'},
            {'icon': 'star', 'title': 'Rating Scales', 'desc': 'Customizable rating frameworks including numeric, descriptive, and OKR-based.'},
            {'icon': 'trending-up', 'title': 'Progress Tracking', 'desc': 'Monitor goal progress throughout the review cycle with visual indicators.'},
            {'icon': 'award', 'title': 'Review Cycles', 'desc': 'Configure annual, bi-annual, or quarterly review cycles per department.'},
            {'icon': 'book-open', 'title': 'Development Plans', 'desc': 'Create individual development plans with training recommendations.'},
        ],
        'how_it_works': [
            {'step': '1', 'title': 'Define Criteria', 'desc': 'Set up performance criteria, KPIs, and rating scales for each role.'},
            {'step': '2', 'title': 'Collect Feedback', 'desc': 'Gather multi-source feedback during the review window.'},
            {'step': '3', 'title': 'Manager Review', 'desc': 'Managers consolidate feedback and complete the formal evaluation.'},
            {'step': '4', 'title': 'Action Plans', 'desc': 'Create development plans and set goals for the next review cycle.'},
        ],
        'other_features': [
            {'name': 'Document Management', 'url': '/features/documents/'},
            {'name': 'Advanced Analytics', 'url': '/features/analytics/'},
            {'name': 'Leave Management', 'url': '/features/leave/'},
        ],
    }
    return render(request, 'ems/feature_detail.html', context)


def feature_documents_page(request):
    """Document Management feature detail page"""
    context = {
        'feature_slug': 'documents',
        'feature_name': 'Document Management',
        'feature_image': 'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=1920&q=80',
        'feature_tagline': 'Every document, organised and accessible.',
        'feature_description': 'Secure document storage, version control, and instant access for all employee records. Keep your organisation compliant and audit-ready at all times.',
        'highlights': [
            {'icon': 'folder', 'title': 'Organised Storage', 'desc': 'Structured folders by employee, document type, and department.'},
            {'icon': 'git-branch', 'title': 'Version Control', 'desc': 'Track all document versions with full history and rollback capability.'},
            {'icon': 'lock', 'title': 'Access Control', 'desc': 'Role-based permissions ensure sensitive documents stay confidential.'},
            {'icon': 'bell', 'title': 'Expiry Alerts', 'desc': 'Automatic reminders for expiring contracts, licences, and certifications.'},
            {'icon': 'search', 'title': 'Instant Search', 'desc': 'Find any document in seconds with full-text search across all files.'},
            {'icon': 'check-square', 'title': 'Compliance Ready', 'desc': 'Audit trails and access logs for every document action.'},
        ],
        'how_it_works': [
            {'step': '1', 'title': 'Upload Documents', 'desc': 'Upload employee documents — contracts, IDs, certificates — in any format.'},
            {'step': '2', 'title': 'Organise & Tag', 'desc': 'Assign categories, expiry dates, and access permissions automatically.'},
            {'step': '3', 'title': 'Review & Approve', 'desc': 'HR reviews and approves submitted documents with comments.'},
            {'step': '4', 'title': 'Stay Compliant', 'desc': 'Get alerts before documents expire and maintain full audit trails.'},
        ],
        'other_features': [
            {'name': 'Smart Attendance', 'url': '/features/attendance/'},
            {'name': 'Performance Reviews', 'url': '/features/performance/'},
            {'name': 'Payroll Processing', 'url': '/features/payroll/'},
        ],
    }
    return render(request, 'ems/feature_detail.html', context)


def feature_analytics_page(request):
    """Advanced Analytics feature detail page"""
    context = {
        'feature_slug': 'analytics',
        'feature_name': 'Advanced Analytics',
        'feature_image': 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1920&q=80',
        'feature_tagline': 'Make decisions backed by real data.',
        'feature_description': 'Real-time HR insights, custom reports, and predictive analytics across attendance, payroll, performance, and more. Turn raw data into strategic decisions.',
        'highlights': [
            {'icon': 'activity', 'title': 'Live Dashboards', 'desc': 'Real-time metrics across all HR modules in one unified view.'},
            {'icon': 'pie-chart', 'title': 'Custom Reports', 'desc': 'Build any report using drag-and-drop report builder with export to Excel/PDF.'},
            {'icon': 'trending-up', 'title': 'Trend Analysis', 'desc': 'Spot patterns in attendance, turnover, and performance over time.'},
            {'icon': 'zap', 'title': 'Predictive Insights', 'desc': 'AI-powered predictions for attrition risk, leave patterns, and budget forecasts.'},
            {'icon': 'share-2', 'title': 'Scheduled Reports', 'desc': 'Auto-send reports to stakeholders on a daily, weekly, or monthly schedule.'},
            {'icon': 'filter', 'title': 'Deep Filtering', 'desc': 'Slice data by department, branch, role, date range, and custom dimensions.'},
        ],
        'how_it_works': [
            {'step': '1', 'title': 'Data Flows In', 'desc': 'All modules feed data automatically — no manual imports needed.'},
            {'step': '2', 'title': 'Choose Your View', 'desc': 'Select from pre-built dashboards or build custom ones from scratch.'},
            {'step': '3', 'title': 'Analyse & Filter', 'desc': 'Drill down into any metric with powerful filtering and comparison tools.'},
            {'step': '4', 'title': 'Share & Act', 'desc': 'Export, share, or schedule reports and act on the insights immediately.'},
        ],
        'other_features': [
            {'name': 'Smart Attendance', 'url': '/features/attendance/'},
            {'name': 'Payroll Processing', 'url': '/features/payroll/'},
            {'name': 'Performance Reviews', 'url': '/features/performance/'},
        ],
    }
    return render(request, 'ems/feature_detail.html', context)


def solutions_page(request):
    """Solutions page"""
    return render(request, 'ems/solutions.html')


def pricing_page(request):
    """Pricing page"""
    return render(request, 'ems/pricing.html')


def help_center_page(request):
    """Help Center page"""
    return render(request, 'ems/help_center.html')


def contact_page(request):
    """Contact Us page"""
    return render(request, 'ems/contact.html')


def status_page(request):
    """System Status page"""
    return render(request, 'ems/status.html')


def documentation_page(request):
    """Documentation page"""
    return render(request, 'ems/documentation.html')


def careers_page(request):
    """Careers page"""
    return render(request, 'ems/careers.html')


def blog_page(request):
    """Blog page"""
    return render(request, 'ems/blog.html')


def press_page(request):
    """Press page"""
    return render(request, 'ems/press.html')


def _get_user_company(user):
    company = getattr(user, 'company', None)
    if company:
        return company

    employer_profile = getattr(user, 'employer_profile', None)
    if employer_profile and getattr(employer_profile, 'company', None):
        company = employer_profile.company
        if company and getattr(user, 'company_id', None) is None:
            user.company = company
            user.save(update_fields=['company'])
        return company

    try:
        return Company.objects.filter(users=user).first()
    except Exception:
        return None


def _has_hr_access(user):
    """Check if user has HR or Admin access"""
    # Check if user has admin role
    if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or user.is_employer_admin:
        return True
    
    # Check if user is an employee with HR role
    if hasattr(user, 'employee_profile') and user.employee_profile:
        if user.employee_profile.employee_role == 'HR':
            return True
    
    return False


def _has_payroll_access(user):
    """
    Check if user has payroll/finance access
    Payroll is sensitive financial data - restrict to finance team only
    """
    # Admins and employer admins always have full access
    if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return True

    # Superadmin/System owner always has access
    if user.role == 'SUPERADMIN' or getattr(user, 'is_superadmin', False):
        return True

    # Check if user is an accountant (Finance team)
    if hasattr(user, 'employee_profile') and user.employee_profile:
        if user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS']:
            return True

    return False


def _safe_reverse(name, *args, **kwargs):
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return '#'


def _blusuite_nav_flags(user):
    """Return navigation flags for BluSuite sidebar based on user role and plan"""
    role = (getattr(user, 'role', '') or '').upper()
    is_admin = role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']
    has_hr = _has_hr_access(user)

    # Get company for plan context
    company = _get_user_company(user)
    plan_ctx = get_plan_context(company) if company else get_plan_context(None)

    nav = {
        'show_staff_suite': True,
        'show_projects_suite': is_admin,
        'show_assets_suite': is_admin or has_hr,
        'show_analytics_suite': is_admin and plan_ctx.get('has_advanced_analytics', False),
        'show_integrations_suite': is_admin and plan_ctx.get('has_custom_integrations', False),
        'show_company_settings': is_admin,
        'show_company_billing': is_admin,
        'show_company_support': True,
        # Plan-gated nav items within Staff Suite
        'show_attendance': plan_ctx.get('has_attendance_basic', True),
        'show_leave': plan_ctx.get('has_leave_management', True),
        'show_payroll': plan_ctx.get('has_payroll_basic', True),
        'show_performance': plan_ctx.get('has_performance_reviews', False),
        'show_documents': plan_ctx.get('has_document_management', False),
        'show_reports': plan_ctx.get('has_custom_reports', False),
    }
    # Merge full plan context so templates can use any has_* flag
    nav.update(plan_ctx)
    return nav


def _get_employer_nav_context(user):
    """Get navigation context for employer/admin views to ensure consistent sidebar"""
    nav_flags = _blusuite_nav_flags(user)
    return {
        'show_attendance': nav_flags.get('show_attendance', True),
        'show_leave': nav_flags.get('show_leave', True),
        'show_documents': nav_flags.get('show_documents', True),
        'show_performance': nav_flags.get('show_performance', False),
        'show_payroll': nav_flags.get('show_payroll', True),
        'show_reports': nav_flags.get('show_reports', True),
        'show_analytics_suite': nav_flags.get('show_analytics_suite', False),
    }


def _collect_blu_suite_overview(user, modules_count):
    """Collect comprehensive system metrics and data for Control Center"""
    from django.contrib.auth import get_user_model
    from django.db.models import Count, Sum, Q
    from datetime import date, timedelta
    
    User = get_user_model()
    company = _get_user_company(user)
    tenant_name = getattr(company, 'name', '') if company else ''
    role = (getattr(user, 'role', '') or '').upper()
    tenant = getattr(company, 'tenant', None) if company else None
    
    # Company-scoped metrics (each employer sees only their own data)
    if company:
        system_metrics = {
            'total_users': User.objects.filter(company=company, is_active=True).count(),
            'active_today': User.objects.filter(company=company, last_login__date=date.today()).count(),
            'new_this_week': User.objects.filter(company=company, date_joined__gte=date.today() - timedelta(days=7)).count(),
            'total_companies': 1,  # Current company only
        }
    else:
        system_metrics = {
            'total_users': 0,
            'active_today': 0,
            'new_this_week': 0,
            'total_companies': 0,
        }
    
    # total_companies already set above (1 for current company, or 0 if no company)
    
    # Module-specific metrics
    module_stats = {}
    
    # Staff Suite metrics
    try:
        from blu_staff.apps.accounts.models import EmployeeProfile
        from blu_staff.apps.attendance.models import Attendance, LeaveRequest
        
        if company:
            employees = EmployeeProfile.objects.filter(company=company, user__is_active=True)
            module_stats['staff'] = {
                'total_employees': employees.count(),
                'present_today': Attendance.objects.filter(
                    employee__company=company,
                    date=date.today(),
                    status='PRESENT'
                ).count(),
                'on_leave': LeaveRequest.objects.filter(
                    employee__company=company,
                    status='APPROVED',
                    start_date__lte=date.today(),
                    end_date__gte=date.today()
                ).count(),
                'pending_requests': LeaveRequest.objects.filter(
                    employee__company=company,
                    status='PENDING'
                ).count(),
            }
    except Exception:
        module_stats['staff'] = {'total_employees': 0, 'present_today': 0, 'on_leave': 0, 'pending_requests': 0}
    
    # Projects Suite metrics
    try:
        from blu_projects.models import Project
        
        if company:
            projects = Project.objects.filter(company=company)
            module_stats['projects'] = {
                'total_projects': projects.count(),
                'active_projects': projects.filter(status='ACTIVE').count(),
                'completed_projects': projects.filter(status='COMPLETED').count(),
                'overdue_projects': projects.filter(
                    status__in=['ACTIVE', 'PLANNING'],
                    end_date__lt=date.today()
                ).count(),
            }
    except Exception:
        module_stats['projects'] = {'total_projects': 0, 'active_projects': 0, 'completed_projects': 0, 'overdue_projects': 0}
    
    # Assets Suite metrics
    try:
        from blu_assets.models import EmployeeAsset
        
        assets = EmployeeAsset.objects.filter(tenant=tenant) if tenant else EmployeeAsset.objects.none()
        if not assets.exists() and company:
            assets = EmployeeAsset.objects.filter(
                Q(department__company=company) | Q(employee__company=company)
            )
        module_stats['assets'] = {
            'total_assets': assets.count(),
            'assigned_assets': assets.filter(status='ASSIGNED').count(),
            'available_assets': assets.filter(status='AVAILABLE').count(),
            'in_repair': assets.filter(status='IN_REPAIR').count(),
        }
    except Exception:
        module_stats['assets'] = {'total_assets': 0, 'assigned_assets': 0, 'available_assets': 0, 'in_repair': 0}
    
    # Recent cross-module activity
    recent_updates = []
    
    # Recent employee activities
    try:
        from blu_staff.apps.accounts.models import EmployeeProfile
        recent_employees = EmployeeProfile.objects.filter(
            company=company,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).select_related('user').order_by('-created_at')[:3]
        
        for emp in recent_employees:
            recent_updates.append({
                'label': 'Staff Suite',
                'primary': f'New employee: {emp.user.get_full_name()}',
                'secondary': f'{emp.position or "Staff"} · {emp.department or "General"}',
                'timestamp': emp.created_at,
                'icon': 'users'
            })
    except Exception:
        pass
    
    # Recent project activities
    try:
        from blu_projects.models import Project
        recent_projects = Project.objects.filter(
            company=company,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')[:3]
        
        for proj in recent_projects:
            recent_updates.append({
                'label': 'Projects Suite',
                'primary': f'New project: {proj.name}',
                'secondary': f'{proj.get_status_display()} · {proj.get_priority_display()} priority',
                'timestamp': proj.created_at,
                'icon': 'grid'
            })
    except Exception:
        pass
    
    # Recent asset activities
    try:
        from blu_assets.models import EmployeeAsset
        recent_assets = EmployeeAsset.objects.filter(
            tenant=tenant,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).select_related('employee').order_by('-created_at')[:3]
        
        for asset in recent_assets:
            emp_name = asset.employee.get_full_name() if asset.employee else 'Unassigned'
            recent_updates.append({
                'label': 'Assets Suite',
                'primary': f'Asset {asset.asset_tag} added',
                'secondary': f'{asset.get_asset_type_display()} · {emp_name}',
                'timestamp': asset.created_at,
                'icon': 'package'
            })
    except Exception:
        pass
    
    # Sort by timestamp
    recent_updates.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_updates = recent_updates[:10]
    
    # Module status
    modules = []
    if user.has_perm('frontend.view_blu_staff_home') or role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
        modules.append({
            'name': 'Staff (EMS)',
            'status': 'Operational',
            'owners': ['HR Admins'],
            'last_update': timezone.now() - timedelta(hours=2),
            'health': 'healthy'
        })
    if role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
        modules.extend([
            {
                'name': 'Projects (PMS)',
                'status': 'Operational',
                'owners': ['Project Managers'],
                'last_update': timezone.now() - timedelta(hours=5),
                'health': 'healthy'
            },
            {
                'name': 'Assets (AMS)',
                'status': 'Operational',
                'owners': ['Asset Managers'],
                'last_update': timezone.now() - timedelta(hours=1),
                'health': 'healthy'
            },
            {
                'name': 'Analytics Studio',
                'status': 'Operational',
                'owners': ['Data Team'],
                'last_update': timezone.now() - timedelta(hours=12),
                'health': 'healthy'
            },
            {
                'name': 'Integrations Hub',
                'status': 'Operational',
                'owners': ['Integration Team'],
                'last_update': timezone.now() - timedelta(days=1),
                'health': 'healthy'
            },
        ])
    
    # System notices (populated from DB when a SystemNotice model exists)
    upcoming_notices = []
    
    # Module requests
    from blu_staff.apps.requests.models import EmployeeRequest
    
    def _scoped(queryset):
        if tenant is not None and hasattr(queryset.model, 'tenant_id'):
            return queryset.filter(tenant=tenant)
        return queryset
    
    module_requests = []
    if role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
        try:
            requests_qs = _scoped(EmployeeRequest.objects.select_related('employee', 'request_type'))
            if tenant is None and company is not None:
                requests_qs = requests_qs.filter(employee__company=company)
            
            module_requests = [
                {
                    'title': req.title,
                    'module': req.request_type.name,
                    'submitted_by': req.employee.get_full_name(),
                    'submitted_at': req.request_date,
                    'status': req.get_status_display(),
            }
            for req in requests_qs.order_by('-request_date')[:6]
        ]
        except Exception:
            pass

    return {
        'tenant_name': tenant_name,
        'role': role,
        'accessible_modules': modules_count,
        'system_metrics': system_metrics,
        'module_stats': module_stats,
        'modules': modules,
        'upcoming_notices': upcoming_notices,
        'module_requests': module_requests,
        'recent_updates': recent_updates,
    }


from django.views.decorators.csrf import csrf_protect

from .auth_views import finalize_login_session

@csrf_protect

def dashboard_redirect(request):
    """Redirect users to appropriate dashboard based on their model type and role"""
    user = request.user

    # Platform-owner role routing
    platform_role = getattr(user, 'platform_role', None)
    if platform_role:
        platform_redirects = {
            'OWNER': 'owner_billing_portal',
            'BILLING': 'owner_billing_portal',
            'SUPPORT': 'owner_support_portal',
            'REGISTRATION': 'owner_registration_portal',
            'ACCOUNT_MANAGER': 'owner_account_manager_portal',
        }
        dest = platform_redirects.get(platform_role)
        if dest:
            return redirect(dest)

    # Check if user is SuperAdmin (from unified User model)
    if hasattr(user, 'is_superadmin') and user.is_superadmin:
        return redirect('superadmin_dashboard')

    # Check if user is regular User (from User model)
    if hasattr(user, 'role'):
        role = user.role.upper() if user.role else None

        # For EMPLOYEE role, check employee_role (HR, Accountant, Supervisor)
        if role == 'EMPLOYEE':
            if hasattr(user, 'employee_profile') and user.employee_profile:
                employee_role = user.employee_profile.employee_role
                
                # Route to specific dashboard based on employee_role
                if employee_role == 'HR':
                    return redirect('hr_dashboard')
                elif employee_role == 'ACCOUNTANT':
                    return redirect('accountant_dashboard')
                elif employee_role == 'SUPERVISOR':
                    return redirect('supervisor_dashboard')
            
            # Regular employee (no special role)
            return redirect('employee_dashboard')
        
        # Admin/Employer roles
        role_redirects = {
            'SUPERADMIN': 'superadmin_dashboard',
            'ADMINISTRATOR': 'employer_dashboard',
            'EMPLOYER_ADMIN': 'employer_dashboard',
        }

        redirect_view = role_redirects.get(role)
        if redirect_view:
            return redirect(redirect_view)

    # Default fallback
    messages.error(request, 'User role not defined. Please contact administrator.')
    return redirect('/')


@login_required
def blu_suite_home(request):
    """Unified entry point for tenant modules."""
    user = request.user
    nav_flags = _blusuite_nav_flags(user)

    modules_config = [
        {
            'title': 'Staff Suite (EMS)',
            'description': 'Operate HR, payroll and workforce journeys in one place.',
            'icon': '''
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"></path>
                    <circle cx="9" cy="7" r="4"></circle>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                </svg>
            ''',
            'color': '#2563eb',
            'url_name': 'blu_staff_home',
            'visible': nav_flags['show_staff_suite'],
        },
        {
            'title': 'Projects Suite (PMS)',
            'description': 'Plan workstreams, assign tasks and keep milestones on track.',
            'icon': '''
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 3h7v7H3z"></path>
                    <path d="M14 3h7v7h-7z"></path>
                    <path d="M14 14h7v7h-7z"></path>
                    <path d="M3 14h7v7H3z"></path>
                </svg>
            ''',
            'color': '#f97316',
            'url_name': 'blu_projects_home',
            'visible': nav_flags['show_projects_suite'],
        },
        {
            'title': 'Assets Suite (AMS)',
            'description': 'Control asset registers, lifecycle tracking and assignments.',
            'icon': '''
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.73z"></path>
                    <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                </svg>
            ''',
            'color': '#22c55e',
            'url_name': 'blu_assets_home',
            'visible': nav_flags['show_assets_suite'],
        },
        {
            'title': 'Analytics Studio',
            'description': 'Explore KPIs, custom dashboards and advanced reporting.',
            'icon': '''
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 20V10"></path>
                    <path d="M12 20V4"></path>
                    <path d="M6 20v-6"></path>
                    <path d="M3 20h18"></path>
                </svg>
            ''',
            'color': '#9333ea',
            'url_name': 'blu_analytics_home',
            'visible': nav_flags['show_analytics_suite'],
        },
        {
            'title': 'E-Forms & Signatures',
            'description': 'Design digital forms, collect submissions and manage e-signatures.',
            'icon': '''
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                </svg>
            ''',
            'color': '#E11D48',
            'url_name': 'eforms_list',
            'visible': True,
        },
        {
            'title': 'Integrations Hub',
            'description': 'Connect ERP, payroll, identity and communication platforms.',
            'icon': '''
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                    <polyline points="15 3 21 3 21 9"></polyline>
                    <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
            ''',
            'color': '#0f172a',
            'url_name': 'blu_integrations_home',
            'visible': nav_flags['show_integrations_suite'],
        },
    ]

    modules = [
        {
            'title': module['title'],
            'description': module['description'],
            'icon_html': module['icon'],
            'color': module['color'],
            'bg_color': f"{module['color']}1A" if module['color'].startswith('#') else module['color'],
            'url': _safe_reverse(module['url_name']),
        }
        for module in modules_config
        if module['visible']
    ]

    overview = _collect_blu_suite_overview(user, len(modules))

    return render(
        request,
        'ems/blusuite_home.html',
        {
            'modules': modules,
            'home_url': reverse('blu_suite_home'),
            'overview': overview,
            **nav_flags,
        },
    )


@login_required
def blu_staff_home(request):
    """Staff Suite overview/landing page - shows module data before entering"""
    nav_flags = _blusuite_nav_flags(request.user)
    user = request.user
    company = getattr(user, 'company', None)
    
    if not company:
        company = getattr(getattr(user, 'employer_profile', None), 'company', None)
    if not company:
        company = getattr(getattr(user, 'employee_profile', None), 'company', None)
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('blu_suite_home')
    
    # Import here to avoid circular imports
    from blu_staff.apps.accounts.models import EmployeeProfile
    from blu_staff.apps.attendance.models import Attendance, LeaveRequest
    from datetime import date, timedelta
    
    total_employees = EmployeeProfile.objects.filter(company=company, user__is_active=True).count()
    present_today = Attendance.objects.filter(
        employee__company=company,
        date=date.today(),
        status='PRESENT'
    ).count()
    on_leave = LeaveRequest.objects.filter(
        employee__company=company,
        status='APPROVED',
        start_date__lte=date.today(),
        end_date__gte=date.today()
    ).count()
    pending_requests = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).count()
    
    stats = {
        'total_employees': total_employees,
        'present_today': present_today,
        'on_leave': on_leave,
        'pending_requests': pending_requests,
    }
    
    # Get recent activities (last 10 activities from the past week)
    recent_activities = []
    try:
        # Recent leave requests
        recent_leaves = LeaveRequest.objects.filter(
            employee__company=company,
            created_at__gte=date.today() - timedelta(days=7)
        ).order_by('-created_at')[:5]
        
        for leave in recent_leaves:
            recent_activities.append({
                'description': f"{leave.employee.user.get_full_name()} requested {leave.leave_type} leave",
                'timestamp': leave.created_at
            })
        
        # Recent employee additions
        recent_employees = EmployeeProfile.objects.filter(
            company=company,
            user__date_joined__gte=date.today() - timedelta(days=7)
        ).order_by('-user__date_joined')[:5]
        
        for emp in recent_employees:
            recent_activities.append({
                'description': f"New employee {emp.user.get_full_name()} joined",
                'timestamp': emp.user.date_joined
            })
        
        # Sort by timestamp
        recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_activities = recent_activities[:10]
    except Exception as e:
        pass
    
    context = {
        'stats': stats,
        'recent_activities': recent_activities,
        **nav_flags,
    }

    return render(request, 'ems/blusuite_staff.html', context)


@login_required
def blu_projects_home(request):
    """Projects Suite overview/landing page - shows module data before entering"""
    nav_flags = _blusuite_nav_flags(request.user)
    user = request.user
    company = getattr(user, 'company', None)
    
    if not company:
        company = getattr(getattr(user, 'employer_profile', None), 'company', None)
    if not company:
        company = getattr(getattr(user, 'employee_profile', None), 'company', None)
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('blu_suite_home')
    
    # Import here to avoid circular imports
    from blu_projects.models import Project, Task, ProjectActivity
    from django.db.models import Count, Q
    from datetime import date, timedelta
    
    # Gather comprehensive overview stats
    total_projects = Project.objects.filter(company=company).count()
    active_projects_count = Project.objects.filter(company=company, status='ACTIVE').count()
    completed_projects = Project.objects.filter(company=company, status='COMPLETED').count()
    on_hold = Project.objects.filter(company=company, status='ON_HOLD').count()
    planning = Project.objects.filter(company=company, status='PLANNING').count()
    
    total_tasks = Task.objects.filter(project__company=company).count()
    completed_tasks = Task.objects.filter(project__company=company, status='COMPLETED').count()
    
    # Calculate completion rate
    completion_rate = 0
    if total_projects > 0:
        completion_rate = int((completed_projects / total_projects) * 100)
    
    # Team members working on projects
    team_members = User.objects.filter(company=company, is_active=True).count()
    
    # Get active projects for display
    active_projects_list = Project.objects.filter(
        company=company, 
        status='ACTIVE'
    ).select_related('project_manager').prefetch_related('team_members').order_by('-created_at')[:6]
    
    # Stats for display
    stats = {
        'total_projects': total_projects,
        'active_projects': active_projects_count,
        'completion_rate': completion_rate,
        'team_members': team_members,
        'planning_count': planning,
        'active_count': active_projects_count,
        'on_hold_count': on_hold,
        'completed_count': completed_projects,
    }
    
    # Get recent activities
    recent_activities = []
    try:
        # Recent project activities
        recent_project_activities = ProjectActivity.objects.filter(
            project__company=company,
            created_at__gte=date.today() - timedelta(days=7)
        ).select_related('project', 'user').order_by('-created_at')[:10]
        
        for activity in recent_project_activities:
            recent_activities.append({
                'description': f"{activity.user.get_full_name() if activity.user else 'System'} {activity.get_action_display().lower()} {activity.project.name}",
                'timestamp': activity.created_at
            })
        
        # Recent project creations
        recent_projects = Project.objects.filter(
            company=company,
            created_at__gte=date.today() - timedelta(days=7)
        ).order_by('-created_at')[:5]
        
        for project in recent_projects:
            recent_activities.append({
                'description': f"New project '{project.name}' created",
                'timestamp': project.created_at
            })
        
        # Sort by timestamp
        recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_activities = recent_activities[:10]
    except Exception as e:
        pass
    
    context = {
        'stats': stats,
        'active_projects': active_projects_list,
        'recent_activities': recent_activities,
        **nav_flags,
    }
    
    return render(request, 'ems/blusuite_projects.html', context)


@login_required
def blu_assets_home(request):
    """AMS Suite overview page in BluSuite hub - shows stats, modules, and launch button"""
    nav_flags = _blusuite_nav_flags(request.user)
    user = request.user
    company = getattr(user, 'company', None)

    if not company:
        company = getattr(getattr(user, 'employer_profile', None), 'company', None)
    if not company:
        company = getattr(getattr(user, 'employee_profile', None), 'company', None)

    if not company:
        messages.error(request, "You must be associated with a company to access AMS.")
        return redirect('blu_suite_home')

    from blu_assets.models import EmployeeAsset, AssetRequest
    from django.db.models import Count, Sum, Q
    from datetime import date, timedelta

    # Get all assets scoped to company
    tenant = getattr(company, 'tenant', None)
    if tenant:
        all_assets = EmployeeAsset.objects.filter(tenant=tenant)
        if not all_assets.exists():
            all_assets = EmployeeAsset.objects.filter(
                Q(department__company=company) | Q(employee__company=company)
            )
    else:
        all_assets = EmployeeAsset.objects.filter(
            Q(department__company=company) | Q(employee__company=company)
        )

    # Stats
    stats = {
        'total_assets': all_assets.count(),
        'assigned': all_assets.filter(status='ASSIGNED').count(),
        'available': all_assets.filter(status='AVAILABLE').count(),
        'in_repair': all_assets.filter(status='IN_REPAIR').count(),
        'total_value': all_assets.aggregate(val=Sum('purchase_price'))['val'] or 0,
    }

    # Pending requests
    req_qs = AssetRequest.objects.filter(department__company=company) if company else AssetRequest.objects.none()
    stats['pending_requests'] = req_qs.filter(status='PENDING').count()

    # Recent activity
    recent_activities = []
    try:
        recent = all_assets.filter(
            assigned_date__gte=date.today() - timedelta(days=14)
        ).select_related('employee').order_by('-assigned_date')[:8]
        for asset in recent:
            if asset.employee:
                recent_activities.append({
                    'description': f"{asset.asset_tag} assigned to {asset.employee.get_full_name()}",
                    'timestamp': asset.assigned_date,
                })
        created = all_assets.filter(
            created_at__gte=date.today() - timedelta(days=14)
        ).order_by('-created_at')[:5]
        for asset in created:
            recent_activities.append({
                'description': f"New {asset.get_asset_type_display()}: {asset.asset_tag}",
                'timestamp': asset.created_at,
            })
        recent_activities.sort(key=lambda x: str(x['timestamp']), reverse=True)
        recent_activities = recent_activities[:8]
    except Exception:
        pass

    # Type breakdown
    type_breakdown = all_assets.values('asset_type').annotate(count=Count('id')).order_by('-count')[:6]
    asset_types_display = dict(EmployeeAsset.AssetType.choices)

    context = {
        'stats': stats,
        'recent_activities': recent_activities,
        'type_breakdown': type_breakdown,
        'asset_types_display': asset_types_display,
        **nav_flags,
    }
    return render(request, 'ems/blusuite_assets.html', context)


@login_required
@require_feature(FEAT_ADVANCED_ANALYTICS)
def blu_analytics_home(request):
    """Analytics Studio with comprehensive metrics and insights"""
    nav_flags = _blusuite_nav_flags(request.user)
    user = request.user
    company = getattr(user, 'company', None)
    
    if not company:
        company = getattr(getattr(user, 'employer_profile', None), 'company', None)
    if not company:
        company = getattr(getattr(user, 'employee_profile', None), 'company', None)
    
    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('blu_suite_home')
    
    from django.db.models import Count, Avg
    from datetime import date, timedelta
    
    # Calculate key metrics
    total_employees = User.objects.filter(company=company, is_active=True).count()
    
    # Employee growth
    last_month = date.today() - timedelta(days=30)
    new_employees = User.objects.filter(company=company, date_joined__gte=last_month).count()
    employee_growth = int((new_employees / total_employees * 100)) if total_employees > 0 else 0
    
    # Attendance rate
    attendance_rate = 0
    attendance_change = 0
    try:
        from blu_staff.apps.attendance.models import Attendance
        total_days = 30
        present_days = Attendance.objects.filter(
            employee__company=company,
            date__gte=last_month,
            status='PRESENT'
        ).count()
        expected_days = total_employees * total_days
        attendance_rate = int((present_days / expected_days * 100)) if expected_days > 0 else 0
        # Calculate trend vs previous month
        two_months_ago = date.today() - timedelta(days=60)
        prev_present = Attendance.objects.filter(
            employee__company=company,
            date__gte=two_months_ago,
            date__lt=last_month,
            status='PRESENT'
        ).count()
        prev_rate = int((prev_present / expected_days * 100)) if expected_days > 0 else 0
        attendance_change = attendance_rate - prev_rate
    except Exception:
        pass
    
    # Projects data
    active_projects = 0
    total_projects = 0
    try:
        from blu_projects.models import Project
        active_projects = Project.objects.filter(company=company, status='ACTIVE').count()
        total_projects = Project.objects.filter(company=company).count()
    except Exception:
        pass
    
    # Payroll cost from actual payroll records
    payroll_cost = 0
    try:
        from blu_staff.apps.payroll.models import Payroll
        from django.db.models import Sum
        payroll_cost = Payroll.objects.filter(
            employee__company=company,
            pay_period_start__gte=last_month,
        ).aggregate(total=Sum('net_salary'))['total'] or 0
    except Exception:
        pass
    
    metrics = {
        'total_employees': total_employees,
        'employee_growth': employee_growth,
        'attendance_rate': attendance_rate,
        'attendance_change': attendance_change,
        'active_projects': active_projects,
        'total_projects': total_projects,
        'payroll_cost': payroll_cost,
    }
    
    # Recent payroll runs as reports
    recent_reports = []
    try:
        from blu_staff.apps.payroll.models import Payroll
        recent_payrolls = Payroll.objects.filter(
            employee__company=company,
        ).order_by('-created_at').values('pay_period_start', 'pay_period_end', 'created_at').distinct()[:5]
        for p in recent_payrolls:
            recent_reports.append({
                'title': f"Payroll: {p['pay_period_start'].strftime('%b %d')} - {p['pay_period_end'].strftime('%b %d, %Y')}",
                'date': p['created_at'],
            })
    except Exception:
        pass
    
    context = {
        'metrics': metrics,
        'recent_reports': recent_reports,
        **nav_flags,
    }

    return render(request, 'ems/blusuite_analytics.html', context)


@login_required
@require_feature(FEAT_CUSTOM_INTEGRATIONS)
def blu_integrations_home(request):
    """Integrations Hub with marketplace and active connections"""
    from blu_staff.apps.accounts.integration_models import Integration, CompanyIntegration, IntegrationLog

    nav_flags = _blusuite_nav_flags(request.user)
    user = request.user
    company = _get_user_company(user)

    if not company:
        messages.error(request, 'Company not assigned.')
        return redirect('blu_suite_home')

    # Handle POST actions (connect, disconnect, configure, test)
    if request.method == 'POST':
        action = request.POST.get('action', '')
        integration_id = request.POST.get('integration_id')

        if action == 'connect' and integration_id:
            try:
                integration = Integration.objects.get(id=integration_id, is_available=True)
                ci, created = CompanyIntegration.objects.get_or_create(
                    company=company, integration=integration,
                    defaults={'connected_by': user, 'status': 'PENDING'}
                )
                config = ci.config_json or {}

                # Save all config_* POST fields into config_json
                for key, val in request.POST.items():
                    if key.startswith('config_'):
                        config[key[7:]] = val.strip()

                # Save API credentials
                api_key = request.POST.get('api_key', '').strip()
                api_secret = request.POST.get('api_secret', '').strip()
                client_id = request.POST.get('client_id', '').strip()
                client_secret = request.POST.get('client_secret', '').strip()

                if api_key:
                    ci.api_key = api_key
                if api_secret:
                    ci.api_secret = api_secret
                if client_id:
                    config['client_id'] = client_id
                if client_secret:
                    config['client_secret'] = client_secret

                # Validate minimum required fields per integration type
                itype = integration.integration_type
                iname = integration.name
                valid = True
                if itype == 'SLACK':
                    if not (client_id and client_secret and config.get('bot_token')):
                        messages.error(request, 'Slack requires Client ID, Client Secret, and Bot Token.')
                        valid = False
                elif itype in ('MICROSOFT_TEAMS',) or iname == 'Microsoft 365':
                    if not (client_id and client_secret and config.get('tenant_id')):
                        messages.error(request, f'{iname} requires Client ID, Client Secret, and Tenant ID.')
                        valid = False
                elif itype == 'ZOOM':
                    if not (client_id and client_secret and config.get('account_id')):
                        messages.error(request, 'Zoom requires Client ID, Client Secret, and Account ID.')
                        valid = False
                elif iname == 'QuickBooks':
                    if not (client_id and client_secret and config.get('realm_id')):
                        messages.error(request, 'QuickBooks requires Client ID, Client Secret, and Realm ID.')
                        valid = False
                elif iname == 'Okta':
                    if not (api_key and config.get('okta_domain')):
                        messages.error(request, 'Okta requires Domain and API Token.')
                        valid = False
                elif iname == 'SMS Gateway (Twilio)':
                    if not (api_key and api_secret and config.get('from_number')):
                        messages.error(request, 'Twilio requires Account SID, Auth Token, and From Number.')
                        valid = False
                elif iname == 'SendGrid':
                    if not (api_key and config.get('from_email')):
                        messages.error(request, 'SendGrid requires API Key and From Email.')
                        valid = False
                elif iname == 'WhatsApp Business':
                    if not (api_key and config.get('phone_number_id') and config.get('waba_id')):
                        messages.error(request, 'WhatsApp requires Access Token, Phone Number ID, and Business Account ID.')
                        valid = False
                elif iname == 'Sage':
                    if not (api_key and config.get('company_id')):
                        messages.error(request, 'Sage requires API Key and Company ID.')
                        valid = False
                elif integration.requires_oauth:
                    if not (client_id and client_secret):
                        messages.error(request, f'{iname} requires Client ID and Client Secret.')
                        valid = False
                else:
                    if not api_key:
                        messages.error(request, f'{iname} requires an API Key.')
                        valid = False

                if valid:
                    ci.config_json = config
                    ci.status = 'ACTIVE'
                    ci.connected_at = timezone.now()
                    ci.connected_by = user
                    ci.save()
                    IntegrationLog.objects.create(
                        company_integration=ci, action='CONNECTED',
                        description=f'Connected by {user.get_full_name()}',
                        success=True, ip_address=request.META.get('REMOTE_ADDR'),
                    )
                    messages.success(request, f'{integration.name} connected successfully!')
                elif created:
                    ci.delete()  # Clean up if validation failed on first connect

            except Integration.DoesNotExist:
                messages.error(request, 'Integration not found.')
            return redirect('blu_integrations_home')

        elif action == 'disconnect' and integration_id:
            try:
                ci = CompanyIntegration.objects.get(company=company, integration_id=integration_id)
                name = ci.integration.name
                IntegrationLog.objects.create(
                    company_integration=ci, action='DISCONNECTED',
                    description=f'Disconnected by {user.get_full_name()}',
                    success=True, ip_address=request.META.get('REMOTE_ADDR'),
                )
                ci.delete()
                messages.success(request, f'{name} disconnected.')
            except CompanyIntegration.DoesNotExist:
                messages.error(request, 'Integration connection not found.')
            return redirect('blu_integrations_home')

        elif action == 'configure' and integration_id:
            try:
                ci = CompanyIntegration.objects.get(company=company, integration_id=integration_id)
                config = ci.config_json or {}
                # Save all config_* POST fields
                for key, val in request.POST.items():
                    if key.startswith('config_'):
                        config[key[7:]] = val.strip()
                ci.config_json = config
                ci.webhook_url = request.POST.get('webhook_url', ci.webhook_url)
                ci.save(update_fields=['config_json', 'webhook_url', 'updated_at'])
                messages.success(request, f'{ci.integration.name} configuration updated.')
            except CompanyIntegration.DoesNotExist:
                messages.error(request, 'Integration connection not found.')
            return redirect('blu_integrations_home')

        elif action == 'test' and integration_id:
            try:
                import requests as http_requests
                ci = CompanyIntegration.objects.get(company=company, integration_id=integration_id)
                config = ci.config_json or {}
                iname = ci.integration.name
                itype = ci.integration.integration_type
                test_ok = False
                test_detail = ''

                try:
                    if itype == 'SLACK':
                        token = config.get('bot_token', '')
                        if token:
                            r = http_requests.post('https://slack.com/api/auth.test',
                                headers={'Authorization': f'Bearer {token}'}, timeout=10)
                            data = r.json()
                            test_ok = data.get('ok', False)
                            test_detail = data.get('team', '') if test_ok else data.get('error', 'Unknown error')
                        else:
                            test_detail = 'No bot token configured'

                    elif itype == 'ZOOM':
                        cid = config.get('client_id', '')
                        csec = config.get('client_secret', '')
                        aid = config.get('account_id', '')
                        if cid and csec and aid:
                            r = http_requests.post('https://zoom.us/oauth/token',
                                params={'grant_type': 'account_credentials', 'account_id': aid},
                                auth=(cid, csec), timeout=10)
                            test_ok = 'access_token' in r.json()
                            test_detail = 'Token obtained' if test_ok else r.json().get('reason', 'Auth failed')
                        else:
                            test_detail = 'Missing Client ID, Secret, or Account ID'

                    elif iname == 'SMS Gateway (Twilio)':
                        sid = ci.api_key or ''
                        token = ci.api_secret or ''
                        if sid and token:
                            r = http_requests.get(f'https://api.twilio.com/2010-04-01/Accounts/{sid}.json',
                                auth=(sid, token), timeout=10)
                            test_ok = r.status_code == 200
                            test_detail = f"Account: {r.json().get('friendly_name', 'OK')}" if test_ok else f'HTTP {r.status_code}'
                        else:
                            test_detail = 'Missing Account SID or Auth Token'

                    elif iname == 'SendGrid':
                        key = ci.api_key or ''
                        if key:
                            r = http_requests.get('https://api.sendgrid.com/v3/user/profile',
                                headers={'Authorization': f'Bearer {key}'}, timeout=10)
                            test_ok = r.status_code == 200
                            test_detail = 'API key valid' if test_ok else f'HTTP {r.status_code}'
                        else:
                            test_detail = 'No API key configured'

                    elif iname == 'WhatsApp Business':
                        token = ci.api_key or ''
                        waba = config.get('waba_id', '')
                        if token and waba:
                            r = http_requests.get(f'https://graph.facebook.com/v18.0/{waba}',
                                headers={'Authorization': f'Bearer {token}'}, timeout=10)
                            test_ok = r.status_code == 200
                            test_detail = 'Connected' if test_ok else r.json().get('error', {}).get('message', f'HTTP {r.status_code}')
                        else:
                            test_detail = 'Missing Access Token or Business Account ID'

                    elif iname == 'Okta':
                        domain = config.get('okta_domain', '').rstrip('/')
                        token = ci.api_key or ''
                        if domain and token:
                            r = http_requests.get(f'{domain}/api/v1/org',
                                headers={'Authorization': f'SSWS {token}'}, timeout=10)
                            test_ok = r.status_code == 200
                            test_detail = f"Org: {r.json().get('name', 'OK')}" if test_ok else f'HTTP {r.status_code}'
                        else:
                            test_detail = 'Missing Okta Domain or API Token'

                    elif itype in ('MICROSOFT_TEAMS',) or iname == 'Microsoft 365':
                        cid = config.get('client_id', '')
                        csec = config.get('client_secret', '')
                        tid = config.get('tenant_id', '')
                        if cid and csec and tid:
                            r = http_requests.post(f'https://login.microsoftonline.com/{tid}/oauth2/v2.0/token',
                                data={'grant_type': 'client_credentials', 'client_id': cid,
                                      'client_secret': csec, 'scope': 'https://graph.microsoft.com/.default'},
                                timeout=10)
                            test_ok = 'access_token' in r.json()
                            test_detail = 'Token obtained' if test_ok else r.json().get('error_description', 'Auth failed')
                        else:
                            test_detail = 'Missing Client ID, Secret, or Tenant ID'

                    elif iname in ('QuickBooks', 'Xero', 'Sage'):
                        # For accounting, just verify credentials are stored
                        has_creds = bool(config.get('client_id') or ci.api_key)
                        test_ok = has_creds
                        test_detail = 'Credentials configured' if has_creds else 'No credentials found'

                    elif itype == 'GOOGLE_CALENDAR':
                        cid = config.get('client_id', '')
                        test_ok = bool(cid)
                        test_detail = 'OAuth credentials configured' if test_ok else 'No credentials found'

                    else:
                        test_ok = bool(ci.api_key or config.get('client_id'))
                        test_detail = 'Credentials present' if test_ok else 'No credentials'

                except http_requests.exceptions.Timeout:
                    test_detail = 'Connection timed out'
                except http_requests.exceptions.ConnectionError:
                    test_detail = 'Could not connect to API endpoint'
                except Exception as e:
                    test_detail = str(e)[:200]

                if test_ok:
                    ci.last_synced_at = timezone.now()
                    ci.reset_errors()
                    ci.save(update_fields=['last_synced_at', 'updated_at'])
                    IntegrationLog.objects.create(
                        company_integration=ci, action='SYNC',
                        description=f'Connection test passed: {test_detail}', success=True,
                        ip_address=request.META.get('REMOTE_ADDR'),
                    )
                    messages.success(request, f'{iname} test passed! {test_detail}')
                else:
                    ci.mark_error(test_detail)
                    IntegrationLog.objects.create(
                        company_integration=ci, action='SYNC',
                        description=f'Connection test failed: {test_detail}', success=False,
                        ip_address=request.META.get('REMOTE_ADDR'),
                    )
                    messages.error(request, f'{iname} test failed: {test_detail}')

            except CompanyIntegration.DoesNotExist:
                messages.error(request, 'Integration connection not found.')
            return redirect('blu_integrations_home')

    # Fetch data
    all_integrations = Integration.objects.filter(is_available=True).order_by('name')
    company_connections = {
        ci.integration_id: ci
        for ci in CompanyIntegration.objects.filter(company=company).select_related('integration')
    }

    # Build integration list with connection status
    integrations_list = []
    for integ in all_integrations:
        ci = company_connections.get(integ.id)
        integrations_list.append({
            'id': integ.id,
            'name': integ.name,
            'type': integ.get_integration_type_display(),
            'type_key': integ.integration_type,
            'description': integ.description,
            'requires_oauth': integ.requires_oauth,
            'documentation_url': integ.documentation_url,
            'connected': ci is not None and ci.status == 'ACTIVE',
            'status': ci.status if ci else None,
            'connection': ci,
            'connected_at': ci.connected_at if ci else None,
            'last_synced_at': ci.last_synced_at if ci else None,
            'last_error': ci.last_error if ci else '',
            'config': ci.config_json if ci else {},
            'webhook_url': ci.webhook_url if ci else '',
        })

    active_count = sum(1 for i in integrations_list if i['connected'])
    error_count = sum(1 for i in integrations_list if i['status'] == 'ERROR')

    # Recent logs
    recent_logs = IntegrationLog.objects.filter(
        company_integration__company=company
    ).select_related('company_integration__integration').order_by('-created_at')[:20]

    # Category grouping
    categories = {}
    for integ in integrations_list:
        cat = integ['type']
        categories.setdefault(cat, []).append(integ)

    context = {
        'integrations': integrations_list,
        'categories': categories,
        'recent_logs': recent_logs,
        'active_count': active_count,
        'error_count': error_count,
        'total_count': len(integrations_list),
        'company': company,
        **nav_flags,
    }

    return render(request, 'ems/blusuite_integrations.html', context)


@login_required
def blu_settings_home(request):
    """Company Settings with comprehensive configuration options"""
    nav_flags = _blusuite_nav_flags(request.user)
    user = request.user
    company = _get_user_company(user)

    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('blu_suite_home')

    form_overrides = {}

    if request.method == 'POST':
        redirect_response = _handle_blu_settings_post(request, company, form_overrides)
        if redirect_response is not None:
            return redirect_response

    settings_context = _collect_company_settings_context(user, nav_flags)

    context = {
        'company': company,
        'settings': settings_context,
        **nav_flags,
    }

    return render(request, 'ems/blusuite_settings.html', context)


def _handle_blu_settings_post(request, company, form_overrides):
    action = (request.POST.get('action') or '').strip()
    if not action:
        messages.error(request, 'Unrecognised settings action.')
        return redirect('blu_settings_home')

    config, _ = EmployeeIdConfiguration.objects.get_or_create(company=company)
    email_settings, _ = CompanyEmailSettings.objects.get_or_create(company=company)
    biometric_settings, _ = CompanyBiometricSettings.objects.get_or_create(company=company)
    notification_settings, _ = CompanyNotificationSettings.objects.get_or_create(company=company)

    if action == 'stamp_upload':
        if 'company_stamp' in request.FILES:
            company.company_stamp = request.FILES['company_stamp']
            company.save(update_fields=['company_stamp'])
            messages.success(request, 'Company stamp saved successfully.')
        else:
            messages.error(request, 'No stamp file received.')
        return redirect('blu_settings_home')

    if action == 'company_profile':
        form = CompanyProfileForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company profile updated successfully.')
            return redirect('blu_settings_home')
        messages.error(request, 'Please correct the errors in the company profile form.')
        form_overrides[( 'profile', )] = form
        return None

    if action == 'employee_id':
        form = EmployeeIdConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Employee ID settings updated.')
            return redirect('blu_settings_home')
        messages.error(request, 'Please correct the errors in Employee ID settings.')
        form_overrides[( 'employee_configuration', 'employee_id' )] = form
        return None

    if action == 'department':
        form = CompanyDepartmentForm(request.POST, company=company)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Department added successfully.')
                return redirect('blu_settings_home')
            except IntegrityError:
                messages.error(request, 'Department with this name already exists.')
        else:
            messages.error(request, 'Please correct the errors in the Department form.')
        form_overrides[( 'employee_configuration', 'department' )] = form
        return None

    if action == 'position':
        form = CompanyPositionForm(request.POST, company=company)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Position added successfully.')
                return redirect('blu_settings_home')
            except IntegrityError:
                messages.error(request, 'Position with this name already exists.')
        else:
            messages.error(request, 'Please correct the errors in the Position form.')
        form_overrides[( 'employee_configuration', 'position' )] = form
        return None

    if action == 'pay_grade':
        form = CompanyPayGradeForm(request.POST, company=company)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Pay grade added successfully.')
                return redirect('blu_settings_home')
            except IntegrityError:
                messages.error(request, 'Pay grade with this name already exists.')
        else:
            messages.error(request, 'Please correct the errors in the Pay grade form.')
        form_overrides[( 'employee_configuration', 'pay_grade' )] = form
        return None

    if action == 'edit_department':
        dept_id = request.POST.get('dept_id')
        try:
            department = CompanyDepartment.objects.get(id=dept_id, company=company)
            department.name = request.POST.get('name')
            department.description = request.POST.get('description', '')
            department.save()
            messages.success(request, f'Department "{department.name}" updated successfully.')
        except CompanyDepartment.DoesNotExist:
            messages.error(request, 'Department not found.')
        except Exception as e:
            messages.error(request, f'Error updating department: {str(e)}')
        return redirect('blu_settings_home')

    if action == 'edit_position':
        pos_id = request.POST.get('pos_id')
        try:
            position = CompanyPosition.objects.get(id=pos_id, company=company)
            position.name = request.POST.get('name')
            position.description = request.POST.get('description', '')
            dept_id = request.POST.get('department')
            if dept_id:
                position.department = CompanyDepartment.objects.get(id=dept_id, company=company)
            else:
                position.department = None
            position.save()
            messages.success(request, f'Position "{position.name}" updated successfully.')
        except CompanyPosition.DoesNotExist:
            messages.error(request, 'Position not found.')
        except Exception as e:
            messages.error(request, f'Error updating position: {str(e)}')
        return redirect('blu_settings_home')

    if action == 'edit_pay_grade':
        grade_id = request.POST.get('grade_id')
        try:
            pay_grade = CompanyPayGrade.objects.get(id=grade_id, company=company)
            pay_grade.name = request.POST.get('name')
            pay_grade.description = request.POST.get('description', '')
            pay_grade.save()
            messages.success(request, f'Pay grade "{pay_grade.name}" updated successfully.')
        except CompanyPayGrade.DoesNotExist:
            messages.error(request, 'Pay grade not found.')
        except Exception as e:
            messages.error(request, f'Error updating pay grade: {str(e)}')
        return redirect('blu_settings_home')

    if action == 'email_smtp':
        form = CompanyEmailSettingsForm(request.POST, instance=email_settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Email settings updated successfully.')
            return redirect('blu_settings_home')
        messages.error(request, 'Please review the email settings form for errors.')
        form_overrides[( 'email', )] = form
        return None

    if action == 'biometric':
        form = CompanyBiometricSettingsForm(request.POST, instance=biometric_settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Biometric settings updated successfully.')
            return redirect('blu_settings_home')
        messages.error(request, 'Please review the biometric settings form for errors.')
        form_overrides[( 'biometric', )] = form
        return None

    if action == 'gps_settings':
        # Handle GPS and geofencing settings
        office_location_name = request.POST.get('office_location_name', '').strip()
        office_lat = request.POST.get('office_latitude', '').strip()
        office_lon = request.POST.get('office_longitude', '').strip()
        geofence_radius = request.POST.get('geofence_radius_meters', '100').strip()
        enforce_geofencing = request.POST.get('enforce_geofencing') == 'on'
        allow_remote = request.POST.get('allow_remote_attendance') == 'on'
        require_renewal_approval = request.POST.get('require_renewal_approval') == 'on'
        
        try:
            from decimal import Decimal, InvalidOperation
            
            # Update location name
            company.office_location_name = office_location_name
            
            # Update GPS coordinates
            if office_lat:
                company.office_latitude = Decimal(office_lat)
            else:
                company.office_latitude = None
                
            if office_lon:
                company.office_longitude = Decimal(office_lon)
            else:
                company.office_longitude = None
            
            # Update geofence settings
            if geofence_radius:
                company.geofence_radius_meters = int(geofence_radius)
            
            company.enforce_geofencing = enforce_geofencing
            company.allow_remote_attendance = allow_remote
            company.require_renewal_approval = require_renewal_approval
            
            company.save()
            messages.success(request, 'Settings updated successfully.')
        except (ValueError, InvalidOperation) as e:
            messages.error(request, 'Invalid GPS coordinates. Please enter valid decimal numbers.')
        
        return redirect('blu_settings_home')
    
    if action == 'update_branch_gps':
        # Handle branch GPS coordinate updates
        branch_id = request.POST.get('branch_id')
        branch_lat = request.POST.get('branch_latitude', '').strip()
        branch_lon = request.POST.get('branch_longitude', '').strip()
        branch_radius = request.POST.get('branch_radius', '100').strip()
        
        try:
            from decimal import Decimal, InvalidOperation
            branch = CompanyBranch.objects.get(id=branch_id, company=company)
            
            if branch_lat:
                branch.latitude = Decimal(branch_lat)
            else:
                branch.latitude = None
                
            if branch_lon:
                branch.longitude = Decimal(branch_lon)
            else:
                branch.longitude = None
            
            if branch_radius:
                branch.geofence_radius_meters = int(branch_radius)
            
            branch.save()
            messages.success(request, f'GPS coordinates updated for {branch.name}.')
        except CompanyBranch.DoesNotExist:
            messages.error(request, 'Branch not found.')
        except (ValueError, InvalidOperation):
            messages.error(request, 'Invalid GPS coordinates. Please enter valid decimal numbers.')
        
        return redirect('blu_settings_home')

    if action == 'notifications':
        form = CompanyNotificationSettingsForm(request.POST, instance=notification_settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification settings updated successfully.')
            return redirect('blu_settings_home')
        messages.error(request, 'Please review the notification settings form for errors.')
        form_overrides[( 'notifications', )] = form
        return None

    if action == 'api_key':
        form = CompanyAPIKeyForm(request.POST)
        if form.is_valid():
            import secrets
            CompanyAPIKey.objects.filter(company=company, is_active=True).update(is_active=False)
            api_key = form.save(commit=False)
            api_key.company = company
            api_key.key = f"ems_api_{secrets.token_urlsafe(32)}"
            api_key.is_active = True
            api_key.save()
            messages.success(request, 'API key generated successfully!')
            return redirect('blu_settings_home')
        messages.error(request, 'Please correct the errors before generating an API key.')
        form_overrides[( 'api_keys', )] = form
        return None

    if action == 'payslip_design':
        section_order_raw = request.POST.get('section_order', '[]')
        field_positions_raw = request.POST.get('field_positions', '{}')

        try:
            company.payslip_section_order = json.loads(section_order_raw) if section_order_raw else []
        except json.JSONDecodeError:
            company.payslip_section_order = ['employee_info', 'salary_info', 'deductions', 'summary']

        try:
            company.payslip_field_positions = json.loads(field_positions_raw) if field_positions_raw else {}
        except json.JSONDecodeError:
            company.payslip_field_positions = {}

        company.payslip_orientation = request.POST.get('orientation', 'portrait')
        company.payslip_layout = request.POST.get('layout', company.payslip_layout)
        company.payslip_header_style = request.POST.get('header_style', company.payslip_header_style)
        company.payslip_logo_position = request.POST.get('logo_position', company.payslip_logo_position)
        company.payslip_stamp_position = request.POST.get('stamp_position', company.payslip_stamp_position)
        company.payslip_address_position = request.POST.get('address_position', company.payslip_address_position)

        company.payslip_header_color = request.POST.get('header_color', company.payslip_header_color)
        company.payslip_accent_color = request.POST.get('accent_color', company.payslip_accent_color)
        company.payslip_section_color = request.POST.get('section_color', company.payslip_section_color)

        company.payslip_header_content = request.POST.get('header_content', company.payslip_header_content)
        company.payslip_footer_content = request.POST.get('footer_content', company.payslip_footer_content)

        company.show_company_logo = request.POST.get('show_logo') == 'on'
        company.show_company_stamp = request.POST.get('show_stamp') == 'on'
        company.show_signature = request.POST.get('show_signature') == 'on'
        company.show_tax_breakdown = request.POST.get('show_tax_breakdown') == 'on'
        company.show_confidentiality_notice = request.POST.get('show_confidentiality_notice') == 'on'

        company.save(update_fields=[
            'payslip_section_order',
            'payslip_field_positions',
            'payslip_orientation',
            'payslip_layout',
            'payslip_header_style',
            'payslip_logo_position',
            'payslip_stamp_position',
            'payslip_address_position',
            'payslip_header_color',
            'payslip_accent_color',
            'payslip_section_color',
            'payslip_header_content',
            'payslip_footer_content',
            'show_company_logo',
            'show_company_stamp',
            'show_signature',
            'show_tax_breakdown',
            'show_confidentiality_notice',
        ])

        messages.success(request, 'Payslip design saved successfully.')
        return redirect('blu_settings_home')

    if action == 'test_smtp':
        try:
            import smtplib
            host = email_settings.smtp_host
            port = email_settings.smtp_port or 587
            if not host:
                return JsonResponse({'success': False, 'message': 'SMTP host is not configured.'})
            server = smtplib.SMTP(host, port, timeout=10)
            if email_settings.smtp_use_tls:
                server.starttls()
            username = email_settings.smtp_username
            password = email_settings.smtp_password
            if username and password:
                server.login(username, password)
            server.quit()
            return JsonResponse({'success': True, 'message': 'SMTP connection successful.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'SMTP test failed: {str(e)}'})

    if action == 'test_biometric':
        try:
            ip = biometric_settings.device_ip
            endpoint = biometric_settings.endpoint
            target = endpoint or (f'http://{ip}' if ip else '')
            if not target:
                return JsonResponse({'success': False, 'message': 'No device IP or endpoint configured.'})
            import requests as http_requests
            resp = http_requests.get(target, timeout=5)
            return JsonResponse({'success': True, 'message': f'Device reachable (HTTP {resp.status_code}).'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Device unreachable: {str(e)}'})

    # ── Security Settings ──
    if action == 'security_password_policy':
        import json as _json
        policy = {
            'min_length': int(request.POST.get('min_password_length', 8)),
            'expiry_days': int(request.POST.get('password_expiry_days', 90)),
            'require_uppercase': request.POST.get('require_uppercase') == 'on',
            'require_lowercase': request.POST.get('require_lowercase') == 'on',
            'require_number': request.POST.get('require_number') == 'on',
            'require_special': request.POST.get('require_special') == 'on',
            'prevent_reuse': request.POST.get('prevent_reuse') == 'on',
        }
        if not hasattr(company, 'security_settings') or company.security_settings is None:
            company.security_settings = {}
        company.security_settings['password_policy'] = policy
        company.save(update_fields=['security_settings'])
        messages.success(request, 'Password policy updated successfully.')
        return redirect('blu_settings_home')

    if action == 'security_session':
        import json as _json
        session_cfg = {
            'timeout_minutes': int(request.POST.get('session_timeout_minutes', 30)),
            'max_hours': int(request.POST.get('max_session_hours', 12)),
            'single_session': request.POST.get('single_session') == 'on',
            'logout_on_close': request.POST.get('logout_on_close') == 'on',
        }
        if not hasattr(company, 'security_settings') or company.security_settings is None:
            company.security_settings = {}
        company.security_settings['session'] = session_cfg
        company.save(update_fields=['security_settings'])
        messages.success(request, 'Session management settings updated successfully.')
        return redirect('blu_settings_home')

    if action == 'security_2fa':
        import json as _json
        twofa_cfg = {
            'enforcement': request.POST.get('twofa_enforcement', 'disabled'),
            'method': request.POST.get('twofa_method', 'email'),
        }
        if not hasattr(company, 'security_settings') or company.security_settings is None:
            company.security_settings = {}
        company.security_settings['twofa'] = twofa_cfg
        company.save(update_fields=['security_settings'])
        messages.success(request, 'Two-factor authentication settings updated successfully.')
        return redirect('blu_settings_home')

    if action == 'security_login_restrictions':
        import json as _json
        login_cfg = {
            'max_failed_attempts': int(request.POST.get('max_failed_attempts', 5)),
            'lockout_duration_minutes': int(request.POST.get('lockout_duration_minutes', 15)),
            'notify_admin_lockout': request.POST.get('notify_admin_lockout') == 'on',
            'log_failed_attempts': request.POST.get('log_failed_attempts') == 'on',
        }
        if not hasattr(company, 'security_settings') or company.security_settings is None:
            company.security_settings = {}
        company.security_settings['login_restrictions'] = login_cfg
        company.save(update_fields=['security_settings'])
        messages.success(request, 'Login restriction settings updated successfully.')
        return redirect('blu_settings_home')

    if action == 'module_toggles':
        from blu_staff.apps.accounts.models import CompanySettings as CS
        cs = CS.get_for_company(company)
        toggle_fields = [
            'enable_attendance', 'enable_leave', 'enable_payroll',
            'enable_performance', 'enable_training', 'enable_onboarding',
            'enable_assets', 'enable_eforms', 'enable_benefits',
            'enable_documents', 'enable_requests', 'enable_communication',
            'enable_reports',
        ]
        for field in toggle_fields:
            setattr(cs, field, request.POST.get(field) == 'on')
        cs.updated_by = request.user
        cs.save()
        messages.success(request, 'Module configuration updated successfully.')
        return redirect('blu_settings_home')

    if action == 'invite_user':
        invite_email = request.POST.get('invite_email', '').strip()
        invite_role = request.POST.get('invite_role', 'EMPLOYEE').strip()
        invite_first = request.POST.get('invite_first_name', '').strip()
        invite_last = request.POST.get('invite_last_name', '').strip()
        invite_job_title = request.POST.get('invite_job_title', '').strip() or 'Employee'
        invite_department = request.POST.get('invite_department', '').strip() or 'General'
        if not invite_email:
            messages.error(request, 'Email address is required to invite a user.')
            return redirect('blu_settings_home')
        if User.objects.filter(email=invite_email).exists():
            messages.error(request, f'A user with email {invite_email} already exists.')
            return redirect('blu_settings_home')
        import secrets
        from datetime import date as _date
        temp_password = secrets.token_urlsafe(10)
        new_user = User.objects.create_user(
            email=invite_email,
            password=temp_password,
            first_name=invite_first,
            last_name=invite_last,
            role=invite_role,
            company=company,
            must_change_password=True,
        )
        # For EMPLOYEE role: auto-provision an EmployeeProfile so they appear in EMS
        if invite_role == 'EMPLOYEE':
            from blu_staff.apps.accounts.models import EmployeeProfile
            emp_count = EmployeeProfile.objects.filter(company=company).count()
            emp_id = f"EMP-{company.id}-{emp_count + 1:03d}"
            # Ensure unique employee_id
            while EmployeeProfile.objects.filter(employee_id=emp_id).exists():
                emp_count += 1
                emp_id = f"EMP-{company.id}-{emp_count + 1:03d}"
            EmployeeProfile.objects.create(
                user=new_user,
                employee_id=emp_id,
                job_title=invite_job_title,
                department=invite_department,
                date_hired=_date.today(),
                company=company,
            )
        # Send credentials email to the invited user
        try:
            from django.core.mail import send_mail
            login_url = request.build_absolute_uri('/')
            send_mail(
                subject=f'Your {company.name} Blusuite account has been created',
                message=(
                    f'Hello {invite_first or invite_email},\n\n'
                    f'An account has been created for you on Blusuite by {request.user.get_full_name()}.\n\n'
                    f'Login URL: {login_url}\n'
                    f'Email: {invite_email}\n'
                    f'Temporary password: {temp_password}\n\n'
                    f'You will be prompted to change your password on first login.\n\n'
                    f'Company: {company.name}\n'
                    f'Role: {invite_role.replace("_", " ").title()}\n'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[invite_email],
                fail_silently=True,
            )
        except Exception:
            pass
        messages.success(request, f'User {invite_email} created with role {invite_role}. Credentials emailed.')
        return redirect('blu_settings_home')

    if action == 'change_user_role':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('new_role', '').strip()
        if user_id and new_role:
            try:
                target_user = User.objects.get(id=user_id, company=company)
                if target_user != request.user:
                    target_user.role = new_role
                    target_user.save(update_fields=['role'])
                    messages.success(request, f'Role updated for {target_user.email}.')
                else:
                    messages.error(request, 'You cannot change your own role.')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
        return redirect('blu_settings_home')

    if action == 'deactivate_user':
        user_id = request.POST.get('user_id')
        if user_id:
            try:
                target_user = User.objects.get(id=user_id, company=company)
                if target_user != request.user:
                    target_user.is_active = False
                    target_user.save(update_fields=['is_active'])
                    messages.success(request, f'User {target_user.email} has been deactivated.')
                else:
                    messages.error(request, 'You cannot deactivate your own account.')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
        return redirect('blu_settings_home')

    messages.error(request, 'Unknown settings action requested.')
    return redirect('blu_settings_home')


@login_required
def blu_billing_home(request):
    """Billing & Subscription management with plan details and history"""
    nav_flags = _blusuite_nav_flags(request.user)
    user = request.user
    company = _get_user_company(user)

    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('blu_suite_home')

    from datetime import date, timedelta
    from blu_staff.apps.accounts.models import BillingInvoice, CompanyRegistrationRequest

    # ── Currency from shared utility ──
    from ems_project.context_processors import get_company_currency
    currency = get_company_currency(company)
    rate = currency['rate']

    # ── Canonical plan pricing (USD base, converted to local currency) ──
    # Flat-rate: one price covers the full employee limit — NOT per user
    PLAN_INFO = {
        'BASIC': {
            'name': 'Starter',
            'base_price': 29.99,
            'price': round(29.99 * rate, 2),
            'employee_limit': 25,
            'description': 'Perfect for small teams getting started',
            'features': [
                'Up to 25 employees',
                'Employee database & profiles',
                'Attendance tracking',
                'Leave management',
                'Payroll processing',
                'Document management',
                'Email support',
            ],
        },
        'PROFESSIONAL': {
            'name': 'Professional',
            'base_price': 79.99,
            'price': round(79.99 * rate, 2),
            'employee_limit': 100,
            'description': 'For growing businesses with advanced HR needs',
            'features': [
                'Up to 100 employees',
                'Everything in Starter',
                'Performance reviews & goals',
                'Advanced analytics & reports',
                'Training management',
                'Benefits management',
                'Approvals & workflows',
                'Priority support',
            ],
        },
        'ENTERPRISE': {
            'name': 'Enterprise',
            'base_price': 199.99,
            'price': round(199.99 * rate, 2),
            'employee_limit': 99999,
            'description': 'For large organizations with custom requirements',
            'features': [
                'Unlimited employees',
                'Everything in Professional',
                'Asset management (AMS)',
                'E-Forms & digital signatures',
                'Custom integrations & API',
                'Dedicated account manager',
                '24/7 phone support',
                'SLA guarantee',
            ],
        },
    }

    # ── Payment gateway options ──
    PAYMENT_GATEWAYS = [
        {'key': 'card', 'name': 'Credit / Debit Card', 'icon': 'credit-card', 'description': 'Visa, Mastercard, Amex — secured by Stripe'},
        {'key': 'mobile_money', 'name': 'Mobile Money', 'icon': 'smartphone', 'description': 'MTN, Airtel, Zamtel'},
        {'key': 'bank_transfer', 'name': 'Bank Transfer', 'icon': 'building', 'description': 'Direct bank deposit or EFT'},
    ]

    # ── Handle POST actions ──
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'change_plan':
            new_plan = request.POST.get('plan', '').upper()
            if new_plan in PLAN_INFO:
                old_plan = company.subscription_plan
                company.subscription_plan = new_plan
                info = PLAN_INFO[new_plan]
                company.max_employees = info['employee_limit'] if info['employee_limit'] < 99999 else 9999
                # End trial if upgrading
                if company.is_trial and new_plan != 'BASIC':
                    company.is_trial = False
                    company.trial_ends_at = None
                company.save(update_fields=['subscription_plan', 'max_employees', 'is_trial', 'trial_ends_at'])
                # Flat-rate invoice
                BillingInvoice.objects.create(
                    company_id=company.pk,
                    date=date.today(),
                    due_date=date.today() + timedelta(days=30),
                    description=f'Plan change: {PLAN_INFO.get(old_plan, {}).get("name", old_plan)} → {info["name"]} (flat-rate {currency["symbol"]} {info["price"]}/mo)',
                    amount=info['price'],
                    status=BillingInvoice.Status.PENDING,
                )
                messages.success(request, f'Subscription changed to {info["name"]} plan.')
            else:
                messages.error(request, 'Invalid plan selected.')
            return redirect('blu_billing_home')

        elif action == 'cancel_subscription':
            reason = request.POST.get('reason', '')
            company.subscription_plan = 'BASIC'
            company.is_trial = False
            company.save(update_fields=['subscription_plan', 'is_trial'])
            BillingInvoice.objects.create(
                company_id=company.pk,
                date=date.today(),
                description=f'Subscription cancelled. Reason: {reason or "Not specified"}',
                amount=0,
                status=BillingInvoice.Status.CANCELLED,
                notes=reason,
            )
            messages.success(request, 'Subscription cancelled. You have been moved to the Starter plan.')
            return redirect('blu_billing_home')

        elif action == 'update_payment':
            pm_type = request.POST.get('payment_type', 'card')
            if not hasattr(company, 'security_settings') or company.security_settings is None:
                company.security_settings = {}
            if pm_type == 'card':
                card_last4 = request.POST.get('card_last4', '')
                card_brand = request.POST.get('card_brand', '')
                card_expiry = request.POST.get('card_expiry', '')
                company.security_settings['payment_method'] = {
                    'type': 'card',
                    'card_last4': card_last4,
                    'card_brand': card_brand,
                    'card_expiry': card_expiry,
                    'updated_at': date.today().isoformat(),
                }
                messages.success(request, 'Card payment method saved successfully.')
            elif pm_type == 'mobile_money':
                provider = request.POST.get('mobile_provider', '')
                number = request.POST.get('mobile_number', '')
                company.security_settings['payment_method'] = {
                    'type': 'mobile_money',
                    'provider': provider,
                    'mobile_number': number,
                    'updated_at': date.today().isoformat(),
                }
                messages.success(request, f'Mobile Money ({provider}) payment method saved. You will receive payment prompts on {number}.')
            elif pm_type == 'bank_transfer':
                company.security_settings['payment_method'] = {
                    'type': 'bank_transfer',
                    'confirmed': True,
                    'updated_at': date.today().isoformat(),
                }
                messages.success(request, 'Bank Transfer confirmed. Please use your license key as the payment reference. Allow 1-2 business days for verification.')
            company.save(update_fields=['security_settings'])
            return redirect('blu_billing_home')

        elif action == 'toggle_billing_cycle':
            cycle = request.POST.get('cycle', 'MONTHLY')
            if hasattr(company, 'registration_request') and company.registration_request:
                company.registration_request.billing_preference = cycle
                company.registration_request.save(update_fields=['billing_preference'])
            messages.success(request, f'Billing cycle changed to {cycle.lower()}.')
            return redirect('blu_billing_home')

    # ── Build subscription context from real model data ──
    current_plan_key = company.subscription_plan or 'BASIC'
    plan_info = PLAN_INFO.get(current_plan_key, PLAN_INFO['BASIC'])

    # Payment method from security_settings
    payment = {}
    if hasattr(company, 'security_settings') and company.security_settings:
        payment = company.security_settings.get('payment_method', {})

    # Billing cycle
    billing_pref = 'MONTHLY'
    if hasattr(company, 'registration_request') and company.registration_request:
        billing_pref = company.registration_request.billing_preference or 'MONTHLY'

    yearly_discount = 0.8  # 20% off for yearly
    price = plan_info['price']
    if billing_pref == 'YEARLY':
        price = round(plan_info['price'] * yearly_discount * 12, 2)

    # Trial info
    trial_days_left = 0
    if company.is_trial and company.trial_ends_at:
        trial_days_left = max(0, (company.trial_ends_at.date() - date.today()).days)

    # Next billing date
    next_billing = date.today() + timedelta(days=30)
    if company.license_expiry:
        next_billing = company.license_expiry

    # Count active users
    active_user_count = User.objects.filter(company_id=company.pk, is_active=True).count()
    employee_count = User.objects.filter(company_id=company.pk, role='EMPLOYEE', is_active=True).count()

    # Flat-rate pricing: one fixed price for the plan (NOT per user)
    flat_monthly = plan_info['price']
    if billing_pref == 'YEARLY':
        flat_monthly_discounted = round(flat_monthly * yearly_discount, 2)
        total_due = round(flat_monthly_discounted * 12, 2)
        billing_period_label = 'year'
    else:
        flat_monthly_discounted = flat_monthly
        total_due = flat_monthly
        billing_period_label = 'month'

    # Payment method display info
    pm_type = payment.get('type', 'card')
    pm_display = 'No payment method'
    if pm_type == 'card' and payment.get('card_last4'):
        pm_display = f"{payment.get('card_brand', 'Card')} **** {payment['card_last4']}"
    elif pm_type == 'mobile_money' and payment.get('mobile_number'):
        pm_display = f"{payment.get('provider', 'Mobile Money')} – {payment['mobile_number']}"
    elif pm_type == 'bank_transfer' and payment.get('confirmed'):
        pm_display = 'Bank Transfer (confirmed)'

    subscription = {
        'plan_key': current_plan_key,
        'plan_name': plan_info['name'],
        'flat_monthly': flat_monthly,
        'flat_monthly_discounted': flat_monthly_discounted,
        'price': total_due,
        'is_trial': company.is_trial,
        'trial_days_left': trial_days_left,
        'employee_limit': plan_info['employee_limit'] if plan_info['employee_limit'] < 99999 else 'Unlimited',
        'employee_count': employee_count,
        'active_user_count': active_user_count,
        'features': plan_info['features'],
        'next_billing_date': next_billing,
        'amount_due': total_due,
        'billing_period_label': billing_period_label,
        # Payment method
        'pm_type': pm_type,
        'pm_display': pm_display,
        'card_last4': payment.get('card_last4', ''),
        'card_brand': payment.get('card_brand', ''),
        'card_expiry': payment.get('card_expiry', ''),
        'mobile_provider': payment.get('provider', ''),
        'mobile_number': payment.get('mobile_number', ''),
        'billing_cycle': billing_pref,
        'license_key': company.license_key,
    }

    # Billing history from DB
    billing_history = BillingInvoice.objects.filter(company_id=company.pk).order_by('-date')[:50]

    # Available plans for plan picker
    plans = []
    for key, info in PLAN_INFO.items():
        plans.append({
            'key': key,
            'name': info['name'],
            'price': info['price'],
            'yearly_price': round(info['price'] * yearly_discount * 12, 2),
            'employee_limit': info['employee_limit'] if info['employee_limit'] < 99999 else 'Unlimited',
            'features': info['features'],
            'description': info.get('description', ''),
            'is_current': key == current_plan_key,
        })

    context = {
        'company': company,
        'subscription': subscription,
        'billing_history': billing_history,
        'plans': plans,
        'currency': currency,
        'payment_gateways': PAYMENT_GATEWAYS,
        **nav_flags,
    }

    return render(request, 'ems/blusuite_billing.html', context)


@login_required
def blu_invoice_pdf(request, invoice_id):
    """Generate and download a PDF invoice."""
    from blu_staff.apps.accounts.models import BillingInvoice
    from django.http import HttpResponse
    from datetime import date

    company = _get_user_company(request.user)

    if not company:
        messages.error(request, "You must be associated with a company.")
        return redirect('blu_billing_home')

    try:
        invoice = BillingInvoice.objects.get(id=invoice_id, company_id=company.pk)
    except BillingInvoice.DoesNotExist:
        messages.error(request, "Invoice not found.")
        return redirect('blu_billing_home')

    # Currency from shared utility
    from ems_project.context_processors import get_company_currency
    cur = get_company_currency(company)['symbol']

    # Build HTML invoice for PDF
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Invoice {invoice.invoice_number}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; color: #1e293b; font-size: 14px; }}
.header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; border-bottom: 3px solid #E11D48; padding-bottom: 20px; }}
.company-info h1 {{ font-size: 22px; margin: 0 0 4px; color: #E11D48; }}
.company-info p {{ margin: 2px 0; color: #64748b; font-size: 13px; }}
.invoice-meta {{ text-align: right; }}
.invoice-meta h2 {{ font-size: 28px; margin: 0 0 8px; color: #1e293b; text-transform: uppercase; letter-spacing: 2px; }}
.invoice-meta p {{ margin: 2px 0; font-size: 13px; color: #64748b; }}
.invoice-meta .inv-num {{ font-weight: 700; color: #1e293b; font-size: 15px; }}
table {{ width: 100%; border-collapse: collapse; margin: 30px 0; }}
th {{ background: #f8fafc; padding: 12px 16px; text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; border-bottom: 2px solid #e2e8f0; }}
td {{ padding: 12px 16px; border-bottom: 1px solid #f1f5f9; }}
.total-row td {{ font-weight: 700; font-size: 16px; border-top: 2px solid #1e293b; border-bottom: none; }}
.status {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
.status-PAID {{ background: #dcfce7; color: #166534; }}
.status-PENDING {{ background: #fef9c3; color: #854d0e; }}
.status-FAILED {{ background: #fee2e2; color: #991b1b; }}
.status-CANCELLED {{ background: #f1f5f9; color: #475569; }}
.status-REFUNDED {{ background: #e0e7ff; color: #3730a3; }}
.footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; color: #94a3b8; font-size: 12px; }}
.notes {{ background: #f8fafc; padding: 16px; border-radius: 4px; margin-top: 20px; }}
.notes h4 {{ margin: 0 0 8px; font-size: 13px; color: #475569; }}
.notes p {{ margin: 0; font-size: 13px; color: #64748b; }}
</style></head><body>
<div class="header">
    <div class="company-info">
        <h1>{company.name}</h1>
        <p>{company.address or ''}</p>
        <p>{company.phone or ''}</p>
        <p>{company.email or ''}</p>
        <p>{company.country or ''}</p>
    </div>
    <div class="invoice-meta">
        <h2>Invoice</h2>
        <p class="inv-num">{invoice.invoice_number}</p>
        <p>Date: {invoice.date.strftime('%B %d, %Y') if invoice.date else '-'}</p>
        <p>Due: {invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'On receipt'}</p>
        <p>Status: <span class="status status-{invoice.status}">{invoice.get_status_display()}</span></p>
    </div>
</div>
<table>
    <thead><tr><th>Description</th><th style="text-align:right;">Amount</th></tr></thead>
    <tbody>
        <tr><td>{invoice.description}</td><td style="text-align:right;">{cur} {invoice.amount:,.2f}</td></tr>
        <tr class="total-row"><td>Total</td><td style="text-align:right;">{cur} {invoice.amount:,.2f}</td></tr>
    </tbody>
</table>
{'<div class="notes"><h4>Notes</h4><p>' + invoice.notes + '</p></div>' if invoice.notes else ''}
{'<p style="margin-top:12px;font-size:13px;color:#64748b;">Payment Method: ' + invoice.payment_method + '</p>' if invoice.payment_method else ''}
{'<p style="font-size:13px;color:#64748b;">Transaction ID: ' + invoice.transaction_id + '</p>' if invoice.transaction_id else ''}
<div class="footer">
    <p>This invoice was generated by BluSuite - {company.name}</p>
    <p>For questions, contact {company.email or 'support'}</p>
</div>
</body></html>"""

    # Try to use weasyprint for real PDF, fallback to HTML download
    try:
        from weasyprint import HTML as WeasyHTML
        pdf_bytes = WeasyHTML(string=html).write_pdf()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        return response
    except ImportError:
        # Fallback: return HTML as downloadable file
        response = HttpResponse(html, content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.html"'
        return response


@login_required
def blu_support_home(request):
    """Support Center with ticketing, knowledge base, and resources"""
    from blu_support.models import SupportTicket, KnowledgeArticle
    from blu_support.forms import SupportTicketForm
    from datetime import timedelta
    from django.db.models import Avg, F

    nav_flags = _blusuite_nav_flags(request.user)
    user = request.user
    company = _get_user_company(user)

    # ── Handle POST actions ──────────────────────────────────────────
    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create_ticket':
            form = SupportTicketForm(request.POST)
            if form.is_valid():
                ticket = form.save(commit=False)
                ticket.company = company
                ticket.created_by = user
                if not ticket.contact_email:
                    ticket.contact_email = getattr(user, 'email', '') or ''
                ticket.save()
                # Send notification email to support
                try:
                    from django.core.mail import send_mail
                    send_mail(
                        f'[{ticket.reference}] New Support Ticket: {ticket.subject}',
                        f'A new support ticket has been submitted.\n\n'
                        f'Reference: {ticket.reference}\n'
                        f'Subject: {ticket.subject}\n'
                        f'Priority: {ticket.get_priority_display()}\n'
                        f'Category: {ticket.category or "General"}\n'
                        f'Company: {company.name if company else "N/A"}\n'
                        f'Submitted by: {user.get_full_name()} ({user.email})\n\n'
                        f'Description:\n{ticket.description}',
                        settings.DEFAULT_FROM_EMAIL,
                        [getattr(settings, 'SUPPORT_EMAIL', 'support@blusuite.com')],
                        fail_silently=True,
                    )
                except Exception:
                    pass
                messages.success(request, f'Ticket {ticket.reference} submitted successfully.')
                return redirect('blu_support_home')
            else:
                messages.error(request, 'Please correct the errors below.')
        elif action == 'close_ticket':
            ticket_id = request.POST.get('ticket_id')
            try:
                ticket = SupportTicket.objects.get(id=ticket_id, company=company)
                ticket.status = SupportTicket.Status.CLOSED
                ticket.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'Ticket {ticket.reference} closed.')
            except SupportTicket.DoesNotExist:
                messages.error(request, 'Ticket not found.')
            return redirect('blu_support_home')
        elif action == 'reopen_ticket':
            ticket_id = request.POST.get('ticket_id')
            try:
                ticket = SupportTicket.objects.get(id=ticket_id, company=company)
                ticket.status = SupportTicket.Status.OPEN
                ticket.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'Ticket {ticket.reference} reopened.')
            except SupportTicket.DoesNotExist:
                messages.error(request, 'Ticket not found.')
            return redirect('blu_support_home')

    # ── Ticket queryset ──────────────────────────────────────────────
    base_qs = SupportTicket.objects.filter(company=company).select_related('created_by') if company else SupportTicket.objects.none()

    # Filters
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    search_query = request.GET.get('search', '').strip()

    tickets = base_qs
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    if search_query:
        from django.db.models import Q
        tickets = tickets.filter(
            Q(subject__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(reference__icontains=search_query)
        )

    # Stats
    open_count = base_qs.filter(status=SupportTicket.Status.OPEN).count()
    in_progress_count = base_qs.filter(status=SupportTicket.Status.IN_PROGRESS).count()
    resolved_count = base_qs.filter(status=SupportTicket.Status.RESOLVED).count()
    closed_count = base_qs.filter(status=SupportTicket.Status.CLOSED).count()

    # Average response time (time between created_at and last_response_at)
    avg_resp = base_qs.filter(last_response_at__isnull=False).aggregate(
        avg=Avg(F('last_response_at') - F('created_at'))
    )['avg']
    if avg_resp and isinstance(avg_resp, timedelta):
        total_hours = avg_resp.total_seconds() / 3600
        if total_hours < 1:
            avg_response_time = f'{int(avg_resp.total_seconds() / 60)}m'
        elif total_hours < 24:
            avg_response_time = f'{total_hours:.1f}h'
        else:
            avg_response_time = f'{total_hours / 24:.1f}d'
    else:
        avg_response_time = '--'

    stats = {
        'open_tickets': open_count + in_progress_count,
        'avg_response_time': avg_response_time,
        'resolved_tickets': resolved_count + closed_count,
        'satisfaction_rate': 98,
    }

    # ── Ticket detail view ───────────────────────────────────────────
    detail_ticket = None
    ticket_id_param = request.GET.get('ticket')
    if ticket_id_param:
        try:
            detail_ticket = base_qs.get(id=ticket_id_param)
        except SupportTicket.DoesNotExist:
            pass

    # ── Knowledge base articles ──────────────────────────────────────
    articles = KnowledgeArticle.objects.filter(
        is_published=True,
        visibility=KnowledgeArticle.Visibility.TENANTS,
    )[:8]

    # Article detail
    article_slug = request.GET.get('article')
    detail_article = None
    if article_slug:
        try:
            detail_article = KnowledgeArticle.objects.get(slug=article_slug, is_published=True)
        except KnowledgeArticle.DoesNotExist:
            pass

    # Fresh form for the create ticket sidebar
    form = SupportTicketForm(initial={
        'priority': SupportTicket.Priority.NORMAL,
        'contact_email': getattr(user, 'email', ''),
    })

    context = {
        'stats': stats,
        'tickets': tickets[:50],
        'recent_tickets': base_qs[:5],
        'total_tickets': base_qs.count(),
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'closed_count': closed_count,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search_query': search_query,
        'status_choices': SupportTicket.Status.choices,
        'priority_choices': SupportTicket.Priority.choices,
        'detail_ticket': detail_ticket,
        'articles': articles,
        'detail_article': detail_article,
        'form': form,
        'company': company,
        **nav_flags,
    }

    return render(request, 'ems/blusuite_support.html', context)


@login_required
def employer_admin_dashboard(request):
    """Dashboard for Employer Admin (Branch/Company Admin)"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with appropriate role (from User model)
    if not (hasattr(request.user, 'role') and request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']):
        return render(request, 'ems/unauthorized.html')

    # Get the company this admin manages
    try:
        company = request.user.company
    except:
        messages.error(request, 'Company not assigned. Please contact your Employer Superuser.')
        return redirect('/')

    from blu_staff.apps.attendance.models import Attendance
    from blu_staff.apps.attendance.models import LeaveRequest
    from datetime import date, datetime, timedelta

    today = date.today()
    # Parse selected date (default today)
    selected_date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date() if selected_date_str else today
    except (ValueError, TypeError):
        selected_date = today

    # Get employees in this company
    employees = User.objects.filter(company=company, role='EMPLOYEE')

    # Statistics
    total_employees = employees.count()

    # Today's attendance
    present_today = Attendance.objects.filter(
        date=today,
        employee__company=company,
        status='PRESENT'
    ).count()

    late_today = Attendance.objects.filter(
        date=today,
        employee__company=company,
        status='LATE'
    ).count()

    absent_today = total_employees - present_today - late_today

    # Pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).count()

    # Today's attendance records (limit to 10 for display)
    today_attendance = Attendance.objects.filter(
        date=today,
        employee__company=company
    ).select_related('employee').order_by('-created_at')[:10]

    # Pending leave requests (limit to 5 for display)
    pending_leave_requests = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).select_related('employee').order_by('start_date')[:5]

    # Recent activities — built from real DB records
    recent_activities = []
    try:
        recent_checkins = Attendance.objects.filter(
            employee__company=company,
            created_at__date=today
        ).select_related('employee').order_by('-created_at')[:3]
        for att in recent_checkins:
            name = att.employee.get_full_name() or att.employee.email
            recent_activities.append({
                'title': 'Attendance recorded',
                'description': f'{name} checked in — {att.get_status_display()}',
                'timestamp': att.created_at,
                'type': 'attendance',
            })
    except Exception:
        pass
    try:
        recent_leaves = LeaveRequest.objects.filter(
            employee__company=company,
        ).select_related('employee').order_by('-created_at')[:3]
        for lr in recent_leaves:
            name = lr.employee.get_full_name() or lr.employee.email
            recent_activities.append({
                'title': 'Leave request',
                'description': f'{name} — {lr.leave_type} ({lr.status.capitalize()})',
                'timestamp': lr.created_at,
                'type': 'leave',
            })
    except Exception:
        pass
    recent_activities = sorted(recent_activities, key=lambda x: x['timestamp'], reverse=True)[:5]

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


@login_required
def employee_dashboard(request):
    """Employee dashboard"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Allow EMPLOYEE role or users with employee_profile (HR, Accountant, Supervisor)
    if not (hasattr(request.user, 'role') and request.user.role == 'EMPLOYEE'):
        # Check if user has employee_profile (HR/Accountant/Supervisor access employee portal)
        if not hasattr(request.user, 'employee_profile'):
            return render(request, 'ems/unauthorized.html')

    employee = request.user

    # Get employee's data
    profile = EmployeeProfile.objects.filter(user=employee).first()

    # Handle profile updates from employee (basic fields + emergency contact)
    if request.method == 'POST' and profile:
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        emergency_name = request.POST.get('emergency_contact_name', '').strip()
        emergency_phone = request.POST.get('emergency_contact_phone', '').strip()
        emergency_email = request.POST.get('emergency_contact_email', '').strip()
        emergency_address = request.POST.get('emergency_contact_address', '').strip()

        # Optional document upload
        document_file = request.FILES.get('document_file')
        document_title = request.POST.get('document_title', '').strip() or 'Employee Document'
        document_type = request.POST.get('document_type', 'OTHER')

        # Update profile basics
        if first_name:
            employee.first_name = first_name
        if last_name:
            employee.last_name = last_name
        if email:
            employee.email = email
        if phone:
            employee.phone_number = phone

        profile.address = address
        profile.emergency_contact_name = emergency_name
        profile.emergency_contact_phone = emergency_phone
        profile.emergency_contact_email = emergency_email
        profile.emergency_contact_address = emergency_address

        employee.save()
        profile.save()

        # Save uploaded document if present
        if document_file:
            try:
                from blu_staff.apps.documents.models import EmployeeDocument
                EmployeeDocument.objects.create(
                    employee=employee,
                    document_type=document_type,
                    title=document_title,
                    description='Uploaded via employee dashboard',
                    file=document_file,
                    uploaded_by=employee,
                    status='PENDING'
                )
                messages.success(request, "Document uploaded successfully.")
            except Exception as e:
                messages.error(request, f"Document upload failed: {e}")
        messages.success(request, "Profile updated successfully.")
        return redirect('employee_dashboard')
    today = date.today()

    # Attendance this month
    month_start = today.replace(day=1)
    attendance_this_month = Attendance.objects.filter(
        employee=employee,
        date__gte=month_start
    ).count()

    # Today's attendance
    today_attendance = Attendance.objects.filter(
        employee=employee,
        date=today
    ).first()

    # Pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        employee=employee,
        status='PENDING'
    ).count()

    # Documents
    try:
        from blu_staff.apps.documents.models import EmployeeDocument
        recent_docs = EmployeeDocument.objects.filter(
            employee=employee
        ).order_by('-created_at')[:5]
        documents_total = EmployeeDocument.objects.filter(employee=employee).count()
        documents_approved = EmployeeDocument.objects.filter(employee=employee, status='APPROVED').count()
        last_document = EmployeeDocument.objects.filter(employee=employee).order_by('-created_at').first()
    except Exception:
        recent_docs = []
        documents_total = 0
        documents_approved = 0
        last_document = None

    # Employment duration
    time_employed_days = None
    if profile and profile.date_hired:
        time_employed_days = (today - profile.date_hired).days

    # Profile completeness (lightweight)
    completeness_fields = [
        profile.employee_id if profile else None,
        profile.job_title if profile else None,
        profile.department if profile else None,
        profile.salary if profile else None,
        profile.bank_name if profile else None,
        profile.account_number if profile else None,
        profile.emergency_contact_name if profile else None,
        profile.date_hired if profile else None,
    ]
    filled_fields = len([f for f in completeness_fields if f])
    total_fields = len(completeness_fields)
    profile_complete_percent = int((filled_fields / total_fields) * 100) if total_fields else 0

    # Upcoming reviews - PERFORMANCE MODULE DISABLED
    # upcoming_reviews = PerformanceReview.objects.filter(
    #     employee=employee,
    #     review_date__gte=today
    # ).order_by('review_date')[:3]
    upcoming_reviews = []

    # Leave balance (approved leaves this year)
    leave_balance = 0
    try:
        annual_allowance = getattr(profile, 'leave_days', 0) or 21
        used_leaves = LeaveRequest.objects.filter(
            employee=employee,
            status='APPROVED',
            start_date__year=today.year,
        ).count()
        leave_balance = max(0, annual_allowance - used_leaves)
    except Exception:
        pass

    # Time employed in months
    time_employed_months = 0
    if time_employed_days:
        time_employed_months = time_employed_days // 30

    # Attendance rate (this month)
    attendance_rate = 0
    try:
        working_days_so_far = max(1, today.day)
        if attendance_this_month:
            attendance_rate = int((attendance_this_month / working_days_so_far) * 100)
    except Exception:
        pass

    # Documents pending
    documents_pending = 0
    try:
        from blu_staff.apps.documents.models import EmployeeDocument as ED
        documents_pending = ED.objects.filter(employee=employee, status='PENDING').count()
    except Exception:
        pass

    # Unread notifications
    unread_notifications = 0
    try:
        from blu_staff.apps.notifications.models import Notification
        unread_notifications = Notification.objects.filter(recipient=employee, is_read=False).count()
    except Exception:
        pass

    # Latest payslip
    latest_payslip = None
    try:
        from blu_staff.apps.payroll.models import Payroll
        latest_payslip = Payroll.objects.filter(employee=employee).order_by('-pay_period_end').first()
    except Exception:
        pass

    # Training stats
    training_enrolled = 0
    training_completed = 0
    training_pending = 0
    try:
        from blu_staff.apps.training.models import TrainingEnrollment
        t_qs = TrainingEnrollment.objects.filter(employee=employee)
        training_enrolled = t_qs.count()
        training_completed = t_qs.filter(status='COMPLETED').count()
        training_pending = t_qs.filter(status__in=['ENROLLED', 'IN_PROGRESS']).count()
    except Exception:
        pass

    # Benefits enrolled
    benefits_enrolled = 0
    try:
        from blu_staff.apps.payroll.models import EmployeeBenefit
        benefits_enrolled = EmployeeBenefit.objects.filter(employee=employee, status='ACTIVE').count()
    except Exception:
        pass

    # Recent activities (combine attendance, leave, documents, payroll)
    recent_activities = []
    try:
        for att in Attendance.objects.filter(employee=employee).order_by('-date')[:3]:
            recent_activities.append({
                'type': 'attendance',
                'title': f'Attendance: {att.get_status_display()}',
                'description': att.date.strftime('%b %d, %Y'),
                'created_at': att.date,
            })
    except Exception:
        pass
    try:
        for lr in LeaveRequest.objects.filter(employee=employee).order_by('-created_at')[:3]:
            recent_activities.append({
                'type': 'leave',
                'title': f'Leave: {lr.get_leave_type_display()}',
                'description': f'{lr.get_status_display()} — {lr.start_date.strftime("%b %d")} to {lr.end_date.strftime("%b %d")}',
                'created_at': lr.created_at,
            })
    except Exception:
        pass
    try:
        for doc in recent_docs[:3]:
            recent_activities.append({
                'type': 'document',
                'title': f'Document: {doc.title or "Untitled"}',
                'description': doc.get_status_display() if hasattr(doc, 'get_status_display') else (doc.status or 'Pending'),
                'created_at': doc.created_at,
            })
    except Exception:
        pass
    def _to_datetime(val):
        """Normalise date/datetime so mixed types can be compared (always aware)."""
        if isinstance(val, datetime):
            if timezone.is_naive(val):
                return timezone.make_aware(val)
            return val
        if isinstance(val, date):
            return timezone.make_aware(datetime.combine(val, datetime.min.time()))
        return timezone.make_aware(datetime.min.replace(year=2000))
    recent_activities.sort(key=lambda x: _to_datetime(x['created_at']), reverse=True)
    recent_activities = recent_activities[:8]

    # Upcoming events (reviews + approved leaves)
    upcoming_events = []
    for review in upcoming_reviews:
        upcoming_events.append({
            'title': f'Performance Review: {review.get_review_type_display()}',
            'date': review.review_date,
        })
    try:
        upcoming_leaves = LeaveRequest.objects.filter(
            employee=employee,
            status='APPROVED',
            start_date__gte=today,
        ).order_by('start_date')[:3]
        for lr in upcoming_leaves:
            upcoming_events.append({
                'title': f'Leave: {lr.get_leave_type_display()}',
                'date': lr.start_date,
            })
    except Exception:
        pass
    upcoming_events.sort(key=lambda x: _to_datetime(x['date']))

    # Pending tasks (onboarding tasks if any)
    pending_tasks = []
    try:
        from blu_staff.apps.onboarding.models import OnboardingTaskCompletion
        for tc in OnboardingTaskCompletion.objects.filter(
            employee_onboarding__employee=employee,
            status__in=['NOT_STARTED', 'IN_PROGRESS'],
        ).select_related('task').order_by('task__order')[:5]:
            pending_tasks.append({'title': tc.task.name})
    except Exception:
        pass

    # Company announcements
    announcements = []
    try:
        from blu_staff.apps.communication.models import Announcement
        company = getattr(employee, 'company', None)
        if company:
            announcements = Announcement.objects.filter(
                company=company,
                is_published=True,
            ).order_by('-created_at')[:3]
    except Exception:
        pass

    # ── Cross-Suite: AMS (My Assets) ─────────────────────────────────
    my_assets = []
    my_assets_count = 0
    try:
        from blu_assets.models import EmployeeAsset
        my_assets_qs = EmployeeAsset.objects.filter(
            employee=employee, status='ASSIGNED'
        ).order_by('-updated_at')
        my_assets_count = my_assets_qs.count()
        my_assets = list(my_assets_qs[:5])
        # Feed into recent activities
        for asset in my_assets_qs[:3]:
            recent_activities.append({
                'type': 'asset',
                'title': f'Asset: {asset.name}',
                'description': f'{asset.get_asset_type_display()} — {asset.get_status_display()}',
                'created_at': asset.updated_at or asset.created_at,
            })
    except Exception:
        pass

    # ── Cross-Suite: PMS (My Projects & Tasks) ───────────────────────
    my_projects = []
    my_projects_count = 0
    my_tasks_pending = 0
    my_tasks_list = []
    try:
        from blu_projects.models import Project, Task
        my_projects_qs = Project.objects.filter(
            team_members=employee, status__in=['PLANNING', 'ACTIVE', 'ON_HOLD']
        ).order_by('-updated_at')
        my_projects_count = my_projects_qs.count()
        my_projects = list(my_projects_qs[:5])
        # My open tasks across all projects
        my_tasks_qs = Task.objects.filter(
            assigned_to=employee, status__in=['TODO', 'IN_PROGRESS', 'IN_REVIEW', 'BLOCKED']
        ).select_related('project').order_by('due_date')
        my_tasks_pending = my_tasks_qs.count()
        my_tasks_list = list(my_tasks_qs[:5])
        # Feed into recent activities
        for proj in my_projects_qs[:2]:
            recent_activities.append({
                'type': 'project',
                'title': f'Project: {proj.name}',
                'description': f'{proj.get_status_display()} — {proj.progress_percentage}% complete',
                'created_at': proj.updated_at or proj.created_at,
            })
        for task in my_tasks_qs[:2]:
            recent_activities.append({
                'type': 'task',
                'title': f'Task: {task.title}',
                'description': f'{task.project.code} — {task.get_status_display()}' + (f' — Due {task.due_date.strftime("%b %d")}' if task.due_date else ''),
                'created_at': task.updated_at or task.created_at,
            })
    except Exception:
        pass

    # Re-sort recent activities after adding cross-suite items
    recent_activities.sort(key=lambda x: _to_datetime(x['created_at']), reverse=True)
    recent_activities = recent_activities[:10]

    context = {
        'employee': employee,
        'profile': profile,
        'current_date': today,
        'attendance_this_month': attendance_this_month,
        'today_attendance': today_attendance,
        'pending_leaves': pending_leaves,
        'recent_docs': recent_docs,
        'upcoming_reviews': upcoming_reviews,
        'documents_total': documents_total,
        'documents_approved': documents_approved,
        'documents_pending': documents_pending,
        'last_document': last_document,
        'time_employed_days': time_employed_days,
        'time_employed_months': time_employed_months,
        'profile_complete_percent': profile_complete_percent,
        'profile_complete_count': filled_fields,
        'profile_complete_total': total_fields,
        'leave_balance': leave_balance,
        'attendance_rate': attendance_rate,
        'unread_notifications': unread_notifications,
        'latest_payslip': latest_payslip,
        'training_enrolled': training_enrolled,
        'training_completed': training_completed,
        'training_pending': training_pending,
        'benefits_enrolled': benefits_enrolled,
        'recent_activities': recent_activities,
        'upcoming_events': upcoming_events,
        'pending_tasks': pending_tasks,
        'announcements': announcements,
        # Cross-suite
        'my_assets': my_assets,
        'my_assets_count': my_assets_count,
        'my_projects': my_projects,
        'my_projects_count': my_projects_count,
        'my_tasks_pending': my_tasks_pending,
        'my_tasks_list': my_tasks_list,
    }
    
    return render(request, 'ems/employee_dashboard.html', context)


@login_required
def employee_suites(request):
    """My Suites tab - shows cross-suite cards, notifications, and activity.
    Only accessible to employees who have been granted access to projects or assets."""
    
    employee = request.user

    # ── Cross-Suite: AMS (My Assets) ─────────────────────────────────
    my_assets = []
    my_assets_count = 0
    cross_suite_activities = []
    has_asset_access = False
    try:
        from blu_assets.models import EmployeeAsset
        my_assets_qs = EmployeeAsset.objects.filter(
            employee=employee, status='ASSIGNED'
        ).order_by('-updated_at')
        my_assets_count = my_assets_qs.count()
        has_asset_access = my_assets_count > 0
        my_assets = list(my_assets_qs[:10])
        for asset in my_assets_qs[:5]:
            cross_suite_activities.append({
                'type': 'asset',
                'title': f'Asset: {asset.name}',
                'description': f'{asset.get_asset_type_display()} — {asset.get_status_display()}',
                'created_at': asset.updated_at or asset.created_at,
            })
    except Exception:
        pass

    # ── Cross-Suite: PMS (My Projects & Tasks) ───────────────────────
    my_projects = []
    my_projects_count = 0
    my_tasks_pending = 0
    my_tasks_list = []
    has_project_access = False
    try:
        from blu_projects.models import Project, Task
        # Check if user is a member of any projects
        my_projects_qs = Project.objects.filter(
            team_members=employee
        ).order_by('-updated_at')
        my_projects_count = my_projects_qs.count()
        has_project_access = my_projects_count > 0
        
        # Get active projects
        my_projects = list(my_projects_qs.filter(status__in=['PLANNING', 'ACTIVE', 'ON_HOLD'])[:10])
        
        # Get tasks assigned to this employee
        my_tasks_qs = Task.objects.filter(
            assigned_to=employee, status__in=['TODO', 'IN_PROGRESS', 'IN_REVIEW', 'BLOCKED']
        ).select_related('project').order_by('due_date')
        my_tasks_pending = my_tasks_qs.count()
        my_tasks_list = list(my_tasks_qs[:10])
        
        # Add to activity feed
        for proj in my_projects_qs[:3]:
            cross_suite_activities.append({
                'type': 'project',
                'title': f'Project: {proj.name}',
                'description': f'{proj.get_status_display()} — {proj.progress_percentage}% complete',
                'created_at': proj.updated_at or proj.created_at,
            })
        for task in my_tasks_qs[:3]:
            cross_suite_activities.append({
                'type': 'task',
                'title': f'Task: {task.title}',
                'description': f'{task.project.code} — {task.get_status_display()}' + (f' — Due {task.due_date.strftime("%b %d")}' if task.due_date else ''),
                'created_at': task.updated_at or task.created_at,
            })
    except Exception:
        pass
    
    # ── Access Control: Only allow if user has been granted access to at least one suite ──
    if not has_asset_access and not has_project_access:
        messages.info(request, 'You do not have access to any suites yet. Contact your administrator to be added to projects or assigned assets.')
        return render(request, 'ems/unauthorized.html', {
            'message': 'No Suite Access',
            'detail': 'You need to be added to a project or assigned an asset to access My Suites.'
        })

    # Sort cross-suite activities
    cross_suite_activities.sort(
        key=lambda x: x['created_at'] if hasattr(x['created_at'], 'timestamp') else x['created_at'],
        reverse=True,
    )

    # ── Suite Notifications (ASSET + PROJECT categories) ─────────────
    suite_notifications = []
    suite_notifications_count = 0
    try:
        from blu_staff.apps.notifications.models import Notification
        suite_notifs_qs = Notification.objects.filter(
            recipient=employee, category__in=['ASSET', 'PROJECT']
        ).order_by('-created_at')[:20]
        suite_notifications = list(suite_notifs_qs)
        suite_notifications_count = Notification.objects.filter(
            recipient=employee, category__in=['ASSET', 'PROJECT'], is_read=False
        ).count()
    except Exception:
        pass

    # ── Access flags ────────────────────────────────────────────────────
    nav_flags = _blusuite_nav_flags(employee)
    can_manage_assets = nav_flags.get('show_assets_suite', False)
    can_manage_projects = nav_flags.get('show_projects_suite', False)

    context = {
        'my_assets': my_assets,
        'my_assets_count': my_assets_count,
        'my_projects': my_projects,
        'my_projects_count': my_projects_count,
        'my_tasks_pending': my_tasks_pending,
        'my_tasks_list': my_tasks_list,
        'suite_notifications': suite_notifications,
        'suite_notifications_count': suite_notifications_count,
        'cross_suite_activities': cross_suite_activities,
        'can_manage_assets': can_manage_assets,
        'can_manage_projects': can_manage_projects,
    }

    return render(request, 'ems/employee_suites.html', context)


@login_required
def employee_profile_view(request):
    """Employee profile page with editable tabs - separate from dashboard"""
    # Allow any user with an employee profile (not just role==EMPLOYEE)
    if not hasattr(request.user, 'employee_profile') or not request.user.employee_profile:
        if not (hasattr(request.user, 'role') and request.user.role == 'EMPLOYEE'):
            return render(request, 'ems/unauthorized.html')

    employee = request.user
    profile = EmployeeProfile.objects.filter(user=employee).first()

    # Handle profile updates from employee (basic fields + emergency contact)
    if request.method == 'POST' and profile:
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        emergency_name = request.POST.get('emergency_contact_name', '').strip()
        emergency_phone = request.POST.get('emergency_contact_phone', '').strip()
        emergency_email = request.POST.get('emergency_contact_email', '').strip()
        emergency_address = request.POST.get('emergency_contact_address', '').strip()

        if first_name:
            employee.first_name = first_name
        if last_name:
            employee.last_name = last_name
        if email:
            employee.email = email
        if phone:
            employee.phone_number = phone
        employee.save(update_fields=['first_name', 'last_name', 'email', 'phone_number'])

        if address:
            profile.address = address
        if emergency_name:
            profile.emergency_contact_name = emergency_name
        if emergency_phone:
            profile.emergency_contact_phone = emergency_phone
        if emergency_email:
            profile.emergency_contact_email = emergency_email
        if emergency_address:
            profile.emergency_contact_address = emergency_address
        profile.save()

        # Handle profile picture upload
        profile_picture = request.FILES.get('profile_picture')
        signature_image = request.FILES.get('signature_image')
        signature_pin = request.POST.get('signature_pin', '').strip()
        if profile_picture:
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
            if profile_picture.content_type in allowed_types and profile_picture.size <= 5 * 1024 * 1024:
                employee.profile_picture = profile_picture
                employee.save()
                messages.success(request, 'Profile picture updated.')
            else:
                messages.error(request, 'Invalid image. Use JPG/PNG under 5MB.')

        # Handle signature upload
        if signature_image:
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
            if signature_image.content_type in allowed_types and signature_image.size <= 5 * 1024 * 1024:
                profile.signature_image = signature_image
                profile.save()
                messages.success(request, 'Signature updated.')
            else:
                messages.error(request, 'Invalid signature file. Use JPG/PNG under 5MB.')

        # Handle signature PIN update
        if signature_pin:
            profile.signature_pin_hash = make_password(signature_pin)
            profile.save(update_fields=['signature_pin_hash'])
            messages.success(request, 'Signature PIN saved.')

        # Handle document upload
        document_file = request.FILES.get('document_file')
        if document_file:
            doc_title = request.POST.get('document_title', '').strip() or document_file.name
            try:
                from blu_staff.apps.documents.models import EmployeeDocument
                EmployeeDocument.objects.create(
                    employee=employee,
                    title=doc_title,
                    file=document_file,
                    status='PENDING',
                )
                messages.success(request, f'Document "{doc_title}" uploaded successfully.')
            except Exception as e:
                messages.error(request, f'Document upload failed: {str(e)}')

        if not profile_picture and not document_file and not signature_image and not signature_pin:
            messages.success(request, 'Profile updated successfully.')
        return redirect('employee_profile')

    from datetime import date
    today = date.today()

    # Profile completeness
    total_fields = 10
    filled_fields = sum(1 for val in [
        employee.first_name, employee.last_name, employee.email,
        employee.phone_number,
        getattr(profile, 'address', None),
        getattr(profile, 'date_of_birth', None),
        getattr(profile, 'employee_id', None),
        getattr(profile, 'job_title', None),
        getattr(profile, 'department', None),
        getattr(profile, 'emergency_contact_name', None),
    ] if val)
    profile_complete_percent = int((filled_fields / total_fields) * 100) if total_fields else 0

    # Time employed
    time_employed_days = (today - profile.date_hired).days if profile and profile.date_hired else 0

    # Attendance
    attendance_this_month = 0
    try:
        from blu_staff.apps.attendance.models import Attendance
        attendance_this_month = Attendance.objects.filter(
            employee=employee,
            date__month=today.month,
            date__year=today.year,
            status__in=['PRESENT', 'LATE', 'HALF_DAY']
        ).count()
    except Exception:
        pass

    # Leave
    pending_leaves = 0
    try:
        from blu_staff.apps.attendance.models import LeaveRequest
        pending_leaves = LeaveRequest.objects.filter(employee=employee, status='PENDING').count()
    except Exception:
        pass

    # Documents
    documents_total = 0
    try:
        from blu_staff.apps.documents.models import EmployeeDocument
        documents_total = EmployeeDocument.objects.filter(employee=employee).count()
    except Exception:
        pass

    # Assets
    employee_assets = []
    try:
        from blu_assets.models import EmployeeAsset
        employee_assets = EmployeeAsset.objects.filter(employee=employee).order_by('-assigned_date')[:10]
    except Exception:
        pass

    context = {
        'employee': employee,
        'profile': profile,
        'current_date': today,
        'attendance_this_month': attendance_this_month,
        'pending_leaves': pending_leaves,
        'documents_total': documents_total,
        'time_employed_days': time_employed_days,
        'profile_complete_percent': profile_complete_percent,
        'employee_assets': employee_assets,
    }

    return render(request, 'ems/employee_dashboard.html', context)


@login_required
def employer_dashboard(request):
    """Employer dashboard with enhanced statistics and alerts"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with appropriate role (from User model)
    if not (hasattr(request.user, 'role') and request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']):
        return render(request, 'ems/unauthorized.html')

    employer = request.user
    company = EmployerProfile.objects.filter(user=employer).first()

    # Get company statistics - handle ADMINISTRATOR role
    if request.user.role == 'ADMINISTRATOR':
        # For ADMINISTRATOR users, get their company directly
        company = request.user.company
        employees = User.objects.filter(company=company, role='EMPLOYEE').select_related('employee_profile')
    else:
        # For EMPLOYER_SUPERUSER/EMPLOYER_ADMIN, use existing logic
        company = EmployerProfile.objects.filter(user=employer).first()
        employees = User.objects.filter(
            employee_profile__user__employer_profile__user=employer
        ).select_related('employee_profile')

    # If no company found, try to get from user.company for ADMINISTRATOR
    if not company and request.user.role == 'ADMINISTRATOR':
        company = request.user.company

    # If still no company, redirect to unauthorized
    if not company:
        return render(request, 'ems/unauthorized.html')

    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Basic Statistics
    total_employees = employees.count()
    active_employees = employees.filter(is_active=True).count()

    # Today's attendance
    today_attendance = Attendance.objects.filter(
        employee__in=employees,
        date=today
    )
    present_today = today_attendance.filter(status='PRESENT').count()
    late_today = today_attendance.filter(status='LATE').count()
    absent_today = total_employees - (present_today + late_today)
    
    attendance_rate = (present_today / total_employees * 100) if total_employees > 0 else 0

    # Attendance Trend (Last 7 days)
    attendance_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_attendance = Attendance.objects.filter(
            employee__in=employees,
            date=day,
            status='PRESENT'
        ).count()
        attendance_trend.append({
            'date': day.strftime('%a'),
            'count': day_attendance,
            'rate': round((day_attendance / total_employees * 100) if total_employees > 0 else 0, 1)
        })

    # Leave Statistics
    pending_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).count()
    
    approved_leaves_this_month = LeaveRequest.objects.filter(
        employee__in=employees,
        status='APPROVED',
        start_date__gte=month_ago
    ).count()

    # Upcoming Birthdays - Feature disabled (no date_of_birth field in model)
    upcoming_birthdays = []

    # Contract Expiry Alerts (Expiring in next 90 days)
    contract_expiry_alerts = []
    for employee in employees:
        if hasattr(employee, 'employee_profile') and employee.employee_profile:
            profile = employee.employee_profile
            expiry_date = None
            contract_type = None
            
            if profile.employment_type == 'CONTRACT' and profile.contract_end_date:
                expiry_date = profile.contract_end_date
                contract_type = 'Contract'
            elif profile.employment_type == 'PROBATION' and profile.probation_end_date:
                expiry_date = profile.probation_end_date
                contract_type = 'Probation'
            elif profile.employment_type == 'TEMPORARY' and profile.temporary_end_date:
                expiry_date = profile.temporary_end_date
                contract_type = 'Temporary'
            
            if expiry_date:
                days_until = (expiry_date - today).days
                if 0 <= days_until <= 90:
                    contract_expiry_alerts.append({
                        'employee': employee,
                        'type': contract_type,
                        'date': expiry_date,
                        'days_until': days_until,
                        'is_critical': days_until <= 30
                    })
    
    contract_expiry_alerts.sort(key=lambda x: x['days_until'])

    # Work Anniversaries (This month)
    work_anniversaries = []
    for employee in employees:
        if hasattr(employee, 'employee_profile') and employee.employee_profile and employee.employee_profile.date_hired:
            hire_date = employee.employee_profile.date_hired
            if hire_date.month == today.month:
                years_employed = today.year - hire_date.year
                if years_employed > 0:
                    work_anniversaries.append({
                        'employee': employee,
                        'date': date(today.year, hire_date.month, hire_date.day),
                        'years': years_employed
                    })
    
    work_anniversaries.sort(key=lambda x: x['date'])

    # Department-wise Statistics
    from django.db.models import Count
    from blu_staff.apps.accounts.models import CompanyDepartment
    
    # Get departments with manual employee count
    departments_list = []
    all_departments = CompanyDepartment.objects.filter(company=company).order_by('name')
    
    for dept in all_departments:
        # Count employees by matching department CharField (not ideal but works with current model)
        emp_count = 0
        for emp in employees:
            if hasattr(emp, 'employee_profile') and emp.employee_profile:
                if emp.employee_profile.department == dept.name:
                    emp_count += 1
        
        if emp_count > 0:
            departments_list.append({
                'name': dept.name,
                'employee_count': emp_count
            })
    
    # Sort by employee count and get top 5
    departments_list.sort(key=lambda x: x['employee_count'], reverse=True)
    departments = departments_list[:5]

    # Recent Documents
    recent_docs = EmployeeDocument.objects.filter(
        employee__in=employees
    ).select_related('employee', 'category').order_by('-created_at')[:10]

    # Recent Performance Reviews - PERFORMANCE MODULE DISABLED
    # recent_reviews = PerformanceReview.objects.filter(
    #     employee__in=employees
    # ).select_related('employee', 'reviewer').order_by('-created_at')[:5]
    recent_reviews = []

    # Pending Approvals Count
    pending_documents = EmployeeDocument.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).count()

    # New hires in last 30 days
    new_hires_month = 0
    try:
        new_hires_month = EmployeeProfile.objects.filter(
            user__in=employees,
            date_hired__gte=month_ago,
        ).count()
    except Exception:
        pass

    # On leave today
    on_leave_today = LeaveRequest.objects.filter(
        employee__in=employees,
        status='APPROVED',
        start_date__lte=today,
        end_date__gte=today,
    ).count()

    # Attrition rate (employees deactivated this year / total)
    attrition_rate = 0
    try:
        deactivated_this_year = User.objects.filter(
            company=company,
            role='EMPLOYEE',
            is_active=False,
            last_login__year=today.year,
        ).count()
        if total_employees > 0:
            attrition_rate = round((deactivated_this_year / (total_employees + deactivated_this_year)) * 100, 1)
    except Exception:
        pass

    # Attendance exceptions today (late + absent)
    attendance_exceptions = late_today + absent_today

    # Probation/contract reviews this week
    probation_reviews = 0
    try:
        from django.db.models import Q as _Q
        next_week = today + timedelta(days=7)
        probation_reviews = EmployeeProfile.objects.filter(
            user__in=employees,
        ).filter(
            _Q(probation_end_date__range=[today, next_week]) |
            _Q(contract_end_date__range=[today, next_week])
        ).count()
    except Exception:
        pass

    # Expiring documents (next 30 days)
    expiring_docs = 0
    try:
        expiring_docs = EmployeeDocument.objects.filter(
            employee__in=employees,
            expiry_date__range=[today, today + timedelta(days=30)],
        ).count()
    except Exception:
        pass

    # Pending benefit enrollments
    pending_benefits = 0
    try:
        from blu_staff.apps.payroll.models import EmployeeBenefit
        pending_benefits = EmployeeBenefit.objects.filter(
            employee__in=employees,
            status='PENDING',
        ).count()
    except Exception:
        pass

    # 30-day attendance trend for charts
    import json
    attendance_dates = []
    attendance_present_data = []
    attendance_absent_data = []
    
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        day_attendance = Attendance.objects.filter(
            employee__in=employees,
            date=day
        )
        present_count = day_attendance.filter(status='PRESENT').count()
        absent_count = total_employees - present_count if total_employees > 0 else 0
        
        attendance_dates.append(day.strftime('%b %d'))
        attendance_present_data.append(present_count)
        attendance_absent_data.append(absent_count)

    context = {
        'employer': employer,
        'company': company,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'present_today': present_today,
        'late_today': late_today,
        'absent_today': absent_today,
        'attendance_rate': round(attendance_rate, 1),
        'attendance_trend': attendance_trend,
        'pending_leaves': pending_leaves,
        'approved_leaves_this_month': approved_leaves_this_month,
        'contract_expiry_alerts': contract_expiry_alerts[:5],
        'work_anniversaries': work_anniversaries,
        'departments': departments,
        'recent_docs': recent_docs,
        'recent_reviews': recent_reviews,
        'pending_documents': pending_documents,
        'user_role': request.user.role,
        'today': today,
        'new_hires_month': new_hires_month,
        'on_leave_today': on_leave_today,
        'attrition_rate': attrition_rate,
        'attendance_exceptions': attendance_exceptions,
        'probation_reviews': probation_reviews,
        'expiring_docs': expiring_docs,
        'pending_benefits': pending_benefits,
        # 30-day attendance chart data
        'attendance_dates_json': json.dumps(attendance_dates),
        'attendance_present_json': json.dumps(attendance_present_data),
        'attendance_absent_json': json.dumps(attendance_absent_data),
        # Navigation visibility flags for sidebar
        'show_attendance': True,
        'show_leave': True,
        'show_documents': True,
        'show_performance': False,
        'show_payroll': True,
        'show_reports': True,
        'show_analytics_suite': True,
    }

    return render(request, 'ems/employer_dashboard_new.html', context)


@login_required
def leave_management(request):
    """Leave management dashboard for admins and employees"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with appropriate role (from User model)
    # Allow EMPLOYEE users with HR role to access
    is_hr = (request.user.role == 'EMPLOYEE' and 
             hasattr(request.user, 'employee_profile') and 
             request.user.employee_profile.employee_role == 'HR')
    
    if not (hasattr(request.user, 'role') and 
            (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'EMPLOYEE'] or is_hr)):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.attendance.models import LeaveRequest
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Count
    from datetime import date, timedelta
    import csv
    from django.http import HttpResponse

    User = get_user_model()

    # Regular employees see their own leave requests - redirect to employee leave page
    # But HR employees should see the management view
    if request.user.role == 'EMPLOYEE' and not is_hr:
        return redirect('employee_leave_request')

    # Employer/Admin see all employee leave requests
    company = _get_user_company(request.user)

    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    employees = User.objects.filter(company=company, role='EMPLOYEE')
    
    # Get all leave requests for statistics
    all_leave_requests = LeaveRequest.objects.filter(employee__in=employees)
    
    # Calculate statistics
    total_requests = all_leave_requests.count()
    pending_count = all_leave_requests.filter(status=LeaveRequest.Status.PENDING).count()
    approved_count = all_leave_requests.filter(status=LeaveRequest.Status.APPROVED).count()
    rejected_count = all_leave_requests.filter(status=LeaveRequest.Status.REJECTED).count()
    
    # Filter leave requests
    leave_requests = all_leave_requests
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        leave_requests = leave_requests.filter(status=status_filter)
    
    # Search filter
    search_query = request.GET.get('search', '').strip()
    if search_query:
        leave_requests = leave_requests.filter(
            Q(employee__first_name__icontains=search_query) |
            Q(employee__last_name__icontains=search_query) |
            Q(employee__email__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
    
    # Leave type filter
    leave_type_filter = request.GET.get('leave_type', '')
    if leave_type_filter:
        leave_requests = leave_requests.filter(leave_type=leave_type_filter)
    
    # Date range filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        leave_requests = leave_requests.filter(start_date__gte=date_from)
    if date_to:
        leave_requests = leave_requests.filter(end_date__lte=date_to)
    
    leave_requests = leave_requests.select_related('employee', 'employee__employee_profile', 'approved_by').order_by('-created_at')
    
    # CSV Export
    if request.GET.get('format') == 'csv':
        filename = f"leave_requests_{date.today().strftime('%Y%m%d')}.csv"
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')  # UTF-8 BOM
        writer = csv.writer(response)
        
        writer.writerow(['Employee', 'Position', 'Leave Type', 'Start Date', 'End Date', 'Days', 'Reason', 'Status', 'Applied Date', 'Approved By'])
        
        for req in leave_requests:
            writer.writerow([
                req.employee.get_full_name(),
                req.employee.employee_profile.job_title if hasattr(req.employee, 'employee_profile') and req.employee.employee_profile else 'N/A',
                req.get_leave_type_display(),
                req.start_date.strftime('%Y-%m-%d'),
                req.end_date.strftime('%Y-%m-%d'),
                req.duration,
                req.reason,
                req.get_status_display(),
                req.created_at.strftime('%Y-%m-%d'),
                req.approved_by.get_full_name() if req.approved_by else 'N/A'
            ])
        
        return response

    _is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or getattr(request.user, 'is_employer_admin', False)
    base_template = 'ems/base_employer.html' if _is_admin else 'ems/base_employee.html'
    context = {
        'leave_requests': leave_requests,
        'status_filter': status_filter,
        'status_choices': LeaveRequest.Status.choices,
        'leave_type_choices': LeaveRequest.LeaveType.choices,
        'company': company,
        'search_query': search_query,
        'leave_type_filter': leave_type_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'employees': employees,
        'base_template': base_template,
        'is_admin': _is_admin,
    }
    if _is_admin:
        context.update(_get_employer_nav_context(request.user))
    return render(request, 'ems/employer_leave_management.html', context)


# Request access page
def request_access(request):
    """Request access page"""
    return render(request, 'ems/request_access.html')

def api_current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Not authenticated'}, status=401)

    user = request.user
    return JsonResponse({
        'id': user.id,
        'email': user.email,
        'role': getattr(user, 'role', None),
        'platform_role': getattr(user, 'platform_role', None),
        'is_superadmin': getattr(user, 'is_superadmin', False),
        'first_name': user.first_name,
        'last_name': user.last_name,
    })

@login_required
def attendance_dashboard(request):
    """Attendance management dashboard for admins"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with appropriate role (from User model)
    # Allow EMPLOYEE users with HR role to access
    is_hr = (request.user.role == 'EMPLOYEE' and 
             hasattr(request.user, 'employee_profile') and 
             request.user.employee_profile.employee_role == 'HR')
    
    if not (hasattr(request.user, 'role') and 
            (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or is_hr)):
        return render(request, 'ems/unauthorized.html')

    # Get basic attendance statistics
    from blu_staff.apps.attendance.models import Attendance, LeaveRequest
    from django.contrib.auth import get_user_model
    from django.http import HttpResponse
    from datetime import date, datetime, timedelta
    import calendar
    from collections import defaultdict
    import csv

    User = get_user_model()
    today = date.today()

    # Get employees based on user role and determine company for template
    company = None
    # SUPERADMIN shouldn't access this (guarded above), but keep fallback
    if request.user.role == 'SUPERADMIN':
        employees = User.objects.filter(role='EMPLOYEE')
    elif request.user.role == 'ADMINISTRATOR':
        # For ADMINISTRATOR users, get employees from their company
        company = _get_user_company(request.user)
        employees = User.objects.filter(company=company, role='EMPLOYEE') if company else User.objects.none()
    else:  # EMPLOYER_ADMIN
        # Try to resolve company for employer admin
        try:
            company = request.user.employer_profile.company
        except Exception:
            company = getattr(request.user, 'company', None)
        if company:
            employees = User.objects.filter(company=company, role='EMPLOYEE')
        else:
            employees = User.objects.filter(
                employee_profile__user__employer_profile__user=request.user
            )

    # Determine selected date from query (defaults to today)
    selected_date = today
    selected_date_param = request.GET.get('date')
    try:
        if selected_date_param:
            selected_date = datetime.strptime(selected_date_param, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        selected_date = today

    # Handle year and month filters
    year_param = request.GET.get('year')
    month_num_param = request.GET.get('month_num')
    
    if year_param and month_num_param:
        try:
            selected_year = int(year_param)
            selected_month_num = int(month_num_param)
            selected_month = date(selected_year, selected_month_num, 1)
        except (TypeError, ValueError):
            selected_month = selected_date.replace(day=1)
    else:
        selected_month = selected_date.replace(day=1)
    
    month_last_day = calendar.monthrange(selected_month.year, selected_month.month)[1]
    month_end = selected_month.replace(day=month_last_day)

    # Filter attendance records for selected date and optional filters
    attendance_qs = Attendance.objects.filter(employee__in=employees)
    attendance_qs = attendance_qs.filter(date=selected_date)

    status_filter = request.GET.get('status')
    if not status_filter:
        status_filter = 'PRESENT'
    if status_filter != 'ALL':
        attendance_qs = attendance_qs.filter(status=status_filter.upper())

    # Employee filter
    employee_filter = request.GET.get('employee')
    employee_filter_id = None
    if employee_filter:
        try:
            employee_filter_id = int(employee_filter)
        except (TypeError, ValueError):
            employee_filter_id = None
    if employee_filter_id:
        employees = employees.filter(id=employee_filter_id)
        attendance_qs = attendance_qs.filter(employee_id=employee_filter_id)
    
    # Search filter
    search_query = request.GET.get('search', '').strip()
    if search_query:
        from django.db.models import Q
        employees = employees.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(employee_profile__employee_id__icontains=search_query)
        )

    # Get all attendance records for the selected date
    attendance_records_dict = {
        record.employee_id: record 
        for record in attendance_qs.select_related('employee')
    }
    
    # Build a list of all employees with their attendance record (or None)
    attendance_records = []
    for employee in employees.select_related('employee_profile').order_by('first_name', 'last_name'):
        record = attendance_records_dict.get(employee.id)
        if record:
            attendance_records.append(record)
        else:
            # Create a placeholder record for employees without attendance
            placeholder = type('obj', (object,), {
                'employee': employee,
                'date': selected_date,
                'check_in': None,
                'check_out': None,
                'status': 'ABSENT',
                'working_hours': 0,
                'latitude': None,
                'longitude': None,
                'location': None,
                'notes': None,
                'id': None,
                'get_status_display': lambda self: 'Absent'
            })()
            attendance_records.append(placeholder)
    
    present_count = attendance_qs.filter(status=Attendance.Status.PRESENT).count()
    late_count = attendance_qs.filter(status=Attendance.Status.LATE).count()
    on_leave_count = attendance_qs.filter(status=Attendance.Status.ON_LEAVE).count()
    half_day_count = attendance_qs.filter(status=Attendance.Status.HALF_DAY).count()
    absent_status_count = attendance_qs.filter(status=Attendance.Status.ABSENT).count()

    # Employees without a record for selected date are counted absent
    employee_ids_with_records = attendance_qs.values_list('employee_id', flat=True)
    missing_record_count = employees.exclude(id__in=employee_ids_with_records).count()
    absent_count = absent_status_count + missing_record_count

    pending_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        status=LeaveRequest.Status.PENDING,
        start_date__lte=selected_date,
        end_date__gte=selected_date
    ).count()

    total_hours = sum(record.working_hours for record in attendance_records)

    matrix_employees_qs = employees
    if employee_filter_id:
        matrix_employees_qs = matrix_employees_qs.filter(id=employee_filter_id)
    matrix_employees = list(matrix_employees_qs.order_by('first_name', 'last_name'))

    month_attendance_qs = Attendance.objects.filter(
        employee__in=employees,
        date__range=[selected_month, month_end]
    ).select_related('employee')
    if employee_filter_id:
        month_attendance_qs = month_attendance_qs.filter(employee_id=employee_filter_id)

    attendance_lookup = defaultdict(dict)
    for record in month_attendance_qs:
        attendance_lookup[record.employee_id][record.date] = record

    month_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        status=LeaveRequest.Status.APPROVED,
        start_date__lte=month_end,
        end_date__gte=selected_month
    )
    if employee_filter_id:
        month_leaves = month_leaves.filter(employee_id=employee_filter_id)

    leave_dates_by_employee = defaultdict(set)
    for leave in month_leaves:
        leave_start = max(leave.start_date, selected_month)
        leave_end = min(leave.end_date, month_end)
        current_day = leave_start
        while current_day <= leave_end:
            leave_dates_by_employee[leave.employee_id].add(current_day)
            current_day += timedelta(days=1)

    # Get holidays for the month (before month_days loop)
    from blu_staff.apps.accounts.models import CompanyHoliday
    holidays = CompanyHoliday.objects.filter(
        company=company,
        date__gte=selected_month,
        date__lte=month_end
    )
    holiday_dates = set(h.date for h in holidays)
    holiday_map = {h.date: h.name for h in holidays}

    month_days = []
    current_day = selected_month
    while current_day <= month_end:
        day_of_week = current_day.weekday()  # 0=Monday, 6=Sunday
        is_sunday = day_of_week == 6
        is_holiday = current_day in holiday_dates
        month_days.append({
            'date': current_day,
            'day_label': current_day.strftime('%a'),
            'day_number': current_day.day,
            'is_sunday': is_sunday,
            'is_holiday': is_holiday,
            'holiday_name': holiday_map.get(current_day, ''),
        })
        current_day += timedelta(days=1)

    status_code_map = {
        Attendance.Status.PRESENT: ('P', 'present'),
        Attendance.Status.LATE: ('Lt', 'late'),
        Attendance.Status.HALF_DAY: ('Hd', 'half_day'),
        Attendance.Status.ABSENT: ('Ab', 'absent'),
        Attendance.Status.ON_LEAVE: ('Lv', 'on_leave'),
    }

    status_legend = [
        {'code': 'P', 'label': 'Present', 'css_class': 'present'},
        {'code': 'Lt', 'label': 'Late', 'css_class': 'late'},
        {'code': 'Hd', 'label': 'Half Day', 'css_class': 'half_day'},
        {'code': 'Ab', 'label': 'Absent', 'css_class': 'absent'},
        {'code': 'Lv', 'label': 'On Leave', 'css_class': 'on_leave'},
        {'code': 'H', 'label': 'Holiday', 'css_class': 'holiday'},
    ]

    attendance_matrix = []
    for employee in matrix_employees:
        employee_records = attendance_lookup.get(employee.id, {})
        row_statuses = []
        leave_dates = leave_dates_by_employee.get(employee.id, set())
        
        # Calculate monthly stats for this employee
        emp_present = 0
        emp_late = 0
        emp_absent = 0
        emp_leave = 0
        emp_half_day = 0
        total_work_hours = 0.0
        
        for day_info in month_days:
            record = employee_records.get(day_info['date'])
            is_holiday = day_info.get('is_holiday', False)
            is_sunday = day_info.get('is_sunday', False)
            
            if record:
                # There's an actual attendance record
                code, css_class = status_code_map.get(record.status, ('', ''))
                if not code and record.status:
                    code = ''.join(part[0] for part in record.status.split('_'))
                    css_class = record.status.lower()
                
                # Count stats
                if record.status == Attendance.Status.PRESENT:
                    emp_present += 1
                elif record.status == Attendance.Status.LATE:
                    emp_late += 1
                elif record.status == Attendance.Status.ABSENT:
                    emp_absent += 1
                elif record.status == Attendance.Status.ON_LEAVE:
                    emp_leave += 1
                elif record.status == Attendance.Status.HALF_DAY:
                    emp_half_day += 1
                
                if record.working_hours:
                    total_work_hours += float(record.working_hours)
            else:
                # No attendance record exists
                if is_holiday:
                    # Holiday - mark as H
                    code, css_class = ('H', 'holiday')
                elif day_info['date'] in leave_dates:
                    # Has approved leave
                    code, css_class = ('Lv', 'on_leave')
                    if day_info['date'] <= today:
                        emp_leave += 1
                elif is_sunday:
                    # Sunday - default to blank
                    code, css_class = ('', '')
                elif day_info['date'] <= today:
                    # Past date with no record - default to Present
                    code, css_class = ('P', 'present')
                    emp_present += 1
                else:
                    # Future date - show blank
                    code, css_class = ('', '')
            
            row_statuses.append({
                'code': code, 
                'css_class': css_class,
                'date': day_info['date'],
                'is_sunday': is_sunday,
                'is_holiday': is_holiday,
                'holiday_name': day_info.get('holiday_name', ''),
            })
        
        # Calculate attendance percentage (excluding holidays, sundays, future dates)
        working_days = sum(1 for d in month_days if not d.get('is_holiday') and not d.get('is_sunday') and d['date'] <= today)
        attendance_percentage = round((emp_present / working_days * 100), 1) if working_days > 0 else 0
        
        attendance_matrix.append({
            'employee': employee,
            'statuses': row_statuses,
            'stats': {
                'present': emp_present,
                'late': emp_late,
                'absent': emp_absent,
                'leave': emp_leave,
                'half_day': emp_half_day,
                'total_hours': round(total_work_hours, 2),
                'percentage': attendance_percentage,
                'working_days': working_days,
            }
        })

    # CSV export
    if request.GET.get('format') == 'csv':
        view_type = request.GET.get('view', 'daily')
        
        if view_type == 'monthly':
            # Export monthly matrix
            filename = f"attendance_monthly_{selected_month.strftime('%Y%m')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            # Add UTF-8 BOM for Excel to properly recognize encoding
            response.write('\ufeff')
            writer = csv.writer(response)
            
            # Header row 1 - Day names
            header_days = ['Employee'] + [day['day_label'] for day in month_days]
            writer.writerow(header_days)
            
            # Header row 2 - Day numbers
            header_dates = [''] + [str(day['day_number']) for day in month_days]
            writer.writerow(header_dates)
            
            # Data rows
            for row in attendance_matrix:
                row_data = [row['employee'].get_full_name()]
                row_data.extend([cell['code'] if cell['code'] else '-' for cell in row['statuses']])
                writer.writerow(row_data)
        else:
            # Export daily records
            filename = f"attendance_daily_{selected_date.strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            # Add UTF-8 BOM for Excel to properly recognize encoding
            response.write('\ufeff')
            writer = csv.writer(response)
            writer.writerow(['Employee', 'Email', 'Date', 'Check In', 'Check Out', 'Status', 'Working Hours', 'Notes'])
            for record in attendance_records:
                writer.writerow([
                    record.employee.get_full_name(),
                    record.employee.email,
                    record.date.strftime('%Y-%m-%d') if record.date else '',
                    record.check_in.strftime('%H:%M:%S') if record.check_in else '',
                    record.check_out.strftime('%H:%M:%S') if record.check_out else '',
                    record.get_status_display(),
                    record.working_hours,
                    record.notes or '',
                ])
        return response

    # Get company settings and holidays
    current_year = today.year
    from blu_staff.apps.accounts.models import CompanyAttendanceSettings, CompanyHoliday
    try:
        attendance_settings = CompanyAttendanceSettings.objects.get(company=company)
        year_range_past = attendance_settings.year_range_past
        year_range_future = attendance_settings.year_range_future
        expected_work_hours = float(attendance_settings.expected_work_hours)
        overtime_threshold = float(attendance_settings.overtime_threshold)
    except CompanyAttendanceSettings.DoesNotExist:
        year_range_past = 2
        year_range_future = 2
        expected_work_hours = 8.0
        overtime_threshold = 8.0
    year_range = range(current_year - year_range_past, current_year + year_range_future + 1)
    
    # Month names
    month_choices = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    
    # Generate trends data for chart (selected month)
    import json
    from calendar import monthrange
    trends_labels = []
    trends_present = []
    trends_late = []
    trends_absent = []
    
    # Get number of days in selected month
    _, num_days = monthrange(selected_month.year, selected_month.month)
    
    # Loop through each day of the selected month
    for day in range(1, num_days + 1):
        trend_date = date(selected_month.year, selected_month.month, day)
        trends_labels.append(trend_date.strftime('%b %d'))
        
        day_attendance = Attendance.objects.filter(
            employee__in=employees,
            date=trend_date
        )
        trends_present.append(day_attendance.filter(status=Attendance.Status.PRESENT).count())
        trends_late.append(day_attendance.filter(status=Attendance.Status.LATE).count())
        trends_absent.append(day_attendance.filter(status=Attendance.Status.ABSENT).count())
    
    trends_data = json.dumps({
        'labels': trends_labels,
        'present': trends_present,
        'late': trends_late,
        'absent': trends_absent,
    })
    
    context = {
        'total_employees': employees.count(),
        'present_count': present_count,
        'late_count': late_count,
        'on_leave_count': on_leave_count,
        'half_day_count': half_day_count,
        'absent_count': absent_count,
        'pending_leaves': pending_leaves,
        'selected_date': selected_date,
        'selected_status': status_filter or '',
        'selected_employee': employee_filter_id or '',
        'selected_month': selected_month,
        'selected_year': selected_month.year,
        'selected_month_num': selected_month.month,
        'year_range': year_range,
        'month_choices': month_choices,
        'attendance_records': attendance_records,
        'employee_options': employees.order_by('first_name', 'last_name'),
        'status_choices': Attendance.Status.choices,
        'total_hours': round(total_hours, 2),
        'company': company,
        'month_days': month_days,
        'attendance_matrix': attendance_matrix,
        'status_legend': status_legend,
        'search_query': search_query,
        'holidays': list(holidays),
        'expected_work_hours': expected_work_hours,
        'overtime_threshold': overtime_threshold,
        'trends_data': trends_data,
    }
    context.update(_get_employer_nav_context(request.user))

    return render(request, 'ems/attendance_dashboard.html', context)

@login_required
def update_attendance_status(request):
    """AJAX endpoint to update attendance status from monthly matrix"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    from django.http import JsonResponse
    from datetime import datetime
    
    try:
        employee_id = request.POST.get('employee_id')
        date_str = request.POST.get('date')
        status = request.POST.get('status')
        
        if not all([employee_id, date_str]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        # Parse date
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get employee
        employee = User.objects.get(id=employee_id)
        
        # Check company access
        company = _get_user_company(request.user)
        if employee.company != company:
            return JsonResponse({'success': False, 'error': 'Access denied'})
        
        # Get or create attendance record
        attendance, created = Attendance.objects.get_or_create(
            employee=employee,
            date=attendance_date,
            defaults={'status': status if status else Attendance.Status.PRESENT}
        )
        
        if not created and status:
            attendance.status = status
            attendance.save()
        elif not created and not status:
            # Delete if setting to blank
            attendance.delete()
            return JsonResponse({'success': True, 'message': 'Attendance record removed'})
        
        return JsonResponse({'success': True, 'message': 'Attendance updated successfully'})
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def bulk_update_attendance(request):
    """AJAX endpoint to bulk update attendance status"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    import json
    from django.http import JsonResponse
    from datetime import datetime
    
    try:
        data = json.loads(request.body)
        employees_data = data.get('employees', [])
        status = data.get('status')
        
        if not employees_data or not status:
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        company = _get_user_company(request.user)
        updated_count = 0
        
        for emp_data in employees_data:
            employee_id = emp_data.get('employee_id')
            date_str = emp_data.get('date')
            
            if not employee_id or not date_str:
                continue
            
            try:
                attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                employee = User.objects.get(id=employee_id, company=company)
                
                attendance, created = Attendance.objects.get_or_create(
                    employee=employee,
                    date=attendance_date,
                    defaults={'status': status}
                )
                
                if not created:
                    attendance.status = status
                    attendance.save()
                
                updated_count += 1
                
            except (User.DoesNotExist, ValueError):
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully updated {updated_count} attendance record(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def employer_edit_attendance(request, attendance_id):
    """Edit attendance record for employers"""
    if not (
        request.user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']
        or getattr(request.user, 'is_employer_admin', False)
    ):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.attendance.models import Attendance
    from django.contrib.auth import get_user_model
    from datetime import datetime

    User = get_user_model()
    company = _get_user_company(request.user)

    try:
        attendance = Attendance.objects.select_related('employee').get(id=attendance_id, employee__company=company)
    except Attendance.DoesNotExist:
        messages.error(request, 'Attendance record not found or access denied.')
        return redirect('attendance_dashboard')

    if request.method == 'POST':
        check_in_str = request.POST.get('check_in')
        check_out_str = request.POST.get('check_out')
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')

        try:
            if check_in_str:
                attendance.check_in = datetime.strptime(f"{attendance.date} {check_in_str}", '%Y-%m-%d %H:%M')
            if check_out_str:
                attendance.check_out = datetime.strptime(f"{attendance.date} {check_out_str}", '%Y-%m-%d %H:%M')
            if status:
                attendance.status = status
            attendance.notes = notes
            attendance.save()
            messages.success(request, 'Attendance record updated successfully.')
            return redirect('attendance_dashboard')
        except Exception as e:
            messages.error(request, f'Error updating attendance: {str(e)}')

    context = {
        'attendance': attendance,
        'status_choices': Attendance.Status.choices,
        'company': company,
    }
    return render(request, 'ems/employer_edit_attendance.html', context)

@login_required
def employer_leave_action(request, leave_id):
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or getattr(request.user, 'is_employer_admin', False)
    is_hr = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'HR'
    )
    is_supervisor = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'SUPERVISOR'
    )
    # If HR hits this endpoint with view=detail, redirect to the HR-friendly detail view
    if request.method != 'POST' and request.GET.get('view') == 'detail' and is_hr:
        return redirect('leave_detail_view', leave_id=leave_id)

    if not (is_admin or is_hr or is_supervisor):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.attendance.models import LeaveRequest
    from django.utils import timezone

    company = _get_user_company(request.user)

    try:
        leave_request = LeaveRequest.objects.select_related('employee', 'employee__employee_profile').get(id=leave_id, employee__company=company)
    except LeaveRequest.DoesNotExist:
        messages.error(request, 'Leave request not found or access denied.')
        return redirect('approval_center')

    # Supervisors can only act on their direct reports
    if is_supervisor:
        supervisor_of = getattr(getattr(leave_request.employee, 'employee_profile', None), 'supervisor', None)
        if supervisor_of != request.user:
            return render(request, 'ems/unauthorized.html')

    # Handle both GET and POST requests
    action = request.POST.get('action') or request.GET.get('action')
    rejection_reason = request.POST.get('reason') or request.GET.get('reason', '')

    if action in ('approve', 'APPROVED'):
        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.approved_by = request.user
        leave_request.approved_at = timezone.now()
        leave_request.save()
        messages.success(request, f'Leave request approved for {leave_request.employee.get_full_name()}.')
        
        # Create in-app notification for employee
        try:
            from blu_staff.apps.notifications.models import Notification
            if leave_request.employee:
                Notification.objects.create(
                    recipient=leave_request.employee,
                    sender=request.user,
                    title='Leave Request Approved',
                    message=f'Your {leave_request.get_leave_type_display()} leave from {leave_request.start_date} to {leave_request.end_date} has been approved.',
                    notification_type='SUCCESS',
                    category='leave',
                    link='/leave/',
                )
        except Exception:
            pass
        
        # Notify all connected integrations
        try:
            from integrations.integration_service import notify_all_channels
            notify_all_channels(company, 'leave_approved', {
                'title': 'Leave Request Approved',
                'employee': leave_request.employee.get_full_name(),
                'leave_type': leave_request.get_leave_type_display(),
                'start_date': str(leave_request.start_date),
                'end_date': str(leave_request.end_date),
                'message': f'{leave_request.employee.get_full_name()}\'s {leave_request.get_leave_type_display()} leave ({leave_request.start_date} to {leave_request.end_date}) has been approved.',
                'sms_text': f'Your {leave_request.get_leave_type_display()} leave ({leave_request.start_date} to {leave_request.end_date}) has been approved.',
            }, employee=leave_request.employee)
        except Exception:
            pass  # Don't block leave approval if notification fails
    elif action in ('reject', 'REJECTED'):
        if rejection_reason or action == 'REJECTED':
            leave_request.status = LeaveRequest.Status.REJECTED
            leave_request.approved_by = request.user
            leave_request.rejection_reason = rejection_reason
            leave_request.save()
            messages.success(request, f'Leave request rejected for {leave_request.employee.get_full_name()}.')
            
            # Create in-app notification for employee
            try:
                from blu_staff.apps.notifications.models import Notification
                if leave_request.employee:
                    Notification.objects.create(
                        recipient=leave_request.employee,
                        sender=request.user,
                        title='Leave Request Rejected',
                        message=f'Your {leave_request.get_leave_type_display()} leave from {leave_request.start_date} to {leave_request.end_date} has been rejected. Reason: {rejection_reason}',
                        notification_type='WARNING',
                        category='leave',
                        link='/leave/',
                    )
            except Exception:
                pass
            
            # Notify employee of rejection
            try:
                from integrations.integration_service import notify_all_channels
                notify_all_channels(company, 'leave_rejected', {
                    'title': 'Leave Request Rejected',
                    'employee': leave_request.employee.get_full_name(),
                    'leave_type': leave_request.get_leave_type_display(),
                    'reason': rejection_reason,
                    'message': f'{leave_request.employee.get_full_name()}\'s {leave_request.get_leave_type_display()} leave has been rejected. Reason: {rejection_reason}',
                    'sms_text': f'Your {leave_request.get_leave_type_display()} leave request has been rejected. Reason: {rejection_reason}',
                }, employee=leave_request.employee)
            except Exception:
                pass
        else:
            messages.error(request, 'Rejection reason is required.')

    # HR/Admin: return to approvals dashboard
    return redirect('approval_center')


@login_required
def leave_detail_view(request, leave_id):
    """Read-only leave detail for HR/Admin without redirecting to My Leave."""
    is_hr = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'HR'
    )
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or getattr(request.user, 'is_employer_admin', False)

    if not (is_hr or is_admin):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.attendance.models import LeaveRequest
    company = _get_user_company(request.user)
    try:
        leave_request = LeaveRequest.objects.select_related('employee').get(id=leave_id, employee__company=company)
    except LeaveRequest.DoesNotExist:
        messages.error(request, 'Leave request not found or access denied.')
        return redirect('approval_center')

    # Admins see employer base; HR sees HR (employee base)
    if is_admin and not is_hr:
        base_template = 'ems/base_employer.html'
    else:
        base_template = 'ems/base_employee.html'
    return render(request, 'ems/leave_detail.html', {
        'leave': leave_request,
        'company': company,
        'base_template': base_template,
    })

@login_required
def bulk_approve_leave(request):
    """Bulk approve leave requests"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    import json
    from blu_staff.apps.attendance.models import LeaveRequest
    from django.utils import timezone
    
    try:
        data = json.loads(request.body)
        leave_ids = data.get('leave_ids', [])
        
        if not leave_ids:
            return JsonResponse({'success': False, 'error': 'No leave requests selected'})
        
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        approved_count = 0
        
        for leave_id in leave_ids:
            try:
                leave_req = LeaveRequest.objects.get(id=leave_id, employee__company=company)
                leave_req.status = LeaveRequest.Status.APPROVED
                leave_req.approved_by = request.user
                leave_req.approved_at = timezone.now()
                leave_req.save()
                approved_count += 1
            except LeaveRequest.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully approved {approved_count} leave request(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def bulk_reject_leave(request):
    """Bulk reject leave requests"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    import json
    from blu_staff.apps.attendance.models import LeaveRequest
    
    try:
        data = json.loads(request.body)
        leave_ids = data.get('leave_ids', [])
        reason = data.get('reason', '')
        
        if not leave_ids:
            return JsonResponse({'success': False, 'error': 'No leave requests selected'})
        
        if not reason:
            return JsonResponse({'success': False, 'error': 'Rejection reason is required'})
        
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        rejected_count = 0
        
        for leave_id in leave_ids:
            try:
                leave_req = LeaveRequest.objects.get(id=leave_id, employee__company=company)
                leave_req.status = LeaveRequest.Status.REJECTED
                leave_req.approved_by = request.user
                leave_req.rejection_reason = reason
                leave_req.save()
                rejected_count += 1
            except LeaveRequest.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully rejected {rejected_count} leave request(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def employee_attendance_view(request):
    """Employee's personal attendance history with clock-in/out"""
    # Allow employees and users with employee profiles (accountants, supervisors, etc.)
    has_profile = hasattr(request.user, 'employee_profile') and request.user.employee_profile
    is_employee = getattr(request.user, 'role', '') == 'EMPLOYEE'
    
    # Allow access if user has employee profile OR is an employee OR is admin/employer_admin
    if not (has_profile or is_employee or request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.attendance.models import Attendance
    from datetime import date, timedelta

    today = date.today()
    now = timezone.now()

    # Handle clock-in / clock-out POST
    if request.method == 'POST':
        action = request.POST.get('action')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        location = request.POST.get('location', '')
        
        # Get company and employee profile for geofencing check
        company = getattr(request.user, 'company', None)
        employee_profile = getattr(request.user, 'employee_profile', None)
        
        # Check if GPS is required for this employee
        require_gps = employee_profile and getattr(employee_profile, 'require_gps_attendance', True)
        
        # Geofence validation (only if GPS is required for this employee)
        if company and company.enforce_geofencing and not company.allow_remote_attendance and require_gps:
            if not latitude or not longitude:
                messages.error(request, 'GPS location is required for attendance. Please enable location services.')
                return redirect('employee_attendance_view')
            
            # Determine which location to use: employee's branch or company office
            office_lat = None
            office_lon = None
            geofence_radius = company.geofence_radius_meters
            location_name = "office"
            
            # Priority 1: Employee's assigned branch location
            if employee_profile and employee_profile.branch:
                branch = employee_profile.branch
                if branch.latitude and branch.longitude:
                    office_lat = branch.latitude
                    office_lon = branch.longitude
                    geofence_radius = branch.geofence_radius_meters
                    location_name = f"{branch.name} branch"
            
            # Priority 2: Company head office location
            if not office_lat and company.office_latitude and company.office_longitude:
                office_lat = company.office_latitude
                office_lon = company.office_longitude
                geofence_radius = company.geofence_radius_meters
                location_name = "office"
            
            # Validate if we have a location to check against
            if office_lat and office_lon:
                try:
                    employee_lat = Decimal(latitude)
                    employee_lon = Decimal(longitude)
                    
                    distance = calculate_distance_meters(
                        office_lat, office_lon,
                        employee_lat, employee_lon
                    )
                    
                    if distance > geofence_radius:
                        messages.error(
                            request,
                            f'You are {int(distance)}m from the {location_name}. You must be within {geofence_radius}m to clock in/out.'
                        )
                        return redirect('employee_attendance_view')
                except Exception as e:
                    messages.error(request, 'Invalid GPS coordinates. Please try again.')
                    return redirect('employee_attendance_view')
        
        if action == 'clock_in':
            defaults = {'check_in': now, 'status': Attendance.Status.PRESENT}
            if latitude and longitude:
                try:
                    defaults['latitude'] = Decimal(latitude)
                    defaults['longitude'] = Decimal(longitude)
                    defaults['location'] = location
                except Exception:
                    pass
            
            att, created = Attendance.objects.get_or_create(
                employee=request.user,
                date=today,
                defaults=defaults,
            )
            if not created and not att.check_in:
                att.check_in = now
                if latitude and longitude:
                    try:
                        att.latitude = Decimal(latitude)
                        att.longitude = Decimal(longitude)
                        att.location = location
                    except Exception:
                        pass
                att.save()
                messages.success(request, 'Clocked in successfully!')
            elif created:
                messages.success(request, 'Clocked in successfully!')
            else:
                messages.info(request, 'You have already clocked in today.')
        elif action == 'clock_out':
            att = Attendance.objects.filter(employee=request.user, date=today).first()
            if att and att.check_in and not att.check_out:
                att.check_out = now
                # Optionally update location on checkout if GPS available
                if latitude and longitude and not att.latitude:
                    try:
                        att.latitude = Decimal(latitude)
                        att.longitude = Decimal(longitude)
                        att.location = location
                    except Exception:
                        pass
                att.save()
                messages.success(request, f'Clocked out successfully! Worked {att.working_hours} hours.')
            elif att and att.check_out:
                messages.info(request, 'You have already clocked out today.')
            else:
                messages.warning(request, 'You need to clock in first.')
        return redirect('employee_attendance_view')

    # Today's attendance record
    today_attendance = Attendance.objects.filter(employee=request.user, date=today).first()

    # Default to current month
    month_filter = request.GET.get('month')
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
        except Exception:
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    else:
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

    attendance_records = Attendance.objects.filter(
        employee=request.user,
        date__range=[start_date, end_date]
    ).order_by('-date')

    # Summary stats
    total_days = attendance_records.count()
    present_count = attendance_records.filter(status=Attendance.Status.PRESENT).count()
    late_count = attendance_records.filter(status=Attendance.Status.LATE).count()
    absent_count = attendance_records.filter(status=Attendance.Status.ABSENT).count()
    half_day_count = attendance_records.filter(status=Attendance.Status.HALF_DAY).count()
    on_leave_count = attendance_records.filter(status=Attendance.Status.ON_LEAVE).count()
    total_hours = sum(record.working_hours for record in attendance_records)
    avg_hours = round(total_hours / total_days, 1) if total_days > 0 else 0

    # Attendance rate for the month
    working_days_in_month = max(1, min(today.day, (end_date - start_date).days + 1))
    attendance_rate = round(((present_count + late_count + half_day_count) / working_days_in_month) * 100, 1) if working_days_in_month > 0 else 0

    # Weekly trend (last 7 days)
    weekly_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_att = Attendance.objects.filter(employee=request.user, date=d).first()
        weekly_trend.append({
            'date': d,
            'day': d.strftime('%a'),
            'status': day_att.status if day_att else None,
            'hours': day_att.working_hours if day_att else 0,
        })

    # Get company and employee geofencing settings
    company = getattr(request.user, 'company', None)
    employee_profile = getattr(request.user, 'employee_profile', None)
    
    geofencing_enabled = False
    geofence_radius = 100
    office_location = None
    location_name = "office"
    require_gps = employee_profile and getattr(employee_profile, 'require_gps_attendance', True)
    
    if company and require_gps:
        geofencing_enabled = company.enforce_geofencing and not company.allow_remote_attendance
        
        # Determine which location to use: employee's branch or company office
        if employee_profile and employee_profile.branch:
            branch = employee_profile.branch
            if branch.latitude and branch.longitude:
                office_location = {
                    'latitude': float(branch.latitude),
                    'longitude': float(branch.longitude)
                }
                geofence_radius = branch.geofence_radius_meters
                location_name = f"{branch.name} branch"
        
        # Fallback to company head office
        if not office_location and company.office_latitude and company.office_longitude:
            office_location = {
                'latitude': float(company.office_latitude),
                'longitude': float(company.office_longitude)
            }
            geofence_radius = company.geofence_radius_meters
            location_name = "office"
    
    context = {
        'attendance_records': attendance_records,
        'start_date': start_date,
        'end_date': end_date,
        'today': today,
        'now': now,
        'today_attendance': today_attendance,
        'total_days': total_days,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'half_day_count': half_day_count,
        'on_leave_count': on_leave_count,
        'total_hours': round(total_hours, 2),
        'avg_hours': avg_hours,
        'attendance_rate': attendance_rate,
        'weekly_trend': weekly_trend,
        'geofencing_enabled': geofencing_enabled,
        'geofence_radius': geofence_radius,
        'office_location': office_location,
    }
    return render(request, 'ems/employee_attendance.html', context)

@login_required
def employee_leave_request(request):
    """Employee leave request submission"""
    if request.user.role != 'EMPLOYEE':
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.attendance.models import LeaveRequest
    from datetime import datetime

    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            if end_date < start_date:
                messages.error(request, 'End date must be after start date.')
            else:
                lr = LeaveRequest.objects.create(
                    employee=request.user,
                    leave_type=leave_type,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                    status=LeaveRequest.Status.PENDING
                )
                messages.success(request, 'Leave request submitted successfully!')
                
                # Create in-app notifications for admins/HR
                try:
                    from blu_staff.apps.notifications.models import Notification
                    emp_company = getattr(request.user, 'company', None)
                    if emp_company:
                        # Get all admins and HR staff
                        from blu_staff.apps.accounts.models import User
                        admins = User.objects.filter(
                            company=emp_company,
                            role__in=['EMPLOYER_ADMIN', 'ADMINISTRATOR']
                        )
                        for admin in admins:
                            Notification.objects.create(
                                recipient=admin,
                                sender=request.user,
                                title='New Leave Request',
                                message=f'{request.user.get_full_name()} submitted {lr.get_leave_type_display()} leave from {start_date} to {end_date}',
                                notification_type='INFO',
                                category='leave',
                                link='/approval-center/',
                            )
                except Exception:
                    pass
                
                # Notify managers via connected integrations
                try:
                    emp_company = getattr(request.user, 'company', None)
                    if emp_company:
                        from integrations.integration_service import notify_all_channels
                        notify_all_channels(emp_company, 'leave_request', {
                            'title': 'New Leave Request',
                            'employee': request.user.get_full_name(),
                            'leave_type': lr.get_leave_type_display(),
                            'start_date': str(start_date),
                            'end_date': str(end_date),
                            'reason': reason,
                            'message': f'{request.user.get_full_name()} has submitted a {lr.get_leave_type_display()} leave request from {start_date} to {end_date}.',
                        })
                except Exception:
                    pass
                return redirect('employee_leave_request')
        except Exception as e:
            messages.error(request, f'Error submitting leave request: {str(e)}')

    # Get employee's leave requests
    leave_requests = LeaveRequest.objects.filter(
        employee=request.user
    ).order_by('-created_at')
    
    # Calculate leave statistics
    from datetime import date
    from django.db.models import Sum, Q
    
    current_year = date.today().year
    
    # Leave statistics for current year
    year_leave_requests = leave_requests.filter(start_date__year=current_year)
    
    total_requests = leave_requests.count()
    pending_count = leave_requests.filter(status=LeaveRequest.Status.PENDING).count()
    approved_count = leave_requests.filter(status=LeaveRequest.Status.APPROVED).count()
    rejected_count = leave_requests.filter(status=LeaveRequest.Status.REJECTED).count()
    
    # Calculate total days used (approved leaves only)
    approved_leaves = year_leave_requests.filter(status=LeaveRequest.Status.APPROVED)
    total_days_used = sum([leave.duration for leave in approved_leaves])
    
    # Get employee profile for leave balance
    try:
        annual_leave_balance = 21  # Default annual leave days
        sick_leave_balance = 14   # Default sick leave days
        
        if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
            profile = request.user.employee_profile
            # If you have leave balance fields in profile, use them
            if hasattr(profile, 'annual_leave_balance'):
                annual_leave_balance = profile.annual_leave_balance
            if hasattr(profile, 'sick_leave_balance'):
                sick_leave_balance = profile.sick_leave_balance
        
        # Calculate remaining balance
        annual_days_used = sum([leave.duration for leave in approved_leaves.filter(leave_type='ANNUAL')])
        sick_days_used = sum([leave.duration for leave in approved_leaves.filter(leave_type='SICK')])
        
        annual_remaining = annual_leave_balance - annual_days_used
        sick_remaining = sick_leave_balance - sick_days_used
        
    except:
        annual_remaining = 21
        sick_remaining = 14
        total_days_used = 0

    context = {
        'leave_requests': leave_requests,
        'leave_type_choices': LeaveRequest.LeaveType.choices,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'total_days_used': total_days_used,
        'annual_remaining': annual_remaining,
        'sick_remaining': sick_remaining,
        'current_year': current_year,
    }
    return render(request, 'ems/employee_leave_request.html', context)

@login_required
def superadmin_dashboard(request):
    """SuperAdmin dashboard with real system metrics"""
    # If a platform user (non-superadmin) hits this view, send them to their portal
    if getattr(request.user, 'platform_role', None) and not getattr(request.user, 'is_superadmin', False):
        return redirect('dashboard_redirect')

    # Check if user is SuperAdmin (from SuperAdmin model)
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.accounts.models import Company, User, CompanyRegistrationRequest
    from blu_billing.models import CompanySubscription, SubscriptionPlan, Invoice, UsageMetric
    from blu_support.models import SupportTicket, SupportTeam
    from datetime import date, timedelta
    from django.db.models import Sum, Count, Q

    today = date.today()
    trial_window_end = today + timedelta(days=30)
    month_start = today.replace(day=1)

    # System-wide statistics
    total_companies = Company.objects.count()
    total_users = User.objects.count()
    total_employees = User.objects.filter(role='EMPLOYEE').count()

    # Subscription metrics (real data)
    try:
        # Active subscriptions by status
        subscription_stats = CompanySubscription.objects.aggregate(
            total_active=Count('id', filter=Q(status='ACTIVE')),
            total_trial=Count('id', filter=Q(status='TRIAL')),
            total_suspended=Count('id', filter=Q(status='SUSPENDED')),
            total_expired=Count('id', filter=Q(status='EXPIRED')),
        )
        
        active_subscriptions = subscription_stats['total_active']
        trial_subscriptions = subscription_stats['total_trial']
        suspended_subscriptions = subscription_stats['total_suspended']
        expired_subscriptions = subscription_stats['total_expired']
        
        # Expiring subscriptions
        trials_expiring_30 = CompanySubscription.objects.filter(
            status='TRIAL',
            trial_ends_at__isnull=False,
            trial_ends_at__lte=trial_window_end
        ).count()
        
        licenses_expiring_30 = CompanySubscription.objects.filter(
            status='ACTIVE',
            current_period_end__isnull=False,
            current_period_end__lte=trial_window_end
        ).count()
        
        # Revenue metrics (real)
        revenue_this_month = Invoice.objects.filter(
            status='PAID',
            paid_at__year=today.year,
            paid_at__month=today.month
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        pending_revenue = Invoice.objects.filter(status='PENDING').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Usage metrics
        total_storage_used = UsageMetric.objects.filter(
            metric_type='storage',
            metric_date=today
        ).aggregate(total=Sum('metric_value'))['total'] or 0
        
        api_calls_today = UsageMetric.objects.filter(
            metric_type='api_calls',
            metric_date=today
        ).aggregate(total=Sum('metric_value'))['total'] or 0
        
    except Exception:
        # Fallback if subscription models don't exist yet
        active_subscriptions = Company.objects.filter(is_active=True, is_trial=False).count()
        trial_subscriptions = Company.objects.filter(is_active=True, is_trial=True).count()
        suspended_subscriptions = 0
        expired_subscriptions = 0
        trials_expiring_30 = Company.objects.filter(
            is_active=True,
            is_trial=True,
            trial_ends_at__isnull=False,
            trial_ends_at__lte=trial_window_end,
        ).count()
        licenses_expiring_30 = Company.objects.filter(
            is_active=True,
            is_trial=False,
            license_expiry__isnull=False,
            license_expiry__lte=trial_window_end,
        ).count()
        revenue_this_month = 0
        pending_revenue = 0
        try:
            from blu_staff.apps.documents.models import EmployeeDocument
            from django.db.models import Sum as _Sum
            _bytes = EmployeeDocument.objects.aggregate(total=_Sum('file_size'))['total'] or 0
            total_storage_used = round(_bytes / (1024 ** 3), 2)
        except Exception:
            total_storage_used = 0
        api_calls_today = 0

    # Pending company registration requests
    pending_company_requests = CompanyRegistrationRequest.objects.filter(status='PENDING').count()

    # Platform-level admin counts
    total_superadmins = User.objects.filter(role='SUPERADMIN').count()
    total_company_admins = User.objects.filter(role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']).count()

    # Support metrics
    try:
        open_tickets = SupportTicket.objects.filter(
            status__in=['OPEN', 'IN_PROGRESS']
        ).count()
        
        urgent_tickets = SupportTicket.objects.filter(
            priority='URGENT',
            status__in=['OPEN', 'IN_PROGRESS']
        ).count()
        
        tickets_resolved_today = SupportTicket.objects.filter(
            status='RESOLVED',
            updated_at__date=today
        ).count()
        
        avg_resolution_time = SupportTicket.objects.filter(
            status='RESOLVED'
        ).aggregate(
            avg_time=Avg(F('updated_at') - F('created_at'))
        )['avg_time']
    except Exception:
        open_tickets = 0
        urgent_tickets = 0
        tickets_resolved_today = 0
        avg_resolution_time = None

    # New companies this month
    new_companies_this_month = Company.objects.filter(
        created_at__gte=month_start
    ).count()

    context = {
        'user': request.user,
        'total_companies': total_companies,
        'total_users': total_users,
        'total_employees': total_employees,
        
        # Subscription metrics
        'active_subscriptions': active_subscriptions,
        'trial_subscriptions': trial_subscriptions,
        'suspended_subscriptions': suspended_subscriptions,
        'expired_subscriptions': expired_subscriptions,
        'trials_expiring_30': trials_expiring_30,
        'licenses_expiring_30': licenses_expiring_30,
        
        # Revenue metrics
        'revenue_this_month': revenue_this_month,
        'pending_revenue': pending_revenue,
        
        # Usage metrics
        'total_storage_used': total_storage_used,
        'api_calls_today': api_calls_today,
        
        # Support metrics
        'open_tickets': open_tickets,
        'urgent_tickets': urgent_tickets,
        'tickets_resolved_today': tickets_resolved_today,
        'avg_resolution_time': avg_resolution_time,
        
        # Other metrics
        'pending_company_requests': pending_company_requests,
        'total_superadmins': total_superadmins,
        'total_company_admins': total_company_admins,
        'new_companies_this_month': new_companies_this_month,
    }

    return render(request, 'ems/superadmin_dashboard.html', context)


@login_required
def superadmin_billing_overview(request):
    """System Owner billing overview across all tenant companies"""
    # Only System Owners should see this
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    # Respect feature flag
    system_settings = SystemSettings.get_solo()
    if not getattr(system_settings, 'enable_billing_module', True):
        messages.error(request, 'Billing module is currently disabled in System Settings.')
        return redirect('superadmin_dashboard')

    today = date.today()
    window_end = today + timedelta(days=30)

    # All approved, active companies
    companies = Company.objects.filter(is_approved=True, is_active=True).select_related('registration_request')

    total_companies = companies.count()

    # Trial / paid breakdown
    trial_qs = companies.filter(is_trial=True)
    paid_qs = companies.filter(is_trial=False)

    trial_ids = list(trial_qs.values_list('id', flat=True))

    # Expiring soon (trial or license)
    expiring_soon_ids = list(
        companies.filter(
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

    # Expired
    expired_ids = list(
        companies.filter(
            Q(is_trial=True, trial_ends_at__isnull=False, trial_ends_at__date__lt=today)
            | Q(
                is_trial=False,
                license_expiry__isnull=False,
                license_expiry__lt=today,
            )
        ).values_list('id', flat=True)
    )

    # Active paid (non-trial and not expired)
    active_paid_qs = paid_qs.filter(
        Q(license_expiry__isnull=True) | Q(license_expiry__gt=today)
    )

    # At-risk tenants: expiring soon or expired
    at_risk_companies = companies.filter(
        Q(id__in=expired_ids) | Q(id__in=expiring_soon_ids)
    ).order_by('name')

    # Plan and billing breakdowns
    plan_breakdown = (
        companies.values('subscription_plan')
        .annotate(count=Count('id'))
        .order_by('subscription_plan')
    )

    billing_breakdown = (
        companies.values('registration_request__billing_preference')
        .annotate(count=Count('id'))
        .order_by('registration_request__billing_preference')
    )

    # Total storage across all companies
    try:
        from blu_staff.apps.documents.models import EmployeeDocument
        from django.db.models import Sum as _Sum
        total_storage_bytes = EmployeeDocument.objects.aggregate(
            total=_Sum('file_size')
        )['total'] or 0
        total_storage = round(total_storage_bytes / (1024 ** 3), 2)
    except Exception:
        total_storage = 0

    context = {
        'user': request.user,
        'today': today,
        'total_companies': total_companies,
        'trial_count': len(trial_ids),
        'paid_count': paid_qs.count(),
        'expiring_soon_count': len(expiring_soon_ids),
        'expired_count': len(expired_ids),
        'active_paid_count': active_paid_qs.count(),
        'at_risk_companies': at_risk_companies,
        'plan_breakdown': plan_breakdown,
        'billing_breakdown': billing_breakdown,
        'plan_choices': CompanyRegistrationRequest.SubscriptionPlan.choices,
        'billing_choices': CompanyRegistrationRequest.BillingPreference.choices,
        'trial_ids': trial_ids,
        'expiring_soon_ids': expiring_soon_ids,
        'expired_ids': expired_ids,
        'total_storage': total_storage,
        'total_api_calls': 0,
    }

    return render(request, 'ems/superadmin_billing_overview.html', context)


def _require_platform_roles(user, roles):
    return getattr(user, 'platform_role', None) in roles or getattr(user, 'is_superadmin', False)


def superadmin_support_center(request):
    """Platform-wide support ticket overview for System Owner"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    tickets = SupportTicket.objects.select_related('company', 'created_by')

    # Filters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    company_filter = request.GET.get('company', '')
    search_query = request.GET.get('search', '')

    if status_filter:
        tickets = tickets.filter(status=status_filter)

    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)

    if company_filter:
        tickets = tickets.filter(company_id=company_filter)

    if search_query:
        tickets = tickets.filter(
            Q(subject__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(company__name__icontains=search_query)
            | Q(created_by__email__icontains=search_query)
        )

    tickets = tickets.order_by('-created_at')

    # Summary stats
    total_tickets = SupportTicket.objects.count()
    open_count = SupportTicket.objects.filter(status=SupportTicket.Status.OPEN).count()
    in_progress_count = SupportTicket.objects.filter(status=SupportTicket.Status.IN_PROGRESS).count()
    resolved_count = SupportTicket.objects.filter(status=SupportTicket.Status.RESOLVED).count()

    companies = Company.objects.filter(is_approved=True).order_by('name')

    context = {
        'user': request.user,
        'tickets': tickets,
        'total_tickets': total_tickets,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'status_choices': SupportTicket.Status.choices,
        'priority_choices': SupportTicket.Priority.choices,
        'companies': companies,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'company_filter': company_filter,
        'search_query': search_query,
    }

    return render(request, 'blu_support/superadmin_support_center.html', context)


# System-owner portals (non-tenant)
@login_required
def owner_billing_portal(request):
    if not _require_platform_roles(request.user, ['BILLING', 'OWNER']):
        return render(request, 'ems/unauthorized.html')
    from blu_staff.apps.accounts.models import Company, CompanyRegistrationRequest
    # Basic metrics using existing data (placeholder revenue calcs)
    companies = Company.objects.all()
    total_companies = companies.count()
    trials = companies.filter(is_trial=True).count()
    active_paid = companies.filter(is_trial=False, is_active=True).count()
    expiring_soon = companies.filter(license_expiry__isnull=False).count()
    pending_registrations = CompanyRegistrationRequest.objects.filter(status='PENDING').count()

    stats = {
        'mrr': 0,
        'arr': 0,
        'failed_invoices': 0,
        'expiring_cards': expiring_soon,
        'total_companies': total_companies,
        'trials': trials,
        'active_paid': active_paid,
        'pending_registrations': pending_registrations,
    }
    return render(request, 'ems/system_owner_billing.html', {'stats': stats})


@login_required
def owner_support_portal(request):
    if not _require_platform_roles(request.user, ['SUPPORT', 'OWNER']):
        return render(request, 'ems/unauthorized.html')
    tickets = SupportTicket.objects.all()
    summary = {
        'total': tickets.count(),
        'open': tickets.filter(status=SupportTicket.Status.OPEN).count(),
        'in_progress': tickets.filter(status=SupportTicket.Status.IN_PROGRESS).count(),
        'resolved': tickets.filter(status=SupportTicket.Status.RESOLVED).count(),
        'urgent': tickets.filter(priority=SupportTicket.Priority.URGENT).count(),
    }
    recent = tickets.select_related('company', 'created_by').order_by('-created_at')[:10]
    return render(request, 'ems/system_owner_support.html', {'summary': summary, 'recent_tickets': recent})


@login_required
def owner_registration_portal(request):
    if not _require_platform_roles(request.user, ['REGISTRATION', 'OWNER']):
        return render(request, 'ems/unauthorized.html')
    from blu_staff.apps.accounts.models import CompanyRegistrationRequest
    pending = CompanyRegistrationRequest.objects.filter(status='PENDING').order_by('-created_at')
    counts = {
        'pending': pending.count(),
        'approved': CompanyRegistrationRequest.objects.filter(status='APPROVED').count(),
        'rejected': CompanyRegistrationRequest.objects.filter(status='REJECTED').count(),
    }
    return render(request, 'ems/system_owner_registration.html', {'pending': pending[:10], 'counts': counts})


@login_required
def owner_account_manager_portal(request):
    if not _require_platform_roles(request.user, ['ACCOUNT_MANAGER', 'OWNER']):
        return render(request, 'ems/unauthorized.html')
    from blu_staff.apps.accounts.models import Company
    companies = Company.objects.order_by('name')[:20]
    summary = {
        'active': companies.filter(is_active=True).count(),
        'inactive': companies.filter(is_active=False).count(),
        'approved': companies.filter(is_approved=True).count(),
        'pending_approval': companies.filter(is_approved=False).count(),
    }
    return render(request, 'ems/system_owner_account_manager.html', {'companies': companies, 'summary': summary})


@login_required
def superadmin_settings(request):
    """Settings page for System Owner (SuperAdmin)"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    system_settings = SystemSettings.get_solo()

    tracked_fields = [
        'allow_public_company_registration',
        'default_subscription_plan',
        'registration_admin_email',
        'maintenance_mode',
        'maintenance_message',
        'enable_billing_module',
        'enable_support_module',
        'enable_analytics_module',
    ]

    if request.method == 'POST':
        old_values = {name: getattr(system_settings, name, None) for name in tracked_fields}
        settings_form = SystemSettingsForm(request.POST, instance=system_settings)
        if settings_form.is_valid():
            updated_settings = settings_form.save()

            changes = []
            for name, old in old_values.items():
                new = getattr(updated_settings, name, None)
                if old != new:
                    changes.append(f"{name}: {old} -> {new}")

            if changes:
                SystemSettingsAudit.objects.create(
                    system_settings=updated_settings,
                    changed_by=request.user if request.user.is_authenticated else None,
                    changes="\n".join(changes),
                )

            messages.success(request, 'System settings updated successfully.')
        else:
            messages.error(request, 'Please correct the errors in the system settings form.')
    else:
        settings_form = SystemSettingsForm(instance=system_settings)

    platform_staff = User.objects.filter(role='SUPERADMIN').order_by('date_joined')
    company_admins = User.objects.filter(
        role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
    ).select_related('company')

    audit_logs = SystemSettingsAudit.objects.select_related('changed_by').order_by('-changed_at')[:20]

    # Get real subscription and storage metrics
    try:
        from blu_billing.models import CompanySubscription
        active_subscriptions = CompanySubscription.objects.filter(status='ACTIVE').count()
    except:
        active_subscriptions = 0
    
    # Calculate real storage usage
    try:
        import os
        from django.conf import settings
        
        # Get database size (SQLite)
        db_size = 0
        if hasattr(settings, 'DATABASES') and 'default' in settings.DATABASES:
            db_path = settings.DATABASES['default'].get('NAME', '')
            if db_path and os.path.exists(db_path):
                db_size = os.path.getsize(db_path) / (1024 * 1024)  # Convert to MB
        
        # Get media files size
        media_size = 0
        if hasattr(settings, 'MEDIA_ROOT') and os.path.exists(settings.MEDIA_ROOT):
            for root, dirs, files in os.walk(settings.MEDIA_ROOT):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        media_size += os.path.getsize(file_path) / (1024 * 1024)  # Convert to MB
        
        total_storage_mb = db_size + media_size
        storage_usage_gb = round(total_storage_mb / 1024, 2) if total_storage_mb > 1024 else round(total_storage_mb, 2)
        storage_unit = 'GB' if total_storage_mb > 1024 else 'MB'
        
        # Calculate percentage (assuming 10GB as base for percentage calculation)
        base_storage_gb = 10
        storage_percentage = round((total_storage_mb / 1024 / base_storage_gb) * 100, 1)
        
    except Exception as e:
        storage_usage_gb = 'N/A'
        storage_unit = ''
        storage_percentage = 0

    context = {
        'user': request.user,
        'system_settings': system_settings,
        'system_settings_form': settings_form,
        'platform_staff': platform_staff,
        'company_admins': company_admins,
        'total_companies': Company.objects.count(),
        'total_admins': company_admins.count(),
        'audit_logs': audit_logs,
        'active_subscriptions': active_subscriptions,
        'storage_usage': f"{storage_usage_gb}{storage_unit}" if storage_usage_gb != 'N/A' else 'N/A',
        'storage_percentage': storage_percentage,
    }

    return render(request, 'ems/superadmin_settings.html', context)


@login_required
def employee_management(request):
    """Employee management dashboard for SuperAdmin"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.accounts.models import Company, User
    from blu_staff.apps.performance.models import PerformanceReview
    from datetime import date

    today = date.today()

    # Get all employees and companies
    employees = User.objects.filter(role='EMPLOYEE').select_related()
    companies = Company.objects.all()

    # Statistics
    total_employees = employees.count()
    active_employees = employees.filter(is_active=True).count()
    total_companies = companies.count()

    # Pending performance reviews - PERFORMANCE MODULE DISABLED
    # pending_reviews = PerformanceReview.objects.filter(
    #     review_date__gte=today
    # ).count()
    pending_reviews = 0

    # Prepare employee data for template
    employee_data = []
    for employee in employees:
        employee_info = {
            'id': employee.id,
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'email': employee.email,
            'phone': employee.phone,
            'role': employee.role,
            'is_active': employee.is_active,
            'date_joined': employee.date_joined,
            'company_name': None
        }

        # Try to get company name if employee belongs to a company
        try:
            if hasattr(employee, 'employee_profile') and employee.employee_profile:
                employee_info['company_name'] = employee.employee_profile.company.name if employee.employee_profile.company else None
        except:
            pass

        employee_data.append(employee_info)

    context = {
        'employees': employee_data,
        'companies': companies,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'total_companies': total_companies,
        'pending_reviews': pending_reviews,
        'today_date': today.strftime('%Y-%m-%d'),
    }

    return render(request, 'ems/employee_management.html', context)

@login_required
def analytics_dashboard(request):
    """Analytics and reporting dashboard for SuperAdmin"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    # Date range filter with validation
    today = date.today()
    start_date = request.GET.get('start_date', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', today.strftime('%Y-%m-%d'))
    
    try:
        start_date_obj = date.fromisoformat(start_date)
        end_date_obj = date.fromisoformat(end_date)
        # Ensure end date is not in the future
        end_date_obj = min(end_date_obj, today)
        # Ensure date range is not too large (max 1 year)
        if (end_date_obj - start_date_obj).days > 365:
            start_date_obj = end_date_obj - timedelta(days=365)
    except (ValueError, TypeError):
        start_date_obj = today - timedelta(days=30)
        end_date_obj = today

    # Filter by company if specified
    company_filter = request.GET.get('company')
    company = None
    if company_filter:
        try:
            company = Company.objects.get(id=company_filter)
        except (Company.DoesNotExist, ValueError):
            pass

    # Base querysets with date range
    attendance_qs = Attendance.objects.filter(date__range=[start_date_obj, end_date_obj])
    leave_qs = LeaveRequest.objects.filter(
        Q(start_date__lte=end_date_obj, end_date__gte=start_date_obj) |
        Q(start_date__range=[start_date_obj, end_date_obj]) |
        Q(end_date__range=[start_date_obj, end_date_obj])
    )
    
    # Apply company filter if selected
    if company:
        attendance_qs = attendance_qs.filter(employee__company=company)
        leave_qs = leave_qs.filter(employee__company=company)
        total_employees = User.objects.filter(role='EMPLOYEE', company=company).count()
    else:
        total_employees = User.objects.filter(role='EMPLOYEE').count()

    # ===== ATTENDANCE ANALYTICS =====
    # Daily attendance summary
    attendance_daily = attendance_qs.values('date').annotate(
        present=Count('id', filter=Q(status='PRESENT')),
        late=Count('id', filter=Q(status='LATE')),
        absent=Count('id', filter=Q(status='ABSENT')),
        on_leave=Count('id', filter=Q(status='ON_LEAVE')),
        total=Count('id')
    ).order_by('date')

    # Monthly attendance trend
    attendance_monthly = attendance_qs.annotate(
        month=ExtractMonth('date'),
        year=ExtractYear('date')
    ).values('year', 'month').annotate(
        present=Count('id', filter=Q(status='PRESENT')),
        late=Count('id', filter=Q(status='LATE')),
        absent=Count('id', filter=Q(status='ABSENT')),
        on_leave=Count('id', filter=Q(status='ON_LEAVE')),
        total=Count('id')
    ).order_by('year', 'month')

    # Calculate attendance rate over time
    attendance_rate = 0
    working_days = 0
    present_days = 0
    
    # Calculate working days in the period (excluding weekends)
    current_date = start_date_obj
    while current_date <= end_date_obj:
        if current_date.weekday() < 5:  # Monday=0, Sunday=6
            working_days += 1
        current_date += timedelta(days=1)
    
    if attendance_qs.exists() and total_employees > 0 and working_days > 0:
        present_days = attendance_qs.filter(
            Q(status='PRESENT') | Q(status='LATE')
        ).count()
        attendance_rate = round((present_days / (total_employees * working_days)) * 100, 1)

    # ===== LEAVE ANALYTICS =====
    # Leave status summary - we'll calculate this in Python since we can't use the duration method in the database query
    leave_stats = []
    status_counts = leave_qs.values('status').annotate(count=Count('id'))
    
    # Calculate total days for each status
    for status in status_counts:
        status_name = status['status']
        leave_days = sum(
            (leave.end_date - leave.start_date).days + 1  # +1 to include both start and end dates
            for leave in leave_qs.filter(status=status_name)
        )
        leave_stats.append({
            'status': status_name,
            'count': status['count'],
            'total_days': leave_days
        })
    
    # Leave by type - also calculated in Python
    leave_by_type = []
    type_counts = leave_qs.values('leave_type').annotate(count=Count('id'))
    
    for leave_type in type_counts:
        type_name = leave_type['leave_type']
        type_leaves = leave_qs.filter(leave_type=type_name)
        total_days = sum(
            (leave.end_date - leave.start_date).days + 1
            for leave in type_leaves
        )
        avg_days = total_days / len(type_leaves) if type_leaves else 0
        
        leave_by_type.append({
            'leave_type': type_name,
            'count': leave_type['count'],
            'total_days': total_days,
            'avg_duration': round(avg_days, 1)
        })
    
    # Sort leave by type by count in descending order
    leave_by_type = sorted(leave_by_type, key=lambda x: x['count'], reverse=True)
    
    # Monthly leave trend - calculated in Python
    monthly_data = {}
    for leave in leave_qs:
        year = leave.start_date.year
        month = leave.start_date.month
        days = (leave.end_date - leave.start_date).days + 1
        
        key = f"{year}-{month:02d}"
        if key not in monthly_data:
            monthly_data[key] = {'year': year, 'month': month, 'count': 0, 'total_days': 0}
            
        monthly_data[key]['count'] += 1
        monthly_data[key]['total_days'] += days
    
    # Convert to list and sort by year and month
    leave_monthly = sorted(monthly_data.values(), key=lambda x: (x['year'], x['month']))

    # ===== PERFORMANCE ANALYTICS ===== - PERFORMANCE MODULE DISABLED
    # performance_reviews = PerformanceReview.objects.filter(
    #     review_date__range=[start_date_obj, end_date_obj]
    # )
    performance_reviews = []
    
    if company:
        performance_reviews = performance_reviews.filter(employee__company=company)
    
    # Performance metrics
    # Calculate average rating by converting the text ratings to numeric scores
    rating_scores = {
        'OUTSTANDING': 5,
        'EXCEEDS_EXPECTATIONS': 4,
        'MEETS_EXPECTATIONS': 3,
        'BELOW_EXPECTATIONS': 2,
        'UNSATISFACTORY': 1
    }
    
    # Calculate average rating
    total_rating = 0
    rating_count = 0
    rating_distribution = {rating: 0 for rating in rating_scores}
    
    for review in performance_reviews:
        if review.overall_rating in rating_scores:
            total_rating += rating_scores[review.overall_rating]
            rating_count += 1
            rating_distribution[review.overall_rating] += 1
    
    avg_rating = round(total_rating / rating_count, 1) if rating_count > 0 else 0.0
    
    # Prepare performance distribution data for the chart
    performance_distribution = [
        {'overall_rating': rating, 'count': count}
        for rating, count in rating_distribution.items()
    ]
    
    # Initialize metrics data with default values
    metrics_data = {
        'productivity': {'average': 0, 'target': 0, 'count': 0},
        'quality': {'average': 0, 'target': 0, 'count': 0},
        'attendance': {'average': 0, 'target': 0, 'count': 0}
    }
    
    # Try to get metrics from PerformanceMetric model if available
    try:
        from blu_staff.apps.performance.models import PerformanceMetric
        if hasattr(PerformanceReview, 'metrics'):
            metrics = PerformanceMetric.objects.filter(
                review__in=performance_reviews,
                name__in=['Productivity', 'Quality', 'Attendance']
            ).values('name').annotate(
                avg_value=Avg('actual_value'),
                target_value=Avg('target_value'),
                count=Count('id')
            )
            
            for metric in metrics:
                metric_name = metric['name'].lower()
                if metric_name in metrics_data:
                    metrics_data[metric_name] = {
                        'average': float(round(metric['avg_value'], 1)) if metric['avg_value'] is not None else 0,
                        'target': float(round(metric['target_value'], 1)) if metric['target_value'] is not None else 0,
                        'count': metric['count']
                    }
    except Exception as e:
        # If there's any error, use default values
        pass

    # ===== DEPARTMENT ANALYTICS =====
    # Get all employees with their departments and ratings
    employees = User.objects.filter(role='EMPLOYEE')
    if company:
        employees = employees.filter(company=company)
    
    # Group employees by department and calculate statistics
    departments = {}
    for emp in employees:
        dept_name = getattr(emp, 'department', 'Unassigned')
        if dept_name not in departments:
            departments[dept_name] = {
                'employee_count': 0,
                'ratings': [],
                'attendance_count': 0,
                'total_days': 0
            }
        
        departments[dept_name]['employee_count'] += 1
        
        # Get performance ratings
        reviews = emp.performance_reviews.all()
        for review in reviews:
            if review.overall_rating in rating_scores:
                departments[dept_name]['ratings'].append(rating_scores[review.overall_rating])
        
        # Get attendance data if available
        if hasattr(emp, 'attendances'):
            attendances = emp.attendances.filter(
                date__range=[start_date_obj, end_date_obj]
            )
            present_days = attendances.filter(
                status__in=['PRESENT', 'LATE']
            ).count()
            total_days = attendances.exclude(status='ON_LEAVE').count()
            
            departments[dept_name]['attendance_count'] += present_days
            departments[dept_name]['total_days'] += total_days
    
    # Prepare department stats
    department_stats = []
    for dept_name, data in departments.items():
        avg_rating = sum(data['ratings']) / len(data['ratings']) if data['ratings'] else 0
        attendance_rate = (data['attendance_count'] / data['total_days'] * 100) if data['total_days'] > 0 else 0
        
        department_stats.append({
            'department__name': dept_name,
            'employee_count': data['employee_count'],
            'avg_rating': round(avg_rating, 1),
            'attendance_rate': round(attendance_rate, 1)
        })
    
    # Sort by employee count
    department_stats = sorted(department_stats, key=lambda x: x['employee_count'], reverse=True)

    # ===== RECENT ACTIVITIES =====
    # High-level activity feed without exposing individual HR details
    recent_activities = []
    
    # Recent leaves (anonymised)
    recent_leaves = leave_qs.select_related('employee').order_by('-created_at')[:5]
    for leave in recent_leaves:
        recent_activities.append({
            'type': 'leave',
            'date': leave.created_at,
            'title': f"Leave request ({leave.get_leave_type_display()})",
            'status': leave.status,
            'icon': 'calendar_today',
            'color': 'primary' if leave.status == 'PENDING' else 'success' if leave.status == 'APPROVED' else 'error'
        })
    
    # Recent reviews (anonymised)
    recent_reviews = performance_reviews.select_related('employee', 'reviewer').order_by('-review_date')[:5]
    for review in recent_reviews:
        recent_activities.append({
            'type': 'review',
            'date': review.review_date,
            'title': "Performance review completed",
            'rating': review.overall_rating,
            'icon': 'star',
            'color': 'warning'
        })
    
    # Sort all activities by date
    recent_activities = sorted(recent_activities, key=lambda x: x['date'], reverse=True)[:10]

    # ===== PREPARE CONTEXT =====
    context = {
        'user': request.user,
        # Summary stats
        'total_users': User.objects.count(),
        'total_companies': Company.objects.count(),
        'total_employees': total_employees,
        'total_employers': User.objects.filter(role='EMPLOYER').count(),
        'present_days': present_days,
        'working_days': working_days,
        'attendance_rate': attendance_rate,
        'avg_rating': avg_rating,
        'start_date': start_date_obj.strftime('%Y-%m-%d'),
        'end_date': end_date_obj.strftime('%Y-%m-%d'),
        'today': today.strftime('%Y-%m-%d'),
        'company_filter': company_filter,
        'companies': Company.objects.all(),
        'selected_company': company,
        'recent_activities': recent_activities,
        'attendance_daily': list(attendance_daily),
        'attendance_monthly': list(attendance_monthly),
        'leave_stats': list(leave_stats),
        'leave_by_type': list(leave_by_type),
        'leave_monthly': list(leave_monthly),
        'performance_distribution': performance_distribution,
        'department_stats': department_stats,
        'metrics_data': metrics_data,
        
        # Summary metrics
        'total_reviews': performance_reviews.count(),
        'pending_leaves': leave_qs.filter(status='PENDING').count(),
        'approved_leaves': leave_qs.filter(status='APPROVED').count(),
        'rejected_leaves': leave_qs.filter(status='REJECTED').count(),
        'total_leave_days': sum(
            (leave.end_date - leave.start_date).days + 1
            for leave in leave_qs.filter(status='APPROVED')
        ),
        
        # Chart data as JSON for JavaScript
        'attendance_daily_json': json.dumps([{
            'date': str(item['date']),
            'present': item['present'],
            'late': item['late'],
            'absent': item['absent'],
            'on_leave': item['on_leave'],
            'total': item['total']
        } for item in attendance_daily]),
        
        'attendance_monthly_json': json.dumps([{
            'month': f"{calendar.month_abbr[item['month']]} {item['year']}",
            'present': item['present'],
            'late': item['late'],
            'absent': item['absent'],
            'on_leave': item['on_leave'],
            'total': item['total']
        } for item in attendance_monthly]),
        
        'leave_by_type_json': json.dumps([{
            'type': item['leave_type'],
            'count': item['count'],
            'total_days': item['total_days'] or 0,
            'avg_duration': float(item['avg_duration']) if item['avg_duration'] else 0
        } for item in leave_by_type]),
        
        'performance_distribution_json': json.dumps([{
            'rating': item['overall_rating'],
            'count': item['count']
        } for item in performance_distribution])
    }

    # Add debug info in development
    if settings.DEBUG:
        context['debug'] = {
            'query_count': len(connection.queries),
            'queries': connection.queries,
        }

    return render(request, 'ems/analytics_dashboard.html', context)

@login_required
def settings_hub(request):
    """Settings hub with quick access to all administrative functions"""
    # Check if user has HR role via employee_profile
    has_hr_access = False
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_hr_access = request.user.employee_profile.employee_role == 'HR'
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'HR'] or request.user.is_employer_admin or has_hr_access):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = request.user.company
    except:
        company = None
    
    context = {
        'company': company,
    }
    
    return render(request, 'ems/settings_hub.html', context)


@login_required
def settings_dashboard(request):
    """Enhanced company settings dashboard with statistics, audit logs, and filters"""
    allowed_roles = {'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'HR'}
    
    # Check if user has HR role via employee_profile
    has_hr_access = False
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_hr_access = request.user.employee_profile.employee_role == 'HR'
    
    if not (
        getattr(request.user, 'role', '') in allowed_roles
        or has_hr_access
        or getattr(request.user, 'is_employer_admin', False)
        or getattr(request.user, 'is_superuser', False)
        or getattr(request.user, 'is_superadmin', False)
    ):
        return render(request, 'ems/unauthorized.html', status=403)

    company = _get_user_company(request.user)
    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    from django.db.models import Q, Count
    from datetime import datetime, timedelta
    import csv
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    dept_filter = request.GET.get('department', '')
    export_type = request.GET.get('export', '')  # departments, positions, pay_grades
    
    config, _ = EmployeeIdConfiguration.objects.get_or_create(company=company)
    email_settings, _ = CompanyEmailSettings.objects.get_or_create(company=company)
    biometric_settings, _ = CompanyBiometricSettings.objects.get_or_create(company=company)

    email_form = CompanyEmailSettingsForm(instance=email_settings)
    biometric_form = CompanyBiometricSettingsForm(instance=biometric_settings)

    # Base querysets
    departments = CompanyDepartment.objects.filter(company=company)
    positions = CompanyPosition.objects.filter(company=company).select_related('department')
    pay_grades = CompanyPayGrade.objects.filter(company=company)

    # Apply search filter
    if search_query:
        departments = departments.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )
        positions = positions.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )
        pay_grades = pay_grades.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Apply department filter for positions
    if dept_filter:
        positions = positions.filter(department_id=dept_filter)

    # Order results
    departments = departments.order_by('name')
    positions = positions.order_by('name')
    pay_grades = pay_grades.order_by('name')

    # Statistics
    total_departments = CompanyDepartment.objects.filter(company=company).count()
    total_positions = CompanyPosition.objects.filter(company=company).count()
    total_pay_grades = CompanyPayGrade.objects.filter(company=company).count()
    total_configurations = total_departments + total_positions + total_pay_grades

    position_by_dept = (
        CompanyPosition.objects.filter(company=company, department__isnull=False)
        .values('department__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Integration data
    integration_cards = []
    integration_logs = []
    try:
        available_integrations_qs = IntegrationDefinition.objects.filter(
            is_available=True,
            is_active=True,
        ).order_by('name')
        existing_connections = IntegrationConnection.objects.filter(company=company).select_related('integration', 'connected_by')
        connection_map = {connection.integration_id: connection for connection in existing_connections}

        for integration in available_integrations_qs:
            connection = connection_map.get(integration.id)
            status_code = connection.status if connection else 'NOT_CONNECTED'
            status_label = connection.get_status_display() if connection else 'Not Connected'

            integration_cards.append(
                {
                    'id': integration.id,
                    'name': integration.name,
                    'description': integration.description,
                    'integration_type': integration.integration_type,
                    'integration_type_label': integration.get_integration_type_display(),
                    'requires_oauth': integration.requires_oauth,
                    'status_code': status_code,
                    'status_label': status_label,
                    'connected': bool(connection),
                    'connected_at': connection.connected_at if connection else None,
                    'connected_by': connection.connected_by.get_full_name() if connection and connection.connected_by else '',
                    'last_synced_at': connection.last_synced_at if connection else None,
                    'last_error': connection.last_error if connection else '',
                    'error_count': connection.error_count if connection else 0,
                    'webhook_url': connection.webhook_url if connection else '',
                    'config': connection.config_json if connection else {},
                    'connect_url': reverse('integration_connect', args=[integration.id]),
                    'disconnect_url': reverse('integration_disconnect', args=[integration.id]),
                    'test_url': reverse('integration_test', args=[integration.id]),
                    'manage_url': reverse('integration_management'),
                }
            )

        recent_integration_logs_qs = IntegrationLog.objects.filter(
            company_integration__company=company
        ).select_related('company_integration__integration')[:10]
        integration_logs = [
            {
                'id': log.id,
                'created_at': log.created_at,
                'action_label': log.get_action_display(),
                'success': log.success,
                'description': log.description,
                'integration_name': log.company_integration.integration.name if log.company_integration and log.company_integration.integration else '',
                'status_code': log.company_integration.status if log.company_integration else '',
            }
            for log in recent_integration_logs_qs
        ]
    except (OperationalError, DatabaseError):
        integration_cards = []
        integration_logs = []

    
    # CSV Export
    if export_type == 'departments':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="departments.csv"'
        writer = csv.writer(response)
        writer.writerow(['Department Name', 'Description', 'Created Date', 'Active'])
        for dept in departments:
            writer.writerow([
                dept.name,
                dept.description or '',
                dept.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(dept, 'created_at') else '',
                'Yes' if dept.is_active else 'No'
            ])
        return response
    
    elif export_type == 'positions':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="positions.csv"'
        writer = csv.writer(response)
        writer.writerow(['Position Name', 'Department', 'Description', 'Created Date'])
        for pos in positions:
            writer.writerow([
                pos.name,
                pos.department.name if pos.department else 'N/A',
                pos.description or '',
                pos.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(pos, 'created_at') else ''
            ])
        return response
    
    elif export_type == 'pay_grades':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="pay_grades.csv"'
        writer = csv.writer(response)
        writer.writerow(['Pay Grade Name', 'Description', 'Min Salary', 'Max Salary', 'Created Date'])
        for grade in pay_grades:
            writer.writerow([
                grade.name,
                grade.description or '',
                grade.min_salary if hasattr(grade, 'min_salary') else '',
                grade.max_salary if hasattr(grade, 'max_salary') else '',
                grade.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(grade, 'created_at') else ''
            ])
        return response

    # Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'employee_id':
            form = EmployeeIdConfigurationForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
                messages.success(request, 'Employee ID settings updated.')
            else:
                messages.error(request, 'Please correct the errors in Employee ID settings.')

        elif action == 'department':
            dept_form = CompanyDepartmentForm(request.POST, company=company)
            if dept_form.is_valid():
                try:
                    dept_form.save()
                    messages.success(request, 'Department added successfully.')
                except IntegrityError:
                    messages.error(request, 'Department with this name already exists.')
            else:
                messages.error(request, 'Please correct the errors in the Department form.')

        elif action == 'position':
            position_form = CompanyPositionForm(request.POST, company=company)
            if position_form.is_valid():
                try:
                    position_form.save()
                    messages.success(request, 'Position added successfully.')
                except IntegrityError:
                    messages.error(request, 'Position with this name already exists.')
            else:
                messages.error(request, 'Please correct the errors in the Position form.')

        elif action == 'pay_grade':
            pay_grade_form = CompanyPayGradeForm(request.POST, company=company)
            if pay_grade_form.is_valid():
                try:
                    pay_grade_form.save()
                    messages.success(request, 'Pay grade added successfully.')
                except IntegrityError:
                    messages.error(request, 'Pay grade with this name already exists.')
            else:
                messages.error(request, 'Please correct the errors in the Pay grade form.')
        
        elif action == 'edit_department':
            dept_id = request.POST.get('dept_id')
            try:
                department = CompanyDepartment.objects.get(id=dept_id, company=company)
                department.name = request.POST.get('name')
                department.description = request.POST.get('description', '')
                department.save()
                messages.success(request, f'Department "{department.name}" updated successfully.')
            except CompanyDepartment.DoesNotExist:
                messages.error(request, 'Department not found.')
            except Exception as e:
                messages.error(request, f'Error updating department: {str(e)}')
        
        elif action == 'edit_position':
            pos_id = request.POST.get('pos_id')
            try:
                position = CompanyPosition.objects.get(id=pos_id, company=company)
                position.name = request.POST.get('name')
                position.description = request.POST.get('description', '')
                dept_id = request.POST.get('department')
                if dept_id:
                    position.department = CompanyDepartment.objects.get(id=dept_id, company=company)
                else:
                    position.department = None
                position.save()
                messages.success(request, f'Position "{position.name}" updated successfully.')
            except CompanyPosition.DoesNotExist:
                messages.error(request, 'Position not found.')
            except Exception as e:
                messages.error(request, f'Error updating position: {str(e)}')
        
        elif action == 'edit_pay_grade':
            grade_id = request.POST.get('grade_id')
            try:
                pay_grade = CompanyPayGrade.objects.get(id=grade_id, company=company)
                pay_grade.name = request.POST.get('name')
                pay_grade.description = request.POST.get('description', '')
                pay_grade.save()
                messages.success(request, f'Pay grade "{pay_grade.name}" updated successfully.')
            except CompanyPayGrade.DoesNotExist:
                messages.error(request, 'Pay grade not found.')
            except Exception as e:
                messages.error(request, f'Error updating pay grade: {str(e)}')

        elif action == 'email_smtp':
            email_form = CompanyEmailSettingsForm(request.POST, instance=email_settings)
            if email_form.is_valid():
                email_form.save()
                messages.success(request, 'Email settings updated successfully.')
                return redirect('settings_dashboard')
            else:
                messages.error(request, 'Please review the email settings form for errors.')

        elif action == 'biometric':
            biometric_form = CompanyBiometricSettingsForm(request.POST, instance=biometric_settings)
            if biometric_form.is_valid():
                biometric_form.save()
                messages.success(request, 'Biometric settings updated successfully.')
                return redirect('settings_dashboard')
            else:
                messages.error(request, 'Please review the biometric settings form for errors.')
        
        elif action == 'notifications':
            from blu_staff.apps.accounts.models import CompanyNotificationSettings
            from blu_staff.apps.accounts.forms import CompanyNotificationSettingsForm
            notification_settings, _ = CompanyNotificationSettings.objects.get_or_create(company=company)
            notification_form = CompanyNotificationSettingsForm(request.POST, instance=notification_settings)
            if notification_form.is_valid():
                notification_form.save()
                messages.success(request, 'Notification settings updated successfully.')
                return redirect('settings_dashboard')
            else:
                messages.error(request, 'Please review the notification settings form for errors.')
        
        elif action == 'api_key':
            from blu_staff.apps.accounts.models import CompanyAPIKey
            import secrets
            # Deactivate old keys
            CompanyAPIKey.objects.filter(company=company, is_active=True).update(is_active=False)
            # Generate new API key
            new_key = f"ems_api_{secrets.token_urlsafe(32)}"
            webhook_url = request.POST.get('webhook_url', '')
            api_key = CompanyAPIKey.objects.create(
                company=company,
                key=new_key,
                name=f"API Key {CompanyAPIKey.objects.filter(company=company).count() + 1}",
                webhook_url=webhook_url
            )
            messages.success(request, f'API key generated successfully!')
            return redirect('settings_dashboard')
        
        elif action == 'webhook':
            from blu_staff.apps.accounts.models import CompanyAPIKey
            webhook_url = request.POST.get('webhook_url', '')
            # Update the primary API key's webhook URL
            primary_key = CompanyAPIKey.objects.filter(company=company, is_active=True).order_by('-created_at').first()
            if primary_key:
                primary_key.webhook_url = webhook_url
                primary_key.save()
                messages.success(request, 'Webhook URL updated successfully!')
            else:
                messages.error(request, 'No active API key found. Please generate an API key first.')
            return redirect('settings_dashboard')
        
        elif action == 'company_profile':
            # Update company profile including logo and stamp
            company.name = request.POST.get('company_name', company.name)
            company.address = request.POST.get('company_address', company.address)
            company.phone = request.POST.get('company_phone', company.phone)
            company.email = request.POST.get('company_email', company.email)
            company.website = request.POST.get('company_website', company.website)
            company.city = request.POST.get('company_city', company.city)
            company.country = request.POST.get('company_country', company.country)
            
            # Handle logo upload
            if 'company_logo' in request.FILES:
                company.logo = request.FILES['company_logo']
            
            # Handle stamp upload
            if 'company_stamp' in request.FILES:
                company.company_stamp = request.FILES['company_stamp']
            
            company.save()
            messages.success(request, 'Company profile updated successfully!')
            return redirect('settings_dashboard')
        
        elif action == 'payslip_design':
            import json
            # Save payslip design settings
            try:
                # Template layout (classic / modern / compact)
                payslip_layout = request.POST.get('payslip_layout', '').strip()
                if payslip_layout in ['classic', 'modern', 'compact', 'detailed']:
                    company.payslip_layout = payslip_layout

                # Section order (drag-and-drop layout)
                section_order_json = request.POST.get('section_order', '[]')
                company.payslip_section_order = json.loads(section_order_json) if section_order_json else []
                
                # Orientation
                company.payslip_orientation = request.POST.get('payslip_orientation', 'portrait')
                
                # Logo and stamp positions
                company.payslip_logo_position = request.POST.get('payslip_logo_position', 'top-left')
                company.payslip_stamp_position = request.POST.get('payslip_stamp_position', 'bottom-right')

                # Stamp drag pixel offsets + opacity + size + font family
                try:
                    field_positions = company.payslip_field_positions or {}
                    field_positions['stamp_drag'] = {
                        'x': float(request.POST.get('stamp_drag_x', 0)),
                        'y': float(request.POST.get('stamp_drag_y', 0)),
                    }
                    field_positions['stamp_opacity'] = float(request.POST.get('stamp_opacity', 100))
                    field_positions['stamp_size'] = float(request.POST.get('stamp_size', 120))
                    font_family = request.POST.get('payslip_font_family', '').strip()
                    if font_family:
                        field_positions['font_family'] = font_family
                    company.payslip_field_positions = field_positions
                except (ValueError, TypeError):
                    pass

                # Company info fields
                company_name = request.POST.get('company_name', '').strip()
                if company_name:
                    company.name = company_name
                company_phone = request.POST.get('company_phone', '').strip()
                if company_phone:
                    company.phone = company_phone
                company_email = request.POST.get('company_email', '').strip()
                if company_email:
                    company.email = company_email
                company_address = request.POST.get('company_address', '').strip()
                if company_address:
                    company.address = company_address
                
                # Header and footer
                company.payslip_header_style = request.POST.get('payslip_header_style', 'professional_table')
                footer_text_raw = request.POST.get('payslip_footer_text', '')
                # Strip literal Django template syntax saved accidentally (e.g. {{ company.payslip_footer_text|default:'...' }})
                import re as _re
                if _re.search(r'\{\{.*?\}\}|\{%.*?%\}', footer_text_raw):
                    footer_text_raw = ''
                company.payslip_footer_text = footer_text_raw
                
                # Layout style
                payslip_layout_style = request.POST.get('payslip_layout_style', 'professional_table')
                company.payslip_header_style = payslip_layout_style  # Store layout style in header_style field
                
                # Display options
                company.show_company_logo = request.POST.get('show_company_logo') == 'on'
                company.show_company_stamp = request.POST.get('show_company_stamp') == 'on'
                company.show_signature = request.POST.get('show_signature') == 'on'
                company.show_tax_breakdown = request.POST.get('show_tax_breakdown') == 'on'
                
                # Colors
                company.payslip_header_color = request.POST.get('payslip_header_color', '#3b82f6')
                company.payslip_accent_color = request.POST.get('payslip_accent_color', '#10b981')
                company.payslip_section_color = request.POST.get('payslip_section_color', '#C5D9F1')
                
                company.save()
                messages.success(request, 'Payslip design saved successfully!')
            except json.JSONDecodeError:
                messages.error(request, 'Invalid section order format.')
            except Exception as e:
                messages.error(request, f'Error saving payslip design: {str(e)}')
            
            return redirect('settings_dashboard')

        else:
            return redirect('settings_dashboard')

    # Get or create notification settings
    from blu_staff.apps.accounts.models import CompanyNotificationSettings, CompanyAPIKey
    from blu_staff.apps.accounts.forms import CompanyNotificationSettingsForm
    notification_settings, _ = CompanyNotificationSettings.objects.get_or_create(company=company)
    notification_form = CompanyNotificationSettingsForm(instance=notification_settings)
    
    # Get API keys
    api_keys = CompanyAPIKey.objects.filter(company=company, is_active=True).order_by('-created_at')
    primary_api_key = api_keys.first()
    
    context = {
        'company': company,
        'employee_id_form': EmployeeIdConfigurationForm(instance=config),
        'department_form': CompanyDepartmentForm(company=company),
        'position_form': CompanyPositionForm(company=company),
        'pay_grade_form': CompanyPayGradeForm(company=company),
        'departments': departments,
        'positions': positions,
        'pay_grades': pay_grades,
        'employee_id_preview': config.generate_employee_id(),
        'email_form': email_form,
        'biometric_form': biometric_form,
        'notification_form': notification_form,
        'notification_settings': notification_settings,
        'api_keys': api_keys,
        'primary_api_key': primary_api_key,
        'integration_cards': integration_cards,
        'integration_logs': integration_logs,

        # Statistics
        'total_departments': total_departments,
        'total_positions': total_positions,
        'total_pay_grades': total_pay_grades,
        'total_configurations': total_configurations,
        'position_by_dept': position_by_dept,
        
        # Filter states
        'search_query': search_query,
        'dept_filter': dept_filter,
        'all_departments': CompanyDepartment.objects.filter(company=company).order_by('name'),
    }

    return render(request, 'ems/settings_company.html', context)

@login_required
def delete_department(request, dept_id):
    """Delete a department"""
    if request.method == 'POST':
        allowed_roles = {'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            dept = CompanyDepartment.objects.get(id=dept_id, company=company)
            dept_name = dept.name
            dept.delete()
            return JsonResponse({'success': True, 'message': f'Department "{dept_name}" deleted successfully'})
        except CompanyDepartment.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Department not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def delete_position(request, pos_id):
    """Delete a position"""
    if request.method == 'POST':
        allowed_roles = {'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

        
        company = _get_user_company(request.user)
        try:
            position = CompanyPosition.objects.get(id=pos_id, company=company)
            pos_name = position.name
            position.delete()
            return JsonResponse({'success': True, 'message': f'Position "{pos_name}" deleted successfully'})
        except CompanyPosition.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Position not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def delete_pay_grade(request, grade_id):
    """Delete a pay grade"""
    if request.method == 'POST':
        allowed_roles = {'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            grade = CompanyPayGrade.objects.get(id=grade_id, company=company)
            grade_name = grade.name
            grade.delete()
            return JsonResponse({'success': True, 'message': f'Pay grade "{grade_name}" deleted successfully'})
        except CompanyPayGrade.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Pay grade not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def test_smtp_connection(request):
    """Test SMTP connection"""
    if request.method == 'POST':
        import json
        from django.core.mail import send_mail
        from django.conf import settings
        import smtplib
        
        allowed_roles = {'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            email_settings = CompanyEmailSettings.objects.get(company=company)
            
            # Test connection
            import smtplib
            smtp = smtplib.SMTP(email_settings.smtp_host, email_settings.smtp_port, timeout=10)
            if email_settings.smtp_use_tls:
                smtp.starttls()
            if email_settings.smtp_username and email_settings.smtp_password:
                smtp.login(email_settings.smtp_username, email_settings.smtp_password)
            smtp.quit()
            
            return JsonResponse({'success': True, 'message': 'SMTP connection successful!'})
        except smtplib.SMTPAuthenticationError:
            return JsonResponse({'success': False, 'error': 'Authentication failed. Check username and password.'}, status=400)
        except smtplib.SMTPConnectError:
            return JsonResponse({'success': False, 'error': 'Cannot connect to SMTP server.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Connection failed: {str(e)}'}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def test_biometric_connection(request):
    """Test biometric device connection"""
    if request.method == 'POST':
        import requests
        
        allowed_roles = {'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            biometric_settings = CompanyBiometricSettings.objects.get(company=company)
            
            if not biometric_settings.device_ip:
                return JsonResponse({'success': False, 'error': 'Device IP not configured'}, status=400)
            
            # Try to ping the device (basic connectivity test)
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((str(biometric_settings.device_ip), 80))
            sock.close()
            
            if result == 0:
                return JsonResponse({'success': True, 'message': 'Biometric device is reachable!'})
            else:
                return JsonResponse({'success': False, 'error': 'Cannot reach device. Check IP address and network.'}, status=400)
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Connection test failed: {str(e)}'}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def employer_employee_management(request):
    """Enhanced employee management with search, filters, and export"""
    # Check if user has HR or admin access (accountants also allowed for salary visibility)
    _is_accountant = (hasattr(request.user, 'employee_profile') and
                      request.user.employee_profile and
                      request.user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    if not _has_hr_access(request.user) and not _is_accountant:
        return render(request, 'ems/unauthorized.html')

    company = _get_user_company(request.user)
    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    from blu_staff.apps.accounts.models import User, CompanyDepartment, CompanyPosition
    from blu_staff.apps.attendance.models import Attendance, LeaveRequest
    from blu_staff.apps.documents.models import EmployeeDocument
    from blu_staff.apps.performance.models import PerformanceReview
    from datetime import date, timedelta
    from django.http import HttpResponse
    import csv

    today = date.today()

    # Get base employees queryset
    employees = User.objects.filter(company=company, role='EMPLOYEE').select_related('employee_profile')

    # Handle CSV Export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="employees_{company.name}_{today}.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Employee ID', 'First Name', 'Last Name', 'Email', 'Phone', 
            'Department', 'Position', 'Employment Type', 'Hire Date', 
            'Status', 'Salary', 'Currency'
        ])
        
        for emp in employees:
            profile = emp.employee_profile if hasattr(emp, 'employee_profile') else None
            writer.writerow([
                profile.employee_id if profile else 'N/A',
                emp.first_name,
                emp.last_name,
                emp.email,
                emp.phone_number or 'N/A',
                profile.department if profile and profile.department else 'N/A',
                profile.job_title if profile and profile.job_title else 'N/A',
                profile.get_employment_type_display() if profile and profile.employment_type else 'N/A',
                profile.date_hired.strftime('%Y-%m-%d') if profile and profile.date_hired else 'N/A',
                'Active' if emp.is_active else 'Inactive',
                profile.salary if profile and profile.salary else 'N/A',
                profile.get_currency_display() if profile and profile.currency else 'N/A'
            ])
        
        return response

    # Search functionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        employees = employees.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(employee_profile__employee_id__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )

    # Department filter
    department_filter = request.GET.get('department', '')
    if department_filter:
        try:
            from blu_staff.apps.accounts.models import CompanyDepartment
            dept = CompanyDepartment.objects.get(id=department_filter, company=company)
            employees = employees.filter(employee_profile__department=dept.name)
        except:
            pass

    # Position filter
    position_filter = request.GET.get('position', '')
    if position_filter:
        try:
            from blu_staff.apps.accounts.models import CompanyPosition
            pos = CompanyPosition.objects.get(id=position_filter, company=company)
            employees = employees.filter(employee_profile__job_title=pos.name)
        except:
            pass

    # Employment type filter
    employment_type_filter = request.GET.get('employment_type', '')
    if employment_type_filter:
        employees = employees.filter(employee_profile__employment_type=employment_type_filter)

    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        employees = employees.filter(is_active=True)
    elif status_filter == 'inactive':
        employees = employees.filter(is_active=False)

    # Statistics for this company
    total_employees = User.objects.filter(company=company, role='EMPLOYEE').count()
    active_employees = User.objects.filter(company=company, role='EMPLOYEE', is_active=True).count()
    inactive_employees = total_employees - active_employees
    filtered_count = employees.count()

    # Today's attendance for this company
    today_attendance = Attendance.objects.filter(date=today, employee__company=company)
    present_today = today_attendance.filter(status='PRESENT').count()
    late_today = today_attendance.filter(status='LATE').count()

    # Pending leave requests for this company
    pending_leaves = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).count()

    # Recent documents for this company
    recent_docs = EmployeeDocument.objects.filter(
        employee__company=company
    ).select_related('employee', 'category').order_by('-created_at')[:5]

    # Upcoming performance reviews for this company - PERFORMANCE MODULE DISABLED
    # upcoming_reviews = PerformanceReview.objects.filter(
    #     employee__company=company,
    #     review_date__gte=today
    # ).select_related('employee', 'reviewer').order_by('review_date')[:5]
    upcoming_reviews = []

    # Get filter options
    all_departments = CompanyDepartment.objects.filter(company=company).order_by('name')
    all_positions = CompanyPosition.objects.filter(company=company).order_by('name')
    
    # Employment type choices
    from blu_staff.apps.accounts.models import EmployeeProfile
    employment_types = EmployeeProfile.EmploymentType.choices

    # Prepare employee data for template
    for employee in employees:
        today_att = today_attendance.filter(employee=employee).first()
        employee.attendance_status = today_att.status if today_att else 'ABSENT'
        employee.pending_leaves = LeaveRequest.objects.filter(
            employee=employee, status='PENDING'
        ).count()

    # Group employees by role for card-based layout
    from collections import OrderedDict
    role_order = ['SUPERVISOR', 'HR', 'EMPLOYEE']
    role_labels = {'SUPERVISOR': 'Supervisors', 'HR': 'HR Personnel', 'EMPLOYEE': 'Employees'}
    role_icons = {'SUPERVISOR': 'shield', 'HR': 'briefcase', 'EMPLOYEE': 'user'}
    grouped_employees = OrderedDict()
    for role_key in role_order:
        grouped_employees[role_key] = {
            'label': role_labels.get(role_key, role_key),
            'icon': role_icons.get(role_key, 'user'),
            'members': [],
        }
    for employee in employees:
        role = 'EMPLOYEE'
        if hasattr(employee, 'employee_profile') and employee.employee_profile:
            role = getattr(employee.employee_profile, 'employee_role', 'EMPLOYEE') or 'EMPLOYEE'
        if role not in grouped_employees:
            grouped_employees[role] = {'label': role.title(), 'icon': 'user', 'members': []}
        grouped_employees[role]['members'].append(employee)
    # Remove empty groups
    grouped_employees = OrderedDict(
        (k, v) for k, v in grouped_employees.items() if v['members']
    )

    context = {
        'user': request.user,
        'company': company,
        'employees': employees,
        'grouped_employees': grouped_employees,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'inactive_employees': inactive_employees,
        'filtered_count': filtered_count,
        'present_today': present_today,
        'late_today': late_today,
        'pending_leaves': pending_leaves,
        'recent_docs': recent_docs,
        'upcoming_reviews': upcoming_reviews,
        'today_date': today.strftime('%Y-%m-%d'),
        # Filter options
        'all_departments': all_departments,
        'all_positions': all_positions,
        'employment_types': employment_types,
        # Current filters
        'search_query': search_query,
        'department_filter': department_filter,
        'position_filter': position_filter,
        'employment_type_filter': employment_type_filter,
        'status_filter': status_filter,
    }
    context.update(_get_employer_nav_context(request.user))
    
    return render(request, 'ems/employer_employee_management.html', context)

@login_required
def employee_bulk_action(request):
    """Handle bulk actions on employees"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    company = _get_user_company(request.user)
    if not company:
        return JsonResponse({'success': False, 'error': 'Company not assigned'}, status=400)
    
    import json
    try:
        data = json.loads(request.body)
        action = data.get('action')
        employee_ids = data.get('employee_ids', [])
        
        if not action or not employee_ids:
            return JsonResponse({'success': False, 'error': 'Missing action or employee IDs'}, status=400)
        
        from blu_staff.apps.accounts.models import User
        employees = User.objects.filter(id__in=employee_ids, company=company, role='EMPLOYEE')
        
        if action == 'activate':
            count = employees.update(is_active=True)
            return JsonResponse({'success': True, 'message': f'{count} employee(s) activated successfully'})
        
        elif action == 'deactivate':
            count = employees.update(is_active=False)
            return JsonResponse({'success': True, 'message': f'{count} employee(s) deactivated successfully'})
        
        elif action == 'delete':
            count = employees.count()
            employees.delete()
            return JsonResponse({'success': True, 'message': f'{count} employee(s) deleted successfully'})
        
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_employee_limit()
def employer_add_employee(request):
    """Add new employee for employers and HR"""
    # Check if user is employer, admin, or HR
    is_hr = hasattr(request.user, 'employee_profile') and request.user.employee_profile and request.user.employee_profile.employee_role == 'HR'
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin or is_hr):
        return render(request, 'ems/unauthorized.html')

    try:
        company = request.user.company
    except:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    from blu_staff.apps.accounts.models import (
        User,
        EmployeeProfile,
    )
    from django.contrib.auth.hashers import make_password

    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        employee_id = request.POST.get('employee_id')
        department = request.POST.get('department')
        job_title = request.POST.get('job_title') or request.POST.get('position')
        salary = request.POST.get('salary')
        pay_grade = request.POST.get('pay_grade')
        hire_date = request.POST.get('hire_date')
        employee_role_value = request.POST.get('employee_role') or EmployeeProfile.EmployeeRole.EMPLOYEE
        employment_type_value = request.POST.get('employment_type') or ''
        currency_value = request.POST.get('currency') or EmployeeProfile.Currency.ZMW
        probation_start_input = request.POST.get('probation_start_date')
        probation_end_input = request.POST.get('probation_end_date')
        contract_start_input = request.POST.get('contract_start_date')
        contract_end_input = request.POST.get('contract_end_date')
        temporary_start_input = request.POST.get('temporary_start_date')
        temporary_end_input = request.POST.get('temporary_end_date')
        profile_picture_file = request.FILES.get('profile_picture')
        signature_image_file = request.FILES.get('signature_image')
        signature_pin_input = request.POST.get('signature_pin')
        supervisor_id = request.POST.get('supervisor')

        if employee_role_value not in EmployeeProfile.EmployeeRole.values:
            employee_role_value = EmployeeProfile.EmployeeRole.EMPLOYEE

        if employment_type_value and employment_type_value not in EmployeeProfile.EmploymentType.values:
            employment_type_value = ''
        
        if currency_value not in EmployeeProfile.Currency.values:
            currency_value = EmployeeProfile.Currency.ZMW

        probation_start_input = request.POST.get('probation_start_date')
        probation_end_input = request.POST.get('probation_end_date')
        contract_start_input = request.POST.get('contract_start_date')
        contract_end_input = request.POST.get('contract_end_date')
        temporary_start_input = request.POST.get('temporary_start_date')
        temporary_end_input = request.POST.get('temporary_end_date')

        try:
            probation_start = datetime.strptime(probation_start_input, '%Y-%m-%d').date() if probation_start_input else None
        except ValueError:
            messages.error(request, 'Invalid probation start date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            probation_end = datetime.strptime(probation_end_input, '%Y-%m-%d').date() if probation_end_input else None
        except ValueError:
            messages.error(request, 'Invalid probation end date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            contract_start = datetime.strptime(contract_start_input, '%Y-%m-%d').date() if contract_start_input else None
        except ValueError:
            messages.error(request, 'Invalid contract start date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            contract_end = datetime.strptime(contract_end_input, '%Y-%m-%d').date() if contract_end_input else None
        except ValueError:
            messages.error(request, 'Invalid contract end date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            temporary_start = datetime.strptime(temporary_start_input, '%Y-%m-%d').date() if temporary_start_input else None
        except ValueError:
            messages.error(request, 'Invalid temporary start date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            temporary_end = datetime.strptime(temporary_end_input, '%Y-%m-%d').date() if temporary_end_input else None
        except ValueError:
            messages.error(request, 'Invalid temporary end date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        if employment_type_value == EmployeeProfile.EmploymentType.PROBATION:
            if not (probation_start and probation_end):
                messages.error(request, 'Probation start and end dates are required for probation employees.')
                return redirect('employer_add_employee')
            if probation_end < probation_start:
                messages.error(request, 'Probation end date cannot be earlier than the start date.')
                return redirect('employer_add_employee')
        else:
            probation_start = None
            probation_end = None

        if employment_type_value == EmployeeProfile.EmploymentType.CONTRACT:
            if not (contract_start and contract_end):
                messages.error(request, 'Contract start and end dates are required for contract employees.')
                return redirect('employer_add_employee')
            if contract_end < contract_start:
                messages.error(request, 'Contract end date cannot be earlier than the start date.')
                return redirect('employer_add_employee')
        else:
            contract_start = None
            contract_end = None

        if employment_type_value == EmployeeProfile.EmploymentType.TEMPORARY:
            if not (temporary_start and temporary_end):
                messages.error(request, 'Temporary start and end dates are required for temporary employees.')
                return redirect('employer_add_employee')
            if temporary_end < temporary_start:
                messages.error(request, 'Temporary end date cannot be earlier than the start date.')
                return redirect('employer_add_employee')
        else:
            temporary_start = None
            temporary_end = None

        # Validation
        if not all([first_name, last_name, email, password, confirm_password]):
            messages.error(request, 'Please fill in all required fields (name, email, password).')
            return redirect('employer_add_employee')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('employer_add_employee')

        # Additional required employment fields
        if not all([employee_id, job_title, hire_date]):
            messages.error(request, 'Please provide Employee ID, Job Title, and Hire Date.')
            return redirect('employer_add_employee')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An employee with this email already exists.')
            return redirect('employer_add_employee')

        try:
            # Create user
            user = User.objects.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone,
                username=email,  # Use email as username
                role='EMPLOYEE',
                is_active=True,
                company=company,
                password=make_password(password)
            )

            if profile_picture_file:
                user.profile_picture = profile_picture_file
                user.save(update_fields=['profile_picture'])

            # Coerce types
            from decimal import Decimal
            salary_val = None
            try:
                salary_val = Decimal(salary) if salary else None
            except Exception:
                salary_val = None

            include_on_payroll = request.POST.get('on_payroll') == 'on'

            # Create employee profile
            profile = EmployeeProfile.objects.create(
                user=user,
                company=company,
                employee_id=employee_id,
                department=department or 'Unassigned',
                job_title=job_title or 'Employee',
                salary=salary_val,
                currency=currency_value,
                pay_grade=pay_grade or '',
                date_hired=hire_date if hire_date else timezone.now().date(),
                employee_role=employee_role_value,
                employment_type=employment_type_value,
                on_payroll=include_on_payroll,
                probation_start_date=probation_start,
                probation_end_date=probation_end,
                contract_start_date=contract_start,
                contract_end_date=contract_end,
                temporary_start_date=temporary_start,
                temporary_end_date=temporary_end,
            )
            
            # Assign supervisor if provided
            if supervisor_id:
                try:
                    supervisor = User.objects.get(id=supervisor_id, company=company)
                    profile.supervisor = supervisor
                    profile.save(update_fields=['supervisor'])
                except User.DoesNotExist:
                    pass

            # Optional emergency fields if the model supports them
            employee.employee_profile = profile

            emergency_fields = {
                'emergency_contact_name': request.POST.get('emergency_contact_name') or None,
                'emergency_contact_relationship': request.POST.get('emergency_contact_relationship') or None,
                'emergency_contact_phone': request.POST.get('emergency_contact_phone') or None,
                'emergency_contact_email': request.POST.get('emergency_contact_email') or None,
                'emergency_contact_address': request.POST.get('emergency_contact_address') or None,
            }
            changed = False
            for attr, val in emergency_fields.items():
                if val and hasattr(profile, attr):
                    setattr(profile, attr, val)
                    changed = True
            if changed:
                profile.save()

            # Increment employee ID counter if auto-generated
            if request.POST.get('employee_id_autofilled') == '1':
                try:
                    config = EmployeeIdConfiguration.objects.get(company=company)
                    config.increment()
                except EmployeeIdConfiguration.DoesNotExist:
                    pass

            # Auto-create employment contract
            try:
                from blu_staff.apps.contracts.utils import create_or_update_employee_contract
                create_or_update_employee_contract(user, profile, created_by=request.user)
            except Exception:
                pass  # Don't fail employee creation if contract creation fails
            
            # Send welcome email with credentials
            try:
                from ems_project.notifications import EmailNotificationService
                EmailNotificationService.send_new_employee_credentials(
                    employee=user,
                    temporary_password=password,
                    created_by=request.user
                )
                messages.success(request, f'Employee {first_name} {last_name} has been added successfully! Login credentials sent to {email}.')
            except Exception as e:
                messages.success(request, f'Employee {first_name} {last_name} has been added successfully!')
                messages.warning(request, f'Email notification could not be sent: {str(e)}')
            
            return redirect('employer_employee_management')

        except Exception as e:
            messages.error(request, f'Error creating employee: {str(e)}')
            return redirect('employer_add_employee')

    # GET request - show the form
    config = EmployeeIdConfiguration.objects.filter(company=company).first()
    employee_id_suggestion = config.generate_employee_id() if config else ''
    company_departments = CompanyDepartment.objects.filter(company=company).order_by('name')
    company_positions = CompanyPosition.objects.filter(company=company).select_related('department').order_by('name')
    company_pay_grades = CompanyPayGrade.objects.filter(company=company).order_by('name')
    
    # Get available supervisors (users with SUPERVISOR role or higher)
    available_supervisors = User.objects.filter(
        company=company,
        is_active=True
    ).filter(
        employee_profile__employee_role__in=['SUPERVISOR', 'HR', 'ADMINISTRATOR']
    ).select_related('employee_profile').order_by('first_name', 'last_name')

    context = {
        'user': request.user,
        'company': company,
        'employee_id_suggestion': employee_id_suggestion,
        'company_departments': company_departments,
        'company_positions': company_positions,
        'company_pay_grades': company_pay_grades,
        'available_supervisors': available_supervisors,
        'employee_role_choices': EmployeeProfile.EmployeeRole.choices,
        'default_employee_role': EmployeeProfile.EmployeeRole.EMPLOYEE,
        'employment_type_choices': EmployeeProfile.EmploymentType.choices,
    }
    context.update(_get_employer_nav_context(request.user))
    return render(request, 'ems/employer_add_employee_simple.html', context)

@login_required
def employer_edit_employee(request, employee_id):
    """Edit employee information for employers and supervisors"""
    try:
        company = request.user.company
    except:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    from blu_staff.apps.accounts.models import User, EmployeeProfile

    try:
        employee = User.objects.get(id=employee_id, company=company, role='EMPLOYEE')
    except User.DoesNotExist:
        messages.error(request, 'Employee not found or not in your company.')
        return redirect('employer_employee_management')
    
    # Check permissions
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin
    is_hr = hasattr(request.user, 'employee_profile') and request.user.employee_profile.employee_role == 'HR'
    is_supervisor = hasattr(request.user, 'employee_profile') and request.user.employee_profile.employee_role == 'SUPERVISOR'
    is_supervising = is_supervisor and employee.employee_profile.supervisor == request.user
    
    if not (is_admin or is_hr or is_supervising):
        messages.error(request, 'Access denied. You do not have permission to view this employee.')
        return render(request, 'ems/unauthorized.html')

    if request.method == 'POST':
        # Only admins and HR can edit employee information
        if not (is_admin or is_hr):
            messages.error(request, 'Access denied. Only administrators and HR can edit employee information.')
            return redirect('employer_edit_employee', employee_id=employee_id)
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        date_of_birth_input = request.POST.get('date_of_birth')
        employee_id_field = request.POST.get('employee_id')
        department = request.POST.get('department')
        position = request.POST.get('position')
        job_title = request.POST.get('job_title')
        salary = request.POST.get('salary')
        pay_grade = request.POST.get('pay_grade')
        hire_date_input = request.POST.get('hire_date')
        bank_name = request.POST.get('bank_name')
        account_number = request.POST.get('account_number')
        bank_branch = request.POST.get('bank_branch')
        include_on_payroll = request.POST.get('on_payroll') == 'on'
        emergency_contact_name = request.POST.get('emergency_contact_name')
        emergency_contact_phone = request.POST.get('emergency_contact_phone')
        emergency_contact_email = request.POST.get('emergency_contact_email')
        emergency_contact_address = request.POST.get('emergency_contact_address')
        is_active = request.POST.get('is_active') == 'on'
        employee_role_value = request.POST.get('employee_role') or EmployeeProfile.EmployeeRole.EMPLOYEE
        employment_type_value = request.POST.get('employment_type') or ''
        currency_value = request.POST.get('currency') or EmployeeProfile.Currency.ZMW
        probation_start_input = request.POST.get('probation_start_date')
        probation_end_input = request.POST.get('probation_end_date')
        contract_start_input = request.POST.get('contract_start_date')
        contract_end_input = request.POST.get('contract_end_date')
        temporary_start_input = request.POST.get('temporary_start_date')
        temporary_end_input = request.POST.get('temporary_end_date')
        profile_picture_file = request.FILES.get('profile_picture')
        supervisor_id = request.POST.get('supervisor')
        branch_id = request.POST.get('branch')
        require_gps = request.POST.get('require_gps_attendance') == 'on'
        
        if employee_role_value not in EmployeeProfile.EmployeeRole.values:
            employee_role_value = EmployeeProfile.EmployeeRole.EMPLOYEE
        
        if employment_type_value and employment_type_value not in EmployeeProfile.EmploymentType.values:
            employment_type_value = ''
        
        if currency_value not in EmployeeProfile.Currency.values:
            currency_value = EmployeeProfile.Currency.ZMW

        def parse_date(value, label):
            if not value:
                return None
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, f'Invalid {label}. Use YYYY-MM-DD format.')
                return None

        probation_start = parse_date(probation_start_input, 'probation start date')
        if probation_start_input and probation_start is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        probation_end = parse_date(probation_end_input, 'probation end date')
        if probation_end_input and probation_end is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        contract_start = parse_date(contract_start_input, 'contract start date')
        if contract_start_input and contract_start is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        contract_end = parse_date(contract_end_input, 'contract end date')
        if contract_end_input and contract_end is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        temporary_start = parse_date(temporary_start_input, 'temporary start date')
        if temporary_start_input and temporary_start is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        temporary_end = parse_date(temporary_end_input, 'temporary end date')
        if temporary_end_input and temporary_end is None:
            return redirect('employer_edit_employee', employee_id=employee_id)

        if employment_type_value == EmployeeProfile.EmploymentType.PROBATION:
            if not (probation_start and probation_end):
                messages.error(request, 'Probation employees require start and end dates.')
                return redirect('employer_edit_employee', employee_id=employee_id)
            if probation_end < probation_start:
                messages.error(request, 'Probation end date cannot be earlier than the start date.')
                return redirect('employer_edit_employee', employee_id=employee_id)
        else:
            probation_start = None
            probation_end = None

        if employment_type_value == EmployeeProfile.EmploymentType.CONTRACT:
            if not (contract_start and contract_end):
                messages.error(request, 'Contract employees require start and end dates.')
                return redirect('employer_edit_employee', employee_id=employee_id)
            if contract_end < contract_start:
                messages.error(request, 'Contract end date cannot be earlier than the start date.')
                return redirect('employer_edit_employee', employee_id=employee_id)
        else:
            contract_start = None
            contract_end = None

        if employment_type_value == EmployeeProfile.EmploymentType.TEMPORARY:
            if not (temporary_start and temporary_end):
                messages.error(request, 'Temporary employees require start and end dates.')
                return redirect('employer_edit_employee', employee_id=employee_id)
            if temporary_end < temporary_start:
                messages.error(request, 'Temporary end date cannot be earlier than the start date.')
                return redirect('employer_edit_employee', employee_id=employee_id)
        else:
            temporary_start = None
            temporary_end = None

        hire_date_value = None
        if hire_date_input:
            try:
                hire_date_value = datetime.strptime(hire_date_input, '%Y-%m-%d').date()
            except ValueError:
                hire_date_value = None

        date_of_birth_value = None
        if date_of_birth_input:
            try:
                date_of_birth_value = datetime.strptime(date_of_birth_input, '%Y-%m-%d').date()
            except ValueError:
                date_of_birth_value = None

        # Check if email is being changed and already exists
        if email != employee.email and User.objects.filter(email=email).exists():
            messages.error(request, 'An employee with this email already exists.')
            return redirect('employer_edit_employee', employee_id=employee_id)

        try:
            # Update user
            employee.first_name = first_name
            employee.last_name = last_name
            employee.email = email
            employee.phone_number = phone  # Fixed: User model has phone_number, not phone
            # Note: address and date_of_birth should be in EmployeeProfile, not User
            employee.is_active = is_active
            # Profile picture is also typically in EmployeeProfile
            employee.save()

            # Update employee profile
            profile, created = EmployeeProfile.objects.get_or_create(user=employee)
            profile.employee_id = employee_id_field
            profile.department = department or ''
            profile.job_title = job_title or position or ''
            profile.salary = Decimal(salary) if salary else None
            profile.currency = currency_value
            profile.pay_grade = pay_grade or ''
            profile.date_hired = hire_date_value if hire_date_value else profile.date_hired
            profile.probation_start_date = probation_start
            profile.probation_end_date = probation_end
            profile.contract_start_date = contract_start
            profile.contract_end_date = contract_end
            profile.temporary_start_date = temporary_start
            profile.temporary_end_date = temporary_end
            profile.bank_name = bank_name or ''
            profile.account_number = account_number or ''
            profile.bank_branch = bank_branch or ''
            profile.emergency_contact_name = emergency_contact_name or ''
            profile.emergency_contact_phone = emergency_contact_phone or ''
            profile.emergency_contact_email = emergency_contact_email or ''
            profile.emergency_contact_address = emergency_contact_address or ''
            profile.employee_role = employee_role_value
            profile.employment_type = employment_type_value
            profile.on_payroll = include_on_payroll
            # Signature image + PIN for e-form signing
            if signature_image_file:
                profile.signature_image = signature_image_file
            if signature_pin_input:
                profile.signature_pin_hash = make_password(signature_pin_input)
            
            # Assign supervisor
            if supervisor_id:
                try:
                    supervisor = User.objects.get(id=supervisor_id, company=company)
                    profile.supervisor = supervisor
                except User.DoesNotExist:
                    profile.supervisor = None
            else:
                profile.supervisor = None
            
            # Assign branch
            if branch_id:
                try:
                    branch = CompanyBranch.objects.get(id=branch_id, company=company)
                    profile.branch = branch
                except CompanyBranch.DoesNotExist:
                    profile.branch = None
            else:
                profile.branch = None
            
            # Set GPS tracking requirement
            profile.require_gps_attendance = require_gps
            
            if not profile.company:
                profile.company = company
            profile.save()

            messages.success(request, f'Employee {first_name} {last_name} has been updated successfully! All changes saved.')
            return redirect('employer_edit_employee', employee_id=employee_id)

        except Exception as e:
            messages.error(request, f'Error updating employee: {str(e)}')
            return redirect('employer_edit_employee', employee_id=employee_id)

    # Get employee profile
    profile_instance, _ = ensure_employee_profile(employee, company)

    # Prepare document context
    categories = list(DocumentCategory.objects.all().order_by('-is_required', 'name'))
    document_type_labels = dict(EmployeeDocument.DocumentType.choices)
    employee_documents = list(
        EmployeeDocument.objects.filter(employee=employee)
        .select_related('category', 'uploaded_by', 'approved_by')
        .order_by('-created_at', '-version')
    )

    documents_by_category = []
    for category in categories:
        category_docs = [doc for doc in employee_documents if doc.category_id == category.id]
        default_document_type = category.default_document_type or EmployeeDocument.DocumentType.OTHER
        if default_document_type not in document_type_labels:
            default_document_type = EmployeeDocument.DocumentType.OTHER
        documents_by_category.append({
            'category': category,
            'documents': category_docs,
            'is_required': category.is_required,
            'is_completed': bool(category_docs),
            'default_document_type': default_document_type,
            'default_document_type_label': document_type_labels.get(default_document_type, document_type_labels.get(EmployeeDocument.DocumentType.OTHER)),
            'tab_id': f"category-{category.id}",
        })

    uncategorized_documents = [doc for doc in employee_documents if doc.category_id is None]
    required_total = sum(1 for entry in documents_by_category if entry['is_required'])
    required_completed = sum(1 for entry in documents_by_category if entry['is_required'] and entry['is_completed'])

    selected_role = getattr(profile_instance, 'employee_role', EmployeeProfile.EmployeeRole.EMPLOYEE) or EmployeeProfile.EmployeeRole.EMPLOYEE
    selected_employment_type = getattr(profile_instance, 'employment_type', '') or ''
    selected_currency = getattr(profile_instance, 'currency', EmployeeProfile.Currency.ZMW) or EmployeeProfile.Currency.ZMW
    
    # Get company configuration options
    departments = CompanyDepartment.objects.filter(company=company).order_by('name')
    positions = CompanyPosition.objects.filter(company=company).order_by('name')
    pay_grades = CompanyPayGrade.objects.filter(company=company).order_by('name')
    company_branches = CompanyBranch.objects.filter(company=company, is_active=True).order_by('-is_head_office', 'name')
    
    # Get available supervisors (users with SUPERVISOR role or higher, excluding the current employee)
    available_supervisors = User.objects.filter(
        company=company,
        is_active=True
    ).filter(
        employee_profile__employee_role__in=['SUPERVISOR', 'HR', 'ADMINISTRATOR']
    ).exclude(
        id=employee.id
    ).select_related('employee_profile').order_by('first_name', 'last_name')

    # Calculate profile completeness
    profile_fields = {
        'employee_id': bool(profile_instance.employee_id),
        'department': bool(profile_instance.department),
        'job_title': bool(profile_instance.job_title),
        'date_hired': bool(profile_instance.date_hired),
        'salary': bool(profile_instance.salary),
        'employment_type': bool(profile_instance.employment_type),
        'phone': bool(employee.phone_number),
        'email': bool(employee.email),
        'bank_info': bool(profile_instance.bank_name and profile_instance.account_number),
        'emergency_contact': bool(profile_instance.emergency_contact_name and profile_instance.emergency_contact_phone),
    }
    completed_fields = sum(profile_fields.values())
    total_fields = len(profile_fields)
    profile_completeness = round((completed_fields / total_fields) * 100) if total_fields > 0 else 0

    # Get employee statistics
    from datetime import date, timedelta
    today = date.today()
    month_ago = today - timedelta(days=30)
    
    # Attendance statistics
    from blu_staff.apps.attendance.models import Attendance
    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__gte=month_ago
    )
    total_attendance_days = attendance_records.count()
    present_days = attendance_records.filter(status='PRESENT').count()
    late_days = attendance_records.filter(status='LATE').count()
    absent_days = attendance_records.filter(status='ABSENT').count()
    attendance_rate = round((present_days / total_attendance_days * 100) if total_attendance_days > 0 else 0, 1)

    # Leave statistics
    from blu_staff.apps.attendance.models import LeaveRequest
    leave_requests = LeaveRequest.objects.filter(employee=employee)
    pending_leaves = leave_requests.filter(status='PENDING').count()
    approved_leaves = leave_requests.filter(status='APPROVED').count()
    rejected_leaves = leave_requests.filter(status='REJECTED').count()
    
    # Recent leave requests
    recent_leaves = leave_requests.order_by('-created_at')[:5]

    # Document statistics
    total_documents = len(employee_documents)
    pending_documents = sum(1 for doc in employee_documents if doc.status == 'PENDING')
    approved_documents = sum(1 for doc in employee_documents if doc.status == 'APPROVED')

    # Performance reviews - PERFORMANCE MODULE DISABLED
    # from blu_staff.apps.performance.models import PerformanceReview
    # performance_reviews = PerformanceReview.objects.filter(
    #     employee=employee
    # ).select_related('reviewer').order_by('-review_date')[:5]
    performance_reviews = []
    
    # Employee assets
    try:
        from blu_assets.models import EmployeeAsset
        employee_assets = EmployeeAsset.objects.filter(employee=employee).order_by('-assigned_date')
        employee_assets_count = employee_assets.count()
        # Get assignable assets: unassigned and in AVAILABLE status
        available_assets = EmployeeAsset.objects.filter(
            employee__isnull=True,
            status='AVAILABLE'
        ).order_by('asset_tag')
        unavailable_asset_count = EmployeeAsset.objects.exclude(
            employee__isnull=True,
            status='AVAILABLE'
        ).count()
    except ImportError:
        employee_assets = []
        employee_assets_count = 0
        available_assets = []
        unavailable_asset_count = 0
    
    # Calculate days employed
    days_employed = (today - profile_instance.date_hired).days if profile_instance.date_hired else 0
    years_employed = days_employed // 365
    months_employed = (days_employed % 365) // 30

    # Contract expiry warning
    contract_expiry_warning = None
    if profile_instance.employment_type == 'CONTRACT' and profile_instance.contract_end_date:
        days_until_expiry = (profile_instance.contract_end_date - today).days
        if 0 <= days_until_expiry <= 90:
            contract_expiry_warning = {
                'days': days_until_expiry,
                'date': profile_instance.contract_end_date,
                'is_critical': days_until_expiry <= 30
            }
    elif profile_instance.employment_type == 'PROBATION' and profile_instance.probation_end_date:
        days_until_expiry = (profile_instance.probation_end_date - today).days
        if 0 <= days_until_expiry <= 90:
            contract_expiry_warning = {
                'days': days_until_expiry,
                'date': profile_instance.probation_end_date,
                'is_critical': days_until_expiry <= 30,
                'type': 'Probation'
            }
    elif profile_instance.employment_type == 'TEMPORARY' and profile_instance.temporary_end_date:
        days_until_expiry = (profile_instance.temporary_end_date - today).days
        if 0 <= days_until_expiry <= 90:
            contract_expiry_warning = {
                'days': days_until_expiry,
                'date': profile_instance.temporary_end_date,
                'is_critical': days_until_expiry <= 30,
                'type': 'Temporary'
            }

    # Determine which base template to use
    # HR users and supervisors use employee navigation
    if is_hr or (is_supervising and not is_admin):
        base_template = 'ems/base_employee.html'
    else:
        base_template = 'ems/base_employer.html'  # Only true admins use employer navigation
    
    context = {
        'user': request.user,
        'company': company,
        'employee': employee,
        'profile': profile_instance,
        'base_template': base_template,
        'employee_role_choices': EmployeeProfile.EmployeeRole.choices,
        'selected_employee_role': selected_role,
        'employment_type_choices': EmployeeProfile.EmploymentType.choices,
        'selected_employment_type': selected_employment_type,
        'currency_choices': EmployeeProfile.Currency.choices,
        'selected_currency': selected_currency,
        'documents_by_category': documents_by_category,
        'uncategorized_documents': uncategorized_documents,
        'required_documents_total': required_total,
        'required_documents_completed': required_completed,
        'company_departments': departments,
        'company_positions': positions,
        'company_pay_grades': pay_grades,
        'company_branches': company_branches,
        'available_supervisors': available_supervisors,
        
        # Permission flags
        'is_admin': is_admin,
        'is_supervisor_view': is_supervising and not is_admin,
        
        # Enhanced statistics
        'profile_completeness': profile_completeness,
        'profile_fields': profile_fields,
        'completed_fields': completed_fields,
        'total_fields': total_fields,
        
        # Attendance stats
        'attendance_rate': attendance_rate,
        'present_days': present_days,
        'late_days': late_days,
        'absent_days': absent_days,
        'total_attendance_days': total_attendance_days,
        
        # Leave stats
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'rejected_leaves': rejected_leaves,
        'recent_leaves': recent_leaves,
        
        # Document stats
        'total_documents': total_documents,
        'pending_documents': pending_documents,
        'approved_documents': approved_documents,
        'employee_documents': employee_documents,
        'employee_documents_count': total_documents,
        
        # Assets
        'employee_assets': employee_assets,
        'employee_assets_count': employee_assets_count,
        'available_assets': available_assets,
        
        # Performance
        'performance_reviews': performance_reviews,
        'performance_reviews_count': performance_reviews.count() if performance_reviews else 0,
        
        # Employment info
        'days_employed': days_employed,
        'years_employed': years_employed,
        'months_employed': months_employed,
        'contract_expiry_warning': contract_expiry_warning,
    }
    context.update(_get_employer_nav_context(request.user))

    return render(request, 'ems/employer_edit_employee.html', context)


@login_required
@require_http_methods(["POST"])
def document_upload(request):
    """Handle document upload for employees"""
    try:
        from blu_staff.apps.documents.models import EmployeeDocument
        
        employee_id = request.POST.get('employee_id')
        document_type = request.POST.get('document_type')
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        file = request.FILES.get('file')
        
        if not all([employee_id, document_type, title, file]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        employee = User.objects.get(id=employee_id)
        
        # Check permissions
        if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
            if request.user.id != employee.id:
                return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Create document
        document = EmployeeDocument.objects.create(
            employee=employee,
            document_type=document_type,
            title=title,
            description=description,
            file=file,
            uploaded_by=request.user,
            status='PENDING'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Document uploaded successfully',
            'document_id': document.id
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def asset_assign(request):
    """Handle asset assignment to employees (assign existing asset from inventory)"""
    try:
        from blu_assets.models import EmployeeAsset
        from datetime import date
        
        employee_id = request.POST.get('employee_id')
        asset_id = request.POST.get('asset_id')
        notes = request.POST.get('notes', '')
        
        if not employee_id or not asset_id:
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        employee = User.objects.get(id=employee_id)
        
        # Check permissions
        if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Get the asset
        try:
            asset = EmployeeAsset.objects.get(id=asset_id)
        except EmployeeAsset.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Asset not found'})
        
        # Check if asset is already assigned
        if asset.employee is not None:
            return JsonResponse({'success': False, 'error': f'Asset is already assigned to {asset.employee.get_full_name()}'})
        
        # Check if asset is available
        if asset.status != 'AVAILABLE':
            return JsonResponse({'success': False, 'error': f'Asset is not available. Current status: {asset.get_status_display()}'})
        
        # Assign the asset
        asset.employee = employee
        asset.status = 'ASSIGNED'
        asset.assigned_date = date.today()
        asset.assigned_by = request.user
        if notes:
            asset.notes = notes if not asset.notes else f"{asset.notes}\n\n[{date.today()}] {notes}"
        asset.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Asset {asset.asset_tag} assigned successfully to {employee.get_full_name()}',
            'asset_id': asset.id
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def employee_reset_password(request):
    """Reset employee password"""
    try:
        employee_id = request.POST.get('employee_id')
        new_password = request.POST.get('new_password')
        
        if not employee_id or not new_password:
            return JsonResponse({'success': False, 'error': 'Missing employee ID or password'})
        
        employee = User.objects.get(id=employee_id)
        
        # Check permissions - only employers can reset passwords
        if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Reset password
        employee.set_password(new_password)
        employee.save()
        
        # Send email notification
        try:
            from ems_project.notifications import EmailNotificationService
            EmailNotificationService.send_password_changed_notification(
                employee=employee,
                new_password=new_password,
                changed_by=request.user
            )
        except Exception:
            pass  # Don't fail password reset if email fails
        
        return JsonResponse({
            'success': True,
            'message': 'Password reset successfully'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def employee_print_profile(request):
    """Printable employee profile page"""
    has_profile = hasattr(request.user, 'employee_profile') and request.user.employee_profile
    if not has_profile and getattr(request.user, 'role', '') != 'EMPLOYEE':
        return render(request, 'ems/unauthorized.html')

    employee = request.user
    profile = EmployeeProfile.objects.filter(user=employee).first()

    context = {
        'employee': employee,
        'profile': profile,
    }
    return render(request, 'ems/employee_print_profile.html', context)


@login_required
def employee_my_payslips(request):
    """Employee's personal payslip history - accessible by any user with an employee profile"""
    has_profile = hasattr(request.user, 'employee_profile') and request.user.employee_profile
    if not has_profile and getattr(request.user, 'role', '') != 'EMPLOYEE':
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.payroll.models import Payroll
    from datetime import date

    payslips = Payroll.objects.filter(
        employee=request.user,
        status__in=['APPROVED', 'PAID']
    ).order_by('-period_start')

    # Summary stats
    today = date.today()
    current_year_payslips = payslips.filter(period_start__year=today.year)
    total_earned_ytd = sum(p.net_pay for p in current_year_payslips)
    total_deductions_ytd = sum(p.total_deductions for p in current_year_payslips)
    latest_payslip = payslips.first()

    context = {
        'payslips': payslips,
        'total_earned_ytd': total_earned_ytd,
        'total_deductions_ytd': total_deductions_ytd,
        'latest_payslip': latest_payslip,
        'current_year': today.year,
        'base_template': 'ems/base_employee.html' if request.user.role == 'EMPLOYEE' else 'ems/base_employer.html',
    }
    return render(request, 'ems/employee_my_payslips.html', context)


@login_required
@require_http_methods(["POST"])
def employee_profile_picture_upload(request):
    """Handle profile picture upload for employees"""
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    import os
    from io import BytesIO
    
    try:
        from PIL import Image
    except ImportError:
        return JsonResponse({
            'success': False, 
            'error': 'Image processing library (Pillow) not installed. Please contact administrator.'
        })
    
    try:
        employee_id = request.POST.get('employee_id')
        profile_picture = request.FILES.get('profile_picture')
        
        if not employee_id or not profile_picture:
            return JsonResponse({'success': False, 'error': 'Missing employee ID or file'})
        
        # Get employee
        employee = User.objects.get(id=employee_id)
        
        # Check permissions
        if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
            # Check if user is editing their own profile
            if request.user.id != employee.id:
                return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if profile_picture.content_type not in allowed_types:
            return JsonResponse({'success': False, 'error': 'Invalid file type. Only JPG and PNG are allowed'})
        
        # Validate file size (5MB max)
        if profile_picture.size > 5 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File too large. Maximum size is 5MB'})
        
        # Process image with Pillow to resize and optimize
        try:
            image = Image.open(profile_picture)
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize to 400x400 maintaining aspect ratio
            image.thumbnail((400, 400), Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = BytesIO()
            image.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            # Delete old profile picture if exists
            if employee.profile_picture:
                try:
                    default_storage.delete(employee.profile_picture.path)
                except:
                    pass
            
            # Generate filename
            ext = 'jpg'
            filename = f'profile_pictures/employee_{employee.id}_{int(timezone.now().timestamp())}.{ext}'
            
            # Save new file
            employee.profile_picture.save(filename, ContentFile(output.read()), save=True)
            
            return JsonResponse({
                'success': True,
                'message': 'Profile picture updated successfully',
                'url': employee.profile_picture.url
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error processing image: {str(e)}'})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def bulk_employee_import(request):
    """Bulk import employees from CSV/Excel"""
    if not _has_hr_access(request.user):
        return render(request, 'ems/unauthorized.html')
    
    if request.method == 'POST':
        import csv
        import io
        
        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'Please upload a file')
            return redirect('bulk_employee_import')
        
        # Check file extension
        if not file.name.endswith('.csv'):
            messages.error(request, 'Only CSV files are supported')
            return redirect('bulk_employee_import')
        
        try:
            # Read CSV
            decoded_file = file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            imported = 0
            errors = []
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Required fields
                    email = row.get('email', '').strip()
                    first_name = row.get('first_name', '').strip()
                    last_name = row.get('last_name', '').strip()
                    
                    if not all([email, first_name, last_name]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Check if user exists
                    if User.objects.filter(email=email).exists():
                        errors.append(f"Row {row_num}: Email {email} already exists")
                        continue
                    
                    # Create user
                    temp_password = 'TempPass123!'
                    user = User.objects.create_user(
                        email=email,
                        username=email,
                        first_name=first_name,
                        last_name=last_name,
                        password=temp_password,
                        role='EMPLOYEE',
                        company=request.user.company
                    )
                    
                    # Create profile
                    profile, created = EmployeeProfile.objects.get_or_create(user=user)
                    profile.employee_id = row.get('employee_id', '')
                    profile.job_title = row.get('job_title', '')
                    profile.department = row.get('department', '')
                    profile.phone_number = row.get('phone_number', '')
                    profile.date_hired = row.get('date_hired', None)
                    profile.save()
                    
                    # Send welcome email
                    try:
                        from ems_project.notifications import EmailNotificationService
                        EmailNotificationService.send_new_employee_credentials(
                            employee=user,
                            temporary_password=temp_password,
                            created_by=request.user
                        )
                    except Exception as email_error:
                        # Don't fail import if email fails
                        errors.append(f"Row {row_num}: Imported but email failed - {str(email_error)}")
                    
                    imported += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            # Show results
            if imported > 0:
                messages.success(request, f'Successfully imported {imported} employees')
            if errors:
                for error in errors[:10]:  # Show first 10 errors
                    messages.warning(request, error)
                if len(errors) > 10:
                    messages.warning(request, f'...and {len(errors) - 10} more errors')
            
            return redirect('bulk_employee_import')
            
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('bulk_employee_import')
    
    is_admin_user = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or getattr(request.user, 'is_employer_admin', False)
    base_template = 'ems/base_employer.html' if is_admin_user else 'ems/base_employee.html'
    context = {'base_template': base_template}
    if is_admin_user:
        context.update(_get_employer_nav_context(request.user))
    return render(request, 'ems/bulk_employee_import.html', context)


@login_required
def reports_center(request):
    """Reports and exports center"""
    # Allow admins, HR, supervisors, and accountants/finance roles
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin
    is_hr = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'HR'
    )
    is_accountant = hasattr(request.user, 'employee_profile') and request.user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS']
    is_supervisor = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'SUPERVISOR'
    )

    if not (is_admin or is_hr or is_accountant or is_supervisor):
        messages.error(request, 'Access denied. Only administrators, HR, supervisors, and accountants can access reports.')
        return render(request, 'ems/unauthorized.html')

    # Feature gate only for admin/accountant — HR and supervisors bypass
    if not (is_supervisor or is_hr):
        from ems_project.plan_features import company_has_feature, FEAT_CUSTOM_REPORTS
        company = getattr(request.user, 'company', None)
        # If no company (e.g., platform admin), skip feature gate
        if company and not company_has_feature(company, FEAT_CUSTOM_REPORTS):
            messages.error(request, 'Reports feature not enabled for this plan.')
            return render(request, 'ems/unauthorized.html')
    
    from blu_staff.apps.attendance.models import Attendance, LeaveRequest
    from blu_staff.apps.documents.models import EmployeeDocument
    from datetime import date, timedelta
    
    # Get employer's company
    if request.user.role == 'ADMINISTRATOR':
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        if is_supervisor:
            employees = User.objects.filter(role='EMPLOYEE', employee_profile__supervisor=request.user)
        else:
            employees = User.objects.filter(company=request.user.company, role='EMPLOYEE')
    
    today = date.today()
    
    # Report statistics
    stats = {
        'total_employees': employees.count(),
        'active_employees': employees.filter(is_active=True).count(),
        'total_attendance_records': Attendance.objects.filter(employee__in=employees).count(),
        'total_leave_requests': LeaveRequest.objects.filter(employee__in=employees).count(),
        'total_documents': EmployeeDocument.objects.filter(employee__in=employees).count(),
    }
    
    # Determine base template based on role
    if (is_accountant and not is_admin) or is_supervisor:
        base_template = 'ems/base_employee.html'
    else:
        base_template = 'ems/base_employer.html'
    
    context = {
        'stats': stats,
        'today': today,
        'base_template': base_template,
    }
    
    return render(request, 'ems/reports_center.html', context)


@login_required
def export_employee_roster(request):
    """Export employee roster to CSV"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    
    # Get employees (company-scoped)
    company = getattr(request.user, 'company', None)
    if not company:
        return JsonResponse({'error': 'No company associated'}, status=403)
    
    employees = User.objects.filter(company=company, role='EMPLOYEE').select_related('employee_profile')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="employee_roster_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee ID', 'First Name', 'Last Name', 'Email', 'Phone', 
        'Department', 'Job Title', 'Employment Type', 'Date Hired', 
        'Status'
    ])
    
    for emp in employees:
        try:
            profile = emp.employee_profile
            emp_id = profile.employee_id or ''
            phone = profile.phone_number or ''
            dept = profile.department or ''
            job_title = profile.job_title or ''
            emp_type = profile.employment_type or ''
            date_hired = profile.date_hired or ''
        except:
            emp_id = phone = dept = job_title = emp_type = date_hired = ''
        
        writer.writerow([
            emp_id,
            emp.first_name,
            emp.last_name,
            emp.email,
            phone,
            dept,
            job_title,
            emp_type,
            date_hired,
            'Active' if emp.is_active else 'Inactive'
        ])
    
    return response


@login_required
def export_attendance_report(request):
    """Export attendance report to CSV"""
    is_supervisor = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'SUPERVISOR'
    )
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin or is_supervisor):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    from blu_staff.apps.attendance.models import Attendance
    
    # Get employees (company-scoped)
    company = getattr(request.user, 'company', None)
    if not company and request.user.role == 'ADMINISTRATOR':
        return JsonResponse({'error': 'No company associated'}, status=403)
    
    if is_supervisor:
        employees = User.objects.filter(role='EMPLOYEE', employee_profile__supervisor=request.user, company=company)
    else:
        employees = User.objects.filter(company=company, role='EMPLOYEE')
    
    # Get attendance records (last 30 days)
    from datetime import timedelta
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    attendance_records = Attendance.objects.filter(
        employee__in=employees,
        date__range=[start_date, end_date]
    ).select_related('employee', 'employee__employee_profile').order_by('-date', 'employee__last_name')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Employee ID', 'Employee Name', 'Department', 
        'Check In', 'Check Out', 'Status', 'Late', 'Hours Worked', 
        'GPS Latitude', 'GPS Longitude', 'GPS Location', 'Notes'
    ])
    
    for record in attendance_records:
        try:
            emp_id = record.employee.employee_profile.employee_id or ''
            dept = record.employee.employee_profile.department or ''
        except:
            emp_id = dept = ''
        
        writer.writerow([
            record.date,
            emp_id,
            record.employee.get_full_name(),
            dept,
            record.check_in.strftime('%H:%M:%S') if record.check_in else '',
            record.check_out.strftime('%H:%M:%S') if record.check_out else '',
            record.get_status_display(),
            'Yes' if record.status == 'LATE' else 'No',
            record.working_hours or '',
            record.latitude or '',
            record.longitude or '',
            record.location or '',
            record.notes or ''
        ])
    
    return response


@login_required
def export_leave_report(request):
    """Export leave report to CSV"""
    is_supervisor = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'SUPERVISOR'
    )
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin or is_supervisor):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    from blu_staff.apps.attendance.models import LeaveRequest
    
    # Get employees (company-scoped)
    company = getattr(request.user, 'company', None)
    if not company and request.user.role == 'ADMINISTRATOR':
        return JsonResponse({'error': 'No company associated'}, status=403)
    
    if is_supervisor:
        employees = User.objects.filter(role='EMPLOYEE', employee_profile__supervisor=request.user, company=company)
    else:
        employees = User.objects.filter(company=company, role='EMPLOYEE')
    
    leave_requests = LeaveRequest.objects.filter(
        employee__in=employees
    ).select_related('employee', 'employee__employee_profile', 'approved_by').order_by('-created_at')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leave_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee ID', 'Employee Name', 'Department', 'Leave Type', 
        'Start Date', 'End Date', 'Total Days', 'Status', 'Reason', 
        'Approved By', 'Created Date'
    ])
    
    for leave in leave_requests:
        try:
            emp_id = leave.employee.employee_profile.employee_id or ''
            dept = leave.employee.employee_profile.department or ''
        except:
            emp_id = dept = ''
        
        writer.writerow([
            emp_id,
            leave.employee.get_full_name(),
            dept,
            leave.leave_type,
            leave.start_date,
            leave.end_date,
            leave.total_days,
            leave.status,
            leave.reason or '',
            leave.approved_by.get_full_name() if leave.approved_by else '',
            leave.created_at.strftime('%Y-%m-%d')
        ])
    
    return response


@login_required
def export_documents_report(request):
    """Export documents report to CSV"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    from blu_staff.apps.documents.models import EmployeeDocument
    
    # Get employees (company-scoped)
    company = getattr(request.user, 'company', None)
    if not company:
        return JsonResponse({'error': 'No company associated'}, status=403)
    
    employees = User.objects.filter(company=company, role='EMPLOYEE')
    
    documents = EmployeeDocument.objects.filter(
        employee__in=employees
    ).select_related('employee', 'employee__employee_profile', 'uploaded_by', 'approved_by').order_by('-created_at')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="documents_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee ID', 'Employee Name', 'Document Type', 'Title', 
        'Status', 'Uploaded Date', 'Uploaded By', 'Approved By', 
        'Expiry Date', 'File Size (KB)'
    ])
    
    for doc in documents:
        try:
            emp_id = doc.employee.employee_profile.employee_id or ''
        except:
            emp_id = ''
        
        file_size = doc.file_size / 1024 if doc.file_size else 0
        writer.writerow([
            emp_id,
            doc.employee.get_full_name(),
            doc.get_document_type_display(),
            doc.title,
            doc.status,
            doc.created_at.strftime('%Y-%m-%d'),
            doc.uploaded_by.get_full_name() if doc.uploaded_by else '',
            doc.approved_by.get_full_name() if doc.approved_by else '',
            doc.expiry_date or '',
            f'{file_size:.2f}'
        ])
    
    return response


@login_required
def export_assets_report(request):
    """Export assets report to CSV"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    
    try:
        from blu_assets.models import EmployeeAsset
        
        # Get employees (company-scoped)
        company = getattr(request.user, 'company', None)
        if not company:
            return JsonResponse({'error': 'No company associated'}, status=403)
        
        employees = User.objects.filter(company=company, role='EMPLOYEE')
        
        assets = EmployeeAsset.objects.filter(
            Q(employee__in=employees) | Q(employee__isnull=True)
        ).select_related('employee', 'assigned_by', 'category').order_by('-assigned_date')
        
        # Create CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="assets_report_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Asset Tag', 'Asset Name', 'Type', 'Serial Number', 'Brand', 'Model',
            'Assigned To', 'Employee ID', 'Status', 'Condition', 
            'Assigned Date', 'Days With Employee', 'Purchase Date', 'Purchase Price'
        ])
        
        for asset in assets:
            if asset.employee:
                try:
                    emp_id = asset.employee.employee_profile.employee_id or ''
                except:
                    emp_id = ''
                emp_name = asset.employee.get_full_name()
            else:
                emp_id = ''
                emp_name = 'Unassigned'
            
            writer.writerow([
                asset.asset_tag,
                asset.name,
                asset.get_asset_type_display(),
                asset.serial_number or '',
                asset.brand or '',
                asset.model or '',
                emp_name,
                emp_id,
                asset.get_status_display(),
                asset.get_condition_display(),
                asset.assigned_date or '',
                asset.days_with_employee if asset.employee else '',
                asset.purchase_date or '',
                asset.purchase_price or ''
            ])
        
        return response
    except ImportError:
        return JsonResponse({'error': 'Assets module not available'}, status=404)


def _report_permission_check(request):
    """Shared permission check for report views."""
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin
    is_accountant = (hasattr(request.user, 'employee_profile') and
                     request.user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    is_hr = (hasattr(request.user, 'employee_profile') and
             request.user.employee_profile.employee_role == 'HR')
    allowed = is_admin or is_accountant or is_hr
    base_template = 'ems/base_employee.html' if (is_accountant and not is_admin) else 'ems/base_employer.html'
    return allowed, base_template


def _report_employees(request):
    """Get scoped employee queryset for reports."""
    if request.user.role == 'ADMINISTRATOR':
        return User.objects.filter(role='EMPLOYEE').select_related('employee_profile')
    return User.objects.filter(company=request.user.company, role='EMPLOYEE').select_related('employee_profile')


@login_required
def report_employee_roster(request):
    """Employee Roster Report - workforce analytics with dept breakdown, tenure, employment type distribution"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    from datetime import date, timedelta
    import json

    employees = _report_employees(request)
    today = date.today()

    # === Summary Stats ===
    total = employees.count()
    active = employees.filter(is_active=True).count()
    inactive = total - active
    new_hires_30d = employees.filter(
        employee_profile__date_hired__gte=today - timedelta(days=30)
    ).count()

    # === Department Breakdown ===
    dept_data = (
        employees.filter(is_active=True)
        .exclude(employee_profile__department='')
        .exclude(employee_profile__department__isnull=True)
        .values('employee_profile__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    dept_breakdown = [{'name': d['employee_profile__department'], 'count': d['count']} for d in dept_data]
    dept_labels = json.dumps([d['name'] for d in dept_breakdown])
    dept_counts = json.dumps([d['count'] for d in dept_breakdown])

    # === Employment Type Distribution ===
    type_data = (
        employees.filter(is_active=True)
        .exclude(employee_profile__employment_type='')
        .exclude(employee_profile__employment_type__isnull=True)
        .values('employee_profile__employment_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    type_breakdown = [{'name': t['employee_profile__employment_type'], 'count': t['count']} for t in type_data]
    type_labels = json.dumps([t['name'] for t in type_breakdown])
    type_counts = json.dumps([t['count'] for t in type_breakdown])

    # === Tenure Analysis ===
    tenure_buckets = {'< 3 months': 0, '3-6 months': 0, '6-12 months': 0, '1-2 years': 0, '2-5 years': 0, '5+ years': 0}
    for emp in employees.filter(is_active=True):
        try:
            hired = emp.employee_profile.date_hired
            if not hired:
                continue
            days = (today - hired).days
            if days < 90:
                tenure_buckets['< 3 months'] += 1
            elif days < 180:
                tenure_buckets['3-6 months'] += 1
            elif days < 365:
                tenure_buckets['6-12 months'] += 1
            elif days < 730:
                tenure_buckets['1-2 years'] += 1
            elif days < 1825:
                tenure_buckets['2-5 years'] += 1
            else:
                tenure_buckets['5+ years'] += 1
        except Exception:
            pass
    tenure_labels = json.dumps(list(tenure_buckets.keys()))
    tenure_counts = json.dumps(list(tenure_buckets.values()))

    # === Monthly Hiring Trend (last 6 months) ===
    hire_trend_labels = []
    hire_trend_data = []
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        hire_trend_labels.append(month_start.strftime('%b %Y'))
        hire_trend_data.append(
            employees.filter(employee_profile__date_hired__range=[month_start, month_end]).count()
        )
    hire_trend_labels_json = json.dumps(hire_trend_labels)
    hire_trend_data_json = json.dumps(hire_trend_data)

    # === Recent Hires (last 30 days) ===
    recent_hires = (
        employees.filter(employee_profile__date_hired__gte=today - timedelta(days=30))
        .order_by('-employee_profile__date_hired')[:10]
    )

    context = {
        'total': total, 'active': active, 'inactive': inactive, 'new_hires_30d': new_hires_30d,
        'dept_breakdown': dept_breakdown, 'dept_labels': dept_labels, 'dept_counts': dept_counts,
        'type_breakdown': type_breakdown, 'type_labels': type_labels, 'type_counts': type_counts,
        'tenure_labels': tenure_labels, 'tenure_counts': tenure_counts,
        'hire_trend_labels': hire_trend_labels_json, 'hire_trend_data': hire_trend_data_json,
        'recent_hires': recent_hires,
        'base_template': base_template,
    }
    return render(request, 'ems/report_employee_roster.html', context)


@login_required
def report_attendance(request):
    """Attendance Report - attendance rate analytics, trends, department breakdown, top absentees"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.attendance.models import Attendance
    from datetime import date, timedelta
    import json

    employees = _report_employees(request)
    company = getattr(request.user, 'company', None)
    today = date.today()
    date_from = request.GET.get('date_from', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', today.strftime('%Y-%m-%d'))
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)

    records = Attendance.objects.filter(
        employee__in=employees, date__range=[start_date, end_date]
    ).select_related('employee', 'employee__employee_profile')

    # === Summary Stats ===
    total_records = records.count()
    present = records.filter(status__in=['PRESENT', 'LATE', 'HALF_DAY']).count()
    absent = records.filter(status='ABSENT').count()
    late = records.filter(status='LATE').count()
    attendance_rate = round((present / total_records * 100), 1) if total_records > 0 else 0

    # === Daily Attendance Trend ===
    trend_labels = []
    trend_present = []
    trend_absent = []
    days_diff = (end_date - start_date).days + 1
    step = max(1, days_diff // 14)
    for offset in range(0, days_diff, step):
        d = start_date + timedelta(days=offset)
        if d > end_date:
            break
        trend_labels.append(d.strftime('%b %d'))
        day_records = records.filter(date=d)
        trend_present.append(day_records.filter(status__in=['PRESENT', 'LATE', 'HALF_DAY']).count())
        trend_absent.append(day_records.filter(status='ABSENT').count())

    # === Attendance by Department ===
    dept_attendance = (
        records.filter(status__in=['PRESENT', 'LATE', 'HALF_DAY'])
        .exclude(employee__employee_profile__department='')
        .exclude(employee__employee_profile__department__isnull=True)
        .values('employee__employee_profile__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    dept_breakdown = [{'name': d['employee__employee_profile__department'], 'count': d['count']} for d in dept_attendance]

    # === Top Absentees ===
    top_absentees = (
        records.filter(status='ABSENT')
        .values('employee__first_name', 'employee__last_name', 'employee__employee_profile__department')
        .annotate(absent_days=Count('id'))
        .order_by('-absent_days')[:10]
    )

    # === Status Distribution ===
    status_dist = records.values('status').annotate(count=Count('id')).order_by('status')
    status_labels = json.dumps([s['status'].replace('_', ' ').title() for s in status_dist])
    status_counts = json.dumps([s['count'] for s in status_dist])

    context = {
        'total_records': total_records, 'present': present, 'absent': absent, 'late': late,
        'attendance_rate': attendance_rate,
        'date_from': date_from, 'date_to': date_to,
        'trend_labels': json.dumps(trend_labels),
        'trend_present': json.dumps(trend_present),
        'trend_absent': json.dumps(trend_absent),
        'dept_breakdown': dept_breakdown,
        'top_absentees': top_absentees,
        'status_labels': status_labels, 'status_counts': status_counts,
        'base_template': base_template,
    }
    return render(request, 'ems/report_attendance.html', context)


@login_required
def report_leave(request):
    """Leave Report - leave usage analytics, type distribution, department breakdown, top users"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.attendance.models import LeaveRequest
    import json

    employees = _report_employees(request)

    records = LeaveRequest.objects.filter(
        employee__in=employees
    ).select_related('employee', 'employee__employee_profile', 'approved_by')

    # === Summary Stats ===
    total = records.count()
    pending = records.filter(status='PENDING').count()
    approved = records.filter(status='APPROVED').count()
    rejected = records.filter(status='REJECTED').count()
    total_days_taken = sum(r.duration or 0 for r in records.filter(status='APPROVED'))

    # === Leave Type Distribution ===
    type_dist = records.values('leave_type').annotate(count=Count('id')).order_by('-count')
    type_labels = json.dumps([str(dict(LeaveRequest.LeaveType.choices).get(t['leave_type'], t['leave_type'])) for t in type_dist])
    type_counts = json.dumps([t['count'] for t in type_dist])

    # === Status Distribution ===
    status_dist = records.values('status').annotate(count=Count('id')).order_by('status')
    status_labels = json.dumps([str(dict(LeaveRequest.Status.choices).get(s['status'], s['status'])) for s in status_dist])
    status_counts = json.dumps([s['count'] for s in status_dist])

    # === Leave by Department ===
    dept_leave = (
        records.filter(status='APPROVED')
        .exclude(employee__employee_profile__department='')
        .exclude(employee__employee_profile__department__isnull=True)
        .values('employee__employee_profile__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    dept_breakdown = [{'name': d['employee__employee_profile__department'], 'count': d['count'], 'days': 0} for d in dept_leave]

    # === Top Leave Users ===
    top_users = (
        records.filter(status='APPROVED')
        .values('employee__first_name', 'employee__last_name', 'employee__employee_profile__department')
        .annotate(leave_count=Count('id'))
        .order_by('-leave_count')[:10]
    )

    # === Monthly Leave Trend (last 6 months) ===
    from datetime import date, timedelta
    today = date.today()
    month_labels = []
    month_data = []
    for i in range(5, -1, -1):
        m = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if m.month == 12:
            m_end = m.replace(year=m.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = m.replace(month=m.month + 1, day=1) - timedelta(days=1)
        month_labels.append(m.strftime('%b %Y'))
        month_data.append(records.filter(status='APPROVED', start_date__range=[m, m_end]).count())

    context = {
        'total': total, 'pending': pending, 'approved': approved, 'rejected': rejected,
        'total_days_taken': total_days_taken,
        'type_labels': type_labels, 'type_counts': type_counts,
        'status_labels': status_labels, 'status_counts': status_counts,
        'dept_breakdown': dept_breakdown, 'top_users': top_users,
        'month_labels': json.dumps(month_labels), 'month_data': json.dumps(month_data),
        'base_template': base_template,
    }
    return render(request, 'ems/report_leave.html', context)


@login_required
def report_documents(request):
    """Documents Report - compliance analytics, expiring docs, type breakdown, employees missing docs"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.documents.models import EmployeeDocument
    from datetime import date, timedelta
    import json

    employees = _report_employees(request)
    today = date.today()

    records = EmployeeDocument.objects.filter(
        employee__in=employees
    ).select_related('employee', 'employee__employee_profile')

    # === Summary Stats ===
    total = records.count()
    approved = records.filter(status='APPROVED').count()
    pending = records.filter(status='PENDING').count()
    rejected = records.filter(status='REJECTED').count()
    compliance_rate = round((approved / total * 100), 1) if total > 0 else 0

    # === Expiring Documents (next 30/60/90 days) ===
    expiring_30 = records.filter(expiry_date__range=[today, today + timedelta(days=30)]).count()
    expiring_60 = records.filter(expiry_date__range=[today, today + timedelta(days=60)]).count()
    expiring_90 = records.filter(expiry_date__range=[today, today + timedelta(days=90)]).count()
    already_expired = records.filter(expiry_date__lt=today).count()

    expiring_soon = records.filter(
        expiry_date__range=[today, today + timedelta(days=30)]
    ).select_related('employee').order_by('expiry_date')[:10]

    # === Document Type Distribution ===
    type_dist = records.values('document_type').annotate(count=Count('id')).order_by('-count')
    type_breakdown = []
    for t in type_dist:
        try:
            label = str(dict(EmployeeDocument.DocumentType.choices).get(t['document_type'], t['document_type']))
        except Exception:
            label = str(t['document_type'] or 'Unknown')
        type_breakdown.append({'name': label, 'count': t['count']})
    type_labels = json.dumps([str(t['name']) for t in type_breakdown])
    type_counts = json.dumps([t['count'] for t in type_breakdown])

    # === Status Distribution ===
    status_dist = records.values('status').annotate(count=Count('id')).order_by('status')
    status_labels = json.dumps([s['status'].replace('_', ' ').title() for s in status_dist])
    status_counts = json.dumps([s['count'] for s in status_dist])

    # === Employees with no documents ===
    employees_with_docs = records.values_list('employee_id', flat=True).distinct()
    employees_no_docs = employees.exclude(id__in=employees_with_docs).count()

    context = {
        'total': total, 'approved': approved, 'pending': pending, 'rejected': rejected,
        'compliance_rate': compliance_rate,
        'expiring_30': expiring_30, 'expiring_60': expiring_60, 'expiring_90': expiring_90,
        'already_expired': already_expired, 'expiring_soon': expiring_soon,
        'type_breakdown': type_breakdown, 'type_labels': type_labels, 'type_counts': type_counts,
        'status_labels': status_labels, 'status_counts': status_counts,
        'employees_no_docs': employees_no_docs,
        'total_employees': employees.count(),
        'base_template': base_template,
    }
    return render(request, 'ems/report_documents.html', context)


@login_required
def report_assets(request):
    """Assets Report - utilization analytics, value summary, type breakdown, overdue assignments"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    try:
        from blu_assets.models import EmployeeAsset
    except ImportError:
        return render(request, 'ems/unauthorized.html', {'error': 'Assets module not available'})

    from datetime import date
    import json

    employees = _report_employees(request)
    today = date.today()

    records = EmployeeAsset.objects.filter(
        Q(employee__in=employees) | Q(employee__isnull=True)
    ).select_related('employee', 'assigned_by', 'category')

    # === Summary Stats ===
    total = records.count()
    assigned = records.filter(status='ASSIGNED').count()
    available = records.filter(status='AVAILABLE').count()
    in_repair = records.filter(status='IN_REPAIR').count()
    retired = records.filter(status='RETIRED').count()
    lost = records.filter(status='LOST').count()
    utilization_rate = round((assigned / total * 100), 1) if total > 0 else 0

    # === Total Asset Value ===
    total_value = records.aggregate(total=Sum('purchase_price'))['total'] or 0
    assigned_value = records.filter(status='ASSIGNED').aggregate(total=Sum('purchase_price'))['total'] or 0

    # === Asset Type Distribution ===
    type_dist = records.values('asset_type').annotate(count=Count('id')).order_by('-count')
    type_breakdown = []
    for t in type_dist:
        try:
            label = str(dict(EmployeeAsset.AssetType.choices).get(t['asset_type'], t['asset_type']))
        except Exception:
            label = str(t['asset_type'] or 'Unknown')
        type_breakdown.append({'name': label, 'count': t['count']})
    type_labels = json.dumps([str(t['name']) for t in type_breakdown])
    type_counts = json.dumps([t['count'] for t in type_breakdown])

    # === Status Distribution ===
    status_dist = records.values('status').annotate(count=Count('id')).order_by('status')
    status_breakdown = []
    for s in status_dist:
        try:
            label = str(dict(EmployeeAsset.Status.choices).get(s['status'], s['status']))
        except Exception:
            label = str(s['status'])
        status_breakdown.append({'name': label, 'count': s['count']})
    status_labels = json.dumps([str(s['name']) for s in status_breakdown])
    status_counts = json.dumps([s['count'] for s in status_breakdown])

    # === Overdue Assets (assigned > 60 days) ===
    overdue_assets = []
    for asset in records.filter(status='ASSIGNED', employee__isnull=False):
        if asset.assigned_date and (today - asset.assigned_date).days > 60:
            overdue_assets.append(asset)
    overdue_assets = overdue_assets[:10]

    # === Warranty Status ===
    warranty_valid = records.filter(warranty_expiry__gte=today).count()
    warranty_expired = records.filter(warranty_expiry__lt=today).count()
    no_warranty = records.filter(warranty_expiry__isnull=True).count()

    context = {
        'total': total, 'assigned': assigned, 'available': available,
        'in_repair': in_repair, 'retired': retired, 'lost': lost,
        'utilization_rate': utilization_rate,
        'total_value': total_value, 'assigned_value': assigned_value,
        'type_breakdown': type_breakdown, 'type_labels': type_labels, 'type_counts': type_counts,
        'status_breakdown': status_breakdown, 'status_labels': status_labels, 'status_counts': status_counts,
        'overdue_assets': overdue_assets,
        'warranty_valid': warranty_valid, 'warranty_expired': warranty_expired, 'no_warranty': no_warranty,
        'base_template': base_template,
    }
    return render(request, 'ems/report_assets.html', context)


@login_required
def report_payroll(request):
    """Payroll Report - salary analytics, status distribution, department costs, monthly trends"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    try:
        from blu_staff.apps.payroll.models import Payroll
    except ImportError:
        return render(request, 'ems/report_payroll.html', {'error': 'Payroll module not available', 'base_template': base_template})

    employees = _report_employees(request)
    records = Payroll.objects.filter(employee__in=employees)

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payroll_report_{date.today()}.csv"'
        import csv
        writer = csv.writer(response)
        writer.writerow(['Employee', 'Period Start', 'Period End', 'Base Pay', 'Gross Pay', 'Deductions', 'Net Pay', 'Status'])
        for r in records.select_related('employee'):
            writer.writerow([r.employee.get_full_name(), r.period_start, r.period_end, r.base_pay, r.gross_pay, r.total_deductions, r.net_pay, r.get_status_display()])
        return response

    total_records = records.count()
    total_gross = records.aggregate(s=Sum('gross_pay'))['s'] or Decimal('0')
    total_net = records.aggregate(s=Sum('net_pay'))['s'] or Decimal('0')
    total_deductions = records.aggregate(s=Sum('total_deductions'))['s'] or Decimal('0')
    avg_salary = records.aggregate(a=Avg('net_pay'))['a'] or Decimal('0')
    paid_count = records.filter(status='PAID').count()

    # Status distribution
    status_dist = records.values('status').annotate(count=Count('id')).order_by('status')
    status_labels = json.dumps([str(dict(Payroll.Status.choices).get(s['status'], s['status'])) for s in status_dist])
    status_counts = json.dumps([s['count'] for s in status_dist])

    # Department cost breakdown
    dept_cost = (
        records.filter(status__in=['APPROVED', 'PAID'])
        .exclude(employee__employee_profile__department='')
        .exclude(employee__employee_profile__department__isnull=True)
        .values('employee__employee_profile__department')
        .annotate(total=Sum('net_pay'), count=Count('id'))
        .order_by('-total')
    )
    dept_breakdown = [{'name': d['employee__employee_profile__department'], 'total': float(d['total']), 'count': d['count']} for d in dept_cost]
    dept_labels = json.dumps([d['name'] for d in dept_breakdown])
    dept_totals = json.dumps([d['total'] for d in dept_breakdown])

    # Monthly payroll trend (last 6 months)
    six_months_ago = date.today() - timedelta(days=180)
    monthly = (
        records.filter(period_end__gte=six_months_ago, status__in=['APPROVED', 'PAID'])
        .annotate(month=ExtractMonth('period_end'), year=ExtractYear('period_end'))
        .values('year', 'month')
        .annotate(total=Sum('net_pay'))
        .order_by('year', 'month')
    )
    month_labels = json.dumps([f"{calendar.month_abbr[m['month']]} {m['year']}" for m in monthly])
    month_data = json.dumps([float(m['total']) for m in monthly])

    # Top earners
    top_earners = (
        records.filter(status__in=['APPROVED', 'PAID'])
        .values('employee__first_name', 'employee__last_name', 'employee__employee_profile__department')
        .annotate(total_earned=Sum('net_pay'))
        .order_by('-total_earned')[:10]
    )

    context = {
        'total_records': total_records, 'total_gross': total_gross, 'total_net': total_net,
        'total_deductions': total_deductions, 'avg_salary': avg_salary, 'paid_count': paid_count,
        'status_labels': status_labels, 'status_counts': status_counts,
        'dept_breakdown': dept_breakdown, 'dept_labels': dept_labels, 'dept_totals': dept_totals,
        'month_labels': month_labels, 'month_data': month_data,
        'top_earners': top_earners,
        'base_template': base_template,
    }
    return render(request, 'ems/report_payroll.html', context)


@login_required
def report_expenses(request):
    """Expense Report - request analytics, status distribution, category breakdown, monthly trends"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    try:
        from blu_staff.apps.requests.models import EmployeeRequest, ReimbursementRequest
    except ImportError:
        return render(request, 'ems/report_expenses.html', {'error': 'Requests module not available', 'base_template': base_template})

    employees = _report_employees(request)
    records = EmployeeRequest.objects.filter(employee__in=employees).select_related('request_type')

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="expense_report_{date.today()}.csv"'
        import csv
        writer = csv.writer(response)
        writer.writerow(['Request #', 'Employee', 'Type', 'Title', 'Amount', 'Currency', 'Status', 'Priority', 'Date'])
        for r in records:
            writer.writerow([r.request_number, r.employee.get_full_name(), str(r.request_type), r.title, r.amount or '', r.currency, r.get_status_display(), r.get_priority_display(), r.request_date.strftime('%Y-%m-%d')])
        return response

    total = records.count()
    pending = records.filter(status='PENDING').count()
    approved = records.filter(status='APPROVED').count()
    total_amount = records.filter(amount__isnull=False).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    approved_amount = records.filter(status__in=['APPROVED', 'COMPLETED'], amount__isnull=False).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # Status distribution
    status_dist = records.values('status').annotate(count=Count('id')).order_by('status')
    status_labels = json.dumps([str(dict(EmployeeRequest.Status.choices).get(s['status'], s['status'])) for s in status_dist])
    status_counts = json.dumps([s['count'] for s in status_dist])

    # Priority distribution
    priority_dist = records.values('priority').annotate(count=Count('id')).order_by('priority')
    priority_labels = json.dumps([str(dict(EmployeeRequest.Priority.choices).get(p['priority'], p['priority'])) for p in priority_dist])
    priority_counts = json.dumps([p['count'] for p in priority_dist])

    # By request type
    type_dist = records.values('request_type__name').annotate(count=Count('id'), total=Sum('amount')).order_by('-count')
    type_breakdown = [{'name': t['request_type__name'] or 'Unknown', 'count': t['count'], 'total': float(t['total'] or 0)} for t in type_dist]
    type_labels = json.dumps([t['name'] for t in type_breakdown])
    type_counts = json.dumps([t['count'] for t in type_breakdown])

    # Monthly trend (last 6 months)
    six_months_ago = date.today() - timedelta(days=180)
    monthly = (
        records.filter(request_date__gte=six_months_ago)
        .annotate(month=ExtractMonth('request_date'), year=ExtractYear('request_date'))
        .values('year', 'month')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('year', 'month')
    )
    month_labels = json.dumps([f"{calendar.month_abbr[m['month']]} {m['year']}" for m in monthly])
    month_counts = json.dumps([m['count'] for m in monthly])

    # Top requesters
    top_requesters = (
        records.values('employee__first_name', 'employee__last_name', 'employee__employee_profile__department')
        .annotate(req_count=Count('id'), total_amount=Sum('amount'))
        .order_by('-req_count')[:10]
    )

    context = {
        'total': total, 'pending': pending, 'approved': approved,
        'total_amount': total_amount, 'approved_amount': approved_amount,
        'status_labels': status_labels, 'status_counts': status_counts,
        'priority_labels': priority_labels, 'priority_counts': priority_counts,
        'type_breakdown': type_breakdown, 'type_labels': type_labels, 'type_counts': type_counts,
        'month_labels': month_labels, 'month_counts': month_counts,
        'top_requesters': top_requesters,
        'base_template': base_template,
    }
    return render(request, 'ems/report_expenses.html', context)


@login_required
def report_training(request):
    """Training Report - program analytics, enrollment status, completion rates, department participation"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    try:
        from blu_staff.apps.training.models import TrainingProgram, TrainingEnrollment
    except ImportError:
        return render(request, 'ems/report_training.html', {'error': 'Training module not available', 'base_template': base_template})

    employees = _report_employees(request)
    tenant = getattr(request, 'tenant', None)

    programs = TrainingProgram.objects.all()
    enrollments = TrainingEnrollment.objects.filter(employee__in=employees)
    if tenant:
        programs = programs.filter(tenant=tenant)
        enrollments = enrollments.filter(tenant=tenant)

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="training_report_{date.today()}.csv"'
        import csv
        writer = csv.writer(response)
        writer.writerow(['Employee', 'Program', 'Type', 'Status', 'Enrollment Date', 'Completion Date', 'Score'])
        for e in enrollments.select_related('employee', 'program'):
            writer.writerow([e.employee.get_full_name(), e.program.title, e.program.get_program_type_display(), e.get_status_display(), e.enrollment_date, e.completion_date or '', e.score or ''])
        return response

    total_programs = programs.count()
    active_programs = programs.filter(is_active=True).count()
    total_enrollments = enrollments.count()
    completed = enrollments.filter(status='COMPLETED').count()
    in_progress = enrollments.filter(status='IN_PROGRESS').count()
    completion_rate = round(completed / total_enrollments * 100) if total_enrollments > 0 else 0
    avg_score = enrollments.filter(score__isnull=False).aggregate(a=Avg('score'))['a']

    # Enrollment status distribution
    status_dist = enrollments.values('status').annotate(count=Count('id')).order_by('status')
    status_labels = json.dumps([str(dict(TrainingEnrollment.Status.choices).get(s['status'], s['status'])) for s in status_dist])
    status_counts = json.dumps([s['count'] for s in status_dist])

    # Program type distribution
    type_dist = programs.filter(is_active=True).values('program_type').annotate(count=Count('id')).order_by('-count')
    type_labels = json.dumps([str(dict(TrainingProgram.ProgramType.choices).get(t['program_type'], t['program_type'])) for t in type_dist])
    type_counts = json.dumps([t['count'] for t in type_dist])

    # Top programs by enrollment
    top_programs = (
        enrollments.values('program__title', 'program__program_type')
        .annotate(enroll_count=Count('id'), completed_count=Count('id', filter=Q(status='COMPLETED')))
        .order_by('-enroll_count')[:10]
    )

    # Department participation
    dept_participation = (
        enrollments
        .exclude(employee__employee_profile__department='')
        .exclude(employee__employee_profile__department__isnull=True)
        .values('employee__employee_profile__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    dept_labels = json.dumps([d['employee__employee_profile__department'] for d in dept_participation])
    dept_counts = json.dumps([d['count'] for d in dept_participation])

    # Total training cost
    total_cost = programs.filter(is_active=True).aggregate(s=Sum('cost'))['s'] or Decimal('0')

    context = {
        'total_programs': total_programs, 'active_programs': active_programs,
        'total_enrollments': total_enrollments, 'completed': completed, 'in_progress': in_progress,
        'completion_rate': completion_rate, 'avg_score': avg_score, 'total_cost': total_cost,
        'status_labels': status_labels, 'status_counts': status_counts,
        'type_labels': type_labels, 'type_counts': type_counts,
        'top_programs': top_programs,
        'dept_labels': dept_labels, 'dept_counts': dept_counts,
        'base_template': base_template,
    }
    return render(request, 'ems/report_training.html', context)


@login_required
def report_contract_expiry(request):
    """Contract Expiry Report - upcoming expirations, probation endings, temporary assignments"""
    allowed, base_template = _report_permission_check(request)
    if not allowed:
        return render(request, 'ems/unauthorized.html')

    employees = _report_employees(request).select_related('employee_profile')
    today = date.today()
    thirty_days = today + timedelta(days=30)
    sixty_days = today + timedelta(days=60)
    ninety_days = today + timedelta(days=90)

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="contract_expiry_report_{date.today()}.csv"'
        import csv
        writer = csv.writer(response)
        writer.writerow(['Employee', 'Department', 'Employment Type', 'Contract End', 'Probation End', 'Temporary End', 'Status'])
        for emp in employees.filter(is_active=True):
            p = getattr(emp, 'employee_profile', None)
            if not p:
                continue
            writer.writerow([emp.get_full_name(), p.department or '', p.employment_type or '', p.contract_end_date or '', p.probation_end_date or '', p.temporary_end_date or '', 'Active' if emp.is_active else 'Inactive'])
        return response

    active_employees = employees.filter(is_active=True)
    total_active = active_employees.count()

    # Contract expirations
    contracts_expiring_30 = active_employees.filter(employee_profile__contract_end_date__gt=today, employee_profile__contract_end_date__lte=thirty_days).select_related('employee_profile')
    contracts_expiring_60 = active_employees.filter(employee_profile__contract_end_date__gt=thirty_days, employee_profile__contract_end_date__lte=sixty_days).select_related('employee_profile')
    contracts_expiring_90 = active_employees.filter(employee_profile__contract_end_date__gt=sixty_days, employee_profile__contract_end_date__lte=ninety_days).select_related('employee_profile')
    contracts_expired = active_employees.filter(employee_profile__contract_end_date__lt=today).select_related('employee_profile')

    # Probation endings
    probation_ending_30 = active_employees.filter(employee_profile__probation_end_date__gt=today, employee_profile__probation_end_date__lte=thirty_days).select_related('employee_profile')
    probation_ended = active_employees.filter(employee_profile__probation_end_date__lt=today).select_related('employee_profile')

    # Temporary assignments ending
    temp_ending_30 = active_employees.filter(employee_profile__temporary_end_date__gt=today, employee_profile__temporary_end_date__lte=thirty_days).select_related('employee_profile')

    # Employment type distribution
    type_dist = (
        active_employees
        .exclude(employee_profile__employment_type='')
        .exclude(employee_profile__employment_type__isnull=True)
        .values('employee_profile__employment_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    type_labels = json.dumps([t['employee_profile__employment_type'] for t in type_dist])
    type_counts = json.dumps([t['count'] for t in type_dist])

    # Upcoming expirations summary for chart
    expiry_labels = json.dumps(['Expired', 'Within 30 Days', '30-60 Days', '60-90 Days'])
    expiry_counts = json.dumps([contracts_expired.count(), contracts_expiring_30.count(), contracts_expiring_60.count(), contracts_expiring_90.count()])

    # Combined urgent list (all expiring within 30 days)
    urgent_list = list(contracts_expiring_30) + list(probation_ending_30) + list(temp_ending_30)

    context = {
        'total_active': total_active,
        'contracts_expiring_30': contracts_expiring_30, 'contracts_expiring_60': contracts_expiring_60,
        'contracts_expiring_90': contracts_expiring_90, 'contracts_expired': contracts_expired,
        'probation_ending_30': probation_ending_30, 'probation_ended': probation_ended,
        'temp_ending_30': temp_ending_30,
        'type_labels': type_labels, 'type_counts': type_counts,
        'expiry_labels': expiry_labels, 'expiry_counts': expiry_counts,
        'urgent_list': urgent_list,
        'base_template': base_template,
    }
    return render(request, 'ems/report_contract_expiry.html', context)


@login_required
def assets_management(request):
    """Assets management dashboard"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        from blu_assets.models import EmployeeAsset, AssetCategory
    except ImportError:
        return render(request, 'ems/unauthorized.html', {'error': 'Assets module not available'})
    
    # Get employer's company
    if request.user.role == 'ADMINISTRATOR':
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        employees = User.objects.filter(company=request.user.company, role='EMPLOYEE')
    
    # Get all assets
    all_assets = EmployeeAsset.objects.filter(
        Q(employee__in=employees) | Q(employee__isnull=True)
    ).select_related('employee', 'assigned_by', 'category').order_by('-assigned_date')
    
    # Filter by status
    status_filter = request.GET.get('status', 'ALL')
    if status_filter and status_filter != 'ALL':
        all_assets = all_assets.filter(status=status_filter)
    
    # Filter by type
    type_filter = request.GET.get('type', 'ALL')
    if type_filter and type_filter != 'ALL':
        all_assets = all_assets.filter(asset_type=type_filter)
    
    # Search
    search = request.GET.get('search', '')
    if search:
        all_assets = all_assets.filter(
            Q(asset_tag__icontains=search) |
            Q(name__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search)
        )
    
    # Statistics
    total_assets = EmployeeAsset.objects.filter(
        Q(employee__in=employees) | Q(employee__isnull=True)
    ).count()
    assigned_assets = EmployeeAsset.objects.filter(employee__in=employees, status='ASSIGNED').count()
    available_assets = EmployeeAsset.objects.filter(employee__isnull=True, status='AVAILABLE').count()
    in_repair = EmployeeAsset.objects.filter(status='IN_REPAIR').count()
    
    # Categories
    categories = AssetCategory.objects.all()
    
    context = {
        'assets': all_assets,
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'available_assets': available_assets,
        'in_repair': in_repair,
        'categories': categories,
        'asset_types': EmployeeAsset.AssetType.choices,
        'asset_statuses': EmployeeAsset.Status.choices,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search': search,
        'employees': employees
    }
    
    return render(request, 'ems/assets_management.html', context)


@login_required
def asset_create(request):
    """Create a new asset"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        from blu_assets.models import EmployeeAsset, AssetCategory
        from blu_staff.apps.accounts.models import CompanyDepartment
    except ImportError:
        return render(request, 'ems/unauthorized.html', {'error': 'Assets module not available'})
    
    if request.method == 'POST':
        try:
            # Create new asset
            asset = EmployeeAsset()
            asset.asset_tag = request.POST.get('asset_tag')
            asset.name = request.POST.get('name')
            asset.asset_type = request.POST.get('asset_type')
            asset.status = request.POST.get('status', 'AVAILABLE')
            asset.serial_number = request.POST.get('serial_number', '')
            asset.brand = request.POST.get('brand', '')
            asset.model = request.POST.get('model', '')
            asset.purchase_date = request.POST.get('purchase_date') or None
            asset.purchase_cost = request.POST.get('purchase_cost') or None
            asset.condition = request.POST.get('condition', 'NEW')
            asset.notes = request.POST.get('notes', '')
            
            # Department
            dept_id = request.POST.get('department')
            if dept_id:
                asset.department = CompanyDepartment.objects.get(id=dept_id)
            
            # Category
            category_id = request.POST.get('category')
            if category_id:
                asset.category = AssetCategory.objects.get(id=category_id)
            
            asset.save()
            messages.success(request, f'Asset "{asset.name}" created successfully!')
            return redirect('assets_management')
        except Exception as e:
            messages.error(request, f'Error creating asset: {str(e)}')
    
    # Get form data
    categories = AssetCategory.objects.all()
    departments = CompanyDepartment.objects.filter(company=request.user.company) if request.user.company else []
    
    context = {
        'categories': categories,
        'departments': departments,
        'asset_types': EmployeeAsset.AssetType.choices,
        'asset_statuses': EmployeeAsset.Status.choices,
        'asset_conditions': EmployeeAsset.Condition.choices,
    }
    
    return render(request, 'ems/asset_create.html', context)


@login_required
def approval_center(request):
    """Centralized approval center for all pending items"""
    is_supervisor = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'SUPERVISOR'
    )

    if not (_has_hr_access(request.user) or is_supervisor):
        return render(request, 'ems/unauthorized.html')
    
    from blu_staff.apps.documents.models import EmployeeDocument
    from blu_staff.apps.attendance.models import LeaveRequest
    from blu_staff.apps.payroll.models import BenefitClaim
    from datetime import date, timedelta
    
    today = date.today()
    next_30_days = today + timedelta(days=30)
    next_60_days = today + timedelta(days=60)
    
    # Get employer's company
    if request.user.role == 'ADMINISTRATOR':
        company = None
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        company = request.user.company
        if is_supervisor:
            employees = User.objects.filter(role='EMPLOYEE', employee_profile__supervisor=request.user)
        else:
            employees = User.objects.filter(company=company, role='EMPLOYEE')
    
    # Pending Documents
    pending_documents = EmployeeDocument.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).select_related('employee', 'uploaded_by').order_by('-created_at')[:20]
    
    # Pending Leave Requests
    pending_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).select_related('employee').order_by('-created_at')[:20]
    
    # Pending Benefit Claims
    pending_benefit_claims = BenefitClaim.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).select_related('employee', 'benefit').order_by('-submitted_at')[:20]
    
    # Contract Expiries (next 60 days)
    expiring_contracts = []
    for emp in employees.select_related('employee_profile'):
        try:
            profile = emp.employee_profile
            if profile.employment_type == 'CONTRACT' and profile.contract_end_date:
                if today <= profile.contract_end_date <= next_60_days:
                    days_until = (profile.contract_end_date - today).days
                    expiring_contracts.append({
                        'employee': emp,
                        'end_date': profile.contract_end_date,
                        'days_until': days_until,
                        'is_critical': days_until <= 30
                    })
        except:
            # Skip employees without profiles
            continue
    
    # Probation Endings (next 60 days)
    ending_probations = []
    for emp in employees.select_related('employee_profile'):
        try:
            profile = emp.employee_profile
            if profile.employment_type == 'PROBATION' and profile.probation_end_date:
                if today <= profile.probation_end_date <= next_60_days:
                    days_until = (profile.probation_end_date - today).days
                    ending_probations.append({
                        'employee': emp,
                        'end_date': profile.probation_end_date,
                        'days_until': days_until,
                        'is_critical': days_until <= 30
                    })
        except:
            # Skip employees without profiles
            continue
    
    # Temporary Contract Endings (next 60 days)
    ending_temporary = []
    for emp in employees.select_related('employee_profile'):
        try:
            profile = emp.employee_profile
            if profile.employment_type == 'TEMPORARY' and profile.temporary_end_date:
                if today <= profile.temporary_end_date <= next_60_days:
                    days_until = (profile.temporary_end_date - today).days
                    ending_temporary.append({
                        'employee': emp,
                        'end_date': profile.temporary_end_date,
                        'days_until': days_until,
                        'is_critical': days_until <= 30
                    })
        except:
            # Skip employees without profiles
            continue
    
    # Sort by days until expiry
    expiring_contracts.sort(key=lambda x: x['days_until'])
    ending_probations.sort(key=lambda x: x['days_until'])
    ending_temporary.sort(key=lambda x: x['days_until'])
    
    # Summary counts
    summary = {
        'pending_documents': pending_documents.count(),
        'pending_leaves': pending_leaves.count(),
        'pending_benefit_claims': pending_benefit_claims.count(),
        'expiring_contracts': len(expiring_contracts),
        'ending_probations': len(ending_probations),
        'ending_temporary': len(ending_temporary),
        'total_pending': pending_documents.count() + pending_leaves.count() + pending_benefit_claims.count() + len(expiring_contracts) + len(ending_probations) + len(ending_temporary)
    }

    tab_items = [
        {'slug': 'documents', 'label': 'Documents', 'count': summary['pending_documents']},
        {'slug': 'leaves', 'label': 'Leave Requests', 'count': summary['pending_leaves']},
        {'slug': 'benefit-claims', 'label': 'Benefit Claims', 'count': summary['pending_benefit_claims']},
        {'slug': 'contracts', 'label': 'Contracts', 'count': summary['expiring_contracts'] + summary['ending_probations'] + summary['ending_temporary']},
    ]
    
    context = {
        'pending_documents': pending_documents,
        'pending_leaves': pending_leaves,
        'pending_benefit_claims': pending_benefit_claims,
        'expiring_contracts': expiring_contracts,
        'ending_probations': ending_probations,
        'ending_temporary': ending_temporary,
        'summary': summary,
        'tab_items': tab_items,
        'today': today
    }
    context.update(_get_employer_nav_context(request.user))
    
    return render(request, 'ems/approval_center.html', context)


@login_required
def user_management(request):
    """User management dashboard for System Superadmin"""
    if not request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.accounts.models import Company, User
    from datetime import date

    today = date.today()

    # Handle user actions (create/toggle active)
    if request.method == 'POST':
        action = request.POST.get('action') or 'create'

        if action == 'toggle_active':
            user_id = request.POST.get('user_id')
            activate_flag = request.POST.get('activate') == '1'
            try:
                target_user = User.objects.get(pk=user_id)
                target_user.is_active = activate_flag
                target_user.save(update_fields=['is_active'])
                state = 'activated' if activate_flag else 'deactivated'
                messages.success(request, f"User {target_user.email} {state}.")
            except User.DoesNotExist:
                messages.error(request, 'User not found.')

            return redirect('user_management')

        if action == 'update_user':
            user_id = request.POST.get('user_id')
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            platform_role_value = request.POST.get('platform_role', '').strip() or None
            is_active_flag = request.POST.get('is_active') == '1'
            new_password = request.POST.get('password', '').strip()

            try:
                target_user = User.objects.get(pk=user_id)
                target_user.first_name = first_name
                target_user.last_name = last_name
                target_user.platform_role = platform_role_value
                target_user.is_active = is_active_flag
                update_fields = ['first_name', 'last_name', 'platform_role', 'is_active']
                if new_password:
                    target_user.set_password(new_password)
                    # set_password doesn't need update_fields; save whole object
                    target_user.save()
                    messages.success(request, f"User {target_user.email} updated. Password set.")
                else:
                    target_user.save(update_fields=update_fields)
                    messages.success(request, f"User {target_user.email} updated.")
            except User.DoesNotExist:
                messages.error(request, 'User not found.')

            return redirect('user_management')

        # Create a SUPERADMIN with optional platform_role
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        platform_role_value = request.POST.get('platform_role', '').strip() or None
        is_active_flag = request.POST.get('is_active') == '1'
        raw_password = request.POST.get('password', '').strip()

        errors = []
        if not email:
            errors.append('Email is required for a platform user.')
        elif User.objects.filter(email=email).exists():
            errors.append('A user with this email already exists.')

        if errors:
            for msg in errors:
                messages.error(request, msg)
        else:
            from django.utils.crypto import get_random_string
            temp_password = raw_password or get_random_string(12)
            user = User.objects.create_user(
                email=email,
                password=temp_password,
                first_name=first_name,
                last_name=last_name,
                role='SUPERADMIN',
                platform_role=platform_role_value,
                is_active=is_active_flag,
            )
            messages.success(request, f"Platform user {user.email} was created. Temp password: {temp_password}")

        return redirect('user_management')

    # Filters
    search_query = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()  # active / inactive
    platform_role_filter = request.GET.get('platform_role', '').strip()
    export_type = request.GET.get('export', '').strip()

    # Base queryset for platform-level users shown in this table (System Owner staff only)
    users_qs = User.objects.filter(role='SUPERADMIN').select_related('company').order_by('email')

    # Apply search over name/email/company
    if search_query:
        users_qs = users_qs.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(company__name__icontains=search_query)
        )

    # Apply role filter
    if role_filter:
        users_qs = users_qs.filter(role=role_filter)

    # Apply status filter
    if status_filter == 'active':
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        users_qs = users_qs.filter(is_active=False)

    # Apply platform role filter (for platform staff)
    if platform_role_filter:
        users_qs = users_qs.filter(platform_role=platform_role_filter)

    # CSV export of filtered admin users
    if export_type == 'admins':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="platform_admins.csv"'

        import csv

        writer = csv.writer(response)
        writer.writerow([
            'Name',
            'Email',
            'Role',
            'Company',
            'Status',
            'Last Login',
            'Date Joined',
        ])

        export_qs = users_qs.filter(role__in=['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN'])

        for user in export_qs:
            writer.writerow(
                [
                    user.get_full_name() or user.email,
                    user.email,
                    user.get_role_display(),
                    user.company.name if user.company else '',
                    'Active' if user.is_active else 'Inactive',
                    user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never',
                    user.date_joined.strftime('%Y-%m-%d'),
                ]
            )

        return response

    # Global stats by role (across the whole platform)
    super_admins = User.objects.filter(role='SUPERADMIN')
    company_admins = User.objects.filter(role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN'])
    employees = User.objects.filter(role='EMPLOYEE')

    # Get companies for context
    companies = Company.objects.all()

    # Recent user registrations (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    recent_users = User.objects.filter(date_joined__gte=thirty_days_ago).order_by('-date_joined')

    # Active vs inactive users (overall)
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()

    context = {
        'user': request.user,
        'super_admins': super_admins,
        'company_admins': company_admins,
        'employees': employees,
        'users': users_qs,
        'companies': companies,
        'recent_users': recent_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'total_users': User.objects.count(),
        'today_date': today.strftime('%Y-%m-%d'),
        # Filters
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'platform_role_filter': platform_role_filter,
        'platform_role_choices': User.PlatformRole.choices,
    }

    return render(request, 'ems/user_management.html', context)


@login_required
def documents_list(request):
    """List documents for employers/admins and employees"""
    from blu_staff.apps.documents.models import DocumentCategory, EmployeeDocument
    try:
        from blu_staff.apps.payroll.models import BenefitClaim
    except Exception:
        BenefitClaim = None
    from django.contrib.auth import get_user_model
    from ems_project.plan_features import company_has_feature, FEAT_DOCUMENT_MANAGEMENT

    User = get_user_model()
    user = request.user
    
    # Check if user is HR (employee with HR role)
    is_hr = (user.role == 'EMPLOYEE' and 
             hasattr(user, 'employee_profile') and 
             user.employee_profile.employee_role == 'HR')
    
    # Check if user wants personal view (from main menu)
    view_personal = request.GET.get('view') == 'personal'

    # Base template: keep employee layout even for HR to avoid admin sidebar
    base_template = 'ems/base_employee.html'
    
    # Filter documents based on role
    company = _get_user_company(request.user)
    if (user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']) or (is_hr and not view_personal):
        # Employers see all employee documents in their company
        employee_documents = EmployeeDocument.objects.filter(
            employee__company=company
        ).select_related('employee', 'category', 'uploaded_by').order_by('-created_at')
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            from django.db.models import Q
            employee_documents = employee_documents.filter(
                Q(title__icontains=search_query) |
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__email__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by status if provided
        status_filter = request.GET.get('status', '')
        if status_filter:
            employee_documents = employee_documents.filter(status=status_filter)
            
        # Filter by document type if provided
        type_filter = request.GET.get('type', '')
        if type_filter:
            employee_documents = employee_documents.filter(document_type=type_filter)
        
        # Filter by category
        category_filter = request.GET.get('category', '')
        if category_filter:
            employee_documents = employee_documents.filter(category_id=category_filter)
        
        # Filter by expiry status
        expiry_filter = request.GET.get('expiry', '')
        from datetime import date, timedelta
        today = date.today()
        if expiry_filter == 'expired':
            employee_documents = employee_documents.filter(expiry_date__lt=today)
        elif expiry_filter == 'expiring_soon':
            # Expiring within 30 days
            employee_documents = employee_documents.filter(
                expiry_date__gte=today,
                expiry_date__lte=today + timedelta(days=30)
            )
            
    elif user.role == 'EMPLOYEE':
        # Employees see only their own documents
        employee_documents = EmployeeDocument.objects.filter(
            employee=user
        ).select_related('category', 'uploaded_by', 'approved_by').order_by('-created_at')
        
        search_query = request.GET.get('search', '').strip()
        if search_query:
            from django.db.models import Q
            employee_documents = employee_documents.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
    else:
        employee_documents = EmployeeDocument.objects.none()
        search_query = ''
    
    # Get categories and document types for filters
    categories = DocumentCategory.objects.all()
    
    # Calculate statistics for employers/admins
    if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        all_docs = EmployeeDocument.objects.filter(employee__company=company)
        total_documents = all_docs.count()
        pending_count = all_docs.filter(status=EmployeeDocument.Status.PENDING).count()
        approved_count = all_docs.filter(status=EmployeeDocument.Status.APPROVED).count()
        rejected_count = all_docs.filter(status=EmployeeDocument.Status.REJECTED).count()
        
        # Expiry statistics
        from datetime import date, timedelta
        today = date.today()
        expired_count = all_docs.filter(expiry_date__lt=today).count()
        expiring_soon_count = all_docs.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30)
        ).count()
    else:
        total_documents = employee_documents.count()
        pending_count = employee_documents.filter(status=EmployeeDocument.Status.PENDING).count()
        approved_count = employee_documents.filter(status=EmployeeDocument.Status.APPROVED).count()
        rejected_count = employee_documents.filter(status=EmployeeDocument.Status.REJECTED).count()
        expired_count = 0
        expiring_soon_count = 0
    
    # Determine which base template to use
    if user.role == 'EMPLOYEE':
        base_template = 'ems/base_employee.html'
    else:
        base_template = 'ems/base_employer.html'
    
    # Claims visible: guard if BenefitClaim exists; employees see own
    if BenefitClaim:
        benefit_claims = BenefitClaim.objects.all()
        if request.user.role == 'EMPLOYEE':
            claims_qs = benefit_claims.filter(employee=user).select_related('benefit', 'enrollment')
        else:
            claims_qs = benefit_claims.select_related('employee', 'benefit', 'enrollment')
    else:
        claims_qs = []

    # Build docs JSON for the new OneDrive-style frontend
    import json as _json
    docs_data = []
    for doc in employee_documents:
        ep = getattr(doc.employee, 'employee_profile', None)
        dept = getattr(ep, 'department', '') or 'General'
        _is_admin_user = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
        _owns = doc.employee_id == user.id
        _can_delete = (
            (_is_admin_user) or
            (_owns and doc.status not in ['APPROVED'])
        )
        docs_data.append({
            'id': doc.id,
            'title': doc.title,
            'type': doc.document_type,
            'type_label': doc.get_document_type_display(),
            'status': doc.status,
            'status_label': doc.get_status_display(),
            'version': doc.version,
            'employee': doc.employee.get_full_name(),
            'employee_id': doc.employee_id,
            'dept': str(dept),
            'size': doc.file_size or 0,
            'date': doc.created_at.strftime('%Y-%m-%d') if doc.created_at else '',
            'filename': doc.original_filename or '',
            'file_url': doc.file.url if doc.file else '',
            'download_url': f'/documents/{doc.id}/download/' if doc.file else '',
            'is_confidential': doc.is_confidential,
            'expiry_date': doc.expiry_date.strftime('%Y-%m-%d') if doc.expiry_date else '',
            'can_delete': _can_delete,
        })
    docs_json = _json.dumps(docs_data)

    # Employees list for share modal
    from django.contrib.auth import get_user_model as _get_user_model
    _User = _get_user_model()
    if company:
        share_employees = list(_User.objects.filter(
            company=company, is_active=True
        ).values('id', 'first_name', 'last_name', 'email'))
        employees_json = _json.dumps([{
            'id': u['id'],
            'name': f"{u['first_name']} {u['last_name']}".strip(),
            'email': u['email'],
        } for u in share_employees])
    else:
        employees_json = '[]'

    # Existing shares for each document (doc_id → list of user ids)
    try:
        from blu_staff.apps.documents.models import DocumentShare as _DS
        doc_ids = [d['id'] for d in docs_data]
        share_map = {}
        for sh in _DS.objects.filter(document_id__in=doc_ids).select_related('shared_with'):
            share_map.setdefault(sh.document_id, []).append({
                'id': sh.shared_with_id,
                'name': sh.shared_with.get_full_name(),
                'email': sh.shared_with.email,
            })
        shares_json = _json.dumps(share_map)
    except Exception:
        shares_json = '{}'

    context = {
        'user': user,
        'company': company,
        'base_template': base_template,
        'employee_documents': employee_documents,
        'categories': categories,
        'document_types': EmployeeDocument.DocumentType.choices,
        'status_choices': EmployeeDocument.Status.choices,
        'status_filter': status_filter if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] else '',
        'type_filter': type_filter if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] else '',
        'category_filter': category_filter if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] else '',
        'expiry_filter': expiry_filter if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] else '',
        'search_query': search_query,
        'total_documents': total_documents,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
        'benefit_claims': claims_qs.order_by('-submitted_at')[:100],
        'docs_json': docs_json,
        'employees_json': employees_json,
        'shares_json': shares_json,
    }
    context.update(_get_employer_nav_context(request.user))

    return render(request, 'ems/documents.html', context)


@login_required
def document_share(request, document_id):
    """AJAX: add or remove a document share for a specific user"""
    import json as _json
    from django.http import JsonResponse
    from blu_staff.apps.documents.models import EmployeeDocument, DocumentShare as _DS
    from django.contrib.auth import get_user_model as _gum

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        company = _get_user_company(request.user)
        doc = EmployeeDocument.objects.get(id=document_id, employee__company=company)
    except EmployeeDocument.DoesNotExist:
        return JsonResponse({'error': 'Document not found'}, status=404)

    data = _json.loads(request.body)
    action = data.get('action')  # 'add' or 'remove'
    user_id = data.get('user_id')

    _User = _gum()
    try:
        target_user = _User.objects.get(id=user_id, company=company)
    except _User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    if action == 'add':
        _DS.objects.get_or_create(
            document=doc,
            shared_with=target_user,
            defaults={'shared_by': request.user}
        )
    elif action == 'remove':
        _DS.objects.filter(document=doc, shared_with=target_user).delete()
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)

    current_shares = list(_DS.objects.filter(document=doc).select_related('shared_with').values(
        'shared_with__id', 'shared_with__first_name', 'shared_with__last_name', 'shared_with__email'
    ))
    return JsonResponse({'ok': True, 'shares': [
        {'id': s['shared_with__id'],
         'name': f"{s['shared_with__first_name']} {s['shared_with__last_name']}".strip(),
         'email': s['shared_with__email']}
        for s in current_shares
    ]})


@login_required
def benefit_claim_submit(request):
    """Submit a benefit claim (employee)"""
    if request.method != 'POST' or request.user.role != 'EMPLOYEE':
        return redirect('benefits_list')

    from blu_staff.apps.payroll.models import Benefit, EmployeeBenefit, BenefitClaim

    benefit_id = request.POST.get('benefit_id')
    raw_amount = request.POST.get('amount') or None
    description = request.POST.get('description', '').strip()
    attachment = request.FILES.get('attachment')
    company = getattr(request.user, 'company', None)

    try:
        benefit = Benefit.objects.get(id=benefit_id)
    except Benefit.DoesNotExist:
        messages.error(request, 'Benefit not found.')
        return redirect('benefits_list')

    enrollment = EmployeeBenefit.objects.filter(employee=request.user, benefit=benefit).order_by('-enrollment_date').first()
    # Fallback: derive company from enrollment if missing
    if not company and enrollment and getattr(enrollment.employee, 'company', None):
        company = enrollment.employee.company
    derived_company = company or getattr(request.user, 'company', None)

    # Validate amount against company contribution limit
    amount = None
    if raw_amount is not None:
        try:
            amount = Decimal(str(raw_amount))
        except Exception:
            messages.error(request, 'Invalid amount. Please enter a valid number.')
            return redirect('benefits_list')

        max_allowed = benefit.company_contribution or Decimal('0.00')
        if amount > max_allowed:
            messages.error(request, f'Amount cannot exceed company contribution of {currency_symbol} {max_allowed}.')
            return redirect('benefits_list')

    try:
        claim = BenefitClaim.objects.create(
            employee=request.user,
            benefit=benefit,
            enrollment=enrollment,
            amount=amount,
            description=description,
            attachment=attachment,
            tenant=getattr(derived_company, 'tenant', None)
        )
        messages.success(request, 'Benefit claim submitted successfully.')
    except Exception as e:
        messages.error(request, f'Could not submit claim: {str(e)}')

    return redirect('benefits_list')


from decimal import Decimal

@login_required
def benefit_claim_cleanup_my_pending(request):
    """One-time cleanup: delete all pending claims for the current user"""
    from blu_staff.apps.payroll.models import BenefitClaim

    deleted, _ = BenefitClaim.objects.filter(employee=request.user, status=BenefitClaim.Status.PENDING).delete()
    messages.success(request, f'Cleaned up {deleted} pending claim(s).')
    return redirect('benefits_list')

@login_required
def benefit_claim_delete(request, claim_id):
    """Delete a pending benefit claim (employee only)"""
    from django.http import Http404
    from blu_staff.apps.payroll.models import BenefitClaim

    # Use unscoped manager to find the claim, then verify ownership and status
    claim = get_object_or_404(BenefitClaim.objects.all(), id=claim_id)
    if claim.employee != request.user:
        raise Http404("Not your claim")
    if claim.status != BenefitClaim.Status.PENDING:
        messages.error(request, 'Only pending claims can be deleted.')
        return redirect('benefits_list')

    claim.delete()
    messages.success(request, 'Claim deleted successfully.')
    return redirect('benefits_list')

@login_required
def benefit_claim_action(request, claim_id):
    """Approve or reject a benefit claim (HR/Admin)"""
    from blu_staff.apps.payroll.models import BenefitClaim
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or getattr(request.user, 'is_employer_admin', False)
    is_hr = (
        getattr(request.user, 'role', '') == 'EMPLOYEE'
        and hasattr(request.user, 'employee_profile')
        and getattr(request.user.employee_profile, 'employee_role', '') == 'HR'
    )
    if not (is_admin or is_hr):
        return render(request, 'ems/unauthorized.html')

    try:
        claim = BenefitClaim.objects.select_related('employee', 'benefit').get(id=claim_id)
    except BenefitClaim.DoesNotExist:
        messages.error(request, 'Claim not found.')
        return redirect('benefits_list')

    action = request.POST.get('action')
    hr_note = request.POST.get('hr_note', '')

    if action == 'approve':
        claim.status = BenefitClaim.Status.APPROVED
        claim.reviewed_at = timezone.now()
        claim.reviewed_by = request.user
        if hr_note:
            claim.hr_note = hr_note
        claim.save()
        messages.success(request, 'Claim approved successfully.')
    elif action == 'reject':
        claim.status = BenefitClaim.Status.REJECTED
        claim.reviewed_at = timezone.now()
        claim.reviewed_by = request.user
        claim.hr_note = hr_note or ''
        claim.save()
        messages.info(request, 'Claim rejected.')
    else:
        messages.error(request, 'Invalid action.')

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('benefits_list')


@login_required
def document_upload(request):
    """Upload document for employee"""
    from blu_staff.apps.documents.models import EmployeeDocument, DocumentCategory
    from django.core.files.storage import default_storage
    
    if request.method == 'POST':
        title = request.POST.get('title')
        document_type = request.POST.get('document_type')
        category_id = request.POST.get('category')
        description = request.POST.get('description', '')
        expiry_date = request.POST.get('expiry_date') or None
        is_confidential = request.POST.get('is_confidential') == 'on'
        file = request.FILES.get('file')
        
        # Determine employee
        if request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
            employee_id = request.POST.get('employee')
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                employee = User.objects.get(id=employee_id, role='EMPLOYEE')
            except User.DoesNotExist:
                messages.error(request, 'Employee not found.')
                return redirect('documents_list')
        else:
            employee = request.user
        
        if not file:
            messages.error(request, 'Please select a file to upload.')
            return redirect('documents_list')
        
        try:
            category = DocumentCategory.objects.get(id=category_id) if category_id else None
            
            doc = EmployeeDocument.objects.create(
                employee=employee,
                category=category,
                document_type=document_type,
                title=title,
                description=description,
                file=file,
                expiry_date=expiry_date,
                is_confidential=is_confidential,
                uploaded_by=request.user,
                status=EmployeeDocument.Status.PENDING
            )
            
            # Send notification to HR/Admin
            from notifications.utils import notify_document_upload
            tenant = getattr(request, 'tenant', None)
            notify_document_upload(doc, tenant=tenant)
            
            messages.success(request, 'Document uploaded successfully!')
        except Exception as e:
            messages.error(request, f'Error uploading document: {str(e)}')
    
    return redirect('documents_list')

@login_required
def document_download(request, document_id):
    """Download document with access logging"""
    from blu_staff.apps.documents.models import EmployeeDocument, DocumentAccessLog
    from django.http import FileResponse, Http404
    import os
    
    try:
        doc = EmployeeDocument.objects.select_related('employee').get(id=document_id)
        
        # Check permissions
        if request.user.role == 'EMPLOYEE':
            if doc.employee != request.user:
                messages.error(request, 'You do not have permission to access this document.')
                return redirect('documents_list')
        elif request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
            if doc.employee.company != company:
                messages.error(request, 'You do not have permission to access this document.')
                return redirect('documents_list')
        else:
            messages.error(request, 'You do not have permission to access this document.')
            return redirect('documents_list')
        
        # Log access
        DocumentAccessLog.objects.create(
            document=doc,
            user=request.user,
            access_type=DocumentAccessLog.AccessType.DOWNLOAD,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Return file
        if doc.file and os.path.exists(doc.file.path):
            filename = doc.original_filename or os.path.basename(doc.file.name)
            response = FileResponse(doc.file.open('rb'), as_attachment=True, filename=filename)
            return response
        else:
            messages.error(request, 'The file for this document is no longer available on the server. Please re-upload it.')
            return redirect('documents_list')
            
    except EmployeeDocument.DoesNotExist:
        messages.error(request, 'Document not found.')
        return redirect('documents_list')

@login_required
def document_approve(request, document_id):
    """Approve document"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')
    
    from blu_staff.apps.documents.models import EmployeeDocument, DocumentAccessLog
    from django.utils import timezone
    
    try:
        doc = EmployeeDocument.objects.get(id=document_id)
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        
        if doc.employee.company != company:
            messages.error(request, 'You do not have permission to approve this document.')
            return redirect('documents_list')
        
        doc.status = EmployeeDocument.Status.APPROVED
        doc.approved_by = request.user
        doc.approved_at = timezone.now()
        doc.save()
        
        # Log access
        DocumentAccessLog.objects.create(
            document=doc,
            user=request.user,
            access_type=DocumentAccessLog.AccessType.APPROVE,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Send notification to employee
        from notifications.utils import notify_document_approval
        tenant = getattr(request, 'tenant', None)
        notify_document_approval(doc, request.user, tenant=tenant)
        
        messages.success(request, 'Document approved successfully!')
    except EmployeeDocument.DoesNotExist:
        messages.error(request, 'Document not found.')
    
    return redirect('documents_list')


@login_required
def document_reject(request, document_id):
    """Reject document"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.documents.models import EmployeeDocument, DocumentAccessLog

    if request.method == 'POST':
        reason = request.POST.get('reason', '')

        try:
            doc = EmployeeDocument.objects.get(id=document_id)
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)

            if doc.employee.company != company:
                messages.error(request, 'You do not have permission to reject this document.')
                return redirect('documents_list')

            doc.status = EmployeeDocument.Status.REJECTED
            doc.rejection_reason = reason
            doc.save()

            # Log access
            DocumentAccessLog.objects.create(
                document=doc,
                user=request.user,
                access_type=DocumentAccessLog.AccessType.REJECT,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Send notification to employee
            from notifications.utils import notify_document_rejection
            tenant = getattr(request, 'tenant', None)
            notify_document_rejection(doc, request.user, reason=reason, tenant=tenant)

            messages.success(request, 'Document rejected.')
        except EmployeeDocument.DoesNotExist:
            messages.error(request, 'Document not found.')

    return redirect('documents_list')

@login_required
def document_delete(request, document_id):
    """Delete a document. Admins can delete any company doc; employees only their own pending docs."""
    from blu_staff.apps.documents.models import EmployeeDocument, DocumentAccessLog
    from django.http import JsonResponse as _JR

    try:
        doc = EmployeeDocument.objects.get(id=document_id)
    except EmployeeDocument.DoesNotExist:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return _JR({'success': False, 'error': 'Document not found.'}, status=404)
        messages.error(request, 'Document not found.')
        return redirect('documents_list')

    user = request.user
    company = getattr(user, 'company', None) or getattr(getattr(user, 'employer_profile', None), 'company', None)

    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    owns_doc = doc.employee == user
    can_delete = (is_admin and doc.employee.company == company) or \
                 (owns_doc and doc.status not in ['APPROVED'])

    if not can_delete:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return _JR({'success': False, 'error': 'Permission denied.'}, status=403)
        messages.error(request, 'You do not have permission to delete this document.')
        return redirect('documents_list')

    if request.method == 'POST':
        doc_title = doc.title
        try:
            DocumentAccessLog.objects.create(
                document=doc,
                user=user,
                access_type='DELETE',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        except Exception:
            pass
        doc.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return _JR({'success': True, 'message': f'Document "{doc_title}" deleted.'})
        messages.success(request, f'Document "{doc_title}" deleted successfully.')
        return redirect('documents_list')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return _JR({'success': False, 'error': 'POST required.'}, status=405)
    messages.error(request, 'Invalid request.')
    return redirect('documents_list')


@login_required
def bulk_approve_documents(request):
    """Bulk approve documents"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    import json
    from blu_staff.apps.documents.models import EmployeeDocument, DocumentAccessLog
    
    try:
        data = json.loads(request.body)
        doc_ids = data.get('doc_ids', [])
        
        if not doc_ids:
            return JsonResponse({'success': False, 'error': 'No documents selected'})
        
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        approved_count = 0
        
        for doc_id in doc_ids:
            try:
                doc = EmployeeDocument.objects.get(id=doc_id, employee__company=company)
                doc.status = EmployeeDocument.Status.APPROVED
                doc.approved_by = request.user
                doc.approved_at = timezone.now()
                doc.save()
                
                # Log access
                DocumentAccessLog.objects.create(
                    document=doc,
                    user=request.user,
                    access_type=DocumentAccessLog.AccessType.APPROVE,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                approved_count += 1
            except EmployeeDocument.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully approved {approved_count} document(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def bulk_download_documents(request):
    """Bulk download documents as ZIP"""
    if request.method != 'POST':
        return redirect('documents_list')
    
    from blu_staff.apps.documents.models import EmployeeDocument, DocumentAccessLog
    import zipfile
    from io import BytesIO
    from django.http import HttpResponse
    
    doc_ids = request.POST.getlist('doc_ids')
    
    if not doc_ids:
        messages.error(request, 'No documents selected')
        return redirect('documents_list')
    
    company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for doc_id in doc_ids:
            try:
                if request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
                    doc = EmployeeDocument.objects.get(id=doc_id, employee__company=company)
                else:
                    doc = EmployeeDocument.objects.get(id=doc_id, employee=request.user)
                
                # Add file to ZIP
                file_path = doc.file.path
                arc_name = f"{doc.employee.get_full_name()}_{doc.title}_{doc.id}{doc.file.name[doc.file.name.rfind('.'):]}"
                zip_file.write(file_path, arc_name)
                
                # Log access
                DocumentAccessLog.objects.create(
                    document=doc,
                    user=request.user,
                    access_type=DocumentAccessLog.AccessType.DOWNLOAD,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except (EmployeeDocument.DoesNotExist, FileNotFoundError):
                continue
    
    # Prepare response
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="documents.zip"'
    
    return response


@login_required
def employee_profile_picture_upload_redirect(request, employee_id):
    """Upload profile picture for an employee (form-based with redirect)."""
    if request.method != 'POST':
        return redirect('employer_edit_employee', employee_id=employee_id)

    employee = get_object_or_404(User, id=employee_id)

    # Permission check
    allowed_roles = {'EMPLOYER_ADMIN', 'ADMINISTRATOR'}
    requester_role = getattr(request.user, 'role', '')
    is_self_upload = request.user.id == employee.id

    if not (is_self_upload or requester_role in allowed_roles):
        messages.error(request, 'You do not have permission to update this profile picture.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    if requester_role in allowed_roles and employee.role == 'EMPLOYEE':
        requester_company = (
            getattr(request.user, 'company', None)
            or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        )
        employee_company = getattr(employee, 'company', None)
        if requester_company and employee_company and requester_company != employee_company:
            messages.error(request, 'You do not have permission to update this employee\'s profile picture.')
            return redirect('employer_edit_employee', employee_id=employee_id)

    profile_picture = request.FILES.get('profile_picture')

    if not profile_picture:
        messages.error(request, 'Please select an image file.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    # Validate file type
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    file_ext = os.path.splitext(profile_picture.name)[1].lower()
    if file_ext not in valid_extensions:
        messages.error(request, 'Invalid file type. Please upload a JPG, PNG, GIF, or WEBP image.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    # Validate file size (max 5MB)
    if profile_picture.size > 5 * 1024 * 1024:
        messages.error(request, 'File size too large. Maximum size is 5MB.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    try:
        # Delete old profile picture if exists
        if employee.profile_picture:
            old_picture_path = employee.profile_picture.path
            if os.path.exists(old_picture_path):
                os.remove(old_picture_path)

        employee.profile_picture = profile_picture
        employee.save()
        messages.success(request, 'Profile picture updated successfully!')
    except Exception as exc:
        messages.error(request, f'Error uploading profile picture: {str(exc)}')

    return redirect('employer_edit_employee', employee_id=employee_id)


@login_required
def employee_document_upload(request, employee_id):
    """Upload a document for a specific employee from the edit page."""
    if request.method != 'POST':
        return redirect('employer_edit_employee', employee_id=employee_id)

    employee = get_object_or_404(User, id=employee_id, role='EMPLOYEE')

    allowed_roles = {'EMPLOYER_ADMIN', 'ADMINISTRATOR'}
    requester_role = getattr(request.user, 'role', '')
    is_self_upload = requester_role == 'EMPLOYEE' and request.user.id == employee.id

    if not (is_self_upload or requester_role in allowed_roles):
        return render(request, 'ems/unauthorized.html')

    if requester_role in allowed_roles:
        requester_company = (
            getattr(request.user, 'company', None)
            or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        )
        employee_company = getattr(employee, 'company', None)
        if requester_company and employee_company and requester_company != employee_company:
            messages.error(request, 'You do not have permission to manage this employee\'s documents.')
            return redirect('employer_edit_employee', employee_id=employee_id)

    title = (request.POST.get('title') or '').strip()
    description = (request.POST.get('description') or '').strip()
    expiry_value = request.POST.get('expiry_date') or None
    is_confidential = request.POST.get('is_confidential') == 'on'
    category_id = request.POST.get('category_id')
    document_type_input = request.POST.get('document_type') or ''
    upload_file = request.FILES.get('file')

    if not title or not upload_file:
        messages.error(request, 'Title and file are required to upload a document.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    category = None
    if category_id:
        category = DocumentCategory.objects.filter(id=category_id).first()
        if category is None:
            messages.error(request, 'Selected category was not found.')
            return redirect('employer_edit_employee', employee_id=employee_id)

    valid_types = {value for value, _ in EmployeeDocument.DocumentType.choices}
    if document_type_input in valid_types:
        document_type = document_type_input
    elif category and category.default_document_type in valid_types and category.default_document_type:
        document_type = category.default_document_type
    else:
        document_type = EmployeeDocument.DocumentType.OTHER

    expiry_date = None
    if expiry_value:
        try:
            expiry_date = datetime.strptime(expiry_value, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid expiry date format. Use YYYY-MM-DD.')
            return redirect('employer_edit_employee', employee_id=employee_id)

    next_version = (
        EmployeeDocument.objects.filter(employee=employee, title=title)
        .aggregate(max_version=Max('version'))
        .get('max_version')
        or 0
    ) + 1

    try:
        document = EmployeeDocument.objects.create(
            employee=employee,
            category=category,
            document_type=document_type,
            title=title,
            description=description,
            file=upload_file,
            expiry_date=expiry_date,
            is_confidential=is_confidential,
            uploaded_by=request.user,
            status=EmployeeDocument.Status.PENDING,
            version=next_version,
        )

        DocumentAccessLog.objects.create(
            document=document,
            user=request.user,
            access_type=DocumentAccessLog.AccessType.UPLOAD,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        messages.success(request, 'Document uploaded successfully and is pending review.')
    except Exception as exc:
        messages.error(request, f'Error uploading document: {str(exc)}')

    return redirect('employer_edit_employee', employee_id=employee_id)


@login_required
def performance_reviews_list(request):
    """List performance reviews for employers and employees"""
    from blu_staff.apps.performance.models import PerformanceReview
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Count
    from datetime import date
    import csv
    from django.http import HttpResponse
    
    User = get_user_model()
    user = request.user
    
    is_hr_employee = (
        hasattr(user, 'employee_profile') and user.employee_profile
        and user.employee_profile.employee_role == 'HR'
    )
    
    # Determine company
    company = None
    if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] or is_hr_employee:
        company = _get_user_company(user)
        
        # Get all reviews for statistics
        all_reviews = PerformanceReview.objects.filter(employee__company=company)
        
        # Calculate statistics
        total_reviews = all_reviews.count()
        draft_count = all_reviews.filter(status='DRAFT').count()
        completed_count = all_reviews.filter(status='COMPLETED').count()
        approved_count = all_reviews.filter(status='APPROVED').count()
        
        # Management sees all reviews in their company
        reviews = all_reviews.select_related('employee', 'employee__employee_profile', 'reviewer').order_by('-review_date')
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            reviews = reviews.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(title__icontains=search_query) |
                Q(employee__email__icontains=search_query)
            )
        
        # Filter by status
        status_filter = request.GET.get('status', '')
        if status_filter:
            reviews = reviews.filter(status=status_filter)
        
        # Filter by review type
        review_type_filter = request.GET.get('review_type', '')
        if review_type_filter:
            reviews = reviews.filter(review_type=review_type_filter)
        
        # Filter by rating
        rating_filter = request.GET.get('rating', '')
        if rating_filter:
            reviews = reviews.filter(overall_rating=rating_filter)
        
        # Date range filter
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        if date_from:
            reviews = reviews.filter(review_date__gte=date_from)
        if date_to:
            reviews = reviews.filter(review_date__lte=date_to)
        
        # Get employees for create review
        employees = User.objects.filter(company=company, role='EMPLOYEE').select_related('employee_profile').order_by('first_name', 'last_name')
        
        # CSV Export
        if request.GET.get('format') == 'csv':
            filename = f"performance_reviews_{date.today().strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(response)
            
            writer.writerow(['Employee', 'Position', 'Review Type', 'Period Start', 'Period End', 'Review Date', 'Rating', 'Status', 'Reviewer'])
            
            for review in reviews:
                writer.writerow([
                    review.employee.get_full_name(),
                    review.employee.employee_profile.job_title if hasattr(review.employee, 'employee_profile') and review.employee.employee_profile else 'N/A',
                    review.get_review_type_display(),
                    review.review_period_start.strftime('%Y-%m-%d'),
                    review.review_period_end.strftime('%Y-%m-%d'),
                    review.review_date.strftime('%Y-%m-%d'),
                    review.get_overall_rating_display(),
                    review.get_status_display(),
                    review.reviewer.get_full_name() if review.reviewer else 'N/A'
                ])
            
            return response
            
    elif user.role == 'EMPLOYEE':
        # Employees see only their own reviews
        reviews = PerformanceReview.objects.filter(
            employee=user
        ).select_related('reviewer').order_by('-review_date')
        status_filter = ''
        search_query = ''
        review_type_filter = ''
        rating_filter = ''
        date_from = ''
        date_to = ''
        total_reviews = reviews.count()
        draft_count = reviews.filter(status='DRAFT').count()
        completed_count = reviews.filter(status='COMPLETED').count()
        approved_count = reviews.filter(status='APPROVED').count()
        employees = User.objects.none()
    else:
        reviews = PerformanceReview.objects.none()
        status_filter = ''
        search_query = ''
        review_type_filter = ''
        rating_filter = ''
        date_from = ''
        date_to = ''
        total_reviews = 0
        draft_count = 0
        completed_count = 0
        approved_count = 0
        employees = User.objects.none()
    
    context = {
        'user': user,
        'company': company,
        'reviews': reviews,
        'status_filter': status_filter,
        'review_types': PerformanceReview.ReviewType.choices,
        'overall_ratings': PerformanceReview.OverallRating.choices,
        'status_choices': [
            ('DRAFT', 'Draft'),
            ('SUBMITTED', 'Submitted'),
            ('UNDER_REVIEW', 'Under Review'),
            ('COMPLETED', 'Completed'),
            ('APPROVED', 'Approved')
        ],
        'search_query': search_query,
        'review_type_filter': review_type_filter,
        'rating_filter': rating_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_reviews': total_reviews,
        'draft_count': draft_count,
        'completed_count': completed_count,
        'approved_count': approved_count,
        'employees': employees,
    }
    
    # Use different templates for employees vs managers/HR
    if user.role == 'EMPLOYEE' and not is_hr_employee:
        return render(request, 'ems/employee_performance_reviews.html', context)
    else:
        context['is_hr_employee'] = is_hr_employee
        if not is_hr_employee:
            context.update(_get_employer_nav_context(request.user))
        return render(request, 'ems/performance_reviews.html', context)

@login_required
def performance_review_create(request):
    """Create new performance review"""
    if not _has_hr_access(request.user):
        return render(request, 'ems/unauthorized.html')
    
    from blu_staff.apps.performance.models import PerformanceReview
    from django.contrib.auth import get_user_model
    from datetime import datetime
    
    User = get_user_model()
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        review_type = request.POST.get('review_type')
        title = request.POST.get('title')
        review_period_start = request.POST.get('review_period_start')
        review_period_end = request.POST.get('review_period_end')
        review_date = request.POST.get('review_date')
        
        try:
            employee = User.objects.get(id=employee_id, role='EMPLOYEE')
            
            review = PerformanceReview.objects.create(
                employee=employee,
                reviewer=request.user,
                review_type=review_type,
                title=title,
                review_period_start=datetime.strptime(review_period_start, '%Y-%m-%d').date(),
                review_period_end=datetime.strptime(review_period_end, '%Y-%m-%d').date(),
                review_date=datetime.strptime(review_date, '%Y-%m-%d').date(),
                status='DRAFT'
            )
            messages.success(request, 'Performance review created successfully!')
            return redirect('performance_review_detail', review_id=review.id)
        except Exception as e:
            messages.error(request, f'Error creating review: {str(e)}')
    
    return redirect('performance_reviews_list')

@login_required
def performance_review_detail(request, review_id):
    """View and edit performance review"""
    from blu_staff.apps.performance.models import PerformanceReview, PerformanceGoal, PerformanceMetric, PerformanceFeedback
    from django.utils import timezone
    
    is_hr = _has_hr_access(request.user)
    is_employee_self = (
        request.user.role == 'EMPLOYEE'
        and not (hasattr(request.user, 'employee_profile') and request.user.employee_profile
                 and request.user.employee_profile.employee_role == 'HR')
    )
    
    try:
        if is_employee_self:
            review = PerformanceReview.objects.select_related(
                'employee', 'reviewer', 'employee__employee_profile'
            ).prefetch_related('goals', 'metrics', 'feedback').get(
                id=review_id, employee=request.user
            )
        elif is_hr:
            company = _get_user_company(request.user)
            review = PerformanceReview.objects.select_related(
                'employee', 'reviewer', 'employee__employee_profile'
            ).prefetch_related('goals', 'metrics', 'feedback').get(
                id=review_id, employee__company=company
            )
        else:
            return render(request, 'ems/unauthorized.html')
        
        if request.method == 'POST':
            action = request.POST.get('action', 'update_review')
            
            if action == 'update_review' and is_hr:
                review.overall_rating = request.POST.get('overall_rating', review.overall_rating)
                review.reviewer_comments = request.POST.get('reviewer_comments', '')
                review.strengths = request.POST.get('strengths', '')
                review.areas_for_improvement = request.POST.get('areas_for_improvement', '')
                review.achievements = request.POST.get('achievements', '')
                review.development_plan = request.POST.get('development_plan', '')
                review.goals_next_period = request.POST.get('goals_next_period', '')
                review.recommended_actions = request.POST.get('recommended_actions', '')
                new_status = request.POST.get('status', review.status)
                if new_status != review.status:
                    review.status = new_status
                    if new_status == 'COMPLETED':
                        review.reviewer_completed_at = timezone.now()
                review.save()
                messages.success(request, 'Review assessment saved.')
                
            elif action == 'self_assess' and is_employee_self:
                review.employee_comments = request.POST.get('employee_comments', '')
                review.achievements = request.POST.get('achievements', '')
                review.challenges_faced = request.POST.get('challenges_faced', '')
                review.training_needs = request.POST.get('training_needs', '')
                review.goals_next_period = request.POST.get('goals_next_period', '')
                review.self_rating = request.POST.get('self_rating') or None
                if review.status == 'DRAFT':
                    review.status = 'SUBMITTED'
                    review.employee_submitted_at = timezone.now()
                review.save()
                messages.success(request, 'Self-assessment submitted successfully.')
                
            elif action == 'add_goal' and is_hr:
                PerformanceGoal.objects.create(
                    review=review,
                    title=request.POST.get('goal_title', ''),
                    description=request.POST.get('goal_description', ''),
                    category=request.POST.get('goal_category', ''),
                    priority=request.POST.get('goal_priority', 'MEDIUM'),
                    status=request.POST.get('goal_status', 'NOT_STARTED'),
                    progress_percentage=int(request.POST.get('goal_progress', 0) or 0),
                    target_completion_date=request.POST.get('goal_due_date') or None,
                    success_criteria=request.POST.get('goal_success_criteria', ''),
                )
                messages.success(request, 'Goal added.')
                
            elif action == 'update_goal' and is_hr:
                goal_id = request.POST.get('goal_id')
                try:
                    goal = PerformanceGoal.objects.get(id=goal_id, review=review)
                    goal.status = request.POST.get('goal_status', goal.status)
                    goal.progress_percentage = int(request.POST.get('goal_progress', goal.progress_percentage) or goal.progress_percentage)
                    goal.save()
                    messages.success(request, 'Goal updated.')
                except PerformanceGoal.DoesNotExist:
                    messages.error(request, 'Goal not found.')
                    
            elif action == 'add_metric' and is_hr:
                PerformanceMetric.objects.create(
                    review=review,
                    name=request.POST.get('metric_name', ''),
                    description=request.POST.get('metric_description', ''),
                    metric_type=request.POST.get('metric_type', 'NUMERIC'),
                    target_value=request.POST.get('metric_target', 0),
                    actual_value=request.POST.get('metric_actual') or None,
                    unit=request.POST.get('metric_unit', ''),
                    weight=int(request.POST.get('metric_weight', 100) or 100),
                    is_achieved=request.POST.get('metric_achieved') == '1',
                )
                messages.success(request, 'Metric added.')
                
            elif action == 'add_feedback':
                company_users = []
                try:
                    company = _get_user_company(request.user)
                    from django.contrib.auth import get_user_model
                    U = get_user_model()
                    company_users = list(U.objects.filter(company=company, is_active=True).values_list('id', flat=True))
                except Exception:
                    pass
                PerformanceFeedback.objects.create(
                    review=review,
                    feedback_type=request.POST.get('feedback_type', 'PEER'),
                    provided_by=request.user,
                    relationship_to_employee=request.POST.get('relationship', ''),
                    rating=int(request.POST.get('feedback_rating', 3) or 3),
                    strengths=request.POST.get('feedback_strengths', ''),
                    areas_for_improvement=request.POST.get('feedback_improvement', ''),
                    overall_comments=request.POST.get('feedback_comments', ''),
                    suggestions=request.POST.get('feedback_suggestions', ''),
                    is_anonymous=request.POST.get('is_anonymous') == '1',
                )
                messages.success(request, 'Feedback submitted.')
                
            elif action == 'advance_status' and is_hr:
                transitions = {
                    'DRAFT': 'UNDER_REVIEW',
                    'SUBMITTED': 'UNDER_REVIEW',
                    'UNDER_REVIEW': 'COMPLETED',
                    'COMPLETED': 'APPROVED',
                }
                new_status = transitions.get(review.status, review.status)
                review.status = new_status
                if new_status in ['COMPLETED', 'APPROVED']:
                    review.reviewer_completed_at = timezone.now()
                review.save()
                messages.success(request, f'Review status advanced to {review.get_status_display()}.')
                
            return redirect('performance_review_detail', review_id=review.id)
        
        context = {
            'review': review,
            'overall_ratings': PerformanceReview.OverallRating.choices,
            'goal_priorities': PerformanceGoal.Priority.choices,
            'goal_statuses': PerformanceGoal.Status.choices,
            'metric_types': PerformanceMetric.MetricType.choices,
            'feedback_types': PerformanceFeedback.FeedbackType.choices,
            'is_hr': is_hr,
            'is_employee_self': is_employee_self,
            'can_self_assess': is_employee_self and review.status in ['DRAFT', 'SUBMITTED'],
        }
        return render(request, 'ems/performance_review_detail.html', context)
        
    except PerformanceReview.DoesNotExist:
        messages.error(request, 'Review not found.')
        return redirect('performance_reviews_list')

@login_required
def performance_review_cycles(request):
    """Manage performance review cycles - HR/Admin only"""
    if not _has_hr_access(request.user):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.performance.models import PerformanceReviewCycle, ReviewCycleAssignment, PerformanceReview
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    User = get_user_model()
    company = _get_user_company(request.user)
    is_hr_employee = (
        hasattr(request.user, 'employee_profile') and request.user.employee_profile
        and request.user.employee_profile.employee_role == 'HR'
    )

    if request.method == 'POST':
        action = request.POST.get('action', 'create_cycle')

        if action == 'create_cycle':
            try:
                cycle = PerformanceReviewCycle.objects.create(
                    name=request.POST.get('cycle_name', ''),
                    description=request.POST.get('cycle_description', ''),
                    review_type=request.POST.get('review_type', 'QUARTERLY'),
                    start_date=request.POST.get('start_date'),
                    end_date=request.POST.get('end_date'),
                    review_period_start=request.POST.get('review_period_start'),
                    review_period_end=request.POST.get('review_period_end'),
                    deadline=request.POST.get('deadline'),
                    status='DRAFT',
                    auto_assign_reviewers=request.POST.get('auto_assign') == '1',
                    send_reminders=request.POST.get('send_reminders') == '1',
                    reminder_days_before=int(request.POST.get('reminder_days', 7) or 7),
                    created_by=request.user,
                )
                messages.success(request, f'Review cycle "{cycle.name}" created successfully.')
            except Exception as e:
                messages.error(request, f'Error creating cycle: {str(e)}')

        elif action == 'activate_cycle':
            cycle_id = request.POST.get('cycle_id')
            try:
                cycle = PerformanceReviewCycle.objects.get(id=cycle_id)
                cycle.status = 'ACTIVE'
                cycle.save()
                messages.success(request, f'Cycle "{cycle.name}" activated.')
            except PerformanceReviewCycle.DoesNotExist:
                messages.error(request, 'Cycle not found.')

        elif action == 'assign_employees':
            cycle_id = request.POST.get('cycle_id')
            employee_ids = request.POST.getlist('employee_ids')
            try:
                cycle = PerformanceReviewCycle.objects.get(id=cycle_id)
                created_count = 0
                for emp_id in employee_ids:
                    emp = User.objects.filter(id=emp_id, company=company, role='EMPLOYEE').first()
                    if emp and not ReviewCycleAssignment.objects.filter(cycle=cycle, employee=emp).exists():
                        ReviewCycleAssignment.objects.create(cycle=cycle, employee=emp)
                        created_count += 1
                messages.success(request, f'{created_count} employee(s) assigned to cycle.')
            except PerformanceReviewCycle.DoesNotExist:
                messages.error(request, 'Cycle not found.')

        elif action == 'launch_reviews':
            cycle_id = request.POST.get('cycle_id')
            try:
                cycle = PerformanceReviewCycle.objects.get(id=cycle_id)
                launched = 0
                for assignment in cycle.assignments.filter(review__isnull=True, status='PENDING'):
                    review = PerformanceReview.objects.create(
                        employee=assignment.employee,
                        reviewer=assignment.reviewer or request.user,
                        review_type=cycle.review_type,
                        review_period_start=cycle.review_period_start,
                        review_period_end=cycle.review_period_end,
                        review_date=timezone.now().date(),
                        title=f'{cycle.name} – {assignment.employee.get_full_name()}',
                        status='DRAFT',
                        cycle=cycle,
                    )
                    assignment.review = review
                    assignment.status = 'IN_PROGRESS'
                    assignment.save()
                    launched += 1
                cycle.status = 'IN_PROGRESS'
                cycle.save()
                messages.success(request, f'{launched} review(s) launched for cycle "{cycle.name}".')
            except PerformanceReviewCycle.DoesNotExist:
                messages.error(request, 'Cycle not found.')

        return redirect('performance_review_cycles')

    cycles = PerformanceReviewCycle.objects.prefetch_related('assignments').order_by('-start_date')
    employees = User.objects.filter(company=company, role='EMPLOYEE').select_related('employee_profile').order_by('first_name', 'last_name')
    review_types = PerformanceReview.ReviewType.choices

    context = {
        'cycles': cycles,
        'employees': employees,
        'review_types': review_types,
        'is_hr_employee': is_hr_employee,
    }
    if not is_hr_employee:
        context.update(_get_employer_nav_context(request.user))
    return render(request, 'ems/performance_review_cycles.html', context)


@login_required
def pms_goals(request):
    """Goals Management - standalone goals dashboard"""
    from blu_staff.apps.performance.models import PerformanceGoal, PerformanceReview
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = request.user
    is_hr = _has_hr_access(user)
    company = _get_user_company(user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_goal':
            goal_id = request.POST.get('goal_id')
            try:
                if is_hr:
                    goal = PerformanceGoal.objects.get(id=goal_id, review__employee__company=company)
                else:
                    goal = PerformanceGoal.objects.get(id=goal_id, review__employee=user)
                goal.status = request.POST.get('status', goal.status)
                goal.progress_percentage = int(request.POST.get('progress_percentage', goal.progress_percentage) or 0)
                goal.challenges = request.POST.get('challenges', goal.challenges)
                goal.save()
                messages.success(request, 'Goal updated successfully.')
            except PerformanceGoal.DoesNotExist:
                messages.error(request, 'Goal not found.')
        elif action == 'add_goal':
            review_id = request.POST.get('review_id')
            title = request.POST.get('title', '').strip()
            if title and review_id:
                try:
                    review = PerformanceReview.objects.get(id=review_id)
                    PerformanceGoal.objects.create(
                        review=review,
                        title=title,
                        description=request.POST.get('description', ''),
                        category=request.POST.get('category', ''),
                        priority=request.POST.get('priority', 'MEDIUM'),
                        target_completion_date=request.POST.get('target_completion_date') or None,
                        success_criteria=request.POST.get('success_criteria', ''),
                        status='NOT_STARTED',
                    )
                    messages.success(request, f'Goal "{title}" added.')
                except PerformanceReview.DoesNotExist:
                    messages.error(request, 'Review not found.')
        return redirect('pms_goals')

    if is_hr:
        goals_qs = PerformanceGoal.objects.filter(
            review__employee__company=company
        ).select_related('review', 'review__employee', 'review__employee__employee_profile')
        reviews_qs = PerformanceReview.objects.filter(
            employee__company=company
        ).select_related('employee').order_by('-review_date')[:50]
    else:
        goals_qs = PerformanceGoal.objects.filter(
            review__employee=user
        ).select_related('review')
        reviews_qs = PerformanceReview.objects.filter(employee=user).order_by('-review_date')[:20]

    total = goals_qs.count()
    completed = goals_qs.filter(status='COMPLETED').count()
    in_progress = goals_qs.filter(status='IN_PROGRESS').count()
    not_started = goals_qs.filter(status='NOT_STARTED').count()

    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    if status_filter:
        goals_qs = goals_qs.filter(status=status_filter)
    if priority_filter:
        goals_qs = goals_qs.filter(priority=priority_filter)
    goals_qs = goals_qs.order_by('-created_at')

    context = {
        'goals': goals_qs,
        'reviews': reviews_qs,
        'total': total,
        'completed': completed,
        'in_progress': in_progress,
        'not_started': not_started,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'status_choices': PerformanceGoal.Status.choices,
        'priority_choices': PerformanceGoal.Priority.choices,
        'is_hr': is_hr,
    }
    context.update(_get_employer_nav_context(user) if is_hr else {})
    return render(request, 'ems/pms_goals.html', context)


@login_required
def pms_metrics(request):
    """Metrics / KPI Dashboard"""
    from blu_staff.apps.performance.models import PerformanceMetric, PerformanceReview
    from django.db.models import Avg, Count, Sum
    user = request.user
    is_hr = _has_hr_access(user)
    company = _get_user_company(user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_metric':
            metric_id = request.POST.get('metric_id')
            try:
                if is_hr:
                    metric = PerformanceMetric.objects.get(id=metric_id, review__employee__company=company)
                else:
                    metric = PerformanceMetric.objects.get(id=metric_id, review__employee=user)
                actual = request.POST.get('actual_value', '')
                if actual != '':
                    from decimal import Decimal
                    metric.actual_value = Decimal(actual)
                    metric.is_achieved = metric.actual_value >= metric.target_value
                metric.save()
                messages.success(request, 'Metric updated.')
            except PerformanceMetric.DoesNotExist:
                messages.error(request, 'Metric not found.')
        elif action == 'add_metric':
            review_id = request.POST.get('review_id')
            name = request.POST.get('name', '').strip()
            if name and review_id:
                try:
                    from decimal import Decimal
                    review = PerformanceReview.objects.get(id=review_id)
                    PerformanceMetric.objects.create(
                        review=review,
                        name=name,
                        description=request.POST.get('description', ''),
                        metric_type=request.POST.get('metric_type', 'NUMERIC'),
                        target_value=Decimal(request.POST.get('target_value', '0') or '0'),
                        unit=request.POST.get('unit', ''),
                        weight=int(request.POST.get('weight', 100) or 100),
                    )
                    messages.success(request, f'Metric "{name}" added.')
                except PerformanceReview.DoesNotExist:
                    messages.error(request, 'Review not found.')
        return redirect('pms_metrics')

    if is_hr:
        metrics_qs = PerformanceMetric.objects.filter(
            review__employee__company=company
        ).select_related('review', 'review__employee', 'review__employee__employee_profile')
        reviews_qs = PerformanceReview.objects.filter(
            employee__company=company
        ).select_related('employee').order_by('-review_date')[:50]
    else:
        metrics_qs = PerformanceMetric.objects.filter(
            review__employee=user
        ).select_related('review')
        reviews_qs = PerformanceReview.objects.filter(employee=user).order_by('-review_date')[:20]

    total = metrics_qs.count()
    achieved = metrics_qs.filter(is_achieved=True).count()
    not_achieved = total - achieved
    avg_achievement = 0
    if total > 0:
        from decimal import Decimal
        achieved_list = [m.achievement_percentage for m in metrics_qs if m.actual_value is not None]
        avg_achievement = int(sum(achieved_list) / len(achieved_list)) if achieved_list else 0

    type_filter = request.GET.get('metric_type', '')
    if type_filter:
        metrics_qs = metrics_qs.filter(metric_type=type_filter)
    metrics_qs = metrics_qs.order_by('-created_at')

    context = {
        'metrics': metrics_qs,
        'reviews': reviews_qs,
        'total': total,
        'achieved': achieved,
        'not_achieved': not_achieved,
        'avg_achievement': avg_achievement,
        'type_filter': type_filter,
        'metric_types': PerformanceMetric.MetricType.choices,
        'is_hr': is_hr,
    }
    context.update(_get_employer_nav_context(user) if is_hr else {})
    return render(request, 'ems/pms_metrics.html', context)


@login_required
def pms_feedback_360(request):
    """360° Feedback Management"""
    from blu_staff.apps.performance.models import PerformanceFeedback, PerformanceReview
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = request.user
    is_hr = _has_hr_access(user)
    company = _get_user_company(user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'submit_feedback':
            review_id = request.POST.get('review_id')
            rating = request.POST.get('rating', '3')
            try:
                if is_hr:
                    review = PerformanceReview.objects.get(id=review_id, employee__company=company)
                else:
                    review = PerformanceReview.objects.get(id=review_id)
                PerformanceFeedback.objects.create(
                    review=review,
                    feedback_type=request.POST.get('feedback_type', 'PEER'),
                    provided_by=user,
                    relationship_to_employee=request.POST.get('relationship', ''),
                    rating=int(rating),
                    strengths=request.POST.get('strengths', ''),
                    areas_for_improvement=request.POST.get('areas_for_improvement', ''),
                    overall_comments=request.POST.get('overall_comments', ''),
                    suggestions=request.POST.get('suggestions', ''),
                    is_anonymous=request.POST.get('is_anonymous') == '1',
                )
                messages.success(request, 'Feedback submitted successfully.')
            except PerformanceReview.DoesNotExist:
                messages.error(request, 'Review not found.')
        elif action == 'delete_feedback':
            feedback_id = request.POST.get('feedback_id')
            if is_hr:
                PerformanceFeedback.objects.filter(id=feedback_id, review__employee__company=company).delete()
                messages.success(request, 'Feedback deleted.')
        return redirect('pms_feedback_360')

    if is_hr:
        feedback_qs = PerformanceFeedback.objects.filter(
            review__employee__company=company
        ).select_related('review', 'review__employee', 'provided_by')
        reviews_qs = PerformanceReview.objects.filter(
            employee__company=company
        ).select_related('employee').order_by('-review_date')[:50]
    else:
        feedback_qs = PerformanceFeedback.objects.filter(
            review__employee=user
        ).select_related('review', 'provided_by')
        reviews_qs = PerformanceReview.objects.filter(employee=user).order_by('-review_date')[:20]

    total = feedback_qs.count()
    peer_count = feedback_qs.filter(feedback_type='PEER').count()
    manager_count = feedback_qs.filter(feedback_type='MANAGER').count()
    self_count = feedback_qs.filter(feedback_type='SELF').count()
    subordinate_count = feedback_qs.filter(feedback_type='SUBORDINATE').count()

    type_filter = request.GET.get('feedback_type', '')
    if type_filter:
        feedback_qs = feedback_qs.filter(feedback_type=type_filter)
    feedback_qs = feedback_qs.order_by('-created_at')

    context = {
        'feedback_list': feedback_qs,
        'reviews': reviews_qs,
        'total': total,
        'peer_count': peer_count,
        'manager_count': manager_count,
        'self_count': self_count,
        'subordinate_count': subordinate_count,
        'type_filter': type_filter,
        'feedback_types': PerformanceFeedback.FeedbackType.choices,
        'is_hr': is_hr,
    }
    context.update(_get_employer_nav_context(user) if is_hr else {})
    return render(request, 'ems/pms_feedback_360.html', context)


@login_required
def pms_self_assessment(request):
    """Employee Self-Assessment Workflow"""
    from blu_staff.apps.performance.models import PerformanceReview, PerformanceGoal, CompetencyRating
    from django.utils import timezone
    user = request.user
    is_hr = _has_hr_access(user)
    company = _get_user_company(user)

    if request.method == 'POST':
        action = request.POST.get('action')
        review_id = request.POST.get('review_id')
        try:
            review = PerformanceReview.objects.get(id=review_id, employee=request.user)
            if action == 'save_draft':
                review.employee_comments = request.POST.get('employee_comments', review.employee_comments)
                review.self_rating = request.POST.get('self_rating', review.self_rating) or None
                review.achievements = request.POST.get('achievements', review.achievements)
                review.challenges_faced = request.POST.get('challenges_faced', review.challenges_faced)
                review.goals_next_period = request.POST.get('goals_next_period', review.goals_next_period)
                review.training_needs = request.POST.get('training_needs', review.training_needs)
                review.save()
                messages.success(request, 'Self-assessment saved as draft.')
            elif action == 'submit':
                if not request.POST.get('employee_comments', '').strip():
                    messages.error(request, 'Please provide your comments before submitting.')
                    return redirect('pms_self_assessment')
                review.employee_comments = request.POST.get('employee_comments', '')
                review.self_rating = request.POST.get('self_rating', '') or None
                review.achievements = request.POST.get('achievements', '')
                review.challenges_faced = request.POST.get('challenges_faced', '')
                review.goals_next_period = request.POST.get('goals_next_period', '')
                review.training_needs = request.POST.get('training_needs', '')
                review.status = 'SUBMITTED'
                review.employee_submitted_at = timezone.now()
                review.save()
                messages.success(request, 'Self-assessment submitted successfully.')
        except PerformanceReview.DoesNotExist:
            messages.error(request, 'Review not found or access denied.')
        return redirect('pms_self_assessment')

    pending_reviews = PerformanceReview.objects.filter(
        employee=user, status__in=['DRAFT', 'UNDER_REVIEW']
    ).prefetch_related('goals', 'metrics', 'competency_ratings__competency').order_by('-review_date')

    submitted_reviews = PerformanceReview.objects.filter(
        employee=user, status__in=['SUBMITTED', 'COMPLETED', 'APPROVED']
    ).order_by('-review_date')

    selected_review = None
    review_id = request.GET.get('review')
    if review_id:
        try:
            selected_review = pending_reviews.get(id=review_id)
        except PerformanceReview.DoesNotExist:
            pass
    if not selected_review and pending_reviews.exists():
        selected_review = pending_reviews.first()

    context = {
        'pending_reviews': pending_reviews,
        'submitted_reviews': submitted_reviews,
        'selected_review': selected_review,
        'rating_choices': PerformanceReview.OverallRating.choices,
        'is_hr': is_hr,
    }
    return render(request, 'ems/pms_self_assessment.html', context)


@login_required
def pms_competencies(request):
    """Competency Framework Management - HR/Admin only"""
    from blu_staff.apps.performance.models import CompetencyFramework, Competency
    user = request.user
    is_hr = _has_hr_access(user)
    if not is_hr:
        return render(request, 'ems/unauthorized.html')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_framework':
            name = request.POST.get('name', '').strip()
            if name:
                fw = CompetencyFramework.objects.create(
                    name=name,
                    description=request.POST.get('description', ''),
                    is_default=request.POST.get('is_default') == '1',
                    is_active=True,
                    created_by=user,
                )
                if fw.is_default:
                    CompetencyFramework.objects.exclude(id=fw.id).update(is_default=False)
                messages.success(request, f'Framework "{name}" created.')
        elif action == 'add_competency':
            framework_id = request.POST.get('framework_id')
            name = request.POST.get('name', '').strip()
            if framework_id and name:
                try:
                    fw = CompetencyFramework.objects.get(id=framework_id)
                    Competency.objects.create(
                        framework=fw,
                        name=name,
                        description=request.POST.get('description', ''),
                        competency_type=request.POST.get('competency_type', 'BEHAVIORAL'),
                        weight=int(request.POST.get('weight', 100) or 100),
                        is_required=request.POST.get('is_required') == '1',
                        level_1_description=request.POST.get('level_1', ''),
                        level_2_description=request.POST.get('level_2', ''),
                        level_3_description=request.POST.get('level_3', ''),
                        level_4_description=request.POST.get('level_4', ''),
                        level_5_description=request.POST.get('level_5', ''),
                    )
                    messages.success(request, f'Competency "{name}" added.')
                except CompetencyFramework.DoesNotExist:
                    messages.error(request, 'Framework not found.')
        elif action == 'delete_competency':
            comp_id = request.POST.get('competency_id')
            Competency.objects.filter(id=comp_id, framework__created_by__company=_get_user_company(user)).delete()
            messages.success(request, 'Competency deleted.')
        elif action == 'toggle_framework':
            fw_id = request.POST.get('framework_id')
            try:
                fw = CompetencyFramework.objects.get(id=fw_id)
                fw.is_active = not fw.is_active
                fw.save()
                messages.success(request, f'Framework {"activated" if fw.is_active else "deactivated"}.')
            except CompetencyFramework.DoesNotExist:
                messages.error(request, 'Framework not found.')
        return redirect('pms_competencies')

    frameworks = CompetencyFramework.objects.prefetch_related('competencies').order_by('-is_default', 'name')
    selected_fw_id = request.GET.get('framework')
    selected_framework = None
    if selected_fw_id:
        try:
            selected_framework = frameworks.get(id=selected_fw_id)
        except CompetencyFramework.DoesNotExist:
            pass
    if not selected_framework and frameworks.exists():
        selected_framework = frameworks.first()

    competency_types = Competency.CompetencyType.choices

    context = {
        'frameworks': frameworks,
        'selected_framework': selected_framework,
        'competency_types': competency_types,
        'is_hr': is_hr,
    }
    context.update(_get_employer_nav_context(user))
    return render(request, 'ems/pms_competencies.html', context)


@login_required
def payroll_list(request):
    """List payroll records"""
    from blu_staff.apps.payroll.models import Payroll, SalaryStructure, PayrollDeduction
    from blu_staff.apps.accounts.models import PayrollDeductionSettings
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Sum
    from datetime import date, datetime
    import csv
    from django.http import HttpResponse
    from decimal import Decimal
    
    User = get_user_model()
    
    # Handle payroll generation POST request
    if request.method == 'POST' and request.POST.get('action') == 'generate_payroll':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied. Only Finance/Accounting staff can generate payroll.')
            return redirect('payroll_list')
        
        try:
            period_start = datetime.strptime(request.POST.get('period_start'), '%Y-%m-%d').date()
            period_end = datetime.strptime(request.POST.get('period_end'), '%Y-%m-%d').date()
            pay_date = datetime.strptime(request.POST.get('pay_date'), '%Y-%m-%d').date()
            employee_selection = request.POST.get('employee_selection')
            
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
            
            # Get employees to generate payroll for
            if employee_selection == 'all':
                employees = User.objects.filter(
                    company=company,
                    role='EMPLOYEE',
                    is_active=True,
                    employee_profile__on_payroll=True,
                )
            else:
                selected_ids = request.POST.getlist('selected_employees')
                employees = User.objects.filter(
                    id__in=selected_ids,
                    company=company,
                    role='EMPLOYEE',
                    employee_profile__on_payroll=True,
                )
            
            # Get deduction settings
            try:
                deduction_settings = PayrollDeductionSettings.objects.get(company=company)
            except PayrollDeductionSettings.DoesNotExist:
                deduction_settings = None
            
            generated_count = 0
            for employee in employees:
                # Check if payroll already exists for this period
                if Payroll.objects.filter(employee=employee, period_start=period_start, period_end=period_end).exists():
                    continue
                
                # Get salary structure
                try:
                    salary_structure = SalaryStructure.objects.filter(employee=employee, is_active=True).first()
                    if not salary_structure:
                        continue
                    
                    base_pay = salary_structure.base_salary
                    
                    # Calculate gratuity
                    gratuity = Decimal('0')
                    if deduction_settings and deduction_settings.gratuity_enabled:
                        gratuity = (base_pay * deduction_settings.gratuity_percentage / 100).quantize(Decimal('0.01'))
                    
                    # Calculate deductions
                    paye = Decimal('0')
                    napsa = Decimal('0')
                    nhima = Decimal('0')
                    
                    if deduction_settings:
                        # Calculate NAPSA
                        if deduction_settings.napsa_enabled:
                            napsa = (base_pay * deduction_settings.napsa_employee_percentage / 100).quantize(Decimal('0.01'))
                        
                        # Calculate NHIMA (now percentage-based)
                        if deduction_settings.nhima_enabled:
                            nhima = (base_pay * deduction_settings.nhima_employee_percentage / 100).quantize(Decimal('0.01'))
                        
                        # Calculate PAYE (simplified - on taxable income after NAPSA and NHIMA)
                        if deduction_settings.paye_enabled and deduction_settings.paye_tax_brackets:
                            taxable_income = base_pay - napsa - nhima
                            for bracket in deduction_settings.paye_tax_brackets:
                                if taxable_income > bracket.get('min', 0):
                                    taxable_amount = min(taxable_income, bracket.get('max', taxable_income)) - bracket.get('min', 0)
                                    paye += (taxable_amount * Decimal(str(bracket.get('rate', 0))) / 100).quantize(Decimal('0.01'))
                    
                    # Determine currency (use salary structure currency, or default from settings, or ZMW)
                    currency = salary_structure.currency if hasattr(salary_structure, 'currency') and salary_structure.currency else (deduction_settings.currency if deduction_settings else 'ZMW')
                    
                    # Create payroll
                    payroll = Payroll.objects.create(
                        employee=employee,
                        period_start=period_start,
                        period_end=period_end,
                        pay_date=pay_date,
                        base_pay=base_pay,
                        overtime_pay=Decimal('0'),
                        bonus=Decimal('0'),
                        commission=Decimal('0'),
                        allowances=Decimal('0'),
                        gratuity=gratuity,
                        tax=paye,
                        social_security=napsa,
                        insurance=nhima,
                        other_deductions=Decimal('0'),
                        currency=currency,
                        status=Payroll.Status.DRAFT
                    )
                    
                    # Create detailed deductions
                    if paye > 0:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type='PAYE',
                            amount=paye,
                            description='Income Tax',
                            is_statutory=True
                        )
                    if napsa > 0:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type='NAPSA',
                            amount=napsa,
                            description='Social Security Contribution',
                            is_statutory=True
                        )
                    if nhima > 0:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type='NHIMA',
                            amount=nhima,
                            description='Health Insurance Contribution',
                            is_statutory=True
                        )
                    
                    generated_count += 1
                    
                except Exception as e:
                    continue
            
            if generated_count > 0:
                messages.success(request, f'Successfully generated payroll for {generated_count} employee(s).')
                # Notify all connected integrations about payroll generation
                try:
                    from integrations.integration_service import notify_all_channels, export_payroll_to_accounting
                    notify_all_channels(company, 'payroll_generated', {
                        'title': 'Payroll Generated',
                        'period': f'{period_start} to {period_end}',
                        'employee_count': generated_count,
                        'message': f'Payroll has been generated for {generated_count} employee(s) for the period {period_start} to {period_end}.',
                    })
                    # Auto-export to accounting if connected
                    export_payroll_to_accounting(company, [
                        {'employee_name': 'Batch', 'gross': 0, 'deductions': 0, 'net': 0, 'period': f'{period_start} to {period_end}', 'count': generated_count}
                    ])
                except Exception:
                    pass
            else:
                messages.warning(request, 'No payroll records were generated. They may already exist or employees may not have salary structures.')
            
            return redirect('payroll_list')
            
        except Exception as e:
            messages.error(request, f'Error generating payroll: {str(e)}')
            return redirect('payroll_list')
    
    # Handle manual payroll creation POST request
    if request.method == 'POST' and request.POST.get('action') == 'create_payroll':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied. Only Finance/Accounting staff can create payroll records.')
            return redirect('payroll_list')
        
        try:
            employee_id = request.POST.get('employee_id')
            employee = User.objects.select_related('employee_profile').get(id=employee_id)
            if not getattr(employee, 'employee_profile', None) or not employee.employee_profile.on_payroll:
                messages.error(request, 'Selected employee is not enabled for payroll.')
                return redirect('payroll_list')
            period_start = datetime.strptime(request.POST.get('period_start'), '%Y-%m-%d').date()
            period_end = datetime.strptime(request.POST.get('period_end'), '%Y-%m-%d').date()
            pay_date = datetime.strptime(request.POST.get('pay_date'), '%Y-%m-%d').date()
            
            # Check if payroll already exists
            if Payroll.objects.filter(employee=employee, period_start=period_start, period_end=period_end).exists():
                messages.error(request, 'Payroll record already exists for this employee and period.')
                return redirect('payroll_list')
            
            # Get form data
            base_pay = Decimal(request.POST.get('base_pay', '0'))
            overtime_pay = Decimal(request.POST.get('overtime_pay', '0'))
            bonus = Decimal(request.POST.get('bonus', '0'))
            commission = Decimal(request.POST.get('commission', '0'))
            allowances = Decimal(request.POST.get('allowances', '0'))
            gratuity = Decimal(request.POST.get('gratuity', '0'))
            
            tax = Decimal(request.POST.get('tax', '0'))
            social_security = Decimal(request.POST.get('social_security', '0'))
            insurance = Decimal(request.POST.get('insurance', '0'))
            late_deduction = Decimal(request.POST.get('late_deduction', '0'))
            absent_deduction = Decimal(request.POST.get('absent_deduction', '0'))
            other_deductions = Decimal(request.POST.get('other_deductions', '0'))
            
            currency = request.POST.get('currency', 'ZMW')
            notes = request.POST.get('notes', '')
            
            # Create payroll
            payroll = Payroll.objects.create(
                employee=employee,
                period_start=period_start,
                period_end=period_end,
                pay_date=pay_date,
                base_pay=base_pay,
                overtime_pay=overtime_pay,
                bonus=bonus,
                commission=commission,
                allowances=allowances,
                gratuity=gratuity,
                tax=tax,
                social_security=social_security,
                insurance=insurance,
                other_deductions=other_deductions + late_deduction + absent_deduction,
                currency=currency,
                notes=notes,
                status=Payroll.Status.DRAFT
            )
            
            # Create detailed deductions
            if tax > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='PAYE',
                    amount=tax,
                    description='Income Tax',
                    is_statutory=True
                )
            if social_security > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='NAPSA',
                    amount=social_security,
                    description='Social Security Contribution',
                    is_statutory=True
                )
            if insurance > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='NHIMA',
                    amount=insurance,
                    description='Health Insurance Contribution',
                    is_statutory=True
                )
            if late_deduction > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='LATE',
                    amount=late_deduction,
                    description='Late Arrival Deduction',
                    is_statutory=False
                )
            if absent_deduction > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='ABSENT',
                    amount=absent_deduction,
                    description='Absence Deduction',
                    is_statutory=False
                )
            if other_deductions > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='OTHER',
                    amount=other_deductions,
                    description='Other Deductions',
                    is_statutory=False
                )
            
            messages.success(request, f'Payroll record created successfully for {employee.get_full_name()}.')
            return redirect('payroll_detail', payroll_id=payroll.id)
            
        except Exception as e:
            messages.error(request, f'Error creating payroll: {str(e)}')
            return redirect('payroll_list')
    
    # Handle payroll configuration update POST request
    if request.method == 'POST' and request.POST.get('action') == 'update_payroll_config':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied. Only Finance/Accounting staff can update payroll configuration.')
            return redirect('payroll_list')
        
        try:
            import json
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
            # For accountants, get their company
            if not company and hasattr(request.user, 'employee_profile'):
                company = request.user.company
            
            # Get or create payroll settings
            payroll_settings, created = PayrollDeductionSettings.objects.get_or_create(company=company)
            
            # Update PAYE settings
            payroll_settings.paye_enabled = request.POST.get('paye_enabled') == 'on'
            try:
                paye_brackets = request.POST.get('paye_tax_brackets', '[]')
                payroll_settings.paye_tax_brackets = json.loads(paye_brackets)
            except json.JSONDecodeError:
                messages.error(request, 'Invalid JSON format for PAYE tax brackets.')
                return redirect('payroll_list')
            
            # Update NAPSA settings
            payroll_settings.napsa_enabled = request.POST.get('napsa_enabled') == 'on'
            payroll_settings.napsa_employee_percentage = Decimal(request.POST.get('napsa_employee_percentage', '5.0'))
            payroll_settings.napsa_employer_percentage = Decimal(request.POST.get('napsa_employer_percentage', '5.0'))
            
            # Update NHIMA settings
            payroll_settings.nhima_enabled = request.POST.get('nhima_enabled') == 'on'
            payroll_settings.nhima_employee_percentage = Decimal(request.POST.get('nhima_employee_percentage', '1.0'))
            payroll_settings.nhima_employer_percentage = Decimal(request.POST.get('nhima_employer_percentage', '1.0'))
            
            # Update Late/Absent deduction settings
            payroll_settings.late_deduction_type = request.POST.get('late_deduction_type', 'PERCENTAGE')
            payroll_settings.late_deduction_percentage = Decimal(request.POST.get('late_deduction_percentage', '5.0'))
            payroll_settings.absent_deduction_type = request.POST.get('absent_deduction_type', 'DAILY_RATE')
            payroll_settings.absent_deduction_percentage = Decimal(request.POST.get('absent_deduction_percentage', '100.0'))
            payroll_settings.working_days_per_month = int(request.POST.get('working_days_per_month', '22'))
            
            # Update Gratuity settings
            payroll_settings.gratuity_enabled = request.POST.get('gratuity_enabled') == 'on'
            payroll_settings.gratuity_percentage = Decimal(request.POST.get('gratuity_percentage', '8.33'))
            payroll_settings.gratuity_eligibility_months = int(request.POST.get('gratuity_eligibility_months', '12'))
            
            # Update currency
            payroll_settings.currency = request.POST.get('default_currency', 'ZMW')
            
            payroll_settings.save()
            messages.success(request, 'Payroll configuration updated successfully.')
            return redirect('payroll_list')
            
        except Exception as e:
            messages.error(request, f'Error updating payroll configuration: {str(e)}')
            return redirect('payroll_list')
    
    # Handle CSV import POST request
    if request.method == 'POST' and request.POST.get('action') == 'import_csv':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied. Only Finance/Accounting staff can import payroll.')
            return redirect('payroll_list')
        
        try:
            import csv as csv_module
            from io import TextIOWrapper
            
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, 'No CSV file uploaded.')
                return redirect('payroll_list')
            
            # Read CSV file
            decoded_file = TextIOWrapper(csv_file.file, encoding='utf-8')
            csv_reader = csv_module.DictReader(decoded_file)
            
            created_count = 0
            error_rows = []
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (1 is header)
                try:
                    employee_id = int(row['employee_id'])
                    employee = User.objects.get(id=employee_id)
                    period_start = datetime.strptime(row['period_start'], '%Y-%m-%d').date()
                    period_end = datetime.strptime(row['period_end'], '%Y-%m-%d').date()
                    pay_date = datetime.strptime(row['pay_date'], '%Y-%m-%d').date()
                    
                    # Check if payroll already exists
                    if Payroll.objects.filter(employee=employee, period_start=period_start, period_end=period_end).exists():
                        error_rows.append(f"Row {row_num}: Payroll already exists for {employee.get_full_name()}")
                        continue
                    
                    # Get values from CSV
                    base_pay = Decimal(row.get('base_pay', '0'))
                    overtime_pay = Decimal(row.get('overtime_pay', '0'))
                    bonus = Decimal(row.get('bonus', '0'))
                    commission = Decimal(row.get('commission', '0'))
                    allowances = Decimal(row.get('allowances', '0'))
                    gratuity = Decimal(row.get('gratuity', '0'))
                    
                    tax = Decimal(row.get('tax', '0'))
                    social_security = Decimal(row.get('napsa', '0'))
                    insurance = Decimal(row.get('nhima', '0'))
                    late_deduction = Decimal(row.get('late_deduction', '0'))
                    absent_deduction = Decimal(row.get('absent_deduction', '0'))
                    other_deductions = Decimal(row.get('other_deductions', '0'))
                    
                    currency = row.get('currency', 'ZMW')
                    notes = row.get('notes', '')
                    
                    # Create payroll
                    payroll = Payroll.objects.create(
                        employee=employee,
                        period_start=period_start,
                        period_end=period_end,
                        pay_date=pay_date,
                        base_pay=base_pay,
                        overtime_pay=overtime_pay,
                        bonus=bonus,
                        commission=commission,
                        allowances=allowances,
                        gratuity=gratuity,
                        tax=tax,
                        social_security=social_security,
                        insurance=insurance,
                        other_deductions=other_deductions + late_deduction + absent_deduction,
                        currency=currency,
                        notes=notes,
                        status=Payroll.Status.DRAFT
                    )
                    
                    # Create detailed deductions
                    if tax > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='PAYE', amount=tax, description='Income Tax', is_statutory=True)
                    if social_security > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='NAPSA', amount=social_security, description='Social Security', is_statutory=True)
                    if insurance > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='NHIMA', amount=insurance, description='Health Insurance', is_statutory=True)
                    if late_deduction > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='LATE', amount=late_deduction, description='Late Deduction', is_statutory=False)
                    if absent_deduction > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='ABSENT', amount=absent_deduction, description='Absence Deduction', is_statutory=False)
                    if other_deductions > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='OTHER', amount=other_deductions, description='Other Deductions', is_statutory=False)
                    
                    created_count += 1
                    
                except Exception as e:
                    error_rows.append(f"Row {row_num}: {str(e)}")
                    continue
            
            if created_count > 0:
                messages.success(request, f'Successfully imported {created_count} payroll record(s) from CSV.')
            if error_rows:
                messages.warning(request, f'Errors encountered: {", ".join(error_rows[:5])}{"..." if len(error_rows) > 5 else ""}')
            if created_count == 0 and not error_rows:
                messages.warning(request, 'No payroll records were imported.')
            
            return redirect('payroll_list')
            
        except Exception as e:
            messages.error(request, f'Error importing CSV: {str(e)}')
            return redirect('payroll_list')
    
    # Handle batch approve
    if request.method == 'POST' and request.POST.get('action') == 'batch_approve':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied.')
            return redirect('payroll_list')
        payroll_ids = request.POST.getlist('payroll_ids')
        if payroll_ids:
            updated = Payroll.objects.filter(
                id__in=payroll_ids,
                status__in=[Payroll.Status.DRAFT, Payroll.Status.PENDING_APPROVAL]
            ).update(status=Payroll.Status.APPROVED)
            messages.success(request, f'{updated} payroll record(s) approved successfully.')
        return redirect('payroll_list')

    # Handle batch mark as paid
    if request.method == 'POST' and request.POST.get('action') == 'batch_mark_paid':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied.')
            return redirect('payroll_list')
        payroll_ids = request.POST.getlist('payroll_ids')
        if payroll_ids:
            updated = Payroll.objects.filter(
                id__in=payroll_ids,
                status=Payroll.Status.APPROVED
            ).update(status=Payroll.Status.PAID)
            messages.success(request, f'{updated} payroll record(s) marked as paid.')
        return redirect('payroll_list')

    # Check payroll access permissions
    has_payroll_access = _has_payroll_access(request.user)

    # Determine base template: only true admins get employer nav; HR/accountant employees get employee nav
    base_template = 'ems/base_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/base_employee.html'
    
    if request.user.role == 'EMPLOYEE' and not has_payroll_access:
        # Regular employees can only see their own payroll
        payrolls = Payroll.objects.filter(employee=request.user).order_by('-period_end')
        
        # Employee statistics
        total_payrolls = payrolls.count()
        draft_count = payrolls.filter(status=Payroll.Status.DRAFT).count()
        approved_count = payrolls.filter(status=Payroll.Status.APPROVED).count()
        paid_count = payrolls.filter(status=Payroll.Status.PAID).count()
        total_earned = payrolls.filter(status=Payroll.Status.PAID).aggregate(total=Sum('net_pay'))['total'] or 0
        
        search_query = ''
        status_filter = ''
        date_from = ''
        date_to = ''
        company = None
        employees = User.objects.none()
        
    elif has_payroll_access:
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        
        # Get all payrolls for statistics
        all_payrolls = Payroll.objects.filter(employee__company=company)
        
        # Calculate statistics
        total_payrolls = all_payrolls.count()
        draft_count = all_payrolls.filter(status=Payroll.Status.DRAFT).count()
        approved_count = all_payrolls.filter(status=Payroll.Status.APPROVED).count()
        paid_count = all_payrolls.filter(status=Payroll.Status.PAID).count()
        total_earned = all_payrolls.filter(status=Payroll.Status.PAID).aggregate(total=Sum('net_pay'))['total'] or 0
        
        payrolls = all_payrolls.select_related('employee', 'employee__employee_profile').order_by('-period_end')
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            payrolls = payrolls.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__email__icontains=search_query)
            )
        
        # Status filter
        status_filter = request.GET.get('status', '')
        if status_filter:
            payrolls = payrolls.filter(status=status_filter)
        
        # Date range filter
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        if date_from:
            payrolls = payrolls.filter(period_end__gte=date_from)
        if date_to:
            payrolls = payrolls.filter(period_end__lte=date_to)
        
        # Get employees for potential filtering (only those allowed on payroll)
        employees = User.objects.filter(
            company=company,
            role='EMPLOYEE',
            is_active=True,
            employee_profile__on_payroll=True,
        )
        
        # CSV Export
        export_type = request.GET.get('export', '')
        if export_type == 'csv':
            filename = f"payrolls_{date.today().strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(response)
            
            writer.writerow([
                'Employee', 'Position', 'Period Start', 'Period End', 'Pay Date',
                'Base Pay', 'Overtime', 'Bonus', 'Gross Pay', 'Deductions', 'Net Pay',
                'Status', 'Currency'
            ])
            
            for payroll in payrolls:
                writer.writerow([
                    payroll.employee.get_full_name(),
                    payroll.employee.employee_profile.job_title if hasattr(payroll.employee, 'employee_profile') and payroll.employee.employee_profile else 'N/A',
                    payroll.period_start.strftime('%Y-%m-%d'),
                    payroll.period_end.strftime('%Y-%m-%d'),
                    payroll.pay_date.strftime('%Y-%m-%d'),
                    payroll.base_pay,
                    payroll.overtime_pay,
                    payroll.bonus,
                    payroll.gross_pay,
                    payroll.total_deductions,
                    payroll.net_pay,
                    payroll.get_status_display(),
                    payroll.currency
                ])
            
            return response
    else:
        payrolls = Payroll.objects.none()
        search_query = ''
        status_filter = ''
        date_from = ''
        date_to = ''
        total_payrolls = 0
        draft_count = 0
        approved_count = 0
        paid_count = 0
        total_earned = 0
        employees = User.objects.none()
        company = request.user.company
    
    payroll_settings = None
    if company:
        # Get or create default payroll settings
        payroll_settings, created = PayrollDeductionSettings.objects.get_or_create(
            company=company,
            defaults={
                'paye_enabled': True,
                'paye_tax_brackets': [
                    {"min": 0, "max": 4800, "rate": 0},
                    {"min": 4800, "max": 50000, "rate": 25},
                    {"min": 50000, "max": None, "rate": 37.5}
                ],
                'napsa_enabled': True,
                'napsa_employee_percentage': Decimal('5.0'),
                'napsa_employer_percentage': Decimal('5.0'),
                'nhima_enabled': True,
                'nhima_employee_percentage': Decimal('1.0'),
                'nhima_employer_percentage': Decimal('1.0'),
                'late_deduction_type': 'PERCENTAGE',
                'late_deduction_percentage': Decimal('5.0'),
                'absent_deduction_type': 'DAILY_RATE',
                'absent_deduction_percentage': Decimal('100.0'),
                'working_days_per_month': 22,
                'gratuity_enabled': False,
                'gratuity_percentage': Decimal('8.33'),
                'gratuity_eligibility_months': 12,
                'currency': 'ZMW'
            }
        )
        if created:
            messages.info(request, 'Default payroll settings have been created. Please review and customize them in the Payroll Configuration tab.')
    
    # Prepare payroll settings as JSON for JavaScript and template
    import json
    payroll_settings_json = None
    paye_tax_brackets_json = None
    if payroll_settings:
        payroll_settings_json = json.dumps({
            'paye_enabled': payroll_settings.paye_enabled,
            'paye_tax_brackets': payroll_settings.paye_tax_brackets,
            'napsa_enabled': payroll_settings.napsa_enabled,
            'napsa_employee_percentage': float(payroll_settings.napsa_employee_percentage),
            'nhima_enabled': payroll_settings.nhima_enabled,
            'nhima_employee_percentage': float(payroll_settings.nhima_employee_percentage),
            'gratuity_enabled': payroll_settings.gratuity_enabled,
            'gratuity_percentage': float(payroll_settings.gratuity_percentage),
            'gratuity_eligibility_months': payroll_settings.gratuity_eligibility_months,
            'working_days_per_month': payroll_settings.working_days_per_month,
        })
        # Serialize paye_tax_brackets for textarea display
        paye_tax_brackets_json = json.dumps(payroll_settings.paye_tax_brackets, indent=2)
    
    # Pending approval count
    pending_approval_count = 0
    if has_payroll_access and company:
        pending_approval_count = Payroll.objects.filter(
            employee__company=company,
            status=Payroll.Status.PENDING_APPROVAL
        ).count()

    # Currency code from settings
    currency_code = getattr(payroll_settings, 'currency', 'ZMW') if payroll_settings else 'ZMW'

    context = {
        'payrolls': payrolls,
        'user': request.user,
        'company': company,
        'base_template': base_template,
        'search_query': search_query,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Payroll.Status.choices,
        'total_payrolls': total_payrolls,
        'draft_count': draft_count,
        'approved_count': approved_count,
        'paid_count': paid_count,
        'pending_approval_count': pending_approval_count,
        'total_earned': total_earned,
        'employees': employees,
        'payroll_settings': payroll_settings,
        'payroll_settings_json': payroll_settings_json,
        'paye_tax_brackets_json': paye_tax_brackets_json,
        'currency_code': currency_code,
        'has_payroll_access': has_payroll_access,
    }
    return render(request, 'ems/payroll_list.html', context)


@login_required
def payroll_detail(request, payroll_id):
    """View individual payslip detail"""
    from blu_staff.apps.payroll.models import Payroll, PayrollDeduction
    
    try:
        payroll = Payroll.objects.select_related('employee', 'employee__employee_profile', 'employee__company').get(id=payroll_id)
    except Payroll.DoesNotExist:
        messages.error(request, 'Payslip not found.')
        return redirect('payroll_list')
    
    # Check permissions
    if request.user.role == 'EMPLOYEE':
        # Employees can only see their own payroll
        if payroll.employee != request.user:
            messages.error(request, 'Access denied. You can only view your own payroll records.')
            return redirect('payroll_list')
    elif not _has_payroll_access(request.user):
        # Only Finance/Accounting/HR staff can view all payroll records
        messages.error(request, 'Access denied. Payroll access is restricted to Finance/Accounting staff.')
        return redirect('payroll_list')
    
    # Get detailed deductions
    deductions = PayrollDeduction.objects.filter(payroll=payroll).order_by('deduction_type')
    
    # Force concrete string evaluation to avoid lazy proxy recursion in Python 3.14
    period_start_formatted = str(payroll.period_start.strftime('%B %Y')) if payroll.period_start else ''
    pay_date_formatted = str(payroll.pay_date.strftime('%d %b %Y').upper()) if payroll.pay_date else ''

    # Get company stamp positioning from designer
    company = payroll.employee.company
    stamp_config = {
        'drag_x': 0,
        'drag_y': 0,
        'opacity': 100,
        'size': 130,
        'rotation': 0,
    }
    if company and hasattr(company, 'payslip_field_positions') and company.payslip_field_positions:
        field_pos = company.payslip_field_positions
        if isinstance(field_pos, dict):
            if 'stamp_drag' in field_pos and isinstance(field_pos['stamp_drag'], dict):
                stamp_config['drag_x'] = field_pos['stamp_drag'].get('x', 0)
                stamp_config['drag_y'] = field_pos['stamp_drag'].get('y', 0)
            stamp_config['opacity'] = field_pos.get('stamp_opacity', 100)
            stamp_config['size'] = field_pos.get('stamp_size', 130)
            stamp_config['rotation'] = field_pos.get('stamp_rotation', 0)

    context = {
        'payroll': payroll,
        'deductions': deductions,
        'period_start_formatted': period_start_formatted,
        'pay_date_formatted': pay_date_formatted,
        'stamp_config': stamp_config,
    }
    return render(request, 'ems/payroll_detail.html', context)


@login_required
def payslip_designer(request):
    """Payslip layout designer – save company payslip settings"""
    from blu_staff.apps.accounts.models import Company

    if request.user.role not in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        messages.error(request, 'Access denied.')
        return redirect('payroll_list')

    try:
        company = Company.objects.get(id=request.user.company_id)
    except Company.DoesNotExist:
        messages.error(request, 'Company not found.')
        return redirect('payroll_list')

    if request.method == 'POST':
        company.payslip_layout = request.POST.get('layout', company.payslip_layout)
        company.payslip_orientation = request.POST.get('orientation', company.payslip_orientation)
        company.payslip_stamp_position = request.POST.get('stamp_position', company.payslip_stamp_position)
        company.payslip_logo_position = request.POST.get('logo_position', company.payslip_logo_position)
        company.payslip_address_position = request.POST.get('address_position', company.payslip_address_position)
        company.payslip_header_content = request.POST.get('header_content', company.payslip_header_content)
        company.payslip_footer_content = request.POST.get('footer_content', company.payslip_footer_content)
        import json
        section_order_raw = request.POST.get('section_order', '[]')
        try:
            company.payslip_section_order = json.loads(section_order_raw)
        except (ValueError, TypeError):
            company.payslip_section_order = []
        company.save()
        messages.success(request, 'Payslip design saved successfully.')
        return redirect('payslip_designer')

    available_sections = [
        {'id': 'header', 'name': 'Company Header', 'icon': '🏢'},
        {'id': 'employee_info', 'name': 'Employee Information', 'icon': '👤'},
        {'id': 'earnings', 'name': 'Earnings', 'icon': '💰'},
        {'id': 'statutory', 'name': 'Statutory Deductions', 'icon': '📋'},
        {'id': 'other_deductions', 'name': 'Other Deductions', 'icon': '➖'},
        {'id': 'summary', 'name': 'Summary Totals', 'icon': '📊'},
        {'id': 'signature', 'name': 'Signature & Stamp', 'icon': '✅'},
        {'id': 'footer', 'name': 'Footer', 'icon': '📄'},
    ]

    position_options = [
        {'value': 'top-left', 'label': '↖ Top Left'},
        {'value': 'top-center', 'label': '↑ Top Center'},
        {'value': 'top-right', 'label': '↗ Top Right'},
        {'value': 'bottom-left', 'label': '↙ Bottom Left'},
        {'value': 'bottom-center', 'label': '↓ Bottom Center'},
        {'value': 'bottom-right', 'label': '↘ Bottom Right'},
    ]

    context = {
        'company': company,
        'available_sections': available_sections,
        'position_options': position_options,
    }
    return render(request, 'ems/payslip_designer.html', context)


@login_required
def benefits_list(request):
    """List employee benefits"""
    from blu_staff.apps.payroll.models import Benefit, EmployeeBenefit, BenefitClaim
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Count
    import csv
    from django.http import HttpResponse
    from datetime import date
    
    User = get_user_model()

    company_contribution_total = Decimal('0.00')
    employee_contribution_total = Decimal('0.00')
    benefit_overview = []

    def build_benefit_overview(enrollments):
        summary = defaultdict(lambda: {
            'benefit': None,
            'total': 0,
            'active': 0,
            'pending': 0,
            'suspended': 0,
            'cancelled': 0,
        })

        for enrollment in enrollments:
            if not enrollment.benefit:
                continue

            data = summary[enrollment.benefit_id]
            if data['benefit'] is None:
                data['benefit'] = enrollment.benefit

            data['total'] += 1
            if enrollment.status == EmployeeBenefit.Status.ACTIVE:
                data['active'] += 1
            elif enrollment.status == EmployeeBenefit.Status.PENDING:
                data['pending'] += 1
            elif enrollment.status == EmployeeBenefit.Status.SUSPENDED:
                data['suspended'] += 1
            elif enrollment.status == EmployeeBenefit.Status.CANCELLED:
                data['cancelled'] += 1

        return sorted(
            summary.values(),
            key=lambda item: item['benefit'].name if item['benefit'] else ''
        )

    def legacy_snapshot_for_company(company):
        snapshot = {
            'enrollments': [],
            'available_benefits': [],
            'total_enrolled': 0,
            'active_count': 0,
            'pending_count': 0,
            'company_contribution_total': Decimal('0.00'),
            'employee_contribution_total': Decimal('0.00'),
            'benefit_overview': [],
        }

        if not company:
            return snapshot

        def dictfetchall(cursor):
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

        def label_from_choices(choices_map, code):
            if code in choices_map:
                return choices_map[code]
            if isinstance(code, str):
                return code.replace('_', ' ').title()
            return code

        benefit_type_labels = dict(Benefit.BenefitType.choices)
        status_labels = dict(EmployeeBenefit.Status.choices)

        class LegacyEmployeeProfile:
            def __init__(self, job_title):
                self.job_title = job_title

        class LegacyEmployee:
            def __init__(self, row):
                self.id = row['employee_id']
                self.first_name = row['first_name']
                self.last_name = row['last_name']
                self.employee_profile = LegacyEmployeeProfile(row.get('job_title'))

            def get_full_name(self):
                return f"{self.first_name} {self.last_name}".strip()

        class LegacyBenefit:
            def __init__(self, row):
                self.id = row['benefit_id']
                self.name = row['benefit_name']
                self.benefit_type = row['benefit_type']
                self.description = row.get('benefit_description')
                self.company_contribution = Decimal(str(row.get('benefit_company_contribution') or 0))
                self.employee_contribution = Decimal(str(row.get('benefit_employee_contribution') or 0))
                self.is_mandatory = bool(row.get('benefit_is_mandatory'))

            def get_benefit_type_display(self):
                return label_from_choices(benefit_type_labels, self.benefit_type)

        class LegacyEnrollment:
            def __init__(self, row):
                self.id = row['id']
                self.employee_id = row['employee_id']
                self.benefit = LegacyBenefit(row)
                self.benefit_id = self.benefit.id
                self.status = row['status']
                self.enrollment_date = row.get('enrollment_date')
                self.effective_date = row.get('effective_date')
                self.end_date = row.get('end_date')
                self.notes = row.get('notes')
                self.created_at = row.get('created_at')
                self.updated_at = row.get('updated_at')
                self.employee = LegacyEmployee(row)

                if isinstance(self.enrollment_date, str):
                    self.enrollment_date = datetime.fromisoformat(self.enrollment_date).date()
                if isinstance(self.effective_date, str):
                    self.effective_date = datetime.fromisoformat(self.effective_date).date()
                if isinstance(self.end_date, str) and self.end_date:
                    self.end_date = datetime.fromisoformat(self.end_date).date()

            def get_status_display(self):
                return label_from_choices(status_labels, self.status)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT eb.id,
                       eb.employee_id,
                       eb.benefit_id,
                       eb.enrollment_date,
                       eb.effective_date,
                       eb.end_date,
                       eb.status,
                       eb.notes,
                       eb.created_at,
                       eb.updated_at,
                       b.name AS benefit_name,
                       b.benefit_type,
                       b.description AS benefit_description,
                       b.company_contribution AS benefit_company_contribution,
                       b.employee_contribution AS benefit_employee_contribution,
                       b.is_mandatory AS benefit_is_mandatory,
                       u.first_name,
                       u.last_name,
                       ep.job_title
                FROM payroll_employeebenefit eb
                INNER JOIN accounts_user u ON eb.employee_id = u.id
                LEFT JOIN accounts_employeeprofile ep ON ep.employee_id = u.id
                INNER JOIN payroll_benefit b ON eb.benefit_id = b.id
                WHERE u.company_id = %s
                ORDER BY eb.enrollment_date DESC
                """,
                [company.id],
            )
            enrollment_rows = dictfetchall(cursor)

            cursor.execute(
                """
                SELECT b.id AS benefit_id,
                       b.name AS benefit_name,
                       b.benefit_type,
                       b.description AS benefit_description,
                       b.company_contribution AS benefit_company_contribution,
                       b.employee_contribution AS benefit_employee_contribution,
                       b.is_mandatory AS benefit_is_mandatory
                FROM payroll_benefit b
                WHERE b.is_active = 1
                ORDER BY b.name ASC
                """
            )
            benefit_rows = dictfetchall(cursor)

        enrollments = [LegacyEnrollment(row) for row in enrollment_rows]
        available_benefits = [LegacyBenefit(row) for row in benefit_rows]

        active_count = 0
        pending_count = 0
        company_contribution_total = Decimal('0.00')
        employee_contribution_total = Decimal('0.00')

        for enrollment in enrollments:
            if enrollment.status == EmployeeBenefit.Status.ACTIVE:
                active_count += 1
                company_contribution_total += enrollment.benefit.company_contribution
                employee_contribution_total += enrollment.benefit.employee_contribution
            elif enrollment.status == EmployeeBenefit.Status.PENDING:
                pending_count += 1
            elif enrollment.status == EmployeeBenefit.Status.SUSPENDED:
                # pending_count remains the same; no extra tracking needed currently
                pass

        snapshot['enrollments'] = enrollments
        snapshot['available_benefits'] = available_benefits
        snapshot['total_enrolled'] = len(enrollments)
        snapshot['active_count'] = active_count
        snapshot['pending_count'] = pending_count
        snapshot['company_contribution_total'] = company_contribution_total
        snapshot['employee_contribution_total'] = employee_contribution_total
        snapshot['benefit_overview'] = build_benefit_overview(enrollments)

        return snapshot

    supports_tenant_metadata = tenant_metadata_available()
    using_legacy_mode = False

    user_company = getattr(request.user, 'company', None)
    tenant_for_forms = getattr(user_company, 'tenant', None) if user_company else None
    company = None

    # Check if user is HR (employee with HR role)
    is_hr = (request.user.role == 'EMPLOYEE' and 
             hasattr(request.user, 'employee_profile') and 
             request.user.employee_profile.employee_role == 'HR')

    # HR/Admin access flag (even if role is EMPLOYEE)
    is_hr_user = _has_hr_access(request.user)

    # Check if user wants personal view (from main menu)
    view_personal = request.GET.get('view') == 'personal'

    # Base template: keep employee layout (avoid admin sidebar)
    base_template = 'ems/base_employee.html'

    enrolled_benefit_ids = set()

    is_accountant_user = (hasattr(request.user, 'employee_profile') and
                          request.user.employee_profile and
                          request.user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])

    if request.user.role == 'EMPLOYEE' and (not (is_hr_user or is_accountant_user) or view_personal):
        if supports_tenant_metadata:
            enrolled_benefits = EmployeeBenefit.objects.filter(employee=request.user).select_related('benefit').order_by('-enrollment_date')
            available_benefits = Benefit.objects.filter(is_active=True)
            enrolled_benefit_ids = set(str(e.benefit_id) for e in enrolled_benefits)
            
            # Employee statistics
            total_enrolled = enrolled_benefits.count()
            active_count = enrolled_benefits.filter(status=EmployeeBenefit.Status.ACTIVE).count()
            pending_count = enrolled_benefits.filter(status=EmployeeBenefit.Status.PENDING).count()

            active_enrollments = enrolled_benefits.filter(status=EmployeeBenefit.Status.ACTIVE)
            contribution_totals = active_enrollments.aggregate(
                company_total=Sum('benefit__company_contribution'),
                employee_total=Sum('benefit__employee_contribution')
            )
            company_contribution_total = contribution_totals.get('company_total') or Decimal('0.00')
            employee_contribution_total = contribution_totals.get('employee_total') or Decimal('0.00')
            try:
                benefit_overview = build_benefit_overview(enrolled_benefits)
            except OperationalError:
                benefit_overview = []
            
            search_query = ''
            status_filter = ''
            benefit_type_filter = ''
            company = None
        else:
            messages.warning(
                request,
                'Benefits data is being displayed in compatibility mode because the local database is missing tenant metadata. Consider running the latest migrations.',
            )

            legacy_data = legacy_snapshot_for_company(user_company)
            user_enrollments = [enrollment for enrollment in legacy_data['enrollments'] if enrollment.employee_id == request.user.id]
            available_benefits = legacy_data['available_benefits']

            total_enrolled = len(user_enrollments)
            active_count = sum(1 for enrollment in user_enrollments if enrollment.status == EmployeeBenefit.Status.ACTIVE)
            pending_count = sum(1 for enrollment in user_enrollments if enrollment.status == EmployeeBenefit.Status.PENDING)
            company_contribution_total = sum(
                enrollment.benefit.company_contribution
                for enrollment in user_enrollments
                if enrollment.status == EmployeeBenefit.Status.ACTIVE
            )
            employee_contribution_total = sum(
                enrollment.benefit.employee_contribution
                for enrollment in user_enrollments
                if enrollment.status == EmployeeBenefit.Status.ACTIVE
            )
            benefit_overview = build_benefit_overview(user_enrollments)

            search_query = request.GET.get('search', '').strip()
            status_filter = request.GET.get('status', '')
            benefit_type_filter = request.GET.get('benefit_type', '')

            def matches_search(enrollment, term):
                if not term:
                    return True
                term_lower = term.lower()
                employee_name = enrollment.employee.get_full_name().lower()
                benefit_name = enrollment.benefit.name.lower() if enrollment.benefit and enrollment.benefit.name else ''
                return term_lower in employee_name or term_lower in benefit_name

            def matches_status(enrollment, code):
                if not code:
                    return True
                return enrollment.status == code

            def matches_benefit_type(enrollment, code):
                if not code:
                    return True
                return enrollment.benefit and enrollment.benefit.benefit_type == code

            enrolled_benefits = [
                enrollment for enrollment in user_enrollments
                if matches_search(enrollment, search_query)
                and matches_status(enrollment, status_filter)
                and matches_benefit_type(enrollment, benefit_type_filter)
            ]

            if request.GET.get('format') == 'csv':
                filename = f"benefits_{date.today().strftime('%Y%m%d')}.csv"
                response = HttpResponse(content_type='text/csv; charset=utf-8')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response.write('\ufeff')
                writer = csv.writer(response)

                writer.writerow([
                    'Benefit Name', 'Benefit Type', 'Enrollment Date', 'Effective Date', 'Status',
                    'Company Contribution', 'Employee Contribution'
                ])

                for enrollment in enrolled_benefits:
                    writer.writerow([
                        enrollment.benefit.name,
                        enrollment.benefit.get_benefit_type_display(),
                        enrollment.enrollment_date.strftime('%Y-%m-%d') if enrollment.enrollment_date else '',
                        enrollment.effective_date.strftime('%Y-%m-%d') if enrollment.effective_date else '',
                        enrollment.get_status_display(),
                        enrollment.benefit.company_contribution,
                        enrollment.benefit.employee_contribution,
                    ])

                return response

            company = None
            using_legacy_mode = True

    elif request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] or is_hr or is_accountant_user:
        company = getattr(request.user, 'company', None) or _get_user_company(request.user)
        tenant = getattr(company, 'tenant', None) if company else None
        fallback_to_legacy = not supports_tenant_metadata

        if not fallback_to_legacy:
            try:
                # Get all enrollments for statistics (scope to tenant when available)
                all_enrollments = EmployeeBenefit.objects.filter(employee__company=company)
                if tenant:
                    all_enrollments = all_enrollments.filter(tenant=tenant)

                # Calculate statistics
                total_enrolled = all_enrollments.count()
                active_enrollments = all_enrollments.filter(status=EmployeeBenefit.Status.ACTIVE)
                active_count = active_enrollments.count()
                pending_count = all_enrollments.filter(status=EmployeeBenefit.Status.PENDING).count()

                contribution_totals = active_enrollments.aggregate(
                    company_total=Sum('benefit__company_contribution'),
                    employee_total=Sum('benefit__employee_contribution')
                )
                company_contribution_total = contribution_totals.get('company_total') or Decimal('0.00')
                employee_contribution_total = contribution_totals.get('employee_total') or Decimal('0.00')

                enrolled_benefits = all_enrollments.select_related('employee', 'employee__employee_profile', 'benefit').order_by('-enrollment_date')
                available_benefits = Benefit.objects.filter(is_active=True)
                if tenant:
                    available_benefits = available_benefits.filter(tenant=tenant)
                benefit_overview = build_benefit_overview(all_enrollments.select_related('benefit'))

                # Search filter
                search_query = request.GET.get('search', '').strip()
                if search_query:
                    enrolled_benefits = enrolled_benefits.filter(
                        Q(employee__first_name__icontains=search_query) |
                        Q(employee__last_name__icontains=search_query) |
                        Q(benefit__name__icontains=search_query)
                    )

                # Status filter
                status_filter = request.GET.get('status', '')
                if status_filter:
                    enrolled_benefits = enrolled_benefits.filter(status=status_filter)

                # Benefit type filter
                benefit_type_filter = request.GET.get('benefit_type', '')
                if benefit_type_filter:
                    enrolled_benefits = enrolled_benefits.filter(benefit__benefit_type=benefit_type_filter)

                # CSV Export
                if request.GET.get('format') == 'csv':
                    filename = f"benefits_{date.today().strftime('%Y%m%d')}.csv"
                    response = HttpResponse(content_type='text/csv; charset=utf-8')
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    response.write('\ufeff')  # UTF-8 BOM
                    writer = csv.writer(response)

                    writer.writerow([
                        'Employee', 'Position', 'Benefit Name', 'Benefit Type',
                        'Enrollment Date', 'Effective Date', 'Status',
                        'Company Contribution', 'Employee Contribution'
                    ])

                    for enrollment in enrolled_benefits:
                        writer.writerow([
                            enrollment.employee.get_full_name(),
                            enrollment.employee.employee_profile.job_title if hasattr(enrollment.employee, 'employee_profile') and enrollment.employee.employee_profile else 'N/A',
                            enrollment.benefit.name,
                            enrollment.benefit.get_benefit_type_display(),
                            enrollment.enrollment_date.strftime('%Y-%m-%d'),
                            enrollment.effective_date.strftime('%Y-%m-%d'),
                            enrollment.get_status_display(),
                            enrollment.benefit.company_contribution,
                            enrollment.benefit.employee_contribution,
                        ])

                    return response

            except OperationalError:
                fallback_to_legacy = True

        if fallback_to_legacy:
            messages.warning(
                request,
                'Benefits data is being displayed in compatibility mode because the local database is missing tenant metadata. Consider running the latest migrations.',
            )

            legacy_data = legacy_snapshot_for_company(company)
            legacy_enrollments = legacy_data['enrollments']
            available_benefits = legacy_data['available_benefits']
            total_enrolled = legacy_data['total_enrolled']
            active_count = legacy_data['active_count']
            pending_count = legacy_data['pending_count']
            company_contribution_total = legacy_data['company_contribution_total']
            employee_contribution_total = legacy_data['employee_contribution_total']
            benefit_overview = legacy_data['benefit_overview']

            search_query = request.GET.get('search', '').strip()
            status_filter = request.GET.get('status', '')
            benefit_type_filter = request.GET.get('benefit_type', '')

            def matches_search(enrollment, term):
                if not term:
                    return True
                term_lower = term.lower()
                employee_name = f"{enrollment.employee.first_name} {enrollment.employee.last_name}".lower()
                benefit_name = enrollment.benefit.name.lower() if enrollment.benefit and enrollment.benefit.name else ''
                return term_lower in employee_name or term_lower in benefit_name

            def matches_status(enrollment, code):
                if not code:
                    return True
                return enrollment.status == code

            def matches_benefit_type(enrollment, code):
                if not code:
                    return True
                return enrollment.benefit and enrollment.benefit.benefit_type == code

            filtered_enrollments = [
                enrollment for enrollment in legacy_enrollments
                if matches_search(enrollment, search_query)
                and matches_status(enrollment, status_filter)
                and matches_benefit_type(enrollment, benefit_type_filter)
            ]

            enrolled_benefits = filtered_enrollments

            if request.GET.get('format') == 'csv':
                filename = f"benefits_{date.today().strftime('%Y%m%d')}.csv"
                response = HttpResponse(content_type='text/csv; charset=utf-8')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response.write('\ufeff')
                writer = csv.writer(response)

                writer.writerow([
                    'Employee', 'Position', 'Benefit Name', 'Benefit Type',
                    'Enrollment Date', 'Effective Date', 'Status',
                    'Company Contribution', 'Employee Contribution'
                ])

                for enrollment in enrolled_benefits:
                    writer.writerow([
                        enrollment.employee.get_full_name(),
                        enrollment.employee.employee_profile.job_title or 'N/A',
                        enrollment.benefit.name,
                        enrollment.benefit.get_benefit_type_display(),
                        enrollment.enrollment_date.strftime('%Y-%m-%d') if enrollment.enrollment_date else '',
                        enrollment.effective_date.strftime('%Y-%m-%d') if enrollment.effective_date else '',
                        enrollment.get_status_display(),
                        enrollment.benefit.company_contribution,
                        enrollment.benefit.employee_contribution,
                    ])

                return response

            using_legacy_mode = True

    else:
        enrolled_benefits = EmployeeBenefit.objects.none()
        available_benefits = Benefit.objects.none()
        search_query = ''
        status_filter = ''
        benefit_type_filter = ''
        total_enrolled = 0
        active_count = 0
        pending_count = 0
        company = None

    # Determine company for claims (reuse existing company if set)
    if not company:
        company = _get_user_company(request.user)

    # Scope claims by company if available (avoid cross-tenant bleed); fallback to user's own claims
    if company:
        benefit_claims = BenefitClaim.objects.filter(employee__company=company)
        # If employee but not HR, restrict to own claims only
        if request.user.role == 'EMPLOYEE' and not is_hr_user:
            benefit_claims = benefit_claims.filter(employee=request.user)
    else:
        benefit_claims = BenefitClaim.objects.filter(employee=request.user)

    try:
        total_benefits_count = available_benefits.count()
    except (TypeError, AttributeError):
        total_benefits_count = len(available_benefits)

    can_manage_benefits = (
        request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
        and not using_legacy_mode
        and supports_tenant_metadata
    )

    benefit_form = None
    enrollment_form = None
    if can_manage_benefits:
        from blu_staff.apps.payroll.forms import BenefitForm, BenefitEnrollmentForm

        benefit_form = BenefitForm()
        enrollment_form = BenefitEnrollmentForm(company=user_company, tenant=tenant_for_forms)

    _is_management_view = (
        request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
        or (hasattr(request.user, 'employee_profile') and request.user.employee_profile
            and request.user.employee_profile.employee_role in ['HR', 'ACCOUNTANT', 'ACCOUNTS'])
        and not view_personal
    )

    context = {
        'enrolled_benefits': enrolled_benefits,
        'available_benefits': available_benefits,
        'enrolled_benefit_ids': enrolled_benefit_ids,
        'user': request.user,
        'company': company,
        'search_query': search_query,
        'status_filter': status_filter,
        'benefit_type_filter': benefit_type_filter,
        'status_choices': EmployeeBenefit.Status.choices,
        'benefit_type_choices': Benefit.BenefitType.choices,
        'total_enrolled': total_enrolled,
        'active_count': active_count,
        'pending_count': pending_count,
        'total_benefits': total_benefits_count,
        'company_contribution_total': company_contribution_total,
        'employee_contribution_total': employee_contribution_total,
        'benefit_overview': benefit_overview,
        'can_manage_benefits': can_manage_benefits,
        'benefit_form': benefit_form,
        'enrollment_form': enrollment_form,
        'using_legacy_mode': using_legacy_mode,
        'base_template': base_template,
        'benefit_claims': benefit_claims,
        'is_management_view': _is_management_view,
    }
    return render(request, 'ems/benefits_list.html', context)


@login_required
@require_POST
def benefit_activation_toggle(request, enrollment_id):
    from blu_staff.apps.payroll.models import EmployeeBenefit

    enrollment = get_object_or_404(EmployeeBenefit, id=enrollment_id)

    if request.user.role == 'EMPLOYEE' and enrollment.employee != request.user:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    if request.user.role not in ['EMPLOYEE', 'EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    action = request.POST.get('action')
    valid_actions = {'activate', 'suspend', 'cancel'}
    if action not in valid_actions:
        return JsonResponse({'error': 'Invalid action'}, status=400)

    status_map = {
        'activate': EmployeeBenefit.Status.ACTIVE,
        'suspend': EmployeeBenefit.Status.SUSPENDED,
        'cancel': EmployeeBenefit.Status.CANCELLED,
    }

    enrollment.status = status_map[action]
    enrollment.save(update_fields=['status', 'updated_at'])

    return JsonResponse({'status': enrollment.get_status_display(), 'status_code': enrollment.status})


@login_required
@require_POST
def benefit_create(request):
    from blu_staff.apps.payroll.forms import BenefitForm

    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    company = getattr(request.user, 'company', None)
    tenant = getattr(company, 'tenant', None) if company else None

    if not tenant_metadata_available():
        return JsonResponse({'error': 'Tenant metadata missing; cannot create benefits in compatibility mode.'}, status=400)

    form = BenefitForm(request.POST)
    if form.is_valid():
        benefit = form.save(commit=False)
        if tenant:
            benefit.tenant = tenant
        benefit.save()
        return JsonResponse({
            'id': benefit.id,
            'name': benefit.name,
            'type': benefit.get_benefit_type_display(),
            'company_contribution': str(benefit.company_contribution),
            'employee_contribution': str(benefit.employee_contribution),
        })

    return JsonResponse({'errors': form.errors}, status=400)


@login_required
def knowledge_base(request):
    """Tenant/company-facing knowledge base listing published articles."""
    # Allow any authenticated tenant user; optionally could restrict further
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '').strip()
    page_number = request.GET.get('page', '1')

    articles = KnowledgeArticle.objects.filter(
        is_published=True,
        visibility=KnowledgeArticle.Visibility.TENANTS,
    )

    if category_filter:
        articles = articles.filter(category__iexact=category_filter)

    if search_query:
        articles = articles.filter(
            Q(title__icontains=search_query)
            | Q(summary__icontains=search_query)
            | Q(content__icontains=search_query)
        )

    articles = articles.order_by('-created_at')

    paginator = Paginator(articles, 9)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    categories = (
        KnowledgeArticle.objects.filter(is_published=True)
        .exclude(category="")
        .order_by('category')
        .values_list('category', flat=True)
        .distinct()
    )

    context = {
        'user': request.user,
        'articles': page_obj.object_list,
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
    }

    return render(request, 'ems/knowledge_base.html', context)


@login_required
def knowledge_article_detail(request, slug):
    article = get_object_or_404(
        KnowledgeArticle,
        slug=slug,
        is_published=True,
        visibility=KnowledgeArticle.Visibility.TENANTS,
    )

    context = {
        'user': request.user,
        'article': article,
    }

    return render(request, 'ems/knowledge_base_detail.html', context)


@login_required
def superadmin_knowledge_base(request):
    """System Owner Knowledge Base management page (no Django admin)."""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    # Filters
    search_query = request.GET.get('search', '').strip()
    visibility_filter = request.GET.get('visibility', '').strip()
    category_filter = request.GET.get('category', '').strip()

    articles = KnowledgeArticle.objects.all()

    if visibility_filter:
        articles = articles.filter(visibility=visibility_filter)

    if category_filter:
        articles = articles.filter(category__iexact=category_filter)

    if search_query:
        articles = articles.filter(
            Q(title__icontains=search_query)
            | Q(summary__icontains=search_query)
            | Q(content__icontains=search_query)
        )

    articles = articles.order_by('-updated_at')

    editing_article = None

    if request.method == 'POST':
        article_id = request.POST.get('article_id')
        if article_id:
            editing_article = get_object_or_404(KnowledgeArticle, pk=article_id)
            form = KnowledgeArticleForm(request.POST, request.FILES, instance=editing_article)
            action = 'updated'
        else:
            form = KnowledgeArticleForm(request.POST, request.FILES)
            action = 'created'

        if form.is_valid():
            article = form.save(commit=False)
            if not article.created_by_id:
                article.created_by = request.user
            article.save()
            messages.success(request, f'Knowledge Base article {action}.')
            return redirect('superadmin_knowledge_base')
        else:
            messages.error(request, 'Please correct the errors in the article form.')
    else:
        edit_id = request.GET.get('edit')
        if edit_id:
            editing_article = get_object_or_404(KnowledgeArticle, pk=edit_id)
            form = KnowledgeArticleForm(instance=editing_article)
        else:
            form = KnowledgeArticleForm()

    categories = (
        KnowledgeArticle.objects.all()
        .exclude(category="")
        .order_by('category')
        .values_list('category', flat=True)
        .distinct()
    )

    context = {
        'user': request.user,
        'form': form,
        'articles': articles,
        'editing_article': editing_article,
        'search_query': search_query,
        'visibility_filter': visibility_filter,
        'category_filter': category_filter,
        'categories': categories,
        'visibility_choices': KnowledgeArticle.Visibility.choices,
    }

    return render(request, 'ems/superadmin_knowledge_base.html', context)


@login_required
@require_POST
def superadmin_knowledge_base_delete(request, article_id):
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    article = get_object_or_404(KnowledgeArticle, pk=article_id)
    article.delete()
    messages.success(request, 'Knowledge Base article deleted.')
    return redirect('superadmin_knowledge_base')


@login_required
@require_POST
def benefit_enrollment_create(request):
    from blu_staff.apps.payroll.forms import BenefitEnrollmentForm
    from blu_staff.apps.payroll.models import EmployeeBenefit

    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    if not tenant_metadata_available():
        return JsonResponse({'error': 'Tenant metadata missing; cannot create enrollments in compatibility mode.'}, status=400)

    company = getattr(request.user, 'company', None)
    tenant = getattr(company, 'tenant', None) if company else None

    form = BenefitEnrollmentForm(request.POST, company=company, tenant=tenant)
    if form.is_valid():
        enrollment = form.save(commit=False)

        if company and enrollment.employee.company_id != company.id:
            form.add_error('employee', 'Selected employee is not part of your company.')
        else:
            if tenant:
                enrollment.tenant = tenant
            enrollment.save()
            enrollment.refresh_from_db()
            return JsonResponse({
                'id': enrollment.id,
                'employee': enrollment.employee.get_full_name(),
                'benefit': enrollment.benefit.name,
                'status': enrollment.get_status_display(),
            })

    return JsonResponse({'errors': form.errors}, status=400)


@login_required
@require_POST
def employee_benefit_self_enroll(request):
    """Allow an employee to request enrollment in an available benefit."""
    from blu_staff.apps.payroll.models import Benefit, EmployeeBenefit
    from django.utils import timezone

    if request.user.role != 'EMPLOYEE':
        messages.error(request, 'Only employees can self-enroll in benefits.')
        return redirect('benefits_list')

    benefit_id = request.POST.get('benefit_id')
    if not benefit_id:
        messages.error(request, 'No benefit selected.')
        return redirect('benefits_list')

    try:
        benefit = Benefit.objects.get(id=benefit_id, is_active=True)
    except Benefit.DoesNotExist:
        messages.error(request, 'Benefit not found or no longer available.')
        return redirect('benefits_list')

    already = EmployeeBenefit.objects.filter(employee=request.user, benefit=benefit).exclude(
        status=EmployeeBenefit.Status.CANCELLED
    ).exists()
    if already:
        messages.warning(request, f'You are already enrolled (or have a pending request) for "{benefit.name}".')
        return redirect('benefits_list')

    EmployeeBenefit.objects.create(
        employee=request.user,
        benefit=benefit,
        status=EmployeeBenefit.Status.PENDING,
        enrollment_date=timezone.now().date(),
        effective_date=timezone.now().date(),
    )
    messages.success(request, f'Enrollment request for "{benefit.name}" submitted. HR will review and activate it.')
    return redirect('benefits_list')


@login_required
def training_list(request):
    """List training programs and enrollments"""
    from blu_staff.apps.training.models import TrainingProgram, TrainingEnrollment, Certification
    from blu_staff.apps.training.forms import TrainingProgramForm, TrainingEnrollmentForm
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Count, Avg
    from datetime import date
    import csv
    from django.http import HttpResponse
    
    User = get_user_model()
    
    # Check if user is HR (employee with HR role)
    is_hr = (request.user.role == 'EMPLOYEE' and 
             hasattr(request.user, 'employee_profile') and 
             request.user.employee_profile.employee_role == 'HR')

    # Check if user wants personal view (from main menu)
    view_personal = request.GET.get('view') == 'personal'
    
    enrolled_program_ids = set()

    if request.user.role == 'EMPLOYEE' and (not is_hr or view_personal):
        # Regular employees see only their personal training
        enrollments = TrainingEnrollment.objects.filter(employee=request.user).select_related('program').order_by('-enrollment_date')
        programs = TrainingProgram.objects.filter(is_active=True)
        enrolled_program_ids = set(str(e.program_id) for e in enrollments)
        
        # Employee statistics
        total_enrollments = enrollments.count()
        completed_count = enrollments.filter(status=TrainingEnrollment.Status.COMPLETED).count()
        in_progress_count = enrollments.filter(status=TrainingEnrollment.Status.IN_PROGRESS).count()
        
        search_query = ''
        status_filter = ''
        program_type_filter = ''
        company = None
        
    elif request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] or is_hr:
        company = getattr(request.user, 'company', None)
        
        # Get all enrollments for statistics
        all_enrollments = TrainingEnrollment.objects.filter(employee__company=company)
        
        # Calculate statistics
        total_enrollments = all_enrollments.count()
        completed_count = all_enrollments.filter(status=TrainingEnrollment.Status.COMPLETED).count()
        in_progress_count = all_enrollments.filter(status=TrainingEnrollment.Status.IN_PROGRESS).count()
        
        enrollments = all_enrollments.select_related('employee', 'employee__employee_profile', 'program').order_by('-enrollment_date')
        programs = TrainingProgram.objects.filter(is_active=True)
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            enrollments = enrollments.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(program__title__icontains=search_query)
            )
        
        # Status filter
        status_filter = request.GET.get('status', '')
        if status_filter:
            enrollments = enrollments.filter(status=status_filter)
        
        # Program type filter
        program_type_filter = request.GET.get('program_type', '')
        if program_type_filter:
            enrollments = enrollments.filter(program__program_type=program_type_filter)
        
        # CSV Export
        if request.GET.get('format') == 'csv':
            filename = f"training_enrollments_{date.today().strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(response)
            
            writer.writerow([
                'Employee', 'Position', 'Program', 'Type', 
                'Enrollment Date', 'Start Date', 'Completion Date',
                'Duration (hours)', 'Status', 'Score', 'Cost'
            ])
            
            for enrollment in enrollments:
                writer.writerow([
                    enrollment.employee.get_full_name(),
                    enrollment.employee.employee_profile.job_title if hasattr(enrollment.employee, 'employee_profile') and enrollment.employee.employee_profile else 'N/A',
                    enrollment.program.title,
                    enrollment.program.get_program_type_display(),
                    enrollment.enrollment_date.strftime('%Y-%m-%d'),
                    enrollment.start_date.strftime('%Y-%m-%d') if enrollment.start_date else 'N/A',
                    enrollment.completion_date.strftime('%Y-%m-%d') if enrollment.completion_date else 'N/A',
                    enrollment.program.duration_hours,
                    enrollment.get_status_display(),
                    enrollment.score if enrollment.score else 'N/A',
                    enrollment.program.cost
                ])
            
            return response
    else:
        enrollments = TrainingEnrollment.objects.none()
        programs = TrainingProgram.objects.none()
        search_query = ''
        status_filter = ''
        program_type_filter = ''
        total_enrollments = 0
        completed_count = 0
        in_progress_count = 0
        company = None
    
    tenant_for_forms = getattr(company, 'tenant', None) if company else None
    can_manage_training = (
        request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
        and company is not None
        and tenant_metadata_available()
    )

    training_program_form = None
    training_enrollment_form = None
    if can_manage_training:
        training_program_form = TrainingProgramForm(company=company, tenant=tenant_for_forms)
        training_enrollment_form = TrainingEnrollmentForm(company=company, tenant=tenant_for_forms)

    if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        base_template = 'ems/base_employer.html'
    else:
        base_template = 'ems/base_employee.html'

    # Certifications
    try:
        certifications = Certification.objects.filter(employee=request.user) if request.user.role == 'EMPLOYEE' else Certification.objects.filter(employee__company=company) if company else Certification.objects.none()
        total_certifications = certifications.count()
    except Exception:
        certifications = []
        total_certifications = 0

    try:
        total_programs = programs.count()
    except Exception:
        total_programs = len(list(programs))

    context = {
        'enrollments': enrollments,
        'programs': programs,
        'certifications': certifications,
        'enrolled_program_ids': enrolled_program_ids,
        'user': request.user,
        'company': company,
        'search_query': search_query,
        'status_filter': status_filter,
        'program_type_filter': program_type_filter,
        'status_choices': TrainingEnrollment.Status.choices,
        'program_type_choices': TrainingProgram.ProgramType.choices,
        'total_enrollments': total_enrollments,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'total_certifications': total_certifications,
        'total_programs': total_programs,
        'can_manage_training': can_manage_training,
        'training_program_form': training_program_form,
        'training_enrollment_form': training_enrollment_form,
        'base_template': base_template,
    }
    context.update(_get_employer_nav_context(request.user))
    return render(request, 'ems/training_list.html', context)


@login_required
@require_POST
def training_program_create(request):
    from blu_staff.apps.training.forms import TrainingProgramForm

    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    company = getattr(request.user, 'company', None)
    if not company:
        return JsonResponse({'error': 'Company context is required.'}, status=400)

    tenant = getattr(company, 'tenant', None)
    if not tenant_metadata_available() or tenant is None:
        return JsonResponse({'error': 'Tenant metadata missing; cannot create training programs in compatibility mode.'}, status=400)

    form = TrainingProgramForm(request.POST, company=company, tenant=tenant)
    if form.is_valid():
        program = form.save(commit=False)
        program.tenant = tenant
        program.created_by = request.user
        program.save()
        return JsonResponse({
            'id': program.id,
            'title': program.title,
            'program_type': program.get_program_type_display(),
            'is_mandatory': program.is_mandatory,
        })

    return JsonResponse({'errors': form.errors}, status=400)


@login_required
@require_POST
def training_enrollment_create(request):
    from blu_staff.apps.training.forms import TrainingEnrollmentForm

    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    company = getattr(request.user, 'company', None)
    if not company:
        return JsonResponse({'error': 'Company context is required.'}, status=400)

    tenant = getattr(company, 'tenant', None)
    if not tenant_metadata_available() or tenant is None:
        return JsonResponse({'error': 'Tenant metadata missing; cannot create enrollments in compatibility mode.'}, status=400)

    form = TrainingEnrollmentForm(request.POST, company=company, tenant=tenant)
    if form.is_valid():
        enrollment = form.save(commit=False)
        if enrollment.employee.company_id != company.id:
            form.add_error('employee', 'Selected employee is not part of your company.')
        else:
            enrollment.tenant = tenant
            enrollment.save()
            enrollment.refresh_from_db()
            return JsonResponse({
                'id': enrollment.id,
                'employee': enrollment.employee.get_full_name(),
                'program': enrollment.program.title,
                'status': enrollment.get_status_display(),
            })

    return JsonResponse({'errors': form.errors}, status=400)


@login_required
@require_POST
def employee_training_self_enroll(request):
    """Allow an employee to self-enroll in an available training program."""
    from blu_staff.apps.training.models import TrainingProgram, TrainingEnrollment
    from django.utils import timezone

    if request.user.role != 'EMPLOYEE':
        messages.error(request, 'Only employees can self-enroll in training programs.')
        return redirect('training_list')

    program_id = request.POST.get('program_id')
    if not program_id:
        messages.error(request, 'No training program selected.')
        return redirect('training_list')

    try:
        program = TrainingProgram.objects.get(id=program_id, is_active=True)
    except TrainingProgram.DoesNotExist:
        messages.error(request, 'Training program not found or no longer available.')
        return redirect('training_list')

    already = TrainingEnrollment.objects.filter(
        employee=request.user, program=program
    ).exclude(status=TrainingEnrollment.Status.CANCELLED).exists()
    if already:
        messages.warning(request, f'You are already enrolled in "{program.title}".')
        return redirect('training_list')

    TrainingEnrollment.objects.create(
        employee=request.user,
        program=program,
        status=TrainingEnrollment.Status.ENROLLED,
        enrollment_date=timezone.now().date(),
    )
    messages.success(request, f'Successfully enrolled in "{program.title}".')
    return redirect('training_list')


@login_required
def finance_policy_settings(request):
    """HR/Admin view to configure company finance policy (advance %, petty cash limits, etc.)."""
    from blu_staff.apps.payroll.models import PayrollSettings

    is_accountant = (hasattr(request.user, 'employee_profile') and
                      request.user.employee_profile and
                      request.user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] and not is_accountant:
        return render(request, 'ems/unauthorized.html', status=403)

    company = getattr(request.user, 'company', None) or _get_user_company(request.user)
    policy = PayrollSettings.for_company(company)

    if request.method == 'POST':
        try:
            policy.advance_max_percentage = request.POST.get('advance_max_percentage', policy.advance_max_percentage)
            policy.max_petty_cash_amount = request.POST.get('max_petty_cash_amount', policy.max_petty_cash_amount)
            policy.max_reimbursement_amount = request.POST.get('max_reimbursement_amount', policy.max_reimbursement_amount)
            policy.advance_repayment_months = int(request.POST.get('advance_repayment_months', policy.advance_repayment_months))
            policy.overtime_rate_multiplier = request.POST.get('overtime_rate_multiplier', policy.overtime_rate_multiplier)
            if company:
                policy.company = company
            policy.save()
            messages.success(request, 'Finance policy updated successfully.')
        except Exception as e:
            messages.error(request, f'Error saving policy: {e}')
        return redirect('finance_policy_settings')

    base_template = 'ems/base_employee.html' if is_accountant else 'ems/base_employer.html'
    context = {
        'policy': policy,
        'company': company,
        'base_template': base_template,
    }
    if not is_accountant:
        context.update(_get_employer_nav_context(request.user))
    return render(request, 'ems/finance_policy_settings.html', context)


@login_required
def onboarding_list(request):
    """List onboarding and offboarding processes with statistics and filters"""
    from blu_staff.apps.onboarding.models import (
        EmployeeOnboarding, EmployeeOffboarding, 
        OnboardingTaskCompletion
    )
    from django.db.models import Q, Count, Avg
    import csv
    
    # Allow HR users to access
    is_hr = (request.user.role == 'EMPLOYEE' and 
             hasattr(request.user, 'employee_profile') and 
             request.user.employee_profile.employee_role == 'HR')
    
    if not (request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] or is_hr):
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(request.user, 'company', None)
    
    # Get query parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    process_type = request.GET.get('process_type', 'onboarding')  # onboarding or offboarding
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    export_csv = request.GET.get('export', '')
    
    # Base querysets
    if process_type == 'offboarding':
        # Offboarding process
        offboardings = EmployeeOffboarding.objects.filter(
            employee__company=company
        ).select_related('employee', 'employee__employer_profile', 'checklist')
        
        # Apply search
        if search_query:
            offboardings = offboardings.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__email__icontains=search_query) |
                Q(reason__icontains=search_query)
            )
        
        # Apply status filter
        if status_filter:
            offboardings = offboardings.filter(status=status_filter)
        
        # Apply date filters
        if date_from:
            offboardings = offboardings.filter(last_working_date__gte=date_from)
        if date_to:
            offboardings = offboardings.filter(last_working_date__lte=date_to)
        
        # Statistics for offboarding
        total_offboardings = offboardings.count()
        not_started_count = offboardings.filter(status='NOT_STARTED').count()
        in_progress_count = offboardings.filter(status='IN_PROGRESS').count()
        completed_count = offboardings.filter(status='COMPLETED').count()
        exit_interviews_completed = offboardings.filter(exit_interview_completed=True).count()
        
        # CSV Export
        if export_csv == 'true':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="offboarding.csv"'
            writer = csv.writer(response)
            writer.writerow(['Employee', 'Position', 'Last Working Date', 'Reason', 'Status', 
                           'Exit Interview', 'Checklist', 'Created Date'])
            
            for offboarding in offboardings:
                position = getattr(offboarding.employee.employer_profile, 'job_title', 'N/A') if hasattr(offboarding.employee, 'employer_profile') else 'N/A'
                writer.writerow([
                    offboarding.employee.get_full_name(),
                    position,
                    offboarding.last_working_date.strftime('%Y-%m-%d'),
                    offboarding.get_reason_display(),
                    offboarding.get_status_display(),
                    'Yes' if offboarding.exit_interview_completed else 'No',
                    offboarding.checklist.name if offboarding.checklist else 'N/A',
                    offboarding.created_at.strftime('%Y-%m-%d'),
                ])
            return response
        
        context = {
            'offboardings': offboardings,
            'total_offboardings': total_offboardings,
            'not_started_count': not_started_count,
            'in_progress_count': in_progress_count,
            'completed_count': completed_count,
            'exit_interviews_completed': exit_interviews_completed,
            'status_choices': EmployeeOffboarding.Status.choices,
            'reason_choices': EmployeeOffboarding.Reason.choices,
            'process_type': process_type,
            'search_query': search_query,
            'status_filter': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'user': request.user,
        }
    else:
        # Onboarding process (default)
        onboardings = EmployeeOnboarding.objects.filter(
            employee__company=company
        ).select_related('employee', 'employee__employer_profile', 'checklist', 'buddy')
        
        # Apply search
        if search_query:
            onboardings = onboardings.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__email__icontains=search_query)
            )
        
        # Apply status filter
        if status_filter:
            onboardings = onboardings.filter(status=status_filter)
        
        # Apply date filters
        if date_from:
            onboardings = onboardings.filter(start_date__gte=date_from)
        if date_to:
            onboardings = onboardings.filter(start_date__lte=date_to)
        
        # Statistics for onboarding
        total_onboardings = onboardings.count()
        not_started_count = onboardings.filter(status='NOT_STARTED').count()
        in_progress_count = onboardings.filter(status='IN_PROGRESS').count()
        completed_count = onboardings.filter(status='COMPLETED').count()
        on_hold_count = onboardings.filter(status='ON_HOLD').count()
        
        # Calculate average completion progress
        onboardings_with_tasks = []
        for onboarding in onboardings:
            total_tasks = OnboardingTaskCompletion.objects.filter(
                employee_onboarding=onboarding
            ).count()
            completed_tasks = OnboardingTaskCompletion.objects.filter(
                employee_onboarding=onboarding,
                status='COMPLETED'
            ).count()
            progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            onboardings_with_tasks.append({
                'onboarding': onboarding,
                'progress': progress,
                'completed_tasks': completed_tasks,
                'total_tasks': total_tasks
            })
        
        # CSV Export
        if export_csv == 'true':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="onboarding.csv"'
            writer = csv.writer(response)
            writer.writerow(['Employee', 'Position', 'Start Date', 'Expected Completion', 
                           'Actual Completion', 'Status', 'Buddy', 'Progress', 'Checklist'])
            
            for item in onboardings_with_tasks:
                onboarding = item['onboarding']
                position = getattr(onboarding.employee.employer_profile, 'job_title', 'N/A') if hasattr(onboarding.employee, 'employer_profile') else 'N/A'
                writer.writerow([
                    onboarding.employee.get_full_name(),
                    position,
                    onboarding.start_date.strftime('%Y-%m-%d'),
                    onboarding.expected_completion_date.strftime('%Y-%m-%d'),
                    onboarding.actual_completion_date.strftime('%Y-%m-%d') if onboarding.actual_completion_date else 'N/A',
                    onboarding.get_status_display(),
                    onboarding.buddy.get_full_name() if onboarding.buddy else 'N/A',
                    f"{item['progress']:.1f}%",
                    onboarding.checklist.name if onboarding.checklist else 'N/A',
                ])
            return response
        
        context = {
            'onboardings_with_tasks': onboardings_with_tasks,
            'total_onboardings': total_onboardings,
            'not_started_count': not_started_count,
            'in_progress_count': in_progress_count,
            'completed_count': completed_count,
            'on_hold_count': on_hold_count,
            'status_choices': EmployeeOnboarding.Status.choices,
            'process_type': process_type,
            'search_query': search_query,
            'status_filter': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'user': request.user,
        }
    
    can_manage_onboarding = (
        request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
        and company is not None
        and tenant_metadata_available()
    )
    if can_manage_onboarding:
        from blu_staff.apps.onboarding.forms import EmployeeOnboardingForm, EmployeeOffboardingForm

        tenant = getattr(company, 'tenant', None)
        onboarding_form = EmployeeOnboardingForm(company=company, tenant=tenant)
        offboarding_form = EmployeeOffboardingForm(company=company, tenant=tenant)
    else:
        onboarding_form = None
        offboarding_form = None

    context.update({
        'can_manage_onboarding': can_manage_onboarding,
        'onboarding_form': onboarding_form,
        'offboarding_form': offboarding_form,
    })
    context.update(_get_employer_nav_context(request.user))

    return render(request, 'ems/onboarding_list.html', context)


@login_required
@require_POST
def onboarding_create(request):
    from blu_staff.apps.onboarding.forms import EmployeeOnboardingForm
    from blu_staff.apps.onboarding.models import OnboardingTaskCompletion

    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    company = getattr(request.user, 'company', None)
    if not company:
        return JsonResponse({'error': 'Company context is required.'}, status=400)

    tenant = getattr(company, 'tenant', None)
    if not tenant_metadata_available() or tenant is None:
        return JsonResponse({'error': 'Tenant metadata missing; cannot start onboarding in compatibility mode.'}, status=400)

    form = EmployeeOnboardingForm(request.POST, company=company, tenant=tenant)
    if form.is_valid():
        onboarding = form.save(commit=False)
        if onboarding.employee.company_id != company.id:
            form.add_error('employee', 'Selected employee is not part of your company.')
        else:
            onboarding.tenant = tenant
            onboarding.status = onboarding.Status.NOT_STARTED
            onboarding.save()
            onboarding.refresh_from_db()

            checklist = onboarding.checklist
            if checklist:
                tasks = checklist.tasks.order_by('order')
                for task in tasks:
                    OnboardingTaskCompletion.objects.create(
                        tenant=tenant,
                        employee_onboarding=onboarding,
                        task=task,
                    )

            return JsonResponse({
                'id': onboarding.id,
                'employee': onboarding.employee.get_full_name(),
                'start_date': onboarding.start_date.strftime('%Y-%m-%d'),
                'status': onboarding.get_status_display(),
            })

    return JsonResponse({'errors': form.errors}, status=400)


@login_required
@require_POST
def offboarding_create(request):
    from blu_staff.apps.onboarding.forms import EmployeeOffboardingForm

    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    company = getattr(request.user, 'company', None)
    if not company:
        return JsonResponse({'error': 'Company context is required.'}, status=400)

    tenant = getattr(company, 'tenant', None)
    if not tenant_metadata_available() or tenant is None:
        return JsonResponse({'error': 'Tenant metadata missing; cannot start offboarding in compatibility mode.'}, status=400)

    form = EmployeeOffboardingForm(request.POST, company=company, tenant=tenant)
    if form.is_valid():
        offboarding = form.save(commit=False)
        if offboarding.employee.company_id != company.id:
            form.add_error('employee', 'Selected employee is not part of your company.')
        else:
            offboarding.tenant = tenant
            offboarding.status = offboarding.Status.NOT_STARTED
            offboarding.save()
            return JsonResponse({
                'id': offboarding.id,
                'employee': offboarding.employee.get_full_name(),
                'last_working_date': offboarding.last_working_date.strftime('%Y-%m-%d'),
                'status': offboarding.get_status_display(),
            })

    return JsonResponse({'errors': form.errors}, status=400)

@login_required
def employer_support_center(request):
    """Employer-facing support center scoped to the current company."""
    # Only employer admins and company administrators should access this view
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')

    # Resolve company from user or employer profile
    company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
    if not company:
        messages.error(request, 'Company not assigned. Please contact your system administrator.')
        return redirect('dashboard_redirect')

    # Base queryset: tickets for this company only
    base_qs = SupportTicket.objects.filter(company=company).select_related('created_by').order_by('-created_at')

    # Filters
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    search_query = request.GET.get('search', '').strip()

    tickets = base_qs
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    if search_query:
        tickets = tickets.filter(
            Q(subject__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(reference__icontains=search_query)
            | Q(created_by__email__icontains=search_query)
        )

    # Summary stats for this company
    total_tickets = base_qs.count()
    open_count = base_qs.filter(status=SupportTicket.Status.OPEN).count()
    in_progress_count = base_qs.filter(status=SupportTicket.Status.IN_PROGRESS).count()
    resolved_count = base_qs.filter(status=SupportTicket.Status.RESOLVED).count()
    closed_count = base_qs.filter(status=SupportTicket.Status.CLOSED).count()

    context = {
        'company': company,
        'tickets': tickets,
        'total_tickets': total_tickets,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'closed_count': closed_count,
        'status_choices': SupportTicket.Status.choices,
        'priority_choices': SupportTicket.Priority.choices,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search_query': search_query,
    }

    return render(request, 'ems/employer_support_center.html', context)


@login_required
def employer_support_ticket_create(request):
    """Create a new support ticket scoped to the current company."""
    role = (getattr(request.user, 'role', '') or '').upper()
    if role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')

    company = _get_user_company(request.user)
    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.company = company
            ticket.created_by = request.user
            if not ticket.contact_email:
                ticket.contact_email = getattr(request.user, 'email', '') or ''
            ticket.save()
            messages.success(request, 'Support ticket submitted successfully.')
            return redirect('employer_support_center')
    else:
        initial = {
            'priority': SupportTicket.Priority.NORMAL,
            'contact_email': getattr(request.user, 'email', ''),
        }
        form = SupportTicketForm(initial=initial)

    context = {
        'company': company,
        'form': form,
    }

    return render(request, 'ems/employer_support_ticket_form.html', context)


@login_required
def analytics_dashboard_view(request):
    """Comprehensive analytics dashboard with charts, reports, and export"""
    # Allow HR and Accountant users to access
    is_hr = (request.user.role == 'EMPLOYEE' and 
             hasattr(request.user, 'employee_profile') and 
             request.user.employee_profile.employee_role == 'HR')
    is_accountant = (request.user.role == 'EMPLOYEE' and 
                     hasattr(request.user, 'employee_profile') and 
                     request.user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    
    if not (request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] or is_hr or is_accountant):
        return render(request, 'ems/unauthorized.html')
    
    # Redirect accountants to their dedicated financial analytics page
    if is_accountant and not is_hr:
        return redirect('financial_analytics')
    
    from datetime import date, timedelta
    from blu_staff.apps.payroll.models import Payroll, EmployeeBenefit, PayrollDeduction
    from blu_staff.apps.training.models import TrainingEnrollment
    from blu_staff.apps.onboarding.models import EmployeeOnboarding, EmployeeOffboarding
    
    company = getattr(request.user, 'company', None)
    
    # Get filter parameters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    report_type = request.GET.get('report_type', 'overview')  # overview, attendance, performance, payroll
    export_csv = request.GET.get('export', '')
    
    # Default date range (last 30 days)
    today = date.today()
    if not date_from:
        date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')
    
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)
    
    employees = User.objects.filter(company=company, role=User.Role.EMPLOYEE) if company else User.objects.none()

    # Base querysets with date filters
    attendance_qs = Attendance.objects.filter(employee__company=company, date__range=[start_date, end_date])
    leave_qs = LeaveRequest.objects.filter(employee__company=company, created_at__date__range=[start_date, end_date])
    # PERFORMANCE MODULE DISABLED
    # review_qs = PerformanceReview.objects.filter(employee__company=company, review_date__range=[start_date, end_date])
    review_qs = []
    document_qs = EmployeeDocument.objects.filter(employee__company=company, created_at__date__range=[start_date, end_date])
    payroll_qs = Payroll.objects.filter(employee__company=company, period_start__range=[start_date, end_date])
    training_qs = TrainingEnrollment.objects.filter(employee__company=company, enrollment_date__range=[start_date, end_date])
    
    # All-time querysets for certain metrics
    all_onboardings = EmployeeOnboarding.objects.filter(employee__company=company)
    all_offboardings = EmployeeOffboarding.objects.filter(employee__company=company)
    all_benefits = EmployeeBenefit.objects.filter(employee__company=company)

    # ===== COMPREHENSIVE STATISTICS =====
    
    # Employee Statistics
    total_employees = employees.count()
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
    
    # Attendance Statistics
    total_attendance_records = attendance_qs.count()
    present_count = attendance_qs.filter(status__in=['PRESENT', 'LATE', 'HALF_DAY']).count()
    absent_count = attendance_qs.filter(status='ABSENT').count()
    attendance_rate = (present_count / total_attendance_records * 100) if total_attendance_records > 0 else 0
    
    # Leave Statistics
    total_leaves = leave_qs.count()
    pending_leaves = leave_qs.filter(status='PENDING').count()
    approved_leaves = leave_qs.filter(status='APPROVED').count()
    rejected_leaves = leave_qs.filter(status='REJECTED').count()
    
    # Performance Statistics (module disabled — stub zeros)
    total_reviews = 0
    avg_rating = 0
    completed_reviews = 0
    pending_reviews = 0
    
    # Document Statistics
    total_documents = document_qs.count()
    approved_documents = document_qs.filter(status='APPROVED').count()
    pending_documents = document_qs.filter(status='PENDING').count()
    rejected_documents = document_qs.filter(status='REJECTED').count()
    
    # Payroll Statistics
    total_payrolls = payroll_qs.count()
    total_gross_pay = payroll_qs.aggregate(total=Sum('gross_pay'))['total'] or 0
    total_net_pay = payroll_qs.aggregate(total=Sum('net_pay'))['total'] or 0
    paid_payrolls = payroll_qs.filter(status='PAID').count()
    
    # Training Statistics
    total_trainings = training_qs.count()
    completed_trainings = training_qs.filter(status='COMPLETED').count()
    in_progress_trainings = training_qs.filter(status='IN_PROGRESS').count()
    
    # Onboarding/Offboarding Statistics
    active_onboardings = all_onboardings.filter(status='IN_PROGRESS').count()
    completed_onboardings = all_onboardings.filter(status='COMPLETED').count()
    active_offboardings = all_offboardings.filter(status='IN_PROGRESS').count()
    
    # Benefits Statistics
    active_benefits = all_benefits.filter(status='ACTIVE').count()
    active_benefit_totals = all_benefits.filter(status='ACTIVE').aggregate(
        company_total=Sum('benefit__company_contribution'),
        employee_total=Sum('benefit__employee_contribution')
    )
    company_benefit_contribution = active_benefit_totals.get('company_total') or 0
    employee_benefit_contribution = active_benefit_totals.get('employee_total') or 0
    total_benefit_cost = company_benefit_contribution + employee_benefit_contribution

    # ===== TREND DATA (Date Range) =====
    date_labels = []
    attendance_trend = []
    absence_trend = []
    leave_trend = []
    
    days_diff = (end_date - start_date).days + 1
    step = max(1, days_diff // 14)  # Show max 14 data points
    
    for offset in range(0, days_diff, step):
        current_day = start_date + timedelta(days=offset)
        if current_day > end_date:
            break
        date_labels.append(current_day.strftime('%b %d'))
        attendance_trend.append(
            Attendance.objects.filter(
                employee__company=company,
                date=current_day, 
                status__in=['PRESENT', 'LATE', 'HALF_DAY']
            ).count()
        )
        absence_trend.append(
            Attendance.objects.filter(
                employee__company=company,
                date=current_day, 
                status='ABSENT'
            ).count()
        )
        leave_trend.append(
            LeaveRequest.objects.filter(
                employee__company=company,
                start_date__lte=current_day,
                end_date__gte=current_day,
                status='APPROVED'
            ).count()
        )

    # ===== DISTRIBUTION CHARTS =====
    
    # Leave Status Distribution
    leave_status_counts = leave_qs.values('status').annotate(count=Count('id')).order_by('status')
    leave_status_labels = []
    leave_status_data = []
    for entry in leave_status_counts:
        label = dict(LeaveRequest.Status.choices).get(entry['status'], entry['status'].title())
        leave_status_labels.append(str(label))
        leave_status_data.append(entry['count'])
    
    if not leave_status_labels:
        leave_status_labels = ['No Data']
        leave_status_data = [0]
    
    # Leave Type Distribution
    leave_type_counts = leave_qs.values('leave_type').annotate(count=Count('id')).order_by('-count')[:5]
    leave_type_labels = []
    leave_type_data = []
    for entry in leave_type_counts:
        label = dict(LeaveRequest.LeaveType.choices).get(entry['leave_type'], entry['leave_type'].title())
        leave_type_labels.append(str(label))
        leave_type_data.append(entry['count'])
    
    if not leave_type_labels:
        leave_type_labels = ['No Data']
        leave_type_data = [0]
    
    # Performance Rating Distribution
    rating_distribution = review_qs.values('overall_rating').annotate(count=Count('id')).order_by('overall_rating')
    rating_labels = []
    rating_data = []
    for entry in rating_distribution:
        label = dict(PerformanceReview.OverallRating.choices).get(entry['overall_rating'], 'N/A')
        rating_labels.append(str(label))
        rating_data.append(entry['count'])
    
    if not rating_labels:
        rating_labels = ['No Data']
        rating_data = [0]
    
    # Training Status Distribution
    training_status_counts = training_qs.values('status').annotate(count=Count('id')).order_by('status')
    training_status_labels = [entry['status'].replace('_', ' ').title() for entry in training_status_counts]
    training_status_data = [entry['count'] for entry in training_status_counts]
    
    if not training_status_labels:
        training_status_labels = ['No Data']
        training_status_data = [0]

    # ===== RECENT ACTIVITY FEED =====
    activity_feed = []
    
    for leave in leave_qs.order_by('-created_at')[:5]:
        activity_feed.append({
            'type': 'leave',
            'title': f"Leave request - {leave.employee.get_full_name()}",
            'description': f"{leave.get_leave_type_display()} • {leave.start_date:%b %d} - {leave.end_date:%b %d}",
            'timestamp': leave.created_at,
            'status': leave.get_status_display(),
        })
    
    for review in review_qs.order_by('-review_date')[:5]:
        activity_feed.append({
            'type': 'review',
            'title': f"Performance review - {review.employee.get_full_name()}",
            'description': f"{review.get_review_type_display()} • {review.review_date:%b %d, %Y}",
            'timestamp': review.review_date,
            'status': review.get_status_display(),
        })
    
    for doc in document_qs.order_by('-created_at')[:5]:
        activity_feed.append({
            'type': 'document',
            'title': f"Document - {doc.title}",
            'description': doc.employee.get_full_name() if doc.employee else '—',
            'timestamp': doc.created_at,
            'status': doc.get_status_display(),
        })
    
    for training in training_qs.order_by('-enrollment_date')[:5]:
        activity_feed.append({
            'type': 'training',
            'title': f"Training - {training.employee.get_full_name()}",
            'description': training.program.title if training.program else 'N/A',
            'timestamp': training.enrollment_date,
            'status': training.get_status_display(),
        })
    
    activity_feed = sorted(activity_feed, key=lambda item: item['timestamp'], reverse=True)[:12]

    # ===== CSV EXPORT =====
    if export_csv == 'true':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="analytics_report_{start_date}_{end_date}.csv"'
        writer = csv.writer(response)
        
        # Write summary statistics
        writer.writerow(['Analytics Report', f'{start_date} to {end_date}'])
        writer.writerow([])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Employees', total_employees])
        writer.writerow(['Attendance Rate', f'{attendance_rate:.1f}%'])
        writer.writerow(['Total Attendance Records', total_attendance_records])
        writer.writerow(['Present Count', present_count])
        writer.writerow(['Absent Count', absent_count])
        writer.writerow(['Total Leave Requests', total_leaves])
        writer.writerow(['Pending Leaves', pending_leaves])
        writer.writerow(['Approved Leaves', approved_leaves])
        writer.writerow(['Total Performance Reviews', total_reviews])
        writer.writerow(['Average Rating', f'{avg_rating:.2f}'])
        writer.writerow(['Completed Reviews', completed_reviews])
        writer.writerow(['Total Documents', total_documents])
        writer.writerow(['Total Payrolls', total_payrolls])
        writer.writerow(['Total Gross Pay', f'{total_gross_pay:.2f}'])
        writer.writerow(['Total Net Pay', f'{total_net_pay:.2f}'])
        writer.writerow(['Total Training Enrollments', total_trainings])
        writer.writerow(['Completed Trainings', completed_trainings])
        writer.writerow(['Active Onboardings', active_onboardings])
        writer.writerow(['Active Benefits', active_benefits])
        writer.writerow([])
        
        # Write trend data
        writer.writerow(['Date', 'Present', 'Absent', 'On Leave'])
        for i, label in enumerate(date_labels):
            writer.writerow([
                label,
                attendance_trend[i] if i < len(attendance_trend) else 0,
                absence_trend[i] if i < len(absence_trend) else 0,
                leave_trend[i] if i < len(leave_trend) else 0
            ])
        
        return response

    context = {
        'company': company,
        'date_from': date_from,
        'date_to': date_to,
        'report_type': report_type,
        
        # Summary Statistics
        'total_employees': total_employees,
        'present_today': present_today,
        'absent_today': absent_today,
        'attendance_rate': round(attendance_rate, 1),
        
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        
        'total_reviews': total_reviews,
        'avg_rating': round(avg_rating, 1),
        'completed_reviews': completed_reviews,
        
        'total_documents': total_documents,
        'pending_documents': pending_documents,
        'approved_documents': approved_documents,
        
        'total_payrolls': total_payrolls,
        'total_gross_pay': total_gross_pay,
        'total_net_pay': total_net_pay,
        'paid_payrolls': paid_payrolls,
        
        'total_trainings': total_trainings,
        'completed_trainings': completed_trainings,
        'in_progress_trainings': in_progress_trainings,
        
        'active_onboardings': active_onboardings,
        'active_offboardings': active_offboardings,
        
        'active_benefits': active_benefits,
        'total_benefit_cost': total_benefit_cost,
        'company_benefit_contribution': company_benefit_contribution,
        'employee_benefit_contribution': employee_benefit_contribution,
        
        # Chart Data
        'attendance_trend_labels': json.dumps(date_labels),
        'attendance_trend_present': json.dumps(attendance_trend),
        'attendance_trend_absent': json.dumps(absence_trend),
        'leave_trend_data': json.dumps(leave_trend),
        
        'leave_status_labels': json.dumps(leave_status_labels),
        'leave_status_data': json.dumps(leave_status_data),
        
        'leave_type_labels': json.dumps(leave_type_labels),
        'leave_type_data': json.dumps(leave_type_data),
        
        'rating_labels': json.dumps(rating_labels),
        'rating_data': json.dumps(rating_data),
        
        'training_status_labels': json.dumps(training_status_labels),
        'training_status_data': json.dumps(training_status_data),
        
        'activity_feed': activity_feed,
        'base_template': 'ems/base_employee.html' if request.user.role == 'EMPLOYEE' else 'ems/base_employer.html',
    }
    return render(request, 'ems/analytics_employer.html', context)


@login_required
def notifications_list(request):
    """Enhanced notifications list with filters, statistics, and actions"""
    from blu_staff.apps.notifications.models import Notification
    from django.db.models import Q, Count
    from django.utils import timezone
    import csv
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')  # all, read, unread
    export_csv = request.GET.get('export', '')
    
    # Base queryset
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender').order_by('-created_at')
    
    # Apply search filter
    if search_query:
        notifications = notifications.filter(
            Q(title__icontains=search_query) |
            Q(message__icontains=search_query) |
            Q(sender__first_name__icontains=search_query) |
            Q(sender__last_name__icontains=search_query)
        )
    
    # Apply category filter
    if category_filter:
        notifications = notifications.filter(category=category_filter)
    
    # Apply type filter
    if type_filter:
        notifications = notifications.filter(notification_type=type_filter)
    
    # Apply status filter
    if status_filter == 'read':
        notifications = notifications.filter(is_read=True)
    elif status_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    
    # Statistics
    total_notifications = Notification.objects.filter(recipient=request.user).count()
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    read_count = Notification.objects.filter(recipient=request.user, is_read=True).count()
    
    # Category breakdown
    category_counts = Notification.objects.filter(
        recipient=request.user
    ).values('category').annotate(count=Count('id')).order_by('-count')
    
    # Type breakdown
    type_counts = Notification.objects.filter(
        recipient=request.user
    ).values('notification_type').annotate(count=Count('id')).order_by('-count')
    
    # Recent unread (for quick actions)
    recent_unread = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # CSV Export
    if export_csv == 'true':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="notifications.csv"'
        writer = csv.writer(response)
        writer.writerow(['Date', 'Title', 'Message', 'Category', 'Type', 'Status', 'Sender'])
        
        for notification in notifications:
            writer.writerow([
                notification.created_at.strftime('%Y-%m-%d %H:%M'),
                notification.title,
                notification.message,
                notification.get_category_display(),
                notification.get_notification_type_display(),
                'Read' if notification.is_read else 'Unread',
                notification.sender.get_full_name() if notification.sender else 'System',
            ])
        return response
    
    # Limit for display
    notifications = notifications[:200]
    
    base_template = 'ems/base_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/base_employee.html'
    context = {
        'notifications': notifications,
        'total_notifications': total_notifications,
        'unread_count': unread_count,
        'read_count': read_count,
        'category_counts': category_counts,
        'type_counts': type_counts,
        'recent_unread': recent_unread,
        'category_choices': Notification.Category.choices,
        'type_choices': Notification.NotificationType.choices,
        'search_query': search_query,
        'category_filter': category_filter,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'user': request.user,
        'base_template': base_template,
    }
    return render(request, 'ems/notifications_list.html', context)


@login_required
def notification_mark_read(request, notification_id):
    """Mark a single notification as read"""
    from blu_staff.apps.notifications.models import Notification
    
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )
            notification.mark_as_read()
            return JsonResponse({'success': True, 'message': 'Notification marked as read'})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Notification not found'}, status=404)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


@login_required
def notification_mark_all_read(request):
    """Mark all notifications as read"""
    from blu_staff.apps.notifications.models import Notification
    from django.utils import timezone
    
    if request.method == 'POST':
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return JsonResponse({
            'success': True,
            'message': f'{count} notification(s) marked as read',
            'count': count
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


@login_required
def notification_delete(request, notification_id):
    """Delete a notification"""
    from blu_staff.apps.notifications.models import Notification
    
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )
            notification.delete()
            return JsonResponse({'success': True, 'message': 'Notification deleted'})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Notification not found'}, status=404)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


@login_required
def system_health(request):
    """System health monitoring dashboard for System Superadmin"""
    if not request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')
    from blu_staff.apps.accounts.models import Company, User
    from blu_staff.apps.attendance.models import Attendance, LeaveRequest
    from blu_staff.apps.documents.models import EmployeeDocument
    from datetime import date, timedelta

    today = date.today()

    # System statistics
    total_companies = Company.objects.count()
    total_users = User.objects.count()
    total_employees = User.objects.filter(role='EMPLOYEE').count()

    # Database statistics
    db_stats = {
        'total_companies': total_companies,
        'total_users': total_users,
        'total_employees': total_employees,
        'total_attendance_records': Attendance.objects.count(),
        'total_leave_requests': LeaveRequest.objects.count(),
        'total_documents': EmployeeDocument.objects.count(),
        # PERFORMANCE MODULE DISABLED
        # 'total_reviews': PerformanceReview.objects.count(),
        'total_reviews': 0,
    }

    # System performance metrics - get real data where possible
    system_metrics = {
        'cpu_usage': 0,
        'memory_usage': 0,
        'disk_usage': 0,
        'uptime_days': 0,
        'response_time_ms': 120,
        'error_rate': 0.01,
        'active_sessions': 0,
        'database_connections': 0,
    }

    # Try to get real system metrics using psutil
    try:
        import psutil
        system_metrics['cpu_usage'] = round(psutil.cpu_percent(interval=1), 1)
        system_metrics['memory_usage'] = round(psutil.virtual_memory().percent, 1)
        system_metrics['disk_usage'] = round(psutil.disk_usage('/').percent, 1)
        system_metrics['active_sessions'] = User.objects.filter(is_active=True).count()
    except ImportError:
        # Use default values if psutil is not available
        system_metrics['cpu_usage'] = 0
        system_metrics['memory_usage'] = 0
        system_metrics['disk_usage'] = 0
    except Exception:
        pass  # Keep default mock values if psutil fails

    # Recent system events — built from real DB activity
    recent_events = []
    try:
        for company_obj in Company.objects.order_by('-created_at')[:2]:
            recent_events.append({
                'timestamp': company_obj.created_at,
                'event_type': 'COMPANY_CREATED',
                'message': f'Company registered: {company_obj.name}',
                'status': 'INFO',
            })
    except Exception:
        pass
    try:
        for u in User.objects.order_by('-date_joined')[:3]:
            recent_events.append({
                'timestamp': u.date_joined,
                'event_type': 'USER_CREATED',
                'message': f'New user account: {u.get_full_name() or u.email} ({u.role})',
                'status': 'SUCCESS',
            })
    except Exception:
        pass
    try:
        for doc in EmployeeDocument.objects.order_by('-created_at')[:2]:
            recent_events.append({
                'timestamp': doc.created_at,
                'event_type': 'DOCUMENT_UPLOADED',
                'message': f'Document uploaded: {doc.title or doc.document_type}',
                'status': 'INFO',
            })
    except Exception:
        pass
    recent_events = sorted(recent_events, key=lambda x: x['timestamp'], reverse=True)[:8]

    # API / module health — derived from real DB query timing
    import time as _time
    def _check(label, fn):
        try:
            t0 = _time.monotonic()
            fn()
            ms = round((_time.monotonic() - t0) * 1000)
            return {'endpoint': label, 'status': 'HEALTHY', 'response_time': ms}
        except Exception:
            return {'endpoint': label, 'status': 'ERROR', 'response_time': 0}

    api_status = [
        _check('Users / Auth',    lambda: User.objects.count()),
        _check('Attendance',      lambda: Attendance.objects.count()),
        _check('Leave Requests',  lambda: LeaveRequest.objects.count()),
        _check('Documents',       lambda: EmployeeDocument.objects.count()),
        _check('Companies',       lambda: Company.objects.count()),
    ]

    context = {
        'user': request.user,
        'db_stats': db_stats,
        'system_metrics': system_metrics,
        'recent_events': recent_events,
        'api_status': api_status,
        'today_date': today.strftime('%Y-%m-%d'),
    }

    return render(request, 'ems/system_health.html', context)


# ============================================================================
# BRANCH MANAGEMENT VIEWS
# ============================================================================

@login_required
def branch_management(request):
    """Branch management dashboard"""
    from blu_staff.apps.accounts.models import CompanyBranch

    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')

    try:
        company = request.user.company
    except Exception:
        return render(request, 'ems/unauthorized.html')

    if request.method == 'POST' and request.POST.get('action') == 'export_branches':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{company.name}_branches.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Code', 'City', 'Country', 'Phone', 'Email', 'Manager', 'Employees'])
        for b in CompanyBranch.objects.filter(company=company).select_related('manager'):
            writer.writerow([
                b.name,
                getattr(b, 'code', ''),
                getattr(b, 'city', ''),
                getattr(b, 'country', ''),
                getattr(b, 'phone', ''),
                getattr(b, 'email', ''),
                b.manager.get_full_name() if b.manager else '',
                b.employees.count() if hasattr(b, 'employees') else '',
            ])
        return response

    branches = CompanyBranch.objects.filter(company=company).select_related('manager')

    context = {
        'company': company,
        'branches': branches,
    }
    context.update(_get_employer_nav_context(request.user))

    return render(request, 'ems/branch_management.html', context)


@login_required
def branch_create(request):
    """Create new branch"""
    from blu_staff.apps.accounts.models import CompanyBranch
    from django.contrib import messages
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = request.user.company
    except:
        return render(request, 'ems/unauthorized.html')
    
    if request.method == 'POST':
        try:
            branch = CompanyBranch.objects.create(
                company=company,
                name=request.POST.get('name'),
                code=request.POST.get('code'),
                address=request.POST.get('address'),
                city=request.POST.get('city'),
                state_province=request.POST.get('state_province', ''),
                country=request.POST.get('country', 'Zambia'),
                postal_code=request.POST.get('postal_code', ''),
                phone=request.POST.get('phone', ''),
                email=request.POST.get('email', ''),
                is_head_office=request.POST.get('is_head_office') == 'on',
                is_active=True,
            )
            
            # Set manager if provided
            manager_id = request.POST.get('manager')
            if manager_id:
                branch.manager_id = manager_id
                branch.save()
            
            messages.success(request, f'Branch "{branch.name}" created successfully!')
            return redirect('branch_management')
        except Exception as e:
            messages.error(request, f'Error creating branch: {str(e)}')
    
    # Get potential managers (admins/employers)
    managers = User.objects.filter(
        company=company,
        role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
    )
    
    context = {
        'company': company,
        'managers': managers,
    }
    context.update(_get_employer_nav_context(request.user))
    
    return render(request, 'ems/branch_form.html', context)


@login_required
def branch_edit(request, branch_id):
    """Edit branch"""
    from blu_staff.apps.accounts.models import CompanyBranch
    from django.contrib import messages
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = request.user.company
        branch = CompanyBranch.objects.get(id=branch_id, company=company)
    except:
        messages.error(request, 'Branch not found')
        return redirect('branch_management')
    
    if request.method == 'POST':
        try:
            branch.name = request.POST.get('name')
            branch.code = request.POST.get('code')
            branch.address = request.POST.get('address')
            branch.city = request.POST.get('city')
            branch.state_province = request.POST.get('state_province', '')
            branch.country = request.POST.get('country', 'Zambia')
            branch.postal_code = request.POST.get('postal_code', '')
            branch.phone = request.POST.get('phone', '')
            branch.email = request.POST.get('email', '')
            branch.is_head_office = request.POST.get('is_head_office') == 'on'
            branch.is_active = request.POST.get('is_active') == 'on'
            
            # Set manager
            manager_id = request.POST.get('manager')
            if manager_id:
                branch.manager_id = manager_id
            else:
                branch.manager = None
            
            branch.save()
            
            messages.success(request, f'Branch "{branch.name}" updated successfully!')
            return redirect('branch_management')
        except Exception as e:
            messages.error(request, f'Error updating branch: {str(e)}')
    
    # Get potential managers
    managers = User.objects.filter(
        company=company,
        role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
    )
    
    context = {
        'company': company,
        'branch': branch,
        'managers': managers,
        'is_edit': True,
    }
    
    return render(request, 'ems/branch_form.html', context)


@login_required
def branch_detail(request, branch_id):
    """Branch detail view with employees"""
    from blu_staff.apps.accounts.models import CompanyBranch
    from django.contrib import messages

    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')

    try:
        company = request.user.company
        branch = CompanyBranch.objects.get(id=branch_id, company=company)
    except Exception:
        messages.error(request, 'Branch not found')
        return redirect('branch_management')

    # ── POST handlers ────────────────────────────────────────────────
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'change_manager':
            manager_id = request.POST.get('manager_id', '').strip()
            if manager_id:
                try:
                    new_manager = User.objects.get(id=manager_id, company=company)
                    branch.manager = new_manager
                    branch.save(update_fields=['manager'])
                    messages.success(request, f'Branch manager changed to {new_manager.get_full_name()}.')
                except User.DoesNotExist:
                    messages.error(request, 'Selected user not found.')
            else:
                branch.manager = None
                branch.save(update_fields=['manager'])
                messages.success(request, 'Branch manager cleared.')
            return redirect('branch_detail', branch_id=branch_id)

        if action == 'assign_employee':
            emp_id = request.POST.get('employee_id', '').strip()
            if emp_id:
                try:
                    from blu_staff.apps.accounts.models import EmployeeProfile
                    ep = EmployeeProfile.objects.get(user_id=emp_id, company=company)
                    ep.branch = branch
                    ep.save(update_fields=['branch'])
                    messages.success(request, f'{ep.user.get_full_name()} assigned to {branch.name}.')
                except EmployeeProfile.DoesNotExist:
                    messages.error(request, 'Employee profile not found.')
            return redirect('branch_detail', branch_id=branch_id)

        if action == 'export_employees':
            import csv
            from django.http import HttpResponse
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{branch.name}_employees.csv"'
            writer = csv.writer(response)
            writer.writerow(['Employee ID', 'Full Name', 'Email', 'Job Title', 'Department', 'Date Hired'])
            from blu_staff.apps.accounts.models import EmployeeProfile
            for ep in EmployeeProfile.objects.filter(branch=branch, company=company).select_related('user'):
                writer.writerow([
                    ep.employee_id,
                    ep.user.get_full_name(),
                    ep.user.email,
                    ep.job_title,
                    ep.department,
                    ep.date_hired,
                ])
            return response

    # Get employees in this branch
    employees = User.objects.filter(
        company=company,
        employee_profile__branch=branch,
        role='EMPLOYEE'
    ).select_related('employee_profile')

    # All company employees for assign-employee dropdown
    all_employees = User.objects.filter(
        company=company, role='EMPLOYEE', is_active=True
    ).select_related('employee_profile').order_by('first_name', 'last_name')

    # All company admins/managers for manager dropdown
    all_managers = User.objects.filter(
        company=company,
        role__in=['EMPLOYEE', 'EMPLOYER_ADMIN', 'ADMINISTRATOR'],
        is_active=True,
    ).order_by('first_name', 'last_name')

    # Get departments in this branch
    from blu_staff.apps.accounts.models import EnhancedDepartment
    departments = EnhancedDepartment.objects.filter(
        company=company,
        branch=branch
    ).select_related('head')

    context = {
        'company': company,
        'branch': branch,
        'employees': employees,
        'all_employees': all_employees,
        'all_managers': all_managers,
        'departments': departments,
        'employee_count': employees.count(),
        'department_count': departments.count(),
        'settings_url': _safe_reverse('blu_settings_home'),
    }

    return render(request, 'ems/branch_detail.html', context)


# ============================================================================
# FINANCIAL ANALYTICS VIEW (Accountant-focused)
# ============================================================================

@login_required
def financial_analytics_view(request):
    """Financial analytics dashboard for Accountants — payroll costs, tax, benefits, expenses"""
    from blu_staff.apps.payroll.models import Payroll, EmployeeBenefit
    from blu_staff.apps.requests.models import EmployeeRequest, PettyCashRequest
    from django.db.models import Sum, Count, Avg, Q, DecimalField
    from django.db.models.functions import Coalesce, TruncMonth
    from datetime import date, timedelta
    from decimal import Decimal
    import json
    
    user = request.user
    is_accountant = (hasattr(user, 'employee_profile') and 
                     user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    is_admin = user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']
    
    if not (is_accountant or is_admin):
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(user, 'company', None) or getattr(getattr(user, 'employer_profile', None), 'company', None)
    today = date.today()
    
    # Date range filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if not date_from:
        date_from = (today - timedelta(days=180)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)
    
    employees = User.objects.filter(company=company, role=User.Role.EMPLOYEE) if company else User.objects.none()
    total_employees = employees.count()
    on_payroll_count = employees.filter(employee_profile__on_payroll=True).count()
    
    # ===== PAYROLL ANALYTICS =====
    payroll_qs = Payroll.objects.filter(
        employee__company=company,
        period_end__range=[start_date, end_date]
    )
    
    total_payrolls = payroll_qs.count()
    paid_payrolls = payroll_qs.filter(status=Payroll.Status.PAID).count()
    pending_payrolls = payroll_qs.filter(status=Payroll.Status.DRAFT).count()
    
    payroll_totals = payroll_qs.filter(status=Payroll.Status.PAID).aggregate(
        total_gross=Coalesce(Sum('gross_pay'), Decimal('0'), output_field=DecimalField()),
        total_net=Coalesce(Sum('net_pay'), Decimal('0'), output_field=DecimalField()),
        total_tax=Coalesce(Sum('tax'), Decimal('0'), output_field=DecimalField()),
        total_base=Coalesce(Sum('base_pay'), Decimal('0'), output_field=DecimalField()),
        total_overtime=Coalesce(Sum('overtime_pay'), Decimal('0'), output_field=DecimalField()),
        total_bonus=Coalesce(Sum('bonus'), Decimal('0'), output_field=DecimalField()),
        total_deductions=Coalesce(Sum('total_deductions'), Decimal('0'), output_field=DecimalField()),
        total_social_security=Coalesce(Sum('social_security'), Decimal('0'), output_field=DecimalField()),
        avg_net=Coalesce(Avg('net_pay'), Decimal('0'), output_field=DecimalField()),
    )
    
    total_gross_pay = payroll_totals['total_gross']
    total_net_pay = payroll_totals['total_net']
    total_tax = payroll_totals['total_tax']
    total_deductions = payroll_totals['total_deductions']
    total_social_security = payroll_totals['total_social_security']
    total_base_pay = payroll_totals['total_base']
    total_overtime = payroll_totals['total_overtime']
    total_bonus = payroll_totals['total_bonus']
    avg_net_pay = payroll_totals['avg_net']
    
    # Monthly payroll trend
    monthly_payroll = payroll_qs.filter(status=Payroll.Status.PAID).annotate(
        month=TruncMonth('period_end')
    ).values('month').annotate(
        gross=Coalesce(Sum('gross_pay'), Decimal('0'), output_field=DecimalField()),
        net=Coalesce(Sum('net_pay'), Decimal('0'), output_field=DecimalField()),
        tax=Coalesce(Sum('tax'), Decimal('0'), output_field=DecimalField()),
    ).order_by('month')
    
    payroll_trend_labels = []
    payroll_trend_gross = []
    payroll_trend_net = []
    payroll_trend_tax = []
    for entry in monthly_payroll:
        payroll_trend_labels.append(entry['month'].strftime('%b %Y'))
        payroll_trend_gross.append(float(entry['gross']))
        payroll_trend_net.append(float(entry['net']))
        payroll_trend_tax.append(float(entry['tax']))
    
    # ===== BENEFITS ANALYTICS =====
    active_benefits = 0
    total_benefit_cost = Decimal('0')
    company_benefit_contribution = Decimal('0')
    employee_benefit_contribution = Decimal('0')
    try:
        benefits_qs = EmployeeBenefit.objects.filter(
            employee__company=company,
            status='ACTIVE'
        )
        active_benefits = benefits_qs.count()
        benefit_totals = benefits_qs.aggregate(
            company_total=Coalesce(Sum('benefit__company_contribution'), Decimal('0'), output_field=DecimalField()),
            employee_total=Coalesce(Sum('benefit__employee_contribution'), Decimal('0'), output_field=DecimalField()),
        )
        company_benefit_contribution = benefit_totals['company_total']
        employee_benefit_contribution = benefit_totals['employee_total']
        total_benefit_cost = company_benefit_contribution + employee_benefit_contribution
    except Exception:
        pass
    
    # ===== PETTY CASH / EXPENSE ANALYTICS =====
    petty_cash_total = Decimal('0')
    petty_cash_approved = 0
    petty_cash_pending = 0
    try:
        tenant = getattr(request, 'tenant', None)
        pc_qs = PettyCashRequest.objects.filter(
            employee_request__employee__company=company,
            employee_request__created_at__date__range=[start_date, end_date]
        )
        petty_cash_approved = pc_qs.filter(employee_request__status='APPROVED').count()
        petty_cash_pending = pc_qs.filter(employee_request__status='PENDING').count()
        petty_cash_total = pc_qs.filter(employee_request__status='APPROVED').aggregate(
            total=Coalesce(Sum('employee_request__amount'), Decimal('0'), output_field=DecimalField())
        )['total']
    except Exception:
        pass
    
    # ===== DEDUCTION BREAKDOWN =====
    from blu_staff.apps.payroll.models import PayrollSettings as _PS
    _psettings = _PS.for_company(company)
    paye_label = _psettings.paye_label or 'PAYE'
    napsa_label = _psettings.napsa_label or 'NAPSA'
    nhima_label = _psettings.nhima_label or 'NHIMA'
    other_deductions = float(total_deductions - total_tax - total_social_security) if total_deductions > total_tax + total_social_security else 0
    deduction_data = {
        paye_label: float(total_tax),
        napsa_label: float(total_social_security),
        'Other Deductions': other_deductions,
    }
    deduction_labels = list(deduction_data.keys())
    deduction_values = list(deduction_data.values())
    
    # ===== COMPENSATION BREAKDOWN (for pie chart) =====
    compensation_data = {
        'Base Pay': float(total_base_pay),
        'Overtime': float(total_overtime),
        'Bonuses': float(total_bonus),
    }
    compensation_labels = list(compensation_data.keys())
    compensation_values = list(compensation_data.values())
    
    # ===== TOTAL COMPANY COST =====
    total_company_cost = total_gross_pay + company_benefit_contribution + petty_cash_total
    
    # ===== CSV EXPORT =====
    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="financial_summary_{start_date}_{end_date}.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Financial Summary Report', f'{start_date} to {end_date}'])
        writer.writerow([])
        writer.writerow(['PAYROLL SUMMARY'])
        writer.writerow(['Metric', 'Value (ZMW)'])
        writer.writerow(['Employees on Payroll', on_payroll_count])
        writer.writerow(['Payroll Runs (Paid)', paid_payrolls])
        writer.writerow(['Total Gross Pay', f'{total_gross_pay:.2f}'])
        writer.writerow(['Total Net Pay', f'{total_net_pay:.2f}'])
        writer.writerow(['Total Base Pay', f'{total_base_pay:.2f}'])
        writer.writerow(['Total Overtime', f'{total_overtime:.2f}'])
        writer.writerow(['Total Bonuses', f'{total_bonus:.2f}'])
        writer.writerow(['Average Net Pay', f'{avg_net_pay:.2f}'])
        writer.writerow([])
        writer.writerow(['TAX & STATUTORY DEDUCTIONS'])
        writer.writerow(['PAYE (Income Tax)', f'{total_tax:.2f}'])
        writer.writerow(['NAPSA (Social Security)', f'{total_social_security:.2f}'])
        writer.writerow(['Total Deductions', f'{total_deductions:.2f}'])
        writer.writerow([])
        writer.writerow(['BENEFITS'])
        writer.writerow(['Active Enrollments', active_benefits])
        writer.writerow(['Company Contribution', f'{company_benefit_contribution:.2f}'])
        writer.writerow(['Employee Contribution', f'{employee_benefit_contribution:.2f}'])
        writer.writerow(['Total Benefit Cost', f'{total_benefit_cost:.2f}'])
        writer.writerow([])
        writer.writerow(['PETTY CASH / EXPENSES'])
        writer.writerow(['Approved Requests', petty_cash_approved])
        writer.writerow(['Pending Requests', petty_cash_pending])
        writer.writerow(['Total Approved Amount', f'{petty_cash_total:.2f}'])
        writer.writerow([])
        writer.writerow(['TOTAL COMPANY COST', f'{total_company_cost:.2f}'])
        return response
    
    base_template = 'ems/base_employee.html' if user.role == 'EMPLOYEE' else 'ems/base_employer.html'
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'total_employees': total_employees,
        'on_payroll_count': on_payroll_count,
        # Payroll
        'total_payrolls': total_payrolls,
        'paid_payrolls': paid_payrolls,
        'pending_payrolls': pending_payrolls,
        'total_gross_pay': total_gross_pay,
        'total_net_pay': total_net_pay,
        'total_tax': total_tax,
        'total_deductions': total_deductions,
        'total_social_security': total_social_security,
        'total_base_pay': total_base_pay,
        'total_overtime': total_overtime,
        'total_bonus': total_bonus,
        'avg_net_pay': avg_net_pay,
        # Payroll trend chart
        'payroll_trend_labels': json.dumps(payroll_trend_labels),
        'payroll_trend_gross': json.dumps(payroll_trend_gross),
        'payroll_trend_net': json.dumps(payroll_trend_net),
        'payroll_trend_tax': json.dumps(payroll_trend_tax),
        # Benefits
        'active_benefits': active_benefits,
        'total_benefit_cost': total_benefit_cost,
        'company_benefit_contribution': company_benefit_contribution,
        'employee_benefit_contribution': employee_benefit_contribution,
        # Petty Cash / Expenses
        'petty_cash_total': petty_cash_total,
        'petty_cash_approved': petty_cash_approved,
        'petty_cash_pending': petty_cash_pending,
        # Deduction labels (localised per company)
        'paye_label': paye_label,
        'napsa_label': napsa_label,
        'nhima_label': nhima_label,
        # Deductions chart
        'deduction_labels': json.dumps(deduction_labels),
        'deduction_values': json.dumps(deduction_values),
        # Compensation chart
        'compensation_labels': json.dumps(compensation_labels),
        'compensation_values': json.dumps(compensation_values),
        # Total
        'total_company_cost': total_company_cost,
        'base_template': base_template,
    }
    return render(request, 'ems/financial_analytics.html', context)


# ============================================================================
# FINANCIAL ASSETS VIEW (Accountant - view only)
# ============================================================================

@login_required
def financial_assets_view(request):
    """Read-only asset register for Accountants — financial tracking, valuation, depreciation"""
    from blu_assets.models import EmployeeAsset
    from django.db.models import Sum, Count, Q, F, Value, DecimalField
    from django.db.models.functions import Coalesce
    from datetime import date
    
    user = request.user
    is_accountant = (hasattr(user, 'employee_profile') and 
                     user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    is_admin = user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']
    
    if not (is_accountant or is_admin):
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(user, 'company', None)
    today = date.today()
    
    assets = EmployeeAsset.objects.filter(
        Q(department__company=company) | Q(employee__company=company)
    ).select_related('employee', 'department', 'category').order_by('-purchase_date', '-created_at')
    
    # Financial summary
    total_assets = assets.count()
    total_purchase_value = assets.aggregate(
        total=Coalesce(Sum('purchase_price'), 0, output_field=DecimalField())
    )['total']
    assigned_count = assets.filter(status='ASSIGNED').count()
    available_count = assets.filter(status='AVAILABLE').count()
    in_repair_count = assets.filter(status='IN_REPAIR').count()
    retired_count = assets.filter(status='RETIRED').count()
    lost_count = assets.filter(status='LOST').count()
    
    # Value by asset type
    value_by_type = assets.values('asset_type').annotate(
        count=Count('id'),
        total_value=Coalesce(Sum('purchase_price'), 0, output_field=DecimalField())
    ).order_by('-total_value')
    
    # Value by status
    value_by_status = assets.values('status').annotate(
        count=Count('id'),
        total_value=Coalesce(Sum('purchase_price'), 0, output_field=DecimalField())
    ).order_by('-total_value')
    
    # Warranty expiring soon (next 90 days)
    from datetime import timedelta
    warranty_expiring = assets.filter(
        warranty_expiry__gte=today,
        warranty_expiry__lte=today + timedelta(days=90)
    ).order_by('warranty_expiry')
    
    # Filters
    search_query = request.GET.get('search', '')
    type_filter = request.GET.get('asset_type', '')
    status_filter = request.GET.get('status', '')
    
    filtered = assets
    if search_query:
        filtered = filtered.filter(
            Q(name__icontains=search_query) |
            Q(asset_tag__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(brand__icontains=search_query)
        )
    if type_filter:
        filtered = filtered.filter(asset_type=type_filter)
    if status_filter:
        filtered = filtered.filter(status=status_filter)
    
    # CSV export
    if request.GET.get('format') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="asset_register_{today}.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Asset Tag', 'Name', 'Type', 'Brand', 'Model', 'Serial #', 'Status', 'Condition',
                         'Purchase Date', 'Purchase Price', 'Warranty Expiry', 'Assigned To', 'Department'])
        for a in filtered:
            writer.writerow([
                a.asset_tag, a.name, a.get_asset_type_display(), a.brand, a.model, a.serial_number,
                a.get_status_display(), a.get_condition_display(),
                a.purchase_date.strftime('%Y-%m-%d') if a.purchase_date else '',
                f'{a.purchase_price:.2f}' if a.purchase_price else '',
                a.warranty_expiry.strftime('%Y-%m-%d') if a.warranty_expiry else '',
                a.employee.get_full_name() if a.employee else '',
                a.department.name if a.department else '',
            ])
        return response
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(filtered, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    base_template = 'ems/base_employee.html' if user.role == 'EMPLOYEE' else 'ems/base_employer.html'
    
    context = {
        'assets': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_assets': total_assets,
        'total_purchase_value': total_purchase_value,
        'assigned_count': assigned_count,
        'available_count': available_count,
        'in_repair_count': in_repair_count,
        'retired_count': retired_count,
        'lost_count': lost_count,
        'value_by_type': value_by_type,
        'value_by_status': value_by_status,
        'warranty_expiring': warranty_expiring,
        'search_query': search_query,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'asset_types': EmployeeAsset.AssetType.choices,
        'status_choices': EmployeeAsset.Status.choices,
        'base_template': base_template,
        'today': today,
    }
    return render(request, 'ems/financial_assets.html', context)


# ============================================================================
# PETTY CASH MANAGEMENT VIEWS
# ============================================================================

@login_required
def petty_cash_dashboard(request):
    """Petty Cash management dashboard for Accountants/Finance"""
    from blu_staff.apps.requests.models import EmployeeRequest, RequestType, PettyCashRequest
    from django.db.models import Sum, Count, Q
    
    user = request.user
    is_accountant = (hasattr(user, 'employee_profile') and 
                     user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    is_admin = user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']
    is_hr = (hasattr(user, 'employee_profile') and 
             user.employee_profile.employee_role == 'HR')
    
    if not (is_accountant or is_admin or is_hr):
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(user, 'company', None)
    
    # Get petty cash request type
    tenant = getattr(request, 'tenant', None)
    petty_cash_type = RequestType.objects.filter(
        code__icontains='PETTY',
        tenant=tenant
    ).first()
    if not petty_cash_type:
        petty_cash_type = RequestType.objects.filter(
            name__icontains='petty cash',
            tenant=tenant
        ).first()
    
    # Get all petty cash requests
    if petty_cash_type:
        petty_cash_requests = EmployeeRequest.objects.filter(
            request_type=petty_cash_type,
            employee__company=company,
        ).select_related('employee', 'employee__employee_profile').order_by('-created_at')
    else:
        petty_cash_requests = EmployeeRequest.objects.none()
    
    # Statistics
    total_requests = petty_cash_requests.count()
    pending_requests = petty_cash_requests.filter(status='PENDING').count()
    approved_requests = petty_cash_requests.filter(status='APPROVED').count()
    total_amount = petty_cash_requests.filter(
        status__in=['APPROVED', 'COMPLETED']
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Filters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    filtered_requests = petty_cash_requests
    if status_filter:
        filtered_requests = filtered_requests.filter(status=status_filter)
    if search_query:
        filtered_requests = filtered_requests.filter(
            Q(employee__first_name__icontains=search_query) |
            Q(employee__last_name__icontains=search_query) |
            Q(request_number__icontains=search_query) |
            Q(title__icontains=search_query)
        )
    if date_from:
        filtered_requests = filtered_requests.filter(request_date__date__gte=date_from)
    if date_to:
        filtered_requests = filtered_requests.filter(request_date__date__lte=date_to)
    
    # Handle POST for approve/reject
    if request.method == 'POST':
        action = request.POST.get('action')
        request_id = request.POST.get('request_id')
        if action and request_id:
            try:
                emp_request = EmployeeRequest.objects.get(id=request_id, employee__company=company)
                if action == 'approve':
                    emp_request.status = 'APPROVED'
                    emp_request.save()
                    messages.success(request, f'Request {emp_request.request_number} approved.')
                elif action == 'reject':
                    emp_request.status = 'REJECTED'
                    emp_request.save()
                    messages.success(request, f'Request {emp_request.request_number} rejected.')
                elif action == 'disburse':
                    emp_request.status = 'COMPLETED'
                    emp_request.save()
                    # Update petty cash details if exists
                    if hasattr(emp_request, 'petty_cash_details'):
                        pc = emp_request.petty_cash_details
                        pc.disbursed = True
                        pc.disbursed_by = user
                        pc.disbursed_date = timezone.now()
                        pc.disbursed_amount = emp_request.amount
                        pc.save()
                    messages.success(request, f'Request {emp_request.request_number} marked as disbursed.')
            except EmployeeRequest.DoesNotExist:
                messages.error(request, 'Request not found.')
            return redirect('petty_cash_dashboard')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(filtered_requests, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    base_template = 'ems/base_employee.html' if user.role == 'EMPLOYEE' else 'ems/base_employer.html'
    
    context = {
        'petty_cash_requests': page_obj,
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'total_amount': total_amount,
        'status_filter': status_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'page_obj': page_obj,
        'paginator': paginator,
        'base_template': base_template,
        'is_accountant': is_accountant,
        'is_admin': is_admin,
        'status_choices': EmployeeRequest.Status.choices,
    }
    
    return render(request, 'ems/petty_cash_dashboard.html', context)


# ============================================================================
# REQUEST MANAGEMENT VIEWS
# ============================================================================

@login_required
def employee_requests_list(request):
    """Employee's request list"""
    from blu_staff.apps.requests.models import EmployeeRequest
    
    # Get employee's requests
    my_requests = EmployeeRequest.objects.filter(
        employee=request.user
    ).select_related('request_type').order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        my_requests = my_requests.filter(status=status_filter)
    
    # Calculate statistics
    all_requests = EmployeeRequest.objects.filter(employee=request.user)
    pending_count = all_requests.filter(status='PENDING').count()
    approved_count = all_requests.filter(status='APPROVED').count()
    rejected_count = all_requests.filter(status='REJECTED').count()
    
    context = {
        'requests': my_requests,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    context.update(_get_employer_nav_context(request.user))
    
    return render(request, 'ems/employee_requests_list.html', context)


@login_required
def employee_request_create(request):
    """Create new request"""
    from blu_staff.apps.requests.models import EmployeeRequest, RequestType
    from django.contrib import messages
    
    if request.method == 'POST':
        try:
            request_type = RequestType.objects.get(id=request.POST.get('request_type'))
            
            # Get department from employee profile
            try:
                department = request.user.employee_profile.department
            except:
                department = ''
            
            employee_request = EmployeeRequest.objects.create(
                request_type=request_type,
                employee=request.user,
                department=department,
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                amount=request.POST.get('amount') if request.POST.get('amount') else None,
                currency=request.POST.get('currency', 'ZMW'),
                priority=request.POST.get('priority', 'MEDIUM'),
                required_by=request.POST.get('required_by') if request.POST.get('required_by') else None,
                status='PENDING',
            )
            
            # Handle attachment
            if request.FILES.get('attachment'):
                employee_request.attachment = request.FILES['attachment']
                employee_request.save()
            
            # Create specific request details based on type
            if request_type.code == 'PETTY_CASH':
                from blu_staff.apps.requests.models import PettyCashRequest
                PettyCashRequest.objects.create(
                    request=employee_request,
                    purpose=request.POST.get('purpose', ''),
                    expense_category=request.POST.get('expense_category', ''),
                    payment_method=request.POST.get('payment_method', 'CASH'),
                )
            elif request_type.code == 'ADVANCE':
                from blu_staff.apps.requests.models import AdvanceRequest
                AdvanceRequest.objects.create(
                    request=employee_request,
                    reason=request.POST.get('reason', ''),
                    repayment_plan=request.POST.get('repayment_plan', ''),
                    installments=int(request.POST.get('installments', 1)),
                )
            elif request_type.code == 'REIMBURSEMENT':
                from blu_staff.apps.requests.models import ReimbursementRequest
                ReimbursementRequest.objects.create(
                    request=employee_request,
                    expense_date=request.POST.get('expense_date'),
                    expense_category=request.POST.get('expense_category', ''),
                    vendor_name=request.POST.get('vendor_name', ''),
                )
            
            messages.success(request, f'Request "{employee_request.title}" submitted successfully!')
            return redirect('employee_requests_list')
        except Exception as e:
            messages.error(request, f'Error creating request: {str(e)}')
    
    # Get active request types
    request_types = RequestType.objects.filter(is_active=True)
    
    # Get employee salary and calculate max advance
    employee_salary = 0
    max_advance_amount = 0
    advance_percentage = 40.0  # Default
    
    try:
        from blu_staff.apps.payroll.models import PayrollSettings
        _company = getattr(request.user, 'company', None)
        payroll_settings = PayrollSettings.for_company(_company)
        advance_percentage = float(payroll_settings.advance_max_percentage or 40.0)
    except Exception:
        pass
    
    try:
        employee_profile = request.user.employee_profile
        if employee_profile and employee_profile.salary:
            employee_salary = float(employee_profile.salary)
            max_advance_amount = (employee_salary * advance_percentage) / 100
    except:
        pass
    
    # Currency symbol
    currency_symbol = 'ZMW'
    currency_code = 'ZMW'
    advance_repayment_months = 3
    try:
        from blu_staff.apps.payroll.models import PayrollSettings
        _company = getattr(request.user, 'company', None)
        _ps = PayrollSettings.for_company(_company)
        advance_repayment_months = int(_ps.advance_repayment_months or 3)
        if _company and hasattr(_company, 'currency_code'):
            currency_code = _company.currency_code or 'ZMW'
    except Exception:
        pass
    _currency_map = {
        'ZMW': 'ZMW', 'MWK': 'MWK', 'KES': 'KSh', 'TZS': 'TSh',
        'UGX': 'USh', 'ZAR': 'R', 'NGN': '₦', 'GHS': 'GH₵',
        'USD': '$', 'GBP': '£', 'EUR': '€',
    }
    currency_symbol = _currency_map.get(currency_code, currency_code)

    context = {
        'request_types': request_types,
        'employee_salary': employee_salary,
        'max_advance_amount': max_advance_amount,
        'advance_percentage': advance_percentage,
        'advance_repayment_months': advance_repayment_months,
        'currency_symbol': currency_symbol,
        'currency_code': currency_code,
    }
    
    return render(request, 'ems/employee_request_form.html', context)


@login_required
def employee_request_detail(request, request_id):
    """View request detail"""
    from blu_staff.apps.requests.models import EmployeeRequest
    from django.contrib import messages
    
    try:
        employee_request = EmployeeRequest.objects.get(id=request_id)
        
        # Check permission
        if request.user.role == 'EMPLOYEE' and employee_request.employee != request.user:
            return render(request, 'ems/unauthorized.html')
    except:
        messages.error(request, 'Request not found')
        return redirect('employee_requests_list')
    
    # Get approvals
    approvals = employee_request.approvals.all().select_related('approver').order_by('approval_level')
    
    # Get comments
    comments = employee_request.comments.all().select_related('user').order_by('-created_at')
    
    # Get specific request details
    specific_details = None
    if hasattr(employee_request, 'petty_cash_details'):
        specific_details = employee_request.petty_cash_details
        specific_type = 'petty_cash'
    elif hasattr(employee_request, 'advance_details'):
        specific_details = employee_request.advance_details
        specific_type = 'advance'
    elif hasattr(employee_request, 'reimbursement_details'):
        specific_details = employee_request.reimbursement_details
        specific_type = 'reimbursement'
    else:
        specific_type = 'general'
    
    # Determine base template based on user role
    if request.user.role == 'EMPLOYEE':
        base_template = 'ems/base_employee.html'
    else:
        base_template = 'ems/base_employer.html'
    
    context = {
        'request': employee_request,
        'approvals': approvals,
        'comments': comments,
        'specific_details': specific_details,
        'specific_type': specific_type,
        'base_template': base_template,
    }
    
    return render(request, 'ems/employee_request_detail.html', context)


@login_required
def employee_request_edit(request, request_id):
    """Edit employee request (only if pending)"""  
    from blu_staff.apps.requests.models import EmployeeRequest
    from django.contrib import messages
    
    try:
        employee_request = EmployeeRequest.objects.get(id=request_id)
        
        # Check permission - only owner can edit and only if pending
        if employee_request.employee != request.user:
            messages.error(request, 'You do not have permission to edit this request')
            return redirect('employee_requests_list')
        
        if employee_request.status != 'PENDING':
            messages.error(request, 'Only pending requests can be edited')
            return redirect('employee_request_detail', request_id=request_id)
    except:
        messages.error(request, 'Request not found')
        return redirect('employee_requests_list')
    
    if request.method == 'POST':
        try:
            # Update basic fields
            employee_request.title = request.POST.get('title')
            employee_request.description = request.POST.get('description')
            employee_request.amount = request.POST.get('amount') if request.POST.get('amount') else None
            employee_request.currency = request.POST.get('currency', 'ZMW')
            employee_request.priority = request.POST.get('priority', 'MEDIUM')
            employee_request.required_by = request.POST.get('required_by') if request.POST.get('required_by') else None
            
            # Handle attachment
            if request.FILES.get('attachment'):
                employee_request.attachment = request.FILES['attachment']
            
            employee_request.save()
            
            messages.success(request, 'Request updated successfully!')
            return redirect('employee_request_detail', request_id=request_id)
        except Exception as e:
            messages.error(request, f'Error updating request: {str(e)}')
    
    context = {
        'request': employee_request,
    }
    
    return render(request, 'ems/employee_request_edit.html', context)


@login_required
def requests_approval_center(request):
    """Request approval center for supervisors/HR/finance"""
    from blu_staff.apps.requests.models import EmployeeRequest, RequestApproval
    
    # Check if user has approval rights
    has_approval_rights = False
    
    if request.user.role == 'EMPLOYEE':
        try:
            profile = request.user.employee_profile
            if profile.employee_role in ['SUPERVISOR', 'HR', 'ACCOUNTANT', 'ACCOUNTS']:
                has_approval_rights = True
        except:
            pass
    elif request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        has_approval_rights = True
    
    if not has_approval_rights:
        return render(request, 'ems/unauthorized.html')
    
    # Get pending requests where user is approver
    pending_approvals = RequestApproval.objects.filter(
        approver=request.user,
        action='PENDING'
    ).select_related('request', 'request__employee', 'request__request_type').order_by('-assigned_date')
    
    # Get all pending requests in company (for HR/Admin)
    if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or \
       (hasattr(request.user, 'employee_profile') and request.user.employee_profile.employee_role == 'HR'):
        all_pending = EmployeeRequest.objects.filter(
            employee__company=request.user.company,
            status='PENDING'
        ).select_related('employee', 'request_type').order_by('-created_at')
    else:
        all_pending = []
    
    context = {
        'pending_approvals': pending_approvals,
        'all_pending': all_pending,
    }
    context.update(_get_employer_nav_context(request.user))
    
    return render(request, 'ems/requests_approval_center.html', context)


@login_required
def request_approve_reject(request, request_id):
    """Approve or reject request"""
    from blu_staff.apps.requests.models import EmployeeRequest, RequestApproval
    from django.contrib import messages
    
    if request.method != 'POST':
        return redirect('requests_approval_center')
    
    try:
        employee_request = EmployeeRequest.objects.get(id=request_id)
        action = request.POST.get('action')  # 'approve' or 'reject'
        comments = request.POST.get('comments', '')
        
        # Find approval record
        approval = RequestApproval.objects.filter(
            request=employee_request,
            approver=request.user,
            action='PENDING'
        ).first()
        
        if not approval:
            messages.error(request, 'No pending approval found for this request')
            return redirect('requests_approval_center')
        
        # Update approval
        if action == 'approve':
            approval.action = 'APPROVED'
            approval.comments = comments
            approval.action_date = timezone.now()
            approval.save()
            
            # Check if all approvals completed
            all_approvals = employee_request.approvals.all()
            if all(a.action == 'APPROVED' for a in all_approvals):
                employee_request.status = 'APPROVED'
                employee_request.save()
                messages.success(request, 'Request approved successfully!')
            else:
                messages.success(request, 'Request approved at your level!')
        
        elif action == 'reject':
            approval.action = 'REJECTED'
            approval.comments = comments
            approval.action_date = timezone.now()
            approval.save()
            
            # Reject the entire request
            employee_request.status = 'REJECTED'
            employee_request.save()
            
            messages.success(request, 'Request rejected!')
        
        return redirect('requests_approval_center')
    except Exception as e:
        messages.error(request, f'Error processing request: {str(e)}')
        return redirect('requests_approval_center')


# ============================================================================
# COMMUNICATION VIEWS
# ============================================================================

@login_required
def chat_groups_list(request):
    """List chat groups"""
    from blu_staff.apps.communication.models import ChatGroup
    
    if request.user.role not in ['EMPLOYEE', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return render(request, 'ems/unauthorized.html')
    
    # Get groups user is member of
    my_groups = ChatGroup.objects.filter(
        members=request.user,
        is_active=True
    ).select_related('company', 'created_by').order_by('-last_activity')
    
    # Get available groups user can join
    available_groups = ChatGroup.objects.filter(
        company=request.user.company,
        is_private=False,
        is_active=True
    ).exclude(members=request.user)
    
    base_template = 'ems/base_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/base_employee.html'
    context = {
        'my_groups': my_groups,
        'available_groups': available_groups,
        'base_template': base_template,
    }
    
    return render(request, 'ems/chat_groups_list.html', context)


@login_required
def chat_group_detail(request, group_id):
    """Chat group conversation view"""
    from blu_staff.apps.communication.models import ChatGroup, GroupMessage, GroupMessageRead
    from django.contrib import messages as django_messages
    
    try:
        group = ChatGroup.objects.get(id=group_id, company=request.user.company)
        
        # Check if user is member
        if request.user not in group.members.all():
            django_messages.error(request, 'You are not a member of this group')
            return redirect('chat_groups_list')
    except:
        django_messages.error(request, 'Group not found')
        return redirect('chat_groups_list')
    
    # Handle new message
    if request.method == 'POST':
        try:
            message_content = request.POST.get('message')
            if message_content:
                message = GroupMessage.objects.create(
                    group=group,
                    sender=request.user,
                    content=message_content,
                    message_type='TEXT'
                )
                
                # Handle attachment
                if request.FILES.get('attachment'):
                    message.attachment = request.FILES['attachment']
                    message.message_type = 'FILE'
                    message.save()
                
                # Update group last activity
                group.last_activity = timezone.now()
                group.save()
                
                return redirect('chat_group_detail', group_id=group_id)
        except Exception as e:
            django_messages.error(request, f'Error sending message: {str(e)}')
    
    # Get messages
    messages = GroupMessage.objects.filter(
        group=group,
        is_deleted=False
    ).select_related('sender').order_by('-created_at')[:50]
    messages = list(reversed(messages))
    
    # Mark as read
    GroupMessageRead.objects.update_or_create(
        user=request.user,
        group=group,
        defaults={'last_read_at': timezone.now()}
    )
    
    base_template = 'ems/base_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/base_employee.html'
    context = {
        'group': group,
        'messages': messages,
        'is_admin': request.user in group.admins.all(),
        'base_template': base_template,
    }
    
    return render(request, 'ems/chat_group_detail.html', context)


@login_required
def direct_messages_list(request):
    """List direct message conversations"""
    from blu_staff.apps.communication.models import DirectMessage
    from django.db.models import Q, Max
    
    if request.user.role not in ['EMPLOYEE', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return render(request, 'ems/unauthorized.html')
    
    # Get unique conversations
    conversations = DirectMessage.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).values(
        'sender', 'recipient'
    ).annotate(
        last_message_time=Max('created_at')
    ).order_by('-last_message_time')
    
    # Build conversation list
    conversation_list = []
    seen_users = set()
    
    for conv in conversations:
        if conv['sender'] == request.user.id:
            other_user_id = conv['recipient']
        else:
            other_user_id = conv['sender']
        
        if other_user_id not in seen_users:
            seen_users.add(other_user_id)
            try:
                other_user = User.objects.get(id=other_user_id)
                
                # Get last message
                last_msg = DirectMessage.objects.filter(
                    Q(sender=request.user, recipient=other_user) |
                    Q(sender=other_user, recipient=request.user)
                ).order_by('-created_at').first()
                
                # Count unread
                unread_count = DirectMessage.objects.filter(
                    sender=other_user,
                    recipient=request.user,
                    is_read=False
                ).count()
                
                conversation_list.append({
                    'user': other_user,
                    'last_message': last_msg,
                    'unread_count': unread_count,
                })
            except:
                continue
    
    # Get all employees/colleagues for new conversation
    colleagues = User.objects.filter(
        company=request.user.company,
        is_active=True,
        role='EMPLOYEE'
    ).exclude(id=request.user.id).select_related('employee_profile').order_by('first_name', 'last_name')
    
    base_template = 'ems/base_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/base_employee.html'
    context = {
        'conversations': conversation_list,
        'colleagues': colleagues,
        'base_template': base_template,
    }
    
    return render(request, 'ems/direct_messages_list.html', context)


@login_required
def direct_message_conversation(request, user_id):
    """Direct message conversation with specific user"""
    from django.db.models import Count, Avg, Q, Sum
    from django.urls import reverse
    from django.contrib import messages as django_messages
    from blu_staff.apps.communication.models import DirectMessage
    
    try:
        other_user = User.objects.get(id=user_id, company=request.user.company)
    except:
        django_messages.error(request, 'User not found')
        return redirect('direct_messages_list')
    
    # Handle new message
    if request.method == 'POST':
        try:
            message_content = request.POST.get('message')
            if message_content:
                message = DirectMessage.objects.create(
                    sender=request.user,
                    recipient=other_user,
                    content=message_content
                )
                
                # Handle attachment
                if request.FILES.get('attachment'):
                    message.attachment = request.FILES['attachment']
                    message.save()
                
                return redirect('direct_message_conversation', user_id=user_id)
        except Exception as e:
            django_messages.error(request, f'Error sending message: {str(e)}')
    
    # Get messages between users
    messages = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=other_user) |
        Q(sender=other_user, recipient=request.user)
    ).select_related('sender', 'recipient').order_by('-created_at')[:50]
    messages = list(reversed(messages))
    
    # Mark received messages as read
    DirectMessage.objects.filter(
        sender=other_user,
        recipient=request.user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    
    base_template = 'ems/base_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/base_employee.html'
    context = {
        'other_user': other_user,
        'messages': messages,
        'base_template': base_template,
    }
    
    return render(request, 'ems/direct_message_conversation.html', context)


@login_required
def announcements_list(request):
    """List announcements"""
    from blu_staff.apps.communication.models import Announcement, AnnouncementRead
    
    # Get active announcements for user
    announcements = Announcement.objects.filter(
        company=request.user.company,
        is_published=True
    ).select_related('published_by').order_by('-published_at')
    
    # Filter based on audience
    user_announcements = []
    for announcement in announcements:
        if announcement.is_active():
            target_users = announcement.get_target_users()
            if request.user in target_users:
                # Check if read
                read_record = AnnouncementRead.objects.filter(
                    announcement=announcement,
                    user=request.user
                ).first()
                
                announcement.is_read = read_record is not None
                announcement.is_acknowledged = read_record.acknowledged if read_record else False
                user_announcements.append(announcement)
    
    unread_count = sum(1 for a in user_announcements if not a.is_read)
    base_template = 'ems/base_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/base_employee.html'
    context = {
        'announcements': user_announcements,
        'unread_count': unread_count,
        'base_template': base_template,
    }
    
    return render(request, 'ems/announcements_list.html', context)


@login_required
def announcement_detail(request, announcement_id):
    """View announcement detail"""
    from blu_staff.apps.communication.models import Announcement, AnnouncementRead
    from django.contrib import messages as django_messages
    
    try:
        announcement = Announcement.objects.get(
            id=announcement_id,
            company=request.user.company,
            is_published=True
        )
    except:
        django_messages.error(request, 'Announcement not found')
        return redirect('announcements_list')
    
    # Mark as read
    read_record, created = AnnouncementRead.objects.get_or_create(
        announcement=announcement,
        user=request.user
    )
    
    # Handle acknowledgment
    if request.method == 'POST' and announcement.requires_acknowledgment:
        if request.POST.get('acknowledge') == 'yes':
            read_record.acknowledged = True
            read_record.acknowledged_at = timezone.now()
            read_record.save()
            django_messages.success(request, 'Announcement acknowledged!')
            return redirect('announcements_list')
    
    base_template = 'ems/base_employer.html' if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] else 'ems/base_employee.html'
    context = {
        'announcement': announcement,
        'read_record': read_record,
        'base_template': base_template,
    }
    
    return render(request, 'ems/announcement_detail.html', context)


# ============================================================================
# SUPERVISOR FEATURES (Phase 4)
# ============================================================================

@login_required
def supervisor_dashboard(request):
    """My Team Dashboard - Overview of supervised employees"""
    # Check if user is a supervisor
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'SUPERVISOR':
            messages.error(request, 'Access denied. Supervisor role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Get team members (employees supervised by this user)
    team_members = User.objects.filter(
        employee_profile__supervisor=request.user,
        company=request.user.company
    ).select_related('employee_profile').order_by('first_name', 'last_name')
    
    # Team statistics
    total_team_members = team_members.count()
    
    # Today's attendance
    today = timezone.now().date()
    present_today = Attendance.objects.filter(
        employee__in=team_members,
        date=today,
        status='PRESENT'
    ).count()
    
    # Pending requests from team
    from blu_staff.apps.requests.models import EmployeeRequest
    pending_requests = EmployeeRequest.objects.filter(
        employee__in=team_members,
        status='PENDING'
    ).select_related('employee', 'request_type').order_by('-created_at')[:10]
    
    # Upcoming leave requests
    upcoming_leaves = LeaveRequest.objects.filter(
        employee__in=team_members,
        status__in=['APPROVED', 'PENDING'],
        start_date__gte=today
    ).select_related('employee').order_by('start_date')[:5]
    
    # Pending leave requests for the team (for approval section)
    pending_leave_requests = LeaveRequest.objects.filter(
        employee__in=team_members,
        status='PENDING'
    ).select_related('employee').order_by('-created_at')[:5]

    # Today's attendance breakdown for team
    today_attendance = Attendance.objects.filter(employee__in=team_members, date=today)
    team_present = today_attendance.filter(status='PRESENT').count()
    team_absent = today_attendance.filter(status='ABSENT').count()
    team_late = today_attendance.filter(status='LATE').count()
    team_half_day = today_attendance.filter(status='HALF_DAY').count()
    attendance_rate = round((present_today / total_team_members * 100) if total_team_members > 0 else 0, 1)

    context = {
        'team_members': team_members,
        'total_team_members': total_team_members,
        # Template aliases
        'team_size': total_team_members,
        'team_present_today': present_today,
        'team_attendance_rate': attendance_rate,
        'attendance_rate': attendance_rate,
        'team_pending_leave': pending_leave_requests.count(),
        'team_avg_performance': 0,
        'team_present': team_present,
        'team_absent': team_absent,
        'team_late': team_late,
        'team_half_day': team_half_day,
        'team_performance': [],
        'team_activities': [],
        'present_today': present_today,
        'pending_requests': pending_requests,
        'pending_leave_requests': pending_leave_requests,
        'upcoming_leaves': upcoming_leaves,
        'reviews_due': [],
        'current_date': today,
        'base_template': 'ems/base_employee.html',
    }

    return render(request, 'ems/supervisor_dashboard_new.html', context)


@login_required
def hr_dashboard(request):
    """HR Dashboard - HR-specific operations and metrics"""
    # Check if user has HR role
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'HR':
            messages.error(request, 'Access denied. HR role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    from django.db.models import Count, Q
    from datetime import date, timedelta
    
    company = request.user.company
    today = date.today()
    first_day_month = today.replace(day=1)
    
    # Total employees
    total_employees = User.objects.filter(
        company=company,
        role='EMPLOYEE',
        is_active=True
    ).count()
    
    # New hires this month
    new_this_month = User.objects.filter(
        company=company,
        role='EMPLOYEE',
        date_joined__gte=first_day_month
    ).count()
    
    # Pending leave requests
    pending_leave = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).count()
    
    # Pending documents
    from blu_staff.apps.documents.models import EmployeeDocument
    pending_documents = EmployeeDocument.objects.filter(
        employee__company=company,
        status='PENDING'
    ).count()
    
    # Active onboarding
    from blu_staff.apps.onboarding.models import EmployeeOnboarding
    active_onboarding = EmployeeOnboarding.objects.filter(
        employee__company=company,
        status='IN_PROGRESS'
    ).count()
    
    # Training completion rate
    from blu_staff.apps.training.models import TrainingEnrollment
    total_training = TrainingEnrollment.objects.filter(
        employee__company=company
    ).count()
    completed_training = TrainingEnrollment.objects.filter(
        employee__company=company,
        status='COMPLETED'
    ).count()
    training_completion = round((completed_training / total_training * 100) if total_training > 0 else 0, 1)
    
    # Pending leave requests with details (for approval section)
    pending_leave_requests = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).select_related('employee').order_by('-created_at')[:5]
    
    # Recent hires
    recent_hires = User.objects.filter(
        company=company,
        role='EMPLOYEE'
    ).select_related('employee_profile').order_by('-date_joined')[:5]
    
    # Onboarding progress
    onboarding_list = EmployeeOnboarding.objects.filter(
        employee__company=company,
        status='IN_PROGRESS'
    ).select_related('employee')[:5]
    
    # Calculate progress for each onboarding
    for onboarding in onboarding_list:
        total_tasks = onboarding.tasks.count()
        completed_tasks = onboarding.tasks.filter(status='COMPLETED').count()
        onboarding.progress = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
    
    # Training statistics
    in_progress_training = TrainingEnrollment.objects.filter(
        employee__company=company,
        status='IN_PROGRESS'
    ).count()
    
    # Enrolled but not started
    enrolled_training = TrainingEnrollment.objects.filter(
        employee__company=company,
        status='ENROLLED'
    ).count()
    
    # Department statistics - get unique departments from employee profiles
    from django.db.models import Value
    departments_data = EmployeeProfile.objects.filter(
        user__company=company,
        user__is_active=True
    ).exclude(
        department__isnull=True
    ).exclude(
        department=''
    ).values('department').annotate(
        employee_count=Count('user')
    ).order_by('-employee_count')
    
    context = {
        'current_date': today,
        'total_employees': total_employees,
        'new_this_month': new_this_month,
        'pending_leave': pending_leave,
        'pending_documents': pending_documents,
        'active_onboarding': active_onboarding,
        'training_completion': training_completion,
        'pending_leave_requests': pending_leave_requests,
        'recent_hires': recent_hires,
        'onboarding_list': onboarding_list,
        'total_training': total_training,
        'completed_training': completed_training,
        'in_progress_training': in_progress_training,
        'enrolled_training': enrolled_training,
        'departments': departments_data,
        'base_template': 'ems/base_employee.html',
    }

    return render(request, 'ems/hr_dashboard.html', context)


@login_required
def employee_salary_list(request):
    """Employee salary structures list — accessible to accountants and admins."""
    from blu_staff.apps.payroll.models import SalaryStructure
    from blu_staff.apps.accounts.models import User
    from datetime import date

    is_accountant = (hasattr(request.user, 'employee_profile') and
                     request.user.employee_profile and
                     request.user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']

    if not (is_accountant or is_admin):
        return render(request, 'ems/unauthorized.html', status=403)

    company = getattr(request.user, 'company', None) or _get_user_company(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        emp_id = request.POST.get('employee_id')
        try:
            target_emp = User.objects.get(id=emp_id, company=company, role='EMPLOYEE')
            base_salary = request.POST.get('base_salary')
            currency = request.POST.get('currency', 'USD').upper()[:3]
            payment_frequency = request.POST.get('payment_frequency', 'MONTHLY')
            effective_date_str = request.POST.get('effective_date') or str(date.today())
            notes = request.POST.get('notes', '')

            obj, created = SalaryStructure.objects.update_or_create(
                employee=target_emp,
                defaults={
                    'base_salary': base_salary,
                    'currency': currency,
                    'payment_frequency': payment_frequency,
                    'effective_date': effective_date_str,
                    'is_active': True,
                    'notes': notes,
                }
            )
            verb = 'created' if created else 'updated'
            messages.success(request, f'Salary structure {verb} for {target_emp.get_full_name()}.')
        except Exception as e:
            messages.error(request, f'Error saving salary: {e}')
        return redirect('employee_salary_list')

    employees = User.objects.filter(
        company=company, role='EMPLOYEE', is_active=True
    ).select_related('employee_profile').order_by('first_name', 'last_name')

    salary_map = {}
    if company:
        structures = SalaryStructure.objects.filter(
            employee__company=company, is_active=True
        ).select_related('employee')
        for s in structures:
            salary_map[s.employee_id] = s

    employee_salaries = []
    for emp in employees:
        employee_salaries.append({
            'employee': emp,
            'salary': salary_map.get(emp.id),
        })

    search = request.GET.get('q', '').strip()
    if search:
        employee_salaries = [
            row for row in employee_salaries
            if search.lower() in (row['employee'].get_full_name() or '').lower()
            or search.lower() in (getattr(row['employee'].employee_profile, 'job_title', '') or '').lower()
        ]

    set_count = sum(1 for r in employee_salaries if r['salary'])
    base_template = 'ems/base_employee.html' if is_accountant else 'ems/base_employer.html'
    context = {
        'employee_salaries': employee_salaries,
        'search': search,
        'base_template': base_template,
        'total': len(employee_salaries),
        'set_count': set_count,
        'today': str(date.today()),
        'freq_choices': SalaryStructure.PaymentFrequency.choices,
    }
    return render(request, 'ems/employee_salary_list.html', context)


@login_required
def accountant_dashboard(request):
    """Accountant Dashboard - Finance and payroll operations"""
    # Check if user has Accountant role
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'ACCOUNTANT':
            messages.error(request, 'Access denied. Accountant role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    from django.db.models import Sum, Count, Q
    from datetime import date
    from blu_staff.apps.payroll.models import Payroll, EmployeeBenefit, PayrollDeduction
    
    company = request.user.company
    today = date.today()
    first_day_month = today.replace(day=1)
    
    # Active employees on payroll
    active_employees = User.objects.filter(
        company=company,
        role='EMPLOYEE',
        is_active=True
    ).count()
    
    # Payroll statistics for current month
    current_month_payrolls = Payroll.objects.filter(
        employee__company=company,
        period_start__gte=first_day_month
    )
    
    # Monthly payroll total
    monthly_payroll = current_month_payrolls.aggregate(
        Sum('net_pay')
    )['net_pay__sum'] or 0
    
    # Pending payroll
    pending_payroll = current_month_payrolls.filter(
        status__in=['DRAFT', 'PENDING_APPROVAL']
    ).count()
    
    # Total deductions
    total_deductions = current_month_payrolls.aggregate(
        Sum('total_deductions')
    )['total_deductions__sum'] or 0
    
    # Benefits cost
    active_benefits = EmployeeBenefit.objects.filter(
        employee__company=company,
        status='ACTIVE'
    )
    
    benefits_cost = active_benefits.aggregate(
        company_cost=Sum('benefit__company_contribution'),
        employee_cost=Sum('benefit__employee_contribution')
    )
    
    company_benefits_cost = benefits_cost['company_cost'] or 0
    employee_benefits_cost = benefits_cost['employee_cost'] or 0
    total_benefits_cost = company_benefits_cost + employee_benefits_cost
    
    # Payroll overview
    total_payrolls = current_month_payrolls.count()
    paid_payrolls = current_month_payrolls.filter(status='PAID').count()
    pending_payrolls = current_month_payrolls.filter(status='PENDING_APPROVAL').count()
    draft_payrolls = current_month_payrolls.filter(status='DRAFT').count()
    
    # Financial summary
    total_gross = current_month_payrolls.aggregate(Sum('gross_pay'))['gross_pay__sum'] or 0
    total_net = current_month_payrolls.aggregate(Sum('net_pay'))['net_pay__sum'] or 0
    
    # Deduction breakdown
    tax_deductions = current_month_payrolls.aggregate(Sum('tax'))['tax__sum'] or 0
    social_security = current_month_payrolls.aggregate(Sum('social_security'))['social_security__sum'] or 0
    insurance_deductions = current_month_payrolls.aggregate(Sum('insurance'))['insurance__sum'] or 0
    
    # Recent payroll runs
    recent_payrolls = Payroll.objects.filter(
        employee__company=company
    ).values('period_start', 'period_end', 'status').annotate(
        employee_count=Count('id'),
        total_net=Sum('net_pay')
    ).order_by('-period_start')[:5]
    
    # Deduction breakdown by type
    deduction_breakdown = PayrollDeduction.objects.filter(
        payroll__employee__company=company,
        payroll__period_start__gte=first_day_month
    ).values('deduction_type').annotate(
        amount=Sum('amount'),
        count=Count('id')
    ).order_by('-amount')
    
    for deduction in deduction_breakdown:
        deduction['type'] = dict(PayrollDeduction.DeductionType.choices).get(
            deduction['deduction_type'],
            deduction['deduction_type']
        )

    # Currency symbol
    currency_code = 'ZMW'
    try:
        latest = Payroll.objects.filter(employee__company=company).values('currency').first()
        if latest and latest['currency']:
            currency_code = latest['currency']
    except Exception:
        pass
    _currency_map = {
        'ZMW': 'K', 'KES': 'KSh', 'TZS': 'TSh', 'UGX': 'USh',
        'ZAR': 'R', 'NGN': '₦', 'GHS': 'GH₵', 'USD': '$', 'GBP': '£', 'EUR': '€',
    }
    currency_symbol = _currency_map.get(currency_code, currency_code)

    context = {
        'current_date': today,
        'active_employees': active_employees,
        'monthly_payroll': monthly_payroll,
        'pending_payroll': pending_payroll,
        'total_deductions': total_deductions,
        'benefits_cost': total_benefits_cost,
        'total_payrolls': total_payrolls,
        'paid_payrolls': paid_payrolls,
        'pending_payrolls': pending_payrolls,
        'draft_payrolls': draft_payrolls,
        'total_gross': total_gross,
        'total_net': total_net,
        'tax_deductions': tax_deductions,
        'social_security': social_security,
        'insurance_deductions': insurance_deductions,
        'recent_payrolls': recent_payrolls,
        'active_benefits': active_benefits.count(),
        'company_benefits_cost': company_benefits_cost,
        'employee_benefits_cost': employee_benefits_cost,
        'total_benefits_cost': total_benefits_cost,
        'deduction_breakdown': deduction_breakdown,
        'currency_symbol': currency_symbol,
        'currency_code': currency_code,
        'base_template': 'ems/base_employee.html',
    }

    return render(request, 'ems/accountant_dashboard.html', context)


@login_required
def supervisor_team_attendance(request):
    """Team Attendance View - Aggregate view of team attendance"""
    # Check if user is a supervisor
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'SUPERVISOR':
            messages.error(request, 'Access denied. Supervisor role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Get team members
    team_members = User.objects.filter(
        employee_profile__supervisor=request.user,
        company=request.user.company
    ).select_related('employee_profile')
    
    # Date range filter
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        try:
            start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
        except:
            pass
    
    if request.GET.get('end_date'):
        try:
            end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
        except:
            pass
    
    # Get attendance records
    attendance_records = Attendance.objects.filter(
        employee__in=team_members,
        date__range=[start_date, end_date]
    ).select_related('employee').order_by('-date', 'employee__first_name')
    
    # Aggregate statistics
    total_days = (end_date - start_date).days + 1
    stats = {
        'total_days': total_days,
        'present': attendance_records.filter(status='PRESENT').count(),
        'absent': attendance_records.filter(status='ABSENT').count(),
        'late': attendance_records.filter(status='LATE').count(),
        'half_day': attendance_records.filter(status='HALF_DAY').count(),
    }
    
    # Per-employee summary
    employee_summary = []
    for member in team_members:
        member_attendance = attendance_records.filter(employee=member)
        summary = {
            'employee': member,
            'total_present': member_attendance.filter(status='PRESENT').count(),
            'total_absent': member_attendance.filter(status='ABSENT').count(),
            'total_late': member_attendance.filter(status='LATE').count(),
            'attendance_rate': round((member_attendance.filter(status='PRESENT').count() / total_days * 100) if total_days > 0 else 0, 1)
        }
        employee_summary.append(summary)
    
    context = {
        'team_members': team_members,
        'attendance_records': attendance_records,
        'stats': stats,
        'employee_summary': employee_summary,
        'start_date': start_date,
        'end_date': end_date,
        'base_template': 'ems/base_employee.html',
    }

    return render(request, 'ems/supervisor_team_attendance.html', context)


@login_required
def supervisor_team_performance(request):
    """Team Performance Metrics - Performance tracking dashboard"""
    # Check if user is a supervisor
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'SUPERVISOR':
            messages.error(request, 'Access denied. Supervisor role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Get team members
    team_members = User.objects.filter(
        employee_profile__supervisor=request.user,
        company=request.user.company
    ).select_related('employee_profile')
    
    # Performance module disabled — use empty stubs to avoid queryset crashes
    employee_performance = [
        {'employee': m, 'total_reviews': 0, 'latest_review': None, 'avg_rating': 0, 'pending_reviews': 0}
        for m in team_members
    ]

    context = {
        'team_members': team_members,
        'reviews': [],
        'completed_reviews_count': 0,
        'pending_reviews_count': 0,
        'avg_overall_rating': 0,
        'employee_performance': employee_performance,
        'base_template': 'ems/base_employee.html',
    }

    return render(request, 'ems/supervisor_team_performance.html', context)


@login_required
def supervisor_request_approval(request):
    """Enhanced Request Approval Interface for Supervisors"""
    # Check if user is a supervisor
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'SUPERVISOR':
            messages.error(request, 'Access denied. Supervisor role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Get team members
    team_members = User.objects.filter(
        employee_profile__supervisor=request.user,
        company=request.user.company
    )
    
    from blu_staff.apps.requests.models import EmployeeRequest, RequestApproval
    
    # Get pending requests from team members
    pending_requests = EmployeeRequest.objects.filter(
        employee__in=team_members,
        status='PENDING'
    ).select_related('employee', 'request_type').prefetch_related('approvals').order_by('-created_at')
    
    # Get requests pending supervisor's approval
    my_pending_approvals = RequestApproval.objects.filter(
        approver=request.user,
        action='PENDING'
    ).select_related('request', 'request__employee', 'request__request_type').order_by('-assigned_date')
    
    # Recently processed requests
    recent_processed = EmployeeRequest.objects.filter(
        employee__in=team_members,
        status__in=['APPROVED', 'REJECTED']
    ).select_related('employee', 'request_type').order_by('-updated_at')[:10]
    
    # Handle approval/rejection
    if request.method == 'POST':
        approval_id = request.POST.get('approval_id')
        action = request.POST.get('action')
        comments = request.POST.get('comments', '')
        
        try:
            approval = RequestApproval.objects.get(
                id=approval_id,
                approver=request.user,
                action='PENDING'
            )
            
            if action in ['APPROVED', 'REJECTED']:
                approval.action = action
                approval.comments = comments
                approval.action_date = timezone.now()
                approval.save()
                
                # Update request status
                emp_request = approval.request
                if action == 'APPROVED':
                    # Check if all approvals are complete
                    all_approved = not emp_request.approvals.filter(action='PENDING').exists()
                    if all_approved:
                        emp_request.status = 'APPROVED'
                        emp_request.save()
                    messages.success(request, f'Request {emp_request.request_number} approved successfully.')
                else:
                    emp_request.status = 'REJECTED'
                    emp_request.save()
                    messages.success(request, f'Request {emp_request.request_number} rejected.')
                
                return redirect('supervisor_request_approval')
        except RequestApproval.DoesNotExist:
            messages.error(request, 'Approval not found or already processed.')
    
    context = {
        'pending_requests': pending_requests,
        'my_pending_approvals': my_pending_approvals,
        'recent_processed': recent_processed,
        'base_template': 'ems/base_employee.html',
    }

    return render(request, 'ems/supervisor_request_approval.html', context)


@login_required
@require_feature(FEAT_CUSTOM_REPORTS)
def custom_report_builder(request):
    """Custom report builder for dynamic reports"""
    if request.user.role not in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return render(request, 'ems/unauthorized.html')
    
    from reports.custom_report_builder import CustomReportBuilder, generate_custom_report
    from django.http import HttpResponse
    
    company = getattr(request.user, 'company', None)
    
    # Get report configuration
    source = request.GET.get('source', 'employees')
    available_sources = CustomReportBuilder.REPORT_SOURCES
    
    # Initialize builder
    builder = CustomReportBuilder(source, company)
    source_config = builder.config
    
    # Handle report generation
    if request.method == 'POST' or request.GET.get('generate'):
        # Get filters
        filters = {}
        for key in request.GET.keys():
            if key not in ['source', 'generate', 'export', 'fields']:
                filters[key] = request.GET.get(key)
        
        # Get selected fields
        selected_fields_param = request.GET.get('fields', '')
        selected_fields = selected_fields_param.split(',') if selected_fields_param else None
        
        # Generate report
        report_data = generate_custom_report(source, company, filters, selected_fields)
        
        # Handle CSV export
        if request.GET.get('export') == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="custom_report_{source}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            response.write(report_data['csv'])
            return response
        
        context = {
            'available_sources': available_sources,
            'current_source': source,
            'source_config': source_config,
            'report_data': report_data['data'],
            'statistics': report_data['statistics'],
            'filters': filters,
            'selected_fields': selected_fields or list(source_config.get('fields', {}).keys()),
        }
        
        return render(request, 'ems/custom_report_builder.html', context)
    
    # Initial view
    context = {
        'available_sources': available_sources,
        'current_source': source,
        'source_config': source_config,
    }
    
    return render(request, 'ems/custom_report_builder.html', context)


@login_required
def payslip_designer(request):
    """Advanced payslip designer with drag-and-drop functionality"""
    allowed_roles = {'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN'}
    if not (
        getattr(request.user, 'role', '') in allowed_roles
        or getattr(request.user, 'is_employer_admin', False)
        or getattr(request.user, 'is_superuser', False)
    ):
        return render(request, 'ems/unauthorized.html', status=403)

    company = _get_user_company(request.user)
    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        # Save payslip design settings
        company.payslip_orientation = request.POST.get('orientation', 'portrait')
        company.payslip_logo_position = request.POST.get('logo_position', 'top-left')
        company.payslip_stamp_position = request.POST.get('stamp_position', 'bottom-right')
        company.payslip_address_position = request.POST.get('address_position', 'top-right')
        company.payslip_header_content = request.POST.get('header_content', '')
        company.payslip_footer_content = request.POST.get('footer_content', '')
        
        # Handle section order
        import json
        section_order = request.POST.get('section_order', '[]')
        try:
            company.payslip_section_order = json.loads(section_order)
        except:
            company.payslip_section_order = ['employee_info', 'salary_info', 'deductions', 'summary']
        
        # Handle field positions
        field_positions = request.POST.get('field_positions', '{}')
        try:
            company.payslip_field_positions = json.loads(field_positions)
        except:
            company.payslip_field_positions = {}
        
        company.save()
        messages.success(request, 'Payslip design saved successfully!')
        return redirect('payslip_designer')

    # Default section order if not set
    if not company.payslip_section_order:
        company.payslip_section_order = ['employee_info', 'salary_info', 'deductions', 'summary']
    
    context = {
        'company': company,
        'available_sections': [
            {'id': 'employee_info', 'name': 'Employee Information', 'icon': ''},
            {'id': 'salary_info', 'name': 'Salary Information', 'icon': ''},
            {'id': 'deductions', 'name': 'Deductions', 'icon': ''},
            {'id': 'allowances', 'name': 'Allowances', 'icon': ''},
            {'id': 'summary', 'name': 'Summary', 'icon': ''},
            {'id': 'tax_breakdown', 'name': 'Tax Breakdown', 'icon': ''},
            {'id': 'ytd_summary', 'name': 'YTD Summary', 'icon': ''},
        ],
        'position_options': [
            {'value': 'top-left', 'label': 'Top Left'},
            {'value': 'top-center', 'label': 'Top Center'},
            {'value': 'top-right', 'label': 'Top Right'},
            {'value': 'bottom-left', 'label': 'Bottom Left'},
            {'value': 'bottom-center', 'label': 'Bottom Center'},
            {'value': 'bottom-right', 'label': 'Bottom Right'},
        ],
    }

    return render(request, 'ems/payslip_designer.html', context)


@login_required
def role_hub(request):
    """Full-page hub showing all role-specific modules as cards"""
    from django.urls import reverse
    
    employee_role = None
    if hasattr(request.user, 'employee_profile'):
        employee_role = request.user.employee_profile.employee_role
    
    if not employee_role or employee_role == 'EMPLOYEE':
        return redirect('employee_dashboard')
    
    modules = []
    role_title = ''
    role_description = ''
    
    if employee_role == 'SUPERVISOR':
        role_title = 'Team Management'
        role_description = 'Manage your team, track performance, and handle approvals'
        modules = [
            {
                'title': 'My Team',
                'description': 'View and manage your direct reports, team structure, and employee details',
                'url': reverse('supervisor_dashboard'),
                'icon': 'users',
                'color': '#2563eb',
                'bg': '#dbeafe',
            },
            {
                'title': 'Team Attendance',
                'description': 'Monitor team attendance, clock-in/out times, and attendance patterns',
                'url': reverse('supervisor_team_attendance'),
                'icon': 'clock-check',
                'color': '#059669',
                'bg': '#d1fae5',
            },
            {
                'title': 'Team Performance',
                'description': 'Track performance metrics, reviews, and development goals for your team',
                'url': reverse('supervisor_team_performance'),
                'icon': 'bar-chart',
                'color': '#7c3aed',
                'bg': '#ede9fe',
            },
            {
                'title': 'Approve Requests',
                'description': 'Review and approve pending leave, expense, and other employee requests',
                'url': reverse('supervisor_request_approval'),
                'icon': 'check-square',
                'color': '#f59e0b',
                'bg': '#fef3c7',
            },
            {
                'title': 'Team Assets',
                'description': 'View assets assigned to your team members and manage asset requests',
                'url': reverse('assets:asset_list'),
                'icon': 'briefcase',
                'color': '#0891b2',
                'bg': '#cffafe',
            },
            {
                'title': 'Team Reports',
                'description': 'Generate and view reports on team attendance, performance, and productivity',
                'url': reverse('reports_center') + '?view=team',
                'icon': 'file-text',
                'color': '#dc2626',
                'bg': '#fee2e2',
            },
        ]
    
    elif employee_role == 'HR':
        role_title = 'HR Functions'
        role_description = 'Manage employees, attendance, leave, performance, and company-wide HR operations'
        modules = [
            {
                'title': 'All Employees',
                'description': 'View, search, and manage all employee records, profiles, and employment details',
                'url': reverse('employer_employee_management'),
                'icon': 'users',
                'color': '#2563eb',
                'bg': '#dbeafe',
            },
            {
                'title': 'Attendance',
                'description': 'Company-wide attendance dashboard with daily summaries and exception tracking',
                'url': reverse('attendance_dashboard'),
                'icon': 'calendar-check',
                'color': '#059669',
                'bg': '#d1fae5',
            },
            {
                'title': 'Leave Management',
                'description': 'Manage leave requests, balances, policies, and company leave calendar',
                'url': reverse('leave_management'),
                'icon': 'calendar-off',
                'color': '#0891b2',
                'bg': '#cffafe',
            },
            {
                'title': 'Documents',
                'description': 'Manage employee documents, contracts, certifications, and compliance files',
                'url': reverse('documents_list'),
                'icon': 'file-text',
                'color': '#6366f1',
                'bg': '#e0e7ff',
            },
            {
                'title': 'Contract Management',
                'description': 'Manage employee contracts, renewals, amendments, and expiry tracking',
                'url': reverse('contracts:contracts_list'),
                'icon': 'file-signature',
                'color': '#8b5cf6',
                'bg': '#ede9fe',
            },
            {
                'title': 'Performance',
                'description': 'Manage performance review cycles, goals, and employee evaluations',
                'url': reverse('performance_reviews_list'),
                'icon': 'star',
                'color': '#f59e0b',
                'bg': '#fef3c7',
            },
            {
                'title': 'Onboarding',
                'description': 'Manage new hire onboarding workflows, checklists, and orientation tasks',
                'url': reverse('onboarding_list'),
                'icon': 'user-plus',
                'color': '#10b981',
                'bg': '#d1fae5',
            },
            {
                'title': 'Training Management',
                'description': 'Create and manage training programs, enrollments, and certifications',
                'url': reverse('training_list'),
                'icon': 'book-open',
                'color': '#7c3aed',
                'bg': '#ede9fe',
            },
            {
                'title': 'Benefits Management',
                'description': 'Manage employee benefit plans, enrollments, and contribution tracking',
                'url': reverse('benefits_list'),
                'icon': 'heart',
                'color': '#ec4899',
                'bg': '#fce7f3',
            },
            {
                'title': 'Approvals',
                'description': 'Review and process pending approvals for leave, requests, and documents',
                'url': reverse('approval_center'),
                'icon': 'check-square',
                'color': '#f97316',
                'bg': '#ffedd5',
            },
            {
                'title': 'Assets Management',
                'description': 'Track company assets, assignments, maintenance, and depreciation',
                'url': reverse('assets:asset_list'),
                'icon': 'briefcase',
                'color': '#0891b2',
                'bg': '#cffafe',
            },
            {
                'title': 'E-Forms Management',
                'description': 'Create and manage electronic forms, templates, and form submissions',
                'url': reverse('eforms_list'),
                'icon': 'clipboard',
                'color': '#8b5cf6',
                'bg': '#ede9fe',
            },
            {
                'title': 'Employee Requests',
                'description': 'Review and manage employee requests, applications, and submissions',
                'url': reverse('employee_requests_list'),
                'icon': 'inbox',
                'color': '#0891b2',
                'bg': '#cffafe',
            },
            {
                'title': 'Bulk Import',
                'description': 'Import employee data in bulk via CSV/Excel for quick onboarding',
                'url': reverse('bulk_employee_import'),
                'icon': 'upload',
                'color': '#64748b',
                'bg': '#f1f5f9',
            },
            {
                'title': 'HR Analytics',
                'description': 'Dashboards and insights on workforce metrics, turnover, and trends',
                'url': reverse('analytics_dashboard_view'),
                'icon': 'pie-chart',
                'color': '#dc2626',
                'bg': '#fee2e2',
            },
            {
                'title': 'HR Reports',
                'description': 'Generate detailed reports on attendance, payroll, compliance, and more',
                'url': reverse('reports_center'),
                'icon': 'file-text',
                'color': '#1d4ed8',
                'bg': '#dbeafe',
            },
            {
                'title': 'Send Payslips',
                'description': 'Search employees and trigger payslips via email or export.',
                'url': reverse('hr_send_email'),
                'icon': 'mail',
                'color': '#0ea5e9',
                'bg': '#e0f2fe',
            },
        ]
    
    elif employee_role in ['ACCOUNTANT', 'ACCOUNTS']:
        role_title = 'Finance Functions'
        role_description = 'Manage payroll, petty cash, financial reports, and analytics'
        modules = [
            {
                'title': 'Payroll',
                'description': 'Process employee payroll, manage salary structures, and generate payslips',
                'url': reverse('payroll_list'),
                'icon': 'dollar-sign',
                'color': '#059669',
                'bg': '#d1fae5',
            },
            {
                'title': 'Petty Cash',
                'description': 'Manage petty cash fund, track disbursements, and reconcile balances',
                'url': reverse('petty_cash_dashboard'),
                'icon': 'credit-card',
                'color': '#f59e0b',
                'bg': '#fef3c7',
            },
            {
                'title': 'Financial Reports',
                'description': 'Generate payroll summaries, expense reports, and financial statements',
                'url': reverse('reports_center'),
                'icon': 'file-text',
                'color': '#2563eb',
                'bg': '#dbeafe',
            },
            {
                'title': 'Financial Analytics',
                'description': 'Visual dashboards for payroll trends, cost analysis, and budget tracking',
                'url': reverse('financial_analytics'),
                'icon': 'pie-chart',
                'color': '#7c3aed',
                'bg': '#ede9fe',
            },
        ]
    
    context = {
        'modules': modules,
        'role_title': role_title,
        'role_description': role_description,
        'employee_role': employee_role,
        'base_template': 'ems/base_employee.html',
    }
    
    return render(request, 'ems/role_hub.html', context)


@login_required
def hr_send_email(request):
    """Basic HR email hub: search employees, select recipients, and compose a message.
    Actual delivery should be wired to configured email backend; this view only stubs success messaging.
    """
    # Ensure HR access
    employee_role = getattr(getattr(request.user, 'employee_profile', None), 'employee_role', None)
    if employee_role != 'HR':
        messages.error(request, 'Unauthorized: HR access required.')
        return redirect('role_hub')

    query = request.GET.get('q', '').strip()

    latest_payroll_sq = Payroll.objects.filter(employee=OuterRef('pk')).order_by('-period_end').values('id')[:1]
    employees = (
        User.objects
        .filter(company=request.user.company, role='EMPLOYEE')
        .select_related('employee_profile')
        .annotate(latest_payroll_id=Subquery(latest_payroll_sq))
    )
    if query:
        employees = employees.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        send_mode = request.POST.get('send_mode', 'selected')
        selected_ids = request.POST.getlist('recipient_ids')
        action = request.POST.get('action', 'send')

        if not subject or not body:
            messages.error(request, 'Subject and message body are required to send an email.')
        else:
            if send_mode == 'all':
                recipients = employees
            else:
                recipients = employees.filter(id__in=selected_ids) if selected_ids else employees.none()

            recipient_count = recipients.count()
            if recipient_count == 0:
                messages.error(request, 'No recipients selected.')
            else:
                success_count = 0
                skipped = 0
                for emp in recipients:
                    payroll_id = emp.latest_payroll_id
                    if not payroll_id:
                        skipped += 1
                        continue
                    try:
                        # Render payslip detail HTML to PDF placeholder (actual PDF generation to be wired)
                        payroll = Payroll.objects.get(id=payroll_id)
                        # Placeholder: instead of actual PDF, send link to payslip detail
                        email = EmailMessage(
                            subject or 'Payslip',
                            f"{body}\n\nView payslip: {request.build_absolute_uri(reverse('payroll_detail', args=[payroll_id]))}",
                            to=[emp.email],
                        )
                        email.send(fail_silently=True)
                        success_count += 1
                    except Exception:
                        skipped += 1
                messages.success(request, f"Payslip emails queued: {success_count}; skipped (no payroll or send error): {skipped}.")

    context = {
        'employees': employees.order_by('-date_joined')[:50],  # limit to keep page light
        'query': query,
    }
    return render(request, 'ems/hr_send_email.html', context)


# Super Admin Tenant Management Views
@login_required
def superadmin_tenants(request):
    """Super Admin tenant management dashboard"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')
    
    from blu_staff.apps.accounts.models import Company, User
    from django.db import models
    from datetime import date, timedelta
    
    today = date.today()
    
    # Get all companies with stats
    companies = Company.objects.all().order_by('-created_at')
    
    from blu_staff.apps.documents.models import EmployeeDocument
    from django.db.models import Sum

    # Calculate stats for each company
    for company in companies:
        company.total_users = User.objects.filter(company=company).count()
        company.total_employees = User.objects.filter(company=company, role='EMPLOYEE').count()
        company.active_users = User.objects.filter(company=company, is_active=True).count()
        storage_bytes = EmployeeDocument.objects.filter(
            employee__company=company
        ).aggregate(total=Sum('file_size'))['total'] or 0
        company.storage_used = round(storage_bytes / (1024 ** 3), 2)
        company.api_calls = 0
        company.monthly_revenue = 0
        
        # Determine status
        if company.is_trial and company.trial_ends_at and company.trial_ends_at < today:
            company.status = 'expired'
        elif hasattr(company, 'is_suspended') and company.is_suspended:
            company.status = 'suspended'
        elif company.is_trial:
            company.status = 'trial'
        elif company.is_active:
            company.status = 'active'
        else:
            company.status = 'inactive'
    
    # Overall stats
    total_tenants = companies.count()
    active_tenants = companies.filter(is_active=True, is_trial=False).count()
    trial_tenants = companies.filter(is_trial=True).count()
    total_users = User.objects.count()
    
    # New tenants this month
    month_start = today.replace(day=1)
    new_this_month = companies.filter(created_at__gte=month_start).count()
    
    # Expiring soon (next 30 days)
    expiring_soon = companies.filter(
        models.Q(trial_ends_at__lte=today + timedelta(days=30)) |
        models.Q(license_expiry__lte=today + timedelta(days=30))
    ).count()
    
    # Pending registration requests
    from blu_staff.apps.accounts.models import CompanyRegistrationRequest
    try:
        pending_registrations = CompanyRegistrationRequest.objects.filter(
            status='PENDING'
        ).order_by('-created_at')
        pending_count = pending_registrations.count()
    except Exception:
        pending_registrations = []
        pending_count = 0

    context = {
        'companies': companies,
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'trial_tenants': trial_tenants,
        'total_users': total_users,
        'new_this_month': new_this_month,
        'expiring_soon': expiring_soon,
        'pending_registrations': pending_registrations,
        'pending_count': pending_count,
    }
    
    return render(request, 'ems/superadmin_tenants.html', context)


@login_required
def tenant_detail(request, company_id):
    """Detailed view of a specific tenant"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')
    
    from blu_staff.apps.accounts.models import Company, User
    from django.shortcuts import get_object_or_404
    
    company = get_object_or_404(Company, id=company_id)
    
    # Get company users
    company_users = User.objects.filter(company=company).order_by('-date_joined')
    recent_users = company_users[:5]
    
    from blu_staff.apps.documents.models import EmployeeDocument
    from django.db.models import Sum
    from datetime import timedelta

    # Calculate metrics
    company.total_users = company_users.count()
    company.total_employees = company_users.filter(role='EMPLOYEE').count()
    company.active_users = company_users.filter(is_active=True).count()
    storage_bytes = EmployeeDocument.objects.filter(
        employee__company=company
    ).aggregate(total=Sum('file_size'))['total'] or 0
    company.storage_used = round(storage_bytes / (1024 ** 3), 2)
    company.api_calls = 0
    company.monthly_revenue = 0

    # Recent activity
    recent_activity = []
    try:
        for u in company_users.order_by('-date_joined')[:4]:
            recent_activity.append({
                'icon': 'user',
                'title': 'User registered',
                'description': f'{u.get_full_name() or u.email} joined as {u.role}',
                'timestamp': u.date_joined,
            })
    except Exception:
        pass
    try:
        for doc in EmployeeDocument.objects.filter(
            employee__company=company
        ).order_by('-created_at')[:4]:
            recent_activity.append({
                'icon': 'document',
                'title': 'Document uploaded',
                'description': f'{doc.title} by {doc.uploaded_by.get_full_name() if doc.uploaded_by else "System"}',
                'timestamp': doc.created_at,
            })
    except Exception:
        pass
    try:
        from blu_staff.apps.attendance.models import Attendance
        for att in Attendance.objects.filter(user__company=company).order_by('-created_at')[:4]:
            recent_activity.append({
                'icon': 'clock',
                'title': 'Attendance recorded',
                'description': f'{att.user.get_full_name() or att.user.email} — {att.get_status_display()}',
                'timestamp': att.created_at,
            })
    except Exception:
        pass
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:8]

    context = {
        'company': company,
        'recent_users': recent_users,
        'recent_activity': recent_activity,
    }

    return render(request, 'ems/tenant_detail.html', context)


@login_required
def suspend_tenant(request, company_id):
    """Suspend a tenant account"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        company = get_object_or_404(Company, id=company_id)
        
        # Suspend all users in the company
        from blu_staff.apps.accounts.models import User
        User.objects.filter(company=company).update(is_active=False)
        
        # Mark company as suspended
        company.is_active = False
        company.is_suspended = True
        company.suspended_at = timezone.now()
        company.suspended_by = request.user
        company.save()
        
        # Log the suspension
        from django.contrib.admin.models import LogEntry, CHANGE
        # LogEntry call removed - was causing errors with content_type_id=None
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def send_announcement(request, company_id):
    """Send announcement to all tenant users"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        message = data.get('message', '')
        
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        company = get_object_or_404(Company, id=company_id)
        
        # Get all active users in the company
        from blu_staff.apps.accounts.models import User
        users = User.objects.filter(company=company, is_active=True)
        
        # Create notifications for all users
        from ems.models import Notification
        notifications_created = 0
        
        for user in users:
            Notification.objects.create(
                user=user,
                title='System Announcement',
                message=message,
                notification_type='SYSTEM',
                created_by=request.user
            )
            notifications_created += 1
        
        # Log the announcement
        from django.contrib.admin.models import LogEntry, ADDITION
        # LogEntry call removed - was causing errors with content_type_id=None
        
        return JsonResponse({'success': True, 'notifications_sent': notifications_created})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def generate_tenant_report(request, company_id):
    """Generate comprehensive tenant report"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = get_object_or_404(Company, id=company_id)

        from blu_staff.apps.documents.models import EmployeeDocument
        from django.db.models import Sum

        company_users = User.objects.filter(company=company)
        company.total_users = company_users.count()
        company.total_employees = company_users.filter(role='EMPLOYEE').count()
        company.active_users = company_users.filter(is_active=True).count()
        storage_bytes = EmployeeDocument.objects.filter(
            employee__company=company
        ).aggregate(total=Sum('file_size'))['total'] or 0
        company.storage_used = round(storage_bytes / (1024 ** 3), 2)
        company.api_calls = 0
        company.monthly_revenue = 0

        return render(request, 'ems/tenant_report.html', {'company': company})
    except Exception as e:
        messages.error(request, f'Error generating report: {str(e)}')
        return redirect('tenant_detail', company_id=company_id)


@csrf_exempt
@login_required
def export_tenant_data(request, company_id):
    """Export all tenant data"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        company = get_object_or_404(Company, id=company_id)
        
        # Get all users data
        from blu_staff.apps.accounts.models import User
        users = User.objects.filter(company=company).values(
            'email', 'first_name', 'last_name', 'role', 'is_active', 
            'date_joined', 'last_login'
        )
        
        # Create CSV content
        import csv
        from io import StringIO
        import datetime
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Email', 'First Name', 'Last Name', 'Role', 'Active', 'Date Joined', 'Last Login'])
        
        # Write user data
        for user in users:
            writer.writerow([
                user['email'],
                user['first_name'] or '',
                user['last_name'] or '',
                user['role'],
                'Yes' if user['is_active'] else 'No',
                user['date_joined'].strftime('%Y-%m-%d %H:%M:%S') if user['date_joined'] else '',
                user['last_login'].strftime('%Y-%m-%d %H:%M:%S') if user['last_login'] else ''
            ])
        
        # Create HTTP response
        response = HttpResponse(
            output.getvalue(),
            content_type='text/csv'
        )
        response['Content-Disposition'] = f'attachment; filename="{company.name}_users_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        # Log the export
        from django.contrib.admin.models import LogEntry
        # LogEntry call removed - was causing errors with content_type_id=None
        
        return response
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def reset_tenant_password(request, company_id):
    """Reset admin password for tenant"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        company = get_object_or_404(Company, id=company_id)
        
        # Get the admin user for this company
        from blu_staff.apps.accounts.models import User
        admin_user = User.objects.filter(
            company=company,
            role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
        ).first()
        
        if not admin_user:
            return JsonResponse({'error': 'No admin user found'}, status=404)
        
        # Generate temporary password
        import random
        import string
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        # Set new password
        admin_user.set_password(temp_password)
        admin_user.save()
        
        # Create notification for the admin user
        try:
            from ems.models import Notification
            Notification.objects.create(
                user=admin_user,
                title='Password Reset',
                message=f'Your password has been reset by SuperAdmin. Your temporary password is: {temp_password}',
                notification_type='SECURITY',
                created_by=request.user
            )
        except:
            pass  # Continue even if notification fails
        
        # Log the password reset
        from django.contrib.admin.models import LogEntry, CHANGE
        # LogEntry call removed - was causing errors with content_type_id=None
        
        return JsonResponse({
            'success': True,
            'temp_password': temp_password,
            'admin_email': admin_user.email
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def tenant_users(request, company_id):
    """List all users for a specific tenant"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')
    
    from blu_staff.apps.accounts.models import Company, User
    from django.shortcuts import get_object_or_404
    from django.core.paginator import Paginator
    
    company = get_object_or_404(Company, id=company_id)
    users = User.objects.filter(company=company).order_by('-date_joined')
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Apply filters
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    if status_filter:
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)
    
    if date_from:
        users = users.filter(date_joined__date__gte=date_from)
    
    if date_to:
        users = users.filter(date_joined__date__lte=date_to)
    
    # Counts before pagination
    active_count = users.filter(is_active=True).count()
    inactive_count = users.filter(is_active=False).count()
    total_count = users.count()

    # Pagination
    paginator = Paginator(users, 25)  # 25 users per page
    page = request.GET.get('page', 1)
    
    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)
    
    context = {
        'company': company,
        'users': users,
        'total_users': total_count,
        'active_users': active_count,
        'inactive_users': inactive_count,
        'is_paginated': users.has_other_pages(),
        'page_obj': users,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'ems/tenant_users.html', context)


@login_required
def tenant_analytics(request, company_id):
    """Analytics dashboard for a specific tenant"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.accounts.models import Company
    from django.shortcuts import get_object_or_404
    from django.db.models import Sum, Count
    from blu_staff.apps.documents.models import EmployeeDocument
    from datetime import date, timedelta

    company = get_object_or_404(Company, id=company_id)
    company_users = User.objects.filter(company=company)

    company.total_users = company_users.count()
    company.active_users = company_users.filter(is_active=True).count()
    company.total_employees = company_users.filter(role='EMPLOYEE').count()

    # Storage used in GB derived from EmployeeDocument.file_size (bytes)
    storage_bytes = EmployeeDocument.objects.filter(
        employee__company=company
    ).aggregate(total=Sum('file_size'))['total'] or 0
    company.storage_used = round(storage_bytes / (1024 ** 3), 2)

    # User distribution by role
    role_dist = list(
        company_users.values('role').annotate(count=Count('id')).order_by('-count')
    )

    # Recent activity — real events from the past 30 days
    cutoff = date.today() - timedelta(days=30)
    recent_activity = []
    try:
        for u in company_users.filter(date_joined__date__gte=cutoff).order_by('-date_joined')[:5]:
            recent_activity.append({
                'icon': 'user',
                'title': 'New user registered',
                'description': f'{u.get_full_name() or u.email} joined as {u.get_role_display() if hasattr(u, "get_role_display") else u.role}',
                'timestamp': u.date_joined,
            })
    except Exception:
        pass
    try:
        from blu_staff.apps.documents.models import EmployeeDocument as EDoc
        for doc in EDoc.objects.filter(employee__company=company).order_by('-created_at')[:5]:
            recent_activity.append({
                'icon': 'document',
                'title': 'Document uploaded',
                'description': f'{doc.title} uploaded by {doc.uploaded_by.get_full_name() if doc.uploaded_by else "System"}',
                'timestamp': doc.created_at,
            })
    except Exception:
        pass
    try:
        from blu_staff.apps.attendance.models import Attendance
        for att in Attendance.objects.filter(user__company=company).order_by('-created_at')[:5]:
            recent_activity.append({
                'icon': 'clock',
                'title': 'Attendance recorded',
                'description': f'{att.user.get_full_name() or att.user.email} — {att.get_status_display()}',
                'timestamp': att.created_at,
            })
    except Exception:
        pass
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:8]

    context = {
        'company': company,
        'role_dist': role_dist,
        'recent_activity': recent_activity,
    }

    return render(request, 'ems/tenant_analytics.html', context)


# ============================================================================
# TIMESHEETS MODULE
# ============================================================================

@login_required
def timesheets_list(request):
    """HR / Accountant view: list all company timesheets with filtering."""
    from blu_staff.apps.payroll.models import Timesheet
    from django.db.models import Sum, Q

    user = request.user
    is_hr = (user.role == 'EMPLOYEE' and hasattr(user, 'employee_profile') and
             user.employee_profile.employee_role == 'HR')
    is_accountant = (user.role == 'EMPLOYEE' and hasattr(user, 'employee_profile') and
                     user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']

    if not (is_hr or is_accountant or is_admin):
        return render(request, 'ems/unauthorized.html', status=403)

    company = getattr(user, 'company', None)
    qs = Timesheet.objects.filter(employee__company=company).select_related(
        'employee', 'employee__employee_profile', 'reviewed_by'
    )

    status_filter = request.GET.get('status', '')
    employee_filter = request.GET.get('employee', '')
    week_from = request.GET.get('week_from', '')
    week_to = request.GET.get('week_to', '')
    search = request.GET.get('search', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if employee_filter:
        qs = qs.filter(employee_id=employee_filter)
    if week_from:
        qs = qs.filter(week_start__gte=week_from)
    if week_to:
        qs = qs.filter(week_start__lte=week_to)
    if search:
        qs = qs.filter(
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search) |
            Q(employee__email__icontains=search)
        )

    qs = qs.order_by('-week_start', 'employee__first_name')

    # Summary counts
    total = qs.count()
    pending_count = qs.filter(status='SUBMITTED').count()
    approved_count = qs.filter(status='APPROVED').count()
    draft_count = qs.filter(status='DRAFT').count()

    employees = User.objects.filter(company=company, role='EMPLOYEE').order_by('first_name')

    base_template = 'ems/base_employee.html' if user.role == 'EMPLOYEE' else 'ems/base_employer.html'
    context = {
        'timesheets': qs,
        'total': total,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'draft_count': draft_count,
        'employees': employees,
        'status_filter': status_filter,
        'employee_filter': employee_filter,
        'week_from': week_from,
        'week_to': week_to,
        'search': search,
        'is_hr': is_hr,
        'is_accountant': is_accountant,
        'base_template': base_template,
    }
    context.update(_get_employer_nav_context(user))
    return render(request, 'ems/timesheets_list.html', context)


@login_required
def timesheet_detail(request, timesheet_id):
    """HR / Accountant: view a single timesheet and approve / reject it."""
    from blu_staff.apps.payroll.models import Timesheet
    from django.utils import timezone

    user = request.user
    is_hr = (user.role == 'EMPLOYEE' and hasattr(user, 'employee_profile') and
             user.employee_profile.employee_role == 'HR')
    is_accountant = (user.role == 'EMPLOYEE' and hasattr(user, 'employee_profile') and
                     user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS'])
    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']

    if not (is_hr or is_accountant or is_admin):
        return render(request, 'ems/unauthorized.html', status=403)

    company = getattr(user, 'company', None)
    timesheet = get_object_or_404(Timesheet, id=timesheet_id, employee__company=company)
    entries = timesheet.entries.order_by('date')

    base_template = 'ems/base_employee.html' if user.role == 'EMPLOYEE' else 'ems/base_employer.html'
    context = {
        'timesheet': timesheet,
        'entries': entries,
        'can_approve': (is_hr or is_admin) and timesheet.status == 'SUBMITTED',
        'base_template': base_template,
    }
    context.update(_get_employer_nav_context(user))
    return render(request, 'ems/timesheet_detail.html', context)


@login_required
def timesheet_action(request, timesheet_id):
    """HR: approve or reject a submitted timesheet."""
    from blu_staff.apps.payroll.models import Timesheet
    from django.utils import timezone

    if request.method != 'POST':
        return redirect('timesheets_list')

    user = request.user
    is_hr = (user.role == 'EMPLOYEE' and hasattr(user, 'employee_profile') and
             user.employee_profile.employee_role == 'HR')
    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']

    if not (is_hr or is_admin):
        return render(request, 'ems/unauthorized.html', status=403)

    company = getattr(user, 'company', None)
    timesheet = get_object_or_404(Timesheet, id=timesheet_id, employee__company=company)

    action = request.POST.get('action', '')
    if action == 'approve' and timesheet.status == 'SUBMITTED':
        timesheet.status = 'APPROVED'
        timesheet.reviewed_by = user
        timesheet.reviewed_at = timezone.now()
        timesheet.rejection_reason = ''
        timesheet.save()
        try:
            from blu_staff.apps.notifications.models import Notification
            Notification.objects.create(
                recipient=timesheet.employee,
                sender=user,
                title='Timesheet Approved',
                message=f'Your timesheet for w/c {timesheet.week_start} has been approved.',
                notification_type='SYSTEM',
            )
        except Exception:
            pass
        messages.success(request, 'Timesheet approved.')
    elif action == 'reject' and timesheet.status == 'SUBMITTED':
        reason = request.POST.get('rejection_reason', '').strip()
        timesheet.status = 'REJECTED'
        timesheet.reviewed_by = user
        timesheet.reviewed_at = timezone.now()
        timesheet.rejection_reason = reason
        timesheet.save()
        try:
            from blu_staff.apps.notifications.models import Notification
            Notification.objects.create(
                recipient=timesheet.employee,
                sender=user,
                title='Timesheet Rejected',
                message=f'Your timesheet for w/c {timesheet.week_start} was rejected. {reason}',
                notification_type='SYSTEM',
            )
        except Exception:
            pass
        messages.warning(request, 'Timesheet rejected.')
    else:
        messages.error(request, 'Invalid action or timesheet not in submitted state.')

    return redirect('timesheet_detail', timesheet_id=timesheet_id)


@login_required
def employee_timesheet(request):
    """Employee: view own timesheets and submit a new one."""
    from blu_staff.apps.payroll.models import Timesheet, TimesheetEntry
    from django.utils import timezone
    from datetime import date, timedelta
    from decimal import Decimal

    if request.user.role != 'EMPLOYEE':
        return redirect('role_hub')

    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action', 'submit')
        week_start_str = request.POST.get('week_start', '')
        try:
            week_start = date.fromisoformat(week_start_str)
            # Ensure it's a Monday
            week_start = week_start - timedelta(days=week_start.weekday())
        except (ValueError, TypeError):
            messages.error(request, 'Invalid week start date.')
            return redirect('employee_timesheet')

        ts, created = Timesheet.objects.get_or_create(
            employee=user,
            week_start=week_start,
            defaults={'status': 'DRAFT'},
        )
        if ts.status in ['APPROVED']:
            messages.error(request, 'Cannot edit an approved timesheet.')
            return redirect('employee_timesheet')

        # Save daily entries
        ts.total_regular_hours = Decimal('0')
        ts.total_overtime_hours = Decimal('0')
        ts.entries.all().delete()

        for i in range(7):
            day = week_start + timedelta(days=i)
            reg = request.POST.get(f'regular_{i}', '0') or '0'
            ot = request.POST.get(f'overtime_{i}', '0') or '0'
            desc = request.POST.get(f'desc_{i}', '')
            try:
                reg_h = Decimal(reg)
                ot_h = Decimal(ot)
            except Exception:
                reg_h = Decimal('0')
                ot_h = Decimal('0')
            if reg_h > 0 or ot_h > 0 or desc:
                TimesheetEntry.objects.create(
                    timesheet=ts, date=day,
                    regular_hours=reg_h, overtime_hours=ot_h,
                    description=desc,
                )
                ts.total_regular_hours += reg_h
                ts.total_overtime_hours += ot_h

        ts.notes = request.POST.get('notes', '')
        if action == 'submit':
            ts.status = 'SUBMITTED'
            ts.submitted_at = timezone.now()
            messages.success(request, f'Timesheet for w/c {week_start} submitted for approval.')
        else:
            ts.status = 'DRAFT'
            messages.success(request, 'Timesheet saved as draft.')
        ts.save()
        return redirect('employee_timesheet')

    # GET: list own timesheets
    my_timesheets = Timesheet.objects.filter(employee=user).order_by('-week_start')[:20]

    # Default week_start = this Monday
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())

    context = {
        'my_timesheets': my_timesheets,
        'this_monday': this_monday,
        'week_days': [(this_monday + timedelta(days=i)) for i in range(7)],
        'base_template': 'ems/base_employee.html',
    }
    return render(request, 'ems/employee_timesheet.html', context)


# ============================================================================
# TO-DO / TASK MODULE
# ============================================================================

@login_required
def tasks_list(request):
    """Kanban task board — personal + shared company tasks."""
    from ems_project.models import Task
    from django.utils import timezone

    user = request.user
    company = getattr(user, 'company', None)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create':
            title = request.POST.get('title', '').strip()
            if title:
                Task.objects.create(
                    title=title,
                    description=request.POST.get('description', ''),
                    created_by=user,
                    assigned_to_id=request.POST.get('assigned_to') or None,
                    due_date=request.POST.get('due_date') or None,
                    priority=request.POST.get('priority', 'MEDIUM'),
                    status=request.POST.get('status', 'TODO'),
                    is_private=request.POST.get('is_private') == 'on',
                )
                messages.success(request, 'Task created.')
            return redirect('tasks_list')

        if action == 'update_status':
            task_id = request.POST.get('task_id')
            new_status = request.POST.get('status')
            try:
                task = Task.objects.get(id=task_id, created_by__company=company)
                task.status = new_status
                if new_status == 'DONE':
                    task.completed_at = timezone.now()
                else:
                    task.completed_at = None
                task.save()
            except Task.DoesNotExist:
                pass
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'ok': True})
            return redirect('tasks_list')

        if action == 'delete':
            task_id = request.POST.get('task_id')
            Task.objects.filter(id=task_id, created_by=user).delete()
            messages.success(request, 'Task deleted.')
            return redirect('tasks_list')

    # GET — build kanban columns
    from django.db.models import Q
    base_qs = Task.objects.filter(
        Q(created_by__company=company, is_private=False) |
        Q(created_by=user) |
        Q(assigned_to=user)
    ).distinct().select_related('created_by', 'assigned_to')

    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    mine_only = request.GET.get('mine', '') == '1'

    qs = base_qs
    if status_filter:
        qs = qs.filter(status=status_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
    if mine_only:
        qs = qs.filter(Q(created_by=user) | Q(assigned_to=user))

    todo_tasks       = qs.filter(status='TODO').order_by('-priority', 'due_date')
    inprogress_tasks = qs.filter(status='IN_PROGRESS').order_by('-priority', 'due_date')
    done_tasks       = qs.filter(status='DONE').order_by('-completed_at')[:20]

    employees = User.objects.filter(company=company, role='EMPLOYEE').order_by('first_name')

    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    base_template = 'ems/base_employer.html' if is_admin else 'ems/base_employee.html'

    context = {
        'todo_tasks': todo_tasks,
        'inprogress_tasks': inprogress_tasks,
        'done_tasks': done_tasks,
        'employees': employees,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'mine_only': mine_only,
        'total_todo': todo_tasks.count(),
        'total_inprogress': inprogress_tasks.count(),
        'base_template': base_template,
    }
    if is_admin:
        context.update(_get_employer_nav_context(user))
    return render(request, 'ems/tasks_list.html', context)


@login_required
def task_detail_update(request, task_id):
    """Edit a task inline (POST only)."""
    from ems_project.models import Task
    from django.utils import timezone

    company = getattr(request.user, 'company', None)
    task = get_object_or_404(Task, id=task_id, created_by__company=company)

    if request.method == 'POST':
        task.title       = request.POST.get('title', task.title).strip()
        task.description = request.POST.get('description', task.description)
        task.priority    = request.POST.get('priority', task.priority)
        task.status      = request.POST.get('status', task.status)
        task.due_date    = request.POST.get('due_date') or None
        task.assigned_to_id = request.POST.get('assigned_to') or None
        task.is_private  = request.POST.get('is_private') == 'on'
        if task.status == 'DONE' and not task.completed_at:
            task.completed_at = timezone.now()
        elif task.status != 'DONE':
            task.completed_at = None
        task.save()
        messages.success(request, 'Task updated.')
    return redirect('tasks_list')


# ============================================================================
# CALENDAR MODULE
# ============================================================================

@login_required
def calendar_view(request):
    """Main calendar page (FullCalendar.js renders the UI)."""
    user = request.user
    company = getattr(user, 'company', None)
    employees = User.objects.filter(company=company, role='EMPLOYEE').order_by('first_name')
    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    base_template = 'ems/base_employer.html' if is_admin else 'ems/base_employee.html'
    context = {
        'employees': employees,
        'base_template': base_template,
        'is_admin': is_admin,
    }
    if is_admin:
        context.update(_get_employer_nav_context(user))
    return render(request, 'ems/calendar.html', context)


@login_required
def calendar_events_json(request):
    """JSON feed for FullCalendar — merges CalendarEvent + Leave + Payroll dates."""
    from ems_project.models import CalendarEvent
    from django.http import JsonResponse
    from django.db.models import Q

    user = request.user
    company = getattr(user, 'company', None)

    start = request.GET.get('start', '')
    end   = request.GET.get('end', '')

    events = []

    # 1. CalendarEvent objects
    qs = CalendarEvent.objects.filter(
        Q(created_by__company=company, is_company_wide=True) |
        Q(created_by=user) |
        Q(attendees=user)
    ).distinct()
    if start:
        qs = qs.filter(end__gte=start) if end else qs.filter(start__gte=start)
    if end:
        qs = qs.filter(start__lte=end)

    type_colors = {
        'MEETING': '#1d4ed8', 'DEADLINE': '#dc2626',
        'REMINDER': '#d97706', 'HOLIDAY': '#059669', 'OTHER': '#64748b',
    }
    for ev in qs:
        events.append({
            'id': f'cal_{ev.id}',
            'title': ev.title,
            'start': ev.start.isoformat(),
            'end': ev.end.isoformat() if ev.end else None,
            'allDay': ev.all_day,
            'color': ev.color or type_colors.get(ev.event_type, '#1d4ed8'),
            'extendedProps': {
                'type': ev.event_type,
                'description': ev.description,
                'location': ev.location,
                'editable': ev.created_by_id == user.id,
            },
        })

    # 2. Leave requests (approved)
    try:
        from blu_staff.apps.attendance.models import LeaveRequest
        leave_qs = LeaveRequest.objects.filter(
            employee__company=company, status='APPROVED'
        ).select_related('employee')
        if start:
            leave_qs = leave_qs.filter(end_date__gte=start[:10])
        if end:
            leave_qs = leave_qs.filter(start_date__lte=end[:10])
        for lr in leave_qs:
            events.append({
                'id': f'leave_{lr.id}',
                'title': f'{lr.employee.get_full_name()} — Leave',
                'start': str(lr.start_date),
                'end': str(lr.end_date),
                'allDay': True,
                'color': '#6366f1',
                'extendedProps': {'type': 'leave', 'editable': False},
            })
    except Exception:
        pass

    # 3. Payroll pay dates
    try:
        from blu_staff.apps.payroll.models import Payroll
        payroll_qs = Payroll.objects.filter(
            employee__company=company, status='PAID'
        )
        if start:
            payroll_qs = payroll_qs.filter(pay_date__gte=start[:10])
        if end:
            payroll_qs = payroll_qs.filter(pay_date__lte=end[:10])
        seen_dates = set()
        for p in payroll_qs:
            if p.pay_date and str(p.pay_date) not in seen_dates:
                seen_dates.add(str(p.pay_date))
                events.append({
                    'id': f'pay_{p.id}',
                    'title': 'Payroll — Pay Day',
                    'start': str(p.pay_date),
                    'allDay': True,
                    'color': '#059669',
                    'extendedProps': {'type': 'payroll', 'editable': False},
                })
    except Exception:
        pass

    return JsonResponse(events, safe=False)


@login_required
def calendar_event_save(request):
    """Create or update a CalendarEvent (AJAX POST)."""
    from ems_project.models import CalendarEvent
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    user = request.user
    company = getattr(user, 'company', None)
    event_id = request.POST.get('event_id')

    if event_id:
        ev = get_object_or_404(CalendarEvent, id=event_id, created_by__company=company)
    else:
        ev = CalendarEvent(created_by=user)

    ev.title       = request.POST.get('title', '').strip() or 'Untitled'
    ev.description = request.POST.get('description', '')
    ev.event_type  = request.POST.get('event_type', 'OTHER')
    ev.location    = request.POST.get('location', '')
    ev.color       = request.POST.get('color', '#1d4ed8')
    ev.all_day     = request.POST.get('all_day') == 'true'
    ev.is_company_wide = request.POST.get('is_company_wide') == 'on'

    try:
        from django.utils.dateparse import parse_datetime, parse_date
        start_val = request.POST.get('start', '')
        end_val   = request.POST.get('end', '')
        ev.start = parse_datetime(start_val) or parse_date(start_val)
        ev.end   = parse_datetime(end_val) or parse_date(end_val) if end_val else None
    except Exception:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    ev.save()

    attendee_ids = request.POST.getlist('attendees')
    if attendee_ids:
        ev.attendees.set(User.objects.filter(id__in=attendee_ids, company=company))

    return JsonResponse({'ok': True, 'id': ev.id, 'title': ev.title})


@login_required
def calendar_event_delete(request, event_id):
    """Delete a CalendarEvent (POST only)."""
    from ems_project.models import CalendarEvent
    from django.http import JsonResponse

    if request.method != 'POST':
        return redirect('calendar_view')

    ev = get_object_or_404(CalendarEvent, id=event_id, created_by=request.user)
    ev.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    messages.success(request, 'Event deleted.')
    return redirect('calendar_view')


# ============================================================================
# FILE MANAGER
# ============================================================================

@login_required
def file_manager(request):
    """Two-panel file manager: folder tree left, files right."""
    from ems_project.models import FileFolder, CompanyFile
    from django.db.models import Q

    user = request.user
    company = getattr(user, 'company', None)
    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']

    folder_id = request.GET.get('folder')
    current_folder = None
    if folder_id:
        try:
            current_folder = FileFolder.objects.get(
                id=folder_id, created_by__company=company
            )
        except FileFolder.DoesNotExist:
            pass

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create_folder':
            name = request.POST.get('name', '').strip()
            parent_id = request.POST.get('parent_id') or None
            if name:
                FileFolder.objects.get_or_create(
                    name=name,
                    parent_id=parent_id,
                    created_by=user,
                    defaults={'is_shared': request.POST.get('is_shared') == 'on'},
                )
                messages.success(request, f'Folder "{name}" created.')
            return redirect(request.get_full_path())

        if action == 'upload':
            uploaded = request.FILES.get('file')
            if uploaded:
                cf = CompanyFile(
                    name=request.POST.get('name', '').strip() or uploaded.name,
                    file=uploaded,
                    folder=current_folder,
                    uploaded_by=user,
                    description=request.POST.get('description', ''),
                    is_shared=request.POST.get('is_shared') == 'on',
                    original_filename=uploaded.name,
                    file_size=uploaded.size,
                    mime_type=getattr(uploaded, 'content_type', 'application/octet-stream'),
                )
                cf.save()
                messages.success(request, f'"{cf.name}" uploaded.')
            return redirect(request.get_full_path())

        if action == 'delete_file':
            file_id = request.POST.get('file_id')
            CompanyFile.objects.filter(
                id=file_id, uploaded_by__company=company
            ).delete()
            messages.success(request, 'File deleted.')
            return redirect(request.get_full_path())

        if action == 'delete_folder':
            fid = request.POST.get('folder_id')
            FileFolder.objects.filter(
                id=fid, created_by__company=company
            ).delete()
            messages.success(request, 'Folder deleted.')
            return redirect(f'/files/')

    # Root folders (no parent)
    root_folders = FileFolder.objects.filter(
        created_by__company=company, parent__isnull=True
    ).prefetch_related('children')

    # Files in current folder (or root if none)
    files_qs = CompanyFile.objects.filter(
        uploaded_by__company=company, folder=current_folder
    ).select_related('uploaded_by')

    # Breadcrumb path
    breadcrumbs = []
    if current_folder:
        node = current_folder
        while node:
            breadcrumbs.insert(0, node)
            node = node.parent

    # Sub-folders of current folder
    sub_folders = FileFolder.objects.filter(
        created_by__company=company, parent=current_folder
    )

    search = request.GET.get('q', '')
    if search:
        files_qs = CompanyFile.objects.filter(
            uploaded_by__company=company,
            name__icontains=search,
        ).select_related('uploaded_by')
        sub_folders = FileFolder.objects.none()

    base_template = 'ems/base_employer.html' if is_admin else 'ems/base_employee.html'
    context = {
        'root_folders': root_folders,
        'sub_folders': sub_folders,
        'files': files_qs,
        'current_folder': current_folder,
        'breadcrumbs': breadcrumbs,
        'search': search,
        'is_admin': is_admin,
        'base_template': base_template,
    }
    if is_admin:
        context.update(_get_employer_nav_context(user))
    return render(request, 'ems/file_manager.html', context)


# ============================================================================
# SOCIAL FEED
# ============================================================================

FEED_EMOJIS = ['👍', '❤️', '😂', '🎉', '👏', '🔥']


@login_required
def social_feed(request):
    """Company social board — any employee can post, react, and comment."""
    from django.http import JsonResponse
    from ems_project.models import FeedPost, FeedPostReaction, FeedPostComment
    from django.db.models import Prefetch

    user = request.user
    company = _get_user_company(user)
    # TenantScopedModel requires a Tenant instance, not Company
    tenant = getattr(company, 'tenant', None) if company else None
    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Create post ────────────────────────────────────────────────────
        if action == 'post':
            body = request.POST.get('body', '').strip()
            if not body:
                messages.error(request, 'Post body cannot be empty.')
                return redirect('social_feed')
            post = FeedPost(author=user, body=body, tenant=tenant)
            if request.FILES.get('image'):
                post.image = request.FILES['image']
            if request.FILES.get('attachment'):
                f = request.FILES['attachment']
                post.attachment = f
                post.attachment_name = f.name
            post.save()
            if is_ajax:
                return JsonResponse({'ok': True, 'post_id': post.id})
            return redirect('social_feed')

        # ── React (toggle) ─────────────────────────────────────────────────
        if action == 'react':
            post_id = request.POST.get('post_id')
            emoji = request.POST.get('emoji', '👍')
            try:
                post = FeedPost.objects.get(id=post_id, tenant=tenant)
                reaction, created = FeedPostReaction.objects.get_or_create(
                    post=post, user=user, emoji=emoji,
                    defaults={'tenant': tenant},
                )
                if not created:
                    reaction.delete()
                    reacted = False
                else:
                    reacted = True
                count = FeedPostReaction.objects.filter(post=post, emoji=emoji).count()
                return JsonResponse({'ok': True, 'reacted': reacted, 'count': count})
            except FeedPost.DoesNotExist:
                return JsonResponse({'error': 'Not found'}, status=404)

        # ── Add comment ────────────────────────────────────────────────────
        if action == 'comment':
            post_id = request.POST.get('post_id')
            body = request.POST.get('body', '').strip()
            parent_id = request.POST.get('parent_id')
            if not body:
                return JsonResponse({'error': 'Empty'}, status=400)
            try:
                post = FeedPost.objects.get(id=post_id, tenant=tenant)
                parent = None
                if parent_id:
                    try:
                        parent = FeedPostComment.objects.get(id=parent_id, post=post)
                    except FeedPostComment.DoesNotExist:
                        pass
                comment = FeedPostComment.objects.create(
                    post=post, author=user, body=body, tenant=tenant, parent=parent,
                )
                initials = (user.first_name[:1] + user.last_name[:1]).upper() or '?'
                return JsonResponse({
                    'ok': True,
                    'id': comment.id,
                    'author': user.get_full_name() or user.username,
                    'initials': initials,
                    'body': comment.body,
                    'created_at': comment.created_at.strftime('%b %d, %H:%M'),
                    'is_reply': parent is not None,
                    'parent_id': parent.id if parent else None,
                })
            except FeedPost.DoesNotExist:
                return JsonResponse({'error': 'Not found'}, status=404)

        # ── Delete comment ─────────────────────────────────────────────────
        if action == 'delete_comment':
            comment_id = request.POST.get('comment_id')
            try:
                comment = FeedPostComment.objects.get(id=comment_id, tenant=tenant)
                if comment.author == user or is_admin:
                    comment.delete()
                    return JsonResponse({'ok': True})
                return JsonResponse({'error': 'Forbidden'}, status=403)
            except FeedPostComment.DoesNotExist:
                return JsonResponse({'error': 'Not found'}, status=404)

        # ── Pin / unpin (admin only) ────────────────────────────────────────
        if action == 'pin' and is_admin:
            post_id = request.POST.get('post_id')
            try:
                post = FeedPost.objects.get(id=post_id, tenant=tenant)
                post.is_pinned = not post.is_pinned
                post.save(update_fields=['is_pinned'])
                return JsonResponse({'ok': True, 'pinned': post.is_pinned})
            except FeedPost.DoesNotExist:
                return JsonResponse({'error': 'Not found'}, status=404)

    # ── GET: paginated feed ────────────────────────────────────────────────
    page = int(request.GET.get('page', 1))
    per_page = 12
    offset = (page - 1) * per_page

    posts_qs = FeedPost.objects.filter(tenant=tenant).select_related('author').prefetch_related(
        Prefetch('comments', queryset=FeedPostComment.objects.filter(parent=None).select_related('author').prefetch_related(
            Prefetch('replies', queryset=FeedPostComment.objects.select_related('author'))
        )),
        Prefetch('reactions', queryset=FeedPostReaction.objects.select_related('user')),
    )
    total = posts_qs.count()
    posts = list(posts_qs[offset:offset + per_page])

    # Build per-user reaction lookup: {(post_id, emoji): True}
    my_reactions = set(
        FeedPostReaction.objects.filter(
            post__in=posts, user=user
        ).values_list('post_id', 'emoji')
    )

    # Build reaction summary per post: {post_id: {emoji: count}}
    reaction_summary = {}
    for post in posts:
        summary = {}
        for r in post.reactions.all():
            summary[r.emoji] = summary.get(r.emoji, 0) + 1
        reaction_summary[post.id] = summary

    import json
    # Serialize for JS: reaction_summary → {str(post_id): {emoji: count}}
    reaction_summary_js = {str(k): v for k, v in reaction_summary.items()}
    # my_reactions → ["post_id::emoji", ...]
    my_reactions_js = [f"{pid}::{emoji}" for pid, emoji in my_reactions]

    base_template = 'ems/base_employer.html' if is_admin else 'ems/base_employee.html'
    context = {
        'posts': posts,
        'my_reactions': my_reactions,
        'reaction_summary': reaction_summary,
        'reaction_summary_json': json.dumps(reaction_summary_js),
        'my_reactions_json': json.dumps(my_reactions_js),
        'page': page,
        'has_next': (offset + per_page) < total,
        'is_admin': is_admin,
        'base_template': base_template,
        'EMOJIS': FEED_EMOJIS,
    }
    if is_admin:
        context.update(_get_employer_nav_context(user))
    return render(request, 'ems/social_feed.html', context)


@login_required
def feed_post_delete(request, post_id):
    """Delete a feed post — author or admin only."""
    from ems_project.models import FeedPost
    company = _get_user_company(request.user)
    tenant = getattr(company, 'tenant', None) if company else None
    is_admin = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    try:
        post = FeedPost.objects.get(id=post_id, tenant=tenant)
        if post.author == request.user or is_admin:
            post.delete()
            messages.success(request, 'Post deleted.')
        else:
            messages.error(request, 'You cannot delete this post.')
    except FeedPost.DoesNotExist:
        messages.error(request, 'Post not found.')
    return redirect('social_feed')


# ============================================================================
# CHAT UI (POLISHED + GROUP CHAT)
# ============================================================================

@login_required
def chat_home(request):
    """Chat home — lists conversations and group rooms."""
    from blu_staff.apps.communication.models import DirectMessage

    user = request.user
    company = getattr(user, 'company', None)
    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']

    # Latest DM per contact
    from django.db.models import Q, Max, Subquery, OuterRef
    contacts_qs = User.objects.filter(
        company=company
    ).exclude(id=user.id).order_by('first_name')

    # Build recent conversations with last message + unread
    recent = []
    for contact in contacts_qs:
        last_msg = DirectMessage.objects.filter(
            Q(sender=user, recipient=contact) |
            Q(sender=contact, recipient=user)
        ).order_by('-created_at').first()
        if last_msg:
            unread = DirectMessage.objects.filter(
                sender=contact, recipient=user, is_read=False
            ).count()
            recent.append({
                'user': contact,
                'last_msg': last_msg,
                'unread': unread,
            })

    recent.sort(key=lambda x: x['last_msg'].created_at, reverse=True)

    # Auto-open the most recent conversation instead of blank "Select a conversation"
    if recent:
        from django.shortcuts import redirect as _redirect
        return _redirect('chat_conversation', user_id=recent[0]['user'].id)

    base_template = 'ems/base_employer.html' if is_admin else 'ems/base_employee.html'
    context = {
        'recent': recent,
        'all_contacts': contacts_qs,
        'base_template': base_template,
        'is_admin': is_admin,
    }
    if is_admin:
        context.update(_get_employer_nav_context(user))
    return render(request, 'ems/chat_home.html', context)


@login_required
def chat_conversation(request, user_id):
    """DM thread with polling refresh — replaces direct_message_conversation."""
    from blu_staff.apps.communication.models import DirectMessage
    from django.db.models import Q

    user = request.user
    company = getattr(user, 'company', None)
    other = get_object_or_404(User, id=user_id, company=company)
    is_admin = user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']

    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            DirectMessage.objects.create(
                sender=user, recipient=other, content=body,
            )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'ok': True})
        return redirect('chat_conversation', user_id=other.id)

    # Poll endpoint — return only new messages since given ID
    since_id = request.GET.get('since')
    msgs_qs = DirectMessage.objects.filter(
        Q(sender=user, recipient=other) | Q(sender=other, recipient=user)
    ).order_by('created_at')

    if since_id and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        new_msgs = msgs_qs.filter(id__gt=since_id)
        msgs_qs.filter(sender=other, recipient=user, is_read=False).update(is_read=True)
        return JsonResponse([{
            'id': m.id,
            'body': m.content,
            'mine': m.sender_id == user.id,
            'sender': m.sender.get_full_name(),
            'time': m.created_at.strftime('%H:%M'),
        } for m in new_msgs], safe=False)

    # Mark as read
    msgs_qs.filter(sender=other, recipient=user, is_read=False).update(is_read=True)
    messages_list = list(msgs_qs.select_related('sender', 'recipient'))
    last_id = messages_list[-1].id if messages_list else 0

    # Build recent conversations sidebar (same as chat_home)
    from django.db.models import Q as _Q
    from blu_staff.apps.communication.models import DirectMessage as _DM
    contacts_qs = User.objects.filter(company=company).exclude(id=user.id).order_by('first_name')
    recent = []
    for contact in contacts_qs:
        last_msg = _DM.objects.filter(
            _Q(sender=user, recipient=contact) | _Q(sender=contact, recipient=user)
        ).order_by('-created_at').first()
        if last_msg:
            unread = _DM.objects.filter(sender=contact, recipient=user, is_read=False).count()
            recent.append({'user': contact, 'last_msg': last_msg, 'unread': unread})
    recent.sort(key=lambda x: x['last_msg'].created_at, reverse=True)
    # Also show contacts with no messages at all
    contacted_ids = {r['user'].id for r in recent}
    for contact in contacts_qs:
        if contact.id not in contacted_ids:
            recent.append({'user': contact, 'last_msg': None, 'unread': 0})

    base_template = 'ems/base_employer.html' if is_admin else 'ems/base_employee.html'
    context = {
        'other': other,
        'messages_list': messages_list,
        'last_id': last_id,
        'recent': recent,
        'base_template': base_template,
        'is_admin': is_admin,
    }
    if is_admin:
        context.update(_get_employer_nav_context(user))
    return render(request, 'ems/chat_conversation.html', context)


@csrf_protect
def company_registration_request(request):
    """Handle company registration requests"""
    if request.method == 'POST':
        form = CompanyRegistrationRequestForm(request.POST)
        if form.is_valid():
            try:
                registration = form.save()
                messages.success(request, 'Your registration request has been submitted successfully!')
                return redirect('registration_success', request_id=registration.id)
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
        else:
            logger.error(f"Form errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CompanyRegistrationRequestForm()
    
    return render(request, 'ems/company_registration.html', {'form': form})

def registration_success(request, request_id):
    """Show registration success page"""
    try:
        from blu_staff.apps.accounts.models import CompanyRegistrationRequest
        registration = CompanyRegistrationRequest.objects.get(id=request_id)
        return render(request, 'ems/registration_success.html', {'registration': registration})
    except CompanyRegistrationRequest.DoesNotExist:
        messages.error(request, 'Invalid registration request ID')
        return redirect('register')

@login_required

def registration_detail(request, request_id):
    """View full details of a company registration request before approving/rejecting"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.accounts.models import CompanyRegistrationRequest
    try:
        registration = CompanyRegistrationRequest.objects.get(id=request_id)
    except CompanyRegistrationRequest.DoesNotExist:
        messages.error(request, 'Registration request not found')
        return redirect('superadmin_tenants')

    return render(request, 'ems/admin/registration_detail.html', {
        'registration': registration
    })


def company_registration_list(request):
    """List all company registration requests (for admin)"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')
    
    from blu_staff.apps.accounts.models import CompanyRegistrationRequest
    registrations = CompanyRegistrationRequest.objects.all().order_by('-created_at')
    return render(request, 'ems/admin/company_registrations.html', {'registrations': registrations})

@login_required
def approve_company_registration(request, request_id):
    """Approve a company registration request - creates tenant + admin user"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    from blu_staff.apps.accounts.models import CompanyRegistrationRequest, Company, User
    import secrets, string
    from datetime import date, timedelta

    try:
        registration = CompanyRegistrationRequest.objects.get(id=request_id)
    except CompanyRegistrationRequest.DoesNotExist:
        messages.error(request, 'Registration request not found')
        return redirect('superadmin_tenants')

    if registration.status == 'APPROVED':
        messages.warning(request, f'{registration.company_name} is already approved.')
        return redirect('superadmin_tenants')

    try:
        # Check if company already exists
        if Company.objects.filter(name=registration.company_name).exists():
            messages.error(request, f'A company named "{registration.company_name}" already exists.')
            return redirect('registration_detail', request_id=request_id)

        # Check if admin user email already exists
        if User.objects.filter(email=registration.contact_email).exists():
            messages.error(request, f'A user with email "{registration.contact_email}" already exists.')
            return redirect('registration_detail', request_id=request_id)

        # Generate a secure temporary password
        alphabet = string.ascii_letters + string.digits + '!@#$%'
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        # Create the Company
        company = Company.objects.create(
            name=registration.company_name,
            email=registration.company_email,
            phone=registration.company_phone or '',
            address=registration.company_address or '',
            city=registration.city or '',
            country=registration.country or '',
            website=registration.company_website or '',
            tax_id=registration.tax_id or '',
            subscription_plan=registration.subscription_plan,
            is_active=True,
            is_approved=True,
            approved_by=request.user,
            registration_request=registration,
            is_trial=True,
            trial_ends_at=__import__('django.utils.timezone', fromlist=['now']).now() + timedelta(days=30),
            max_employees=registration.number_of_employees or 10,
        )

        # Create the admin user
        admin_user = User.objects.create_user(
            email=registration.contact_email,
            password=temp_password,
            first_name=registration.contact_first_name,
            last_name=registration.contact_last_name,
            role='ADMINISTRATOR',
            company=company,
            must_change_password=True,
            is_active=True,
        )

        # Mark registration as approved
        from django.utils import timezone
        registration.status = 'APPROVED'
        registration.reviewed_by = request.user
        registration.reviewed_at = timezone.now()
        registration.save()

        # Set approved_at on company
        company.approved_at = timezone.now()
        company.save(update_fields=['approved_at'])

        # Try to send welcome email (may fail if SMTP blocked)
        email_sent = False
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject=f'Welcome to BLU Suite EMS - {registration.company_name}',
                message=f"""Dear {registration.contact_first_name},

Your company registration for {registration.company_name} has been approved!

Your login credentials:
  Email: {registration.contact_email}
  Password: {temp_password}

Please login at: http://161.35.192.144/
You will be prompted to change your password on first login.

Best regards,
BLU Suite EMS Team""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[registration.contact_email],
                fail_silently=False,
            )
            email_sent = True
        except Exception:
            email_sent = False

        # Store credentials in session for display on success page
        request.session['approval_success'] = {
            'company_name': registration.company_name,
            'contact_name': f'{registration.contact_first_name} {registration.contact_last_name}',
            'contact_email': registration.contact_email,
            'temp_password': temp_password,
            'email_sent': email_sent,
            'company_id': company.id,
        }

        return redirect('approval_success')

    except Exception as e:
        logger.error(f"Error approving registration {request_id}: {e}", exc_info=True)
        messages.error(request, f'Error approving registration: {str(e)}')
        return redirect('registration_detail', request_id=request_id)


def approval_success(request):
    """Show approval success page with generated credentials"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    data = request.session.pop('approval_success', None)
    if not data:
        return redirect('superadmin_tenants')

    return render(request, 'ems/admin/approval_success.html', {'data': data})


@login_required
def reject_company_registration(request, request_id):
    """Reject a company registration request"""
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        from blu_staff.apps.accounts.models import CompanyRegistrationRequest
        registration = CompanyRegistrationRequest.objects.get(id=request_id)
        registration.status = 'REJECTED'
        registration.save()
        messages.success(request, f'Registration for {registration.company_name} has been rejected')
    except CompanyRegistrationRequest.DoesNotExist:
        messages.error(request, 'Registration request not found')
    
    return redirect('company_registration_list')

def superadmin_login(request):
    """SuperAdmin login at eiscomtech URL - exclusive access"""
    if request.method == 'GET':
        if request.user.is_authenticated and hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
            return redirect('/dashboard/')
        from django.contrib import messages
        storage = messages.get_messages(request)
        storage.used = True
        return render(request, 'ems/superadmin_login.html')
    elif request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')
        if not email or not password:
            messages.error(request, 'Please enter both email and password')
            return render(request, 'ems/superadmin_login.html', {'error': 'Please enter both email and password'})
        user = authenticate(request, username=email, password=password)
        if not user or not user.is_active or user.role != 'SUPERADMIN':
            messages.error(request, 'Invalid SuperAdmin credentials or account is disabled.')
            return render(request, 'ems/superadmin_login.html')
        finalize_login_session(request, user)
        request.session['is_superadmin'] = True
        return redirect('/dashboard/')
    return HttpResponseNotAllowed(['GET', 'POST'])
