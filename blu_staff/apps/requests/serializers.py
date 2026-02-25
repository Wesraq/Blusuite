from rest_framework import serializers

from .models import (
    RequestType,
    EmployeeRequest,
    RequestApproval,
    RequestComment,
    PettyCashRequest,
    AdvanceRequest,
    ReimbursementRequest,
)


class RequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestType
        fields = [
            'id', 'name', 'code', 'description', 'requires_approval',
            'approval_levels', 'is_active', 'icon', 'requires_amount',
            'requires_attachment', 'max_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_code(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and RequestType.objects.filter(tenant=tenant, code=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('Request type code already exists for this tenant.')
        return value


class EmployeeRequestSerializer(serializers.ModelSerializer):
    request_type = serializers.PrimaryKeyRelatedField(queryset=RequestType.objects.all())

    class Meta:
        model = EmployeeRequest
        fields = [
            'id', 'request_number', 'request_type', 'employee', 'department',
            'title', 'description', 'amount', 'currency', 'status', 'priority',
            'request_date', 'required_by', 'completed_date', 'attachment',
            'current_approval_level', 'created_at', 'updated_at'
        ]
        read_only_fields = ['request_number', 'employee', 'created_at', 'updated_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        request_type = attrs.get('request_type') or getattr(self.instance, 'request_type', None)
        if tenant:
            if request_type and request_type.tenant_id != tenant.id:
                raise serializers.ValidationError({'request_type': 'Request type does not belong to this tenant.'})
            user = self.context['request'].user
            if getattr(user.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError('Current user does not belong to this tenant.')
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('employee', request.user)
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)


class RequestApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestApproval
        fields = [
            'id', 'request', 'approval_level', 'approver', 'action', 'comments',
            'assigned_date', 'action_date'
        ]
        read_only_fields = ['assigned_date', 'action_date']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        employee_request = attrs.get('request') or getattr(self.instance, 'request', None)
        approver = attrs.get('approver') or getattr(self.instance, 'approver', None)
        if tenant:
            if employee_request and employee_request.tenant_id != tenant.id:
                raise serializers.ValidationError({'request': 'Request does not belong to this tenant.'})
            if approver and getattr(approver.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'approver': 'Approver does not belong to this tenant.'})
        return attrs


class RequestCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestComment
        fields = ['id', 'request', 'user', 'comment', 'is_internal', 'created_at']
        read_only_fields = ['created_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        employee_request = attrs.get('request') or getattr(self.instance, 'request', None)
        user = attrs.get('user') or getattr(self.context.get('request'), 'user', None)
        if tenant:
            if employee_request and employee_request.tenant_id != tenant.id:
                raise serializers.ValidationError({'request': 'Request does not belong to this tenant.'})
            if user and getattr(user.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'user': 'User does not belong to this tenant.'})
        return attrs


class PettyCashRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PettyCashRequest
        fields = [
            'id', 'request', 'purpose', 'expense_category', 'payment_method',
            'disbursed', 'disbursed_by', 'disbursed_date', 'disbursed_amount',
            'receipt_submitted', 'receipt_file'
        ]

    def validate_request(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError('Request does not belong to this tenant.')
        return value


class AdvanceRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvanceRequest
        fields = [
            'id', 'request', 'reason', 'repayment_plan', 'installments',
            'approved_amount', 'disbursed', 'disbursement_date'
        ]

    def validate_request(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError('Request does not belong to this tenant.')
        return value


class ReimbursementRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReimbursementRequest
        fields = [
            'id', 'request', 'expense_date', 'expense_category', 'vendor_name',
            'receipt_required', 'receipts', 'paid', 'payment_date', 'payment_reference'
        ]

    def validate_request(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError('Request does not belong to this tenant.')
        return value
