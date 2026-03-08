from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from tenant_management.models import TenantScopedModel


class CompanyRegistrationRequest(TenantScopedModel):
    """Model for company registration requests"""

    class RequestStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    class SubscriptionPlan(models.TextChoices):
        BASIC = 'BASIC', 'Basic Plan'
        STANDARD = 'STANDARD', 'Standard Plan'
        PROFESSIONAL = 'PROFESSIONAL', 'Professional Plan'
        ENTERPRISE = 'ENTERPRISE', 'Enterprise Plan'

    class BillingPreference(models.TextChoices):
        TRIAL = 'TRIAL', 'Trial'
        MONTHLY = 'MONTHLY', 'Monthly subscription'
        YEARLY = 'YEARLY', 'Yearly subscription'

    # Company Information
    company_name = models.CharField(max_length=200)
    company_address = models.TextField()
    company_phone = models.CharField(max_length=20, blank=True)
    company_email = models.EmailField()
    company_website = models.URLField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Zambia')

    # Contact Person Information
    contact_first_name = models.CharField(max_length=100)
    contact_last_name = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    contact_position = models.CharField(max_length=100, blank=True)

    # Subscription Details
    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.BASIC
    )
    number_of_employees = models.PositiveIntegerField(default=1)
    business_type = models.CharField(max_length=100, blank=True)
    company_size = models.CharField(max_length=50, blank=True)
    billing_preference = models.CharField(
        max_length=20,
        choices=BillingPreference.choices,
        default=BillingPreference.TRIAL,
    )

    # Request Status
    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING
    )
    reviewed_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    # System Generated Fields
    request_number = models.CharField(max_length=20, unique=True, blank=True)  # Auto-generated
    generated_password = models.CharField(max_length=128, blank=True)  # Temporary password
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Company Registration Request'
        verbose_name_plural = 'Company Registration Requests'

    def __str__(self):
        return f"{self.company_name} - {self.contact_email}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            # Generate unique request number
            timestamp = timezone.now().strftime('%Y%m%d')
            counter = CompanyRegistrationRequest.objects.filter(
                created_at__date=timezone.now().date()
            ).count() + 1
            self.request_number = f"REQ-{timestamp}-{counter:03d}"

        if not self.generated_password and self.status == self.RequestStatus.APPROVED:
            # Generate temporary password when approved
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            self.generated_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        super().save(*args, **kwargs)


