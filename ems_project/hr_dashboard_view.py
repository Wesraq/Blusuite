"""
HR Dashboard View Function
Add this to frontend_views.py
"""

@login_required
def hr_dashboard(request):
    """HR Dashboard - HR-specific operations and metrics"""
    # Check if user has HR role
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'HR':
            messages.error(request, 'Access denied. HR role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    from django.db.models import Count, Q
    from datetime import date, timedelta
    from attendance.models import Attendance
    from requests.models import LeaveRequest
    from documents.models import EmployeeDocument
    from onboarding.models import EmployeeOnboarding
    from training.models import TrainingEnrollment
    from accounts.models import Department
    
    company = request.user.company
    today = date.today()
    first_day_month = today.replace(day=1)
    
    # Total employees
    total_employees = User.objects.filter(
        company=company,
        role='EMPLOYEE',
        is_active=True
    ).count()
    
    # New hires this month
    new_this_month = User.objects.filter(
        company=company,
        role='EMPLOYEE',
        date_joined__gte=first_day_month
    ).count()
    
    # Pending leave requests
    pending_leave = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).count()
    
    # Pending documents
    pending_documents = EmployeeDocument.objects.filter(
        employee__company=company,
        status='PENDING'
    ).count()
    
    # Active onboarding
    active_onboarding = EmployeeOnboarding.objects.filter(
        employee__company=company,
        status='IN_PROGRESS'
    ).count()
    
    # Training completion rate
    total_training = TrainingEnrollment.objects.filter(
        employee__company=company
    ).count()
    completed_training = TrainingEnrollment.objects.filter(
        employee__company=company,
        status='COMPLETED'
    ).count()
    training_completion = round((completed_training / total_training * 100) if total_training > 0 else 0, 1)
    
    # Pending leave requests with details (for approval section)
    pending_leave_requests = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).select_related('employee').order_by('-created_at')[:5]
    
    # Recent hires
    recent_hires = User.objects.filter(
        company=company,
        role='EMPLOYEE'
    ).select_related('employee_profile__department').order_by('-date_joined')[:5]
    
    # Onboarding progress
    onboarding_list = EmployeeOnboarding.objects.filter(
        employee__company=company,
        status='IN_PROGRESS'
    ).select_related('employee')[:5]
    
    # Calculate progress for each onboarding
    for onboarding in onboarding_list:
        total_tasks = onboarding.tasks.count()
        completed_tasks = onboarding.tasks.filter(status='COMPLETED').count()
        onboarding.progress = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
    
    # Training statistics
    in_progress_training = TrainingEnrollment.objects.filter(
        employee__company=company,
        status='IN_PROGRESS'
    ).count()
    
    overdue_training = TrainingEnrollment.objects.filter(
        employee__company=company,
        status__in=['NOT_STARTED', 'IN_PROGRESS'],
        target_completion_date__lt=today
    ).count()
    
    # Department statistics
    departments = Department.objects.filter(
        company=company
    ).annotate(
        employee_count=Count('employeeprofile', filter=Q(employeeprofile__user__is_active=True))
    ).order_by('-employee_count')
    
    context = {
        'current_date': today,
        'total_employees': total_employees,
        'new_this_month': new_this_month,
        'pending_leave': pending_leave,
        'pending_documents': pending_documents,
        'active_onboarding': active_onboarding,
        'training_completion': training_completion,
        'pending_leave_requests': pending_leave_requests,
        'recent_hires': recent_hires,
        'onboarding_list': onboarding_list,
        'total_training': total_training,
        'completed_training': completed_training,
        'in_progress_training': in_progress_training,
        'overdue_training': overdue_training,
        'departments': departments,
    }
    
    return render(request, 'ems/hr_dashboard.html', context)


