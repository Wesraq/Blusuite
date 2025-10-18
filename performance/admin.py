from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import (
    PerformanceReview, PerformanceGoal, PerformanceMetric,
    PerformanceFeedback, PerformanceTemplate
)

User = get_user_model()


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    """Admin interface for PerformanceReview model"""
    list_display = [
        'title', 'employee', 'reviewer', 'review_type', 'review_date',
        'overall_rating', 'status'
    ]
    list_filter = [
        'status', 'review_type', 'overall_rating', 'review_date',
        'is_confidential'
    ]
    search_fields = [
        'title', 'objectives', 'employee__first_name', 'employee__last_name',
        'employee__email', 'reviewer__first_name', 'reviewer__last_name'
    ]
    ordering = ['-review_date']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('employee', 'reviewer', 'title', 'review_type')
        }),
        ('Review Period', {
            'fields': ('review_period_start', 'review_period_end', 'review_date')
        }),
        ('Rating & Status', {
            'fields': ('overall_rating', 'status', 'is_confidential')
        }),
        ('Review Content', {
            'fields': ('objectives', 'achievements', 'strengths', 'areas_for_improvement'),
            'classes': ('collapse',)
        }),
        ('Development Plan', {
            'fields': ('development_plan', 'goals_next_period', 'additional_comments'),
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
        """Set reviewer when creating new review"""
        if not change and not obj.reviewer:
            obj.reviewer = request.user
        super().save_model(request, obj, form, change)


@admin.register(PerformanceGoal)
class PerformanceGoalAdmin(admin.ModelAdmin):
    """Admin interface for PerformanceGoal model"""
    list_display = [
        'title', 'review', 'priority', 'status', 'progress_percentage',
        'target_completion_date'
    ]
    list_filter = ['status', 'priority', 'category']
    search_fields = [
        'title', 'description', 'review__employee__first_name',
        'review__employee__last_name'
    ]
    ordering = ['-review__review_date', 'priority']

    fieldsets = (
        ('Goal Information', {
            'fields': ('review', 'title', 'description', 'category')
        }),
        ('Priority & Progress', {
            'fields': ('priority', 'status', 'progress_percentage')
        }),
        ('Timeline', {
            'fields': ('target_completion_date', 'actual_completion_date'),
            'classes': ('collapse',)
        }),
        ('Additional Details', {
            'fields': ('success_criteria', 'challenges', 'support_needed'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    """Admin interface for PerformanceMetric model"""
    list_display = [
        'name', 'review', 'metric_type', 'target_value', 'actual_value',
        'achievement_percentage', 'is_achieved'
    ]
    list_filter = ['metric_type', 'is_achieved']
    search_fields = ['name', 'description']
    ordering = ['-review__review_date', 'weight']

    fieldsets = (
        ('Metric Information', {
            'fields': ('review', 'name', 'description', 'metric_type')
        }),
        ('Values', {
            'fields': ('target_value', 'actual_value', 'unit', 'weight')
        }),
        ('Results', {
            'fields': ('is_achieved', 'achievement_percentage'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['achievement_percentage']


@admin.register(PerformanceFeedback)
class PerformanceFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for PerformanceFeedback model"""
    list_display = [
        'review', 'feedback_type', 'provided_by', 'rating', 'is_anonymous'
    ]
    list_filter = ['feedback_type', 'rating', 'is_anonymous']
    search_fields = [
        'review__employee__first_name', 'review__employee__last_name',
        'provided_by__first_name', 'provided_by__last_name'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Feedback Information', {
            'fields': ('review', 'feedback_type', 'provided_by', 'relationship_to_employee')
        }),
        ('Rating & Content', {
            'fields': ('rating', 'strengths', 'areas_for_improvement')
        }),
        ('Comments', {
            'fields': ('overall_comments', 'suggestions', 'is_anonymous'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter queryset based on user role"""
        qs = super().get_queryset(request)
        if request.user.role == 'EMPLOYEE':
            qs = qs.filter(review__employee=request.user)
        elif request.user.role == 'EMPLOYER':
            qs = qs.filter(review__employee__employer_profile__user=request.user)
        # Admin sees all records
        return qs


@admin.register(PerformanceTemplate)
class PerformanceTemplateAdmin(admin.ModelAdmin):
    """Admin interface for PerformanceTemplate model"""
    list_display = ['name', 'review_type', 'is_default', 'is_active', 'created_by']
    list_filter = ['review_type', 'is_default', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['-is_default', 'name']

    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'description', 'review_type')
        }),
        ('Configuration', {
            'fields': ('is_default', 'is_active', 'sections')
        }),
        ('System Information', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_by']