class Company(models.Model):
    """Company model for multi-tenant structure"""
    company_id = models.CharField(max_length=20, unique=True, blank=True, help_text="Auto-generated company ID (e.g., COMP-20251007-001)")
    name = models.CharField(max_length=200, unique=True)
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    company_stamp = models.ImageField(upload_to='company_stamps/', null=True, blank=True, help_text="Company official stamp for payslips")
    signature = models.ImageField(upload_to='company_signatures/', null=True, blank=True, help_text="Authorized signatory signature")
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True, help_text="Province or state")
    country = models.CharField(max_length=100, default='Zambia')
    postal_code = models.CharField(max_length=20, blank=True, help_text="Postal / Zip code")

    industry = models.CharField(max_length=100, blank=True, help_text="Industry or sector")
    company_size = models.CharField(
        max_length=30, blank=True,
        choices=[
            ('1-10', '1-10 employees'),
            ('11-50', '11-50 employees'),
            ('51-200', '51-200 employees'),
            ('201-500', '201-500 employees'),
            ('500+', '500+ employees'),
        ],
        help_text="Approximate number of employees",
    )
    alternative_phone = models.CharField(max_length=20, blank=True, help_text="Secondary contact number")

    # Company Documents
    tax_certificate = models.FileField(upload_to='company_documents/tax/', null=True, blank=True, help_text="TPIN Certificate")
    business_registration = models.FileField(upload_to='company_documents/registration/', null=True, blank=True, help_text="PACRA Certificate")
    trade_license = models.FileField(upload_to='company_documents/licenses/', null=True, blank=True, help_text="Trading License")
    napsa_certificate = models.FileField(upload_to='company_documents/napsa/', null=True, blank=True, help_text="NAPSA Certificate")
    nhima_certificate = models.FileField(upload_to='company_documents/nhima/', null=True, blank=True, help_text="NHIMA Certificate")
    workers_compensation = models.FileField(upload_to='company_documents/wcf/', null=True, blank=True, help_text="Workers Compensation Certificate")
    
    # Corporate Branding Colors
    primary_color = models.CharField(max_length=7, default='#2d3748', help_text="Top bar & sidebar color")
    secondary_color = models.CharField(max_length=7, default='#718096', help_text="Secondary/accent color (hex)")
    text_color = models.CharField(max_length=7, default='#1e293b', help_text="Primary text color (hex)")
    background_color = models.CharField(max_length=7, default='#ffffff', help_text="Background color (hex)")
    card_header_color = models.CharField(max_length=7, default='#10b981', help_text="Content card header color")
    button_color = models.CharField(max_length=7, default='#3b82f6', help_text="Primary button color")
    
    # Payslip Design Settings
    payslip_layout = models.CharField(max_length=20, default='classic', choices=[
        ('classic', 'Classic'), ('modern', 'Modern'), ('compact', 'Compact'), ('detailed', 'Detailed')
    ])
    payslip_orientation = models.CharField(max_length=10, default='portrait', choices=[
        ('portrait', 'Portrait'), ('landscape', 'Landscape')
    ])
    payslip_header_style = models.CharField(max_length=20, default='logo_left', choices=[
        ('logo_left', 'Logo Left'), ('logo_center', 'Logo Center'), 
        ('logo_right', 'Logo Right'), ('full_width', 'Full Width')
    ])
    show_company_logo = models.BooleanField(default=True)
    show_company_stamp = models.BooleanField(default=True)
    show_signature = models.BooleanField(default=True)
    show_qr_code = models.BooleanField(default=False)
    show_tax_breakdown = models.BooleanField(default=True)
    show_ytd_summary = models.BooleanField(default=False)
    payslip_header_color = models.CharField(max_length=7, default='#3b82f6')
    payslip_accent_color = models.CharField(max_length=7, default='#10b981')
    payslip_section_color = models.CharField(max_length=7, default='#C5D9F1', blank=True, help_text='Color for section headers (Earnings, Deductions, etc.)')
    payslip_footer_text = models.TextField(blank=True, default='This is a computer-generated payslip and does not require a signature.')
    show_confidentiality_notice = models.BooleanField(default=True)
    
    # Advanced Payslip Customization
    payslip_logo_position = models.CharField(max_length=50, default='top-left', help_text='Logo position (e.g., top-left, top-center)')
    payslip_stamp_position = models.CharField(max_length=50, default='bottom-right', help_text='Stamp position')
    payslip_address_position = models.CharField(max_length=50, default='top-right', help_text='Company address position')
    payslip_header_content = models.TextField(blank=True, help_text='Custom header HTML/text')
    payslip_footer_content = models.TextField(blank=True, help_text='Custom footer HTML/text')
    payslip_section_order = models.JSONField(default=list, blank=True, help_text='Order of sections: employee_info, salary_info, deductions, etc.')
    payslip_field_positions = models.JSONField(default=dict, blank=True, help_text='Custom field positions for drag-and-drop')

    # GPS Geofencing Settings for Attendance
    office_location_name = models.CharField(
        max_length=500, blank=True,
        help_text="Office location name/address (e.g., '123 Main St, Lusaka, Zambia')"
    )
    office_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Office location latitude for GPS attendance verification"
    )
    office_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Office location longitude for GPS attendance verification"
    )
    geofence_radius_meters = models.PositiveIntegerField(
        default=100,
        help_text="Allowed radius in meters from office location for clock-in (default: 100m)"
    )
    enforce_geofencing = models.BooleanField(
        default=False,
        help_text="Require employees to be within geofence radius to clock in/out"
    )
    allow_remote_attendance = models.BooleanField(
        default=False,
        help_text="Allow employees to clock in from anywhere (overrides geofencing)"
    )
    
    # Contract Management Settings
    require_renewal_approval = models.BooleanField(
        default=True,
        help_text="Require admin approval for contract renewals. Disable for direct renewal (SMEs)"
    )

    # Security Settings (password policy, session, 2FA, login restrictions)
    security_settings = models.JSONField(default=dict, blank=True, help_text='Security configuration: password_policy, session, twofa, login_restrictions')

    # Multi-tenancy fields
    is_active = models.BooleanField(default=True)  # Active once approved
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_companies')
    approved_at = models.DateTimeField(null=True, blank=True)

    # License/Subscription Information
    registration_request = models.OneToOneField(
        'CompanyRegistrationRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_company'
    )
    subscription_plan = models.CharField(
        max_length=20,
        choices=CompanyRegistrationRequest.SubscriptionPlan.choices,
        default=CompanyRegistrationRequest.SubscriptionPlan.BASIC
    )
    license_key = models.CharField(max_length=100, unique=True, blank=True)  # Auto-generated
    license_expiry = models.DateField(null=True, blank=True)
    max_employees = models.PositiveIntegerField(default=10)
    is_trial = models.BooleanField(default=False)
    onboarding_complete = models.BooleanField(default=True, help_text='False for newly approved companies until QSG is completed')
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    # Parent-child relationship for sub-companies
    parent_company = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_companies')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Generate unique company ID if not exists
        if not self.company_id:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d')
            # Count companies created on the same date
            counter = Company.objects.filter(
                created_at__date=timezone.now().date()
            ).count() + 1
            self.company_id = f"COMP-{timestamp}-{counter:03d}"
        
        if not self.license_key:
            # Generate unique license key
            import secrets
            import string
            alphabet = string.ascii_uppercase + string.digits
            self.license_key = ''.join(secrets.choice(alphabet) for _ in range(16))

        super().save(*args, **kwargs)

    @property
    def is_main_company(self):
        """Check if this is a main company (not a sub-company)"""
        return self.parent_company is None

    @property
    def get_all_sub_companies(self):
        """Get all sub-companies recursively"""
        sub_companies = list(self.sub_companies.all())
        for sub_company in self.sub_companies.all():
            sub_companies.extend(sub_company.get_all_sub_companies)
        return sub_companies

    @property
    def is_license_active(self):
        """Check if company license is active"""
        if self.is_trial:
            return self.trial_ends_at > timezone.now()
        return self.license_expiry is None or self.license_expiry > timezone.now().date()


