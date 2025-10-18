"""
URL configuration for ems_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf.urls.static import static

from . import frontend_views, auth_views
from accounts import views as account_views
from accounts.registration_views import (
    company_registration_request,
    registration_success,
    company_registration_list,
    approve_company_registration,
    reject_company_registration
)

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
    # Redirect /login/ to root for better UX
    path('login/', auth_views.general_user_login, name='login'),  # General user login
    # SuperAdmin login at eiscomtech
    path('eiscomtech/', frontend_views.superadmin_login, name='superadmin_login'),
    # Django auth compatibility - redirect to our custom login
    path('accounts/login/', auth_views.general_user_login, name='accounts_login'),

    # Company Registration
    path('register/', company_registration_request, name='company_registration'),
    path('register/success/<str:request_id>/', registration_success, name='registration_success'),
    path('admin/company-requests/', company_registration_list, name='company_registration_list'),
    path('admin/company-requests/<int:request_id>/approve/', approve_company_registration, name='approve_company_registration'),
    path('admin/company-requests/<int:request_id>/reject/', reject_company_registration, name='reject_company_registration'),

    path('dashboard/', frontend_views.dashboard_redirect, name='dashboard_redirect'),
    path('superadmin/', frontend_views.superadmin_dashboard, name='superadmin_dashboard'),
    path('employee/', frontend_views.employee_dashboard, name='employee_dashboard'),
    path('employer/', frontend_views.employer_dashboard, name='employer_dashboard'),
    path('employer-admin/', frontend_views.employer_admin_dashboard, name='employer_admin_dashboard'),
    path('attendance/', frontend_views.attendance_dashboard, name='attendance_dashboard'),
    path('attendance/update-status/', frontend_views.update_attendance_status, name='update_attendance_status'),
    path('attendance/bulk-update/', frontend_views.bulk_update_attendance, name='bulk_update_attendance'),
    path('attendance/<int:attendance_id>/edit/', frontend_views.employer_edit_attendance, name='employer_edit_attendance'),
    path('leave/', frontend_views.leave_management, name='leave_management'),
    path('leave/<int:leave_id>/action/', frontend_views.employer_leave_action, name='employer_leave_action'),
    path('leave/bulk-approve/', frontend_views.bulk_approve_leave, name='bulk_approve_leave'),
    path('leave/bulk-reject/', frontend_views.bulk_reject_leave, name='bulk_reject_leave'),
    path('documents/', frontend_views.documents_list, name='documents_list'),
    path('documents/upload/', frontend_views.document_upload, name='document_upload'),
    path('documents/<int:document_id>/download/', frontend_views.document_download, name='document_download'),
    path('documents/<int:document_id>/approve/', frontend_views.document_approve, name='document_approve'),
    path('documents/<int:document_id>/reject/', frontend_views.document_reject, name='document_reject'),
    path('documents/bulk-approve/', frontend_views.bulk_approve_documents, name='bulk_approve_documents'),
    path('documents/bulk-download/', frontend_views.bulk_download_documents, name='bulk_download_documents'),
    path('employer/employees/<int:employee_id>/documents/upload/', frontend_views.employee_document_upload, name='employee_document_upload'),
    path('employer/employees/<int:employee_id>/profile-picture/upload/', frontend_views.employee_profile_picture_upload_redirect, name='employee_profile_picture_upload_with_redirect'),
    path('performance/', frontend_views.performance_reviews_list, name='performance_reviews_list'),
    path('performance/create/', frontend_views.performance_review_create, name='performance_review_create'),
    path('performance/<int:review_id>/', frontend_views.performance_review_detail, name='performance_review_detail'),
    path('payroll/', frontend_views.payroll_list, name='payroll_list'),
    path('payroll/<int:payroll_id>/', frontend_views.payroll_detail, name='payroll_detail'),
    path('benefits/', frontend_views.benefits_list, name='benefits_list'),
    path('training/', frontend_views.training_list, name='training_list'),
    path('onboarding/', frontend_views.onboarding_list, name='onboarding_list'),
    path('analytics/dashboard/', frontend_views.analytics_dashboard_view, name='analytics_dashboard_view'),
    path('notifications/', frontend_views.notifications_list, name='notifications_list'),
    path('notifications/<int:notification_id>/mark-read/', frontend_views.notification_mark_read, name='notification_mark_read'),
    path('notifications/mark-all-read/', frontend_views.notification_mark_all_read, name='notification_mark_all_read'),
    path('notifications/<int:notification_id>/delete/', frontend_views.notification_delete, name='notification_delete'),
    path('employee-management/', frontend_views.employer_employee_management, name='employer_employee_management'),
    path('employee-management/bulk-action/', frontend_views.employee_bulk_action, name='employee_bulk_action'),
    path('analytics/', frontend_views.analytics_dashboard, name='analytics_dashboard'),
    path('approvals/', frontend_views.approval_center, name='approval_center'),
    path('assets/', frontend_views.assets_management, name='assets_management'),
    path('assets/create/', frontend_views.asset_create, name='asset_create'),
    path('bulk-import/', frontend_views.bulk_employee_import, name='bulk_employee_import'),
    path('reports/', frontend_views.reports_center, name='reports_center'),
    path('reports/custom/', frontend_views.custom_report_builder, name='custom_report_builder'),
    path('reports/export/roster/', frontend_views.export_employee_roster, name='export_employee_roster'),
    path('reports/export/attendance/', frontend_views.export_attendance_report, name='export_attendance_report'),
    path('reports/export/leave/', frontend_views.export_leave_report, name='export_leave_report'),
    path('reports/export/documents/', frontend_views.export_documents_report, name='export_documents_report'),
    path('reports/export/assets/', frontend_views.export_assets_report, name='export_assets_report'),
    path('integrations/', include('accounts.integration_urls')),
    path('logout/', auth_views.ems_logout, name='ems_logout'),
    path('settings/', frontend_views.settings_hub, name='settings_hub'),
    path('settings/config/', frontend_views.settings_dashboard, name='settings_dashboard'),
    path('settings/delete-department/<int:dept_id>/', frontend_views.delete_department, name='delete_department'),
    path('settings/delete-position/<int:pos_id>/', frontend_views.delete_position, name='delete_position'),
    path('settings/delete-pay-grade/<int:grade_id>/', frontend_views.delete_pay_grade, name='delete_pay_grade'),
    path('settings/test-smtp/', frontend_views.test_smtp_connection, name='test_smtp'),
    path('settings/test-biometric/', frontend_views.test_biometric_connection, name='test_biometric'),
    path('companies/', account_views.company_list, name='company_list'),
    path('companies/create/', account_views.company_create, name='company_create'),
    path('companies/<int:company_id>/edit/', account_views.company_edit, name='company_edit'),
    path('companies/<int:request_id>/approve/', account_views.approve_company, name='approve_company'),
    path('companies/<int:request_id>/approve-existing/', account_views.approve_existing_company, name='approve_existing_company'),
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
    path('requests/approvals/', frontend_views.requests_approval_center, name='requests_approval_center'),
    path('requests/<int:request_id>/action/', frontend_views.request_approve_reject, name='request_approve_reject'),
    
    # Communication
    path('groups/', frontend_views.chat_groups_list, name='chat_groups_list'),
    path('groups/<int:group_id>/', frontend_views.chat_group_detail, name='chat_group_detail'),
    path('messages/', frontend_views.direct_messages_list, name='direct_messages_list'),
    path('messages/<int:user_id>/', frontend_views.direct_message_conversation, name='direct_message_conversation'),
    path('announcements/', frontend_views.announcements_list, name='announcements_list'),
    path('announcements/<int:announcement_id>/', frontend_views.announcement_detail, name='announcement_detail'),
    
    # Supervisor Features (Phase 4)
    path('supervisor/dashboard/', frontend_views.supervisor_dashboard, name='supervisor_dashboard'),
    path('supervisor/team-attendance/', frontend_views.supervisor_team_attendance, name='supervisor_team_attendance'),
    path('supervisor/team-performance/', frontend_views.supervisor_team_performance, name='supervisor_team_performance'),
    path('supervisor/request-approvals/', frontend_views.supervisor_request_approval, name='supervisor_request_approval'),
    
    # E-Forms & E-Signature (Phase 5)
    path('forms/', include('eforms.urls')),
    
    # Asset Management (New System - Department-based)
    path('asset-management/', include('assets.urls')),
    
    # Training & Development
    path('training/', include('training.frontend_urls')),

    # Django Admin - Standard Django admin (staff only)
    path('admin/', admin.site.urls),
    path('admin/login/', auth_views.django_admin_login, name='django_admin_login'),

    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # API v1
    path('api/v1/auth/', include('accounts.urls')),
    
    # Accounts app URLs
    path('', include('accounts.urls')),
    path('api/v1/attendance/', include('attendance.urls')),
    path('api/v1/documents/', include('documents.urls')),
    path('api/v1/performance/', include('performance.urls')),
    # path('api/v1/payroll/', include('payroll.urls')),  # Temporarily disabled

    # Health check
    path('health/', include('health_check.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers (uncomment when DEBUG=False for production)
# handler404 = 'ems_project.error_views.handler404'
# handler500 = 'ems_project.error_views.handler500'
# handler403 = 'ems_project.error_views.handler403'
