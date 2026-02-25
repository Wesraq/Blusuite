from rest_framework import serializers

from .models import (
    TrainingProgram,
    TrainingEnrollment,
    Certification,
    TrainingRequest,
)


class TrainingProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingProgram
        fields = [
            'id', 'department', 'created_by', 'title', 'description', 'program_type',
            'duration_hours', 'is_mandatory', 'cost', 'provider', 'instructor',
            'is_active', 'requires_approval', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data.setdefault('created_by', request.user)
            validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)

    def validate_department(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if value and tenant and getattr(value.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError('Department does not belong to this tenant.')
        return value


class TrainingEnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingEnrollment
        fields = [
            'id', 'employee', 'program', 'enrollment_date', 'start_date', 'completion_date',
            'status', 'score', 'feedback', 'certificate_url', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        program = attrs.get('program') or getattr(self.instance, 'program', None)
        employee = attrs.get('employee') or getattr(self.instance, 'employee', None)
        if tenant:
            if program and program.tenant_id != tenant.id:
                raise serializers.ValidationError({'program': 'Training program does not belong to this tenant.'})
            if employee and getattr(employee.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'employee': 'Employee does not belong to this tenant.'})
        return attrs


class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = [
            'id', 'employee', 'name', 'issuing_organization', 'issue_date',
            'expiry_date', 'credential_id', 'credential_url', 'status', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_employee(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and getattr(value.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError('Employee does not belong to this tenant.')
        return value


class TrainingRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingRequest
        fields = [
            'id', 'department', 'requested_by', 'training_title', 'program_type',
            'description', 'target_employees', 'duration_hours', 'estimated_cost',
            'preferred_provider', 'priority', 'business_justification', 'urgency_reason',
            'status', 'approved_by', 'approval_date', 'rejection_reason', 'admin_notes',
            'created_training', 'created_at', 'updated_at'
        ]
        read_only_fields = ['requested_by', 'approved_by', 'approval_date', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data.setdefault('requested_by', request.user)
            validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)

    def validate_department(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and getattr(value.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError('Department does not belong to this tenant.')
        return value
