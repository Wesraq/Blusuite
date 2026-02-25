from rest_framework import serializers

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'sender', 'title', 'message', 'notification_type',
            'category', 'link', 'is_read', 'read_at', 'is_email_sent', 'created_at'
        ]
        read_only_fields = ['recipient', 'created_at', 'is_email_sent']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        recipient = attrs.get('recipient') or getattr(self.instance, 'recipient', None)
        sender = attrs.get('sender') or getattr(self.instance, 'sender', None)
        if tenant:
            if recipient and getattr(recipient.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'recipient': 'Recipient does not belong to this tenant.'})
            if sender and getattr(sender.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'sender': 'Sender does not belong to this tenant.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)
        validated_data.setdefault('tenant', tenant)
        validated_data.setdefault('recipient', request.user)
        return super().create(validated_data)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user',
            'email_attendance', 'email_leave', 'email_document', 'email_performance', 'email_payroll', 'email_training',
            'inapp_attendance', 'inapp_leave', 'inapp_document', 'inapp_performance', 'inapp_payroll', 'inapp_training',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def validate_user(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and getattr(value.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError('User does not belong to this tenant.')
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        validated_data.setdefault('user', request.user)
        return super().create(validated_data)
