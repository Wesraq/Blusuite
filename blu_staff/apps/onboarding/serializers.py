from rest_framework import serializers

from .models import (
    OnboardingChecklist,
    OffboardingChecklist,
    OnboardingTask,
    OnboardingTaskCompletion,
    EmployeeOnboarding,
    EmployeeOffboarding,
)


class OnboardingChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingChecklist
        fields = [
            'id', 'name', 'description', 'is_default', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        queryset = OnboardingChecklist.objects.filter(tenant=tenant, name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if tenant and queryset.exists():
            raise serializers.ValidationError('Checklist name already exists for this tenant.')
        return value


class OffboardingChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = OffboardingChecklist
        fields = [
            'id', 'name', 'description', 'is_default', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        queryset = OffboardingChecklist.objects.filter(tenant=tenant, name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if tenant and queryset.exists():
            raise serializers.ValidationError('Checklist name already exists for this tenant.')
        return value


class OnboardingTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingTask
        fields = [
            'id', 'checklist', 'title', 'description', 'priority',
            'order', 'days_to_complete', 'assigned_to_role',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_checklist(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError('Checklist does not belong to this tenant.')
        return value


class EmployeeOnboardingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeOnboarding
        fields = [
            'id', 'employee', 'checklist', 'start_date',
            'expected_completion_date', 'actual_completion_date', 'status',
            'buddy', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        employee = attrs.get('employee') or getattr(self.instance, 'employee', None)
        checklist = attrs.get('checklist') or getattr(self.instance, 'checklist', None)
        buddy = attrs.get('buddy') or getattr(self.instance, 'buddy', None)
        if tenant:
            if employee and getattr(employee.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'employee': 'Employee does not belong to this tenant.'})
            if checklist and checklist.tenant_id != tenant.id:
                raise serializers.ValidationError({'checklist': 'Checklist does not belong to this tenant.'})
            if buddy and getattr(buddy.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'buddy': 'Buddy does not belong to this tenant.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)


class EmployeeOffboardingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeOffboarding
        fields = [
            'id', 'employee', 'checklist', 'last_working_date',
            'reason', 'status', 'exit_interview_completed',
            'exit_interview_notes', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        employee = attrs.get('employee') or getattr(self.instance, 'employee', None)
        checklist = attrs.get('checklist') or getattr(self.instance, 'checklist', None)
        if tenant:
            if employee and getattr(employee.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'employee': 'Employee does not belong to this tenant.'})
            if checklist and checklist.tenant_id != tenant.id:
                raise serializers.ValidationError({'checklist': 'Checklist does not belong to this tenant.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)


class OnboardingTaskCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingTaskCompletion
        fields = [
            'id', 'employee_onboarding', 'task', 'status',
            'completed_by', 'completed_at', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        employee_onboarding = attrs.get('employee_onboarding') or getattr(self.instance, 'employee_onboarding', None)
        task = attrs.get('task') or getattr(self.instance, 'task', None)
        completed_by = attrs.get('completed_by') or getattr(self.instance, 'completed_by', None)
        if tenant:
            if employee_onboarding and employee_onboarding.tenant_id != tenant.id:
                raise serializers.ValidationError({'employee_onboarding': 'Employee onboarding does not belong to this tenant.'})
            if task and task.tenant_id != tenant.id:
                raise serializers.ValidationError({'task': 'Task does not belong to this tenant.'})
            if completed_by and getattr(completed_by.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'completed_by': 'User does not belong to this tenant.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)
