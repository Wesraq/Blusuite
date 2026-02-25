from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from decimal import Decimal

from tenant_management.models import TenantScopedModel, TenantScopedManager

User = get_user_model()


class SalaryStructure(TenantScopedModel):
    """Model for employee salary structure"""
    
    class PaymentFrequency(models.TextChoices):
        MONTHLY = 'MONTHLY', _('Monthly')
        BIWEEKLY = 'BIWEEKLY', _('Bi-weekly')
        WEEKLY = 'WEEKLY', _('Weekly')
    
    employee = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='salary_structure',
        limit_choices_to={'role': 'EMPLOYEE'}
    )
    base_salary = models.DecimalField(_('base salary'), max_digits=12, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    payment_frequency = models.CharField(
        _('payment frequency'),
        max_length=20,
        choices=PaymentFrequency.choices,
        default=PaymentFrequency.MONTHLY
    )
    effective_date = models.DateField(_('effective date'))
    is_active = models.BooleanField(_('active'), default=True)
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('salary structure')
        verbose_name_plural = _('salary structures')
        ordering = ['-effective_date']
        unique_together = ['tenant', 'employee']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.base_salary} {self.currency}"


class Payroll(TenantScopedModel):
    """Model for monthly payroll"""
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        PENDING_APPROVAL = 'PENDING_APPROVAL', _('Pending Approval')
        APPROVED = 'APPROVED', _('Approved')
        PAID = 'PAID', _('Paid')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payrolls'
    )
    period_start = models.DateField(_('period start'))
    period_end = models.DateField(_('period end'))
    pay_date = models.DateField(_('pay date'))
    
    # Earnings
    base_pay = models.DecimalField(_('base pay'), max_digits=12, decimal_places=2)
    overtime_pay = models.DecimalField(_('overtime pay'), max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(_('bonus'), max_digits=12, decimal_places=2, default=0)
    commission = models.DecimalField(_('commission'), max_digits=12, decimal_places=2, default=0)
    allowances = models.DecimalField(_('allowances'), max_digits=12, decimal_places=2, default=0)
    gratuity = models.DecimalField(_('gratuity'), max_digits=12, decimal_places=2, default=0)
    
    # Deductions
    tax = models.DecimalField(_('tax'), max_digits=12, decimal_places=2, default=0)
    social_security = models.DecimalField(_('social security'), max_digits=12, decimal_places=2, default=0)
    insurance = models.DecimalField(_('insurance'), max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(_('other deductions'), max_digits=12, decimal_places=2, default=0)
    
    # Calculated fields
    gross_pay = models.DecimalField(_('gross pay'), max_digits=12, decimal_places=2)
    total_deductions = models.DecimalField(_('total deductions'), max_digits=12, decimal_places=2)
    net_pay = models.DecimalField(_('net pay'), max_digits=12, decimal_places=2)
    
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    notes = models.TextField(_('notes'), blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_payrolls'
    )
    approved_at = models.DateTimeField(_('approved at'), null=True, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('payroll')
        verbose_name_plural = _('payrolls')
        ordering = ['-period_end', '-pay_date']
        unique_together = ['tenant', 'employee', 'period_start', 'period_end']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.period_start} to {self.period_end}"
    
    def save(self, *args, **kwargs):
        # Calculate totals
        self.gross_pay = (
            self.base_pay + self.overtime_pay + self.bonus + 
            self.commission + self.allowances + self.gratuity
        )
        self.total_deductions = (
            self.tax + self.social_security + self.insurance + self.other_deductions
        )
        self.net_pay = self.gross_pay - self.total_deductions
        super().save(*args, **kwargs)


class Benefit(TenantScopedModel):
    """Model for employee benefits"""
    
    class BenefitType(models.TextChoices):
        HEALTH_INSURANCE = 'HEALTH_INSURANCE', _('Health Insurance')
        DENTAL_INSURANCE = 'DENTAL_INSURANCE', _('Dental Insurance')
        VISION_INSURANCE = 'VISION_INSURANCE', _('Vision Insurance')
        LIFE_INSURANCE = 'LIFE_INSURANCE', _('Life Insurance')
        RETIREMENT_401K = 'RETIREMENT_401K', _('401(k) Retirement Plan')
        PENSION = 'PENSION', _('Pension Plan')
        PAID_TIME_OFF = 'PAID_TIME_OFF', _('Paid Time Off')
        SICK_LEAVE = 'SICK_LEAVE', _('Sick Leave')
        STUDY_LEAVE = 'STUDY_LEAVE', _('Study Leave')
        PARENTAL_LEAVE = 'PARENTAL_LEAVE', _('Parental Leave')
        TRANSPORT = 'TRANSPORT', _('Transportation Allowance')
        MEAL_VOUCHER = 'MEAL_VOUCHER', _('Meal Voucher')
        GYM_MEMBERSHIP = 'GYM_MEMBERSHIP', _('Gym Membership')
        OTHER = 'OTHER', _('Other')
    
    name = models.CharField(_('benefit name'), max_length=200)
    benefit_type = models.CharField(
        _('benefit type'),
        max_length=30,
        choices=BenefitType.choices,
        default=BenefitType.OTHER
    )
    description = models.TextField(_('description'), blank=True)
    company_contribution = models.DecimalField(
        _('company contribution'),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_('Amount company pays per month')
    )
    employee_contribution = models.DecimalField(
        _('employee contribution'),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_('Amount employee pays per month')
    )
    is_mandatory = models.BooleanField(_('mandatory'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('benefit')
        verbose_name_plural = _('benefits')
        ordering = ['name']
        unique_together = ['tenant', 'name']
    
    def __str__(self):
        return self.name


class EmployeeBenefit(TenantScopedModel):
    """Model for employee benefit enrollment"""
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        ACTIVE = 'ACTIVE', _('Active')
        SUSPENDED = 'SUSPENDED', _('Suspended')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='enrolled_benefits'
    )
    benefit = models.ForeignKey(
        Benefit,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    enrollment_date = models.DateField(_('enrollment date'))
    effective_date = models.DateField(_('effective date'))
    end_date = models.DateField(_('end date'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('employee benefit')
        verbose_name_plural = _('employee benefits')
        ordering = ['-enrollment_date']
        unique_together = ['tenant', 'employee', 'benefit', 'enrollment_date']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.benefit.name}"


class BenefitClaim(TenantScopedModel):
    """Claims submitted by employees against a benefit"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='benefit_claims',
        limit_choices_to={'role': 'EMPLOYEE'}
    )
    benefit = models.ForeignKey(
        Benefit,
        on_delete=models.CASCADE,
        related_name='claims'
    )
    enrollment = models.ForeignKey(
        EmployeeBenefit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claims'
    )
    amount = models.DecimalField(_('claimed amount'), max_digits=10, decimal_places=2, null=True, blank=True)
    description = models.TextField(_('claim description'), blank=True)
    attachment = models.FileField(_('supporting file'), upload_to='benefit_claims/', null=True, blank=True)
    status = models.CharField(_('status'), max_length=20, choices=Status.choices, default=Status.PENDING)
    hr_note = models.TextField(_('HR note'), blank=True)
    submitted_at = models.DateTimeField(_('submitted at'), auto_now_add=True)
    reviewed_at = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='benefit_claims_reviewed',
        limit_choices_to={'role__in': ['EMPLOYER_ADMIN', 'ADMINISTRATOR', 'EMPLOYEE']}
    )

    objects = TenantScopedManager()

    class Meta:
        verbose_name = _('benefit claim')
        verbose_name_plural = _('benefit claims')
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.benefit.name} claim"


class PayrollDeduction(TenantScopedModel):
    """Detailed deductions for payroll"""
    
    class DeductionType(models.TextChoices):
        PAYE = 'PAYE', _('PAYE (Income Tax)')
        NAPSA = 'NAPSA', _('NAPSA (Social Security)')
        NHIMA = 'NHIMA', _('NHIMA (Health Insurance)')
        LATE = 'LATE', _('Late Deduction')
        ABSENT = 'ABSENT', _('Absent Deduction')
        LOAN = 'LOAN', _('Loan Repayment')
        ADVANCE = 'ADVANCE', _('Salary Advance')
        OTHER = 'OTHER', _('Other Deduction')
    
    payroll = models.ForeignKey(
        Payroll,
        on_delete=models.CASCADE,
        related_name='detailed_deductions'
    )
    deduction_type = models.CharField(
        _('deduction type'),
        max_length=20,
        choices=DeductionType.choices
    )
    amount = models.DecimalField(_('amount'), max_digits=12, decimal_places=2)
    description = models.TextField(_('description'), blank=True)
    is_statutory = models.BooleanField(_('statutory deduction'), default=False, help_text=_('PAYE, NAPSA, NHIMA'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('payroll deduction')
        verbose_name_plural = _('payroll deductions')
        ordering = ['payroll', 'deduction_type']
    
    def __str__(self):
        return f"{self.get_deduction_type_display()} - {self.amount}"
