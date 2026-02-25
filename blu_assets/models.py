from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from tenant_management.models import TenantScopedModel
from blu_staff.apps.accounts.models import CompanyDepartment

User = get_user_model()


class AssetCategory(TenantScopedModel):
    """Categories for organizing assets"""
    name = models.CharField(_('category name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('asset category')
        verbose_name_plural = _('asset categories')
        ordering = ['name']
        unique_together = ['tenant', 'name']
        app_label = 'blu_assets'

    def __str__(self):
        return self.name


class EmployeeAsset(TenantScopedModel):
    """Model for tracking employee assets (laptops, phones, equipment, etc.)"""

    class AssetType(models.TextChoices):
        LAPTOP = 'LAPTOP', _('Laptop')
        DESKTOP = 'DESKTOP', _('Desktop Computer')
        PHONE = 'PHONE', _('Mobile Phone')
        TABLET = 'TABLET', _('Tablet')
        MONITOR = 'MONITOR', _('Monitor')
        KEYBOARD = 'KEYBOARD', _('Keyboard')
        MOUSE = 'MOUSE', _('Mouse')
        HEADSET = 'HEADSET', _('Headset')
        PRINTER = 'PRINTER', _('Printer')
        VEHICLE = 'VEHICLE', _('Vehicle')
        ACCESS_CARD = 'ACCESS_CARD', _('Access Card')
        UNIFORM = 'UNIFORM', _('Uniform')
        TOOLS = 'TOOLS', _('Tools')
        SOFTWARE = 'SOFTWARE', _('Software License')
        OTHER = 'OTHER', _('Other')

    class Status(models.TextChoices):
        ASSIGNED = 'ASSIGNED', _('Assigned')
        AVAILABLE = 'AVAILABLE', _('Available')
        IN_REPAIR = 'IN_REPAIR', _('In Repair')
        RETIRED = 'RETIRED', _('Retired')
        LOST = 'LOST', _('Lost')

    class Condition(models.TextChoices):
        NEW = 'NEW', _('New')
        EXCELLENT = 'EXCELLENT', _('Excellent')
        GOOD = 'GOOD', _('Good')
        FAIR = 'FAIR', _('Fair')
        POOR = 'POOR', _('Poor')

    # Department-based ownership
    department = models.ForeignKey(
        CompanyDepartment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='department_assets',
        verbose_name=_('department'),
        help_text=_('Department that owns this asset')
    )
    # Current user of the asset
    employee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets',
        limit_choices_to={'role': 'EMPLOYEE'},
        help_text=_('Employee currently using this asset')
    )
    # Department custodian/manager responsible for the asset
    custodian = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custodian_assets',
        verbose_name=_('custodian'),
        help_text=_('Department manager/supervisor responsible for this asset')
    )
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets'
    )
    # Physical location
    location = models.CharField(_('location'), max_length=200, blank=True, help_text=_('Office, room, or physical location'))
    asset_type = models.CharField(
        _('asset type'),
        max_length=20,
        choices=AssetType.choices,
        default=AssetType.OTHER
    )
    asset_tag = models.CharField(_('asset tag'), max_length=100, help_text=_('Unique asset identifier'))
    name = models.CharField(_('asset name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    brand = models.CharField(_('brand'), max_length=100, blank=True)
    model = models.CharField(_('model'), max_length=100, blank=True)
    serial_number = models.CharField(_('serial number'), max_length=200, blank=True)
    purchase_date = models.DateField(_('purchase date'), null=True, blank=True)
    purchase_price = models.DecimalField(_('purchase price'), max_digits=10, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(_('warranty expiry'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE
    )
    condition = models.CharField(
        _('condition'),
        max_length=20,
        choices=Condition.choices,
        default=Condition.NEW
    )
    assigned_date = models.DateField(_('assigned date'), null=True, blank=True)
    return_date = models.DateField(_('return date'), null=True, blank=True)
    notes = models.TextField(_('notes'), blank=True)
    quantity = models.PositiveIntegerField(_('quantity'), default=1, help_text=_('Number of units for this asset record'))
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_assets',
        limit_choices_to={'role__in': ['ADMIN', 'EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN']}
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('employee asset')
        verbose_name_plural = _('employee assets')
        ordering = ['-assigned_date', '-created_at']
        unique_together = ['tenant', 'asset_tag']
        app_label = 'blu_assets'

    def __str__(self):
        employee_name = self.employee.get_full_name() if self.employee else "Unassigned"
        return f"{self.asset_tag} - {self.name} ({employee_name})"

    def save(self, *args, **kwargs):
        """
        Normalize assignment-related fields, but respect explicit non-assignment statuses:
        - If status is IN_REPAIR/RETIRED/LOST, do not override.
        - If no employee and status is ASSIGNED, force AVAILABLE and clear dates.
        - If employee present and status is AVAILABLE, force ASSIGNED and set assigned_date.
        """
        if self.status not in [self.Status.IN_REPAIR, self.Status.RETIRED, self.Status.LOST]:
            if not self.employee:
                if self.status == self.Status.ASSIGNED:
                    self.status = self.Status.AVAILABLE
                self.assigned_date = None
                self.return_date = None
            else:
                self.status = self.Status.ASSIGNED
                if not self.assigned_date:
                    from django.utils import timezone
                    self.assigned_date = timezone.now().date()
        super().save(*args, **kwargs)

    @property
    def is_warranty_valid(self):
        """Check if warranty is still valid"""
        if self.warranty_expiry:
            from django.utils import timezone
            return self.warranty_expiry >= timezone.now().date()
        return False

    @property
    def days_with_employee(self):
        """Calculate how many days asset has been with employee"""
        if self.assigned_date and not self.return_date:
            from django.utils import timezone
            return (timezone.now().date() - self.assigned_date).days
        return 0


class AssetMaintenanceLog(TenantScopedModel):
    """Model for tracking asset maintenance"""

    class MaintenanceType(models.TextChoices):
        REPAIR = 'REPAIR', _('Repair')
        UPGRADE = 'UPGRADE', _('Upgrade')
        CLEANING = 'CLEANING', _('Cleaning')
        INSPECTION = 'INSPECTION', _('Inspection')
        OTHER = 'OTHER', _('Other')

    asset = models.ForeignKey(
        EmployeeAsset,
        on_delete=models.CASCADE,
        related_name='maintenance_logs'
    )
    maintenance_type = models.CharField(
        _('maintenance type'),
        max_length=20,
        choices=MaintenanceType.choices,
        default=MaintenanceType.REPAIR
    )
    description = models.TextField(_('description'))
    cost = models.DecimalField(_('cost'), max_digits=10, decimal_places=2, null=True, blank=True)
    performed_by = models.CharField(_('performed by'), max_length=200, blank=True)
    performed_date = models.DateField(_('performed date'))
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='asset_maintenance_logs'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('asset maintenance log')
        verbose_name_plural = _('asset maintenance logs')
        ordering = ['-performed_date']
        app_label = 'blu_assets'

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.get_maintenance_type_display()} ({self.performed_date})"


class AssetCollectionRecord(TenantScopedModel):
    """Capture collection/handover acknowledgement with signature."""
    asset = models.ForeignKey(EmployeeAsset, on_delete=models.CASCADE, related_name='collection_records')
    employee_name = models.CharField(_('employee name'), max_length=200)
    position = models.CharField(_('position/department'), max_length=200, blank=True)
    notes = models.TextField(_('notes'), blank=True)
    signature_data = models.TextField(_('signature data'), help_text=_('Base64-encoded signature image'))
    signed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='asset_collections')
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('asset collection record')
        verbose_name_plural = _('asset collection records')
        ordering = ['-signed_at']
        app_label = 'blu_assets'

    def __str__(self):
        return f"Collection for {self.asset.asset_tag} by {self.employee_name} on {self.signed_at}"

class AssetRequest(TenantScopedModel):
    """Model for employees to request new assets with department-based approval workflow"""
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending Approval')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        FULFILLED = 'FULFILLED', _('Fulfilled')
    
    class Priority(models.TextChoices):
        LOW = 'LOW', _('Low')
        MEDIUM = 'MEDIUM', _('Medium')
        HIGH = 'HIGH', _('High')
        URGENT = 'URGENT', _('Urgent')
    
    class ApprovalLevel(models.TextChoices):
        SUPERVISOR = 'SUPERVISOR', _('Supervisor Review')
        MANAGER = 'MANAGER', _('Department Manager')
        HR = 'HR', _('HR Review')
        ADMIN = 'ADMIN', _('Admin/Procurement')
    
    department = models.ForeignKey(
        CompanyDepartment,
        on_delete=models.CASCADE,
        related_name='asset_requests',
        verbose_name=_('department')
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='asset_requests_made',
        verbose_name=_('requested by')
    )
    asset_type = models.CharField(
        _('asset type'),
        max_length=20,
        choices=EmployeeAsset.AssetType.choices
    )
    asset_name = models.CharField(_('asset name'), max_length=200)
    description = models.TextField(_('description/justification'))
    quantity = models.PositiveIntegerField(_('quantity'), default=1)
    estimated_cost = models.DecimalField(_('estimated cost'), max_digits=10, decimal_places=2, null=True, blank=True)
    priority = models.CharField(
        _('priority'),
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    urgency_reason = models.TextField(_('urgency reason'), blank=True, help_text=_('Explain why this is urgent'))
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # Approval workflow fields
    current_approval_level = models.CharField(
        _('current approval level'),
        max_length=20,
        choices=ApprovalLevel.choices,
        default=ApprovalLevel.SUPERVISOR,
        help_text=_('Current stage in approval workflow')
    )
    supervisor_approved = models.BooleanField(_('supervisor approved'), default=False)
    supervisor_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_requests_supervisor_approved',
        verbose_name=_('supervisor')
    )
    supervisor_approval_date = models.DateTimeField(_('supervisor approval date'), null=True, blank=True)
    
    manager_approved = models.BooleanField(_('manager approved'), default=False)
    manager_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_requests_manager_approved',
        verbose_name=_('department manager')
    )
    manager_approval_date = models.DateTimeField(_('manager approval date'), null=True, blank=True)
    
    hr_approved = models.BooleanField(_('HR approved'), default=False)
    hr_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_requests_hr_approved',
        verbose_name=_('HR reviewer')
    )
    hr_approval_date = models.DateTimeField(_('HR approval date'), null=True, blank=True)
    
    # Final approval (kept for backward compatibility)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_requests_approved',
        verbose_name=_('final approved by')
    )
    approval_date = models.DateTimeField(_('final approval date'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    admin_notes = models.TextField(_('admin notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('asset request')
        verbose_name_plural = _('asset requests')
        ordering = ['-created_at']
        app_label = 'blu_assets'
    
    def __str__(self):
        return f"{self.department.name} - {self.asset_name} ({self.get_status_display()})"
    
    def get_approval_workflow(self):
        """
        Determine approval workflow based on department and asset type.
        Returns list of approval levels required for this request.
        """
        workflow = []
        dept_name = self.department.name.upper() if self.department else ''
        
        # Department-based routing
        if 'IT' in dept_name or 'TECH' in dept_name or self.asset_type in ['LAPTOP', 'DESKTOP', 'SOFTWARE']:
            # IT/Tech assets: Supervisor → Manager → Admin (skip HR)
            workflow = [self.ApprovalLevel.SUPERVISOR, self.ApprovalLevel.MANAGER, self.ApprovalLevel.ADMIN]
        elif 'HR' in dept_name or 'HUMAN' in dept_name:
            # HR assets: Manager → Admin (skip supervisor and HR review)
            workflow = [self.ApprovalLevel.MANAGER, self.ApprovalLevel.ADMIN]
        elif 'FINANCE' in dept_name or 'ACCOUNT' in dept_name:
            # Finance assets: Manager → Admin
            workflow = [self.ApprovalLevel.MANAGER, self.ApprovalLevel.ADMIN]
        else:
            # General departments: Full chain
            workflow = [self.ApprovalLevel.SUPERVISOR, self.ApprovalLevel.MANAGER, self.ApprovalLevel.HR, self.ApprovalLevel.ADMIN]
        
        return workflow
    
    def get_next_approval_level(self):
        """Get the next approval level in the workflow"""
        workflow = self.get_approval_workflow()
        
        # Find current position in workflow
        try:
            current_index = workflow.index(self.current_approval_level)
            if current_index + 1 < len(workflow):
                return workflow[current_index + 1]
        except (ValueError, IndexError):
            pass
        
        return None
    
    def is_approval_complete(self):
        """Check if all required approvals are obtained"""
        workflow = self.get_approval_workflow()
        
        for level in workflow:
            if level == self.ApprovalLevel.SUPERVISOR and not self.supervisor_approved:
                return False
            elif level == self.ApprovalLevel.MANAGER and not self.manager_approved:
                return False
            elif level == self.ApprovalLevel.HR and not self.hr_approved:
                return False
            elif level == self.ApprovalLevel.ADMIN and self.status != self.Status.APPROVED:
                return False
        
        return True
    
    def get_pending_approver_role(self):
        """Get the role/title of who needs to approve next"""
        if self.status == self.Status.REJECTED:
            return None
        
        workflow = self.get_approval_workflow()
        
        for level in workflow:
            if level == self.ApprovalLevel.SUPERVISOR and not self.supervisor_approved:
                return 'Supervisor'
            elif level == self.ApprovalLevel.MANAGER and not self.manager_approved:
                return 'Department Manager'
            elif level == self.ApprovalLevel.HR and not self.hr_approved:
                return 'HR'
            elif level == self.ApprovalLevel.ADMIN and self.status != self.Status.APPROVED:
                return 'Admin/Procurement'
        
        return 'Completed'
    
    def can_user_approve(self, user):
        """Check if a user can approve at the current level"""
        if self.status != self.Status.PENDING:
            return False
        
        # Admins can always approve
        if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
            return True
        
        current_level = self.current_approval_level
        
        # Check supervisor level
        if current_level == self.ApprovalLevel.SUPERVISOR:
            # User must be a supervisor in the same department
            if user.role == 'SUPERVISOR':
                user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
                return user_dept == self.department
        
        # Check manager level
        elif current_level == self.ApprovalLevel.MANAGER:
            # User must be a department manager in the same department
            if user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
                user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
                return user_dept == self.department
        
        # Check HR level
        elif current_level == self.ApprovalLevel.HR:
            # User must have HR role
            if hasattr(user, 'employee_profile'):
                return user.employee_profile.employee_type == 'HR'
        
        return False
