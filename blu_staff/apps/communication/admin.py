from django.contrib import admin
from .models import (
    ChatGroup,
    GroupMessage,
    GroupMessageRead,
    DirectMessage,
    Announcement,
    AnnouncementRead
)


@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'group_type', 'company', 'is_private', 'is_active', 'get_member_count', 'created_at')
    list_filter = ('group_type', 'is_private', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('admins', 'members')
    readonly_fields = ('created_at', 'updated_at', 'last_activity')
    
    fieldsets = (
        ('Group Information', {
            'fields': ('name', 'description', 'group_type', 'company')
        }),
        ('Ownership & Members', {
            'fields': ('created_by', 'admins', 'members')
        }),
        ('Group Image', {
            'fields': ('group_image',)
        }),
        ('Settings', {
            'fields': ('is_private', 'allow_member_posts', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_activity'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = ('group', 'sender', 'message_type', 'is_pinned', 'is_deleted', 'created_at')
    list_filter = ('message_type', 'is_pinned', 'is_deleted', 'created_at')
    search_fields = ('content', 'group__name', 'sender__first_name', 'sender__last_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GroupMessageRead)
class GroupMessageReadAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'last_read_at')
    list_filter = ('last_read_at',)
    search_fields = ('user__first_name', 'user__last_name', 'group__name')


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__first_name', 'sender__last_name', 'recipient__first_name', 'recipient__last_name', 'content')
    readonly_fields = ('created_at',)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'priority', 'audience_type', 'is_published', 'published_at', 'created_at')
    list_filter = ('priority', 'audience_type', 'is_published', 'requires_acknowledgment', 'created_at')
    search_fields = ('title', 'content')
    filter_horizontal = ('specific_users',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Announcement Details', {
            'fields': ('title', 'content', 'priority', 'attachment')
        }),
        ('Audience', {
            'fields': ('company', 'audience_type', 'target_department', 'target_branch', 'specific_users')
        }),
        ('Publishing', {
            'fields': ('published_by', 'is_published', 'published_at', 'expires_at')
        }),
        ('Settings', {
            'fields': ('requires_acknowledgment', 'send_email', 'send_notification')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AnnouncementRead)
class AnnouncementReadAdmin(admin.ModelAdmin):
    list_display = ('announcement', 'user', 'read_at', 'acknowledged', 'acknowledged_at')
    list_filter = ('acknowledged', 'read_at')
    search_fields = ('announcement__title', 'user__first_name', 'user__last_name')
