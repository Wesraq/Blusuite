from rest_framework import serializers

from .models import (
    SalaryStructure,
    Payroll,
    Benefit,
    EmployeeBenefit,
    PayrollDeduction,
)


class SalaryStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryStructure
        fields = [
            'id', 'employee', 'base_salary', 'currency', 'payment_frequency',
            'effective_date', 'is_active', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_employee(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and getattr(value.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError('Employee does not belong to this tenant.')
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)


class BenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Benefit
        fields = [
            'id', 'name', 'benefit_type', 'description', 'company_contribution',
            'employee_contribution', 'is_mandatory', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        queryset = Benefit.objects.filter(tenant=tenant, name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if tenant and queryset.exists():
            raise serializers.ValidationError('Benefit name already exists for this tenant.')
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)


class PayrollSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payroll
        fields = [
            'id', 'employee', 'period_start', 'period_end', 'pay_date',
            'base_pay', 'overtime_pay', 'bonus', 'commission', 'allowances', 'gratuity',
            'tax', 'social_security', 'insurance', 'other_deductions',
            'gross_pay', 'total_deductions', 'net_pay', 'currency', 'status',
            'notes', 'approved_by', 'approved_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['gross_pay', 'total_deductions', 'net_pay', 'created_at', 'updated_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        employee = attrs.get('employee') or getattr(self.instance, 'employee', None)
        approved_by = attrs.get('approved_by') or getattr(self.instance, 'approved_by', None)
        if tenant:
            if employee and getattr(employee.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'employee': 'Employee does not belong to this tenant.'})
            if approved_by and getattr(approved_by.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'approved_by': 'Approver does not belong to this tenant.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)


class EmployeeBenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeBenefit
        fields = [
            'id', 'employee', 'benefit', 'enrollment_date', 'effective_date',
            'end_date', 'status', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        employee = attrs.get('employee') or getattr(self.instance, 'employee', None)
        benefit = attrs.get('benefit') or getattr(self.instance, 'benefit', None)
        if tenant:
            if employee and getattr(employee.company, 'tenant_id', None) != tenant.id:
                raise serializers.ValidationError({'employee': 'Employee does not belong to this tenant.'})
            if benefit and benefit.tenant_id != tenant.id:
                raise serializers.ValidationError({'benefit': 'Benefit does not belong to this tenant.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)


class PayrollDeductionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollDeduction
        fields = [
            'id', 'payroll', 'deduction_type', 'amount', 'description',
            'is_statutory', 'created_at'
        ]
        read_only_fields = ['created_at']

    def validate_payroll(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError('Payroll does not belong to this tenant.')
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)
