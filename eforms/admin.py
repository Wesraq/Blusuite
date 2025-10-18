from django.contrib import admin
from .models import FormTemplate, FormSubmission, FormField, ESignature, SignatureAuditLog, FormApproval


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'requires_signature', 'requires_approval', 'created_by', 'created_at']
    list_filter = ['category', 'status', 'requires_signature', 'requires_approval']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ['template', 'submitted_by', 'status', 'submitted_at', 'approved_by']
    list_filter = ['status', 'submitted_at']
    search_fields = ['template__title', 'submitted_by__email']
    readonly_fields = ['created_at', 'updated_at', 'submitted_at', 'approved_at']


@admin.register(FormField)
class FormFieldAdmin(admin.ModelAdmin):
    list_display = ['label', 'template', 'field_type', 'required', 'order']
    list_filter = ['field_type', 'required']
    search_fields = ['label', 'template__title']


@admin.register(ESignature)
class ESignatureAdmin(admin.ModelAdmin):
    list_display = ['signer', 'submission', 'signature_type', 'signed_at', 'consented']
    list_filter = ['signature_type', 'consented', 'signed_at']
    search_fields = ['signer__email', 'submission__template__title']
    readonly_fields = ['signed_at', 'ip_address', 'user_agent']


@admin.register(SignatureAuditLog)
class SignatureAuditLogAdmin(admin.ModelAdmin):
    list_display = ['signature', 'action', 'performed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['signature__signer__email']
    readonly_fields = ['timestamp']


@admin.register(FormApproval)
class FormApprovalAdmin(admin.ModelAdmin):
    list_display = ['submission', 'approver', 'status', 'assigned_at', 'reviewed_at']
    list_filter = ['status', 'assigned_at']
    search_fields = ['submission__template__title', 'approver__email']
    readonly_fields = ['assigned_at', 'reviewed_at']