class UserManager(BaseUserManager):
    """Custom user model manager where email is the unique identifier"""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)


# SuperAdmin model removed - merged into User model


class User(AbstractUser):
    """Unified user model that supports both regular users and SuperAdmins"""

    class Role(models.TextChoices):
        SUPERADMIN = 'SUPERADMIN', 'SuperAdmin'  # System administrator
        ADMINISTRATOR = 'ADMINISTRATOR', 'Administrator'  # Company owner/admin
        EMPLOYER_ADMIN = 'EMPLOYER_ADMIN', 'Employer Admin'  # Branch/Company admin
        EMPLOYEE = 'EMPLOYEE', 'Employee'  # Regular employee

    class PlatformRole(models.TextChoices):
        OWNER = 'OWNER', 'Admin'
        SUPPORT = 'SUPPORT', 'Support'
        REGISTRATION = 'REGISTRATION', 'Registration'
        BILLING = 'BILLING', 'Billing'
        ACCOUNT_MANAGER = 'ACCOUNT_MANAGER', 'Account Manager'

    username = models.CharField(_('username'), max_length=150, blank=True, null=True, unique=True)
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default='EMPLOYEE')
    platform_role = models.CharField(
        max_length=20,
        choices=PlatformRole.choices,
        blank=True,
        null=True,
        help_text='Platform-level staff role for the technical owner portal.',
    )
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    # Password change requirement
    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)

    # SuperAdmin specific fields (for when role is SUPERADMIN)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    # Company relationship (for non-SuperAdmin users)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, null=True, blank=True, related_name='users')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    # Override groups and user_permissions to avoid clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_('The groups this user belongs to. A user will get all permissions granted to each of their groups.'),
        related_name='user_set',
        related_query_name='user'
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='user_set',
        related_query_name='user'
    )

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        db_table = 'accounts_user'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.must_change_password and not self.password_changed_at:
            # If password must be changed but hasn't been, keep the flag
            pass
        elif self.pk and not self.must_change_password:
            # If password change is not required, clear the timestamp
            self.password_changed_at = None
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        """Override to handle password change requirement"""
        super().set_password(raw_password)
        if self.must_change_password:
            self.password_changed_at = timezone.now()
            self.must_change_password = False

    @property
    def is_superadmin(self):
        return self.role == 'SUPERADMIN'

    @property
    def is_employer_admin(self):
        return self.role == 'EMPLOYER_ADMIN'

    @property
    def is_employee(self):
        return self.role == 'EMPLOYEE'

    @property
    def is_administrator(self):
        return self.role == 'ADMINISTRATOR'

    @property
    def is_employer(self):
        """Check if user is any type of employer (administrator or admin)"""
        return self.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']

    @property
    def can_manage_company(self):
        """Check if user can manage company settings"""
        return self.role in ['ADMINISTRATOR', 'SUPERADMIN']

    @property
    def can_manage_employees(self):
        """Check if user can manage employees"""
        return self.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']

    @property
    def can_approve_companies(self):
        """Check if user can approve new company requests"""
        return self.role == 'SUPERADMIN'


