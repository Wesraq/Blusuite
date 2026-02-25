from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    OnboardingChecklistViewSet,
    OffboardingChecklistViewSet,
    OnboardingTaskViewSet,
    EmployeeOnboardingViewSet,
    EmployeeOffboardingViewSet,
    OnboardingTaskCompletionViewSet,
)

router = DefaultRouter()
router.register(r'checklists', OnboardingChecklistViewSet, basename='onboarding-checklists')
router.register(r'offboarding-checklists', OffboardingChecklistViewSet, basename='offboarding-checklists')
router.register(r'tasks', OnboardingTaskViewSet, basename='onboarding-tasks')
router.register(r'employee', EmployeeOnboardingViewSet, basename='employee-onboarding')
router.register(r'employee-offboarding', EmployeeOffboardingViewSet, basename='employee-offboarding')
router.register(r'task-completions', OnboardingTaskCompletionViewSet, basename='onboarding-task-completions')

urlpatterns = [
    path('', include(router.urls)),
]
