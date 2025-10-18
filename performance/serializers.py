from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    PerformanceReview, PerformanceGoal, PerformanceMetric,
    PerformanceFeedback, PerformanceTemplate
)

User = get_user_model()


class PerformanceReviewSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceReview model"""
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)

    class Meta:
        model = PerformanceReview
        fields = [
            'id', 'employee', 'employee_name', 'reviewer', 'reviewer_name',
            'review_type', 'review_period_start', 'review_period_end',
            'review_date', 'overall_rating', 'title', 'objectives',
            'achievements', 'strengths', 'areas_for_improvement',
            'development_plan', 'goals_next_period', 'additional_comments',
            'status', 'is_confidential', 'created_at', 'updated_at'
        ]
        read_only_fields = ['employee', 'reviewer', 'created_at', 'updated_at']


class PerformanceGoalSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceGoal model"""

    class Meta:
        model = PerformanceGoal
        fields = [
            'id', 'review', 'title', 'description', 'category', 'priority',
            'status', 'progress_percentage', 'target_completion_date',
            'actual_completion_date', 'success_criteria', 'challenges',
            'support_needed', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceMetric model"""
    achievement_percentage = serializers.ReadOnlyField()

    class Meta:
        model = PerformanceMetric
        fields = [
            'id', 'review', 'name', 'description', 'metric_type',
            'target_value', 'actual_value', 'unit', 'weight',
            'is_achieved', 'achievement_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'achievement_percentage']


class PerformanceFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceFeedback model"""
    employee_name = serializers.CharField(source='review.employee.get_full_name', read_only=True)
    provided_by_name = serializers.CharField(source='provided_by.get_full_name', read_only=True)

    class Meta:
        model = PerformanceFeedback
        fields = [
            'id', 'review', 'employee_name', 'feedback_type', 'provided_by',
            'provided_by_name', 'relationship_to_employee', 'rating',
            'strengths', 'areas_for_improvement', 'overall_comments',
            'suggestions', 'is_anonymous', 'created_at', 'updated_at'
        ]
        read_only_fields = ['provided_by', 'created_at', 'updated_at']


class PerformanceTemplateSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceTemplate model"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = PerformanceTemplate
        fields = [
            'id', 'name', 'description', 'review_type', 'is_default',
            'sections', 'created_by', 'created_by_name', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class PerformanceStatsSerializer(serializers.Serializer):
    """Serializer for performance statistics"""
    total_reviews = serializers.IntegerField(read_only=True)
    completed_reviews = serializers.IntegerField(read_only=True)
    pending_reviews = serializers.IntegerField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    reviews_this_month = serializers.IntegerField(read_only=True)
    upcoming_reviews = serializers.IntegerField(read_only=True)
