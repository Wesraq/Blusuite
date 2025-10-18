from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
import json
import base64

from .models import (
    FormTemplate, FormSubmission, FormField, 
    ESignature, SignatureAuditLog, FormApproval
)


# ============================================================================
# FORM TEMPLATE MANAGEMENT
# ============================================================================

@login_required
def form_templates_list(request):
    """List all form templates"""
    # Check if user has permission (HR, Admin, or Employer)
    if not (request.user.is_employer or 
            request.user.employee_profile.employee_role in ['HR', 'SUPERVISOR']):
        messages.error(request, 'Access denied. Insufficient permissions.')
        return redirect('employee_dashboard')
    
    templates = FormTemplate.objects.filter(
        company=request.user.company
    ).order_by('-created_at')
    
    # Filter by category
    category = request.GET.get('category')
    if category:
        templates = templates.filter(category=category)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        templates = templates.filter(status=status)
    
    context = {
        'templates': templates,
        'categories': FormTemplate.FormCategory.choices,
        'selected_category': category,
        'selected_status': status,
    }
    
    return render(request, 'eforms/templates_list.html', context)


@login_required
def form_template_create(request):
    """Create a new form template"""
    if not (request.user.is_employer or 
            request.user.employee_profile.employee_role == 'HR'):
        messages.error(request, 'Access denied. HR or Admin only.')
        return redirect('employee_dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        category = request.POST.get('category', 'GENERAL')
        requires_signature = request.POST.get('requires_signature') == 'on'
        requires_approval = request.POST.get('requires_approval') == 'on'
        approver_role = request.POST.get('approver_role', '')
        
        template = FormTemplate.objects.create(
            title=title,
            description=description,
            category=category,
            company=request.user.company,
            requires_signature=requires_signature,
            requires_approval=requires_approval,
            approver_role=approver_role,
            created_by=request.user,
            status='DRAFT'
        )
        
        messages.success(request, f'Form template "{title}" created successfully!')
        return redirect('form_builder', template_id=template.id)
    
    context = {
        'categories': FormTemplate.FormCategory.choices,
    }
    
    return render(request, 'eforms/template_create.html', context)


@login_required
def form_builder(request, template_id):
    """Form builder interface"""
    template = get_object_or_404(FormTemplate, id=template_id, company=request.user.company)
    
    if not (request.user.is_employer or 
            request.user.employee_profile.employee_role == 'HR' or 
            template.created_by == request.user):
        messages.error(request, 'Access denied.')
        return redirect('form_templates_list')
    
    if request.method == 'POST':
        # Save form structure from JSON
        form_fields_json = request.POST.get('form_fields')
        if form_fields_json:
            try:
                template.form_fields = json.loads(form_fields_json)
                template.status = request.POST.get('status', 'DRAFT')
                template.save()
                messages.success(request, 'Form template saved successfully!')
                return redirect('form_templates_list')
            except json.JSONDecodeError:
                messages.error(request, 'Invalid form data.')
    
    context = {
        'template': template,
        'field_types': FormField.FieldType.choices,
    }
    
    return render(request, 'eforms/form_builder.html', context)


@login_required
def form_template_edit(request, template_id):
    """Edit form template settings"""
    template = get_object_or_404(FormTemplate, id=template_id, company=request.user.company)
    
    if not (request.user.is_employer or 
            request.user.employee_profile.employee_role == 'HR' or 
            template.created_by == request.user):
        messages.error(request, 'Access denied.')
        return redirect('form_templates_list')
    
    if request.method == 'POST':
        template.title = request.POST.get('title')
        template.description = request.POST.get('description', '')
        template.category = request.POST.get('category')
        template.requires_signature = request.POST.get('requires_signature') == 'on'
        template.requires_approval = request.POST.get('requires_approval') == 'on'
        template.approver_role = request.POST.get('approver_role', '')
        template.status = request.POST.get('status')
        template.save()
        
        messages.success(request, 'Template updated successfully!')
        return redirect('form_templates_list')
    
    context = {
        'template': template,
        'categories': FormTemplate.FormCategory.choices,
    }
    
    return render(request, 'eforms/template_edit.html', context)


# ============================================================================
# FORM SUBMISSION
# ============================================================================

@login_required
def form_fill(request, template_id):
    """Fill out a form"""
    template = get_object_or_404(
        FormTemplate, 
        id=template_id, 
        company=request.user.company,
        status='ACTIVE'
    )
    
    if request.method == 'POST':
        # Collect form data
        form_data = {}
        for key, value in request.POST.items():
            if key not in ['csrfmiddlewaretoken', 'action']:
                form_data[key] = value
        
        # Create or update submission
        submission_id = request.POST.get('submission_id')
        if submission_id:
            submission = get_object_or_404(
                FormSubmission, 
                id=submission_id, 
                submitted_by=request.user
            )
            submission.form_data = form_data
        else:
            submission = FormSubmission.objects.create(
                template=template,
                submitted_by=request.user,
                company=request.user.company,
                form_data=form_data,
                status='DRAFT'
            )
        
        action = request.POST.get('action')
        if action == 'submit':
            submission.submit()
            
            if template.requires_signature:
                messages.info(request, 'Form submitted! Please add your signature.')
                return redirect('form_sign', submission_id=submission.id)
            else:
                messages.success(request, 'Form submitted successfully!')
                return redirect('form_submissions_list')
        else:
            submission.save()
            messages.success(request, 'Form saved as draft.')
            return redirect('form_submissions_list')
    
    context = {
        'template': template,
    }
    
    return render(request, 'eforms/form_fill.html', context)


@login_required
def form_submissions_list(request):
    """List user's form submissions"""
    submissions = FormSubmission.objects.filter(
        submitted_by=request.user
    ).select_related('template').order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        submissions = submissions.filter(status=status)
    
    context = {
        'submissions': submissions,
        'selected_status': status,
    }
    
    return render(request, 'eforms/submissions_list.html', context)


@login_required
def form_submission_detail(request, submission_id):
    """View form submission details"""
    submission = get_object_or_404(
        FormSubmission, 
        id=submission_id,
        company=request.user.company
    )
    
    # Check permission
    if not (submission.submitted_by == request.user or 
            request.user.is_employer or
            request.user.employee_profile.employee_role in ['HR', 'SUPERVISOR']):
        messages.error(request, 'Access denied.')
        return redirect('form_submissions_list')
    
    context = {
        'submission': submission,
    }
    
    return render(request, 'eforms/submission_detail.html', context)


# ============================================================================
# E-SIGNATURE
# ============================================================================

@login_required
def form_sign(request, submission_id):
    """Sign a form submission"""
    submission = get_object_or_404(
        FormSubmission, 
        id=submission_id,
        submitted_by=request.user
    )
    
    if not submission.template.requires_signature:
        messages.error(request, 'This form does not require a signature.')
        return redirect('form_submission_detail', submission_id=submission.id)
    
    # Check if already signed
    existing_signature = ESignature.objects.filter(
        submission=submission,
        signer=request.user
    ).first()
    
    if request.method == 'POST':
        signature_type = request.POST.get('signature_type')
        signature_data = request.POST.get('signature_data')
        consent = request.POST.get('consent') == 'on'
        
        if not consent:
            messages.error(request, 'You must agree to the consent terms.')
            return redirect('form_sign', submission_id=submission.id)
        
        # Get IP and user agent
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        consent_text = f"I, {request.user.get_full_name()}, electronically sign this document and agree that this signature is legally binding."
        
        signature = ESignature.objects.create(
            submission=submission,
            signer=request.user,
            signature_type=signature_type,
            signature_data=signature_data,
            ip_address=ip_address,
            user_agent=user_agent,
            consent_text=consent_text,
            consented=True
        )
        
        # Create audit log
        SignatureAuditLog.objects.create(
            signature=signature,
            action='CREATED',
            performed_by=request.user,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        messages.success(request, 'Form signed successfully!')
        return redirect('form_submission_detail', submission_id=submission.id)
    
    context = {
        'submission': submission,
        'existing_signature': existing_signature,
    }
    
    return render(request, 'eforms/form_sign.html', context)


@login_required
def signature_audit_trail(request, signature_id):
    """View signature audit trail"""
    signature = get_object_or_404(ESignature, id=signature_id)
    
    # Check permission
    if not (signature.signer == request.user or 
            request.user.is_employer or
            request.user.employee_profile.employee_role == 'HR'):
        messages.error(request, 'Access denied.')
        return redirect('employee_dashboard')
    
    audit_logs = signature.audit_logs.all()
    
    context = {
        'signature': signature,
        'audit_logs': audit_logs,
    }
    
    return render(request, 'eforms/signature_audit.html', context)


# ============================================================================
# FORM APPROVALS
# ============================================================================

@login_required
def form_approvals_list(request):
    """List forms pending approval"""
    # Check if user can approve forms
    if not (request.user.is_employer or 
            request.user.employee_profile.employee_role in ['HR', 'SUPERVISOR']):
        messages.error(request, 'Access denied. Insufficient permissions.')
        return redirect('employee_dashboard')
    
    # Get pending approvals assigned to this user
    my_approvals = FormApproval.objects.filter(
        approver=request.user,
        status='PENDING'
    ).select_related('submission', 'submission__template', 'submission__submitted_by')
    
    # Get all pending submissions (for HR/Admin)
    all_pending = FormSubmission.objects.filter(
        company=request.user.company,
        status='PENDING_APPROVAL'
    ).select_related('template', 'submitted_by')
    
    context = {
        'my_approvals': my_approvals,
        'all_pending': all_pending,
    }
    
    return render(request, 'eforms/approvals_list.html', context)


@login_required
@require_http_methods(["POST"])
def form_approve_reject(request, submission_id):
    """Approve or reject a form submission"""
    submission = get_object_or_404(
        FormSubmission, 
        id=submission_id,
        company=request.user.company
    )
    
    action = request.POST.get('action')
    comments = request.POST.get('comments', '')
    
    # Check permission
    if not (request.user.is_employer or 
            request.user.employee_profile.employee_role in ['HR', 'SUPERVISOR']):
        messages.error(request, 'Access denied.')
        return redirect('form_approvals_list')
    
    if action == 'approve':
        submission.status = 'APPROVED'
        submission.approved_by = request.user
        submission.approved_at = timezone.now()
        submission.save()
        
        # Update approval record if exists
        FormApproval.objects.filter(
            submission=submission,
            approver=request.user
        ).update(
            status='APPROVED',
            comments=comments,
            reviewed_at=timezone.now()
        )
        
        messages.success(request, f'Form submitted by {submission.submitted_by.get_full_name()} approved!')
    
    elif action == 'reject':
        submission.status = 'REJECTED'
        submission.rejection_reason = comments
        submission.save()
        
        # Update approval record if exists
        FormApproval.objects.filter(
            submission=submission,
            approver=request.user
        ).update(
            status='REJECTED',
            comments=comments,
            reviewed_at=timezone.now()
        )
        
        messages.success(request, f'Form submitted by {submission.submitted_by.get_full_name()} rejected.')
    
    return redirect('form_approvals_list')