class EmployeeProfile(TenantScopedModel):
    """Profile model for employees"""

    class EmployeeRole(models.TextChoices):
        EMPLOYEE = 'EMPLOYEE', 'Employee'
        SUPERVISOR = 'SUPERVISOR', 'Supervisor'
        HR = 'HR', 'HR'
        ACCOUNTANT = 'ACCOUNTANT', 'Accountant'
        ACCOUNTS = 'ACCOUNTS', 'Accounts'

    class EmploymentType(models.TextChoices):
        PERMANENT = 'PERMANENT', 'Permanent'
        CONTRACT = 'CONTRACT', 'Contract'
        PROBATION = 'PROBATION', 'Probation'
        TEMPORARY = 'TEMPORARY', 'Temporary'
        INTERN = 'INTERN', 'Intern'
        PART_TIME = 'PART_TIME', 'Part-time'

    class Currency(models.TextChoices):
        ZMW = 'ZMW', 'ZMW (Zambian Kwacha)'
        USD = 'USD', 'USD (US Dollar)'

    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='employee_profile')
    employee_id = models.CharField(max_length=50, unique=True)
    job_title = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    
    # Branch and supervisor assignment
    branch = models.ForeignKey('CompanyBranch', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    supervisor = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='supervised_employees', help_text="Direct supervisor")
    
    # GPS Attendance Tracking
    require_gps_attendance = models.BooleanField(
        default=True,
        help_text="Require GPS tracking for this employee's attendance (can be disabled for remote workers)"
    )
    
    date_hired = models.DateField()
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.ZMW,
        blank=True,
    )
    pay_grade = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    on_payroll = models.BooleanField(default=True, help_text="Include employee in payroll generation and selection.")
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    emergency_contact_email = models.CharField(max_length=254, blank=True)
    emergency_contact_address = models.CharField(max_length=255, blank=True)
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        blank=True,
        default='',
    )
    # Employment type specific dates
    probation_start_date = models.DateField(null=True, blank=True, help_text='Probation period start date')
    probation_end_date = models.DateField(null=True, blank=True, help_text='Probation period end date')
    contract_start_date = models.DateField(null=True, blank=True, help_text='Contract start date')
    contract_end_date = models.DateField(null=True, blank=True, help_text='Contract end date')
    temporary_start_date = models.DateField(null=True, blank=True, help_text='Temporary employment start date')
    temporary_end_date = models.DateField(null=True, blank=True, help_text='Temporary employment end date')
    # Add company relationship for employees
    company = models.ForeignKey('Company', on_delete=models.CASCADE, null=True, blank=True)
    employee_role = models.CharField(
        max_length=20,
        choices=EmployeeRole.choices,
        default=EmployeeRole.EMPLOYEE,
    )
    signature_image = models.ImageField(upload_to='user_signatures/', null=True, blank=True, help_text="Uploaded signature for e-forms.")
    signature_pin_hash = models.CharField(max_length=128, blank=True, help_text="Hashed PIN/password protecting signature use.")

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.job_title}"

    @property
    def position(self):
        """Backward compatible alias for job title."""
        return self.job_title

    @position.setter
    def position(self, value):
        self.job_title = value or ''


