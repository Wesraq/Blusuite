from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from accounts.models import CompanyDepartment

User = get_user_model()


class AssetCategory(models.Model):
    """Categories for organizing assets"""
    name = models.CharField(_('category name'), max_length=100, unique=True)
    description = models.TextField(_('description'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('asset category')
        verbose_name_plural = _('asset categories')
        ordering = ['name']

    def __str__(self):
        return self.name


class EmployeeAsset(models.Model):
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
    asset_tag = models.CharField(_('asset tag'), max_length=100, unique=True, help_text=_('Unique asset identifier'))
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

    def __str__(self):
        employee_name = self.employee.get_full_name() if self.employee else "Unassigned"
        return f"{self.asset_tag} - {self.name} ({employee_name})"

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


class AssetMaintenanceLog(models.Model):
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

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.get_maintenance_type_display()} ({self.performed_date})"


class AssetRequest(models.Model):
    """Model for department managers to request new assets from admin"""
    
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
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_requests_approved',
        verbose_name=_('approved by')
    )
    approval_date = models.DateTimeField(_('approval date'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    admin_notes = models.TextField(_('admin notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('asset request')
        verbose_name_plural = _('asset requests')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.department.name} - {self.asset_name} ({self.get_status_display()})"
