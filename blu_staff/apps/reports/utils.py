"""
Reporting and Analytics utility functions for the EMS
"""
from django.db.models import Count, Avg, Sum, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal


def get_employee_headcount_stats(company, tenant=None):
    """Get employee headcount statistics"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    employees = User.objects.filter(company=company, role='EMPLOYEE')
    if tenant:
        employees = employees.filter(tenant=tenant)
    
    total = employees.count()
    active = employees.filter(is_active=True).count()
    inactive = employees.filter(is_active=False).count()
    
    # By department
    by_department = employees.filter(
        employee_profile__department__isnull=False
    ).exclude(
        employee_profile__department=''
    ).values('employee_profile__department').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # By position (job_title)
    by_position = employees.filter(
        employee_profile__job_title__isnull=False
    ).exclude(
        employee_profile__job_title=''
    ).values('employee_profile__job_title').annotate(
        count=Count('id')
    ).order_by('-count')
    
    return {
        'total': total,
        'active': active,
        'inactive': inactive,
        'by_department': list(by_department),
        'by_position': list(by_position)
    }


def get_attendance_stats(company, start_date=None, end_date=None, tenant=None):
    """Get attendance statistics"""
    from attendance.models import Attendance
    
    queryset = Attendance.objects.filter(employee__company=company)
    if tenant:
        queryset = queryset.filter(tenant=tenant)
    
    if not start_date:
        start_date = timezone.now().date() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now().date()
    
    queryset = queryset.filter(date__range=[start_date, end_date])
    
    total_records = queryset.count()
    present = queryset.filter(status='PRESENT').count()
    absent = queryset.filter(status='ABSENT').count()
    late = queryset.filter(status='LATE').count()
    half_day = queryset.filter(status='HALF_DAY').count()
    
    attendance_rate = (present / total_records * 100) if total_records > 0 else 0
    
    return {
        'total_records': total_records,
        'present': present,
        'absent': absent,
        'late': late,
        'half_day': half_day,
        'attendance_rate': round(attendance_rate, 2),
        'period': f"{start_date} to {end_date}"
    }


def get_leave_stats(company, start_date=None, end_date=None, tenant=None):
    """Get leave statistics"""
    from attendance.models import LeaveRequest
    
    queryset = LeaveRequest.objects.filter(employee__company=company)
    if tenant:
        queryset = queryset.filter(tenant=tenant)
    
    if start_date and end_date:
        queryset = queryset.filter(start_date__range=[start_date, end_date])
    
    total = queryset.count()
    pending = queryset.filter(status='PENDING').count()
    approved = queryset.filter(status='APPROVED').count()
    rejected = queryset.filter(status='REJECTED').count()
    
    # By leave type
    by_type = queryset.values('leave_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Total days requested
    total_days = sum([lr.total_days for lr in queryset if hasattr(lr, 'total_days')])
    
    return {
        'total': total,
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
        'by_type': list(by_type),
        'total_days': total_days
    }


def get_document_stats(company, tenant=None):
    """Get document statistics"""
    from documents.models import EmployeeDocument
    
    queryset = EmployeeDocument.objects.filter(employee__company=company)
    if tenant:
        queryset = queryset.filter(tenant=tenant)
    
    total = queryset.count()
    pending = queryset.filter(status='PENDING').count()
    approved = queryset.filter(status='APPROVED').count()
    rejected = queryset.filter(status='REJECTED').count()
    
    # By document type
    by_type = queryset.values('document_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Total file size
    total_size = queryset.aggregate(Sum('file_size'))['file_size__sum'] or 0
    total_size_mb = round(total_size / (1024 * 1024), 2)
    
    return {
        'total': total,
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
        'by_type': list(by_type),
        'total_size_mb': total_size_mb
    }


def get_payroll_stats(company, start_date=None, end_date=None, tenant=None):
    """Get payroll statistics"""
    from payroll.models import Payroll
    
    queryset = Payroll.objects.filter(employee__company=company)
    if tenant:
        queryset = queryset.filter(tenant=tenant)
    
    if start_date and end_date:
        queryset = queryset.filter(period_start__range=[start_date, end_date])
    
    total_payrolls = queryset.count()
    
    # Status breakdown
    draft = queryset.filter(status='DRAFT').count()
    pending = queryset.filter(status='PENDING_APPROVAL').count()
    approved = queryset.filter(status='APPROVED').count()
    paid = queryset.filter(status='PAID').count()
    
    # Financial totals
    total_gross = queryset.aggregate(Sum('gross_pay'))['gross_pay__sum'] or Decimal('0')
    total_deductions = queryset.aggregate(Sum('total_deductions'))['total_deductions__sum'] or Decimal('0')
    total_net = queryset.aggregate(Sum('net_pay'))['net_pay__sum'] or Decimal('0')
    
    return {
        'total_payrolls': total_payrolls,
        'draft': draft,
        'pending': pending,
        'approved': approved,
        'paid': paid,
        'total_gross': float(total_gross),
        'total_deductions': float(total_deductions),
        'total_net': float(total_net)
    }


def get_performance_stats(company, tenant=None):
    """Get performance review statistics"""
    from performance.models import PerformanceReview
    
    queryset = PerformanceReview.objects.filter(employee__company=company)
    if tenant:
        queryset = queryset.filter(tenant=tenant)
    
    total = queryset.count()
    
    # Status breakdown
    draft = queryset.filter(status='DRAFT').count()
    submitted = queryset.filter(status='SUBMITTED').count()
    completed = queryset.filter(status='COMPLETED').count()
    
    # Average rating
    avg_rating = queryset.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0
    
    return {
        'total': total,
        'draft': draft,
        'submitted': submitted,
        'completed': completed,
        'average_rating': round(avg_rating, 2)
    }


def get_training_stats(company, tenant=None):
    """Get training statistics"""
    from training.models import TrainingEnrollment
    
    queryset = TrainingEnrollment.objects.filter(employee__company=company)
    if tenant:
        queryset = queryset.filter(tenant=tenant)
    
    total = queryset.count()
    in_progress = queryset.filter(status='IN_PROGRESS').count()
    completed = queryset.filter(status='COMPLETED').count()
    not_started = queryset.filter(status='NOT_STARTED').count()
    
    # Completion rate
    completion_rate = (completed / total * 100) if total > 0 else 0
    
    return {
        'total': total,
        'in_progress': in_progress,
        'completed': completed,
        'not_started': not_started,
        'completion_rate': round(completion_rate, 2)
    }


def get_dashboard_overview(company, tenant=None):
    """Get comprehensive dashboard overview"""
    return {
        'employees': get_employee_headcount_stats(company, tenant),
        'attendance': get_attendance_stats(company, tenant=tenant),
        'leave': get_leave_stats(company, tenant=tenant),
        'documents': get_document_stats(company, tenant),
        'payroll': get_payroll_stats(company, tenant=tenant),
        'performance': get_performance_stats(company, tenant),
        'training': get_training_stats(company, tenant)
    }


def generate_attendance_report(company, start_date, end_date, tenant=None):
    """Generate detailed attendance report"""
    from attendance.models import Attendance
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    employees = User.objects.filter(company=company, role='EMPLOYEE')
    if tenant:
        employees = employees.filter(tenant=tenant)
    
    report_data = []
    
    for employee in employees:
        attendance_records = Attendance.objects.filter(
            employee=employee,
            date__range=[start_date, end_date]
        )
        if tenant:
            attendance_records = attendance_records.filter(tenant=tenant)
        
        total_days = (end_date - start_date).days + 1
        present = attendance_records.filter(status='PRESENT').count()
        absent = attendance_records.filter(status='ABSENT').count()
        late = attendance_records.filter(status='LATE').count()
        half_day = attendance_records.filter(status='HALF_DAY').count()
        
        attendance_rate = (present / total_days * 100) if total_days > 0 else 0
        
        report_data.append({
            'employee_id': employee.id,
            'employee_name': employee.get_full_name(),
            'department': employee.employee_profile.department.name if hasattr(employee, 'employee_profile') and employee.employee_profile.department else 'N/A',
            'total_days': total_days,
            'present': present,
            'absent': absent,
            'late': late,
            'half_day': half_day,
            'attendance_rate': round(attendance_rate, 2)
        })
    
    return report_data


def generate_leave_report(company, start_date, end_date, tenant=None):
    """Generate detailed leave report"""
    from attendance.models import LeaveRequest
    
    leave_requests = LeaveRequest.objects.filter(
        employee__company=company,
        start_date__range=[start_date, end_date]
    )
    if tenant:
        leave_requests = leave_requests.filter(tenant=tenant)
    
    report_data = []
    
    for leave in leave_requests:
        report_data.append({
            'employee_name': leave.employee.get_full_name(),
            'leave_type': leave.leave_type,
            'start_date': leave.start_date,
            'end_date': leave.end_date,
            'total_days': leave.total_days if hasattr(leave, 'total_days') else 0,
            'status': leave.status,
            'reason': leave.reason
        })
    
    return report_data


def get_monthly_trends(company, months=6, tenant=None):
    """Get monthly trends for key metrics"""
    from django.contrib.auth import get_user_model
    from attendance.models import Attendance, LeaveRequest
    
    User = get_user_model()
    trends = []
    
    for i in range(months):
        month_start = timezone.now().date().replace(day=1) - timedelta(days=30 * i)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Employee count
        employee_count = User.objects.filter(
            company=company,
            role='EMPLOYEE',
            date_joined__lte=month_end
        ).count()
        
        # Attendance rate
        attendance = Attendance.objects.filter(
            employee__company=company,
            date__range=[month_start, month_end]
        )
        if tenant:
            attendance = attendance.filter(tenant=tenant)
        
        total_att = attendance.count()
        present_att = attendance.filter(status='PRESENT').count()
        att_rate = (present_att / total_att * 100) if total_att > 0 else 0
        
        # Leave requests
        leave_count = LeaveRequest.objects.filter(
            employee__company=company,
            start_date__range=[month_start, month_end]
        ).count()
        
        trends.append({
            'month': month_start.strftime('%B %Y'),
            'employee_count': employee_count,
            'attendance_rate': round(att_rate, 2),
            'leave_requests': leave_count
        })
    
    return list(reversed(trends))