class EmployerProfile(TenantScopedModel):
    """Profile model for employers"""
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='employer_profile')
    company_name = models.CharField(max_length=200)
    company_address = models.TextField()
    company_phone = models.CharField(max_length=20, blank=True)
    company_email = models.EmailField(blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    # Add company relationship for employers
    company = models.OneToOneField('Company', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.company_name


class EmployeeIdConfiguration(TenantScopedModel):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='employee_id_config')
    prefix = models.CharField(max_length=10, blank=True)
    suffix = models.CharField(max_length=10, blank=True)
    padding = models.PositiveIntegerField(default=4)
    next_number = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Employee ID Config for {self.company.name}"

    def generate_employee_id(self) -> str:
        number = str(self.next_number).zfill(self.padding)
        return f"{self.prefix}{number}{self.suffix}"

    def increment(self):
        self.next_number += 1
        self.save(update_fields=['next_number'])


class CompanyDepartment(TenantScopedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class CompanyPosition(TenantScopedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='positions')
    name = models.CharField(max_length=100)
    department = models.ForeignKey(CompanyDepartment, on_delete=models.SET_NULL, null=True, blank=True, related_name='positions')

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class CompanyPayGrade(TenantScopedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pay_grades')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class CompanyBranch(TenantScopedModel):
    """Branch/Location model for companies with multiple locations"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, help_text="Branch code/identifier")
    
    # Location details
    address = models.TextField()
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Zambia')
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Contact information
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Branch manager
    manager = models.ForeignKey(
        'User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_branches',
        help_text="Branch Manager"
    )
    
    # GPS Geofencing for this branch
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Branch location latitude for GPS attendance verification"
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Branch location longitude for GPS attendance verification"
    )
    geofence_radius_meters = models.PositiveIntegerField(
        default=100,
        help_text="Allowed radius in meters from branch location for clock-in (default: 100m)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_head_office = models.BooleanField(default=False, help_text="Is this the main/head office?")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['company', 'code'], ['company', 'name']]
        ordering = ['-is_head_office', 'name']
        verbose_name_plural = 'Company Branches'
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"


class EnhancedDepartment(TenantScopedModel):
    """Enhanced department model with supervisors and branch assignment"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='enhanced_departments')
    branch = models.ForeignKey(CompanyBranch, on_delete=models.CASCADE, related_name='departments', null=True, blank=True)
    
    # Department details
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Department head/supervisor
    head = models.ForeignKey(
        'User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='headed_departments',
        help_text="Department Head"
    )
    
    # Parent department (for sub-departments)
    parent_department = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sub_departments'
    )
    
    # Budget information
    budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='ZMW')
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['company', 'code'], ['company', 'branch', 'name']]
        ordering = ['name']
    
    def __str__(self):
        branch_name = f" - {self.branch.name}" if self.branch else ""
        return f"{self.name}{branch_name} ({self.company.name})"
    
    def get_all_employees(self):
        """Get all employees in this department"""
        return User.objects.filter(
            employee_profile__department=self.name,
            company=self.company
        )
    
    def get_employee_count(self):
        """Get count of employees in department"""
        return self.get_all_employees().count()


class CompanyEmailSettings(TenantScopedModel):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='email_settings')
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_sender_name = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    from_email = models.EmailField(blank=True)
    from_name = models.CharField(max_length=255, blank=True)
    
    # Email notification toggles
    enable_email_notifications = models.BooleanField(default=False, help_text='Master switch for all email notifications')
    enable_performance_emails = models.BooleanField(default=True)
    enable_leave_emails = models.BooleanField(default=True)
    enable_attendance_emails = models.BooleanField(default=True)
    enable_payroll_emails = models.BooleanField(default=True)
    enable_training_emails = models.BooleanField(default=True)
    enable_document_emails = models.BooleanField(default=True)

    def __str__(self):
        return f"Email Settings for {self.company.name}"


class CompanyBiometricSettings(TenantScopedModel):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='biometric_settings')
    provider = models.CharField(max_length=100, blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    device_serial = models.CharField(max_length=100, blank=True)
    endpoint = models.CharField(max_length=255, blank=True)
    device_ip = models.GenericIPAddressField(null=True, blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    api_secret = models.CharField(max_length=255, blank=True)
    webhook_url = models.URLField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    sync_interval = models.PositiveIntegerField(default=15)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Biometric Settings for {self.company.name}"


class CompanyAttendanceSettings(TenantScopedModel):
    """Settings for attendance module"""
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='attendance_settings')
    year_range_past = models.PositiveIntegerField(default=2, help_text="Number of past years to show in year dropdown")
    year_range_future = models.PositiveIntegerField(default=2, help_text="Number of future years to show in year dropdown")
    
    # Late threshold settings
    late_grace_minutes = models.PositiveIntegerField(default=15, help_text="Grace period in minutes before marking as late")
    expected_work_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.0, help_text="Expected work hours per day")
    overtime_threshold = models.DecimalField(max_digits=4, decimal_places=2, default=8.0, help_text="Hours threshold for overtime")
    
    class Meta:
        verbose_name = 'Company Attendance Settings'
        verbose_name_plural = 'Company Attendance Settings'
    
    def __str__(self):
        return f"Attendance Settings for {self.company.name}"


