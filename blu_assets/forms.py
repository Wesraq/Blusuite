from django import forms
from .models import EmployeeAsset, AssetMaintenanceLog


class EmployeeAssetForm(forms.ModelForm):
    class Meta:
        model = EmployeeAsset
        fields = [
            'asset_type', 'asset_tag', 'name', 'description', 'brand', 'model',
            'serial_number', 'department', 'custodian', 'category', 'location',
            'condition', 'purchase_date', 'purchase_price', 'warranty_expiry',
            'quantity', 'employee', 'notes'
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'warranty_expiry': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Scope dropdowns to tenant/company if request is provided
        tenant = getattr(self.request, 'tenant', None) if self.request else None
        user = getattr(self.request, 'user', None) if self.request else None
        if tenant:
            if 'department' in self.fields and hasattr(self.fields['department'].queryset.model, 'tenant_id'):
                self.fields['department'].queryset = self.fields['department'].queryset.filter(tenant=tenant)
            if 'category' in self.fields and hasattr(self.fields['category'].queryset.model, 'tenant_id'):
                self.fields['category'].queryset = self.fields['category'].queryset.filter(tenant=tenant)
        if user and hasattr(user, 'company'):
            company = user.company
            if company:
                self.fields['employee'].queryset = self.fields['employee'].queryset.filter(
                    company=company, role='EMPLOYEE'
                )
                self.fields['department'].queryset = self.fields['department'].queryset.filter(company=company)
                self.fields['custodian'].queryset = self.fields['custodian'].queryset.filter(
                    company=company,
                    role__in=['ADMIN', 'EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN', 'DEPARTMENT_MANAGER', 'SUPERVISOR']
                )

    def clean_asset_tag(self):
        asset_tag = self.cleaned_data['asset_tag']
        tenant = getattr(self.request, 'tenant', None) if self.request else None
        qs = EmployeeAsset.objects.filter(asset_tag=asset_tag)
        if tenant:
            qs = qs.filter(tenant=tenant)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Asset tag already exists for this tenant.')
        return asset_tag

    def save(self, commit=True):
        obj = super().save(commit=False)
        tenant = getattr(self.request, 'tenant', None) if self.request else None
        if tenant:
            obj.tenant = tenant
        # Assigned_by is set only when employee chosen and not already set
        if obj.employee and not obj.assigned_by and self.request and self.request.user.is_authenticated:
            obj.assigned_by = self.request.user
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class AssetCollectionForm(forms.Form):
    employee = forms.CharField(label='Employee', max_length=200)
    position = forms.CharField(label='Position/Department', max_length=200, required=False)
    notes = forms.CharField(label='Notes', widget=forms.Textarea(attrs={'rows': 3}), required=False)
    use_saved_signature = forms.BooleanField(label='Use saved signature', required=False)
    pin = forms.CharField(label='PIN/Password', max_length=128, required=False, widget=forms.PasswordInput)
    signature_data = forms.CharField(widget=forms.HiddenInput, required=False)


class AssetMaintenanceLogForm(forms.ModelForm):
    class Meta:
        model = AssetMaintenanceLog
        fields = ['maintenance_type', 'description', 'cost', 'performed_by', 'performed_date', 'notes']
        widgets = {
            'performed_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.request and self.request.user.is_authenticated:
            obj.created_by = self.request.user
            obj.tenant = getattr(self.request, 'tenant', None)
        if commit:
            obj.save()
        return obj
