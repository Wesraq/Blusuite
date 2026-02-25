from rest_framework import serializers

from .models import ChatGroup, GroupMessage, GroupMessageRead, DirectMessage, Announcement, AnnouncementRead


class ChatGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source='get_member_count', read_only=True)

    class Meta:
        model = ChatGroup
        fields = [
            'id', 'name', 'description', 'group_type', 'company', 'created_by',
            'admins', 'members', 'group_image', 'is_private', 'allow_member_posts',
            'is_active', 'created_at', 'updated_at', 'last_activity', 'member_count'
        ]
        read_only_fields = ['company', 'created_by', 'created_at', 'updated_at', 'last_activity', 'member_count']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data.setdefault('company', getattr(request.user, 'company', None))
            validated_data.setdefault('created_by', request.user)
            validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        company = attrs.get('company') or getattr(self.instance, 'company', None)
        if tenant and company and getattr(company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError({'company': 'Company does not belong to this tenant.'})
        return attrs


class GroupMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMessage
        fields = [
            'id', 'group', 'sender', 'message_type', 'content', 'attachment',
            'reply_to', 'is_pinned', 'is_deleted', 'deleted_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['sender', 'is_deleted', 'deleted_at', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data.setdefault('sender', request.user)
            validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)

    def validate_group(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError('Group does not belong to this tenant.')
        return value


class GroupMessageReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMessageRead
        fields = ['id', 'user', 'group', 'last_read_at']
        read_only_fields = ['last_read_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        group = attrs.get('group') or getattr(self.instance, 'group', None)
        user = attrs.get('user') or getattr(self.instance, 'user', None)
        if tenant:
            if group and group.tenant_id != tenant.id:
                raise serializers.ValidationError({'group': 'Group does not belong to this tenant.'})
            if user and getattr(user.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'user': 'User does not belong to this tenant.'})
        return attrs


class DirectMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DirectMessage
        fields = [
            'id', 'sender', 'recipient', 'content', 'attachment', 'is_read',
            'read_at', 'is_deleted_by_sender', 'is_deleted_by_recipient', 'created_at'
        ]
        read_only_fields = ['sender', 'is_read', 'read_at', 'created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data.setdefault('sender', request.user)
            validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)

    def validate_recipient(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and getattr(value.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError('Recipient does not belong to this tenant.')
        return value


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'content', 'priority', 'company', 'audience_type',
            'target_department', 'target_branch', 'specific_users', 'attachment',
            'published_by', 'is_published', 'published_at', 'expires_at',
            'requires_acknowledgment', 'send_email', 'send_notification',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['company', 'published_by', 'published_at', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data.setdefault('company', getattr(request.user, 'company', None))
            validated_data.setdefault('published_by', request.user)
            validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        company = attrs.get('company') or getattr(self.instance, 'company', None)
        if tenant and company and getattr(company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError({'company': 'Company does not belong to this tenant.'})
        return attrs


class AnnouncementReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementRead
        fields = ['id', 'announcement', 'user', 'read_at', 'acknowledged', 'acknowledged_at']
        read_only_fields = ['read_at', 'acknowledged_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        announcement = attrs.get('announcement') or getattr(self.instance, 'announcement', None)
        user = attrs.get('user') or getattr(self.instance, 'user', None)
        if tenant:
            if announcement and announcement.tenant_id != tenant.id:
                raise serializers.ValidationError({'announcement': 'Announcement does not belong to this tenant.'})
            if user and getattr(user.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'user': 'User does not belong to this tenant.'})
        return attrs