class CompanyHoliday(TenantScopedModel):
    """Public holidays for companies"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='holidays')
    name = models.CharField(max_length=200, help_text="Holiday name (e.g., Christmas Day, New Year)")
    date = models.DateField()
    is_recurring = models.BooleanField(default=False, help_text="Recurring annually on same date")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Company Holiday'
        verbose_name_plural = 'Company Holidays'
        unique_together = [('tenant', 'company', 'date')]
        ordering = ['date']
    
    def __str__(self):
        return f"{self.name} - {self.date.strftime('%Y-%m-%d')} ({self.company.name})"


class CompanyNotificationSettings(TenantScopedModel):
    """Notification preferences for companies"""
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='notification_settings')
    
    # Email Notifications
    email_leave_requests = models.BooleanField(default=True, help_text="Notify managers of leave requests")
    email_leave_approvals = models.BooleanField(default=True, help_text="Notify employees of leave approvals/rejections")
    email_document_uploads = models.BooleanField(default=True, help_text="Notify on document uploads")
    email_performance_reminders = models.BooleanField(default=False, help_text="Send performance review reminders")
    email_training_assignments = models.BooleanField(default=False, help_text="Notify on training assignments")
    
    # In-App Notifications
    inapp_realtime = models.BooleanField(default=True, help_text="Real-time in-app notifications")
    inapp_sound_alerts = models.BooleanField(default=True, help_text="Play sound for notifications")
    inapp_desktop_notifications = models.BooleanField(default=False, help_text="Browser desktop notifications")
    
    # Notification Frequency
    digest_time = models.TimeField(default='09:00:00', help_text="Time to send daily digest emails")
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ('IMMEDIATE', 'Immediate'),
            ('DAILY', 'Daily Digest'),
            ('WEEKLY', 'Weekly Digest')
        ],
        default='DAILY'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Company Notification Settings'
        verbose_name_plural = 'Company Notification Settings'
    
    def __str__(self):
        return f"Notification Settings for {self.company.name}"


from .integration_models import Integration, CompanyIntegration, IntegrationLog  # noqa: E402


class CompanyAPIKey(TenantScopedModel):
    """API keys for company integrations"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='api_keys')
    key = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100, help_text="Name/description for this key")
    is_active = models.BooleanField(default=True)
    webhook_url = models.URLField(blank=True, help_text="Webhook URL for receiving events")
    
    # Permissions
    scopes = models.JSONField(default=list, help_text="List of allowed API scopes/permissions")
    
    # Usage tracking
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Company API Key'
        verbose_name_plural = 'Company API Keys'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.company.name}"


