from rest_framework import permissions, viewsets, filters

from tenant_management.permissions import IsTenantMember, IsTenantAdmin

from .models import (
    OnboardingChecklist,
    OffboardingChecklist,
    OnboardingTask,
    OnboardingTaskCompletion,
    EmployeeOnboarding,
    EmployeeOffboarding,
)
from .serializers import (
    OnboardingChecklistSerializer,
    OffboardingChecklistSerializer,
    OnboardingTaskSerializer,
    OnboardingTaskCompletionSerializer,
    EmployeeOnboardingSerializer,
    EmployeeOffboardingSerializer,
)


class TenantScopedViewSet(viewsets.ModelViewSet):
    """Base viewset to ensure data is scoped to the active tenant."""

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(tenant=tenant)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class OnboardingChecklistViewSet(TenantScopedViewSet):
    queryset = OnboardingChecklist.objects.prefetch_related('tasks')
    serializer_class = OnboardingChecklistSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']


class OffboardingChecklistViewSet(TenantScopedViewSet):
    queryset = OffboardingChecklist.objects.prefetch_related('tasks')
    serializer_class = OffboardingChecklistSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']


class OnboardingTaskViewSet(TenantScopedViewSet):
    queryset = OnboardingTask.objects.select_related('checklist')
    serializer_class = OnboardingTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['sequence', 'due_days']
    ordering = ['sequence']


class EmployeeOnboardingViewSet(TenantScopedViewSet):
    queryset = EmployeeOnboarding.objects.select_related('employee', 'checklist')
    serializer_class = EmployeeOnboardingSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employee__first_name', 'employee__last_name', 'status']
    ordering_fields = ['start_date', 'status']
    ordering = ['-start_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'checklist')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset.filter(employee__company=user.company)
        return queryset.filter(employee=user)


class EmployeeOffboardingViewSet(TenantScopedViewSet):
    queryset = EmployeeOffboarding.objects.select_related('employee', 'checklist')
    serializer_class = EmployeeOffboardingSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employee__first_name', 'employee__last_name', 'status']
    ordering_fields = ['start_date', 'status']
    ordering = ['-start_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'checklist')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset.filter(employee__company=user.company)
        return queryset.filter(employee=user)


class OnboardingTaskCompletionViewSet(TenantScopedViewSet):
    queryset = OnboardingTaskCompletion.objects.select_related('task', 'employee_onboarding')
    serializer_class = OnboardingTaskCompletionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['completed_at']
    ordering = ['-completed_at']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('task', 'employee_onboarding')
        user = self.request.user
        return queryset.filter(
            models.Q(employee_onboarding__employee=user) |
            models.Q(employee_onboarding__manager=user)
        )
