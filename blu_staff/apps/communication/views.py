from django.db import models
from rest_framework import permissions, viewsets, filters
from rest_framework.exceptions import ValidationError

from tenant_management.permissions import IsTenantMember, IsTenantAdmin

from .models import (
    ChatGroup,
    GroupMessage,
    GroupMessageRead,
    DirectMessage,
    Announcement,
    AnnouncementRead,
)
from .serializers import (
    ChatGroupSerializer,
    GroupMessageSerializer,
    GroupMessageReadSerializer,
    DirectMessageSerializer,
    AnnouncementSerializer,
    AnnouncementReadSerializer,
)


class TenantScopedViewSet(viewsets.ModelViewSet):
    """Base viewset that scopes queryset to the active tenant."""

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
            raise ValidationError("No active tenant resolved for this request.")
        serializer.save(tenant=tenant)


class ChatGroupViewSet(TenantScopedViewSet):
    queryset = ChatGroup.objects.select_related('company', 'created_by')
    serializer_class = ChatGroupSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('members', 'admins')
        user = self.request.user
        if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']:
            return queryset
        return queryset.filter(members=user)

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        company = getattr(self.request.user, 'company', None)
        serializer.save(
            tenant=tenant,
            company=company,
            created_by=self.request.user,
        )


class GroupMessageViewSet(TenantScopedViewSet):
    queryset = GroupMessage.objects.select_related('group', 'sender')
    serializer_class = GroupMessageSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter]
    search_fields = ['content']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('group', 'sender')
        group_id = self.request.query_params.get('group')
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        group = serializer.validated_data.get('group')
        if group and group.tenant_id != getattr(tenant, 'id', None):
            raise ValidationError('Group does not belong to the active tenant.')
        serializer.save(tenant=tenant, sender=self.request.user)


class GroupMessageReadViewSet(TenantScopedViewSet):
    queryset = GroupMessageRead.objects.select_related('group', 'user')
    serializer_class = GroupMessageReadSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        queryset = super().get_queryset()
        group_id = self.request.query_params.get('group')
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        serializer.save(tenant=tenant, user=self.request.user)


class DirectMessageViewSet(TenantScopedViewSet):
    queryset = DirectMessage.objects.select_related('sender', 'recipient')
    serializer_class = DirectMessageSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter]
    search_fields = ['content', 'sender__first_name', 'recipient__first_name']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('sender', 'recipient')
        user = self.request.user
        return queryset.filter(
            models.Q(sender=user) | models.Q(recipient=user)
        ).order_by('-created_at')

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        recipient = serializer.validated_data.get('recipient')
        if recipient and getattr(recipient.company, 'tenant_id', None) != getattr(tenant, 'id', None):
            raise ValidationError('Recipient does not belong to the active tenant.')
        serializer.save(tenant=tenant, sender=self.request.user)


class AnnouncementViewSet(TenantScopedViewSet):
    queryset = Announcement.objects.select_related('company', 'published_by')
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'content']

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        company = getattr(self.request.user, 'company', None)
        serializer.save(
            tenant=tenant,
            company=company,
            published_by=self.request.user,
        )


class AnnouncementReadViewSet(TenantScopedViewSet):
    queryset = AnnouncementRead.objects.select_related('announcement', 'user')
    serializer_class = AnnouncementReadSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        queryset = super().get_queryset()
        announcement_id = self.request.query_params.get('announcement')
        if announcement_id:
            queryset = queryset.filter(announcement_id=announcement_id)
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        serializer.save(tenant=tenant, user=self.request.user)