class PayrollDeductionSettings(models.Model):
    """Payroll deduction configuration for a company"""
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='payroll_deduction_settings')
    
    # PAYE (Income Tax) Settings - JSON structure for tax brackets
    # Example: [{"min": 0, "max": 4800, "rate": 0}, {"min": 4801, "max": 9999999, "rate": 37.5}]
    paye_tax_brackets = models.JSONField(
        default=list,
        help_text="Tax brackets with min, max, and rate percentage"
    )
    paye_enabled = models.BooleanField(default=True)
    
    # NAPSA (Social Security) Settings
    napsa_employee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.0,
        help_text="Employee contribution percentage"
    )
    napsa_employer_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.0,
        help_text="Employer contribution percentage"
    )
    napsa_enabled = models.BooleanField(default=True)
    
    # NHIMA (Health Insurance) Settings
    nhima_employee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        help_text="Employee contribution percentage"
    )
    nhima_employer_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        help_text="Employer contribution percentage"
    )
    nhima_enabled = models.BooleanField(default=True)
    
    # Attendance-based Deductions
    late_deduction_type = models.CharField(
        max_length=20,
        choices=[('PERCENTAGE', 'Percentage of Daily Rate'), ('HOURLY_RATE', 'Hourly Rate')],
        default='PERCENTAGE',
        help_text="How to calculate late deduction"
    )
    late_deduction_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.0,
        help_text="Percentage of daily rate deducted per late occurrence"
    )
    absent_deduction_type = models.CharField(
        max_length=20,
        choices=[('DAILY_RATE', 'Full Daily Rate'), ('PERCENTAGE', 'Percentage of Daily Rate')],
        default='DAILY_RATE',
        help_text="How to calculate absence deduction"
    )
    absent_deduction_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.0,
        help_text="Percentage of daily rate deducted per absence (100 = full day's pay)"
    )
    working_days_per_month = models.IntegerField(
        default=22,
        help_text="Number of working days per month for daily rate calculation"
    )
    
    # Gratuity Settings
    gratuity_enabled = models.BooleanField(default=False)
    gratuity_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=8.33,
        help_text="Percentage of basic salary accrued monthly (8.33% = 1 month salary per year)"
    )
    gratuity_eligibility_months = models.IntegerField(
        default=12,
        help_text="Minimum months of service required for gratuity eligibility"
    )
    
    # Currency
    currency = models.CharField(max_length=3, default='ZMW')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Payroll Deduction Settings'
        verbose_name_plural = 'Payroll Deduction Settings'
    
    def __str__(self):
        return f"Deduction Settings - {self.company.name}"


class CompanySettings(TenantScopedModel):
    """Company-level settings managed by Administrator/Employer Admin."""
    
    # Module Visibility
    enable_attendance = models.BooleanField(default=True, help_text="Enable Attendance module")
    enable_leave = models.BooleanField(default=True, help_text="Enable Leave Management module")
    enable_payroll = models.BooleanField(default=True, help_text="Enable Payroll module")
    enable_performance = models.BooleanField(default=True, help_text="Enable Performance Reviews module")
    enable_training = models.BooleanField(default=True, help_text="Enable Training module")
    enable_onboarding = models.BooleanField(default=True, help_text="Enable Onboarding module")
    enable_assets = models.BooleanField(default=True, help_text="Enable Assets Management module")
    enable_eforms = models.BooleanField(default=True, help_text="Enable E-Forms module")
    enable_benefits = models.BooleanField(default=True, help_text="Enable Benefits module")
    enable_documents = models.BooleanField(default=True, help_text="Enable Documents module")
    enable_requests = models.BooleanField(default=True, help_text="Enable Employee Requests module")
    enable_communication = models.BooleanField(default=True, help_text="Enable Communication module")
    enable_reports = models.BooleanField(default=True, help_text="Enable Reports module")
    
    # Feature Flags
    enable_biometric_integration = models.BooleanField(default=False, help_text="Enable biometric device integration")
    enable_email_notifications = models.BooleanField(default=True, help_text="Enable email notifications")
    enable_sms_notifications = models.BooleanField(default=False, help_text="Enable SMS notifications")
    enable_slack_integration = models.BooleanField(default=False, help_text="Enable Slack integration")
    
    # Workflow Settings
    require_leave_approval = models.BooleanField(default=True, help_text="Require approval for leave requests")
    require_document_approval = models.BooleanField(default=True, help_text="Require approval for documents")
    require_request_approval = models.BooleanField(default=True, help_text="Require approval for employee requests")
    
    # Attendance Settings
    allow_manual_attendance = models.BooleanField(default=True, help_text="Allow manual attendance entry")
    require_attendance_photo = models.BooleanField(default=False, help_text="Require photo for attendance")
    attendance_grace_period_minutes = models.IntegerField(default=15, help_text="Grace period for late arrivals (minutes)")
    
    # Leave Settings
    max_leave_days_per_year = models.IntegerField(default=30, help_text="Maximum leave days per year")
    allow_negative_leave_balance = models.BooleanField(default=False, help_text="Allow negative leave balance")
    
    # Payroll Settings
    payroll_frequency = models.CharField(
        max_length=20,
        choices=[
            ('WEEKLY', 'Weekly'),
            ('BIWEEKLY', 'Bi-Weekly'),
            ('MONTHLY', 'Monthly'),
        ],
        default='MONTHLY',
        help_text="Payroll processing frequency"
    )
    payroll_day_of_month = models.IntegerField(default=25, help_text="Day of month for payroll processing")
    
    # Security Settings
    require_password_change_days = models.IntegerField(default=90, help_text="Days before password change required (0 = never)")
    session_timeout_minutes = models.IntegerField(default=60, help_text="Session timeout in minutes")
    enable_two_factor_auth = models.BooleanField(default=False, help_text="Enable two-factor authentication")
    
    # Branding
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True, help_text="Company logo for documents and reports")
    company_stamp = models.ImageField(upload_to='company_stamps/', blank=True, null=True, help_text="Company stamp for official documents")
    
    # Audit
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='company_settings_updates')
    
    class Meta:
        verbose_name = 'Company Settings'
        verbose_name_plural = 'Company Settings'
    
    def __str__(self):
        return f"Settings - {self.tenant.name if self.tenant else 'No Tenant'}"
    
    @classmethod
    def get_for_company(cls, company):
        """Get or create settings for a company."""
        tenant = getattr(company, 'tenant', None)
        if tenant:
            settings, created = cls.objects.get_or_create(tenant=tenant)
        else:
            settings, created = cls.objects.get_or_create(tenant=None)
        return settings


