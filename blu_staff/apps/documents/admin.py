from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import DocumentCategory, EmployeeDocument, DocumentTemplate, DocumentAccessLog

User = get_user_model()


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    """Admin interface for DocumentCategory model"""
    list_display = ['name', 'description', 'is_required', 'created_at']
    list_filter = ['is_required', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    """Admin interface for EmployeeDocument model"""
    list_display = [
        'title', 'employee', 'document_type', 'status', 'expiry_date',
        'is_expired', 'uploaded_by', 'created_at'
    ]
    list_filter = [
        'status', 'document_type', 'is_confidential',
        'created_at', 'expiry_date'
    ]
    search_fields = [
        'title', 'description', 'employee__first_name', 'employee__last_name',
        'employee__email', 'uploaded_by__first_name', 'uploaded_by__last_name'
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'file_size', 'mime_type', 'original_filename']

    fieldsets = (
        ('Document Information', {
            'fields': ('employee', 'title', 'description', 'document_type', 'category')
        }),
        ('File Information', {
            'fields': ('file', 'original_filename', 'file_size', 'mime_type', 'expiry_date'),
            'classes': ('collapse',)
        }),
        ('Status & Security', {
            'fields': ('status', 'is_confidential', 'version'),
            'classes': ('collapse',)
        }),
        ('Approval Information', {
            'fields': ('uploaded_by', 'approved_by', 'approved_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter queryset based on user role"""
        qs = super().get_queryset(request)
        if request.user.role == 'EMPLOYEE':
            qs = qs.filter(employee=request.user)
        elif request.user.role == 'EMPLOYER':
            qs = qs.filter(employee__employer_profile__user=request.user)
        # Admin sees all records
        return qs

    def save_model(self, request, obj, form, change):
        """Set uploaded_by when creating new document"""
        if not change and not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    """Admin interface for DocumentTemplate model"""
    list_display = ['name', 'category', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'category', 'created_at']
    search_fields = ['name', 'description', 'created_by__first_name', 'created_by__last_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'description', 'category', 'template_file')
        }),
        ('Settings', {
            'fields': ('is_active',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Only show templates created by employer or admin"""
        qs = super().get_queryset(request)
        if request.user.role == 'EMPLOYER':
            qs = qs.filter(created_by=request.user)
        # Admin sees all records
        return qs


@admin.register(DocumentAccessLog)
class DocumentAccessLogAdmin(admin.ModelAdmin):
    """Admin interface for DocumentAccessLog model"""
    list_display = ['document', 'user', 'access_type', 'ip_address', 'accessed_at']
    list_filter = ['access_type', 'accessed_at']
    search_fields = [
        'document__title', 'user__first_name', 'user__last_name',
        'user__email', 'ip_address'
    ]
    ordering = ['-accessed_at']
    readonly_fields = ['accessed_at', 'ip_address', 'user_agent']

    def has_add_permission(self, request):
        """Prevent manual creation of access logs"""
        return False

    def get_queryset(self, request):
        """Filter queryset based on user role"""
        qs = super().get_queryset(request)
        if request.user.role == 'EMPLOYEE':
            qs = qs.filter(document__employee=request.user)
        elif request.user.role == 'EMPLOYER':
            qs = qs.filter(document__employee__employer_profile__user=request.user)
        # Admin sees all records
        return qs
