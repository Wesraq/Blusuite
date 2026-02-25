from rest_framework import serializers
from django.contrib.auth import get_user_model
from blu_staff.apps.accounts.models import User, EmployeeProfile, EmployerProfile
from blu_staff.apps.attendance.models import Attendance, LeaveRequest
from blu_staff.apps.documents.models import DocumentCategory, EmployeeDocument, DocumentTemplate, DocumentAccessLog
from blu_staff.apps.performance.models import (
    PerformanceReview, PerformanceGoal, PerformanceMetric,
    PerformanceFeedback, PerformanceTemplate
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'role', 'phone_number',
            'address', 'date_of_birth', 'profile_picture', 'is_verified',
            'is_active', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']


class EmployeeProfileSerializer(serializers.ModelSerializer):
    """Serializer for Employee Profile"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = '__all__'


class EmployerProfileSerializer(serializers.ModelSerializer):
    """Serializer for Employer Profile"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = EmployerProfile
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    """Serializer for Attendance model"""
    employee = UserSerializer(read_only=True)

    class Meta:
        model = Attendance
        fields = '__all__'


class LeaveRequestSerializer(serializers.ModelSerializer):
    """Serializer for Leave Request model"""
    employee = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'


class DocumentCategorySerializer(serializers.ModelSerializer):
    """Serializer for Document Category model"""
    class Meta:
        model = DocumentCategory
        fields = '__all__'


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    """Serializer for Employee Document model"""
    employee = UserSerializer(read_only=True)
    uploaded_by = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)

    class Meta:
        model = EmployeeDocument
        fields = '__all__'


class DocumentTemplateSerializer(serializers.ModelSerializer):
    """Serializer for Document Template model"""
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = DocumentTemplate
        fields = '__all__'


class DocumentAccessLogSerializer(serializers.ModelSerializer):
    """Serializer for Document Access Log model"""
    document = EmployeeDocumentSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = DocumentAccessLog
        fields = '__all__'


class PerformanceReviewSerializer(serializers.ModelSerializer):
    """Serializer for Performance Review model"""
    employee = UserSerializer(read_only=True)
    reviewer = UserSerializer(read_only=True)

    class Meta:
        model = PerformanceReview
        fields = '__all__'


class PerformanceGoalSerializer(serializers.ModelSerializer):
    """Serializer for Performance Goal model"""
    review = PerformanceReviewSerializer(read_only=True)

    class Meta:
        model = PerformanceGoal
        fields = '__all__'


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """Serializer for Performance Metric model"""
    review = PerformanceReviewSerializer(read_only=True)

    class Meta:
        model = PerformanceMetric
        fields = '__all__'


class PerformanceFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for Performance Feedback model"""
    review = PerformanceReviewSerializer(read_only=True)
    provided_by = UserSerializer(read_only=True)

    class Meta:
        model = PerformanceFeedback
        fields = '__all__'


class PerformanceTemplateSerializer(serializers.ModelSerializer):
    """Serializer for Performance Template model"""
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = PerformanceTemplate
        fields = '__all__'
