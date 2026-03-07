"""
URL configuration for ems_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.shortcuts import redirect
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf.urls.static import static

from . import frontend_views, auth_views
from blu_staff.apps.accounts import views as account_views

schema_view = get_schema_view(
    openapi.Info(
        title="Employee Management System API",
        default_version='v1',
        description="API for Employee Management System",
        terms_of_service="https://www.yourapp.com/terms/",
        contact=openapi.Contact(email="contact@yourapp.com"),
        license=openapi.License(name="Your License"),
    ),
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Frontend pages - Landing page at root
    path('', frontend_views.landing_page, name='landing_page'),  # Proper landing page
    path('about/', frontend_views.about_page, name='about_page'),
    path('features/', frontend_views.features_page, name='features_page'),
    path('features/attendance/', frontend_views.feature_attendance_page, name='feature_attendance'),
    path('features/leave/', frontend_views.feature_leave_page, name='feature_leave'),
    path('features/payroll/', frontend_views.feature_payroll_page, name='feature_payroll'),
    path('features/performance/', frontend_views.feature_performance_page, name='feature_performance'),
    path('features/documents/', frontend_views.feature_documents_page, name='feature_documents'),
    path('features/analytics/', frontend_views.feature_analytics_page, name='feature_analytics'),
    path('solutions/', frontend_views.solutions_page, name='solutions_page'),
    path('pricing/', frontend_views.pricing_page, name='pricing_page'),
    path('help/', frontend_views.help_center_page, name='help_center_page'),
    path('contact/', frontend_views.contact_page, name='contact_page'),
    path('status/', frontend_views.status_page, name='status_page'),
    path('docs/', frontend_views.documentation_page, name='documentation_page'),
    path('careers/', frontend_views.careers_page, name='careers_page'),
    path('blog/', frontend_views.blog_page, name='blog_page'),
    path('press/', frontend_views.press_page, name='press_page'),
    # Redirect /login/ to root for better UX
    path('login/', auth_views.general_user_login, name='login'),  # General user login
    # SuperAdmin login at eiscomtech
    path('eiscomtech/', frontend_views.superadmin_login, name='superadmin_login'),
    # Django auth compatibility - redirect to our custom login
    path('accounts/login/', auth_views.general_user_login, name='accounts_login'),

    # Company Registration
    path('register/', frontend_views.company_registration_request, name='company_registration'),
    path('register/success/<str:request_id>/', frontend_views.registration_success, name='registration_success'),
    path('admin/company-requests/', frontend_views.company_registration_list, name='company_registration_list'),
    path('admin/company-requests/<int:request_id>/approve/', frontend_views.approve_company_registration, name='approve_company_registration'),
    path('admin/company-requests/<int:request_id>/reject/', frontend_views.reject_company_registration, name='reject_company_registration'),

    # Auth/session helpers
    path('api/v1/auth/users/me/', frontend_views.api_current_user, name='api_current_user'),

    path('dashboard/', frontend_views.dashboard_redirect, name='dashboard_redirect'),
    path('superadmin/', frontend_views.superadmin_dashboard, name='superadmin_dashboard'),
    path('superadmin/support/', frontend_views.superadmin_support_center, name='superadmin_support_center'),
    path('superadmin/knowledge-base/', frontend_views.superadmin_knowledge_base, name='superadmin_knowledge_base'),
    path('superadmin/knowledge-base/<int:article_id>/delete/', frontend_views.superadmin_knowledge_base_delete, name='superadmin_knowledge_base_delete'),
    path('billing/overview/', frontend_views.superadmin_billing_overview, name='superadmin_billing_overview'),
    # System owner portals (platform roles)
    path('owner/billing/', frontend_views.owner_billing_portal, name='owner_billing_portal'),
    path('owner/support/', frontend_views.owner_support_portal, name='owner_support_portal'),
    path('owner/registration/', frontend_views.company_registration_request, name='owner_registration_portal'),
    path('owner/account-manager/', frontend_views.owner_account_manager_portal, name='owner_account_manager_portal'),
    path('superadmin/settings/', frontend_views.superadmin_settings, name='superadmin_settings'),
    
    # Super Admin Tenant Management
    path('superadmin/tenants/', frontend_views.superadmin_tenants, name='superadmin_tenants'),
    path('tenant/<int:company_id>/', frontend_views.tenant_detail, name='tenant_detail'),
    path('tenant/<int:company_id>/users/', frontend_views.tenant_users, name='tenant_users'),
    path('tenant/<int:company_id>/analytics/', frontend_views.tenant_analytics, name='tenant_analytics'),
    
    # Tenant Management Actions
    path('admin/tenants/<int:company_id>/suspend/', frontend_views.suspend_tenant, name='suspend_tenant'),
    path('admin/tenants/<int:company_id>/announce/', frontend_views.send_announcement, name='send_announcement'),
    path('admin/tenants/<int:company_id>/report/', frontend_views.generate_tenant_report, name='generate_tenant_report'),
    path('admin/tenants/<int:company_id>/export/', frontend_views.export_tenant_data, name='export_tenant_data'),
    path('admin/tenants/<int:company_id>/reset-password/', frontend_views.reset_tenant_password, name='reset_tenant_password'),
    path('employee/', frontend_views.employee_dashboard, name='employee_dashboard'),
    path('employee/suites/', frontend_views.employee_suites, name='employee_suites'),
    path('employee/profile/', frontend_views.employee_profile_view, name='employee_profile'),
    path('employee/my-payslips/', frontend_views.employee_my_payslips, name='employee_my_payslips'),
    path('employee/print-profile/', frontend_views.employee_print_profile, name='employee_print_profile'),
    path('employee/role-hub/', frontend_views.role_hub, name='role_hub'),
    path('employee/hr-send-email/', frontend_views.hr_send_email, name='hr_send_email'),
    path('petty-cash/', frontend_views.petty_cash_dashboard, name='petty_cash_dashboard'),
    path('financial-assets/', frontend_views.financial_assets_view, name='financial_assets'),
    path('financial-analytics/', frontend_views.financial_analytics_view, name='financial_analytics'),
    path('employer/', frontend_views.employer_dashboard, name='employer_dashboard'),
    path('blusuite/', frontend_views.blu_suite_home, name='blu_suite_home'),
    path('blusuite/staff/', frontend_views.blu_staff_home, name='blu_staff_home'),
    path('blusuite/projects/', frontend_views.blu_projects_home, name='blu_projects_home'),
    path('blusuite/assets/', frontend_views.blu_assets_home, name='blu_assets_home'),
    path('blusuite/analytics/', frontend_views.blu_analytics_home, name='blu_analytics_home'),
    path('blusuite/integrations/', frontend_views.blu_integrations_home, name='blu_integrations_home'),
    path('blusuite/settings/', frontend_views.blu_settings_home, name='blu_settings_home'),
    path('blusuite/billing/', frontend_views.blu_billing_home, name='blu_billing_home'),
    path('blusuite/billing/invoice/<int:invoice_id>/pdf/', frontend_views.blu_invoice_pdf, name='blu_invoice_pdf'),
    path('blusuite/support/', frontend_views.blu_support_home, name='blu_support_home'),
    path('employer-admin/', frontend_views.employer_admin_dashboard, name='employer_admin_dashboard'),
    path('attendance/', frontend_views.attendance_dashboard, name='attendance_dashboard'),
    path('attendance/update-status/', frontend_views.update_attendance_status, name='update_attendance_status'),
    path('attendance/bulk-update/', frontend_views.bulk_update_attendance, name='bulk_update_attendance'),
    path('attendance/<int:attendance_id>/edit/', frontend_views.employer_edit_attendance, name='employer_edit_attendance'),
    path('leave/', frontend_views.leave_management, name='leave_management'),
    path('leave/<int:leave_id>/action/', frontend_views.employer_leave_action, name='employer_leave_action'),
    path('leave/<int:leave_id>/detail/', frontend_views.leave_detail_view, name='leave_detail_view'),
    path('leave/bulk-approve/', frontend_views.bulk_approve_leave, name='bulk_approve_leave'),
    path('leave/bulk-reject/', frontend_views.bulk_reject_leave, name='bulk_reject_leave'),
    path('documents/', frontend_views.documents_list, name='documents_list'),
    path('documents/upload/', frontend_views.document_upload, name='document_upload'),
    path('documents/<int:document_id>/download/', frontend_views.document_download, name='document_download'),
    path('documents/<int:document_id>/approve/', frontend_views.document_approve, name='document_approve'),
    path('documents/<int:document_id>/reject/', frontend_views.document_reject, name='document_reject'),
    path('documents/bulk-approve/', frontend_views.bulk_approve_documents, name='bulk_approve_documents'),
    path('documents/bulk-download/', frontend_views.bulk_download_documents, name='bulk_download_documents'),
    path('documents/<int:document_id>/share/', frontend_views.document_share, name='document_share'),
    path('documents/<int:document_id>/delete/', frontend_views.document_delete, name='document_delete'),
    path('employer/employees/<int:employee_id>/documents/upload/', frontend_views.employee_document_upload, name='employee_document_upload'),
    path('employer/employees/<int:employee_id>/profile-picture/upload/', frontend_views.employee_profile_picture_upload_redirect, name='employee_profile_picture_upload_with_redirect'),
    path('contracts/', include('blu_staff.apps.contracts.urls')),
    path('payroll/', frontend_views.payroll_list, name='payroll_list'),
    path('payroll/employee-salaries/', frontend_views.employee_salary_list, name='employee_salary_list'),
    path('payroll/<int:payroll_id>/', frontend_views.payroll_detail, name='payroll_detail'),
    path('payroll/designer/', frontend_views.payslip_designer, name='payslip_designer'),
    path('benefits/', frontend_views.benefits_list, name='benefits_list'),
    path('benefits/claim/submit/', frontend_views.benefit_claim_submit, name='benefit_claim_submit'),
    path('benefits/claim/cleanup-mine/', frontend_views.benefit_claim_cleanup_my_pending, name='benefit_claim_cleanup_my_pending'),
    path('benefits/claim/<int:claim_id>/delete/', frontend_views.benefit_claim_delete, name='benefit_claim_delete'),
    path('benefits/claim/<int:claim_id>/action/', frontend_views.benefit_claim_action, name='benefit_claim_action'),
    path('benefits/create/', frontend_views.benefit_create, name='benefit_create'),
    path('benefits/enroll/', frontend_views.benefit_enrollment_create, name='benefit_enrollment_create'),
    path('benefits/self-enroll/', frontend_views.employee_benefit_self_enroll, name='employee_benefit_self_enroll'),
    path('benefits/<int:enrollment_id>/toggle/', frontend_views.benefit_activation_toggle, name='benefit_activation_toggle'),
    path('training/', frontend_views.training_list, name='training_list'),
    path('training/create-program/', frontend_views.training_program_create, name='training_program_create'),
    path('training/create-enrollment/', frontend_views.training_enrollment_create, name='training_enrollment_create'),
    path('training/self-enroll/', frontend_views.employee_training_self_enroll, name='employee_training_self_enroll'),
    path('settings/finance-policy/', frontend_views.finance_policy_settings, name='finance_policy_settings'),
    path('onboarding/', frontend_views.onboarding_list, name='onboarding_list'),
    path('onboarding/create/', frontend_views.onboarding_create, name='onboarding_create'),
    path('offboarding/create/', frontend_views.offboarding_create, name='offboarding_create'),
    path('analytics/dashboard/', frontend_views.analytics_dashboard_view, name='analytics_dashboard_view'),
    path('notifications/', frontend_views.notifications_list, name='notifications_list'),
    path('notifications/<int:notification_id>/mark-read/', frontend_views.notification_mark_read, name='notification_mark_read'),
    path('notifications/mark-all-read/', frontend_views.notification_mark_all_read, name='notification_mark_all_read'),
    path('notifications/<int:notification_id>/delete/', frontend_views.notification_delete, name='notification_delete'),
    path('employee-management/', frontend_views.employer_employee_management, name='employer_employee_management'),
    path('employee-management/bulk-action/', frontend_views.employee_bulk_action, name='employee_bulk_action'),
    path('analytics/', frontend_views.analytics_dashboard, name='analytics_dashboard'),
    path('approvals/', frontend_views.approval_center, name='approval_center'),
    path('support/new/', frontend_views.employer_support_ticket_create, name='employer_support_ticket_create'),
    path('support/', frontend_views.employer_support_center, name='employer_support_center'),
    # Assets redirect stubs removed - assets now mounted at /assets/ directly
    path('bulk-import/', frontend_views.bulk_employee_import, name='bulk_employee_import'),
    path('reports/', frontend_views.reports_center, name='reports_center'),
    path('reports/custom/', frontend_views.custom_report_builder, name='custom_report_builder'),
    path('reports/employee-roster/', frontend_views.report_employee_roster, name='report_employee_roster'),
    path('reports/attendance/', frontend_views.report_attendance, name='report_attendance'),
    path('reports/leave/', frontend_views.report_leave, name='report_leave'),
    path('reports/documents/', frontend_views.report_documents, name='report_documents'),
    path('reports/assets/', frontend_views.report_assets, name='report_assets'),
    path('reports/payroll/', frontend_views.report_payroll, name='report_payroll'),
    path('reports/expenses/', frontend_views.report_expenses, name='report_expenses'),
    path('reports/training/', frontend_views.report_training, name='report_training'),
    path('reports/contract-expiry/', frontend_views.report_contract_expiry, name='report_contract_expiry'),
    path('reports/export/roster/', frontend_views.export_employee_roster, name='export_employee_roster'),
    path('reports/export/attendance/', frontend_views.export_attendance_report, name='export_attendance_report'),
    path('reports/export/leave/', frontend_views.export_leave_report, name='export_leave_report'),
    path('reports/export/documents/', frontend_views.export_documents_report, name='export_documents_report'),
    path('reports/export/assets/', frontend_views.export_assets_report, name='export_assets_report'),
    path('integrations/', include('blu_staff.apps.accounts.integration_urls')),
    path('logout/', auth_views.ems_logout, name='ems_logout'),
    path('settings/', frontend_views.settings_hub, name='settings_hub'),
    path('settings/config/', frontend_views.settings_dashboard, name='settings_dashboard'),
    path('settings/delete-department/<int:dept_id>/', frontend_views.delete_department, name='delete_department'),
    path('settings/delete-position/<int:pos_id>/', frontend_views.delete_position, name='delete_position'),
    path('settings/delete-pay-grade/<int:grade_id>/', frontend_views.delete_pay_grade, name='delete_pay_grade'),
    path('settings/test-smtp/', frontend_views.test_smtp_connection, name='test_smtp'),
    path('settings/test-biometric/', frontend_views.test_biometric_connection, name='test_biometric'),
    path('knowledge-base/', frontend_views.knowledge_base, name='knowledge_base'),
    path('knowledge-base/<slug:slug>/', frontend_views.knowledge_article_detail, name='knowledge_article_detail'),
    path('companies/', account_views.company_list, name='company_list'),
    path('companies/create/', account_views.company_create, name='company_create'),
    path('companies/<int:company_id>/edit/', account_views.company_edit, name='company_edit'),
    path('companies/<int:request_id>/approve/', account_views.approve_company, name='approve_company'),
    path('companies/<int:company_id>/approve-existing/', account_views.approve_existing_company, name='approve_existing_company'),
    path('companies/<int:company_id>/reject/', account_views.reject_company, name='reject_company'),
    path('users/', frontend_views.user_management, name='user_management'),
    path('system-health/', frontend_views.system_health, name='system_health'),
    path('employer/employees/add/', frontend_views.employer_add_employee, name='employer_add_employee'),
    path('employer/employees/<int:employee_id>/edit/', frontend_views.employer_edit_employee, name='employer_edit_employee'),
    path('employee/profile-picture/upload/', frontend_views.employee_profile_picture_upload, name='employee_profile_picture_upload'),
    path('employee/document/upload/', frontend_views.document_upload, name='document_upload'),
    path('employee/asset/assign/', frontend_views.asset_assign, name='asset_assign'),
    path('employee/reset-password/', frontend_views.employee_reset_password, name='employee_reset_password'),
    path('employee/attendance/', frontend_views.employee_attendance_view, name='employee_attendance_view'),
    path('employee/leave/', frontend_views.employee_leave_request, name='employee_leave_request'),
    
    # Branch Management
    path('branches/', frontend_views.branch_management, name='branch_management'),
    path('branches/create/', frontend_views.branch_create, name='branch_create'),
    path('branches/<int:branch_id>/edit/', frontend_views.branch_edit, name='branch_edit'),
    path('branches/<int:branch_id>/', frontend_views.branch_detail, name='branch_detail'),
    
    # Request Management
    path('requests/', frontend_views.employee_requests_list, name='employee_requests_list'),
    path('requests/create/', frontend_views.employee_request_create, name='employee_request_create'),
    path('requests/<int:request_id>/', frontend_views.employee_request_detail, name='employee_request_detail'),
    path('requests/<int:request_id>/edit/', frontend_views.employee_request_edit, name='employee_request_edit'),
    path('requests/approvals/', frontend_views.requests_approval_center, name='requests_approval_center'),
    path('requests/<int:request_id>/action/', frontend_views.request_approve_reject, name='request_approve_reject'),
    
    # Communication
    path('groups/', frontend_views.chat_groups_list, name='chat_groups_list'),
    path('groups/<int:group_id>/', frontend_views.chat_group_detail, name='chat_group_detail'),
    path('messages/', frontend_views.direct_messages_list, name='direct_messages_list'),
    path('messages/<int:user_id>/', frontend_views.direct_message_conversation, name='direct_message_conversation'),
    path('announcements/', frontend_views.announcements_list, name='announcements_list'),
    path('announcements/<int:announcement_id>/', frontend_views.announcement_detail, name='announcement_detail'),
    
    # Performance Reviews
    path('performance/', frontend_views.performance_reviews_list, name='performance_reviews_list'),
    path('performance/create/', frontend_views.performance_review_create, name='performance_review_create'),
    path('performance/cycles/', frontend_views.performance_review_cycles, name='performance_review_cycles'),
    path('performance/goals/', frontend_views.pms_goals, name='pms_goals'),
    path('performance/metrics/', frontend_views.pms_metrics, name='pms_metrics'),
    path('performance/feedback/', frontend_views.pms_feedback_360, name='pms_feedback_360'),
    path('performance/self-assessment/', frontend_views.pms_self_assessment, name='pms_self_assessment'),
    path('performance/competencies/', frontend_views.pms_competencies, name='pms_competencies'),
    path('performance/<int:review_id>/', frontend_views.performance_review_detail, name='performance_review_detail'),

    # To-Do / Tasks
    path('tasks/', frontend_views.tasks_list, name='tasks_list'),
    path('tasks/<int:task_id>/update/', frontend_views.task_detail_update, name='task_detail_update'),

    # File Manager
    path('files/', frontend_views.file_manager, name='file_manager'),

    # Social Feed
    path('feed/', frontend_views.social_feed, name='social_feed'),
    path('feed/post/<int:post_id>/delete/', frontend_views.feed_post_delete, name='feed_post_delete'),

    # Chat (polished)
    path('chat/', frontend_views.chat_home, name='chat_home'),
    path('chat/<int:user_id>/', frontend_views.chat_conversation, name='chat_conversation'),

    # Calendar
    path('calendar/', frontend_views.calendar_view, name='calendar_view'),
    path('calendar/events.json', frontend_views.calendar_events_json, name='calendar_events_json'),
    path('calendar/events/save/', frontend_views.calendar_event_save, name='calendar_event_save'),
    path('calendar/events/<int:event_id>/delete/', frontend_views.calendar_event_delete, name='calendar_event_delete'),

    # Timesheets
    path('timesheets/', frontend_views.timesheets_list, name='timesheets_list'),
    path('timesheets/<int:timesheet_id>/', frontend_views.timesheet_detail, name='timesheet_detail'),
    path('timesheets/<int:timesheet_id>/action/', frontend_views.timesheet_action, name='timesheet_action'),
    path('employee/my-timesheet/', frontend_views.employee_timesheet, name='employee_timesheet'),

    # Role-Based Dashboards
    path('hr/dashboard/', frontend_views.hr_dashboard, name='hr_dashboard'),
    path('accountant/dashboard/', frontend_views.accountant_dashboard, name='accountant_dashboard'),
    
    # Supervisor Features (Phase 4)
    path('supervisor/dashboard/', frontend_views.supervisor_dashboard, name='supervisor_dashboard'),
    path('supervisor/team-attendance/', frontend_views.supervisor_team_attendance, name='supervisor_team_attendance'),
    path('supervisor/team-performance/', frontend_views.supervisor_team_performance, name='supervisor_team_performance'),
    path('supervisor/request-approvals/', frontend_views.supervisor_request_approval, name='supervisor_request_approval'),
    
    # E-Forms & E-Signature (Phase 5)
    path('forms/', include('blu_staff.apps.eforms.urls')),
    path('eforms/', include('blu_staff.apps.eforms.urls')),  # Alias for navigation consistency
    
    # Payment Processing
    path('payments/', include('ems_project.payments.urls')),
    
    # Asset Management Suite (AMS) - Standalone suite
    path('asset-management/', include(('blu_assets.urls', 'blu_assets'), namespace='assets')),
    
    # Training & Development
    path('training/', include('blu_staff.apps.training.frontend_urls')),
    
    # BLU Projects - Project Management
    path('projects/', include('blu_projects.urls')),
    
    # BLU Analytics - Analytics & Reporting
    path('analytics/', include('blu_analytics.urls')),

    # Django Admin - Standard Django admin (staff only)
    path('admin/', admin.site.urls),
    path('admin/login/', auth_views.django_admin_login, name='django_admin_login'),

    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # API v1
    path('api/v1/auth/', include('blu_staff.apps.accounts.urls')),
    
    # Accounts app URLs
    path('', include('blu_staff.apps.accounts.urls')),
    path('api/v1/attendance/', include('blu_staff.apps.attendance.urls')),
    path('api/v1/documents/', include('blu_staff.apps.documents.urls')),
    # PERFORMANCE MODULE DISABLED
    # path('api/v1/performance/', include('blu_staff.apps.performance.urls')),
    path('api/v1/communication/', include('blu_staff.apps.communication.urls')),
    path('api/v1/requests/', include('blu_staff.apps.requests.urls')),
    path('api/v1/notifications/', include('blu_staff.apps.notifications.urls')),
    path('api/v1/onboarding/', include('blu_staff.apps.onboarding.urls')),
    path('api/v1/payroll/', include('blu_staff.apps.payroll.urls')),
    path('api/v1/reports/', include('blu_staff.apps.reports.urls')),

    # Health check
    path('health/', include('health_check.urls')),
    
    # Billing Module
    path('billing/', include('blu_billing.urls')),
    
    # Support Module
    path('support/', include('blu_support.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers (uncomment when DEBUG=False for production)
# handler404 = 'ems_project.error_views.handler404'
# handler500 = 'ems_project.error_views.handler500'
# handler403 = 'ems_project.error_views.handler403'