class BillingInvoice(models.Model):
    """Tracks billing history, invoices, and plan changes for a company."""

    class Status(models.TextChoices):
        PAID = 'PAID', 'Paid'
        PENDING = 'PENDING', 'Pending'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'
        CANCELLED = 'CANCELLED', 'Cancelled'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='billing_invoices')
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=100, blank=True)
    transaction_id = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Billing Invoice'
        verbose_name_plural = 'Billing Invoices'

    def __str__(self):
        return f"{self.invoice_number} - {self.company.name} - ${self.amount}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            from django.utils import timezone
            ts = timezone.now().strftime('%Y%m%d%H%M%S')
            count = BillingInvoice.objects.filter(company=self.company).count() + 1
            self.invoice_number = f"INV-{self.company.company_id or 'X'}-{ts[-6:]}-{count:04d}"
        super().save(*args, **kwargs)


class SystemSettings(models.Model):
    """Global system-wide settings for the EMS platform (System Owner only)."""

    allow_public_company_registration = models.BooleanField(
        default=True,
        help_text="Allow companies to submit registration requests via the public registration form.",
    )

    default_subscription_plan = models.CharField(
        max_length=20,
        choices=CompanyRegistrationRequest.SubscriptionPlan.choices,
        default=CompanyRegistrationRequest.SubscriptionPlan.BASIC,
        help_text="Default subscription plan suggested during company registration.",
    )

    registration_admin_email = models.EmailField(
        blank=True,
        help_text="Override notification email for new company registrations. Leave blank to use ADMIN_EMAIL.",
    )

    maintenance_mode = models.BooleanField(
        default=False,
        help_text="If enabled, the system can display maintenance notices (not yet enforced everywhere).",
    )
    maintenance_message = models.TextField(
        blank=True,
        default="The system is currently under maintenance. Please try again later.",
    )

    enable_billing_module = models.BooleanField(
        default=True,
        help_text="Enable the System Owner billing overview module.",
    )
    enable_support_module = models.BooleanField(
        default=True,
        help_text="Enable the System Owner support center module.",
    )
    enable_analytics_module = models.BooleanField(
        default=True,
        help_text="Enable the System Owner analytics dashboard.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return "System Settings"

    @classmethod
    def get_solo(cls):
        """Return the single SystemSettings instance, creating it if needed."""
        instance = cls.objects.first()
        if not instance:
            instance = cls.objects.create()
        return instance


class SystemSettingsAudit(models.Model):
    system_settings = models.ForeignKey(
        SystemSettings,
        on_delete=models.CASCADE,
        related_name='audit_entries',
    )
    changed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_settings_changes',
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    changes = models.TextField()

    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'System Settings Audit'
        verbose_name_plural = 'System Settings Audits'

    def __str__(self):
        who = self.changed_by.email if self.changed_by else 'System'
        return f"Settings change by {who} at {self.changed_at:%Y-%m-%d %H:%M:%S}"
