from rest_framework import serializers

from .models import AssetCategory, EmployeeAsset, AssetMaintenanceLog, AssetRequest


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and AssetCategory.objects.filter(tenant=tenant, name=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('Category name already exists for this tenant.')
        return value


class EmployeeAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAsset
        fields = [
            'id', 'department', 'employee', 'custodian', 'category', 'location',
            'asset_type', 'asset_tag', 'name', 'description', 'brand', 'model',
            'serial_number', 'purchase_date', 'purchase_price', 'warranty_expiry',
            'status', 'condition', 'assigned_date', 'return_date', 'notes',
            'assigned_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        asset_tag = attrs.get('asset_tag') or getattr(self.instance, 'asset_tag', None)
        if tenant and asset_tag:
            existing = EmployeeAsset.objects.filter(tenant=tenant, asset_tag=asset_tag)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({'asset_tag': 'Asset tag already exists for this tenant.'})

        department = attrs.get('department') or getattr(self.instance, 'department', None)
        if department and tenant and getattr(department.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError({'department': 'Department does not belong to this tenant.'})

        employee = attrs.get('employee') or getattr(self.instance, 'employee', None)
        if employee and tenant and getattr(employee.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError({'employee': 'Employee does not belong to this tenant.'})

        category = attrs.get('category') or getattr(self.instance, 'category', None)
        if category and category.tenant_id != tenant.id:
            raise serializers.ValidationError({'category': 'Category does not belong to this tenant.'})

        custodian = attrs.get('custodian') or getattr(self.instance, 'custodian', None)
        if custodian and tenant and getattr(custodian.company, 'tenant_id', None) != tenant.id:
            raise serializers.ValidationError({'custodian': 'Custodian does not belong to this tenant.'})

        return attrs


class AssetMaintenanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetMaintenanceLog
        fields = [
            'id', 'asset', 'maintenance_type', 'description', 'cost', 'performed_by',
            'performed_date', 'notes', 'created_by', 'created_at'
        ]
        read_only_fields = ['created_by', 'created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data.setdefault('created_by', request.user)
            validated_data.setdefault('tenant', getattr(request, 'tenant', None))
        return super().create(validated_data)

    def validate_asset(self, value):
        tenant = getattr(self.context.get('request'), 'tenant', None)
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError('Asset does not belong to this tenant.')
        return value


class AssetRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetRequest
        fields = [
            'id', 'department', 'requested_by', 'asset_type', 'asset_name',
            'description', 'quantity', 'estimated_cost', 'priority',
            'urgency_reason', 'status', 'approved_by', 'approval_date',
            'rejection_reason', 'admin_notes', 'created_at', 'updated_at'
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
