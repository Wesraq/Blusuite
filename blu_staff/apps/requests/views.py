from django.db import models
from rest_framework import permissions, viewsets, filters
from rest_framework.exceptions import ValidationError

from tenant_management.permissions import IsTenantMember, IsTenantAdmin

from .models import (
    RequestType,
    EmployeeRequest,
    RequestApproval,
    RequestComment,
    PettyCashRequest,
    AdvanceRequest,
    ReimbursementRequest,
)
from .serializers import (
    RequestTypeSerializer,
    EmployeeRequestSerializer,
    RequestApprovalSerializer,
    RequestCommentSerializer,
    PettyCashRequestSerializer,
    AdvanceRequestSerializer,
    ReimbursementRequestSerializer,
)


class TenantScopedViewSet(viewsets.ModelViewSet):
    """Base viewset that limits data to the active tenant."""

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(tenant=tenant)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            raise ValidationError('No active tenant found for this request.')
        serializer.save(tenant=tenant)


class RequestTypeViewSet(TenantScopedViewSet):
    queryset = RequestType.objects.all()
    serializer_class = RequestTypeSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class EmployeeRequestViewSet(TenantScopedViewSet):
    queryset = EmployeeRequest.objects.select_related('request_type', 'employee')
    serializer_class = EmployeeRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['request_number', 'title', 'employee__first_name', 'employee__last_name']
    ordering_fields = ['request_date', 'status', 'priority']
    ordering = ['-request_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('request_type', 'employee')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset.filter(employee__company=user.company)
        return queryset.filter(employee=user)


class RequestApprovalViewSet(TenantScopedViewSet):
    queryset = RequestApproval.objects.select_related('request', 'approver')
    serializer_class = RequestApprovalSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['approval_level', 'assigned_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('request', 'approver')
        user = self.request.user
        return queryset.filter(models.Q(approver=user) | models.Q(request__employee=user))


class RequestCommentViewSet(TenantScopedViewSet):
    queryset = RequestComment.objects.select_related('request', 'user')
    serializer_class = RequestCommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter]
    search_fields = ['comment', 'user__first_name', 'user__last_name']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('request', 'user')
        user = self.request.user
        return queryset.filter(models.Q(user=user) | models.Q(request__employee=user))


class PettyCashRequestViewSet(TenantScopedViewSet):
    queryset = PettyCashRequest.objects.select_related('request', 'disbursed_by')
    serializer_class = PettyCashRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('request', 'disbursed_by')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset.filter(request__employee__company=user.company)
        return queryset.filter(request__employee=user)


class AdvanceRequestViewSet(TenantScopedViewSet):
    queryset = AdvanceRequest.objects.select_related('request')
    serializer_class = AdvanceRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('request')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset.filter(request__employee__company=user.company)
        return queryset.filter(request__employee=user)


class ReimbursementRequestViewSet(TenantScopedViewSet):
    queryset = ReimbursementRequest.objects.select_related('request')
    serializer_class = ReimbursementRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('request')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset.filter(request__employee__company=user.company)
        return queryset.filter(request__employee=user)
