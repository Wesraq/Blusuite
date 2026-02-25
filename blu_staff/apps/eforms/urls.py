from django.urls import path
from . import views

urlpatterns = [
    # Default landing aliases
    path('', views.form_templates_list, name='eforms_list'),
    path('list/', views.form_templates_list, name='eforms_list_alias'),

    # Form Template Management
    path('templates/', views.form_templates_list, name='form_templates_list'),
    path('templates/create/', views.form_template_create, name='form_template_create'),
    path('templates/<int:template_id>/edit/', views.form_template_edit, name='form_template_edit'),
    path('templates/<int:template_id>/builder/', views.form_builder, name='form_builder'),
    path('templates/<int:template_id>/delete/', views.form_template_delete, name='form_template_delete'),
    
    # Form Submission
    path('templates/<int:template_id>/fill/', views.form_fill, name='form_fill'),
    path('submissions/', views.form_submissions_list, name='form_submissions_list'),
    path('submissions/<int:submission_id>/', views.form_submission_detail, name='form_submission_detail'),
    path('submissions/<int:submission_id>/pdf/', views.submission_export_pdf, name='submission_export_pdf'),
    
    # E-Signature
    path('submissions/<int:submission_id>/sign/', views.form_sign, name='form_sign'),
    path('signatures/<int:signature_id>/audit/', views.signature_audit_trail, name='signature_audit_trail'),
    
    # Approvals
    path('approvals/', views.form_approvals_list, name='form_approvals_list'),
    path('approvals/<int:submission_id>/action/', views.form_approve_reject, name='form_approve_reject'),
]