@login_required
def accountant_dashboard(request):
    """Accountant Dashboard - Finance and payroll operations"""
    # Check if user has Accountant role
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'ACCOUNTANT':
            messages.error(request, 'Access denied. Accountant role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    from django.db.models import Sum, Count, Q
    from datetime import date
    from payroll.models import Payroll, EmployeeBenefit, PayrollDeduction
    
    company = request.user.company
    today = date.today()
    first_day_month = today.replace(day=1)
    currency = 'USD'  # Get from company settings if available
    
    # Active employees on payroll
    active_employees = User.objects.filter(
        company=company,
        role='EMPLOYEE',
        is_active=True
    ).count()
    
    # Payroll statistics for current month
    current_month_payrolls = Payroll.objects.filter(
        employee__company=company,
        period_start__gte=first_day_month
    )
    
    # Monthly payroll total
    monthly_payroll = current_month_payrolls.aggregate(
        Sum('net_pay')
    )['net_pay__sum'] or 0
    
    # Pending payroll
    pending_payroll = current_month_payrolls.filter(
        status__in=['DRAFT', 'PENDING_APPROVAL']
    ).count()
    
    # Total deductions
    total_deductions = current_month_payrolls.aggregate(
        Sum('total_deductions')
    )['total_deductions__sum'] or 0
    
    # Benefits cost
    active_benefits = EmployeeBenefit.objects.filter(
        employee__company=company,
        status='ACTIVE'
    )
    
    benefits_cost = active_benefits.aggregate(
        company_cost=Sum('benefit__company_contribution'),
        employee_cost=Sum('benefit__employee_contribution')
    )
    
    company_benefits_cost = benefits_cost['company_cost'] or 0
    employee_benefits_cost = benefits_cost['employee_cost'] or 0
    total_benefits_cost = company_benefits_cost + employee_benefits_cost
    
    # Payroll overview
    total_payrolls = current_month_payrolls.count()
    paid_payrolls = current_month_payrolls.filter(status='PAID').count()
    pending_payrolls = current_month_payrolls.filter(status='PENDING_APPROVAL').count()
    draft_payrolls = current_month_payrolls.filter(status='DRAFT').count()
    
    # Financial summary
    total_gross = current_month_payrolls.aggregate(Sum('gross_pay'))['gross_pay__sum'] or 0
    total_net = current_month_payrolls.aggregate(Sum('net_pay'))['net_pay__sum'] or 0
    
    # Deduction breakdown
    tax_deductions = current_month_payrolls.aggregate(Sum('tax'))['tax__sum'] or 0
    social_security = current_month_payrolls.aggregate(Sum('social_security'))['social_security__sum'] or 0
    insurance_deductions = current_month_payrolls.aggregate(Sum('insurance'))['insurance__sum'] or 0
    
    # Recent payroll runs
    recent_payrolls = Payroll.objects.filter(
        employee__company=company
    ).values('period_start', 'period_end', 'status').annotate(
        employee_count=Count('id'),
        total_net=Sum('net_pay')
    ).order_by('-period_start')[:5]
    
    # Deduction breakdown by type
    deduction_breakdown = PayrollDeduction.objects.filter(
        payroll__employee__company=company,
        payroll__period_start__gte=first_day_month
    ).values('deduction_type').annotate(
        amount=Sum('amount'),
        count=Count('id')
    ).order_by('-amount')
    
    for deduction in deduction_breakdown:
        deduction['type'] = dict(PayrollDeduction.DeductionType.choices).get(
            deduction['deduction_type'], 
            deduction['deduction_type']
        )
    
    context = {
        'current_date': today,
        'currency': currency,
        'active_employees': active_employees,
        'monthly_payroll': monthly_payroll,
        'pending_payroll': pending_payroll,
        'total_deductions': total_deductions,
        'benefits_cost': total_benefits_cost,
        'total_payrolls': total_payrolls,
        'paid_payrolls': paid_payrolls,
        'pending_payrolls': pending_payrolls,
        'draft_payrolls': draft_payrolls,
        'total_gross': total_gross,
        'total_net': total_net,
        'tax_deductions': tax_deductions,
        'social_security': social_security,
        'insurance_deductions': insurance_deductions,
        'recent_payrolls': recent_payrolls,
        'active_benefits': active_benefits.count(),
        'company_benefits_cost': company_benefits_cost,
        'employee_benefits_cost': employee_benefits_cost,
        'total_benefits_cost': total_benefits_cost,
        'deduction_breakdown': deduction_breakdown,
    }
    
    return render(request, 'ems/accountant_dashboard.html', context)
