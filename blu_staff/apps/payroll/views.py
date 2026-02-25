from rest_framework import permissions, viewsets, filters

from tenant_management.permissions import IsTenantMember, IsTenantAdmin

from .models import (
    SalaryStructure,
    Payroll,
    Benefit,
    EmployeeBenefit,
    PayrollDeduction,
)
from .serializers import (
    SalaryStructureSerializer,
    PayrollSerializer,
    BenefitSerializer,
    EmployeeBenefitSerializer,
    PayrollDeductionSerializer,
)


class TenantScopedViewSet(viewsets.ModelViewSet):
    """Base viewset ensuring data is scoped to the current tenant."""

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(tenant=tenant)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class SalaryStructureViewSet(TenantScopedViewSet):
    queryset = SalaryStructure.objects.select_related('employee')
    serializer_class = SalaryStructureSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employee__first_name', 'employee__last_name']
    ordering_fields = ['effective_date', 'base_salary']
    ordering = ['-effective_date']


class BenefitViewSet(TenantScopedViewSet):
    queryset = Benefit.objects.all()
    serializer_class = BenefitSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'benefit_type']


class EmployeeBenefitViewSet(TenantScopedViewSet):
    queryset = EmployeeBenefit.objects.select_related('employee', 'benefit')
    serializer_class = EmployeeBenefitSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employee__first_name', 'employee__last_name', 'benefit__name']
    ordering_fields = ['enrollment_date', 'effective_date']
    ordering = ['-enrollment_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'benefit')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset.filter(employee__company=user.company)
        return queryset.filter(employee=user)


class PayrollViewSet(TenantScopedViewSet):
    queryset = Payroll.objects.select_related('employee', 'approved_by')
    serializer_class = PayrollSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employee__first_name', 'employee__last_name', 'status']
    ordering_fields = ['period_start', 'period_end', 'pay_date']
    ordering = ['-period_end']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'approved_by')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset.filter(employee__company=user.company)
        return queryset.filter(employee=user)


class PayrollDeductionViewSet(TenantScopedViewSet):
    queryset = PayrollDeduction.objects.select_related('payroll')
    serializer_class = PayrollDeductionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter]
    search_fields = ['deduction_type', 'description']
