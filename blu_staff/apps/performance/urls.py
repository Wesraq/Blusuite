from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import frontend_views as views
from . import review_views
from .views import (
    PerformanceReviewViewSet, PerformanceGoalViewSet, 
    PerformanceFeedbackViewSet, PerformanceTemplateViewSet,
    PerformanceStatsView, PerformanceDashboardView
)

app_name = 'performance'

# API Routers
router = DefaultRouter()
router.register(r'api/reviews', PerformanceReviewViewSet)
router.register(r'api/goals', PerformanceGoalViewSet)
router.register(r'api/feedback', PerformanceFeedbackViewSet)
router.register(r'api/templates', PerformanceTemplateViewSet)

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Frontend views
    path('reviews/', views.ReviewListView.as_view(), name='review_list'),
    path('reviews/create/', views.ReviewCreateView.as_view(), name='review_create'),
    path('reviews/<int:pk>/', views.ReviewDetailView.as_view(), name='review_detail'),
    path('reviews/<int:pk>/edit/', views.ReviewUpdateView.as_view(), name='review_edit'),
    path('reviews/<int:pk>/delete/', views.ReviewDeleteView.as_view(), name='review_delete'),
    path('reviews/<int:pk>/submit/', views.review_submit, name='review_submit'),
    
    # Goals
    path('goals/', views.GoalListView.as_view(), name='goal_list'),
    path('goals/create/', views.GoalCreateView.as_view(), name='goal_create'),
    path('goals/<int:pk>/', views.GoalDetailView.as_view(), name='goal_detail'),
    path('goals/<int:pk>/update/', views.GoalUpdateView.as_view(), name='goal_update'),
    path('goals/<int:pk>/delete/', views.GoalDeleteView.as_view(), name='goal_delete'),
    
    # Feedback
    path('feedback/create/', views.FeedbackCreateView.as_view(), name='feedback_create'),
    path('feedback/<int:pk>/', views.FeedbackDetailView.as_view(), name='feedback_detail'),
    
    # Dashboard and Stats
    path('dashboard/', views.performance_dashboard, name='dashboard'),
    path('api/stats/', PerformanceStatsView.as_view(), name='performance_stats'),
    path('api/dashboard/', PerformanceDashboardView.as_view(), name='api_dashboard'),
    
    # Employee and Reviewer Interfaces
    path('review/<int:review_id>/employee/', review_views.employee_review_interface, name='employee_review_interface'),
    path('review/<int:review_id>/reviewer/', review_views.reviewer_interface, name='reviewer_interface'),
    path('review/<int:review_id>/view/', review_views.review_view_only, name='review_view_only'),
]
