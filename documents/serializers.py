from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DocumentCategory, EmployeeDocument, DocumentTemplate, DocumentAccessLog

User = get_user_model()


class DocumentCategorySerializer(serializers.ModelSerializer):
    """Serializer for DocumentCategory model"""

    class Meta:
        model = DocumentCategory
        fields = ['id', 'name', 'description', 'is_required', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeDocument model"""
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    is_expired = serializers.ReadOnlyField()
    file_extension = serializers.ReadOnlyField(source='get_file_extension')

    class Meta:
        model = EmployeeDocument
        fields = [
            'id', 'employee', 'employee_name', 'category', 'category_name',
            'document_type', 'title', 'description', 'file', 'file_url',
            'original_filename', 'file_size', 'mime_type', 'status',
            'expiry_date', 'version', 'is_confidential', 'uploaded_by',
            'uploaded_by_name', 'approved_by', 'approved_by_name',
            'approved_at', 'rejection_reason', 'is_expired', 'file_extension',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'employee', 'original_filename', 'file_size', 'mime_type',
            'uploaded_by', 'approved_by', 'approved_at', 'created_at', 'updated_at'
        ]

    def get_file_url(self, obj):
        """Get the file URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None

    def validate_file(self, value):
        """Validate uploaded file"""
        if value:
            # Check file size (max 10MB)
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("File size cannot exceed 10MB")

            # Check file extension
            allowed_extensions = [
                '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png',
                '.xls', '.xlsx', '.txt', '.rtf'
            ]
            import os
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in allowed_extensions:
                raise serializers.ValidationError("File type not allowed")

        return value

    def create(self, validated_data):
        """Set uploaded_by to current user"""
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)


class DocumentTemplateSerializer(serializers.ModelSerializer):
    """Serializer for DocumentTemplate model"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    template_file_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentTemplate
        fields = [
            'id', 'name', 'description', 'category', 'category_name',
            'template_file', 'template_file_url', 'is_active',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_template_file_url(self, obj):
        """Get the template file URL"""
        if obj.template_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.template_file.url)
        return None

    def create(self, validated_data):
        """Set created_by to current user"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class DocumentAccessLogSerializer(serializers.ModelSerializer):
    """Serializer for DocumentAccessLog model"""
    document_title = serializers.CharField(source='document.title', read_only=True)
    employee_name = serializers.CharField(source='document.employee.get_full_name', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = DocumentAccessLog
        fields = [
            'id', 'document', 'document_title', 'employee_name', 'user',
            'user_name', 'access_type', 'ip_address', 'user_agent', 'accessed_at'
        ]
        read_only_fields = ['user', 'ip_address', 'user_agent', 'accessed_at']

    def create(self, validated_data):
        """Set user and IP address automatically"""
        request = self.context.get('request')
        if request:
            validated_data['user'] = request.user
            validated_data['ip_address'] = request.META.get('REMOTE_ADDR')
            validated_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        return super().create(validated_data)


class DocumentUploadSerializer(serializers.Serializer):
    """Serializer for document upload"""
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    document_type = serializers.ChoiceField(choices=EmployeeDocument.DocumentType.choices)
    category = serializers.PrimaryKeyRelatedField(
        queryset=DocumentCategory.objects.all(),
        required=False
    )
    file = serializers.FileField()
    expiry_date = serializers.DateField(required=False)
    is_confidential = serializers.BooleanField(default=False)

    def validate(self, data):
        """Validate the data"""
        user = self.context['request'].user

        # Check if user is employee
        if user.role != User.Role.EMPLOYEE:
            raise serializers.ValidationError("Only employees can upload documents")

        return data


class DocumentApprovalSerializer(serializers.Serializer):
    """Serializer for document approval/rejection"""
    status = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validate approval data"""
        user = self.context['request'].user

        # Check if user can approve documents
        if user.role not in [User.Role.ADMIN, User.Role.EMPLOYER]:
            raise serializers.ValidationError("Only admins and employers can approve documents")

        if data['status'] == 'REJECTED' and not data.get('rejection_reason'):
            raise serializers.ValidationError("Rejection reason is required when rejecting a document")

        return data


class DocumentStatsSerializer(serializers.Serializer):
    """Serializer for document statistics"""
    total_documents = serializers.IntegerField(read_only=True)
    pending_documents = serializers.IntegerField(read_only=True)
    approved_documents = serializers.IntegerField(read_only=True)
    rejected_documents = serializers.IntegerField(read_only=True)
    expired_documents = serializers.IntegerField(read_only=True)
    total_size = serializers.IntegerField(read_only=True)  # in bytes
