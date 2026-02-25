"""
Benefits management utility functions for enrollment workflows and eligibility
"""
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


def check_benefit_eligibility(employee, benefit):
    """
    Check if an employee is eligible for a benefit based on various criteria
    
    Args:
        employee: User object with role='EMPLOYEE'
        benefit: Benefit object
    
    Returns:
        tuple: (is_eligible: bool, reason: str)
    """
    # Check if employee has profile
    if not hasattr(employee, 'employee_profile'):
        return False, "Employee profile not found"
    
    profile = employee.employee_profile
    
    # Check probation status
    if hasattr(profile, 'probation_end_date') and profile.probation_end_date:
        if timezone.now().date() < profile.probation_end_date:
            return False, "Employee is still on probation"
    
    # Check tenure (employment duration)
    if hasattr(profile, 'hire_date') and profile.hire_date:
        tenure_days = (timezone.now().date() - profile.hire_date).days
        
        # Some benefits require minimum tenure (e.g., 90 days)
        if benefit.benefit_type in ['RETIREMENT_401K', 'PENSION']:
            if tenure_days < 90:
                return False, f"Requires 90 days of employment (current: {tenure_days} days)"
        
        # Study leave might require 1 year
        if benefit.benefit_type == 'STUDY_LEAVE':
            if tenure_days < 365:
                return False, f"Requires 1 year of employment (current: {tenure_days} days)"
    
    # Check if employee is active
    if not employee.is_active:
        return False, "Employee is not active"
    
    # Check if already enrolled
    from payroll.models import EmployeeBenefit
    existing_enrollment = EmployeeBenefit.objects.filter(
        employee=employee,
        benefit=benefit,
        status__in=['ACTIVE', 'PENDING']
    ).exists()
    
    if existing_enrollment:
        return False, "Already enrolled in this benefit"
    
    return True, "Eligible"


def calculate_benefit_cost(employee, benefit):
    """
    Calculate the total cost of a benefit for an employee
    
    Returns:
        dict with company_contribution, employee_contribution, total_cost
    """
    company_cost = benefit.company_contribution
    employee_cost = benefit.employee_contribution
    total_cost = company_cost + employee_cost
    
    return {
        'company_contribution': float(company_cost),
        'employee_contribution': float(employee_cost),
        'total_cost': float(total_cost),
        'currency': 'USD'
    }


def enroll_employee_in_benefit(employee, benefit, enrollment_date=None, effective_date=None, notes='', tenant=None):
    """
    Enroll an employee in a benefit program
    
    Args:
        employee: User object
        benefit: Benefit object
        enrollment_date: Date of enrollment (defaults to today)
        effective_date: Date benefit becomes effective (defaults to enrollment_date)
        notes: Optional notes
        tenant: Tenant object for multi-tenancy
    
    Returns:
        EmployeeBenefit object or None if enrollment fails
    """
    from payroll.models import EmployeeBenefit
    
    # Check eligibility
    is_eligible, reason = check_benefit_eligibility(employee, benefit)
    if not is_eligible:
        return None, reason
    
    # Set dates
    if not enrollment_date:
        enrollment_date = timezone.now().date()
    if not effective_date:
        effective_date = enrollment_date
    
    # Create enrollment
    try:
        enrollment = EmployeeBenefit.objects.create(
            employee=employee,
            benefit=benefit,
            enrollment_date=enrollment_date,
            effective_date=effective_date,
            status='ACTIVE',
            notes=notes,
            tenant=tenant
        )
        
        # Send notification
        from notifications.utils import notify_benefit_enrollment
        notify_benefit_enrollment(enrollment, tenant=tenant)
        
        return enrollment, "Successfully enrolled"
    except Exception as e:
        return None, f"Enrollment failed: {str(e)}"


def get_employee_benefits_summary(employee):
    """
    Get a summary of all benefits for an employee
    
    Returns:
        dict with active benefits, pending benefits, total costs
    """
    from payroll.models import EmployeeBenefit
    
    active_benefits = EmployeeBenefit.objects.filter(
        employee=employee,
        status='ACTIVE'
    ).select_related('benefit')
    
    pending_benefits = EmployeeBenefit.objects.filter(
        employee=employee,
        status='PENDING'
    ).select_related('benefit')
    
    # Calculate total costs
    total_company_contribution = sum([eb.benefit.company_contribution for eb in active_benefits])
    total_employee_contribution = sum([eb.benefit.employee_contribution for eb in active_benefits])
    
    return {
        'active_benefits': list(active_benefits),
        'pending_benefits': list(pending_benefits),
        'active_count': active_benefits.count(),
        'pending_count': pending_benefits.count(),
        'total_company_contribution': float(total_company_contribution),
        'total_employee_contribution': float(total_employee_contribution),
        'total_monthly_cost': float(total_company_contribution + total_employee_contribution)
    }


def get_available_benefits_for_employee(employee, company):
    """
    Get all benefits available to an employee based on eligibility
    
    Returns:
        list of dicts with benefit info and eligibility status
    """
    from payroll.models import Benefit
    
    all_benefits = Benefit.objects.filter(
        tenant=getattr(employee, 'tenant', None),
        is_active=True
    )
    
    available_benefits = []
    
    for benefit in all_benefits:
        is_eligible, reason = check_benefit_eligibility(employee, benefit)
        cost_info = calculate_benefit_cost(employee, benefit)
        
        available_benefits.append({
            'benefit': benefit,
            'is_eligible': is_eligible,
            'eligibility_reason': reason,
            'company_contribution': cost_info['company_contribution'],
            'employee_contribution': cost_info['employee_contribution'],
            'total_cost': cost_info['total_cost']
        })
    
    return available_benefits


def suspend_benefit_enrollment(enrollment, reason=''):
    """Suspend a benefit enrollment"""
    enrollment.status = 'SUSPENDED'
    enrollment.notes = f"{enrollment.notes}\nSuspended: {reason}" if enrollment.notes else f"Suspended: {reason}"
    enrollment.save()
    return True


def cancel_benefit_enrollment(enrollment, reason=''):
    """Cancel a benefit enrollment"""
    enrollment.status = 'CANCELLED'
    enrollment.end_date = timezone.now().date()
    enrollment.notes = f"{enrollment.notes}\nCancelled: {reason}" if enrollment.notes else f"Cancelled: {reason}"
    enrollment.save()
    return True


def reactivate_benefit_enrollment(enrollment):
    """Reactivate a suspended benefit enrollment"""
    if enrollment.status == 'SUSPENDED':
        enrollment.status = 'ACTIVE'
        enrollment.notes = f"{enrollment.notes}\nReactivated on {timezone.now().date()}" if enrollment.notes else f"Reactivated on {timezone.now().date()}"
        enrollment.save()
        return True
    return False


def bulk_enroll_employees(employees, benefit, enrollment_date=None, effective_date=None, tenant=None):
    """
    Enroll multiple employees in a benefit
    
    Returns:
        dict with success_count, failed_count, and details
    """
    results = {
        'success_count': 0,
        'failed_count': 0,
        'details': []
    }
    
    for employee in employees:
        enrollment, message = enroll_employee_in_benefit(
            employee, benefit, enrollment_date, effective_date, tenant=tenant
        )
        
        if enrollment:
            results['success_count'] += 1
            results['details'].append({
                'employee': employee.get_full_name(),
                'status': 'success',
                'message': message
            })
        else:
            results['failed_count'] += 1
            results['details'].append({
                'employee': employee.get_full_name(),
                'status': 'failed',
                'message': message
            })
    
    return results
