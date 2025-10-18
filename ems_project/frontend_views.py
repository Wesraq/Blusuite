from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Avg, Sum, Q, F, ExpressionWrapper, DurationField, Max
from django.db.models.functions import TruncDate, ExtractWeek, ExtractMonth, ExtractYear
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.conf import settings
from django.db import connection, IntegrityError
from decimal import Decimal
import calendar
import json
import os

# Local imports
from accounts.models import (
    Company,
    CompanyBiometricSettings,
    CompanyDepartment,
    CompanyEmailSettings,
    CompanyPayGrade,
    CompanyPosition,
    EmployeeIdConfiguration,
    EmployeeProfile,
    EmployerProfile,
    User,
)
from accounts.forms import (
    CompanyDepartmentForm,
    CompanyBiometricSettingsForm,
    CompanyEmailSettingsForm,
    CompanyPayGradeForm,
    CompanyPositionForm,
    EmployeeIdConfigurationForm,
)
from attendance.models import Attendance, LeaveRequest
from documents.models import EmployeeDocument, DocumentCategory, DocumentAccessLog
from django.urls import reverse
from performance.models import PerformanceReview


def _generate_employee_identifier(employee, company):
    """Generate a unique employee ID using configuration when available."""
    config = EmployeeIdConfiguration.objects.filter(company=company).first()
    base_identifier = None
    if config:
        base_identifier = config.generate_employee_id()

    if not base_identifier:
        company_part = company.pk if company and company.pk else 'EMP'
        base_identifier = f"{company_part}-{employee.pk}"

    unique_identifier = base_identifier
    counter = 1
    while EmployeeProfile.objects.filter(employee_id=unique_identifier).exists():
        unique_identifier = f"{base_identifier}-{counter}"
        counter += 1

    return unique_identifier, config


def ensure_employee_profile(employee, company):
    """Guarantee that every employee has an associated profile."""
    if hasattr(employee, 'employee_profile') and employee.employee_profile:
        return employee.employee_profile, False

    identifier, config = _generate_employee_identifier(employee, company)
    hire_date = None
    if getattr(employee, 'date_joined', None):
        hire_date = employee.date_joined.date()

    defaults = {
        'company': company,
        'employee_id': identifier,
        'job_title': 'Employee',
        'department': 'Unassigned',
        'date_hired': hire_date or timezone.now().date(),
        'salary': None,
        'pay_grade': '',
        'bank_name': '',
        'account_number': '',
        'bank_branch': '',
        'emergency_contact_name': '',
        'emergency_contact_phone': '',
        'emergency_contact_email': '',
        'emergency_contact_address': '',
        'employment_type': '',
        'employee_role': EmployeeProfile.EmployeeRole.EMPLOYEE,
    }

    profile, created = EmployeeProfile.objects.get_or_create(user=employee, defaults=defaults)

    if created and config:
        try:
            config.increment()
        except Exception:
            pass

    return profile, created

User = get_user_model()


def landing_page(request):
    """Main landing page for Eicomtech EMS"""
    return render(request, 'ems/landing.html')


def _get_user_company(user):
    company = getattr(user, 'company', None)
    if company:
        return company

    employer_profile = getattr(user, 'employer_profile', None)
    if employer_profile and getattr(employer_profile, 'company', None):
        company = employer_profile.company
        if company and getattr(user, 'company_id', None) is None:
            user.company = company
            user.save(update_fields=['company'])
        return company

    try:
        return Company.objects.filter(users=user).first()
    except Exception:
        return None


def _has_hr_access(user):
    """Check if user has HR or Admin access"""
    # Check if user has admin role
    if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or user.is_employer_admin:
        return True
    
    # Check if user is an employee with HR role
    if hasattr(user, 'employee_profile') and user.employee_profile:
        if user.employee_profile.employee_role == 'HR':
            return True
    
    return False


def _has_payroll_access(user):
    """
    Check if user has payroll/finance access
    Payroll is sensitive financial data - restrict to finance team only
    """
    # Check if user is an accountant (Finance team)
    if hasattr(user, 'employee_profile') and user.employee_profile:
        if user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS']:
            return True
    
    # Superadmin/System owner always has access
    if user.role == 'SUPERADMIN' or getattr(user, 'is_superadmin', False):
        return True
    
    # HR managers can view payroll for administrative purposes
    if hasattr(user, 'employee_profile') and user.employee_profile:
        if user.employee_profile.employee_role == 'HR':
            return True
    
    return False


from django.views.decorators.csrf import csrf_protect

@csrf_protect
def superadmin_login(request):
    """SuperAdmin login at eiscomtech URL - exclusive access"""
    if request.method == 'GET':
        if request.user.is_authenticated and hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
            return redirect('/dashboard/')
        return render(request, 'ems/superadmin_login.html')

    elif request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')

        if not email or not password:
            messages.error(request, 'Please enter both email and password')
            return render(request, 'ems/superadmin_login.html', {'error': 'Please enter both email and password'})

        # Check User model (unified model now handles both SuperAdmin and regular users)
        from accounts.models import User
        try:
            user = User.objects.get(email=email)
            if user.check_password(password) and user.is_active and user.role == 'SUPERADMIN':
                # Clear any existing session data before login
                request.session.flush()

                # Re-fetch user from database to ensure we have latest data
                user = User.objects.get(id=user.id)

                # Login with SuperAdmin user
                from django.contrib.auth import login as auth_login
                auth_login(request, user)

                # Create or get authentication token for API access
                from rest_framework.authtoken.models import Token
                token, created = Token.objects.get_or_create(user=user)
                # Store token in session for JavaScript access
                request.session['auth_token'] = token.key

                # Store user info in session for easy access
                request.session['user_role'] = user.role
                request.session['user_id'] = user.id
                request.session['user_email'] = user.email
                request.session['last_login'] = str(user.last_login)
                request.session['is_superadmin'] = user.is_superadmin

                # Set session to expire when browser closes for security
                request.session.set_expiry(0)

                return redirect('/dashboard/')
            else:
                return render(request, 'ems/superadmin_login.html', {'error': 'Invalid SuperAdmin credentials or account is disabled.'})
        except User.DoesNotExist:
            return render(request, 'ems/superadmin_login.html', {'error': 'SuperAdmin account not found.'})

@csrf_protect
def index(request):
    """Show SuperAdmin login at root URL"""
    if request.method == 'GET':
        # Check if user is SuperAdmin (from SuperAdmin model)
        if request.user.is_authenticated and hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
            return redirect('/dashboard/')
        # Check if user is regular User (from User model)
        if request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'ADMINISTRATOR']:
            return redirect('/dashboard/')
        return render(request, 'ems/login.html')

    elif request.method == 'POST':
        # Handle login form submission at root URL
        email = request.POST.get('username')

        if not email or not password:
            messages.error(request, 'Please enter both email and password')
            return render(request, 'ems/login.html', {'error': 'Please enter both email and password'})

        # Check User model (unified model now handles both SuperAdmin and regular users)
        from accounts.models import User
        try:
            user = User.objects.get(email__iexact=email)
            if user.check_password(password) and user.is_active:
                # Clear any existing session data before login
                request.session.flush()

                # Re-fetch user from database to ensure we have latest data
                user = User.objects.get(id=user.id)

                # Login with user
                from django.contrib.auth import login as auth_login
                auth_login(request, user)

                # Create or get authentication token for API access
                from rest_framework.authtoken.models import Token
                token, created = Token.objects.get_or_create(user=user)
                # Store token in session for JavaScript access
                request.session['auth_token'] = token.key

                # Store user info in session for easy access
                request.session['user_role'] = user.role
                request.session['user_id'] = user.id
                request.session['user_email'] = user.email
                request.session['last_login'] = str(user.last_login)
                request.session['is_superadmin'] = user.is_superadmin

                # Set session to expire when browser closes for security
                request.session.set_expiry(0)

                next_url = request.POST.get('next') or request.GET.get('next') or '/dashboard/'
                return redirect(next_url)
            else:
                return render(request, 'ems/login.html', {'error': 'Invalid login credentials or account is disabled.'})
        except User.DoesNotExist:
            return render(request, 'ems/login.html', {'error': 'Account not found.'})


@login_required
def dashboard_redirect(request):
    """Redirect users to appropriate dashboard based on their model type and role"""
    user = request.user

    # Check if user is SuperAdmin (from unified User model)
    if hasattr(user, 'is_superadmin') and user.is_superadmin:
        return redirect('superadmin_dashboard')

    # Check if user is regular User (from User model)
    if hasattr(user, 'role'):
        role = user.role.upper() if user.role else None

        role_redirects = {
            'SUPERADMIN': 'superadmin_dashboard',
            'ADMINISTRATOR': 'employer_dashboard',  # Main employer role
            'EMPLOYER_ADMIN': 'employer_dashboard',  # Alias for backward compatibility
            'EMPLOYEE': 'employee_dashboard'
        }

        redirect_view = role_redirects.get(role)
        if redirect_view:
            return redirect(redirect_view)

    # Default fallback
    messages.error(request, 'User role not defined. Please contact administrator.')
    return redirect('/')


@login_required
def employer_admin_dashboard(request):
    """Dashboard for Employer Admin (Branch/Company Admin)"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with appropriate role (from User model)
    if not (hasattr(request.user, 'role') and request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']):
        return render(request, 'ems/unauthorized.html')

    # Get the company this admin manages
    try:
        company = request.user.company
    except:
        messages.error(request, 'Company not assigned. Please contact your Employer Superuser.')
        return redirect('/')

    from attendance.models import Attendance
    from leave.models import LeaveRequest
    from datetime import date, datetime, timedelta

    today = date.today()
    # Parse selected date (default today)
    selected_date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date() if selected_date_str else today
    except (ValueError, TypeError):
        selected_date = today

    # Get employees in this company
    employees = User.objects.filter(company=company, role='EMPLOYEE')

    # Statistics
    total_employees = employees.count()

    # Today's attendance
    present_today = Attendance.objects.filter(
        date=today,
        user__company=company,
        status='PRESENT'
    ).count()

    late_today = Attendance.objects.filter(
        date=today,
        user__company=company,
        status='LATE'
    ).count()

    absent_today = total_employees - present_today - late_today

    # Pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        user__company=company,
        status='PENDING'
    ).count()

    # Today's attendance records (limit to 10 for display)
    today_attendance = Attendance.objects.filter(
        date=today,
        user__company=company
    ).select_related('user').order_by('-created_at')[:10]

    # Pending leave requests (limit to 5 for display)
    pending_leave_requests = LeaveRequest.objects.filter(
        user__company=company,
        status='PENDING'
    ).select_related('user').order_by('start_date')[:5]

    # Recent activities (placeholder)
    recent_activities = [
        {
            'title': 'Attendance marked',
            'description': f'{today_attendance.count()} employees marked attendance today',
            'timestamp': timezone.now() - timedelta(hours=1),
            'type': 'attendance'
        },
        {
            'title': 'Leave request submitted',
            'description': 'New leave request from Marketing department',
            'timestamp': timezone.now() - timedelta(hours=3),
            'type': 'leave'
        },
        {
            'title': 'Payroll processed',
            'description': f'Payroll processed for {total_employees} employees',
            'timestamp': timezone.now() - timedelta(days=1),
            'type': 'payroll'
        }
    ][:5]

    context = {
        'user': request.user,
        'company': company,
        'total_employees': total_employees,
        'present_today': present_today,
        'late_today': late_today,
        'absent_today': absent_today,
        'pending_leaves': pending_leaves,
        'today_attendance': today_attendance,
        'pending_leave_requests': pending_leave_requests,
        'recent_activities': recent_activities,
    }

    return render(request, 'ems/employer_admin_dashboard.html', context)


@login_required
def employee_dashboard(request):
    """Employee dashboard"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with EMPLOYEE role (from User model)
    if not (hasattr(request.user, 'role') and request.user.role == 'EMPLOYEE'):
        return render(request, 'ems/unauthorized.html')

    employee = request.user

    # Get employee's data
    profile = EmployeeProfile.objects.filter(user=employee).first()
    today = date.today()

    # Attendance this month
    month_start = today.replace(day=1)
    attendance_this_month = Attendance.objects.filter(
        employee=employee,
        date__gte=month_start
    ).count()

    # Today's attendance
    today_attendance = Attendance.objects.filter(
        employee=employee,
        date=today
    ).first()

    # Pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        employee=employee,
        status='PENDING'
    ).count()

    # Recent documents
    recent_docs = EmployeeDocument.objects.filter(
        employee=employee
    ).order_by('-created_at')[:5]

    # Upcoming reviews
    upcoming_reviews = PerformanceReview.objects.filter(
        employee=employee,
        review_date__gte=today
    ).order_by('review_date')[:3]

    context = {
        'employee': employee,
        'profile': profile,
        'attendance_this_month': attendance_this_month,
        'today_attendance': today_attendance,
        'pending_leaves': pending_leaves,
        'recent_docs': recent_docs,
        'upcoming_reviews': upcoming_reviews,
    }

    return render(request, 'ems/employee_dashboard.html', context)


@login_required
def employer_dashboard(request):
    """Employer dashboard with enhanced statistics and alerts"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with appropriate role (from User model)
    if not (hasattr(request.user, 'role') and request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']):
        return render(request, 'ems/unauthorized.html')

    employer = request.user
    company = EmployerProfile.objects.filter(user=employer).first()

    # Get company statistics - handle ADMINISTRATOR role
    if request.user.role == 'ADMINISTRATOR':
        # For ADMINISTRATOR users, get their company directly
        company = request.user.company
        employees = User.objects.filter(company=company, role='EMPLOYEE').select_related('employee_profile')
    else:
        # For EMPLOYER_SUPERUSER/EMPLOYER_ADMIN, use existing logic
        company = EmployerProfile.objects.filter(user=employer).first()
        employees = User.objects.filter(
            employee_profile__user__employer_profile__user=employer
        ).select_related('employee_profile')

    # If no company found, try to get from user.company for ADMINISTRATOR
    if not company and request.user.role == 'ADMINISTRATOR':
        company = request.user.company

    # If still no company, redirect to unauthorized
    if not company:
        return render(request, 'ems/unauthorized.html')

    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Basic Statistics
    total_employees = employees.count()
    active_employees = employees.filter(is_active=True).count()

    # Today's attendance
    today_attendance = Attendance.objects.filter(
        employee__in=employees,
        date=today
    )
    present_today = today_attendance.filter(status='PRESENT').count()
    late_today = today_attendance.filter(status='LATE').count()
    absent_today = total_employees - (present_today + late_today)
    
    attendance_rate = (present_today / total_employees * 100) if total_employees > 0 else 0

    # Attendance Trend (Last 7 days)
    attendance_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_attendance = Attendance.objects.filter(
            employee__in=employees,
            date=day,
            status='PRESENT'
        ).count()
        attendance_trend.append({
            'date': day.strftime('%a'),
            'count': day_attendance,
            'rate': round((day_attendance / total_employees * 100) if total_employees > 0 else 0, 1)
        })

    # Leave Statistics
    pending_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).count()
    
    approved_leaves_this_month = LeaveRequest.objects.filter(
        employee__in=employees,
        status='APPROVED',
        start_date__gte=month_ago
    ).count()

    # Upcoming Birthdays - Feature disabled (no date_of_birth field in model)
    upcoming_birthdays = []

    # Contract Expiry Alerts (Expiring in next 90 days)
    contract_expiry_alerts = []
    for employee in employees:
        if hasattr(employee, 'employee_profile') and employee.employee_profile:
            profile = employee.employee_profile
            expiry_date = None
            contract_type = None
            
            if profile.employment_type == 'CONTRACT' and profile.contract_end_date:
                expiry_date = profile.contract_end_date
                contract_type = 'Contract'
            elif profile.employment_type == 'PROBATION' and profile.probation_end_date:
                expiry_date = profile.probation_end_date
                contract_type = 'Probation'
            elif profile.employment_type == 'TEMPORARY' and profile.temporary_end_date:
                expiry_date = profile.temporary_end_date
                contract_type = 'Temporary'
            
            if expiry_date:
                days_until = (expiry_date - today).days
                if 0 <= days_until <= 90:
                    contract_expiry_alerts.append({
                        'employee': employee,
                        'type': contract_type,
                        'date': expiry_date,
                        'days_until': days_until,
                        'is_critical': days_until <= 30
                    })
    
    contract_expiry_alerts.sort(key=lambda x: x['days_until'])

    # Work Anniversaries (This month)
    work_anniversaries = []
    for employee in employees:
        if hasattr(employee, 'employee_profile') and employee.employee_profile and employee.employee_profile.date_hired:
            hire_date = employee.employee_profile.date_hired
            if hire_date.month == today.month:
                years_employed = today.year - hire_date.year
                if years_employed > 0:
                    work_anniversaries.append({
                        'employee': employee,
                        'date': date(today.year, hire_date.month, hire_date.day),
                        'years': years_employed
                    })
    
    work_anniversaries.sort(key=lambda x: x['date'])

    # Department-wise Statistics
    from django.db.models import Count
    from accounts.models import CompanyDepartment
    
    # Get departments with manual employee count
    departments_list = []
    all_departments = CompanyDepartment.objects.filter(company=company).order_by('name')
    
    for dept in all_departments:
        # Count employees by matching department CharField (not ideal but works with current model)
        emp_count = 0
        for emp in employees:
            if hasattr(emp, 'employee_profile') and emp.employee_profile:
                if emp.employee_profile.department == dept.name:
                    emp_count += 1
        
        if emp_count > 0:
            departments_list.append({
                'name': dept.name,
                'employee_count': emp_count
            })
    
    # Sort by employee count and get top 5
    departments_list.sort(key=lambda x: x['employee_count'], reverse=True)
    departments = departments_list[:5]

    # Recent Documents
    recent_docs = EmployeeDocument.objects.filter(
        employee__in=employees
    ).select_related('employee', 'category').order_by('-created_at')[:10]

    # Recent Performance Reviews
    recent_reviews = PerformanceReview.objects.filter(
        employee__in=employees
    ).select_related('employee', 'reviewer').order_by('-created_at')[:5]

    # Pending Approvals Count
    pending_documents = EmployeeDocument.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).count()

    context = {
        'employer': employer,
        'company': company,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'present_today': present_today,
        'late_today': late_today,
        'absent_today': absent_today,
        'attendance_rate': round(attendance_rate, 1),
        'attendance_trend': attendance_trend,
        'pending_leaves': pending_leaves,
        'approved_leaves_this_month': approved_leaves_this_month,
        'contract_expiry_alerts': contract_expiry_alerts[:5],  # Show top 5
        'work_anniversaries': work_anniversaries,
        'departments': departments,
        'recent_docs': recent_docs,
        'recent_reviews': recent_reviews,
        'pending_documents': pending_documents,
        'user_role': request.user.role,
        'today': today,
    }

    return render(request, 'ems/employer_dashboard.html', context)


@login_required
def leave_management(request):
    """Leave management dashboard for admins and employees"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with appropriate role (from User model)
    if not (hasattr(request.user, 'role') and request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'EMPLOYEE']):
        return render(request, 'ems/unauthorized.html')

    from attendance.models import LeaveRequest
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Count
    from datetime import date, timedelta
    import csv
    from django.http import HttpResponse

    User = get_user_model()

    # Employees see their own leave requests - redirect to employee leave page
    if request.user.role == 'EMPLOYEE':
        return redirect('employee_leave_request')

    # Employer/Admin see all employee leave requests
    company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)

    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    employees = User.objects.filter(company=company, role='EMPLOYEE')
    
    # Get all leave requests for statistics
    all_leave_requests = LeaveRequest.objects.filter(employee__in=employees)
    
    # Calculate statistics
    total_requests = all_leave_requests.count()
    pending_count = all_leave_requests.filter(status=LeaveRequest.Status.PENDING).count()
    approved_count = all_leave_requests.filter(status=LeaveRequest.Status.APPROVED).count()
    rejected_count = all_leave_requests.filter(status=LeaveRequest.Status.REJECTED).count()
    
    # Filter leave requests
    leave_requests = all_leave_requests
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        leave_requests = leave_requests.filter(status=status_filter)
    
    # Search filter
    search_query = request.GET.get('search', '').strip()
    if search_query:
        leave_requests = leave_requests.filter(
            Q(employee__first_name__icontains=search_query) |
            Q(employee__last_name__icontains=search_query) |
            Q(employee__email__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
    
    # Leave type filter
    leave_type_filter = request.GET.get('leave_type', '')
    if leave_type_filter:
        leave_requests = leave_requests.filter(leave_type=leave_type_filter)
    
    # Date range filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        leave_requests = leave_requests.filter(start_date__gte=date_from)
    if date_to:
        leave_requests = leave_requests.filter(end_date__lte=date_to)
    
    leave_requests = leave_requests.select_related('employee', 'employee__employee_profile', 'approved_by').order_by('-created_at')
    
    # CSV Export
    if request.GET.get('format') == 'csv':
        filename = f"leave_requests_{date.today().strftime('%Y%m%d')}.csv"
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')  # UTF-8 BOM
        writer = csv.writer(response)
        
        writer.writerow(['Employee', 'Position', 'Leave Type', 'Start Date', 'End Date', 'Days', 'Reason', 'Status', 'Applied Date', 'Approved By'])
        
        for req in leave_requests:
            writer.writerow([
                req.employee.get_full_name(),
                req.employee.employee_profile.job_title if hasattr(req.employee, 'employee_profile') and req.employee.employee_profile else 'N/A',
                req.get_leave_type_display(),
                req.start_date.strftime('%Y-%m-%d'),
                req.end_date.strftime('%Y-%m-%d'),
                req.duration,
                req.reason,
                req.get_status_display(),
                req.created_at.strftime('%Y-%m-%d'),
                req.approved_by.get_full_name() if req.approved_by else 'N/A'
            ])
        
        return response

    context = {
        'leave_requests': leave_requests,
        'status_filter': status_filter,
        'status_choices': LeaveRequest.Status.choices,
        'leave_type_choices': LeaveRequest.LeaveType.choices,
        'company': company,
        'search_query': search_query,
        'leave_type_filter': leave_type_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'employees': employees,
    }
    return render(request, 'ems/employer_leave_management.html', context)


# Request access page
def request_access(request):
    """Request access page"""
    return render(request, 'ems/request_access.html')
@login_required
def attendance_dashboard(request):
    """Attendance management dashboard for admins"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if hasattr(request.user, 'is_superadmin') and request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    # Check if user is regular User with appropriate role (from User model)
    if not (hasattr(request.user, 'role') and request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']):
        return render(request, 'ems/unauthorized.html')

    # Get basic attendance statistics
    from attendance.models import Attendance, LeaveRequest
    from django.contrib.auth import get_user_model
    from django.http import HttpResponse
    from datetime import date, datetime, timedelta
    import calendar
    from collections import defaultdict
    import csv

    User = get_user_model()
    today = date.today()

    # Get employees based on user role and determine company for template
    company = None
    # SUPERADMIN shouldn't access this (guarded above), but keep fallback
    if request.user.role == 'SUPERADMIN':
        employees = User.objects.filter(role='EMPLOYEE')
    elif request.user.role == 'ADMINISTRATOR':
        # For ADMINISTRATOR users, get employees from their company
        company = getattr(request.user, 'company', None)
        employees = User.objects.filter(company=company, role='EMPLOYEE') if company else User.objects.none()
    else:  # EMPLOYER_ADMIN
        # Try to resolve company for employer admin
        try:
            company = request.user.employer_profile.company
        except Exception:
            company = getattr(request.user, 'company', None)
        if company:
            employees = User.objects.filter(company=company, role='EMPLOYEE')
        else:
            employees = User.objects.filter(
                employee_profile__user__employer_profile__user=request.user
            )

    # Determine selected date from query (defaults to today)
    selected_date = today
    selected_date_param = request.GET.get('date')
    try:
        if selected_date_param:
            selected_date = datetime.strptime(selected_date_param, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        selected_date = today

    # Handle year and month filters
    year_param = request.GET.get('year')
    month_num_param = request.GET.get('month_num')
    
    if year_param and month_num_param:
        try:
            selected_year = int(year_param)
            selected_month_num = int(month_num_param)
            selected_month = date(selected_year, selected_month_num, 1)
        except (TypeError, ValueError):
            selected_month = selected_date.replace(day=1)
    else:
        selected_month = selected_date.replace(day=1)
    
    month_last_day = calendar.monthrange(selected_month.year, selected_month.month)[1]
    month_end = selected_month.replace(day=month_last_day)

    # Filter attendance records for selected date and optional filters
    attendance_qs = Attendance.objects.filter(employee__in=employees)
    attendance_qs = attendance_qs.filter(date=selected_date)

    status_filter = request.GET.get('status')
    if not status_filter:
        status_filter = 'PRESENT'
    if status_filter != 'ALL':
        attendance_qs = attendance_qs.filter(status=status_filter.upper())

    # Employee filter
    employee_filter = request.GET.get('employee')
    employee_filter_id = None
    if employee_filter:
        try:
            employee_filter_id = int(employee_filter)
        except (TypeError, ValueError):
            employee_filter_id = None
    if employee_filter_id:
        employees = employees.filter(id=employee_filter_id)
        attendance_qs = attendance_qs.filter(employee_id=employee_filter_id)
    
    # Search filter
    search_query = request.GET.get('search', '').strip()
    if search_query:
        from django.db.models import Q
        employees = employees.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(employee_profile__employee_id__icontains=search_query)
        )

    attendance_records = attendance_qs.select_related('employee').order_by(
        'employee__first_name', 'employee__last_name'
    )
    present_count = attendance_qs.filter(status=Attendance.Status.PRESENT).count()
    late_count = attendance_qs.filter(status=Attendance.Status.LATE).count()
    on_leave_count = attendance_qs.filter(status=Attendance.Status.ON_LEAVE).count()
    half_day_count = attendance_qs.filter(status=Attendance.Status.HALF_DAY).count()
    absent_status_count = attendance_qs.filter(status=Attendance.Status.ABSENT).count()

    # Employees without a record for selected date are counted absent
    employee_ids_with_records = attendance_qs.values_list('employee_id', flat=True)
    missing_record_count = employees.exclude(id__in=employee_ids_with_records).count()
    absent_count = absent_status_count + missing_record_count

    pending_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        status=LeaveRequest.Status.PENDING,
        start_date__lte=selected_date,
        end_date__gte=selected_date
    ).count()

    total_hours = sum(record.working_hours for record in attendance_records)

    matrix_employees_qs = employees
    if employee_filter_id:
        matrix_employees_qs = matrix_employees_qs.filter(id=employee_filter_id)
    matrix_employees = list(matrix_employees_qs.order_by('first_name', 'last_name'))

    month_attendance_qs = Attendance.objects.filter(
        employee__in=employees,
        date__range=[selected_month, month_end]
    ).select_related('employee')
    if employee_filter_id:
        month_attendance_qs = month_attendance_qs.filter(employee_id=employee_filter_id)

    attendance_lookup = defaultdict(dict)
    for record in month_attendance_qs:
        attendance_lookup[record.employee_id][record.date] = record

    month_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        status=LeaveRequest.Status.APPROVED,
        start_date__lte=month_end,
        end_date__gte=selected_month
    )
    if employee_filter_id:
        month_leaves = month_leaves.filter(employee_id=employee_filter_id)

    leave_dates_by_employee = defaultdict(set)
    for leave in month_leaves:
        leave_start = max(leave.start_date, selected_month)
        leave_end = min(leave.end_date, month_end)
        current_day = leave_start
        while current_day <= leave_end:
            leave_dates_by_employee[leave.employee_id].add(current_day)
            current_day += timedelta(days=1)

    # Get holidays for the month (before month_days loop)
    from accounts.models import CompanyHoliday
    holidays = CompanyHoliday.objects.filter(
        company=company,
        date__gte=selected_month,
        date__lte=month_end
    )
    holiday_dates = set(h.date for h in holidays)
    holiday_map = {h.date: h.name for h in holidays}

    month_days = []
    current_day = selected_month
    while current_day <= month_end:
        day_of_week = current_day.weekday()  # 0=Monday, 6=Sunday
        is_sunday = day_of_week == 6
        is_holiday = current_day in holiday_dates
        month_days.append({
            'date': current_day,
            'day_label': current_day.strftime('%a'),
            'day_number': current_day.day,
            'is_sunday': is_sunday,
            'is_holiday': is_holiday,
            'holiday_name': holiday_map.get(current_day, ''),
        })
        current_day += timedelta(days=1)

    status_code_map = {
        Attendance.Status.PRESENT: ('P', 'present'),
        Attendance.Status.LATE: ('Lt', 'late'),
        Attendance.Status.HALF_DAY: ('Hd', 'half_day'),
        Attendance.Status.ABSENT: ('Ab', 'absent'),
        Attendance.Status.ON_LEAVE: ('Lv', 'on_leave'),
    }

    status_legend = [
        {'code': 'P', 'label': 'Present', 'css_class': 'present'},
        {'code': 'Lt', 'label': 'Late', 'css_class': 'late'},
        {'code': 'Hd', 'label': 'Half Day', 'css_class': 'half_day'},
        {'code': 'Ab', 'label': 'Absent', 'css_class': 'absent'},
        {'code': 'Lv', 'label': 'On Leave', 'css_class': 'on_leave'},
        {'code': 'H', 'label': 'Holiday', 'css_class': 'holiday'},
    ]

    attendance_matrix = []
    for employee in matrix_employees:
        employee_records = attendance_lookup.get(employee.id, {})
        row_statuses = []
        leave_dates = leave_dates_by_employee.get(employee.id, set())
        
        # Calculate monthly stats for this employee
        emp_present = 0
        emp_late = 0
        emp_absent = 0
        emp_leave = 0
        emp_half_day = 0
        total_work_hours = 0.0
        
        for day_info in month_days:
            record = employee_records.get(day_info['date'])
            is_holiday = day_info.get('is_holiday', False)
            is_sunday = day_info.get('is_sunday', False)
            
            if record:
                # There's an actual attendance record
                code, css_class = status_code_map.get(record.status, ('', ''))
                if not code and record.status:
                    code = ''.join(part[0] for part in record.status.split('_'))
                    css_class = record.status.lower()
                
                # Count stats
                if record.status == Attendance.Status.PRESENT:
                    emp_present += 1
                elif record.status == Attendance.Status.LATE:
                    emp_late += 1
                elif record.status == Attendance.Status.ABSENT:
                    emp_absent += 1
                elif record.status == Attendance.Status.ON_LEAVE:
                    emp_leave += 1
                elif record.status == Attendance.Status.HALF_DAY:
                    emp_half_day += 1
                
                if record.working_hours:
                    total_work_hours += float(record.working_hours)
            else:
                # No attendance record exists
                if is_holiday:
                    # Holiday - mark as H
                    code, css_class = ('H', 'holiday')
                elif day_info['date'] in leave_dates:
                    # Has approved leave
                    code, css_class = ('Lv', 'on_leave')
                    if day_info['date'] <= today:
                        emp_leave += 1
                elif is_sunday:
                    # Sunday - default to blank
                    code, css_class = ('', '')
                elif day_info['date'] <= today:
                    # Past date with no record - default to Present
                    code, css_class = ('P', 'present')
                    emp_present += 1
                else:
                    # Future date - show blank
                    code, css_class = ('', '')
            
            row_statuses.append({
                'code': code, 
                'css_class': css_class,
                'date': day_info['date'],
                'is_sunday': is_sunday,
                'is_holiday': is_holiday,
                'holiday_name': day_info.get('holiday_name', ''),
            })
        
        # Calculate attendance percentage (excluding holidays, sundays, future dates)
        working_days = sum(1 for d in month_days if not d.get('is_holiday') and not d.get('is_sunday') and d['date'] <= today)
        attendance_percentage = round((emp_present / working_days * 100), 1) if working_days > 0 else 0
        
        attendance_matrix.append({
            'employee': employee,
            'statuses': row_statuses,
            'stats': {
                'present': emp_present,
                'late': emp_late,
                'absent': emp_absent,
                'leave': emp_leave,
                'half_day': emp_half_day,
                'total_hours': round(total_work_hours, 2),
                'percentage': attendance_percentage,
                'working_days': working_days,
            }
        })

    # CSV export
    if request.GET.get('format') == 'csv':
        view_type = request.GET.get('view', 'daily')
        
        if view_type == 'monthly':
            # Export monthly matrix
            filename = f"attendance_monthly_{selected_month.strftime('%Y%m')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            # Add UTF-8 BOM for Excel to properly recognize encoding
            response.write('\ufeff')
            writer = csv.writer(response)
            
            # Header row 1 - Day names
            header_days = ['Employee'] + [day['day_label'] for day in month_days]
            writer.writerow(header_days)
            
            # Header row 2 - Day numbers
            header_dates = [''] + [str(day['day_number']) for day in month_days]
            writer.writerow(header_dates)
            
            # Data rows
            for row in attendance_matrix:
                row_data = [row['employee'].get_full_name()]
                row_data.extend([cell['code'] if cell['code'] else '-' for cell in row['statuses']])
                writer.writerow(row_data)
        else:
            # Export daily records
            filename = f"attendance_daily_{selected_date.strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            # Add UTF-8 BOM for Excel to properly recognize encoding
            response.write('\ufeff')
            writer = csv.writer(response)
            writer.writerow(['Employee', 'Email', 'Date', 'Check In', 'Check Out', 'Status', 'Working Hours', 'Notes'])
            for record in attendance_records:
                writer.writerow([
                    record.employee.get_full_name(),
                    record.employee.email,
                    record.date.strftime('%Y-%m-%d') if record.date else '',
                    record.check_in.strftime('%H:%M:%S') if record.check_in else '',
                    record.check_out.strftime('%H:%M:%S') if record.check_out else '',
                    record.get_status_display(),
                    record.working_hours,
                    record.notes or '',
                ])
        return response

    # Get company settings and holidays
    current_year = today.year
    from accounts.models import CompanyAttendanceSettings, CompanyHoliday
    try:
        attendance_settings = CompanyAttendanceSettings.objects.get(company=company)
        year_range_past = attendance_settings.year_range_past
        year_range_future = attendance_settings.year_range_future
        expected_work_hours = float(attendance_settings.expected_work_hours)
        overtime_threshold = float(attendance_settings.overtime_threshold)
    except CompanyAttendanceSettings.DoesNotExist:
        year_range_past = 2
        year_range_future = 2
        expected_work_hours = 8.0
        overtime_threshold = 8.0
    year_range = range(current_year - year_range_past, current_year + year_range_future + 1)
    
    # Month names
    month_choices = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    
    # Generate trends data for chart (last 30 days)
    import json
    trends_labels = []
    trends_present = []
    trends_late = []
    trends_absent = []
    
    for i in range(29, -1, -1):
        trend_date = today - timedelta(days=i)
        trends_labels.append(trend_date.strftime('%b %d'))
        
        day_attendance = Attendance.objects.filter(
            employee__in=employees,
            date=trend_date
        )
        trends_present.append(day_attendance.filter(status=Attendance.Status.PRESENT).count())
        trends_late.append(day_attendance.filter(status=Attendance.Status.LATE).count())
        trends_absent.append(day_attendance.filter(status=Attendance.Status.ABSENT).count())
    
    trends_data = json.dumps({
        'labels': trends_labels,
        'present': trends_present,
        'late': trends_late,
        'absent': trends_absent,
    })
    
    context = {
        'total_employees': employees.count(),
        'present_count': present_count,
        'late_count': late_count,
        'on_leave_count': on_leave_count,
        'half_day_count': half_day_count,
        'absent_count': absent_count,
        'pending_leaves': pending_leaves,
        'selected_date': selected_date,
        'selected_status': status_filter or '',
        'selected_employee': employee_filter_id or '',
        'selected_month': selected_month,
        'selected_year': selected_month.year,
        'selected_month_num': selected_month.month,
        'year_range': year_range,
        'month_choices': month_choices,
        'attendance_records': attendance_records,
        'employee_options': employees.order_by('first_name', 'last_name'),
        'status_choices': Attendance.Status.choices,
        'total_hours': round(total_hours, 2),
        'company': company,
        'month_days': month_days,
        'attendance_matrix': attendance_matrix,
        'status_legend': status_legend,
        'search_query': search_query,
        'holidays': list(holidays),
        'expected_work_hours': expected_work_hours,
        'overtime_threshold': overtime_threshold,
        'trends_data': trends_data,
    }

    return render(request, 'ems/attendance_dashboard.html', context)

@login_required
def update_attendance_status(request):
    """AJAX endpoint to update attendance status from monthly matrix"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    from django.http import JsonResponse
    from datetime import datetime
    
    try:
        employee_id = request.POST.get('employee_id')
        date_str = request.POST.get('date')
        status = request.POST.get('status')
        
        if not all([employee_id, date_str]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        # Parse date
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get employee
        employee = User.objects.get(id=employee_id)
        
        # Check company access
        company = _get_user_company(request.user)
        if employee.company != company:
            return JsonResponse({'success': False, 'error': 'Access denied'})
        
        # Get or create attendance record
        attendance, created = Attendance.objects.get_or_create(
            employee=employee,
            date=attendance_date,
            defaults={'status': status if status else Attendance.Status.PRESENT}
        )
        
        if not created and status:
            attendance.status = status
            attendance.save()
        elif not created and not status:
            # Delete if setting to blank
            attendance.delete()
            return JsonResponse({'success': True, 'message': 'Attendance record removed'})
        
        return JsonResponse({'success': True, 'message': 'Attendance updated successfully'})
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def bulk_update_attendance(request):
    """AJAX endpoint to bulk update attendance status"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    import json
    from django.http import JsonResponse
    from datetime import datetime
    
    try:
        data = json.loads(request.body)
        employees_data = data.get('employees', [])
        status = data.get('status')
        
        if not employees_data or not status:
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        company = _get_user_company(request.user)
        updated_count = 0
        
        for emp_data in employees_data:
            employee_id = emp_data.get('employee_id')
            date_str = emp_data.get('date')
            
            if not employee_id or not date_str:
                continue
            
            try:
                attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                employee = User.objects.get(id=employee_id, company=company)
                
                attendance, created = Attendance.objects.get_or_create(
                    employee=employee,
                    date=attendance_date,
                    defaults={'status': status}
                )
                
                if not created:
                    attendance.status = status
                    attendance.save()
                
                updated_count += 1
                
            except (User.DoesNotExist, ValueError):
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully updated {updated_count} attendance record(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def employer_edit_attendance(request, attendance_id):
    """Edit attendance record for employers"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')

    from attendance.models import Attendance
    from django.contrib.auth import get_user_model
    from datetime import datetime

    User = get_user_model()
    company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)

    try:
        attendance = Attendance.objects.select_related('employee').get(id=attendance_id, employee__company=company)
    except Attendance.DoesNotExist:
        messages.error(request, 'Attendance record not found or access denied.')
        return redirect('attendance_dashboard')

    if request.method == 'POST':
        check_in_str = request.POST.get('check_in')
        check_out_str = request.POST.get('check_out')
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')

        try:
            if check_in_str:
                attendance.check_in = datetime.strptime(f"{attendance.date} {check_in_str}", '%Y-%m-%d %H:%M')
            if check_out_str:
                attendance.check_out = datetime.strptime(f"{attendance.date} {check_out_str}", '%Y-%m-%d %H:%M')
            if status:
                attendance.status = status
            attendance.notes = notes
            attendance.save()
            messages.success(request, 'Attendance record updated successfully.')
            return redirect('attendance_dashboard')
        except Exception as e:
            messages.error(request, f'Error updating attendance: {str(e)}')

    context = {
        'attendance': attendance,
        'status_choices': Attendance.Status.choices,
        'company': company,
    }
    return render(request, 'ems/employer_edit_attendance.html', context)

@login_required
def employer_leave_action(request, leave_id):
    """Approve or reject leave request"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')

    from attendance.models import LeaveRequest
    from django.utils import timezone

    company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)

    try:
        leave_request = LeaveRequest.objects.select_related('employee').get(id=leave_id, employee__company=company)
    except LeaveRequest.DoesNotExist:
        messages.error(request, 'Leave request not found or access denied.')
        return redirect('leave_management')

    # Handle both GET and POST requests
    action = request.POST.get('action') or request.GET.get('action')
    rejection_reason = request.POST.get('reason') or request.GET.get('reason', '')

    if action == 'approve':
        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.approved_by = request.user
        leave_request.approved_at = timezone.now()
        leave_request.save()
        messages.success(request, f'Leave request approved for {leave_request.employee.get_full_name()}.')
    elif action == 'reject':
        if rejection_reason:
            leave_request.status = LeaveRequest.Status.REJECTED
            leave_request.approved_by = request.user
            leave_request.rejection_reason = rejection_reason
            leave_request.save()
            messages.success(request, f'Leave request rejected for {leave_request.employee.get_full_name()}.')
        else:
            messages.error(request, 'Rejection reason is required.')
    elif action == 'APPROVED':
        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.approved_by = request.user
        leave_request.approved_at = timezone.now()
        leave_request.save()
        messages.success(request, f'Leave request approved for {leave_request.employee.get_full_name()}.')
    elif action == 'REJECTED':
        leave_request.status = LeaveRequest.Status.REJECTED
        leave_request.approved_by = request.user
        leave_request.rejection_reason = rejection_reason
        leave_request.save()
        messages.success(request, f'Leave request rejected for {leave_request.employee.get_full_name()}.')

    return redirect('leave_management')

@login_required
def bulk_approve_leave(request):
    """Bulk approve leave requests"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    import json
    from attendance.models import LeaveRequest
    from django.utils import timezone
    
    try:
        data = json.loads(request.body)
        leave_ids = data.get('leave_ids', [])
        
        if not leave_ids:
            return JsonResponse({'success': False, 'error': 'No leave requests selected'})
        
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        approved_count = 0
        
        for leave_id in leave_ids:
            try:
                leave_req = LeaveRequest.objects.get(id=leave_id, employee__company=company)
                leave_req.status = LeaveRequest.Status.APPROVED
                leave_req.approved_by = request.user
                leave_req.approved_at = timezone.now()
                leave_req.save()
                approved_count += 1
            except LeaveRequest.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully approved {approved_count} leave request(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def bulk_reject_leave(request):
    """Bulk reject leave requests"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    import json
    from attendance.models import LeaveRequest
    
    try:
        data = json.loads(request.body)
        leave_ids = data.get('leave_ids', [])
        reason = data.get('reason', '')
        
        if not leave_ids:
            return JsonResponse({'success': False, 'error': 'No leave requests selected'})
        
        if not reason:
            return JsonResponse({'success': False, 'error': 'Rejection reason is required'})
        
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        rejected_count = 0
        
        for leave_id in leave_ids:
            try:
                leave_req = LeaveRequest.objects.get(id=leave_id, employee__company=company)
                leave_req.status = LeaveRequest.Status.REJECTED
                leave_req.approved_by = request.user
                leave_req.rejection_reason = reason
                leave_req.save()
                rejected_count += 1
            except LeaveRequest.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully rejected {rejected_count} leave request(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def employee_attendance_view(request):
    """Employee's personal attendance history"""
    if request.user.role != 'EMPLOYEE':
        return render(request, 'ems/unauthorized.html')

    from attendance.models import Attendance
    from datetime import date, timedelta

    today = date.today()
    
    # Default to current month
    month_filter = request.GET.get('month')
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
        except:
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    else:
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

    attendance_records = Attendance.objects.filter(
        employee=request.user,
        date__range=[start_date, end_date]
    ).order_by('-date')

    # Summary stats
    total_days = attendance_records.count()
    present_count = attendance_records.filter(status=Attendance.Status.PRESENT).count()
    late_count = attendance_records.filter(status=Attendance.Status.LATE).count()
    absent_count = attendance_records.filter(status=Attendance.Status.ABSENT).count()
    on_leave_count = attendance_records.filter(status=Attendance.Status.ON_LEAVE).count()
    total_hours = sum(record.working_hours for record in attendance_records)

    context = {
        'attendance_records': attendance_records,
        'start_date': start_date,
        'end_date': end_date,
        'total_days': total_days,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'on_leave_count': on_leave_count,
        'total_hours': round(total_hours, 2),
    }
    return render(request, 'ems/employee_attendance.html', context)

@login_required
def employee_leave_request(request):
    """Employee leave request submission"""
    if request.user.role != 'EMPLOYEE':
        return render(request, 'ems/unauthorized.html')

    from attendance.models import LeaveRequest
    from datetime import datetime

    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            if end_date < start_date:
                messages.error(request, 'End date must be after start date.')
            else:
                LeaveRequest.objects.create(
                    employee=request.user,
                    leave_type=leave_type,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                    status=LeaveRequest.Status.PENDING
                )
                messages.success(request, 'Leave request submitted successfully!')
                return redirect('employee_leave_request')
        except Exception as e:
            messages.error(request, f'Error submitting leave request: {str(e)}')

    # Get employee's leave requests
    leave_requests = LeaveRequest.objects.filter(
        employee=request.user
    ).order_by('-created_at')
    
    # Calculate leave statistics
    from datetime import date
    from django.db.models import Sum, Q
    
    current_year = date.today().year
    
    # Leave statistics for current year
    year_leave_requests = leave_requests.filter(start_date__year=current_year)
    
    total_requests = leave_requests.count()
    pending_count = leave_requests.filter(status=LeaveRequest.Status.PENDING).count()
    approved_count = leave_requests.filter(status=LeaveRequest.Status.APPROVED).count()
    rejected_count = leave_requests.filter(status=LeaveRequest.Status.REJECTED).count()
    
    # Calculate total days used (approved leaves only)
    approved_leaves = year_leave_requests.filter(status=LeaveRequest.Status.APPROVED)
    total_days_used = sum([leave.duration for leave in approved_leaves])
    
    # Get employee profile for leave balance
    try:
        annual_leave_balance = 21  # Default annual leave days
        sick_leave_balance = 14   # Default sick leave days
        
        if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
            profile = request.user.employee_profile
            # If you have leave balance fields in profile, use them
            if hasattr(profile, 'annual_leave_balance'):
                annual_leave_balance = profile.annual_leave_balance
            if hasattr(profile, 'sick_leave_balance'):
                sick_leave_balance = profile.sick_leave_balance
        
        # Calculate remaining balance
        annual_days_used = sum([leave.duration for leave in approved_leaves.filter(leave_type='ANNUAL')])
        sick_days_used = sum([leave.duration for leave in approved_leaves.filter(leave_type='SICK')])
        
        annual_remaining = annual_leave_balance - annual_days_used
        sick_remaining = sick_leave_balance - sick_days_used
        
    except:
        annual_remaining = 21
        sick_remaining = 14
        total_days_used = 0

    context = {
        'leave_requests': leave_requests,
        'leave_type_choices': LeaveRequest.LeaveType.choices,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'total_days_used': total_days_used,
        'annual_remaining': annual_remaining,
        'sick_remaining': sick_remaining,
        'current_year': current_year,
    }
    return render(request, 'ems/employee_leave_request.html', context)

@login_required
def superadmin_dashboard(request):
    """SuperAdmin dashboard with system overview"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    from accounts.models import Company, User
    from attendance.models import Attendance, LeaveRequest
    from documents.models import EmployeeDocument
    from performance.models import PerformanceReview
    from datetime import date, timedelta

    today = date.today()

    # System-wide statistics
    total_companies = Company.objects.count()
    total_users = User.objects.count()
    total_employees = User.objects.filter(role='EMPLOYEE').count()

    # Today's attendance summary
    today_attendance = Attendance.objects.filter(date=today)
    present_today = today_attendance.filter(status='PRESENT').count()
    late_today = today_attendance.filter(status='LATE').count()
    absent_today = total_employees - today_attendance.count()

    # Pending leave requests
    pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()

    # Recent documents
    recent_docs = EmployeeDocument.objects.all().order_by('-created_at')[:10]

    # Upcoming performance reviews
    upcoming_reviews = PerformanceReview.objects.filter(
        review_date__gte=today
    ).order_by('review_date')[:5]

    # Monthly statistics
    month_start = today.replace(day=1)
    attendance_this_month = Attendance.objects.filter(date__gte=month_start).count()
    leave_requests_this_month = LeaveRequest.objects.filter(
        start_date__gte=month_start
    ).count()

    context = {
        'user': request.user,
        'total_companies': total_companies,
        'total_users': total_users,
        'total_employees': total_employees,
        'present_today': present_today,
        'late_today': late_today,
        'absent_today': absent_today,
        'pending_leaves': pending_leaves,
        'recent_docs': recent_docs,
        'upcoming_reviews': upcoming_reviews,
        'attendance_this_month': attendance_this_month,
        'leave_requests_this_month': leave_requests_this_month,
        'today_date': today.strftime('%Y-%m-%d'),
    }

    return render(request, 'ems/superadmin_dashboard.html', context)

@login_required
def employee_management(request):
    """Employee management dashboard for SuperAdmin"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    from accounts.models import Company, User
    from performance.models import PerformanceReview
    from datetime import date

    today = date.today()

    # Get all employees and companies
    employees = User.objects.filter(role='EMPLOYEE').select_related()
    companies = Company.objects.all()

    # Statistics
    total_employees = employees.count()
    active_employees = employees.filter(is_active=True).count()
    total_companies = companies.count()

    # Pending performance reviews
    pending_reviews = PerformanceReview.objects.filter(
        review_date__gte=today
    ).count()

    # Prepare employee data for template
    employee_data = []
    for employee in employees:
        employee_info = {
            'id': employee.id,
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'email': employee.email,
            'phone': employee.phone,
            'role': employee.role,
            'is_active': employee.is_active,
            'date_joined': employee.date_joined,
            'company_name': None
        }

        # Try to get company name if employee belongs to a company
        try:
            if hasattr(employee, 'employee_profile') and employee.employee_profile:
                employee_info['company_name'] = employee.employee_profile.company.name if employee.employee_profile.company else None
        except:
            pass

        employee_data.append(employee_info)

    context = {
        'employees': employee_data,
        'companies': companies,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'total_companies': total_companies,
        'pending_reviews': pending_reviews,
        'today_date': today.strftime('%Y-%m-%d'),
    }

    return render(request, 'ems/employee_management.html', context)

@login_required
def analytics_dashboard(request):
    """Analytics and reporting dashboard for SuperAdmin"""
    # Check if user is SuperAdmin (from SuperAdmin model)
    if not (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return render(request, 'ems/unauthorized.html')

    # Date range filter with validation
    today = date.today()
    start_date = request.GET.get('start_date', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', today.strftime('%Y-%m-%d'))
    
    try:
        start_date_obj = date.fromisoformat(start_date)
        end_date_obj = date.fromisoformat(end_date)
        # Ensure end date is not in the future
        end_date_obj = min(end_date_obj, today)
        # Ensure date range is not too large (max 1 year)
        if (end_date_obj - start_date_obj).days > 365:
            start_date_obj = end_date_obj - timedelta(days=365)
    except (ValueError, TypeError):
        start_date_obj = today - timedelta(days=30)
        end_date_obj = today

    # Filter by company if specified
    company_filter = request.GET.get('company')
    company = None
    if company_filter:
        try:
            company = Company.objects.get(id=company_filter)
        except (Company.DoesNotExist, ValueError):
            pass

    # Base querysets with date range
    attendance_qs = Attendance.objects.filter(date__range=[start_date_obj, end_date_obj])
    leave_qs = LeaveRequest.objects.filter(
        Q(start_date__lte=end_date_obj, end_date__gte=start_date_obj) |
        Q(start_date__range=[start_date_obj, end_date_obj]) |
        Q(end_date__range=[start_date_obj, end_date_obj])
    )
    
    # Apply company filter if selected
    if company:
        attendance_qs = attendance_qs.filter(employee__company=company)
        leave_qs = leave_qs.filter(employee__company=company)
        total_employees = User.objects.filter(role='EMPLOYEE', company=company).count()
    else:
        total_employees = User.objects.filter(role='EMPLOYEE').count()

    # ===== ATTENDANCE ANALYTICS =====
    # Daily attendance summary
    attendance_daily = attendance_qs.values('date').annotate(
        present=Count('id', filter=Q(status='PRESENT')),
        late=Count('id', filter=Q(status='LATE')),
        absent=Count('id', filter=Q(status='ABSENT')),
        on_leave=Count('id', filter=Q(status='ON_LEAVE')),
        total=Count('id')
    ).order_by('date')

    # Monthly attendance trend
    attendance_monthly = attendance_qs.annotate(
        month=ExtractMonth('date'),
        year=ExtractYear('date')
    ).values('year', 'month').annotate(
        present=Count('id', filter=Q(status='PRESENT')),
        late=Count('id', filter=Q(status='LATE')),
        absent=Count('id', filter=Q(status='ABSENT')),
        on_leave=Count('id', filter=Q(status='ON_LEAVE')),
        total=Count('id')
    ).order_by('year', 'month')

    # Calculate attendance rate over time
    attendance_rate = 0
    working_days = 0
    present_days = 0
    
    # Calculate working days in the period (excluding weekends)
    current_date = start_date_obj
    while current_date <= end_date_obj:
        if current_date.weekday() < 5:  # Monday=0, Sunday=6
            working_days += 1
        current_date += timedelta(days=1)
    
    if attendance_qs.exists() and total_employees > 0 and working_days > 0:
        present_days = attendance_qs.filter(
            Q(status='PRESENT') | Q(status='LATE')
        ).count()
        attendance_rate = round((present_days / (total_employees * working_days)) * 100, 1)

    # ===== LEAVE ANALYTICS =====
    # Leave status summary - we'll calculate this in Python since we can't use the duration method in the database query
    leave_stats = []
    status_counts = leave_qs.values('status').annotate(count=Count('id'))
    
    # Calculate total days for each status
    for status in status_counts:
        status_name = status['status']
        leave_days = sum(
            (leave.end_date - leave.start_date).days + 1  # +1 to include both start and end dates
            for leave in leave_qs.filter(status=status_name)
        )
        leave_stats.append({
            'status': status_name,
            'count': status['count'],
            'total_days': leave_days
        })
    
    # Leave by type - also calculated in Python
    leave_by_type = []
    type_counts = leave_qs.values('leave_type').annotate(count=Count('id'))
    
    for leave_type in type_counts:
        type_name = leave_type['leave_type']
        type_leaves = leave_qs.filter(leave_type=type_name)
        total_days = sum(
            (leave.end_date - leave.start_date).days + 1
            for leave in type_leaves
        )
        avg_days = total_days / len(type_leaves) if type_leaves else 0
        
        leave_by_type.append({
            'leave_type': type_name,
            'count': leave_type['count'],
            'total_days': total_days,
            'avg_duration': round(avg_days, 1)
        })
    
    # Sort leave by type by count in descending order
    leave_by_type = sorted(leave_by_type, key=lambda x: x['count'], reverse=True)
    
    # Monthly leave trend - calculated in Python
    monthly_data = {}
    for leave in leave_qs:
        year = leave.start_date.year
        month = leave.start_date.month
        days = (leave.end_date - leave.start_date).days + 1
        
        key = f"{year}-{month:02d}"
        if key not in monthly_data:
            monthly_data[key] = {'year': year, 'month': month, 'count': 0, 'total_days': 0}
            
        monthly_data[key]['count'] += 1
        monthly_data[key]['total_days'] += days
    
    # Convert to list and sort by year and month
    leave_monthly = sorted(monthly_data.values(), key=lambda x: (x['year'], x['month']))

    # ===== PERFORMANCE ANALYTICS =====
    performance_reviews = PerformanceReview.objects.filter(
        review_date__range=[start_date_obj, end_date_obj]
    )
    
    if company:
        performance_reviews = performance_reviews.filter(employee__company=company)
    
    # Performance metrics
    # Calculate average rating by converting the text ratings to numeric scores
    rating_scores = {
        'OUTSTANDING': 5,
        'EXCEEDS_EXPECTATIONS': 4,
        'MEETS_EXPECTATIONS': 3,
        'BELOW_EXPECTATIONS': 2,
        'UNSATISFACTORY': 1
    }
    
    # Calculate average rating
    total_rating = 0
    rating_count = 0
    rating_distribution = {rating: 0 for rating in rating_scores}
    
    for review in performance_reviews:
        if review.overall_rating in rating_scores:
            total_rating += rating_scores[review.overall_rating]
            rating_count += 1
            rating_distribution[review.overall_rating] += 1
    
    avg_rating = round(total_rating / rating_count, 1) if rating_count > 0 else 0.0
    
    # Prepare performance distribution data for the chart
    performance_distribution = [
        {'overall_rating': rating, 'count': count}
        for rating, count in rating_distribution.items()
    ]
    
    # Initialize metrics data with default values
    metrics_data = {
        'productivity': {'average': 0, 'target': 0, 'count': 0},
        'quality': {'average': 0, 'target': 0, 'count': 0},
        'attendance': {'average': 0, 'target': 0, 'count': 0}
    }
    
    # Try to get metrics from PerformanceMetric model if available
    try:
        from performance.models import PerformanceMetric
        if hasattr(PerformanceReview, 'metrics'):
            metrics = PerformanceMetric.objects.filter(
                review__in=performance_reviews,
                name__in=['Productivity', 'Quality', 'Attendance']
            ).values('name').annotate(
                avg_value=Avg('actual_value'),
                target_value=Avg('target_value'),
                count=Count('id')
            )
            
            for metric in metrics:
                metric_name = metric['name'].lower()
                if metric_name in metrics_data:
                    metrics_data[metric_name] = {
                        'average': float(round(metric['avg_value'], 1)) if metric['avg_value'] is not None else 0,
                        'target': float(round(metric['target_value'], 1)) if metric['target_value'] is not None else 0,
                        'count': metric['count']
                    }
    except Exception as e:
        # If there's any error, use default values
        pass

    # ===== DEPARTMENT ANALYTICS =====
    # Get all employees with their departments and ratings
    employees = User.objects.filter(role='EMPLOYEE')
    if company:
        employees = employees.filter(company=company)
    
    # Group employees by department and calculate statistics
    departments = {}
    for emp in employees:
        dept_name = getattr(emp, 'department', 'Unassigned')
        if dept_name not in departments:
            departments[dept_name] = {
                'employee_count': 0,
                'ratings': [],
                'attendance_count': 0,
                'total_days': 0
            }
        
        departments[dept_name]['employee_count'] += 1
        
        # Get performance ratings
        reviews = emp.performance_reviews.all()
        for review in reviews:
            if review.overall_rating in rating_scores:
                departments[dept_name]['ratings'].append(rating_scores[review.overall_rating])
        
        # Get attendance data if available
        if hasattr(emp, 'attendances'):
            attendances = emp.attendances.filter(
                date__range=[start_date_obj, end_date_obj]
            )
            present_days = attendances.filter(
                status__in=['PRESENT', 'LATE']
            ).count()
            total_days = attendances.exclude(status='ON_LEAVE').count()
            
            departments[dept_name]['attendance_count'] += present_days
            departments[dept_name]['total_days'] += total_days
    
    # Prepare department stats
    department_stats = []
    for dept_name, data in departments.items():
        avg_rating = sum(data['ratings']) / len(data['ratings']) if data['ratings'] else 0
        attendance_rate = (data['attendance_count'] / data['total_days'] * 100) if data['total_days'] > 0 else 0
        
        department_stats.append({
            'department__name': dept_name,
            'employee_count': data['employee_count'],
            'avg_rating': round(avg_rating, 1),
            'attendance_rate': round(attendance_rate, 1)
        })
    
    # Sort by employee count
    department_stats = sorted(department_stats, key=lambda x: x['employee_count'], reverse=True)

    # ===== RECENT ACTIVITIES =====
    recent_activities = []
    
    # Recent leaves
    recent_leaves = leave_qs.select_related('employee').order_by('-created_at')[:5]
    for leave in recent_leaves:
        recent_activities.append({
            'type': 'leave',
            'date': leave.created_at,
            'title': f"{leave.employee.get_full_name()} requested {leave.leave_type}",
            'status': leave.status,
            'icon': 'calendar_today',
            'color': 'primary' if leave.status == 'PENDING' else 'success' if leave.status == 'APPROVED' else 'error'
        })
    
    # Recent reviews
    recent_reviews = performance_reviews.select_related('employee', 'reviewer').order_by('-review_date')[:5]
    for review in recent_reviews:
        recent_activities.append({
            'type': 'review',
            'date': review.review_date,
            'title': f"Performance review for {review.employee.get_full_name()}",
            'rating': review.overall_rating,
            'icon': 'star',
            'color': 'warning'
        })
    
    # Sort all activities by date
    recent_activities = sorted(recent_activities, key=lambda x: x['date'], reverse=True)[:10]

    # ===== PREPARE CONTEXT =====
    context = {
        'user': request.user,
        # Summary stats
        'total_users': User.objects.count(),
        'total_companies': Company.objects.count(),
        'total_employees': total_employees,
        'total_employers': User.objects.filter(role='EMPLOYER').count(),
        'present_days': present_days,
        'working_days': working_days,
        'attendance_rate': attendance_rate,
        'avg_rating': avg_rating,
        'start_date': start_date_obj.strftime('%Y-%m-%d'),
        'end_date': end_date_obj.strftime('%Y-%m-%d'),
        'today': today.strftime('%Y-%m-%d'),
        'company_filter': company_filter,
        'companies': Company.objects.all(),
        'selected_company': company,
        'recent_activities': recent_activities,
        'attendance_daily': list(attendance_daily),
        'attendance_monthly': list(attendance_monthly),
        'leave_stats': list(leave_stats),
        'leave_by_type': list(leave_by_type),
        'leave_monthly': list(leave_monthly),
        'performance_distribution': performance_distribution,
        'department_stats': department_stats,
        'metrics_data': metrics_data,
        
        # Summary metrics
        'total_reviews': performance_reviews.count(),
        'pending_leaves': leave_qs.filter(status='PENDING').count(),
        'approved_leaves': leave_qs.filter(status='APPROVED').count(),
        'rejected_leaves': leave_qs.filter(status='REJECTED').count(),
        'total_leave_days': sum(
            (leave.end_date - leave.start_date).days + 1
            for leave in leave_qs.filter(status='APPROVED')
        ),
        
        # Chart data as JSON for JavaScript
        'attendance_daily_json': json.dumps([{
            'date': str(item['date']),
            'present': item['present'],
            'late': item['late'],
            'absent': item['absent'],
            'on_leave': item['on_leave'],
            'total': item['total']
        } for item in attendance_daily]),
        
        'attendance_monthly_json': json.dumps([{
            'month': f"{calendar.month_abbr[item['month']]} {item['year']}",
            'present': item['present'],
            'late': item['late'],
            'absent': item['absent'],
            'on_leave': item['on_leave'],
            'total': item['total']
        } for item in attendance_monthly]),
        
        'leave_by_type_json': json.dumps([{
            'type': item['leave_type'],
            'count': item['count'],
            'total_days': item['total_days'] or 0,
            'avg_duration': float(item['avg_duration']) if item['avg_duration'] else 0
        } for item in leave_by_type]),
        
        'performance_distribution_json': json.dumps([{
            'rating': item['overall_rating'],
            'count': item['count']
        } for item in performance_distribution])
    }

    # Add debug info in development
    if settings.DEBUG:
        context['debug'] = {
            'query_count': len(connection.queries),
            'queries': connection.queries,
        }

    return render(request, 'ems/analytics_dashboard.html', context)

@login_required
def settings_hub(request):
    """Settings hub with quick access to all administrative functions"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = request.user.company
    except:
        company = None
    
    context = {
        'company': company,
    }
    
    return render(request, 'ems/settings_hub.html', context)


@login_required
def settings_dashboard(request):
    """Enhanced company settings dashboard with statistics, audit logs, and filters"""
    allowed_roles = {'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'ADMIN'}
    if not (
        getattr(request.user, 'role', '') in allowed_roles
        or getattr(request.user, 'is_employer_admin', False)
        or getattr(request.user, 'is_superuser', False)
        or getattr(request.user, 'is_superadmin', False)
    ):
        return render(request, 'ems/unauthorized.html', status=403)

    company = _get_user_company(request.user)
    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    from django.db.models import Q, Count
    from datetime import datetime, timedelta
    import csv
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    dept_filter = request.GET.get('department', '')
    export_type = request.GET.get('export', '')  # departments, positions, pay_grades
    
    config, _ = EmployeeIdConfiguration.objects.get_or_create(company=company)
    email_settings, _ = CompanyEmailSettings.objects.get_or_create(company=company)
    biometric_settings, _ = CompanyBiometricSettings.objects.get_or_create(company=company)

    email_form = CompanyEmailSettingsForm(instance=email_settings)
    biometric_form = CompanyBiometricSettingsForm(instance=biometric_settings)
    
    # Get all configuration items with filtering
    departments = CompanyDepartment.objects.filter(company=company)
    positions = CompanyPosition.objects.filter(company=company).select_related('department')
    pay_grades = CompanyPayGrade.objects.filter(company=company)
    
    # Apply search filter
    if search_query:
        departments = departments.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
        positions = positions.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
        pay_grades = pay_grades.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
    
    # Apply department filter for positions
    if dept_filter:
        positions = positions.filter(department_id=dept_filter)
    
    # Order results
    departments = departments.order_by('name')
    positions = positions.order_by('name')
    pay_grades = pay_grades.order_by('name')
    
    # Statistics
    total_departments = CompanyDepartment.objects.filter(company=company).count()
    total_positions = CompanyPosition.objects.filter(company=company).count()
    total_pay_grades = CompanyPayGrade.objects.filter(company=company).count()
    
    # Configuration totals (models don't have created_at field)
    # Show total configurations instead of recent changes
    total_configurations = total_departments + total_positions + total_pay_grades
    
    # Position distribution by department
    position_by_dept = CompanyPosition.objects.filter(company=company).values(
        'department__name'
    ).annotate(count=Count('id')).order_by('-count')[:5]
    
    # CSV Export
    if export_type == 'departments':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="departments.csv"'
        writer = csv.writer(response)
        writer.writerow(['Department Name', 'Description', 'Created Date', 'Active'])
        for dept in departments:
            writer.writerow([
                dept.name,
                dept.description or '',
                dept.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(dept, 'created_at') else '',
                'Yes' if dept.is_active else 'No'
            ])
        return response
    
    elif export_type == 'positions':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="positions.csv"'
        writer = csv.writer(response)
        writer.writerow(['Position Name', 'Department', 'Description', 'Created Date'])
        for pos in positions:
            writer.writerow([
                pos.name,
                pos.department.name if pos.department else 'N/A',
                pos.description or '',
                pos.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(pos, 'created_at') else ''
            ])
        return response
    
    elif export_type == 'pay_grades':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="pay_grades.csv"'
        writer = csv.writer(response)
        writer.writerow(['Pay Grade Name', 'Description', 'Min Salary', 'Max Salary', 'Created Date'])
        for grade in pay_grades:
            writer.writerow([
                grade.name,
                grade.description or '',
                grade.min_salary if hasattr(grade, 'min_salary') else '',
                grade.max_salary if hasattr(grade, 'max_salary') else '',
                grade.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(grade, 'created_at') else ''
            ])
        return response

    # Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'employee_id':
            form = EmployeeIdConfigurationForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
                messages.success(request, 'Employee ID settings updated.')
            else:
                messages.error(request, 'Please correct the errors in Employee ID settings.')

        elif action == 'department':
            dept_form = CompanyDepartmentForm(request.POST, company=company)
            if dept_form.is_valid():
                try:
                    dept_form.save()
                    messages.success(request, 'Department added successfully.')
                except IntegrityError:
                    messages.error(request, 'Department with this name already exists.')
            else:
                messages.error(request, 'Please correct the errors in the Department form.')

        elif action == 'position':
            position_form = CompanyPositionForm(request.POST, company=company)
            if position_form.is_valid():
                try:
                    position_form.save()
                    messages.success(request, 'Position added successfully.')
                except IntegrityError:
                    messages.error(request, 'Position with this name already exists.')
            else:
                messages.error(request, 'Please correct the errors in the Position form.')

        elif action == 'pay_grade':
            pay_grade_form = CompanyPayGradeForm(request.POST, company=company)
            if pay_grade_form.is_valid():
                try:
                    pay_grade_form.save()
                    messages.success(request, 'Pay grade added successfully.')
                except IntegrityError:
                    messages.error(request, 'Pay grade with this name already exists.')
            else:
                messages.error(request, 'Please correct the errors in the Pay grade form.')
        
        elif action == 'edit_department':
            dept_id = request.POST.get('dept_id')
            try:
                department = CompanyDepartment.objects.get(id=dept_id, company=company)
                department.name = request.POST.get('name')
                department.description = request.POST.get('description', '')
                department.save()
                messages.success(request, f'Department "{department.name}" updated successfully.')
            except CompanyDepartment.DoesNotExist:
                messages.error(request, 'Department not found.')
            except Exception as e:
                messages.error(request, f'Error updating department: {str(e)}')
        
        elif action == 'edit_position':
            pos_id = request.POST.get('pos_id')
            try:
                position = CompanyPosition.objects.get(id=pos_id, company=company)
                position.name = request.POST.get('name')
                position.description = request.POST.get('description', '')
                dept_id = request.POST.get('department')
                if dept_id:
                    position.department = CompanyDepartment.objects.get(id=dept_id, company=company)
                else:
                    position.department = None
                position.save()
                messages.success(request, f'Position "{position.name}" updated successfully.')
            except CompanyPosition.DoesNotExist:
                messages.error(request, 'Position not found.')
            except Exception as e:
                messages.error(request, f'Error updating position: {str(e)}')
        
        elif action == 'edit_pay_grade':
            grade_id = request.POST.get('grade_id')
            try:
                pay_grade = CompanyPayGrade.objects.get(id=grade_id, company=company)
                pay_grade.name = request.POST.get('name')
                pay_grade.description = request.POST.get('description', '')
                pay_grade.save()
                messages.success(request, f'Pay grade "{pay_grade.name}" updated successfully.')
            except CompanyPayGrade.DoesNotExist:
                messages.error(request, 'Pay grade not found.')
            except Exception as e:
                messages.error(request, f'Error updating pay grade: {str(e)}')

        elif action == 'email_smtp':
            email_form = CompanyEmailSettingsForm(request.POST, instance=email_settings)
            if email_form.is_valid():
                email_form.save()
                messages.success(request, 'Email settings updated successfully.')
                return redirect('settings_dashboard')
            else:
                messages.error(request, 'Please review the email settings form for errors.')

        elif action == 'biometric':
            biometric_form = CompanyBiometricSettingsForm(request.POST, instance=biometric_settings)
            if biometric_form.is_valid():
                biometric_form.save()
                messages.success(request, 'Biometric settings updated successfully.')
                return redirect('settings_dashboard')
            else:
                messages.error(request, 'Please review the biometric settings form for errors.')
        
        elif action == 'notifications':
            from accounts.models import CompanyNotificationSettings
            from accounts.forms import CompanyNotificationSettingsForm
            notification_settings, _ = CompanyNotificationSettings.objects.get_or_create(company=company)
            notification_form = CompanyNotificationSettingsForm(request.POST, instance=notification_settings)
            if notification_form.is_valid():
                notification_form.save()
                messages.success(request, 'Notification settings updated successfully.')
                return redirect('settings_dashboard')
            else:
                messages.error(request, 'Please review the notification settings form for errors.')
        
        elif action == 'api_key':
            from accounts.models import CompanyAPIKey
            import secrets
            # Deactivate old keys
            CompanyAPIKey.objects.filter(company=company, is_active=True).update(is_active=False)
            # Generate new API key
            new_key = f"ems_api_{secrets.token_urlsafe(32)}"
            webhook_url = request.POST.get('webhook_url', '')
            api_key = CompanyAPIKey.objects.create(
                company=company,
                key=new_key,
                name=f"API Key {CompanyAPIKey.objects.filter(company=company).count() + 1}",
                webhook_url=webhook_url
            )
            messages.success(request, f'API key generated successfully!')
            return redirect('settings_dashboard')
        
        elif action == 'webhook':
            from accounts.models import CompanyAPIKey
            webhook_url = request.POST.get('webhook_url', '')
            # Update the primary API key's webhook URL
            primary_key = CompanyAPIKey.objects.filter(company=company, is_active=True).order_by('-created_at').first()
            if primary_key:
                primary_key.webhook_url = webhook_url
                primary_key.save()
                messages.success(request, 'Webhook URL updated successfully!')
            else:
                messages.error(request, 'No active API key found. Please generate an API key first.')
            return redirect('settings_dashboard')
        
        elif action == 'company_profile':
            # Update company profile including logo and stamp
            company.name = request.POST.get('company_name', company.name)
            company.address = request.POST.get('company_address', company.address)
            company.phone = request.POST.get('company_phone', company.phone)
            company.email = request.POST.get('company_email', company.email)
            company.website = request.POST.get('company_website', company.website)
            company.city = request.POST.get('company_city', company.city)
            company.country = request.POST.get('company_country', company.country)
            
            # Handle logo upload
            if 'company_logo' in request.FILES:
                company.logo = request.FILES['company_logo']
            
            # Handle stamp upload
            if 'company_stamp' in request.FILES:
                company.company_stamp = request.FILES['company_stamp']
            
            company.save()
            messages.success(request, 'Company profile updated successfully!')
            return redirect('settings_dashboard')
        
        elif action == 'payslip_design':
            import json
            # Save payslip design settings
            try:
                # Section order (drag-and-drop layout)
                section_order_json = request.POST.get('section_order', '[]')
                company.payslip_section_order = json.loads(section_order_json) if section_order_json else []
                
                # Orientation
                company.payslip_orientation = request.POST.get('payslip_orientation', 'portrait')
                
                # Logo and stamp positions
                company.payslip_logo_position = request.POST.get('payslip_logo_position', 'top-left')
                company.payslip_stamp_position = request.POST.get('payslip_stamp_position', 'bottom-right')
                
                # Header and footer
                company.payslip_header_style = request.POST.get('payslip_header_style', 'professional_table')
                company.payslip_footer_text = request.POST.get('payslip_footer_text', '')
                
                # Layout style
                payslip_layout_style = request.POST.get('payslip_layout_style', 'professional_table')
                company.payslip_header_style = payslip_layout_style  # Store layout style in header_style field
                
                # Display options
                company.show_company_logo = request.POST.get('show_company_logo') == 'on'
                company.show_company_stamp = request.POST.get('show_company_stamp') == 'on'
                company.show_signature = request.POST.get('show_signature') == 'on'
                company.show_tax_breakdown = request.POST.get('show_tax_breakdown') == 'on'
                
                # Colors
                company.payslip_header_color = request.POST.get('payslip_header_color', '#3b82f6')
                company.payslip_accent_color = request.POST.get('payslip_accent_color', '#10b981')
                company.payslip_section_color = request.POST.get('payslip_section_color', '#C5D9F1')
                
                company.save()
                messages.success(request, '✅ Payslip design saved successfully!')
            except json.JSONDecodeError:
                messages.error(request, 'Invalid section order format.')
            except Exception as e:
                messages.error(request, f'Error saving payslip design: {str(e)}')
            
            return redirect('settings_dashboard')

        else:
            return redirect('settings_dashboard')

    # Get or create notification settings
    from accounts.models import CompanyNotificationSettings, CompanyAPIKey
    from accounts.forms import CompanyNotificationSettingsForm
    notification_settings, _ = CompanyNotificationSettings.objects.get_or_create(company=company)
    notification_form = CompanyNotificationSettingsForm(instance=notification_settings)
    
    # Get API keys
    api_keys = CompanyAPIKey.objects.filter(company=company, is_active=True).order_by('-created_at')
    primary_api_key = api_keys.first()
    
    context = {
        'company': company,
        'employee_id_form': EmployeeIdConfigurationForm(instance=config),
        'department_form': CompanyDepartmentForm(company=company),
        'position_form': CompanyPositionForm(company=company),
        'pay_grade_form': CompanyPayGradeForm(company=company),
        'departments': departments,
        'positions': positions,
        'pay_grades': pay_grades,
        'employee_id_preview': config.generate_employee_id(),
        'email_form': email_form,
        'biometric_form': biometric_form,
        'notification_form': notification_form,
        'notification_settings': notification_settings,
        'api_keys': api_keys,
        'primary_api_key': primary_api_key,
        
        # Statistics
        'total_departments': total_departments,
        'total_positions': total_positions,
        'total_pay_grades': total_pay_grades,
        'total_configurations': total_configurations,
        'position_by_dept': position_by_dept,
        
        # Filter states
        'search_query': search_query,
        'dept_filter': dept_filter,
        'all_departments': CompanyDepartment.objects.filter(company=company).order_by('name'),
    }

    return render(request, 'ems/settings_company.html', context)

@login_required
def delete_department(request, dept_id):
    """Delete a department"""
    if request.method == 'POST':
        allowed_roles = {'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            dept = CompanyDepartment.objects.get(id=dept_id, company=company)
            dept_name = dept.name
            dept.delete()
            return JsonResponse({'success': True, 'message': f'Department "{dept_name}" deleted successfully'})
        except CompanyDepartment.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Department not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def delete_position(request, pos_id):
    """Delete a position"""
    if request.method == 'POST':
        allowed_roles = {'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            position = CompanyPosition.objects.get(id=pos_id, company=company)
            pos_name = position.name
            position.delete()
            return JsonResponse({'success': True, 'message': f'Position "{pos_name}" deleted successfully'})
        except CompanyPosition.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Position not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def delete_pay_grade(request, grade_id):
    """Delete a pay grade"""
    if request.method == 'POST':
        allowed_roles = {'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            grade = CompanyPayGrade.objects.get(id=grade_id, company=company)
            grade_name = grade.name
            grade.delete()
            return JsonResponse({'success': True, 'message': f'Pay grade "{grade_name}" deleted successfully'})
        except CompanyPayGrade.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Pay grade not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def test_smtp_connection(request):
    """Test SMTP connection"""
    if request.method == 'POST':
        import json
        from django.core.mail import send_mail
        from django.conf import settings
        import smtplib
        
        allowed_roles = {'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            email_settings = CompanyEmailSettings.objects.get(company=company)
            
            # Test connection
            import smtplib
            smtp = smtplib.SMTP(email_settings.smtp_host, email_settings.smtp_port, timeout=10)
            if email_settings.smtp_use_tls:
                smtp.starttls()
            if email_settings.smtp_username and email_settings.smtp_password:
                smtp.login(email_settings.smtp_username, email_settings.smtp_password)
            smtp.quit()
            
            return JsonResponse({'success': True, 'message': 'SMTP connection successful!'})
        except smtplib.SMTPAuthenticationError:
            return JsonResponse({'success': False, 'error': 'Authentication failed. Check username and password.'}, status=400)
        except smtplib.SMTPConnectError:
            return JsonResponse({'success': False, 'error': 'Cannot connect to SMTP server.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Connection failed: {str(e)}'}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def test_biometric_connection(request):
    """Test biometric device connection"""
    if request.method == 'POST':
        import requests
        
        allowed_roles = {'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'ADMIN'}
        if not (getattr(request.user, 'role', '') in allowed_roles):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        company = _get_user_company(request.user)
        try:
            biometric_settings = CompanyBiometricSettings.objects.get(company=company)
            
            if not biometric_settings.device_ip:
                return JsonResponse({'success': False, 'error': 'Device IP not configured'}, status=400)
            
            # Try to ping the device (basic connectivity test)
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((str(biometric_settings.device_ip), 80))
            sock.close()
            
            if result == 0:
                return JsonResponse({'success': True, 'message': 'Biometric device is reachable!'})
            else:
                return JsonResponse({'success': False, 'error': 'Cannot reach device. Check IP address and network.'}, status=400)
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Connection test failed: {str(e)}'}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def employer_employee_management(request):
    """Enhanced employee management with search, filters, and export"""
    # Check if user has HR or admin access
    if not _has_hr_access(request.user):
        return render(request, 'ems/unauthorized.html')

    company = _get_user_company(request.user)
    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    from accounts.models import User, CompanyDepartment, CompanyPosition
    from attendance.models import Attendance, LeaveRequest
    from documents.models import EmployeeDocument
    from performance.models import PerformanceReview
    from datetime import date, timedelta
    from django.http import HttpResponse
    import csv

    today = date.today()

    # Get base employees queryset
    employees = User.objects.filter(company=company, role='EMPLOYEE').select_related('employee_profile')

    # Handle CSV Export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="employees_{company.name}_{today}.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Employee ID', 'First Name', 'Last Name', 'Email', 'Phone', 
            'Department', 'Position', 'Employment Type', 'Hire Date', 
            'Status', 'Salary', 'Currency'
        ])
        
        for emp in employees:
            profile = emp.employee_profile if hasattr(emp, 'employee_profile') else None
            writer.writerow([
                profile.employee_id if profile else 'N/A',
                emp.first_name,
                emp.last_name,
                emp.email,
                emp.phone_number or 'N/A',
                profile.department if profile and profile.department else 'N/A',
                profile.job_title if profile and profile.job_title else 'N/A',
                profile.get_employment_type_display() if profile and profile.employment_type else 'N/A',
                profile.date_hired.strftime('%Y-%m-%d') if profile and profile.date_hired else 'N/A',
                'Active' if emp.is_active else 'Inactive',
                profile.salary if profile and profile.salary else 'N/A',
                profile.get_currency_display() if profile and profile.currency else 'N/A'
            ])
        
        return response

    # Search functionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        employees = employees.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(employee_profile__employee_id__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )

    # Department filter
    department_filter = request.GET.get('department', '')
    if department_filter:
        try:
            from accounts.models import CompanyDepartment
            dept = CompanyDepartment.objects.get(id=department_filter, company=company)
            employees = employees.filter(employee_profile__department=dept.name)
        except:
            pass

    # Position filter
    position_filter = request.GET.get('position', '')
    if position_filter:
        try:
            from accounts.models import CompanyPosition
            pos = CompanyPosition.objects.get(id=position_filter, company=company)
            employees = employees.filter(employee_profile__job_title=pos.name)
        except:
            pass

    # Employment type filter
    employment_type_filter = request.GET.get('employment_type', '')
    if employment_type_filter:
        employees = employees.filter(employee_profile__employment_type=employment_type_filter)

    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        employees = employees.filter(is_active=True)
    elif status_filter == 'inactive':
        employees = employees.filter(is_active=False)

    # Statistics for this company
    total_employees = User.objects.filter(company=company, role='EMPLOYEE').count()
    active_employees = User.objects.filter(company=company, role='EMPLOYEE', is_active=True).count()
    inactive_employees = total_employees - active_employees
    filtered_count = employees.count()

    # Today's attendance for this company
    today_attendance = Attendance.objects.filter(date=today, employee__company=company)
    present_today = today_attendance.filter(status='PRESENT').count()
    late_today = today_attendance.filter(status='LATE').count()

    # Pending leave requests for this company
    pending_leaves = LeaveRequest.objects.filter(
        employee__company=company,
        status='PENDING'
    ).count()

    # Recent documents for this company
    recent_docs = EmployeeDocument.objects.filter(
        employee__company=company
    ).select_related('employee', 'category').order_by('-created_at')[:5]

    # Upcoming performance reviews for this company
    upcoming_reviews = PerformanceReview.objects.filter(
        employee__company=company,
        review_date__gte=today
    ).select_related('employee', 'reviewer').order_by('review_date')[:5]

    # Get filter options
    all_departments = CompanyDepartment.objects.filter(company=company).order_by('name')
    all_positions = CompanyPosition.objects.filter(company=company).order_by('name')
    
    # Employment type choices
    from accounts.models import EmployeeProfile
    employment_types = EmployeeProfile.EmploymentType.choices

    # Prepare employee data for template
    for employee in employees:
        today_att = today_attendance.filter(employee=employee).first()
        employee.attendance_status = today_att.status if today_att else 'ABSENT'
        employee.pending_leaves = LeaveRequest.objects.filter(
            employee=employee, status='PENDING'
        ).count()

    context = {
        'user': request.user,
        'company': company,
        'employees': employees,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'inactive_employees': inactive_employees,
        'filtered_count': filtered_count,
        'present_today': present_today,
        'late_today': late_today,
        'pending_leaves': pending_leaves,
        'recent_docs': recent_docs,
        'upcoming_reviews': upcoming_reviews,
        'today_date': today.strftime('%Y-%m-%d'),
        # Filter options
        'all_departments': all_departments,
        'all_positions': all_positions,
        'employment_types': employment_types,
        # Current filters
        'search_query': search_query,
        'department_filter': department_filter,
        'position_filter': position_filter,
        'employment_type_filter': employment_type_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'ems/employer_employee_management.html', context)

@login_required
def employee_bulk_action(request):
    """Handle bulk actions on employees"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    company = _get_user_company(request.user)
    if not company:
        return JsonResponse({'success': False, 'error': 'Company not assigned'}, status=400)
    
    import json
    try:
        data = json.loads(request.body)
        action = data.get('action')
        employee_ids = data.get('employee_ids', [])
        
        if not action or not employee_ids:
            return JsonResponse({'success': False, 'error': 'Missing action or employee IDs'}, status=400)
        
        from accounts.models import User
        employees = User.objects.filter(id__in=employee_ids, company=company, role='EMPLOYEE')
        
        if action == 'activate':
            count = employees.update(is_active=True)
            return JsonResponse({'success': True, 'message': f'{count} employee(s) activated successfully'})
        
        elif action == 'deactivate':
            count = employees.update(is_active=False)
            return JsonResponse({'success': True, 'message': f'{count} employee(s) deactivated successfully'})
        
        elif action == 'delete':
            count = employees.count()
            employees.delete()
            return JsonResponse({'success': True, 'message': f'{count} employee(s) deleted successfully'})
        
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def employer_add_employee(request):
    """Add new employee for employers"""
    # Check if user is employer (superuser or admin)
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')

    try:
        company = request.user.company
    except:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    from accounts.models import (
        User,
        EmployeeProfile,
    )
    from django.contrib.auth.hashers import make_password

    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        employee_id = request.POST.get('employee_id')
        department = request.POST.get('department')
        job_title = request.POST.get('job_title') or request.POST.get('position')
        salary = request.POST.get('salary')
        pay_grade = request.POST.get('pay_grade')
        hire_date = request.POST.get('hire_date')
        employee_role_value = request.POST.get('employee_role') or EmployeeProfile.EmployeeRole.EMPLOYEE
        employment_type_value = request.POST.get('employment_type') or ''
        currency_value = request.POST.get('currency') or EmployeeProfile.Currency.ZMW
        probation_start_input = request.POST.get('probation_start_date')
        probation_end_input = request.POST.get('probation_end_date')
        contract_start_input = request.POST.get('contract_start_date')
        contract_end_input = request.POST.get('contract_end_date')
        temporary_start_input = request.POST.get('temporary_start_date')
        temporary_end_input = request.POST.get('temporary_end_date')
        profile_picture_file = request.FILES.get('profile_picture')
        supervisor_id = request.POST.get('supervisor')

        if employee_role_value not in EmployeeProfile.EmployeeRole.values:
            employee_role_value = EmployeeProfile.EmployeeRole.EMPLOYEE

        if employment_type_value and employment_type_value not in EmployeeProfile.EmploymentType.values:
            employment_type_value = ''
        
        if currency_value not in EmployeeProfile.Currency.values:
            currency_value = EmployeeProfile.Currency.ZMW

        probation_start_input = request.POST.get('probation_start_date')
        probation_end_input = request.POST.get('probation_end_date')
        contract_start_input = request.POST.get('contract_start_date')
        contract_end_input = request.POST.get('contract_end_date')
        temporary_start_input = request.POST.get('temporary_start_date')
        temporary_end_input = request.POST.get('temporary_end_date')

        try:
            probation_start = datetime.strptime(probation_start_input, '%Y-%m-%d').date() if probation_start_input else None
        except ValueError:
            messages.error(request, 'Invalid probation start date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            probation_end = datetime.strptime(probation_end_input, '%Y-%m-%d').date() if probation_end_input else None
        except ValueError:
            messages.error(request, 'Invalid probation end date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            contract_start = datetime.strptime(contract_start_input, '%Y-%m-%d').date() if contract_start_input else None
        except ValueError:
            messages.error(request, 'Invalid contract start date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            contract_end = datetime.strptime(contract_end_input, '%Y-%m-%d').date() if contract_end_input else None
        except ValueError:
            messages.error(request, 'Invalid contract end date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            temporary_start = datetime.strptime(temporary_start_input, '%Y-%m-%d').date() if temporary_start_input else None
        except ValueError:
            messages.error(request, 'Invalid temporary start date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        try:
            temporary_end = datetime.strptime(temporary_end_input, '%Y-%m-%d').date() if temporary_end_input else None
        except ValueError:
            messages.error(request, 'Invalid temporary end date. Use YYYY-MM-DD.')
            return redirect('employer_add_employee')

        if employment_type_value == EmployeeProfile.EmploymentType.PROBATION:
            if not (probation_start and probation_end):
                messages.error(request, 'Probation start and end dates are required for probation employees.')
                return redirect('employer_add_employee')
            if probation_end < probation_start:
                messages.error(request, 'Probation end date cannot be earlier than the start date.')
                return redirect('employer_add_employee')
        else:
            probation_start = None
            probation_end = None

        if employment_type_value == EmployeeProfile.EmploymentType.CONTRACT:
            if not (contract_start and contract_end):
                messages.error(request, 'Contract start and end dates are required for contract employees.')
                return redirect('employer_add_employee')
            if contract_end < contract_start:
                messages.error(request, 'Contract end date cannot be earlier than the start date.')
                return redirect('employer_add_employee')
        else:
            contract_start = None
            contract_end = None

        if employment_type_value == EmployeeProfile.EmploymentType.TEMPORARY:
            if not (temporary_start and temporary_end):
                messages.error(request, 'Temporary start and end dates are required for temporary employees.')
                return redirect('employer_add_employee')
            if temporary_end < temporary_start:
                messages.error(request, 'Temporary end date cannot be earlier than the start date.')
                return redirect('employer_add_employee')
        else:
            temporary_start = None
            temporary_end = None

        # Validation
        if not all([first_name, last_name, email, password, confirm_password]):
            messages.error(request, 'Please fill in all required fields (name, email, password).')
            return redirect('employer_add_employee')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('employer_add_employee')

        # Additional required employment fields
        if not all([employee_id, job_title, hire_date]):
            messages.error(request, 'Please provide Employee ID, Job Title, and Hire Date.')
            return redirect('employer_add_employee')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An employee with this email already exists.')
            return redirect('employer_add_employee')

        try:
            # Create user
            user = User.objects.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone,
                username=email,  # Use email as username
                role='EMPLOYEE',
                is_active=True,
                company=company,
                password=make_password(password)
            )

            if profile_picture_file:
                user.profile_picture = profile_picture_file
                user.save(update_fields=['profile_picture'])

            # Coerce types
            from decimal import Decimal
            salary_val = None
            try:
                salary_val = Decimal(salary) if salary else None
            except Exception:
                salary_val = None

            # Create employee profile
            profile = EmployeeProfile.objects.create(
                user=user,
                company=company,
                employee_id=employee_id,
                department=department or 'Unassigned',
                job_title=job_title or 'Employee',
                salary=salary_val,
                currency=currency_value,
                pay_grade=pay_grade or '',
                date_hired=hire_date if hire_date else timezone.now().date(),
                employee_role=employee_role_value,
                employment_type=employment_type_value,
                probation_start_date=probation_start,
                probation_end_date=probation_end,
                contract_start_date=contract_start,
                contract_end_date=contract_end,
                temporary_start_date=temporary_start,
                temporary_end_date=temporary_end,
            )
            
            # Assign supervisor if provided
            if supervisor_id:
                try:
                    supervisor = User.objects.get(id=supervisor_id, company=company)
                    profile.supervisor = supervisor
                    profile.save(update_fields=['supervisor'])
                except User.DoesNotExist:
                    pass

            # Optional emergency fields if the model supports them
            employee.employee_profile = profile

            emergency_fields = {
                'emergency_contact_name': request.POST.get('emergency_contact_name') or None,
                'emergency_contact_relationship': request.POST.get('emergency_contact_relationship') or None,
                'emergency_contact_phone': request.POST.get('emergency_contact_phone') or None,
                'emergency_contact_email': request.POST.get('emergency_contact_email') or None,
                'emergency_contact_address': request.POST.get('emergency_contact_address') or None,
            }
            changed = False
            for attr, val in emergency_fields.items():
                if val and hasattr(profile, attr):
                    setattr(profile, attr, val)
                    changed = True
            if changed:
                profile.save()

            # Increment employee ID counter if auto-generated
            if request.POST.get('employee_id_autofilled') == '1':
                try:
                    config = EmployeeIdConfiguration.objects.get(company=company)
                    config.increment()
                except EmployeeIdConfiguration.DoesNotExist:
                    pass

            # Send welcome email with credentials
            try:
                from ems_project.notifications import EmailNotificationService
                EmailNotificationService.send_new_employee_credentials(
                    employee=user,
                    temporary_password=password,
                    created_by=request.user
                )
                messages.success(request, f'Employee {first_name} {last_name} has been added successfully! Login credentials sent to {email}.')
            except Exception as e:
                messages.success(request, f'Employee {first_name} {last_name} has been added successfully!')
                messages.warning(request, f'Email notification could not be sent: {str(e)}')
            
            return redirect('employer_employee_management')

        except Exception as e:
            messages.error(request, f'Error creating employee: {str(e)}')
            return redirect('employer_add_employee')

    # GET request - show the form
    config = EmployeeIdConfiguration.objects.filter(company=company).first()
    employee_id_suggestion = config.generate_employee_id() if config else ''
    company_departments = CompanyDepartment.objects.filter(company=company).order_by('name')
    company_positions = CompanyPosition.objects.filter(company=company).select_related('department').order_by('name')
    company_pay_grades = CompanyPayGrade.objects.filter(company=company).order_by('name')
    
    # Get available supervisors (users with SUPERVISOR role or higher)
    available_supervisors = User.objects.filter(
        company=company,
        is_active=True
    ).filter(
        employee_profile__employee_role__in=['SUPERVISOR', 'HR', 'ADMINISTRATOR']
    ).select_related('employee_profile').order_by('first_name', 'last_name')

    context = {
        'user': request.user,
        'company': company,
        'employee_id_suggestion': employee_id_suggestion,
        'company_departments': company_departments,
        'company_positions': company_positions,
        'company_pay_grades': company_pay_grades,
        'available_supervisors': available_supervisors,
        'employee_role_choices': EmployeeProfile.EmployeeRole.choices,
        'default_employee_role': EmployeeProfile.EmployeeRole.EMPLOYEE,
        'employment_type_choices': EmployeeProfile.EmploymentType.choices,
    }
    return render(request, 'ems/employer_add_employee_simple.html', context)

@login_required
def employer_edit_employee(request, employee_id):
    """Edit employee information for employers and supervisors"""
    try:
        company = request.user.company
    except:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    from accounts.models import User, EmployeeProfile

    try:
        employee = User.objects.get(id=employee_id, company=company, role='EMPLOYEE')
    except User.DoesNotExist:
        messages.error(request, 'Employee not found or not in your company.')
        return redirect('employer_employee_management')
    
    # Check permissions
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin
    is_supervisor = hasattr(request.user, 'employee_profile') and request.user.employee_profile.employee_role == 'SUPERVISOR'
    is_supervising = is_supervisor and employee.employee_profile.supervisor == request.user
    
    if not (is_admin or is_supervising):
        messages.error(request, 'Access denied. You do not have permission to view this employee.')
        return render(request, 'ems/unauthorized.html')

    if request.method == 'POST':
        # Only admins can edit employee information
        if not is_admin:
            messages.error(request, 'Access denied. Only administrators can edit employee information.')
            return redirect('employer_edit_employee', employee_id=employee_id)
        print("=" * 80)
        print("FORM SUBMISSION RECEIVED")
        print(f"POST Data: {dict(request.POST)}")
        print(f"FILES: {dict(request.FILES)}")
        print("=" * 80)
        
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        date_of_birth_input = request.POST.get('date_of_birth')
        employee_id_field = request.POST.get('employee_id')
        department = request.POST.get('department')
        position = request.POST.get('position')
        job_title = request.POST.get('job_title')
        salary = request.POST.get('salary')
        pay_grade = request.POST.get('pay_grade')
        hire_date_input = request.POST.get('hire_date')
        bank_name = request.POST.get('bank_name')
        account_number = request.POST.get('account_number')
        bank_branch = request.POST.get('bank_branch')
        emergency_contact_name = request.POST.get('emergency_contact_name')
        emergency_contact_phone = request.POST.get('emergency_contact_phone')
        emergency_contact_email = request.POST.get('emergency_contact_email')
        emergency_contact_address = request.POST.get('emergency_contact_address')
        is_active = request.POST.get('is_active') == 'on'
        employee_role_value = request.POST.get('employee_role') or EmployeeProfile.EmployeeRole.EMPLOYEE
        employment_type_value = request.POST.get('employment_type') or ''
        currency_value = request.POST.get('currency') or EmployeeProfile.Currency.ZMW
        probation_start_input = request.POST.get('probation_start_date')
        probation_end_input = request.POST.get('probation_end_date')
        contract_start_input = request.POST.get('contract_start_date')
        contract_end_input = request.POST.get('contract_end_date')
        temporary_start_input = request.POST.get('temporary_start_date')
        temporary_end_input = request.POST.get('temporary_end_date')
        profile_picture_file = request.FILES.get('profile_picture')
        supervisor_id = request.POST.get('supervisor')
        
        print(f"Processing update for: {first_name} {last_name}")

        if employee_role_value not in EmployeeProfile.EmployeeRole.values:
            employee_role_value = EmployeeProfile.EmployeeRole.EMPLOYEE
        
        if employment_type_value and employment_type_value not in EmployeeProfile.EmploymentType.values:
            employment_type_value = ''
        
        if currency_value not in EmployeeProfile.Currency.values:
            currency_value = EmployeeProfile.Currency.ZMW

        def parse_date(value, label):
            if not value:
                return None
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, f'Invalid {label}. Use YYYY-MM-DD format.')
                return None

        probation_start = parse_date(probation_start_input, 'probation start date')
        if probation_start_input and probation_start is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        probation_end = parse_date(probation_end_input, 'probation end date')
        if probation_end_input and probation_end is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        contract_start = parse_date(contract_start_input, 'contract start date')
        if contract_start_input and contract_start is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        contract_end = parse_date(contract_end_input, 'contract end date')
        if contract_end_input and contract_end is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        temporary_start = parse_date(temporary_start_input, 'temporary start date')
        if temporary_start_input and temporary_start is None:
            return redirect('employer_edit_employee', employee_id=employee_id)
        temporary_end = parse_date(temporary_end_input, 'temporary end date')
        if temporary_end_input and temporary_end is None:
            return redirect('employer_edit_employee', employee_id=employee_id)

        if employment_type_value == EmployeeProfile.EmploymentType.PROBATION:
            if not (probation_start and probation_end):
                messages.error(request, 'Probation employees require start and end dates.')
                return redirect('employer_edit_employee', employee_id=employee_id)
            if probation_end < probation_start:
                messages.error(request, 'Probation end date cannot be earlier than the start date.')
                return redirect('employer_edit_employee', employee_id=employee_id)
        else:
            probation_start = None
            probation_end = None

        if employment_type_value == EmployeeProfile.EmploymentType.CONTRACT:
            if not (contract_start and contract_end):
                messages.error(request, 'Contract employees require start and end dates.')
                return redirect('employer_edit_employee', employee_id=employee_id)
            if contract_end < contract_start:
                messages.error(request, 'Contract end date cannot be earlier than the start date.')
                return redirect('employer_edit_employee', employee_id=employee_id)
        else:
            contract_start = None
            contract_end = None

        if employment_type_value == EmployeeProfile.EmploymentType.TEMPORARY:
            if not (temporary_start and temporary_end):
                messages.error(request, 'Temporary employees require start and end dates.')
                return redirect('employer_edit_employee', employee_id=employee_id)
            if temporary_end < temporary_start:
                messages.error(request, 'Temporary end date cannot be earlier than the start date.')
                return redirect('employer_edit_employee', employee_id=employee_id)
        else:
            temporary_start = None
            temporary_end = None

        hire_date_value = None
        if hire_date_input:
            try:
                hire_date_value = datetime.strptime(hire_date_input, '%Y-%m-%d').date()
            except ValueError:
                hire_date_value = None

        date_of_birth_value = None
        if date_of_birth_input:
            try:
                date_of_birth_value = datetime.strptime(date_of_birth_input, '%Y-%m-%d').date()
            except ValueError:
                date_of_birth_value = None

        # Check if email is being changed and already exists
        if email != employee.email and User.objects.filter(email=email).exists():
            messages.error(request, 'An employee with this email already exists.')
            return redirect('employer_edit_employee', employee_id=employee_id)

        try:
            # Update user
            employee.first_name = first_name
            employee.last_name = last_name
            employee.email = email
            employee.phone_number = phone  # Fixed: User model has phone_number, not phone
            # Note: address and date_of_birth should be in EmployeeProfile, not User
            employee.is_active = is_active
            # Profile picture is also typically in EmployeeProfile
            employee.save()

            # Update employee profile
            profile, created = EmployeeProfile.objects.get_or_create(user=employee)
            profile.employee_id = employee_id_field
            profile.department = department or ''
            profile.job_title = job_title or position or ''
            profile.salary = Decimal(salary) if salary else None
            profile.currency = currency_value
            profile.pay_grade = pay_grade or ''
            profile.date_hired = hire_date_value if hire_date_value else profile.date_hired
            profile.probation_start_date = probation_start
            profile.probation_end_date = probation_end
            profile.contract_start_date = contract_start
            profile.contract_end_date = contract_end
            profile.temporary_start_date = temporary_start
            profile.temporary_end_date = temporary_end
            profile.bank_name = bank_name or ''
            profile.account_number = account_number or ''
            profile.bank_branch = bank_branch or ''
            profile.emergency_contact_name = emergency_contact_name or ''
            profile.emergency_contact_phone = emergency_contact_phone or ''
            profile.emergency_contact_email = emergency_contact_email or ''
            profile.emergency_contact_address = emergency_contact_address or ''
            profile.employee_role = employee_role_value
            profile.employment_type = employment_type_value
            
            # Assign supervisor
            if supervisor_id:
                try:
                    supervisor = User.objects.get(id=supervisor_id, company=company)
                    profile.supervisor = supervisor
                except User.DoesNotExist:
                    profile.supervisor = None
            else:
                profile.supervisor = None
            
            if not profile.company:
                profile.company = company
            profile.save()

            print(f"✓ Employee {first_name} {last_name} updated successfully!")
            print("=" * 80)
            messages.success(request, f'✓ Employee {first_name} {last_name} has been updated successfully! All changes saved.')
            return redirect('employer_edit_employee', employee_id=employee_id)

        except Exception as e:
            print(f"✗ ERROR updating employee: {str(e)}")
            print("=" * 80)
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error updating employee: {str(e)}')
            return redirect('employer_edit_employee', employee_id=employee_id)

    # Get employee profile
    profile_instance, _ = ensure_employee_profile(employee, company)

    # Prepare document context
    categories = list(DocumentCategory.objects.all().order_by('-is_required', 'name'))
    document_type_labels = dict(EmployeeDocument.DocumentType.choices)
    employee_documents = list(
        EmployeeDocument.objects.filter(employee=employee)
        .select_related('category', 'uploaded_by', 'approved_by')
        .order_by('-created_at', '-version')
    )

    documents_by_category = []
    for category in categories:
        category_docs = [doc for doc in employee_documents if doc.category_id == category.id]
        default_document_type = category.default_document_type or EmployeeDocument.DocumentType.OTHER
        if default_document_type not in document_type_labels:
            default_document_type = EmployeeDocument.DocumentType.OTHER
        documents_by_category.append({
            'category': category,
            'documents': category_docs,
            'is_required': category.is_required,
            'is_completed': bool(category_docs),
            'default_document_type': default_document_type,
            'default_document_type_label': document_type_labels.get(default_document_type, document_type_labels.get(EmployeeDocument.DocumentType.OTHER)),
            'tab_id': f"category-{category.id}",
        })

    uncategorized_documents = [doc for doc in employee_documents if doc.category_id is None]
    required_total = sum(1 for entry in documents_by_category if entry['is_required'])
    required_completed = sum(1 for entry in documents_by_category if entry['is_required'] and entry['is_completed'])

    selected_role = getattr(profile_instance, 'employee_role', EmployeeProfile.EmployeeRole.EMPLOYEE) or EmployeeProfile.EmployeeRole.EMPLOYEE
    selected_employment_type = getattr(profile_instance, 'employment_type', '') or ''
    selected_currency = getattr(profile_instance, 'currency', EmployeeProfile.Currency.ZMW) or EmployeeProfile.Currency.ZMW
    
    # Debug logging
    print(f"DEBUG - Profile employee_role from DB: '{profile_instance.employee_role}'")
    print(f"DEBUG - Selected role for template: '{selected_role}'")

    # Get company configuration options
    departments = CompanyDepartment.objects.filter(company=company).order_by('name')
    positions = CompanyPosition.objects.filter(company=company).order_by('name')
    pay_grades = CompanyPayGrade.objects.filter(company=company).order_by('name')
    
    # Get available supervisors (users with SUPERVISOR role or higher, excluding the current employee)
    available_supervisors = User.objects.filter(
        company=company,
        is_active=True
    ).filter(
        employee_profile__employee_role__in=['SUPERVISOR', 'HR', 'ADMINISTRATOR']
    ).exclude(
        id=employee.id
    ).select_related('employee_profile').order_by('first_name', 'last_name')

    # Calculate profile completeness
    profile_fields = {
        'employee_id': bool(profile_instance.employee_id),
        'department': bool(profile_instance.department),
        'job_title': bool(profile_instance.job_title),
        'date_hired': bool(profile_instance.date_hired),
        'salary': bool(profile_instance.salary),
        'employment_type': bool(profile_instance.employment_type),
        'phone': bool(employee.phone_number),
        'email': bool(employee.email),
        'bank_info': bool(profile_instance.bank_name and profile_instance.account_number),
        'emergency_contact': bool(profile_instance.emergency_contact_name and profile_instance.emergency_contact_phone),
    }
    completed_fields = sum(profile_fields.values())
    total_fields = len(profile_fields)
    profile_completeness = round((completed_fields / total_fields) * 100) if total_fields > 0 else 0

    # Get employee statistics
    from datetime import date, timedelta
    today = date.today()
    month_ago = today - timedelta(days=30)
    
    # Attendance statistics
    from attendance.models import Attendance
    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__gte=month_ago
    )
    total_attendance_days = attendance_records.count()
    present_days = attendance_records.filter(status='PRESENT').count()
    late_days = attendance_records.filter(status='LATE').count()
    absent_days = attendance_records.filter(status='ABSENT').count()
    attendance_rate = round((present_days / total_attendance_days * 100) if total_attendance_days > 0 else 0, 1)

    # Leave statistics
    from attendance.models import LeaveRequest
    leave_requests = LeaveRequest.objects.filter(employee=employee)
    pending_leaves = leave_requests.filter(status='PENDING').count()
    approved_leaves = leave_requests.filter(status='APPROVED').count()
    rejected_leaves = leave_requests.filter(status='REJECTED').count()
    
    # Recent leave requests
    recent_leaves = leave_requests.order_by('-created_at')[:5]

    # Document statistics
    total_documents = len(employee_documents)
    pending_documents = sum(1 for doc in employee_documents if doc.status == 'PENDING')
    approved_documents = sum(1 for doc in employee_documents if doc.status == 'APPROVED')

    # Performance reviews
    from performance.models import PerformanceReview
    performance_reviews = PerformanceReview.objects.filter(
        employee=employee
    ).select_related('reviewer').order_by('-review_date')[:5]
    
    # Employee assets
    try:
        from assets.models import EmployeeAsset
        employee_assets = EmployeeAsset.objects.filter(employee=employee).order_by('-assigned_date')
        employee_assets_count = employee_assets.count()
        # Get available assets (unassigned) for assignment dropdown
        available_assets = EmployeeAsset.objects.filter(
            status='AVAILABLE',
            employee__isnull=True
        ).order_by('asset_tag')
    except ImportError:
        employee_assets = []
        employee_assets_count = 0
        available_assets = []
    
    # Calculate days employed
    days_employed = (today - profile_instance.date_hired).days if profile_instance.date_hired else 0
    years_employed = days_employed // 365
    months_employed = (days_employed % 365) // 30

    # Contract expiry warning
    contract_expiry_warning = None
    if profile_instance.employment_type == 'CONTRACT' and profile_instance.contract_end_date:
        days_until_expiry = (profile_instance.contract_end_date - today).days
        if 0 <= days_until_expiry <= 90:
            contract_expiry_warning = {
                'days': days_until_expiry,
                'date': profile_instance.contract_end_date,
                'is_critical': days_until_expiry <= 30
            }
    elif profile_instance.employment_type == 'PROBATION' and profile_instance.probation_end_date:
        days_until_expiry = (profile_instance.probation_end_date - today).days
        if 0 <= days_until_expiry <= 90:
            contract_expiry_warning = {
                'days': days_until_expiry,
                'date': profile_instance.probation_end_date,
                'is_critical': days_until_expiry <= 30,
                'type': 'Probation'
            }
    elif profile_instance.employment_type == 'TEMPORARY' and profile_instance.temporary_end_date:
        days_until_expiry = (profile_instance.temporary_end_date - today).days
        if 0 <= days_until_expiry <= 90:
            contract_expiry_warning = {
                'days': days_until_expiry,
                'date': profile_instance.temporary_end_date,
                'is_critical': days_until_expiry <= 30,
                'type': 'Temporary'
            }

    # Determine which base template to use
    if is_supervising and not is_admin:
        base_template = 'ems/base_employee.html'  # Supervisors use employee navigation
    else:
        base_template = 'ems/base_employer.html'  # Admins use employer navigation
    
    context = {
        'user': request.user,
        'company': company,
        'employee': employee,
        'profile': profile_instance,
        'base_template': base_template,
        'employee_role_choices': EmployeeProfile.EmployeeRole.choices,
        'selected_employee_role': selected_role,
        'employment_type_choices': EmployeeProfile.EmploymentType.choices,
        'selected_employment_type': selected_employment_type,
        'currency_choices': EmployeeProfile.Currency.choices,
        'selected_currency': selected_currency,
        'documents_by_category': documents_by_category,
        'uncategorized_documents': uncategorized_documents,
        'required_documents_total': required_total,
        'required_documents_completed': required_completed,
        'company_departments': departments,
        'company_positions': positions,
        'company_pay_grades': pay_grades,
        'available_supervisors': available_supervisors,
        
        # Permission flags
        'is_admin': is_admin,
        'is_supervisor_view': is_supervising and not is_admin,
        
        # Enhanced statistics
        'profile_completeness': profile_completeness,
        'profile_fields': profile_fields,
        'completed_fields': completed_fields,
        'total_fields': total_fields,
        
        # Attendance stats
        'attendance_rate': attendance_rate,
        'present_days': present_days,
        'late_days': late_days,
        'absent_days': absent_days,
        'total_attendance_days': total_attendance_days,
        
        # Leave stats
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'rejected_leaves': rejected_leaves,
        'recent_leaves': recent_leaves,
        
        # Document stats
        'total_documents': total_documents,
        'pending_documents': pending_documents,
        'approved_documents': approved_documents,
        'employee_documents': employee_documents,
        'employee_documents_count': total_documents,
        
        # Assets
        'employee_assets': employee_assets,
        'employee_assets_count': employee_assets_count,
        'available_assets': available_assets,
        
        # Performance
        'performance_reviews': performance_reviews,
        'performance_reviews_count': performance_reviews.count() if performance_reviews else 0,
        
        # Employment info
        'days_employed': days_employed,
        'years_employed': years_employed,
        'months_employed': months_employed,
        'contract_expiry_warning': contract_expiry_warning,
    }

    return render(request, 'ems/employer_edit_employee.html', context)


@login_required
@require_http_methods(["POST"])
def document_upload(request):
    """Handle document upload for employees"""
    try:
        from documents.models import EmployeeDocument
        
        employee_id = request.POST.get('employee_id')
        document_type = request.POST.get('document_type')
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        file = request.FILES.get('file')
        
        if not all([employee_id, document_type, title, file]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        employee = User.objects.get(id=employee_id)
        
        # Check permissions
        if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
            if request.user.id != employee.id:
                return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Create document
        document = EmployeeDocument.objects.create(
            employee=employee,
            document_type=document_type,
            title=title,
            description=description,
            file=file,
            uploaded_by=request.user,
            status='PENDING'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Document uploaded successfully',
            'document_id': document.id
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def asset_assign(request):
    """Handle asset assignment to employees (assign existing asset from inventory)"""
    try:
        from assets.models import EmployeeAsset
        from datetime import date
        
        employee_id = request.POST.get('employee_id')
        asset_id = request.POST.get('asset_id')
        notes = request.POST.get('notes', '')
        
        if not employee_id or not asset_id:
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        employee = User.objects.get(id=employee_id)
        
        # Check permissions
        if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Get the asset
        try:
            asset = EmployeeAsset.objects.get(id=asset_id)
        except EmployeeAsset.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Asset not found'})
        
        # Check if asset is already assigned
        if asset.employee is not None:
            return JsonResponse({'success': False, 'error': f'Asset is already assigned to {asset.employee.get_full_name()}'})
        
        # Check if asset is available
        if asset.status != 'AVAILABLE':
            return JsonResponse({'success': False, 'error': f'Asset is not available. Current status: {asset.get_status_display()}'})
        
        # Assign the asset
        asset.employee = employee
        asset.status = 'ASSIGNED'
        asset.assigned_date = date.today()
        asset.assigned_by = request.user
        if notes:
            asset.notes = notes if not asset.notes else f"{asset.notes}\n\n[{date.today()}] {notes}"
        asset.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Asset {asset.asset_tag} assigned successfully to {employee.get_full_name()}',
            'asset_id': asset.id
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def employee_reset_password(request):
    """Reset employee password"""
    try:
        employee_id = request.POST.get('employee_id')
        new_password = request.POST.get('new_password')
        
        if not employee_id or not new_password:
            return JsonResponse({'success': False, 'error': 'Missing employee ID or password'})
        
        employee = User.objects.get(id=employee_id)
        
        # Check permissions - only employers can reset passwords
        if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Reset password
        employee.set_password(new_password)
        employee.save()
        
        # Send email notification
        try:
            from ems_project.notifications import EmailNotificationService
            EmailNotificationService.send_password_changed_notification(
                employee=employee,
                new_password=new_password,
                changed_by=request.user
            )
        except Exception as e:
            # Don't fail password reset if email fails
            print(f"Failed to send password reset email: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Password reset successfully'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def employee_profile_picture_upload(request):
    """Handle profile picture upload for employees"""
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    import os
    from io import BytesIO
    
    try:
        from PIL import Image
    except ImportError:
        return JsonResponse({
            'success': False, 
            'error': 'Image processing library (Pillow) not installed. Please contact administrator.'
        })
    
    try:
        employee_id = request.POST.get('employee_id')
        profile_picture = request.FILES.get('profile_picture')
        
        if not employee_id or not profile_picture:
            return JsonResponse({'success': False, 'error': 'Missing employee ID or file'})
        
        # Get employee
        employee = User.objects.get(id=employee_id)
        
        # Check permissions
        if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
            # Check if user is editing their own profile
            if request.user.id != employee.id:
                return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if profile_picture.content_type not in allowed_types:
            return JsonResponse({'success': False, 'error': 'Invalid file type. Only JPG and PNG are allowed'})
        
        # Validate file size (5MB max)
        if profile_picture.size > 5 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File too large. Maximum size is 5MB'})
        
        # Process image with Pillow to resize and optimize
        try:
            image = Image.open(profile_picture)
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize to 400x400 maintaining aspect ratio
            image.thumbnail((400, 400), Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = BytesIO()
            image.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            # Delete old profile picture if exists
            if employee.profile_picture:
                try:
                    default_storage.delete(employee.profile_picture.path)
                except:
                    pass
            
            # Generate filename
            ext = 'jpg'
            filename = f'profile_pictures/employee_{employee.id}_{int(timezone.now().timestamp())}.{ext}'
            
            # Save new file
            employee.profile_picture.save(filename, ContentFile(output.read()), save=True)
            
            return JsonResponse({
                'success': True,
                'message': 'Profile picture updated successfully',
                'url': employee.profile_picture.url
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error processing image: {str(e)}'})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def bulk_employee_import(request):
    """Bulk import employees from CSV/Excel"""
    if not _has_hr_access(request.user):
        return render(request, 'ems/unauthorized.html')
    
    if request.method == 'POST':
        import csv
        import io
        
        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'Please upload a file')
            return redirect('bulk_employee_import')
        
        # Check file extension
        if not file.name.endswith('.csv'):
            messages.error(request, 'Only CSV files are supported')
            return redirect('bulk_employee_import')
        
        try:
            # Read CSV
            decoded_file = file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            imported = 0
            errors = []
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Required fields
                    email = row.get('email', '').strip()
                    first_name = row.get('first_name', '').strip()
                    last_name = row.get('last_name', '').strip()
                    
                    if not all([email, first_name, last_name]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Check if user exists
                    if User.objects.filter(email=email).exists():
                        errors.append(f"Row {row_num}: Email {email} already exists")
                        continue
                    
                    # Create user
                    temp_password = 'TempPass123!'
                    user = User.objects.create_user(
                        email=email,
                        username=email,
                        first_name=first_name,
                        last_name=last_name,
                        password=temp_password,
                        role='EMPLOYEE',
                        company=request.user.company
                    )
                    
                    # Create profile
                    profile, created = EmployeeProfile.objects.get_or_create(user=user)
                    profile.employee_id = row.get('employee_id', '')
                    profile.job_title = row.get('job_title', '')
                    profile.department = row.get('department', '')
                    profile.phone_number = row.get('phone_number', '')
                    profile.date_hired = row.get('date_hired', None)
                    profile.save()
                    
                    # Send welcome email
                    try:
                        from ems_project.notifications import EmailNotificationService
                        EmailNotificationService.send_new_employee_credentials(
                            employee=user,
                            temporary_password=temp_password,
                            created_by=request.user
                        )
                    except Exception as email_error:
                        # Don't fail import if email fails
                        errors.append(f"Row {row_num}: Imported but email failed - {str(email_error)}")
                    
                    imported += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            # Show results
            if imported > 0:
                messages.success(request, f'Successfully imported {imported} employees')
            if errors:
                for error in errors[:10]:  # Show first 10 errors
                    messages.warning(request, error)
                if len(errors) > 10:
                    messages.warning(request, f'...and {len(errors) - 10} more errors')
            
            return redirect('bulk_employee_import')
            
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('bulk_employee_import')
    
    return render(request, 'ems/bulk_employee_import.html')


@login_required
def reports_center(request):
    """Reports and exports center"""
    # Allow admins and accountants/finance roles
    is_admin = request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin
    is_accountant = hasattr(request.user, 'employee_profile') and request.user.employee_profile.employee_role in ['ACCOUNTANT', 'ACCOUNTS']
    
    if not (is_admin or is_accountant):
        messages.error(request, 'Access denied. Only administrators and accountants can access reports.')
        return render(request, 'ems/unauthorized.html')
    
    from attendance.models import Attendance, LeaveRequest
    from documents.models import EmployeeDocument
    from datetime import date, timedelta
    
    # Get employer's company
    if request.user.role == 'ADMINISTRATOR':
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        employees = User.objects.filter(company=request.user.company, role='EMPLOYEE')
    
    today = date.today()
    
    # Report statistics
    stats = {
        'total_employees': employees.count(),
        'active_employees': employees.filter(is_active=True).count(),
        'total_attendance_records': Attendance.objects.filter(employee__in=employees).count(),
        'total_leave_requests': LeaveRequest.objects.filter(employee__in=employees).count(),
        'total_documents': EmployeeDocument.objects.filter(employee__in=employees).count(),
    }
    
    # Determine base template based on role
    if is_accountant and not is_admin:
        base_template = 'ems/base_employee.html'
    else:
        base_template = 'ems/base_employer.html'
    
    context = {
        'stats': stats,
        'today': today,
        'base_template': base_template,
    }
    
    return render(request, 'ems/reports_center.html', context)


@login_required
def export_employee_roster(request):
    """Export employee roster to CSV"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    
    # Get employees
    if request.user.role == 'ADMINISTRATOR':
        employees = User.objects.filter(role='EMPLOYEE').select_related('employee_profile')
    else:
        employees = User.objects.filter(company=request.user.company, role='EMPLOYEE').select_related('employee_profile')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="employee_roster_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee ID', 'First Name', 'Last Name', 'Email', 'Phone', 
        'Department', 'Job Title', 'Employment Type', 'Date Hired', 
        'Status'
    ])
    
    for emp in employees:
        try:
            profile = emp.employee_profile
            emp_id = profile.employee_id or ''
            phone = profile.phone_number or ''
            dept = profile.department or ''
            job_title = profile.job_title or ''
            emp_type = profile.employment_type or ''
            date_hired = profile.date_hired or ''
        except:
            emp_id = phone = dept = job_title = emp_type = date_hired = ''
        
        writer.writerow([
            emp_id,
            emp.first_name,
            emp.last_name,
            emp.email,
            phone,
            dept,
            job_title,
            emp_type,
            date_hired,
            'Active' if emp.is_active else 'Inactive'
        ])
    
    return response


@login_required
def export_attendance_report(request):
    """Export attendance report to CSV"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    from attendance.models import Attendance
    
    # Get employees
    if request.user.role == 'ADMINISTRATOR':
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        employees = User.objects.filter(company=request.user.company, role='EMPLOYEE')
    
    # Get attendance records (last 30 days)
    from datetime import timedelta
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    attendance_records = Attendance.objects.filter(
        employee__in=employees,
        date__range=[start_date, end_date]
    ).select_related('employee', 'employee__employee_profile').order_by('-date', 'employee__last_name')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Employee ID', 'Employee Name', 'Department', 
        'Check In', 'Check Out', 'Status', 'Late', 'Hours Worked', 'Notes'
    ])
    
    for record in attendance_records:
        try:
            emp_id = record.employee.employee_profile.employee_id or ''
            dept = record.employee.employee_profile.department or ''
        except:
            emp_id = dept = ''
        
        writer.writerow([
            record.date,
            emp_id,
            record.employee.get_full_name(),
            dept,
            record.check_in_time or '',
            record.check_out_time or '',
            record.status,
            'Yes' if record.is_late else 'No',
            record.hours_worked or '',
            record.notes or ''
        ])
    
    return response


@login_required
def export_leave_report(request):
    """Export leave report to CSV"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    from attendance.models import LeaveRequest
    
    # Get employees
    if request.user.role == 'ADMINISTRATOR':
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        employees = User.objects.filter(company=request.user.company, role='EMPLOYEE')
    
    leave_requests = LeaveRequest.objects.filter(
        employee__in=employees
    ).select_related('employee', 'employee__employee_profile', 'approved_by').order_by('-created_at')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leave_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee ID', 'Employee Name', 'Department', 'Leave Type', 
        'Start Date', 'End Date', 'Total Days', 'Status', 'Reason', 
        'Approved By', 'Created Date'
    ])
    
    for leave in leave_requests:
        try:
            emp_id = leave.employee.employee_profile.employee_id or ''
            dept = leave.employee.employee_profile.department or ''
        except:
            emp_id = dept = ''
        
        writer.writerow([
            emp_id,
            leave.employee.get_full_name(),
            dept,
            leave.leave_type,
            leave.start_date,
            leave.end_date,
            leave.total_days,
            leave.status,
            leave.reason or '',
            leave.approved_by.get_full_name() if leave.approved_by else '',
            leave.created_at.strftime('%Y-%m-%d')
        ])
    
    return response


@login_required
def export_documents_report(request):
    """Export documents report to CSV"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    from documents.models import EmployeeDocument
    
    # Get employees
    if request.user.role == 'ADMINISTRATOR':
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        employees = User.objects.filter(company=request.user.company, role='EMPLOYEE')
    
    documents = EmployeeDocument.objects.filter(
        employee__in=employees
    ).select_related('employee', 'employee__employee_profile', 'uploaded_by', 'approved_by').order_by('-created_at')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="documents_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee ID', 'Employee Name', 'Document Type', 'Title', 
        'Status', 'Uploaded Date', 'Uploaded By', 'Approved By', 
        'Expiry Date', 'File Size (KB)'
    ])
    
    for doc in documents:
        try:
            emp_id = doc.employee.employee_profile.employee_id or ''
        except:
            emp_id = ''
        
        file_size = doc.file_size / 1024 if doc.file_size else 0
        writer.writerow([
            emp_id,
            doc.employee.get_full_name(),
            doc.get_document_type_display(),
            doc.title,
            doc.status,
            doc.created_at.strftime('%Y-%m-%d'),
            doc.uploaded_by.get_full_name() if doc.uploaded_by else '',
            doc.approved_by.get_full_name() if doc.approved_by else '',
            doc.expiry_date or '',
            f'{file_size:.2f}'
        ])
    
    return response


@login_required
def export_assets_report(request):
    """Export assets report to CSV"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import csv
    from django.http import HttpResponse
    
    try:
        from assets.models import EmployeeAsset
        
        # Get employees
        if request.user.role == 'ADMINISTRATOR':
            employees = User.objects.filter(role='EMPLOYEE')
        else:
            employees = User.objects.filter(company=request.user.company, role='EMPLOYEE')
        
        assets = EmployeeAsset.objects.filter(
            Q(employee__in=employees) | Q(employee__isnull=True)
        ).select_related('employee', 'assigned_by', 'category').order_by('-assigned_date')
        
        # Create CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="assets_report_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Asset Tag', 'Asset Name', 'Type', 'Serial Number', 'Brand', 'Model',
            'Assigned To', 'Employee ID', 'Status', 'Condition', 
            'Assigned Date', 'Days With Employee', 'Purchase Date', 'Purchase Price'
        ])
        
        for asset in assets:
            if asset.employee:
                try:
                    emp_id = asset.employee.employee_profile.employee_id or ''
                except:
                    emp_id = ''
                emp_name = asset.employee.get_full_name()
            else:
                emp_id = ''
                emp_name = 'Unassigned'
            
            writer.writerow([
                asset.asset_tag,
                asset.name,
                asset.get_asset_type_display(),
                asset.serial_number or '',
                asset.brand or '',
                asset.model or '',
                emp_name,
                emp_id,
                asset.get_status_display(),
                asset.get_condition_display(),
                asset.assigned_date or '',
                asset.days_with_employee if asset.employee else '',
                asset.purchase_date or '',
                asset.purchase_price or ''
            ])
        
        return response
    except ImportError:
        return JsonResponse({'error': 'Assets module not available'}, status=404)


@login_required
def assets_management(request):
    """Assets management dashboard"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        from assets.models import EmployeeAsset, AssetCategory
    except ImportError:
        return render(request, 'ems/unauthorized.html', {'error': 'Assets module not available'})
    
    # Get employer's company
    if request.user.role == 'ADMINISTRATOR':
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        employees = User.objects.filter(company=request.user.company, role='EMPLOYEE')
    
    # Get all assets
    all_assets = EmployeeAsset.objects.filter(
        Q(employee__in=employees) | Q(employee__isnull=True)
    ).select_related('employee', 'assigned_by', 'category').order_by('-assigned_date')
    
    # Filter by status
    status_filter = request.GET.get('status', 'ALL')
    if status_filter and status_filter != 'ALL':
        all_assets = all_assets.filter(status=status_filter)
    
    # Filter by type
    type_filter = request.GET.get('type', 'ALL')
    if type_filter and type_filter != 'ALL':
        all_assets = all_assets.filter(asset_type=type_filter)
    
    # Search
    search = request.GET.get('search', '')
    if search:
        all_assets = all_assets.filter(
            Q(asset_tag__icontains=search) |
            Q(name__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search)
        )
    
    # Statistics
    total_assets = EmployeeAsset.objects.filter(
        Q(employee__in=employees) | Q(employee__isnull=True)
    ).count()
    assigned_assets = EmployeeAsset.objects.filter(employee__in=employees, status='ASSIGNED').count()
    available_assets = EmployeeAsset.objects.filter(employee__isnull=True, status='AVAILABLE').count()
    in_repair = EmployeeAsset.objects.filter(status='IN_REPAIR').count()
    
    # Categories
    categories = AssetCategory.objects.all()
    
    context = {
        'assets': all_assets,
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'available_assets': available_assets,
        'in_repair': in_repair,
        'categories': categories,
        'asset_types': EmployeeAsset.AssetType.choices,
        'asset_statuses': EmployeeAsset.Status.choices,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search': search,
        'employees': employees
    }
    
    return render(request, 'ems/assets_management.html', context)


@login_required
def asset_create(request):
    """Create a new asset"""
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        from assets.models import EmployeeAsset, AssetCategory
        from accounts.models import CompanyDepartment
    except ImportError:
        return render(request, 'ems/unauthorized.html', {'error': 'Assets module not available'})
    
    if request.method == 'POST':
        try:
            # Create new asset
            asset = EmployeeAsset()
            asset.asset_tag = request.POST.get('asset_tag')
            asset.name = request.POST.get('name')
            asset.asset_type = request.POST.get('asset_type')
            asset.status = request.POST.get('status', 'AVAILABLE')
            asset.serial_number = request.POST.get('serial_number', '')
            asset.brand = request.POST.get('brand', '')
            asset.model = request.POST.get('model', '')
            asset.purchase_date = request.POST.get('purchase_date') or None
            asset.purchase_cost = request.POST.get('purchase_cost') or None
            asset.condition = request.POST.get('condition', 'NEW')
            asset.notes = request.POST.get('notes', '')
            
            # Department
            dept_id = request.POST.get('department')
            if dept_id:
                asset.department = CompanyDepartment.objects.get(id=dept_id)
            
            # Category
            category_id = request.POST.get('category')
            if category_id:
                asset.category = AssetCategory.objects.get(id=category_id)
            
            asset.save()
            messages.success(request, f'Asset "{asset.name}" created successfully!')
            return redirect('assets_management')
        except Exception as e:
            messages.error(request, f'Error creating asset: {str(e)}')
    
    # Get form data
    categories = AssetCategory.objects.all()
    departments = CompanyDepartment.objects.filter(company=request.user.company) if request.user.company else []
    
    context = {
        'categories': categories,
        'departments': departments,
        'asset_types': EmployeeAsset.AssetType.choices,
        'asset_statuses': EmployeeAsset.Status.choices,
        'asset_conditions': EmployeeAsset.Condition.choices,
    }
    
    return render(request, 'ems/asset_create.html', context)


@login_required
def approval_center(request):
    """Centralized approval center for all pending items"""
    if not _has_hr_access(request.user):
        return render(request, 'ems/unauthorized.html')
    
    from documents.models import EmployeeDocument
    from attendance.models import LeaveRequest
    from datetime import date, timedelta
    
    today = date.today()
    next_30_days = today + timedelta(days=30)
    next_60_days = today + timedelta(days=60)
    
    # Get employer's company
    if request.user.role == 'ADMINISTRATOR':
        company = None
        employees = User.objects.filter(role='EMPLOYEE')
    else:
        company = request.user.company
        employees = User.objects.filter(company=company, role='EMPLOYEE')
    
    # Pending Documents
    pending_documents = EmployeeDocument.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).select_related('employee', 'uploaded_by').order_by('-created_at')[:20]
    
    # Pending Leave Requests
    pending_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        status='PENDING'
    ).select_related('employee').order_by('-created_at')[:20]
    
    # Contract Expiries (next 60 days)
    expiring_contracts = []
    for emp in employees.select_related('employee_profile'):
        try:
            profile = emp.employee_profile
            if profile.employment_type == 'CONTRACT' and profile.contract_end_date:
                if today <= profile.contract_end_date <= next_60_days:
                    days_until = (profile.contract_end_date - today).days
                    expiring_contracts.append({
                        'employee': emp,
                        'end_date': profile.contract_end_date,
                        'days_until': days_until,
                        'is_critical': days_until <= 30
                    })
        except:
            # Skip employees without profiles
            continue
    
    # Probation Endings (next 60 days)
    ending_probations = []
    for emp in employees.select_related('employee_profile'):
        try:
            profile = emp.employee_profile
            if profile.employment_type == 'PROBATION' and profile.probation_end_date:
                if today <= profile.probation_end_date <= next_60_days:
                    days_until = (profile.probation_end_date - today).days
                    ending_probations.append({
                        'employee': emp,
                        'end_date': profile.probation_end_date,
                        'days_until': days_until,
                        'is_critical': days_until <= 30
                    })
        except:
            # Skip employees without profiles
            continue
    
    # Temporary Contract Endings (next 60 days)
    ending_temporary = []
    for emp in employees.select_related('employee_profile'):
        try:
            profile = emp.employee_profile
            if profile.employment_type == 'TEMPORARY' and profile.temporary_end_date:
                if today <= profile.temporary_end_date <= next_60_days:
                    days_until = (profile.temporary_end_date - today).days
                    ending_temporary.append({
                        'employee': emp,
                        'end_date': profile.temporary_end_date,
                        'days_until': days_until,
                        'is_critical': days_until <= 30
                    })
        except:
            # Skip employees without profiles
            continue
    
    # Sort by days until expiry
    expiring_contracts.sort(key=lambda x: x['days_until'])
    ending_probations.sort(key=lambda x: x['days_until'])
    ending_temporary.sort(key=lambda x: x['days_until'])
    
    # Summary counts
    summary = {
        'pending_documents': pending_documents.count(),
        'pending_leaves': pending_leaves.count(),
        'expiring_contracts': len(expiring_contracts),
        'ending_probations': len(ending_probations),
        'ending_temporary': len(ending_temporary),
        'total_pending': pending_documents.count() + pending_leaves.count() + len(expiring_contracts) + len(ending_probations) + len(ending_temporary)
    }
    
    context = {
        'pending_documents': pending_documents,
        'pending_leaves': pending_leaves,
        'expiring_contracts': expiring_contracts,
        'ending_probations': ending_probations,
        'ending_temporary': ending_temporary,
        'summary': summary,
        'today': today
    }
    
    return render(request, 'ems/approval_center.html', context)


@login_required
def user_management(request):
    """User management dashboard for System Superadmin"""
    if not request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')

    from accounts.models import Company, User
    from datetime import date

    today = date.today()

    # Get all users grouped by role
    super_admins = User.objects.filter(role='SUPERADMIN')
    company_admins = User.objects.filter(role='ADMINISTRATOR')
    hr_managers = User.objects.filter(role='HR_MANAGER')
    employees = User.objects.filter(role='EMPLOYEE')

    # Get companies for context
    companies = Company.objects.all()

    # Recent user registrations (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    recent_users = User.objects.filter(date_joined__gte=thirty_days_ago).order_by('-date_joined')

    # Active vs inactive users
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()

    context = {
        'user': request.user,
        'super_admins': super_admins,
        'company_admins': company_admins,
        'hr_managers': hr_managers,
        'employees': employees,
        'companies': companies,
        'recent_users': recent_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'total_users': User.objects.count(),
        'today_date': today.strftime('%Y-%m-%d'),
    }

    return render(request, 'ems/user_management.html', context)


@login_required
def documents_list(request):
    """Document management for employees and employers"""
    from documents.models import EmployeeDocument, DocumentCategory
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    user = request.user
    
    # Determine company
    company = None
    if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        if user.role == 'ADMINISTRATOR':
            company = getattr(user, 'company', None)
        else:
            company = getattr(getattr(user, 'employer_profile', None), 'company', None) or getattr(user, 'company', None)
    elif user.role == 'EMPLOYEE':
        company = getattr(user, 'company', None)
    
    # Filter documents based on role
    if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        # Employers see all employee documents in their company
        employee_documents = EmployeeDocument.objects.filter(
            employee__company=company
        ).select_related('employee', 'category', 'uploaded_by').order_by('-created_at')
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            from django.db.models import Q
            employee_documents = employee_documents.filter(
                Q(title__icontains=search_query) |
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__email__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by status if provided
        status_filter = request.GET.get('status', '')
        if status_filter:
            employee_documents = employee_documents.filter(status=status_filter)
            
        # Filter by document type if provided
        type_filter = request.GET.get('type', '')
        if type_filter:
            employee_documents = employee_documents.filter(document_type=type_filter)
        
        # Filter by category
        category_filter = request.GET.get('category', '')
        if category_filter:
            employee_documents = employee_documents.filter(category_id=category_filter)
        
        # Filter by expiry status
        expiry_filter = request.GET.get('expiry', '')
        from datetime import date, timedelta
        today = date.today()
        if expiry_filter == 'expired':
            employee_documents = employee_documents.filter(expiry_date__lt=today)
        elif expiry_filter == 'expiring_soon':
            # Expiring within 30 days
            employee_documents = employee_documents.filter(
                expiry_date__gte=today,
                expiry_date__lte=today + timedelta(days=30)
            )
            
    elif user.role == 'EMPLOYEE':
        # Employees see only their own documents
        employee_documents = EmployeeDocument.objects.filter(
            employee=user
        ).select_related('category', 'uploaded_by', 'approved_by').order_by('-created_at')
        
        search_query = request.GET.get('search', '').strip()
        if search_query:
            from django.db.models import Q
            employee_documents = employee_documents.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
    else:
        employee_documents = EmployeeDocument.objects.none()
        search_query = ''
    
    # Get categories and document types for filters
    categories = DocumentCategory.objects.all()
    
    # Calculate statistics for employers/admins
    if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        all_docs = EmployeeDocument.objects.filter(employee__company=company)
        total_documents = all_docs.count()
        pending_count = all_docs.filter(status=EmployeeDocument.Status.PENDING).count()
        approved_count = all_docs.filter(status=EmployeeDocument.Status.APPROVED).count()
        rejected_count = all_docs.filter(status=EmployeeDocument.Status.REJECTED).count()
        
        # Expiry statistics
        from datetime import date, timedelta
        today = date.today()
        expired_count = all_docs.filter(expiry_date__lt=today).count()
        expiring_soon_count = all_docs.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30)
        ).count()
    else:
        total_documents = employee_documents.count()
        pending_count = employee_documents.filter(status=EmployeeDocument.Status.PENDING).count()
        approved_count = employee_documents.filter(status=EmployeeDocument.Status.APPROVED).count()
        rejected_count = employee_documents.filter(status=EmployeeDocument.Status.REJECTED).count()
        expired_count = 0
        expiring_soon_count = 0
    
    # Determine which base template to use
    if user.role == 'EMPLOYEE':
        base_template = 'ems/base_employee.html'
    else:
        base_template = 'ems/base_employer.html'
    
    context = {
        'user': user,
        'company': company,
        'base_template': base_template,
        'employee_documents': employee_documents,
        'categories': categories,
        'document_types': EmployeeDocument.DocumentType.choices,
        'status_choices': EmployeeDocument.Status.choices,
        'status_filter': status_filter if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] else '',
        'type_filter': type_filter if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] else '',
        'category_filter': category_filter if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] else '',
        'expiry_filter': expiry_filter if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] else '',
        'search_query': search_query,
        'total_documents': total_documents,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
    }
    
    return render(request, 'ems/documents.html', context)

@login_required
def document_upload(request):
    """Upload document for employee"""
    from documents.models import EmployeeDocument, DocumentCategory
    from django.core.files.storage import default_storage
    
    if request.method == 'POST':
        title = request.POST.get('title')
        document_type = request.POST.get('document_type')
        category_id = request.POST.get('category')
        description = request.POST.get('description', '')
        expiry_date = request.POST.get('expiry_date') or None
        is_confidential = request.POST.get('is_confidential') == 'on'
        file = request.FILES.get('file')
        
        # Determine employee
        if request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
            employee_id = request.POST.get('employee')
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                employee = User.objects.get(id=employee_id, role='EMPLOYEE')
            except User.DoesNotExist:
                messages.error(request, 'Employee not found.')
                return redirect('documents_list')
        else:
            employee = request.user
        
        if not file:
            messages.error(request, 'Please select a file to upload.')
            return redirect('documents_list')
        
        try:
            category = DocumentCategory.objects.get(id=category_id) if category_id else None
            
            doc = EmployeeDocument.objects.create(
                employee=employee,
                category=category,
                document_type=document_type,
                title=title,
                description=description,
                file=file,
                expiry_date=expiry_date,
                is_confidential=is_confidential,
                uploaded_by=request.user,
                status=EmployeeDocument.Status.PENDING
            )
            messages.success(request, 'Document uploaded successfully!')
        except Exception as e:
            messages.error(request, f'Error uploading document: {str(e)}')
    
    return redirect('documents_list')

@login_required
def document_download(request, document_id):
    """Download document with access logging"""
    from documents.models import EmployeeDocument, DocumentAccessLog
    from django.http import FileResponse, Http404
    import os
    
    try:
        doc = EmployeeDocument.objects.select_related('employee').get(id=document_id)
        
        # Check permissions
        if request.user.role == 'EMPLOYEE':
            if doc.employee != request.user:
                messages.error(request, 'You do not have permission to access this document.')
                return redirect('documents_list')
        elif request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
            if doc.employee.company != company:
                messages.error(request, 'You do not have permission to access this document.')
                return redirect('documents_list')
        else:
            messages.error(request, 'You do not have permission to access this document.')
            return redirect('documents_list')
        
        # Log access
        DocumentAccessLog.objects.create(
            document=doc,
            user=request.user,
            access_type=DocumentAccessLog.AccessType.DOWNLOAD,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Return file
        if os.path.exists(doc.file.path):
            response = FileResponse(doc.file.open('rb'), as_attachment=True, filename=doc.original_filename)
            return response
        else:
            raise Http404('File not found')
            
    except EmployeeDocument.DoesNotExist:
        raise Http404('Document not found')

@login_required
def document_approve(request, document_id):
    """Approve document"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')
    
    from documents.models import EmployeeDocument, DocumentAccessLog
    from django.utils import timezone
    
    try:
        doc = EmployeeDocument.objects.get(id=document_id)
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        
        if doc.employee.company != company:
            messages.error(request, 'You do not have permission to approve this document.')
            return redirect('documents_list')
        
        doc.status = EmployeeDocument.Status.APPROVED
        doc.approved_by = request.user
        doc.approved_at = timezone.now()
        doc.save()
        
        # Log access
        DocumentAccessLog.objects.create(
            document=doc,
            user=request.user,
            access_type=DocumentAccessLog.AccessType.APPROVE,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        messages.success(request, 'Document approved successfully!')
    except EmployeeDocument.DoesNotExist:
        messages.error(request, 'Document not found.')
    
    return redirect('documents_list')


@login_required
def document_reject(request, document_id):
    """Reject document"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')

    from documents.models import EmployeeDocument, DocumentAccessLog

    if request.method == 'POST':
        reason = request.POST.get('reason', '')

        try:
            doc = EmployeeDocument.objects.get(id=document_id)
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)

            if doc.employee.company != company:
                messages.error(request, 'You do not have permission to reject this document.')
                return redirect('documents_list')

            doc.status = EmployeeDocument.Status.REJECTED
            doc.rejection_reason = reason
            doc.save()

            # Log access
            DocumentAccessLog.objects.create(
                document=doc,
                user=request.user,
                access_type=DocumentAccessLog.AccessType.REJECT,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

            messages.success(request, 'Document rejected.')
        except EmployeeDocument.DoesNotExist:
            messages.error(request, 'Document not found.')

    return redirect('documents_list')

@login_required
def bulk_approve_documents(request):
    """Bulk approve documents"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    import json
    from documents.models import EmployeeDocument, DocumentAccessLog
    
    try:
        data = json.loads(request.body)
        doc_ids = data.get('doc_ids', [])
        
        if not doc_ids:
            return JsonResponse({'success': False, 'error': 'No documents selected'})
        
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        approved_count = 0
        
        for doc_id in doc_ids:
            try:
                doc = EmployeeDocument.objects.get(id=doc_id, employee__company=company)
                doc.status = EmployeeDocument.Status.APPROVED
                doc.approved_by = request.user
                doc.approved_at = timezone.now()
                doc.save()
                
                # Log access
                DocumentAccessLog.objects.create(
                    document=doc,
                    user=request.user,
                    access_type=DocumentAccessLog.AccessType.APPROVE,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                approved_count += 1
            except EmployeeDocument.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully approved {approved_count} document(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def bulk_download_documents(request):
    """Bulk download documents as ZIP"""
    if request.method != 'POST':
        return redirect('documents_list')
    
    from documents.models import EmployeeDocument, DocumentAccessLog
    import zipfile
    from io import BytesIO
    from django.http import HttpResponse
    
    doc_ids = request.POST.getlist('doc_ids')
    
    if not doc_ids:
        messages.error(request, 'No documents selected')
        return redirect('documents_list')
    
    company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for doc_id in doc_ids:
            try:
                if request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
                    doc = EmployeeDocument.objects.get(id=doc_id, employee__company=company)
                else:
                    doc = EmployeeDocument.objects.get(id=doc_id, employee=request.user)
                
                # Add file to ZIP
                file_path = doc.file.path
                arc_name = f"{doc.employee.get_full_name()}_{doc.title}_{doc.id}{doc.file.name[doc.file.name.rfind('.'):]}"
                zip_file.write(file_path, arc_name)
                
                # Log access
                DocumentAccessLog.objects.create(
                    document=doc,
                    user=request.user,
                    access_type=DocumentAccessLog.AccessType.DOWNLOAD,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except (EmployeeDocument.DoesNotExist, FileNotFoundError):
                continue
    
    # Prepare response
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="documents.zip"'
    
    return response


@login_required
def employee_profile_picture_upload_redirect(request, employee_id):
    """Upload profile picture for an employee (form-based with redirect)."""
    if request.method != 'POST':
        return redirect('employer_edit_employee', employee_id=employee_id)

    employee = get_object_or_404(User, id=employee_id)

    # Permission check
    allowed_roles = {'EMPLOYER_ADMIN', 'ADMINISTRATOR'}
    requester_role = getattr(request.user, 'role', '')
    is_self_upload = request.user.id == employee.id

    if not (is_self_upload or requester_role in allowed_roles):
        messages.error(request, 'You do not have permission to update this profile picture.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    if requester_role in allowed_roles and employee.role == 'EMPLOYEE':
        requester_company = (
            getattr(request.user, 'company', None)
            or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        )
        employee_company = getattr(employee, 'company', None)
        if requester_company and employee_company and requester_company != employee_company:
            messages.error(request, 'You do not have permission to update this employee\'s profile picture.')
            return redirect('employer_edit_employee', employee_id=employee_id)

    profile_picture = request.FILES.get('profile_picture')

    if not profile_picture:
        messages.error(request, 'Please select an image file.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    # Validate file type
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    file_ext = os.path.splitext(profile_picture.name)[1].lower()
    if file_ext not in valid_extensions:
        messages.error(request, 'Invalid file type. Please upload a JPG, PNG, GIF, or WEBP image.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    # Validate file size (max 5MB)
    if profile_picture.size > 5 * 1024 * 1024:
        messages.error(request, 'File size too large. Maximum size is 5MB.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    try:
        # Delete old profile picture if exists
        if employee.profile_picture:
            old_picture_path = employee.profile_picture.path
            if os.path.exists(old_picture_path):
                os.remove(old_picture_path)

        employee.profile_picture = profile_picture
        employee.save()
        messages.success(request, 'Profile picture updated successfully!')
    except Exception as exc:
        messages.error(request, f'Error uploading profile picture: {str(exc)}')

    return redirect('employer_edit_employee', employee_id=employee_id)


@login_required
def employee_document_upload(request, employee_id):
    """Upload a document for a specific employee from the edit page."""
    if request.method != 'POST':
        return redirect('employer_edit_employee', employee_id=employee_id)

    employee = get_object_or_404(User, id=employee_id, role='EMPLOYEE')

    allowed_roles = {'EMPLOYER_ADMIN', 'ADMINISTRATOR'}
    requester_role = getattr(request.user, 'role', '')
    is_self_upload = requester_role == 'EMPLOYEE' and request.user.id == employee.id

    if not (is_self_upload or requester_role in allowed_roles):
        return render(request, 'ems/unauthorized.html')

    if requester_role in allowed_roles:
        requester_company = (
            getattr(request.user, 'company', None)
            or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        )
        employee_company = getattr(employee, 'company', None)
        if requester_company and employee_company and requester_company != employee_company:
            messages.error(request, 'You do not have permission to manage this employee\'s documents.')
            return redirect('employer_edit_employee', employee_id=employee_id)

    title = (request.POST.get('title') or '').strip()
    description = (request.POST.get('description') or '').strip()
    expiry_value = request.POST.get('expiry_date') or None
    is_confidential = request.POST.get('is_confidential') == 'on'
    category_id = request.POST.get('category_id')
    document_type_input = request.POST.get('document_type') or ''
    upload_file = request.FILES.get('file')

    if not title or not upload_file:
        messages.error(request, 'Title and file are required to upload a document.')
        return redirect('employer_edit_employee', employee_id=employee_id)

    category = None
    if category_id:
        category = DocumentCategory.objects.filter(id=category_id).first()
        if category is None:
            messages.error(request, 'Selected category was not found.')
            return redirect('employer_edit_employee', employee_id=employee_id)

    valid_types = {value for value, _ in EmployeeDocument.DocumentType.choices}
    if document_type_input in valid_types:
        document_type = document_type_input
    elif category and category.default_document_type in valid_types and category.default_document_type:
        document_type = category.default_document_type
    else:
        document_type = EmployeeDocument.DocumentType.OTHER

    expiry_date = None
    if expiry_value:
        try:
            expiry_date = datetime.strptime(expiry_value, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid expiry date format. Use YYYY-MM-DD.')
            return redirect('employer_edit_employee', employee_id=employee_id)

    next_version = (
        EmployeeDocument.objects.filter(employee=employee, title=title)
        .aggregate(max_version=Max('version'))
        .get('max_version')
        or 0
    ) + 1

    try:
        document = EmployeeDocument.objects.create(
            employee=employee,
            category=category,
            document_type=document_type,
            title=title,
            description=description,
            file=upload_file,
            expiry_date=expiry_date,
            is_confidential=is_confidential,
            uploaded_by=request.user,
            status=EmployeeDocument.Status.PENDING,
            version=next_version,
        )

        DocumentAccessLog.objects.create(
            document=document,
            user=request.user,
            access_type=DocumentAccessLog.AccessType.UPLOAD,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        messages.success(request, 'Document uploaded successfully and is pending review.')
    except Exception as exc:
        messages.error(request, f'Error uploading document: {str(exc)}')

    return redirect('employer_edit_employee', employee_id=employee_id)


@login_required
def performance_reviews_list(request):
    """List performance reviews for employers and employees"""
    from performance.models import PerformanceReview
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Count
    from datetime import date
    import csv
    from django.http import HttpResponse
    
    User = get_user_model()
    user = request.user
    
    # Determine company
    company = None
    if user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        company = getattr(user, 'company', None) or getattr(getattr(user, 'employer_profile', None), 'company', None)
        
        # Get all reviews for statistics
        all_reviews = PerformanceReview.objects.filter(employee__company=company)
        
        # Calculate statistics
        total_reviews = all_reviews.count()
        draft_count = all_reviews.filter(status='DRAFT').count()
        completed_count = all_reviews.filter(status='COMPLETED').count()
        approved_count = all_reviews.filter(status='APPROVED').count()
        
        # Employers see all reviews in their company
        reviews = all_reviews.select_related('employee', 'employee__employee_profile', 'reviewer').order_by('-review_date')
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            reviews = reviews.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(title__icontains=search_query) |
                Q(employee__email__icontains=search_query)
            )
        
        # Filter by status
        status_filter = request.GET.get('status', '')
        if status_filter:
            reviews = reviews.filter(status=status_filter)
        
        # Filter by review type
        review_type_filter = request.GET.get('review_type', '')
        if review_type_filter:
            reviews = reviews.filter(review_type=review_type_filter)
        
        # Filter by rating
        rating_filter = request.GET.get('rating', '')
        if rating_filter:
            reviews = reviews.filter(overall_rating=rating_filter)
        
        # Date range filter
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        if date_from:
            reviews = reviews.filter(review_date__gte=date_from)
        if date_to:
            reviews = reviews.filter(review_date__lte=date_to)
        
        # Get employees for create review
        employees = User.objects.filter(company=company, role='EMPLOYEE')
        
        # CSV Export
        if request.GET.get('format') == 'csv':
            filename = f"performance_reviews_{date.today().strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(response)
            
            writer.writerow(['Employee', 'Position', 'Review Type', 'Period Start', 'Period End', 'Review Date', 'Rating', 'Status', 'Reviewer'])
            
            for review in reviews:
                writer.writerow([
                    review.employee.get_full_name(),
                    review.employee.employee_profile.job_title if hasattr(review.employee, 'employee_profile') and review.employee.employee_profile else 'N/A',
                    review.get_review_type_display(),
                    review.review_period_start.strftime('%Y-%m-%d'),
                    review.review_period_end.strftime('%Y-%m-%d'),
                    review.review_date.strftime('%Y-%m-%d'),
                    review.get_overall_rating_display(),
                    review.get_status_display(),
                    review.reviewer.get_full_name() if review.reviewer else 'N/A'
                ])
            
            return response
            
    elif user.role == 'EMPLOYEE':
        # Employees see only their own reviews
        reviews = PerformanceReview.objects.filter(
            employee=user
        ).select_related('reviewer').order_by('-review_date')
        status_filter = ''
        search_query = ''
        review_type_filter = ''
        rating_filter = ''
        date_from = ''
        date_to = ''
        total_reviews = reviews.count()
        draft_count = reviews.filter(status='DRAFT').count()
        completed_count = reviews.filter(status='COMPLETED').count()
        approved_count = reviews.filter(status='APPROVED').count()
        employees = User.objects.none()
    else:
        reviews = PerformanceReview.objects.none()
        status_filter = ''
        search_query = ''
        review_type_filter = ''
        rating_filter = ''
        date_from = ''
        date_to = ''
        total_reviews = 0
        draft_count = 0
        completed_count = 0
        approved_count = 0
        employees = User.objects.none()
    
    context = {
        'user': user,
        'company': company,
        'reviews': reviews,
        'status_filter': status_filter,
        'review_types': PerformanceReview.ReviewType.choices,
        'overall_ratings': PerformanceReview.OverallRating.choices,
        'status_choices': [
            ('DRAFT', 'Draft'),
            ('SUBMITTED', 'Submitted'),
            ('UNDER_REVIEW', 'Under Review'),
            ('COMPLETED', 'Completed'),
            ('APPROVED', 'Approved')
        ],
        'search_query': search_query,
        'review_type_filter': review_type_filter,
        'rating_filter': rating_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_reviews': total_reviews,
        'draft_count': draft_count,
        'completed_count': completed_count,
        'approved_count': approved_count,
        'employees': employees,
    }
    
    return render(request, 'ems/performance_reviews.html', context)

@login_required
def performance_review_create(request):
    """Create new performance review"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')
    
    from performance.models import PerformanceReview
    from django.contrib.auth import get_user_model
    from datetime import datetime
    
    User = get_user_model()
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        review_type = request.POST.get('review_type')
        title = request.POST.get('title')
        review_period_start = request.POST.get('review_period_start')
        review_period_end = request.POST.get('review_period_end')
        review_date = request.POST.get('review_date')
        
        try:
            employee = User.objects.get(id=employee_id, role='EMPLOYEE')
            
            review = PerformanceReview.objects.create(
                employee=employee,
                reviewer=request.user,
                review_type=review_type,
                title=title,
                review_period_start=datetime.strptime(review_period_start, '%Y-%m-%d').date(),
                review_period_end=datetime.strptime(review_period_end, '%Y-%m-%d').date(),
                review_date=datetime.strptime(review_date, '%Y-%m-%d').date(),
                status='DRAFT'
            )
            messages.success(request, 'Performance review created successfully!')
            return redirect('performance_review_detail', review_id=review.id)
        except Exception as e:
            messages.error(request, f'Error creating review: {str(e)}')
    
    return redirect('performance_reviews_list')

@login_required
def performance_review_detail(request, review_id):
    """View and edit performance review"""
    from performance.models import PerformanceReview
    
    try:
        if request.user.role == 'EMPLOYEE':
            review = PerformanceReview.objects.select_related('employee', 'reviewer').prefetch_related('goals', 'metrics', 'feedback').get(
                id=review_id, employee=request.user
            )
        elif request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
            review = PerformanceReview.objects.select_related('employee', 'reviewer').prefetch_related('goals', 'metrics', 'feedback').get(
                id=review_id, employee__company=company
            )
        else:
            return render(request, 'ems/unauthorized.html')
        
        if request.method == 'POST':
            # Update review
            review.overall_rating = request.POST.get('overall_rating', review.overall_rating)
            review.achievements = request.POST.get('achievements', '')
            review.strengths = request.POST.get('strengths', '')
            review.areas_for_improvement = request.POST.get('areas_for_improvement', '')
            review.development_plan = request.POST.get('development_plan', '')
            review.goals_next_period = request.POST.get('goals_next_period', '')
            review.additional_comments = request.POST.get('additional_comments', '')
            review.status = request.POST.get('status', review.status)
            review.save()
            messages.success(request, 'Review updated successfully!')
            return redirect('performance_review_detail', review_id=review.id)
        
        context = {
            'review': review,
            'overall_ratings': PerformanceReview.OverallRating.choices,
        }
        return render(request, 'ems/performance_review_detail.html', context)
        
    except PerformanceReview.DoesNotExist:
        messages.error(request, 'Review not found.')
        return redirect('performance_reviews_list')

@login_required
def payroll_list(request):
    """List payroll records"""
    from payroll.models import Payroll, SalaryStructure, PayrollDeduction
    from accounts.models import PayrollDeductionSettings
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Sum
    from datetime import date, datetime
    import csv
    from django.http import HttpResponse
    from decimal import Decimal
    
    User = get_user_model()
    
    # Handle payroll generation POST request
    if request.method == 'POST' and request.POST.get('action') == 'generate_payroll':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied. Only Finance/Accounting staff can generate payroll.')
            return redirect('payroll_list')
        
        try:
            period_start = datetime.strptime(request.POST.get('period_start'), '%Y-%m-%d').date()
            period_end = datetime.strptime(request.POST.get('period_end'), '%Y-%m-%d').date()
            pay_date = datetime.strptime(request.POST.get('pay_date'), '%Y-%m-%d').date()
            employee_selection = request.POST.get('employee_selection')
            
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
            
            # Get employees to generate payroll for
            if employee_selection == 'all':
                employees = User.objects.filter(company=company, role='EMPLOYEE', is_active=True)
            else:
                selected_ids = request.POST.getlist('selected_employees')
                employees = User.objects.filter(id__in=selected_ids, company=company, role='EMPLOYEE')
            
            # Get deduction settings
            try:
                deduction_settings = PayrollDeductionSettings.objects.get(company=company)
            except PayrollDeductionSettings.DoesNotExist:
                deduction_settings = None
            
            generated_count = 0
            for employee in employees:
                # Check if payroll already exists for this period
                if Payroll.objects.filter(employee=employee, period_start=period_start, period_end=period_end).exists():
                    continue
                
                # Get salary structure
                try:
                    salary_structure = SalaryStructure.objects.filter(employee=employee, is_active=True).first()
                    if not salary_structure:
                        continue
                    
                    base_pay = salary_structure.base_salary
                    
                    # Calculate gratuity
                    gratuity = Decimal('0')
                    if deduction_settings and deduction_settings.gratuity_enabled:
                        gratuity = (base_pay * deduction_settings.gratuity_percentage / 100).quantize(Decimal('0.01'))
                    
                    # Calculate deductions
                    paye = Decimal('0')
                    napsa = Decimal('0')
                    nhima = Decimal('0')
                    
                    if deduction_settings:
                        # Calculate NAPSA
                        if deduction_settings.napsa_enabled:
                            napsa = (base_pay * deduction_settings.napsa_employee_percentage / 100).quantize(Decimal('0.01'))
                        
                        # Calculate NHIMA (now percentage-based)
                        if deduction_settings.nhima_enabled:
                            nhima = (base_pay * deduction_settings.nhima_employee_percentage / 100).quantize(Decimal('0.01'))
                        
                        # Calculate PAYE (simplified - on taxable income after NAPSA and NHIMA)
                        if deduction_settings.paye_enabled and deduction_settings.paye_tax_brackets:
                            taxable_income = base_pay - napsa - nhima
                            for bracket in deduction_settings.paye_tax_brackets:
                                if taxable_income > bracket.get('min', 0):
                                    taxable_amount = min(taxable_income, bracket.get('max', taxable_income)) - bracket.get('min', 0)
                                    paye += (taxable_amount * Decimal(str(bracket.get('rate', 0))) / 100).quantize(Decimal('0.01'))
                    
                    # Determine currency (use salary structure currency, or default from settings, or ZMW)
                    currency = salary_structure.currency if hasattr(salary_structure, 'currency') and salary_structure.currency else (deduction_settings.currency if deduction_settings else 'ZMW')
                    
                    # Create payroll
                    payroll = Payroll.objects.create(
                        employee=employee,
                        period_start=period_start,
                        period_end=period_end,
                        pay_date=pay_date,
                        base_pay=base_pay,
                        overtime_pay=Decimal('0'),
                        bonus=Decimal('0'),
                        commission=Decimal('0'),
                        allowances=Decimal('0'),
                        gratuity=gratuity,
                        tax=paye,
                        social_security=napsa,
                        insurance=nhima,
                        other_deductions=Decimal('0'),
                        currency=currency,
                        status=Payroll.Status.DRAFT
                    )
                    
                    # Create detailed deductions
                    if paye > 0:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type='PAYE',
                            amount=paye,
                            description='Income Tax',
                            is_statutory=True
                        )
                    if napsa > 0:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type='NAPSA',
                            amount=napsa,
                            description='Social Security Contribution',
                            is_statutory=True
                        )
                    if nhima > 0:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type='NHIMA',
                            amount=nhima,
                            description='Health Insurance Contribution',
                            is_statutory=True
                        )
                    
                    generated_count += 1
                    
                except Exception as e:
                    continue
            
            if generated_count > 0:
                messages.success(request, f'Successfully generated payroll for {generated_count} employee(s).')
            else:
                messages.warning(request, 'No payroll records were generated. They may already exist or employees may not have salary structures.')
            
            return redirect('payroll_list')
            
        except Exception as e:
            messages.error(request, f'Error generating payroll: {str(e)}')
            return redirect('payroll_list')
    
    # Handle manual payroll creation POST request
    if request.method == 'POST' and request.POST.get('action') == 'create_payroll':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied. Only Finance/Accounting staff can create payroll records.')
            return redirect('payroll_list')
        
        try:
            employee_id = request.POST.get('employee_id')
            employee = User.objects.get(id=employee_id)
            period_start = datetime.strptime(request.POST.get('period_start'), '%Y-%m-%d').date()
            period_end = datetime.strptime(request.POST.get('period_end'), '%Y-%m-%d').date()
            pay_date = datetime.strptime(request.POST.get('pay_date'), '%Y-%m-%d').date()
            
            # Check if payroll already exists
            if Payroll.objects.filter(employee=employee, period_start=period_start, period_end=period_end).exists():
                messages.error(request, 'Payroll record already exists for this employee and period.')
                return redirect('payroll_list')
            
            # Get form data
            base_pay = Decimal(request.POST.get('base_pay', '0'))
            overtime_pay = Decimal(request.POST.get('overtime_pay', '0'))
            bonus = Decimal(request.POST.get('bonus', '0'))
            commission = Decimal(request.POST.get('commission', '0'))
            allowances = Decimal(request.POST.get('allowances', '0'))
            gratuity = Decimal(request.POST.get('gratuity', '0'))
            
            tax = Decimal(request.POST.get('tax', '0'))
            social_security = Decimal(request.POST.get('social_security', '0'))
            insurance = Decimal(request.POST.get('insurance', '0'))
            late_deduction = Decimal(request.POST.get('late_deduction', '0'))
            absent_deduction = Decimal(request.POST.get('absent_deduction', '0'))
            other_deductions = Decimal(request.POST.get('other_deductions', '0'))
            
            currency = request.POST.get('currency', 'ZMW')
            notes = request.POST.get('notes', '')
            
            # Create payroll
            payroll = Payroll.objects.create(
                employee=employee,
                period_start=period_start,
                period_end=period_end,
                pay_date=pay_date,
                base_pay=base_pay,
                overtime_pay=overtime_pay,
                bonus=bonus,
                commission=commission,
                allowances=allowances,
                gratuity=gratuity,
                tax=tax,
                social_security=social_security,
                insurance=insurance,
                other_deductions=other_deductions + late_deduction + absent_deduction,
                currency=currency,
                notes=notes,
                status=Payroll.Status.DRAFT
            )
            
            # Create detailed deductions
            if tax > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='PAYE',
                    amount=tax,
                    description='Income Tax',
                    is_statutory=True
                )
            if social_security > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='NAPSA',
                    amount=social_security,
                    description='Social Security Contribution',
                    is_statutory=True
                )
            if insurance > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='NHIMA',
                    amount=insurance,
                    description='Health Insurance Contribution',
                    is_statutory=True
                )
            if late_deduction > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='LATE',
                    amount=late_deduction,
                    description='Late Arrival Deduction',
                    is_statutory=False
                )
            if absent_deduction > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='ABSENT',
                    amount=absent_deduction,
                    description='Absence Deduction',
                    is_statutory=False
                )
            if other_deductions > 0:
                PayrollDeduction.objects.create(
                    payroll=payroll,
                    deduction_type='OTHER',
                    amount=other_deductions,
                    description='Other Deductions',
                    is_statutory=False
                )
            
            messages.success(request, f'Payroll record created successfully for {employee.get_full_name()}.')
            return redirect('payroll_detail', payroll_id=payroll.id)
            
        except Exception as e:
            messages.error(request, f'Error creating payroll: {str(e)}')
            return redirect('payroll_list')
    
    # Handle payroll configuration update POST request
    if request.method == 'POST' and request.POST.get('action') == 'update_payroll_config':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied. Only Finance/Accounting staff can update payroll configuration.')
            return redirect('payroll_list')
        
        try:
            import json
            company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
            # For accountants, get their company
            if not company and hasattr(request.user, 'employee_profile'):
                company = request.user.company
            
            # Get or create payroll settings
            payroll_settings, created = PayrollDeductionSettings.objects.get_or_create(company=company)
            
            # Update PAYE settings
            payroll_settings.paye_enabled = request.POST.get('paye_enabled') == 'on'
            try:
                paye_brackets = request.POST.get('paye_tax_brackets', '[]')
                payroll_settings.paye_tax_brackets = json.loads(paye_brackets)
            except json.JSONDecodeError:
                messages.error(request, 'Invalid JSON format for PAYE tax brackets.')
                return redirect('payroll_list')
            
            # Update NAPSA settings
            payroll_settings.napsa_enabled = request.POST.get('napsa_enabled') == 'on'
            payroll_settings.napsa_employee_percentage = Decimal(request.POST.get('napsa_employee_percentage', '5.0'))
            payroll_settings.napsa_employer_percentage = Decimal(request.POST.get('napsa_employer_percentage', '5.0'))
            
            # Update NHIMA settings
            payroll_settings.nhima_enabled = request.POST.get('nhima_enabled') == 'on'
            payroll_settings.nhima_employee_percentage = Decimal(request.POST.get('nhima_employee_percentage', '1.0'))
            payroll_settings.nhima_employer_percentage = Decimal(request.POST.get('nhima_employer_percentage', '1.0'))
            
            # Update Late/Absent deduction settings
            payroll_settings.late_deduction_type = request.POST.get('late_deduction_type', 'PERCENTAGE')
            payroll_settings.late_deduction_percentage = Decimal(request.POST.get('late_deduction_percentage', '5.0'))
            payroll_settings.absent_deduction_type = request.POST.get('absent_deduction_type', 'DAILY_RATE')
            payroll_settings.absent_deduction_percentage = Decimal(request.POST.get('absent_deduction_percentage', '100.0'))
            payroll_settings.working_days_per_month = int(request.POST.get('working_days_per_month', '22'))
            
            # Update Gratuity settings
            payroll_settings.gratuity_enabled = request.POST.get('gratuity_enabled') == 'on'
            payroll_settings.gratuity_percentage = Decimal(request.POST.get('gratuity_percentage', '8.33'))
            payroll_settings.gratuity_eligibility_months = int(request.POST.get('gratuity_eligibility_months', '12'))
            
            # Update currency
            payroll_settings.currency = request.POST.get('default_currency', 'ZMW')
            
            payroll_settings.save()
            messages.success(request, 'Payroll configuration updated successfully.')
            return redirect('payroll_list')
            
        except Exception as e:
            messages.error(request, f'Error updating payroll configuration: {str(e)}')
            return redirect('payroll_list')
    
    # Handle CSV import POST request
    if request.method == 'POST' and request.POST.get('action') == 'import_csv':
        if not _has_payroll_access(request.user):
            messages.error(request, 'Permission denied. Only Finance/Accounting staff can import payroll.')
            return redirect('payroll_list')
        
        try:
            import csv as csv_module
            from io import TextIOWrapper
            
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, 'No CSV file uploaded.')
                return redirect('payroll_list')
            
            # Read CSV file
            decoded_file = TextIOWrapper(csv_file.file, encoding='utf-8')
            csv_reader = csv_module.DictReader(decoded_file)
            
            created_count = 0
            error_rows = []
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (1 is header)
                try:
                    employee_id = int(row['employee_id'])
                    employee = User.objects.get(id=employee_id)
                    period_start = datetime.strptime(row['period_start'], '%Y-%m-%d').date()
                    period_end = datetime.strptime(row['period_end'], '%Y-%m-%d').date()
                    pay_date = datetime.strptime(row['pay_date'], '%Y-%m-%d').date()
                    
                    # Check if payroll already exists
                    if Payroll.objects.filter(employee=employee, period_start=period_start, period_end=period_end).exists():
                        error_rows.append(f"Row {row_num}: Payroll already exists for {employee.get_full_name()}")
                        continue
                    
                    # Get values from CSV
                    base_pay = Decimal(row.get('base_pay', '0'))
                    overtime_pay = Decimal(row.get('overtime_pay', '0'))
                    bonus = Decimal(row.get('bonus', '0'))
                    commission = Decimal(row.get('commission', '0'))
                    allowances = Decimal(row.get('allowances', '0'))
                    gratuity = Decimal(row.get('gratuity', '0'))
                    
                    tax = Decimal(row.get('tax', '0'))
                    social_security = Decimal(row.get('napsa', '0'))
                    insurance = Decimal(row.get('nhima', '0'))
                    late_deduction = Decimal(row.get('late_deduction', '0'))
                    absent_deduction = Decimal(row.get('absent_deduction', '0'))
                    other_deductions = Decimal(row.get('other_deductions', '0'))
                    
                    currency = row.get('currency', 'ZMW')
                    notes = row.get('notes', '')
                    
                    # Create payroll
                    payroll = Payroll.objects.create(
                        employee=employee,
                        period_start=period_start,
                        period_end=period_end,
                        pay_date=pay_date,
                        base_pay=base_pay,
                        overtime_pay=overtime_pay,
                        bonus=bonus,
                        commission=commission,
                        allowances=allowances,
                        gratuity=gratuity,
                        tax=tax,
                        social_security=social_security,
                        insurance=insurance,
                        other_deductions=other_deductions + late_deduction + absent_deduction,
                        currency=currency,
                        notes=notes,
                        status=Payroll.Status.DRAFT
                    )
                    
                    # Create detailed deductions
                    if tax > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='PAYE', amount=tax, description='Income Tax', is_statutory=True)
                    if social_security > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='NAPSA', amount=social_security, description='Social Security', is_statutory=True)
                    if insurance > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='NHIMA', amount=insurance, description='Health Insurance', is_statutory=True)
                    if late_deduction > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='LATE', amount=late_deduction, description='Late Deduction', is_statutory=False)
                    if absent_deduction > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='ABSENT', amount=absent_deduction, description='Absence Deduction', is_statutory=False)
                    if other_deductions > 0:
                        PayrollDeduction.objects.create(payroll=payroll, deduction_type='OTHER', amount=other_deductions, description='Other Deductions', is_statutory=False)
                    
                    created_count += 1
                    
                except Exception as e:
                    error_rows.append(f"Row {row_num}: {str(e)}")
                    continue
            
            if created_count > 0:
                messages.success(request, f'Successfully imported {created_count} payroll record(s) from CSV.')
            if error_rows:
                messages.warning(request, f'Errors encountered: {", ".join(error_rows[:5])}{"..." if len(error_rows) > 5 else ""}')
            if created_count == 0 and not error_rows:
                messages.warning(request, 'No payroll records were imported.')
            
            return redirect('payroll_list')
            
        except Exception as e:
            messages.error(request, f'Error importing CSV: {str(e)}')
            return redirect('payroll_list')
    
    # Check payroll access permissions
    has_payroll_access = _has_payroll_access(request.user)
    
    if request.user.role == 'EMPLOYEE' and not has_payroll_access:
        # Regular employees can only see their own payroll
        payrolls = Payroll.objects.filter(employee=request.user).order_by('-period_end')
        
        # Employee statistics
        total_payrolls = payrolls.count()
        draft_count = payrolls.filter(status=Payroll.Status.DRAFT).count()
        approved_count = payrolls.filter(status=Payroll.Status.APPROVED).count()
        paid_count = payrolls.filter(status=Payroll.Status.PAID).count()
        total_earned = payrolls.filter(status=Payroll.Status.PAID).aggregate(total=Sum('net_pay'))['total'] or 0
        
        search_query = ''
        status_filter = ''
        date_from = ''
        date_to = ''
        company = None
        employees = User.objects.none()
        
    elif has_payroll_access:
        company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
        
        # Get all payrolls for statistics
        all_payrolls = Payroll.objects.filter(employee__company=company)
        
        # Calculate statistics
        total_payrolls = all_payrolls.count()
        draft_count = all_payrolls.filter(status=Payroll.Status.DRAFT).count()
        approved_count = all_payrolls.filter(status=Payroll.Status.APPROVED).count()
        paid_count = all_payrolls.filter(status=Payroll.Status.PAID).count()
        total_earned = all_payrolls.filter(status=Payroll.Status.PAID).aggregate(total=Sum('net_pay'))['total'] or 0
        
        payrolls = all_payrolls.select_related('employee', 'employee__employee_profile').order_by('-period_end')
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            payrolls = payrolls.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__email__icontains=search_query)
            )
        
        # Status filter
        status_filter = request.GET.get('status', '')
        if status_filter:
            payrolls = payrolls.filter(status=status_filter)
        
        # Date range filter
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        if date_from:
            payrolls = payrolls.filter(period_end__gte=date_from)
        if date_to:
            payrolls = payrolls.filter(period_end__lte=date_to)
        
        # Get employees for potential filtering
        employees = User.objects.filter(company=company, role='EMPLOYEE')
        
        # CSV Export
        if request.GET.get('format') == 'csv':
            filename = f"payroll_{date.today().strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(response)
            
            writer.writerow([
                'Employee', 'Position', 'Period Start', 'Period End', 'Pay Date',
                'Base Pay', 'Overtime', 'Bonus', 'Gross Pay', 'Deductions', 'Net Pay',
                'Status', 'Currency'
            ])
            
            for payroll in payrolls:
                writer.writerow([
                    payroll.employee.get_full_name(),
                    payroll.employee.employee_profile.job_title if hasattr(payroll.employee, 'employee_profile') and payroll.employee.employee_profile else 'N/A',
                    payroll.period_start.strftime('%Y-%m-%d'),
                    payroll.period_end.strftime('%Y-%m-%d'),
                    payroll.pay_date.strftime('%Y-%m-%d'),
                    payroll.base_pay,
                    payroll.overtime_pay,
                    payroll.bonus,
                    payroll.gross_pay,
                    payroll.total_deductions,
                    payroll.net_pay,
                    payroll.get_status_display(),
                    payroll.currency
                ])
            
            return response
    else:
        payrolls = Payroll.objects.none()
        search_query = ''
        status_filter = ''
        date_from = ''
        date_to = ''
        total_payrolls = 0
        draft_count = 0
        approved_count = 0
        paid_count = 0
        total_earned = 0
        company = None
        employees = User.objects.none()
    
    # Determine which base template to use
    if request.user.role == 'EMPLOYEE':
        base_template = 'ems/base_employee.html'
    else:
        base_template = 'ems/base_employer.html'
    
    # Get payroll settings for configuration tab
    payroll_settings = None
    # For accountants, get their company
    if not company and hasattr(request.user, 'employee_profile'):
        company = request.user.company
    
    if company:
        # Get or create default payroll settings
        payroll_settings, created = PayrollDeductionSettings.objects.get_or_create(
            company=company,
            defaults={
                'paye_enabled': True,
                'paye_tax_brackets': [
                    {"min": 0, "max": 4800, "rate": 0},
                    {"min": 4800, "max": 50000, "rate": 25},
                    {"min": 50000, "max": None, "rate": 37.5}
                ],
                'napsa_enabled': True,
                'napsa_employee_percentage': Decimal('5.0'),
                'napsa_employer_percentage': Decimal('5.0'),
                'nhima_enabled': True,
                'nhima_employee_percentage': Decimal('1.0'),
                'nhima_employer_percentage': Decimal('1.0'),
                'late_deduction_type': 'PERCENTAGE',
                'late_deduction_percentage': Decimal('5.0'),
                'absent_deduction_type': 'DAILY_RATE',
                'absent_deduction_percentage': Decimal('100.0'),
                'working_days_per_month': 22,
                'gratuity_enabled': False,
                'gratuity_percentage': Decimal('8.33'),
                'gratuity_eligibility_months': 12,
                'currency': 'ZMW'
            }
        )
        if created:
            messages.info(request, 'Default payroll settings have been created. Please review and customize them in the Payroll Configuration tab.')
    
    # Prepare payroll settings as JSON for JavaScript and template
    import json
    payroll_settings_json = None
    paye_tax_brackets_json = None
    if payroll_settings:
        payroll_settings_json = json.dumps({
            'paye_enabled': payroll_settings.paye_enabled,
            'paye_tax_brackets': payroll_settings.paye_tax_brackets,
            'napsa_enabled': payroll_settings.napsa_enabled,
            'napsa_employee_percentage': float(payroll_settings.napsa_employee_percentage),
            'nhima_enabled': payroll_settings.nhima_enabled,
            'nhima_employee_percentage': float(payroll_settings.nhima_employee_percentage),
            'gratuity_enabled': payroll_settings.gratuity_enabled,
            'gratuity_percentage': float(payroll_settings.gratuity_percentage),
            'gratuity_eligibility_months': payroll_settings.gratuity_eligibility_months,
            'working_days_per_month': payroll_settings.working_days_per_month,
        })
        # Serialize paye_tax_brackets for textarea display
        paye_tax_brackets_json = json.dumps(payroll_settings.paye_tax_brackets, indent=2)
    
    context = {
        'payrolls': payrolls,
        'user': request.user,
        'company': company,
        'base_template': base_template,
        'search_query': search_query,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Payroll.Status.choices,
        'total_payrolls': total_payrolls,
        'draft_count': draft_count,
        'approved_count': approved_count,
        'paid_count': paid_count,
        'total_earned': total_earned,
        'employees': employees,
        'payroll_settings': payroll_settings,
        'payroll_settings_json': payroll_settings_json,
        'paye_tax_brackets_json': paye_tax_brackets_json,
    }
    return render(request, 'ems/payroll_list.html', context)


@login_required
def payroll_detail(request, payroll_id):
    """View individual payslip detail"""
    from payroll.models import Payroll, PayrollDeduction
    
    try:
        payroll = Payroll.objects.select_related('employee', 'employee__employee_profile').get(id=payroll_id)
    except Payroll.DoesNotExist:
        messages.error(request, 'Payslip not found.')
        return redirect('payroll_list')
    
    # Check permissions
    if request.user.role == 'EMPLOYEE':
        # Employees can only see their own payroll
        if payroll.employee != request.user:
            messages.error(request, 'Access denied. You can only view your own payroll records.')
            return redirect('payroll_list')
    elif not _has_payroll_access(request.user):
        # Only Finance/Accounting/HR staff can view all payroll records
        messages.error(request, 'Access denied. Payroll access is restricted to Finance/Accounting staff.')
        return redirect('payroll_list')
    
    # Get detailed deductions
    deductions = PayrollDeduction.objects.filter(payroll=payroll).order_by('deduction_type')
    
    # Determine base template
    if request.user.role == 'EMPLOYEE':
        base_template = 'ems/base_employee.html'
    else:
        base_template = 'ems/base_employer.html'
    
    context = {
        'payroll': payroll,
        'deductions': deductions,
        'base_template': base_template,
    }
    return render(request, 'ems/payroll_detail.html', context)


@login_required
def benefits_list(request):
    """List employee benefits"""
    from payroll.models import Benefit, EmployeeBenefit
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Count
    import csv
    from django.http import HttpResponse
    from datetime import date
    
    User = get_user_model()
    
    if request.user.role == 'EMPLOYEE':
        enrolled_benefits = EmployeeBenefit.objects.filter(employee=request.user).select_related('benefit').order_by('-enrollment_date')
        available_benefits = Benefit.objects.filter(is_active=True)
        
        # Employee statistics
        total_enrolled = enrolled_benefits.count()
        active_count = enrolled_benefits.filter(status=EmployeeBenefit.Status.ACTIVE).count()
        pending_count = enrolled_benefits.filter(status=EmployeeBenefit.Status.PENDING).count()
        
        search_query = ''
        status_filter = ''
        benefit_type_filter = ''
        company = None
        
    elif request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        company = getattr(request.user, 'company', None)
        
        # Get all enrollments for statistics
        all_enrollments = EmployeeBenefit.objects.filter(employee__company=company)
        
        # Calculate statistics
        total_enrolled = all_enrollments.count()
        active_count = all_enrollments.filter(status=EmployeeBenefit.Status.ACTIVE).count()
        pending_count = all_enrollments.filter(status=EmployeeBenefit.Status.PENDING).count()
        
        enrolled_benefits = all_enrollments.select_related('employee', 'employee__employee_profile', 'benefit').order_by('-enrollment_date')
        available_benefits = Benefit.objects.filter(is_active=True)
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            enrolled_benefits = enrolled_benefits.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(benefit__name__icontains=search_query)
            )
        
        # Status filter
        status_filter = request.GET.get('status', '')
        if status_filter:
            enrolled_benefits = enrolled_benefits.filter(status=status_filter)
        
        # Benefit type filter
        benefit_type_filter = request.GET.get('benefit_type', '')
        if benefit_type_filter:
            enrolled_benefits = enrolled_benefits.filter(benefit__benefit_type=benefit_type_filter)
        
        # CSV Export
        if request.GET.get('format') == 'csv':
            filename = f"benefits_{date.today().strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(response)
            
            writer.writerow([
                'Employee', 'Position', 'Benefit Name', 'Benefit Type', 
                'Enrollment Date', 'Effective Date', 'Status', 
                'Company Contribution', 'Employee Contribution'
            ])
            
            for enrollment in enrolled_benefits:
                writer.writerow([
                    enrollment.employee.get_full_name(),
                    enrollment.employee.employee_profile.job_title if hasattr(enrollment.employee, 'employee_profile') and enrollment.employee.employee_profile else 'N/A',
                    enrollment.benefit.name,
                    enrollment.benefit.get_benefit_type_display(),
                    enrollment.enrollment_date.strftime('%Y-%m-%d'),
                    enrollment.effective_date.strftime('%Y-%m-%d'),
                    enrollment.get_status_display(),
                    enrollment.benefit.company_contribution,
                    enrollment.benefit.employee_contribution
                ])
            
            return response
    else:
        enrolled_benefits = EmployeeBenefit.objects.none()
        available_benefits = Benefit.objects.none()
        search_query = ''
        status_filter = ''
        benefit_type_filter = ''
        total_enrolled = 0
        active_count = 0
        pending_count = 0
        company = None
    
    context = {
        'enrolled_benefits': enrolled_benefits,
        'available_benefits': available_benefits,
        'user': request.user,
        'company': company,
        'search_query': search_query,
        'status_filter': status_filter,
        'benefit_type_filter': benefit_type_filter,
        'status_choices': EmployeeBenefit.Status.choices,
        'benefit_type_choices': Benefit.BenefitType.choices,
        'total_enrolled': total_enrolled,
        'active_count': active_count,
        'pending_count': pending_count,
        'total_benefits': available_benefits.count(),
    }
    return render(request, 'ems/benefits_list.html', context)

@login_required
def training_list(request):
    """List training programs and enrollments"""
    from training.models import TrainingProgram, TrainingEnrollment, Certification
    from django.contrib.auth import get_user_model
    from django.db.models import Q, Count, Avg
    from datetime import date
    import csv
    from django.http import HttpResponse
    
    User = get_user_model()
    
    if request.user.role == 'EMPLOYEE':
        enrollments = TrainingEnrollment.objects.filter(employee=request.user).select_related('program').order_by('-enrollment_date')
        programs = TrainingProgram.objects.filter(is_active=True)
        certifications = Certification.objects.filter(employee=request.user).order_by('-issue_date')
        
        # Employee statistics
        total_enrollments = enrollments.count()
        completed_count = enrollments.filter(status=TrainingEnrollment.Status.COMPLETED).count()
        in_progress_count = enrollments.filter(status=TrainingEnrollment.Status.IN_PROGRESS).count()
        total_certifications = certifications.count()
        
        search_query = ''
        status_filter = ''
        program_type_filter = ''
        company = None
        
    elif request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        company = getattr(request.user, 'company', None)
        
        # Get all enrollments for statistics
        all_enrollments = TrainingEnrollment.objects.filter(employee__company=company)
        
        # Calculate statistics
        total_enrollments = all_enrollments.count()
        completed_count = all_enrollments.filter(status=TrainingEnrollment.Status.COMPLETED).count()
        in_progress_count = all_enrollments.filter(status=TrainingEnrollment.Status.IN_PROGRESS).count()
        total_certifications = Certification.objects.filter(employee__company=company).count()
        
        enrollments = all_enrollments.select_related('employee', 'employee__employee_profile', 'program').order_by('-enrollment_date')
        programs = TrainingProgram.objects.filter(is_active=True)
        certifications = Certification.objects.filter(employee__company=company).select_related('employee', 'employee__employee_profile').order_by('-issue_date')
        
        # Search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            enrollments = enrollments.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(program__title__icontains=search_query)
            )
        
        # Status filter
        status_filter = request.GET.get('status', '')
        if status_filter:
            enrollments = enrollments.filter(status=status_filter)
        
        # Program type filter
        program_type_filter = request.GET.get('program_type', '')
        if program_type_filter:
            enrollments = enrollments.filter(program__program_type=program_type_filter)
        
        # CSV Export
        if request.GET.get('format') == 'csv':
            filename = f"training_enrollments_{date.today().strftime('%Y%m%d')}.csv"
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(response)
            
            writer.writerow([
                'Employee', 'Position', 'Program', 'Type', 
                'Enrollment Date', 'Start Date', 'Completion Date',
                'Duration (hours)', 'Status', 'Score', 'Cost'
            ])
            
            for enrollment in enrollments:
                writer.writerow([
                    enrollment.employee.get_full_name(),
                    enrollment.employee.employee_profile.job_title if hasattr(enrollment.employee, 'employee_profile') and enrollment.employee.employee_profile else 'N/A',
                    enrollment.program.title,
                    enrollment.program.get_program_type_display(),
                    enrollment.enrollment_date.strftime('%Y-%m-%d'),
                    enrollment.start_date.strftime('%Y-%m-%d') if enrollment.start_date else 'N/A',
                    enrollment.completion_date.strftime('%Y-%m-%d') if enrollment.completion_date else 'N/A',
                    enrollment.program.duration_hours,
                    enrollment.get_status_display(),
                    enrollment.score if enrollment.score else 'N/A',
                    enrollment.program.cost
                ])
            
            return response
    else:
        enrollments = TrainingEnrollment.objects.none()
        programs = TrainingProgram.objects.none()
        certifications = Certification.objects.none()
        search_query = ''
        status_filter = ''
        program_type_filter = ''
        total_enrollments = 0
        completed_count = 0
        in_progress_count = 0
        total_certifications = 0
        company = None
    
    context = {
        'enrollments': enrollments,
        'programs': programs,
        'certifications': certifications,
        'user': request.user,
        'company': company,
        'search_query': search_query,
        'status_filter': status_filter,
        'program_type_filter': program_type_filter,
        'status_choices': TrainingEnrollment.Status.choices,
        'program_type_choices': TrainingProgram.ProgramType.choices,
        'total_enrollments': total_enrollments,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'total_certifications': total_certifications,
        'total_programs': programs.count(),
    }
    return render(request, 'ems/training_list.html', context)

@login_required
def onboarding_list(request):
    """List onboarding and offboarding processes with statistics and filters"""
    from onboarding.models import (
        EmployeeOnboarding, EmployeeOffboarding, 
        OnboardingTaskCompletion
    )
    from django.db.models import Q, Count, Avg
    import csv
    
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(request.user, 'company', None)
    
    # Get query parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    process_type = request.GET.get('process_type', 'onboarding')  # onboarding or offboarding
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    export_csv = request.GET.get('export', '')
    
    # Base querysets
    if process_type == 'offboarding':
        # Offboarding process
        offboardings = EmployeeOffboarding.objects.filter(
            employee__company=company
        ).select_related('employee', 'employee__employer_profile', 'checklist')
        
        # Apply search
        if search_query:
            offboardings = offboardings.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__email__icontains=search_query) |
                Q(reason__icontains=search_query)
            )
        
        # Apply status filter
        if status_filter:
            offboardings = offboardings.filter(status=status_filter)
        
        # Apply date filters
        if date_from:
            offboardings = offboardings.filter(last_working_date__gte=date_from)
        if date_to:
            offboardings = offboardings.filter(last_working_date__lte=date_to)
        
        # Statistics for offboarding
        total_offboardings = offboardings.count()
        not_started_count = offboardings.filter(status='NOT_STARTED').count()
        in_progress_count = offboardings.filter(status='IN_PROGRESS').count()
        completed_count = offboardings.filter(status='COMPLETED').count()
        exit_interviews_completed = offboardings.filter(exit_interview_completed=True).count()
        
        # CSV Export
        if export_csv == 'true':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="offboarding.csv"'
            writer = csv.writer(response)
            writer.writerow(['Employee', 'Position', 'Last Working Date', 'Reason', 'Status', 
                           'Exit Interview', 'Checklist', 'Created Date'])
            
            for offboarding in offboardings:
                position = getattr(offboarding.employee.employer_profile, 'job_title', 'N/A') if hasattr(offboarding.employee, 'employer_profile') else 'N/A'
                writer.writerow([
                    offboarding.employee.get_full_name(),
                    position,
                    offboarding.last_working_date.strftime('%Y-%m-%d'),
                    offboarding.get_reason_display(),
                    offboarding.get_status_display(),
                    'Yes' if offboarding.exit_interview_completed else 'No',
                    offboarding.checklist.name if offboarding.checklist else 'N/A',
                    offboarding.created_at.strftime('%Y-%m-%d'),
                ])
            return response
        
        context = {
            'offboardings': offboardings,
            'total_offboardings': total_offboardings,
            'not_started_count': not_started_count,
            'in_progress_count': in_progress_count,
            'completed_count': completed_count,
            'exit_interviews_completed': exit_interviews_completed,
            'status_choices': EmployeeOffboarding.Status.choices,
            'reason_choices': EmployeeOffboarding.Reason.choices,
            'process_type': process_type,
            'search_query': search_query,
            'status_filter': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'user': request.user,
        }
    else:
        # Onboarding process (default)
        onboardings = EmployeeOnboarding.objects.filter(
            employee__company=company
        ).select_related('employee', 'employee__employer_profile', 'checklist', 'buddy')
        
        # Apply search
        if search_query:
            onboardings = onboardings.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__email__icontains=search_query)
            )
        
        # Apply status filter
        if status_filter:
            onboardings = onboardings.filter(status=status_filter)
        
        # Apply date filters
        if date_from:
            onboardings = onboardings.filter(start_date__gte=date_from)
        if date_to:
            onboardings = onboardings.filter(start_date__lte=date_to)
        
        # Statistics for onboarding
        total_onboardings = onboardings.count()
        not_started_count = onboardings.filter(status='NOT_STARTED').count()
        in_progress_count = onboardings.filter(status='IN_PROGRESS').count()
        completed_count = onboardings.filter(status='COMPLETED').count()
        on_hold_count = onboardings.filter(status='ON_HOLD').count()
        
        # Calculate average completion progress
        onboardings_with_tasks = []
        for onboarding in onboardings:
            total_tasks = OnboardingTaskCompletion.objects.filter(
                employee_onboarding=onboarding
            ).count()
            completed_tasks = OnboardingTaskCompletion.objects.filter(
                employee_onboarding=onboarding,
                status='COMPLETED'
            ).count()
            progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            onboardings_with_tasks.append({
                'onboarding': onboarding,
                'progress': progress,
                'completed_tasks': completed_tasks,
                'total_tasks': total_tasks
            })
        
        # CSV Export
        if export_csv == 'true':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="onboarding.csv"'
            writer = csv.writer(response)
            writer.writerow(['Employee', 'Position', 'Start Date', 'Expected Completion', 
                           'Actual Completion', 'Status', 'Buddy', 'Progress', 'Checklist'])
            
            for item in onboardings_with_tasks:
                onboarding = item['onboarding']
                position = getattr(onboarding.employee.employer_profile, 'job_title', 'N/A') if hasattr(onboarding.employee, 'employer_profile') else 'N/A'
                writer.writerow([
                    onboarding.employee.get_full_name(),
                    position,
                    onboarding.start_date.strftime('%Y-%m-%d'),
                    onboarding.expected_completion_date.strftime('%Y-%m-%d'),
                    onboarding.actual_completion_date.strftime('%Y-%m-%d') if onboarding.actual_completion_date else 'N/A',
                    onboarding.get_status_display(),
                    onboarding.buddy.get_full_name() if onboarding.buddy else 'N/A',
                    f"{item['progress']:.1f}%",
                    onboarding.checklist.name if onboarding.checklist else 'N/A',
                ])
            return response
        
        context = {
            'onboardings_with_tasks': onboardings_with_tasks,
            'total_onboardings': total_onboardings,
            'not_started_count': not_started_count,
            'in_progress_count': in_progress_count,
            'completed_count': completed_count,
            'on_hold_count': on_hold_count,
            'status_choices': EmployeeOnboarding.Status.choices,
            'process_type': process_type,
            'search_query': search_query,
            'status_filter': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'user': request.user,
        }
    
    return render(request, 'ems/onboarding_list.html', context)

@login_required
def analytics_dashboard_view(request):
    """Comprehensive analytics dashboard with charts, reports, and export"""
    if request.user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        return render(request, 'ems/unauthorized.html')
    
    from attendance.models import Attendance, LeaveRequest
    from performance.models import PerformanceReview
    from documents.models import EmployeeDocument
    from accounts.models import User
    from payroll.models import Payroll, EmployeeBenefit
    from training.models import TrainingEnrollment
    from onboarding.models import EmployeeOnboarding, EmployeeOffboarding
    from django.db.models import Avg, Count, Sum, Q
    from datetime import date, timedelta
    import json
    import csv
    
    company = getattr(request.user, 'company', None) or getattr(getattr(request.user, 'employer_profile', None), 'company', None)
    
    # Get filter parameters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    report_type = request.GET.get('report_type', 'overview')  # overview, attendance, performance, payroll
    export_csv = request.GET.get('export', '')
    
    # Default date range (last 30 days)
    today = date.today()
    if not date_from:
        date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')
    
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)
    
    employees = User.objects.filter(company=company, role=User.Role.EMPLOYEE) if company else User.objects.none()

    # Base querysets with date filters
    attendance_qs = Attendance.objects.filter(employee__company=company, date__range=[start_date, end_date])
    leave_qs = LeaveRequest.objects.filter(employee__company=company, created_at__date__range=[start_date, end_date])
    review_qs = PerformanceReview.objects.filter(employee__company=company, review_date__range=[start_date, end_date])
    document_qs = EmployeeDocument.objects.filter(employee__company=company, created_at__date__range=[start_date, end_date])
    payroll_qs = Payroll.objects.filter(employee__company=company, period_start__range=[start_date, end_date])
    training_qs = TrainingEnrollment.objects.filter(employee__company=company, enrollment_date__range=[start_date, end_date])
    
    # All-time querysets for certain metrics
    all_onboardings = EmployeeOnboarding.objects.filter(employee__company=company)
    all_offboardings = EmployeeOffboarding.objects.filter(employee__company=company)
    all_benefits = EmployeeBenefit.objects.filter(employee__company=company)

    # ===== COMPREHENSIVE STATISTICS =====
    
    # Employee Statistics
    total_employees = employees.count()
    present_today = Attendance.objects.filter(
        employee__company=company, 
        date=today, 
        status__in=['PRESENT', 'LATE', 'HALF_DAY']
    ).count()
    absent_today = Attendance.objects.filter(
        employee__company=company,
        date=today, 
        status='ABSENT'
    ).count()
    
    # Attendance Statistics
    total_attendance_records = attendance_qs.count()
    present_count = attendance_qs.filter(status__in=['PRESENT', 'LATE', 'HALF_DAY']).count()
    absent_count = attendance_qs.filter(status='ABSENT').count()
    attendance_rate = (present_count / total_attendance_records * 100) if total_attendance_records > 0 else 0
    
    # Leave Statistics
    total_leaves = leave_qs.count()
    pending_leaves = leave_qs.filter(status='PENDING').count()
    approved_leaves = leave_qs.filter(status='APPROVED').count()
    rejected_leaves = leave_qs.filter(status='REJECTED').count()
    
    # Performance Statistics
    total_reviews = review_qs.count()
    avg_rating = review_qs.aggregate(avg=Avg('overall_rating'))['avg'] or 0
    completed_reviews = review_qs.filter(status='COMPLETED').count()
    pending_reviews = review_qs.filter(status__in=['DRAFT', 'SUBMITTED']).count()
    
    # Document Statistics
    total_documents = document_qs.count()
    approved_documents = document_qs.filter(status='APPROVED').count()
    pending_documents = document_qs.filter(status='PENDING').count()
    rejected_documents = document_qs.filter(status='REJECTED').count()
    
    # Payroll Statistics
    total_payrolls = payroll_qs.count()
    total_gross_pay = payroll_qs.aggregate(total=Sum('gross_pay'))['total'] or 0
    total_net_pay = payroll_qs.aggregate(total=Sum('net_pay'))['total'] or 0
    paid_payrolls = payroll_qs.filter(status='PAID').count()
    
    # Training Statistics
    total_trainings = training_qs.count()
    completed_trainings = training_qs.filter(status='COMPLETED').count()
    in_progress_trainings = training_qs.filter(status='IN_PROGRESS').count()
    
    # Onboarding/Offboarding Statistics
    active_onboardings = all_onboardings.filter(status='IN_PROGRESS').count()
    completed_onboardings = all_onboardings.filter(status='COMPLETED').count()
    active_offboardings = all_offboardings.filter(status='IN_PROGRESS').count()
    
    # Benefits Statistics
    active_benefits = all_benefits.filter(status='ACTIVE').count()
    total_benefit_cost = all_benefits.filter(status='ACTIVE').aggregate(
        total=Sum('benefit__cost')
    )['total'] or 0

    # ===== TREND DATA (Date Range) =====
    date_labels = []
    attendance_trend = []
    absence_trend = []
    leave_trend = []
    
    days_diff = (end_date - start_date).days + 1
    step = max(1, days_diff // 14)  # Show max 14 data points
    
    for offset in range(0, days_diff, step):
        current_day = start_date + timedelta(days=offset)
        if current_day > end_date:
            break
        date_labels.append(current_day.strftime('%b %d'))
        attendance_trend.append(
            Attendance.objects.filter(
                employee__company=company,
                date=current_day, 
                status__in=['PRESENT', 'LATE', 'HALF_DAY']
            ).count()
        )
        absence_trend.append(
            Attendance.objects.filter(
                employee__company=company,
                date=current_day, 
                status='ABSENT'
            ).count()
        )
        leave_trend.append(
            LeaveRequest.objects.filter(
                employee__company=company,
                start_date__lte=current_day,
                end_date__gte=current_day,
                status='APPROVED'
            ).count()
        )

    # ===== DISTRIBUTION CHARTS =====
    
    # Leave Status Distribution
    leave_status_counts = leave_qs.values('status').annotate(count=Count('id')).order_by('status')
    leave_status_labels = []
    leave_status_data = []
    for entry in leave_status_counts:
        leave_status_labels.append(dict(LeaveRequest.Status.choices).get(entry['status'], entry['status'].title()))
        leave_status_data.append(entry['count'])
    
    if not leave_status_labels:
        leave_status_labels = ['No Data']
        leave_status_data = [0]
    
    # Leave Type Distribution
    leave_type_counts = leave_qs.values('leave_type').annotate(count=Count('id')).order_by('-count')[:5]
    leave_type_labels = []
    leave_type_data = []
    for entry in leave_type_counts:
        leave_type_labels.append(dict(LeaveRequest.LeaveType.choices).get(entry['leave_type'], entry['leave_type'].title()))
        leave_type_data.append(entry['count'])
    
    if not leave_type_labels:
        leave_type_labels = ['No Data']
        leave_type_data = [0]
    
    # Performance Rating Distribution
    rating_distribution = review_qs.values('overall_rating').annotate(count=Count('id')).order_by('overall_rating')
    rating_labels = []
    rating_data = []
    for entry in rating_distribution:
        rating_labels.append(dict(PerformanceReview.OverallRating.choices).get(entry['overall_rating'], 'N/A'))
        rating_data.append(entry['count'])
    
    if not rating_labels:
        rating_labels = ['No Data']
        rating_data = [0]
    
    # Training Status Distribution
    training_status_counts = training_qs.values('status').annotate(count=Count('id')).order_by('status')
    training_status_labels = [entry['status'].replace('_', ' ').title() for entry in training_status_counts]
    training_status_data = [entry['count'] for entry in training_status_counts]
    
    if not training_status_labels:
        training_status_labels = ['No Data']
        training_status_data = [0]

    # ===== RECENT ACTIVITY FEED =====
    activity_feed = []
    
    for leave in leave_qs.order_by('-created_at')[:5]:
        activity_feed.append({
            'type': 'leave',
            'title': f"Leave request - {leave.employee.get_full_name()}",
            'description': f"{leave.get_leave_type_display()} • {leave.start_date:%b %d} - {leave.end_date:%b %d}",
            'timestamp': leave.created_at,
            'status': leave.get_status_display(),
            'icon': '🏖️'
        })
    
    for review in review_qs.order_by('-review_date')[:5]:
        activity_feed.append({
            'type': 'review',
            'title': f"Performance review - {review.employee.get_full_name()}",
            'description': f"{review.get_review_type_display()} • {review.review_date:%b %d, %Y}",
            'timestamp': review.review_date,
            'status': review.get_status_display(),
            'icon': '📊'
        })
    
    for doc in document_qs.order_by('-created_at')[:5]:
        activity_feed.append({
            'type': 'document',
            'title': f"Document - {doc.document_name}",
            'description': doc.employee.get_full_name() if doc.employee else '—',
            'timestamp': doc.created_at,
            'status': doc.get_status_display(),
            'icon': '📄'
        })
    
    for training in training_qs.order_by('-enrollment_date')[:5]:
        activity_feed.append({
            'type': 'training',
            'title': f"Training - {training.employee.get_full_name()}",
            'description': training.program.title if training.program else 'N/A',
            'timestamp': training.enrollment_date,
            'status': training.get_status_display(),
            'icon': '🎓'
        })
    
    activity_feed = sorted(activity_feed, key=lambda item: item['timestamp'], reverse=True)[:12]

    # ===== CSV EXPORT =====
    if export_csv == 'true':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="analytics_report_{start_date}_{end_date}.csv"'
        writer = csv.writer(response)
        
        # Write summary statistics
        writer.writerow(['Analytics Report', f'{start_date} to {end_date}'])
        writer.writerow([])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Employees', total_employees])
        writer.writerow(['Attendance Rate', f'{attendance_rate:.1f}%'])
        writer.writerow(['Total Attendance Records', total_attendance_records])
        writer.writerow(['Present Count', present_count])
        writer.writerow(['Absent Count', absent_count])
        writer.writerow(['Total Leave Requests', total_leaves])
        writer.writerow(['Pending Leaves', pending_leaves])
        writer.writerow(['Approved Leaves', approved_leaves])
        writer.writerow(['Total Performance Reviews', total_reviews])
        writer.writerow(['Average Rating', f'{avg_rating:.2f}'])
        writer.writerow(['Completed Reviews', completed_reviews])
        writer.writerow(['Total Documents', total_documents])
        writer.writerow(['Total Payrolls', total_payrolls])
        writer.writerow(['Total Gross Pay', f'{total_gross_pay:.2f}'])
        writer.writerow(['Total Net Pay', f'{total_net_pay:.2f}'])
        writer.writerow(['Total Training Enrollments', total_trainings])
        writer.writerow(['Completed Trainings', completed_trainings])
        writer.writerow(['Active Onboardings', active_onboardings])
        writer.writerow(['Active Benefits', active_benefits])
        writer.writerow([])
        
        # Write trend data
        writer.writerow(['Date', 'Present', 'Absent', 'On Leave'])
        for i, label in enumerate(date_labels):
            writer.writerow([
                label,
                attendance_trend[i] if i < len(attendance_trend) else 0,
                absence_trend[i] if i < len(absence_trend) else 0,
                leave_trend[i] if i < len(leave_trend) else 0
            ])
        
        return response

    context = {
        'company': company,
        'date_from': date_from,
        'date_to': date_to,
        'report_type': report_type,
        
        # Summary Statistics
        'total_employees': total_employees,
        'present_today': present_today,
        'absent_today': absent_today,
        'attendance_rate': round(attendance_rate, 1),
        
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        
        'total_reviews': total_reviews,
        'avg_rating': round(avg_rating, 1),
        'completed_reviews': completed_reviews,
        
        'total_documents': total_documents,
        'pending_documents': pending_documents,
        'approved_documents': approved_documents,
        
        'total_payrolls': total_payrolls,
        'total_gross_pay': total_gross_pay,
        'total_net_pay': total_net_pay,
        'paid_payrolls': paid_payrolls,
        
        'total_trainings': total_trainings,
        'completed_trainings': completed_trainings,
        'in_progress_trainings': in_progress_trainings,
        
        'active_onboardings': active_onboardings,
        'active_offboardings': active_offboardings,
        
        'active_benefits': active_benefits,
        'total_benefit_cost': total_benefit_cost,
        
        # Chart Data
        'attendance_trend_labels': json.dumps(date_labels),
        'attendance_trend_present': json.dumps(attendance_trend),
        'attendance_trend_absent': json.dumps(absence_trend),
        'leave_trend_data': json.dumps(leave_trend),
        
        'leave_status_labels': json.dumps(leave_status_labels),
        'leave_status_data': json.dumps(leave_status_data),
        
        'leave_type_labels': json.dumps(leave_type_labels),
        'leave_type_data': json.dumps(leave_type_data),
        
        'rating_labels': json.dumps(rating_labels),
        'rating_data': json.dumps(rating_data),
        
        'training_status_labels': json.dumps(training_status_labels),
        'training_status_data': json.dumps(training_status_data),
        
        'activity_feed': activity_feed,
    }
    return render(request, 'ems/analytics_employer.html', context)


@login_required
def notifications_list(request):
    """Enhanced notifications list with filters, statistics, and actions"""
    from notifications.models import Notification
    from django.db.models import Q, Count
    from django.utils import timezone
    import csv
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')  # all, read, unread
    export_csv = request.GET.get('export', '')
    
    # Base queryset
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender').order_by('-created_at')
    
    # Apply search filter
    if search_query:
        notifications = notifications.filter(
            Q(title__icontains=search_query) |
            Q(message__icontains=search_query) |
            Q(sender__first_name__icontains=search_query) |
            Q(sender__last_name__icontains=search_query)
        )
    
    # Apply category filter
    if category_filter:
        notifications = notifications.filter(category=category_filter)
    
    # Apply type filter
    if type_filter:
        notifications = notifications.filter(notification_type=type_filter)
    
    # Apply status filter
    if status_filter == 'read':
        notifications = notifications.filter(is_read=True)
    elif status_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    
    # Statistics
    total_notifications = Notification.objects.filter(recipient=request.user).count()
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    read_count = Notification.objects.filter(recipient=request.user, is_read=True).count()
    
    # Category breakdown
    category_counts = Notification.objects.filter(
        recipient=request.user
    ).values('category').annotate(count=Count('id')).order_by('-count')
    
    # Type breakdown
    type_counts = Notification.objects.filter(
        recipient=request.user
    ).values('notification_type').annotate(count=Count('id')).order_by('-count')
    
    # Recent unread (for quick actions)
    recent_unread = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # CSV Export
    if export_csv == 'true':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="notifications.csv"'
        writer = csv.writer(response)
        writer.writerow(['Date', 'Title', 'Message', 'Category', 'Type', 'Status', 'Sender'])
        
        for notification in notifications:
            writer.writerow([
                notification.created_at.strftime('%Y-%m-%d %H:%M'),
                notification.title,
                notification.message,
                notification.get_category_display(),
                notification.get_notification_type_display(),
                'Read' if notification.is_read else 'Unread',
                notification.sender.get_full_name() if notification.sender else 'System',
            ])
        return response
    
    # Limit for display
    notifications = notifications[:200]
    
    context = {
        'notifications': notifications,
        'total_notifications': total_notifications,
        'unread_count': unread_count,
        'read_count': read_count,
        'category_counts': category_counts,
        'type_counts': type_counts,
        'recent_unread': recent_unread,
        'category_choices': Notification.Category.choices,
        'type_choices': Notification.NotificationType.choices,
        'search_query': search_query,
        'category_filter': category_filter,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'user': request.user,
    }
    return render(request, 'ems/notifications_list.html', context)


@login_required
def notification_mark_read(request, notification_id):
    """Mark a single notification as read"""
    from notifications.models import Notification
    
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )
            notification.mark_as_read()
            return JsonResponse({'success': True, 'message': 'Notification marked as read'})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Notification not found'}, status=404)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


@login_required
def notification_mark_all_read(request):
    """Mark all notifications as read"""
    from notifications.models import Notification
    from django.utils import timezone
    
    if request.method == 'POST':
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return JsonResponse({
            'success': True,
            'message': f'{count} notification(s) marked as read',
            'count': count
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


@login_required
def notification_delete(request, notification_id):
    """Delete a notification"""
    from notifications.models import Notification
    
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )
            notification.delete()
            return JsonResponse({'success': True, 'message': 'Notification deleted'})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Notification not found'}, status=404)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


@login_required
def system_health(request):
    """System health monitoring dashboard for System Superadmin"""
    if not request.user.is_superadmin:
        return render(request, 'ems/unauthorized.html')
    from accounts.models import Company, User
    from attendance.models import Attendance, LeaveRequest
    from documents.models import EmployeeDocument
    from datetime import date, timedelta

    today = date.today()

    # System statistics
    total_companies = Company.objects.count()
    total_users = User.objects.count()
    total_employees = User.objects.filter(role='EMPLOYEE').count()

    # Database statistics
    db_stats = {
        'total_companies': total_companies,
        'total_users': total_users,
        'total_employees': total_employees,
        'total_attendance_records': Attendance.objects.count(),
        'total_leave_requests': LeaveRequest.objects.count(),
        'total_documents': EmployeeDocument.objects.count(),
        'total_reviews': PerformanceReview.objects.count(),
    }

    # System performance metrics - get real data where possible
    system_metrics = {
        'cpu_usage': 0,
        'memory_usage': 0,
        'disk_usage': 0,
        'uptime_days': 0,
        'response_time_ms': 120,
        'error_rate': 0.01,
        'active_sessions': 45,
        'database_connections': 12,
    }

    # Try to get real system metrics using psutil
    try:
        import psutil
        system_metrics['cpu_usage'] = psutil.cpu_percent(interval=1)
        system_metrics['memory_usage'] = psutil.virtual_memory().percent
        system_metrics['disk_usage'] = psutil.disk_usage('/').percent
    except ImportError:
        # Use mock data if psutil is not available
        system_metrics['cpu_usage'] = 45.2
        system_metrics['memory_usage'] = 62.8
        system_metrics['disk_usage'] = 34.1
    except Exception as e:
        # Handle any other psutil errors gracefully
        print(f"Error getting system metrics: {e}")
        # Keep default mock values

    # Recent system events (mock data)
    recent_events = [
        {
            'timestamp': timezone.now() - timedelta(minutes=5),
            'event_type': 'USER_LOGIN',
            'message': 'User logged in successfully',
            'status': 'SUCCESS'
        },
        {
            'timestamp': timezone.now() - timedelta(hours=1),
            'event_type': 'COMPANY_CREATED',
            'message': 'New company registered: Tech Solutions Inc',
            'status': 'INFO'
        },
        {
            'timestamp': timezone.now() - timedelta(hours=2),
            'event_type': 'SYSTEM_BACKUP',
            'message': 'Automated system backup completed',
            'status': 'SUCCESS'
        },
        {
            'timestamp': timezone.now() - timedelta(hours=6),
            'event_type': 'ERROR',
            'message': 'Failed login attempt detected',
            'status': 'WARNING'
        },
    ]

    # API endpoints status (mock data)
    api_status = [
        {'endpoint': '/api/v1/auth/', 'status': 'HEALTHY', 'response_time': 85},
        {'endpoint': '/api/v1/attendance/', 'status': 'HEALTHY', 'response_time': 120},
        {'endpoint': '/api/v1/performance/', 'status': 'HEALTHY', 'response_time': 95},
        {'endpoint': '/api/v1/documents/', 'status': 'HEALTHY', 'response_time': 110},
    ]

    context = {
        'user': request.user,
        'db_stats': db_stats,
        'system_metrics': system_metrics,
        'recent_events': recent_events,
        'api_status': api_status,
        'today_date': today.strftime('%Y-%m-%d'),
    }

    return render(request, 'ems/system_health.html', context)


# ============================================================================
# BRANCH MANAGEMENT VIEWS
# ============================================================================

@login_required
def branch_management(request):
    """Branch management dashboard"""
    from accounts.models import CompanyBranch
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = request.user.company
    except:
        return render(request, 'ems/unauthorized.html')
    
    branches = CompanyBranch.objects.filter(company=company).select_related('manager')
    
    context = {
        'company': company,
        'branches': branches,
    }
    
    return render(request, 'ems/branch_management.html', context)


@login_required
def branch_create(request):
    """Create new branch"""
    from accounts.models import CompanyBranch
    from django.contrib import messages
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = request.user.company
    except:
        return render(request, 'ems/unauthorized.html')
    
    if request.method == 'POST':
        try:
            branch = CompanyBranch.objects.create(
                company=company,
                name=request.POST.get('name'),
                code=request.POST.get('code'),
                address=request.POST.get('address'),
                city=request.POST.get('city'),
                state_province=request.POST.get('state_province', ''),
                country=request.POST.get('country', 'Zambia'),
                postal_code=request.POST.get('postal_code', ''),
                phone=request.POST.get('phone', ''),
                email=request.POST.get('email', ''),
                is_head_office=request.POST.get('is_head_office') == 'on',
                is_active=True,
            )
            
            # Set manager if provided
            manager_id = request.POST.get('manager')
            if manager_id:
                branch.manager_id = manager_id
                branch.save()
            
            messages.success(request, f'Branch "{branch.name}" created successfully!')
            return redirect('branch_management')
        except Exception as e:
            messages.error(request, f'Error creating branch: {str(e)}')
    
    # Get potential managers (admins/employers)
    managers = User.objects.filter(
        company=company,
        role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
    )
    
    context = {
        'company': company,
        'managers': managers,
    }
    
    return render(request, 'ems/branch_form.html', context)


@login_required
def branch_edit(request, branch_id):
    """Edit branch"""
    from accounts.models import CompanyBranch
    from django.contrib import messages
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = request.user.company
        branch = CompanyBranch.objects.get(id=branch_id, company=company)
    except:
        messages.error(request, 'Branch not found')
        return redirect('branch_management')
    
    if request.method == 'POST':
        try:
            branch.name = request.POST.get('name')
            branch.code = request.POST.get('code')
            branch.address = request.POST.get('address')
            branch.city = request.POST.get('city')
            branch.state_province = request.POST.get('state_province', '')
            branch.country = request.POST.get('country', 'Zambia')
            branch.postal_code = request.POST.get('postal_code', '')
            branch.phone = request.POST.get('phone', '')
            branch.email = request.POST.get('email', '')
            branch.is_head_office = request.POST.get('is_head_office') == 'on'
            branch.is_active = request.POST.get('is_active') == 'on'
            
            # Set manager
            manager_id = request.POST.get('manager')
            if manager_id:
                branch.manager_id = manager_id
            else:
                branch.manager = None
            
            branch.save()
            
            messages.success(request, f'Branch "{branch.name}" updated successfully!')
            return redirect('branch_management')
        except Exception as e:
            messages.error(request, f'Error updating branch: {str(e)}')
    
    # Get potential managers
    managers = User.objects.filter(
        company=company,
        role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']
    )
    
    context = {
        'company': company,
        'branch': branch,
        'managers': managers,
        'is_edit': True,
    }
    
    return render(request, 'ems/branch_form.html', context)


@login_required
def branch_detail(request, branch_id):
    """Branch detail view with employees"""
    from accounts.models import CompanyBranch
    from django.contrib import messages
    
    if not (request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or request.user.is_employer_admin):
        return render(request, 'ems/unauthorized.html')
    
    try:
        company = request.user.company
        branch = CompanyBranch.objects.get(id=branch_id, company=company)
    except:
        messages.error(request, 'Branch not found')
        return redirect('branch_management')
    
    # Get employees in this branch
    employees = User.objects.filter(
        company=company,
        employee_profile__branch=branch,
        role='EMPLOYEE'
    ).select_related('employee_profile')
    
    # Get departments in this branch
    from accounts.models import EnhancedDepartment
    departments = EnhancedDepartment.objects.filter(
        company=company,
        branch=branch
    ).select_related('head')
    
    context = {
        'company': company,
        'branch': branch,
        'employees': employees,
        'departments': departments,
        'employee_count': employees.count(),
        'department_count': departments.count(),
    }
    
    return render(request, 'ems/branch_detail.html', context)


# ============================================================================
# REQUEST MANAGEMENT VIEWS
# ============================================================================

@login_required
def employee_requests_list(request):
    """Employee's request list"""
    from requests.models import EmployeeRequest
    
    if request.user.role != 'EMPLOYEE':
        return render(request, 'ems/unauthorized.html')
    
    # Get employee's requests
    my_requests = EmployeeRequest.objects.filter(
        employee=request.user
    ).select_related('request_type').order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        my_requests = my_requests.filter(status=status_filter)
    
    context = {
        'requests': my_requests,
        'status_filter': status_filter,
    }
    
    return render(request, 'ems/employee_requests_list.html', context)


@login_required
def employee_request_create(request):
    """Create new request"""
    from requests.models import EmployeeRequest, RequestType
    from django.contrib import messages
    
    if request.user.role != 'EMPLOYEE':
        return render(request, 'ems/unauthorized.html')
    
    if request.method == 'POST':
        try:
            request_type = RequestType.objects.get(id=request.POST.get('request_type'))
            
            # Get department from employee profile
            try:
                department = request.user.employee_profile.department
            except:
                department = ''
            
            employee_request = EmployeeRequest.objects.create(
                request_type=request_type,
                employee=request.user,
                department=department,
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                amount=request.POST.get('amount') if request.POST.get('amount') else None,
                currency=request.POST.get('currency', 'ZMW'),
                priority=request.POST.get('priority', 'MEDIUM'),
                required_by=request.POST.get('required_by') if request.POST.get('required_by') else None,
                status='PENDING',
            )
            
            # Handle attachment
            if request.FILES.get('attachment'):
                employee_request.attachment = request.FILES['attachment']
                employee_request.save()
            
            # Create specific request details based on type
            if request_type.code == 'PETTY_CASH':
                from requests.models import PettyCashRequest
                PettyCashRequest.objects.create(
                    request=employee_request,
                    purpose=request.POST.get('purpose', ''),
                    expense_category=request.POST.get('expense_category', ''),
                    payment_method=request.POST.get('payment_method', 'CASH'),
                )
            elif request_type.code == 'ADVANCE':
                from requests.models import AdvanceRequest
                AdvanceRequest.objects.create(
                    request=employee_request,
                    reason=request.POST.get('reason', ''),
                    repayment_plan=request.POST.get('repayment_plan', ''),
                    installments=int(request.POST.get('installments', 1)),
                )
            elif request_type.code == 'REIMBURSEMENT':
                from requests.models import ReimbursementRequest
                ReimbursementRequest.objects.create(
                    request=employee_request,
                    expense_date=request.POST.get('expense_date'),
                    expense_category=request.POST.get('expense_category', ''),
                    vendor_name=request.POST.get('vendor_name', ''),
                )
            
            messages.success(request, f'Request "{employee_request.title}" submitted successfully!')
            return redirect('employee_requests_list')
        except Exception as e:
            messages.error(request, f'Error creating request: {str(e)}')
    
    # Get active request types
    request_types = RequestType.objects.filter(is_active=True)
    
    context = {
        'request_types': request_types,
    }
    
    return render(request, 'ems/employee_request_form.html', context)


@login_required
def employee_request_detail(request, request_id):
    """View request detail"""
    from requests.models import EmployeeRequest
    from django.contrib import messages
    
    try:
        employee_request = EmployeeRequest.objects.get(id=request_id)
        
        # Check permission
        if request.user.role == 'EMPLOYEE' and employee_request.employee != request.user:
            return render(request, 'ems/unauthorized.html')
    except:
        messages.error(request, 'Request not found')
        return redirect('employee_requests_list')
    
    # Get approvals
    approvals = employee_request.approvals.all().select_related('approver').order_by('approval_level')
    
    # Get comments
    comments = employee_request.comments.all().select_related('user').order_by('-created_at')
    
    # Get specific request details
    specific_details = None
    if hasattr(employee_request, 'petty_cash_details'):
        specific_details = employee_request.petty_cash_details
        specific_type = 'petty_cash'
    elif hasattr(employee_request, 'advance_details'):
        specific_details = employee_request.advance_details
        specific_type = 'advance'
    elif hasattr(employee_request, 'reimbursement_details'):
        specific_details = employee_request.reimbursement_details
        specific_type = 'reimbursement'
    else:
        specific_type = 'general'
    
    context = {
        'request': employee_request,
        'approvals': approvals,
        'comments': comments,
        'specific_details': specific_details,
        'specific_type': specific_type,
    }
    
    return render(request, 'ems/employee_request_detail.html', context)


@login_required
def requests_approval_center(request):
    """Request approval center for supervisors/HR/finance"""
    from requests.models import EmployeeRequest, RequestApproval
    
    # Check if user has approval rights
    has_approval_rights = False
    
    if request.user.role == 'EMPLOYEE':
        try:
            profile = request.user.employee_profile
            if profile.employee_role in ['SUPERVISOR', 'HR', 'ACCOUNTANT', 'ACCOUNTS']:
                has_approval_rights = True
        except:
            pass
    elif request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        has_approval_rights = True
    
    if not has_approval_rights:
        return render(request, 'ems/unauthorized.html')
    
    # Get pending requests where user is approver
    pending_approvals = RequestApproval.objects.filter(
        approver=request.user,
        action='PENDING'
    ).select_related('request', 'request__employee', 'request__request_type').order_by('-assigned_date')
    
    # Get all pending requests in company (for HR/Admin)
    if request.user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN'] or \
       (hasattr(request.user, 'employee_profile') and request.user.employee_profile.employee_role == 'HR'):
        all_pending = EmployeeRequest.objects.filter(
            employee__company=request.user.company,
            status='PENDING'
        ).select_related('employee', 'request_type').order_by('-created_at')
    else:
        all_pending = []
    
    context = {
        'pending_approvals': pending_approvals,
        'all_pending': all_pending,
    }
    
    return render(request, 'ems/requests_approval_center.html', context)


@login_required
def request_approve_reject(request, request_id):
    """Approve or reject request"""
    from requests.models import EmployeeRequest, RequestApproval
    from django.contrib import messages
    
    if request.method != 'POST':
        return redirect('requests_approval_center')
    
    try:
        employee_request = EmployeeRequest.objects.get(id=request_id)
        action = request.POST.get('action')  # 'approve' or 'reject'
        comments = request.POST.get('comments', '')
        
        # Find approval record
        approval = RequestApproval.objects.filter(
            request=employee_request,
            approver=request.user,
            action='PENDING'
        ).first()
        
        if not approval:
            messages.error(request, 'No pending approval found for this request')
            return redirect('requests_approval_center')
        
        # Update approval
        if action == 'approve':
            approval.action = 'APPROVED'
            approval.comments = comments
            approval.action_date = timezone.now()
            approval.save()
            
            # Check if all approvals completed
            all_approvals = employee_request.approvals.all()
            if all(a.action == 'APPROVED' for a in all_approvals):
                employee_request.status = 'APPROVED'
                employee_request.save()
                messages.success(request, 'Request approved successfully!')
            else:
                messages.success(request, 'Request approved at your level!')
        
        elif action == 'reject':
            approval.action = 'REJECTED'
            approval.comments = comments
            approval.action_date = timezone.now()
            approval.save()
            
            # Reject the entire request
            employee_request.status = 'REJECTED'
            employee_request.save()
            
            messages.success(request, 'Request rejected!')
        
        return redirect('requests_approval_center')
    except Exception as e:
        messages.error(request, f'Error processing request: {str(e)}')
        return redirect('requests_approval_center')


# ============================================================================
# COMMUNICATION VIEWS
# ============================================================================

@login_required
def chat_groups_list(request):
    """List chat groups"""
    from communication.models import ChatGroup
    
    if request.user.role not in ['EMPLOYEE', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return render(request, 'ems/unauthorized.html')
    
    # Get groups user is member of
    my_groups = ChatGroup.objects.filter(
        members=request.user,
        is_active=True
    ).select_related('company', 'created_by').order_by('-last_activity')
    
    # Get available groups user can join
    available_groups = ChatGroup.objects.filter(
        company=request.user.company,
        is_private=False,
        is_active=True
    ).exclude(members=request.user)
    
    context = {
        'my_groups': my_groups,
        'available_groups': available_groups,
    }
    
    return render(request, 'ems/chat_groups_list.html', context)


@login_required
def chat_group_detail(request, group_id):
    """Chat group conversation view"""
    from communication.models import ChatGroup, GroupMessage, GroupMessageRead
    from django.contrib import messages as django_messages
    
    try:
        group = ChatGroup.objects.get(id=group_id, company=request.user.company)
        
        # Check if user is member
        if request.user not in group.members.all():
            django_messages.error(request, 'You are not a member of this group')
            return redirect('chat_groups_list')
    except:
        django_messages.error(request, 'Group not found')
        return redirect('chat_groups_list')
    
    # Handle new message
    if request.method == 'POST':
        try:
            message_content = request.POST.get('message')
            if message_content:
                message = GroupMessage.objects.create(
                    group=group,
                    sender=request.user,
                    content=message_content,
                    message_type='TEXT'
                )
                
                # Handle attachment
                if request.FILES.get('attachment'):
                    message.attachment = request.FILES['attachment']
                    message.message_type = 'FILE'
                    message.save()
                
                # Update group last activity
                group.last_activity = timezone.now()
                group.save()
                
                return redirect('chat_group_detail', group_id=group_id)
        except Exception as e:
            django_messages.error(request, f'Error sending message: {str(e)}')
    
    # Get messages
    messages = GroupMessage.objects.filter(
        group=group,
        is_deleted=False
    ).select_related('sender').order_by('-created_at')[:50]
    messages = list(reversed(messages))
    
    # Mark as read
    GroupMessageRead.objects.update_or_create(
        user=request.user,
        group=group,
        defaults={'last_read_at': timezone.now()}
    )
    
    context = {
        'group': group,
        'messages': messages,
        'is_admin': request.user in group.admins.all(),
    }
    
    return render(request, 'ems/chat_group_detail.html', context)


@login_required
def direct_messages_list(request):
    """List direct message conversations"""
    from communication.models import DirectMessage
    from django.db.models import Q, Max
    
    if request.user.role not in ['EMPLOYEE', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return render(request, 'ems/unauthorized.html')
    
    # Get unique conversations
    conversations = DirectMessage.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).values(
        'sender', 'recipient'
    ).annotate(
        last_message_time=Max('created_at')
    ).order_by('-last_message_time')
    
    # Build conversation list
    conversation_list = []
    seen_users = set()
    
    for conv in conversations:
        if conv['sender'] == request.user.id:
            other_user_id = conv['recipient']
        else:
            other_user_id = conv['sender']
        
        if other_user_id not in seen_users:
            seen_users.add(other_user_id)
            try:
                other_user = User.objects.get(id=other_user_id)
                
                # Get last message
                last_msg = DirectMessage.objects.filter(
                    Q(sender=request.user, recipient=other_user) |
                    Q(sender=other_user, recipient=request.user)
                ).order_by('-created_at').first()
                
                # Count unread
                unread_count = DirectMessage.objects.filter(
                    sender=other_user,
                    recipient=request.user,
                    is_read=False
                ).count()
                
                conversation_list.append({
                    'user': other_user,
                    'last_message': last_msg,
                    'unread_count': unread_count,
                })
            except:
                continue
    
    # Get all employees/colleagues for new conversation
    colleagues = User.objects.filter(
        company=request.user.company,
        is_active=True,
        role='EMPLOYEE'
    ).exclude(id=request.user.id).select_related('employee_profile').order_by('first_name', 'last_name')
    
    context = {
        'conversations': conversation_list,
        'colleagues': colleagues,
    }
    
    return render(request, 'ems/direct_messages_list.html', context)


@login_required
def direct_message_conversation(request, user_id):
    """Direct message conversation with specific user"""
    from communication.models import DirectMessage
    from django.db.models import Q
    from django.contrib import messages as django_messages
    
    try:
        other_user = User.objects.get(id=user_id, company=request.user.company)
    except:
        django_messages.error(request, 'User not found')
        return redirect('direct_messages_list')
    
    # Handle new message
    if request.method == 'POST':
        try:
            message_content = request.POST.get('message')
            if message_content:
                message = DirectMessage.objects.create(
                    sender=request.user,
                    recipient=other_user,
                    content=message_content
                )
                
                # Handle attachment
                if request.FILES.get('attachment'):
                    message.attachment = request.FILES['attachment']
                    message.save()
                
                return redirect('direct_message_conversation', user_id=user_id)
        except Exception as e:
            django_messages.error(request, f'Error sending message: {str(e)}')
    
    # Get messages between users
    messages = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=other_user) |
        Q(sender=other_user, recipient=request.user)
    ).select_related('sender', 'recipient').order_by('-created_at')[:50]
    messages = list(reversed(messages))
    
    # Mark received messages as read
    DirectMessage.objects.filter(
        sender=other_user,
        recipient=request.user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    
    context = {
        'other_user': other_user,
        'messages': messages,
    }
    
    return render(request, 'ems/direct_message_conversation.html', context)


@login_required
def announcements_list(request):
    """List announcements"""
    from communication.models import Announcement, AnnouncementRead
    
    # Get active announcements for user
    announcements = Announcement.objects.filter(
        company=request.user.company,
        is_published=True
    ).select_related('published_by').order_by('-published_at')
    
    # Filter based on audience
    user_announcements = []
    for announcement in announcements:
        if announcement.is_active():
            target_users = announcement.get_target_users()
            if request.user in target_users:
                # Check if read
                read_record = AnnouncementRead.objects.filter(
                    announcement=announcement,
                    user=request.user
                ).first()
                
                announcement.is_read = read_record is not None
                announcement.is_acknowledged = read_record.acknowledged if read_record else False
                user_announcements.append(announcement)
    
    context = {
        'announcements': user_announcements,
    }
    
    return render(request, 'ems/announcements_list.html', context)


@login_required
def announcement_detail(request, announcement_id):
    """View announcement detail"""
    from communication.models import Announcement, AnnouncementRead
    from django.contrib import messages as django_messages
    
    try:
        announcement = Announcement.objects.get(
            id=announcement_id,
            company=request.user.company,
            is_published=True
        )
    except:
        django_messages.error(request, 'Announcement not found')
        return redirect('announcements_list')
    
    # Mark as read
    read_record, created = AnnouncementRead.objects.get_or_create(
        announcement=announcement,
        user=request.user
    )
    
    # Handle acknowledgment
    if request.method == 'POST' and announcement.requires_acknowledgment:
        if request.POST.get('acknowledge') == 'yes':
            read_record.acknowledged = True
            read_record.acknowledged_at = timezone.now()
            read_record.save()
            django_messages.success(request, 'Announcement acknowledged!')
            return redirect('announcements_list')
    
    context = {
        'announcement': announcement,
        'read_record': read_record,
    }
    
    return render(request, 'ems/announcement_detail.html', context)


# ============================================================================
# SUPERVISOR FEATURES (Phase 4)
# ============================================================================

@login_required
def supervisor_dashboard(request):
    """My Team Dashboard - Overview of supervised employees"""
    # Check if user is a supervisor
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'SUPERVISOR':
            messages.error(request, 'Access denied. Supervisor role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Get team members (employees supervised by this user)
    team_members = User.objects.filter(
        employee_profile__supervisor=request.user,
        company=request.user.company
    ).select_related('employee_profile').order_by('first_name', 'last_name')
    
    # Team statistics
    total_team_members = team_members.count()
    
    # Today's attendance
    today = timezone.now().date()
    present_today = Attendance.objects.filter(
        employee__in=team_members,
        date=today,
        status='PRESENT'
    ).count()
    
    # Pending requests from team
    from requests.models import EmployeeRequest
    pending_requests = EmployeeRequest.objects.filter(
        employee__in=team_members,
        status='PENDING'
    ).select_related('employee', 'request_type').order_by('-created_at')[:10]
    
    # Upcoming leave requests
    upcoming_leaves = LeaveRequest.objects.filter(
        employee__in=team_members,
        status__in=['APPROVED', 'PENDING'],
        start_date__gte=today
    ).select_related('employee').order_by('start_date')[:5]
    
    # Performance reviews due
    reviews_due = PerformanceReview.objects.filter(
        employee__in=team_members,
        status='IN_PROGRESS',
        review_period_end__lte=today + timedelta(days=30)
    ).select_related('employee').order_by('review_period_end')[:5]
    
    context = {
        'team_members': team_members,
        'total_team_members': total_team_members,
        'present_today': present_today,
        'attendance_rate': round((present_today / total_team_members * 100) if total_team_members > 0 else 0, 1),
        'pending_requests': pending_requests,
        'upcoming_leaves': upcoming_leaves,
        'reviews_due': reviews_due,
    }
    
    return render(request, 'ems/supervisor_dashboard.html', context)


@login_required
def supervisor_team_attendance(request):
    """Team Attendance View - Aggregate view of team attendance"""
    # Check if user is a supervisor
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'SUPERVISOR':
            messages.error(request, 'Access denied. Supervisor role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Get team members
    team_members = User.objects.filter(
        employee_profile__supervisor=request.user,
        company=request.user.company
    ).select_related('employee_profile')
    
    # Date range filter
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        try:
            start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
        except:
            pass
    
    if request.GET.get('end_date'):
        try:
            end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
        except:
            pass
    
    # Get attendance records
    attendance_records = Attendance.objects.filter(
        employee__in=team_members,
        date__range=[start_date, end_date]
    ).select_related('employee').order_by('-date', 'employee__first_name')
    
    # Aggregate statistics
    total_days = (end_date - start_date).days + 1
    stats = {
        'total_days': total_days,
        'present': attendance_records.filter(status='PRESENT').count(),
        'absent': attendance_records.filter(status='ABSENT').count(),
        'late': attendance_records.filter(status='LATE').count(),
        'half_day': attendance_records.filter(status='HALF_DAY').count(),
    }
    
    # Per-employee summary
    employee_summary = []
    for member in team_members:
        member_attendance = attendance_records.filter(employee=member)
        summary = {
            'employee': member,
            'total_present': member_attendance.filter(status='PRESENT').count(),
            'total_absent': member_attendance.filter(status='ABSENT').count(),
            'total_late': member_attendance.filter(status='LATE').count(),
            'attendance_rate': round((member_attendance.filter(status='PRESENT').count() / total_days * 100) if total_days > 0 else 0, 1)
        }
        employee_summary.append(summary)
    
    context = {
        'team_members': team_members,
        'attendance_records': attendance_records,
        'stats': stats,
        'employee_summary': employee_summary,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'ems/supervisor_team_attendance.html', context)


@login_required
def supervisor_team_performance(request):
    """Team Performance Metrics - Performance tracking dashboard"""
    # Check if user is a supervisor
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'SUPERVISOR':
            messages.error(request, 'Access denied. Supervisor role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Get team members
    team_members = User.objects.filter(
        employee_profile__supervisor=request.user,
        company=request.user.company
    ).select_related('employee_profile')
    
    # Get performance reviews
    reviews = PerformanceReview.objects.filter(
        employee__in=team_members
    ).select_related('employee', 'reviewer').order_by('-review_period_end')
    
    # Performance statistics
    completed_reviews = reviews.filter(status='COMPLETED')
    pending_reviews = reviews.filter(status__in=['DRAFT', 'IN_PROGRESS'])
    
    # Average ratings
    if completed_reviews.exists():
        avg_overall = completed_reviews.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0
    else:
        avg_overall = 0
    
    # Employee performance summary
    employee_performance = []
    for member in team_members:
        member_reviews = completed_reviews.filter(employee=member)
        latest_review = member_reviews.first()
        
        summary = {
            'employee': member,
            'total_reviews': member_reviews.count(),
            'latest_review': latest_review,
            'avg_rating': member_reviews.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0,
            'pending_reviews': pending_reviews.filter(employee=member).count(),
        }
        employee_performance.append(summary)
    
    context = {
        'team_members': team_members,
        'reviews': reviews[:10],  # Latest 10
        'completed_reviews_count': completed_reviews.count(),
        'pending_reviews_count': pending_reviews.count(),
        'avg_overall_rating': round(avg_overall, 2),
        'employee_performance': employee_performance,
    }
    
    return render(request, 'ems/supervisor_team_performance.html', context)


@login_required
def supervisor_request_approval(request):
    """Enhanced Request Approval Interface for Supervisors"""
    # Check if user is a supervisor
    try:
        profile = request.user.employee_profile
        if profile.employee_role != 'SUPERVISOR':
            messages.error(request, 'Access denied. Supervisor role required.')
            return redirect('employee_dashboard')
    except:
        messages.error(request, 'Employee profile not found.')
        return redirect('employee_dashboard')
    
    # Get team members
    team_members = User.objects.filter(
        employee_profile__supervisor=request.user,
        company=request.user.company
    )
    
    from requests.models import EmployeeRequest, RequestApproval
    
    # Get pending requests from team members
    pending_requests = EmployeeRequest.objects.filter(
        employee__in=team_members,
        status='PENDING'
    ).select_related('employee', 'request_type').prefetch_related('approvals').order_by('-created_at')
    
    # Get requests pending supervisor's approval
    my_pending_approvals = RequestApproval.objects.filter(
        approver=request.user,
        action='PENDING'
    ).select_related('request', 'request__employee', 'request__request_type').order_by('-assigned_date')
    
    # Recently processed requests
    recent_processed = EmployeeRequest.objects.filter(
        employee__in=team_members,
        status__in=['APPROVED', 'REJECTED']
    ).select_related('employee', 'request_type').order_by('-updated_at')[:10]
    
    # Handle approval/rejection
    if request.method == 'POST':
        approval_id = request.POST.get('approval_id')
        action = request.POST.get('action')
        comments = request.POST.get('comments', '')
        
        try:
            approval = RequestApproval.objects.get(
                id=approval_id,
                approver=request.user,
                action='PENDING'
            )
            
            if action in ['APPROVED', 'REJECTED']:
                approval.action = action
                approval.comments = comments
                approval.action_date = timezone.now()
                approval.save()
                
                # Update request status
                emp_request = approval.request
                if action == 'APPROVED':
                    # Check if all approvals are complete
                    all_approved = not emp_request.approvals.filter(action='PENDING').exists()
                    if all_approved:
                        emp_request.status = 'APPROVED'
                        emp_request.save()
                    messages.success(request, f'Request {emp_request.request_number} approved successfully.')
                else:
                    emp_request.status = 'REJECTED'
                    emp_request.save()
                    messages.success(request, f'Request {emp_request.request_number} rejected.')
                
                return redirect('supervisor_request_approval')
        except RequestApproval.DoesNotExist:
            messages.error(request, 'Approval not found or already processed.')
    
    context = {
        'pending_requests': pending_requests,
        'my_pending_approvals': my_pending_approvals,
        'recent_processed': recent_processed,
    }
    
    return render(request, 'ems/supervisor_request_approval.html', context)


@login_required
def custom_report_builder(request):
    """Custom report builder for dynamic reports"""
    if request.user.role not in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return render(request, 'ems/unauthorized.html')
    
    from reports.custom_report_builder import CustomReportBuilder, generate_custom_report
    from django.http import HttpResponse
    
    company = getattr(request.user, 'company', None)
    
    # Get report configuration
    source = request.GET.get('source', 'employees')
    available_sources = CustomReportBuilder.REPORT_SOURCES
    
    # Initialize builder
    builder = CustomReportBuilder(source, company)
    source_config = builder.config
    
    # Handle report generation
    if request.method == 'POST' or request.GET.get('generate'):
        # Get filters
        filters = {}
        for key in request.GET.keys():
            if key not in ['source', 'generate', 'export', 'fields']:
                filters[key] = request.GET.get(key)
        
        # Get selected fields
        selected_fields_param = request.GET.get('fields', '')
        selected_fields = selected_fields_param.split(',') if selected_fields_param else None
        
        # Generate report
        report_data = generate_custom_report(source, company, filters, selected_fields)
        
        # Handle CSV export
        if request.GET.get('export') == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="custom_report_{source}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            response.write(report_data['csv'])
            return response
        
        context = {
            'available_sources': available_sources,
            'current_source': source,
            'source_config': source_config,
            'report_data': report_data['data'],
            'statistics': report_data['statistics'],
            'filters': filters,
            'selected_fields': selected_fields or list(source_config.get('fields', {}).keys()),
        }
        
        return render(request, 'ems/custom_report_builder.html', context)
    
    # Initial view
    context = {
        'available_sources': available_sources,
        'current_source': source,
        'source_config': source_config,
    }
    
    return render(request, 'ems/custom_report_builder.html', context)


@login_required
def payslip_designer(request):
    """Advanced payslip designer with drag-and-drop functionality"""
    allowed_roles = {'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'ADMIN'}
    if not (
        getattr(request.user, 'role', '') in allowed_roles
        or getattr(request.user, 'is_employer_admin', False)
        or getattr(request.user, 'is_superuser', False)
    ):
        return render(request, 'ems/unauthorized.html', status=403)

    company = _get_user_company(request.user)
    if not company:
        messages.error(request, 'Company not assigned. Please contact your administrator.')
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        # Save payslip design settings
        company.payslip_orientation = request.POST.get('orientation', 'portrait')
        company.payslip_logo_position = request.POST.get('logo_position', 'top-left')
        company.payslip_stamp_position = request.POST.get('stamp_position', 'bottom-right')
        company.payslip_address_position = request.POST.get('address_position', 'top-right')
        company.payslip_header_content = request.POST.get('header_content', '')
        company.payslip_footer_content = request.POST.get('footer_content', '')
        
        # Handle section order
        import json
        section_order = request.POST.get('section_order', '[]')
        try:
            company.payslip_section_order = json.loads(section_order)
        except:
            company.payslip_section_order = ['employee_info', 'salary_info', 'deductions', 'summary']
        
        # Handle field positions
        field_positions = request.POST.get('field_positions', '{}')
        try:
            company.payslip_field_positions = json.loads(field_positions)
        except:
            company.payslip_field_positions = {}
        
        company.save()
        messages.success(request, 'Payslip design saved successfully!')
        return redirect('payslip_designer')

    # Default section order if not set
    if not company.payslip_section_order:
        company.payslip_section_order = ['employee_info', 'salary_info', 'deductions', 'summary']
    
    context = {
        'company': company,
        'available_sections': [
            {'id': 'employee_info', 'name': 'Employee Information', 'icon': '👤'},
            {'id': 'salary_info', 'name': 'Salary Information', 'icon': '💰'},
            {'id': 'deductions', 'name': 'Deductions', 'icon': '📉'},
            {'id': 'allowances', 'name': 'Allowances', 'icon': '➕'},
            {'id': 'summary', 'name': 'Summary', 'icon': '📊'},
            {'id': 'tax_breakdown', 'name': 'Tax Breakdown', 'icon': '🧾'},
            {'id': 'ytd_summary', 'name': 'YTD Summary', 'icon': '📅'},
        ],
        'position_options': [
            {'value': 'top-left', 'label': 'Top Left'},
            {'value': 'top-center', 'label': 'Top Center'},
            {'value': 'top-right', 'label': 'Top Right'},
            {'value': 'bottom-left', 'label': 'Bottom Left'},
            {'value': 'bottom-center', 'label': 'Bottom Center'},
            {'value': 'bottom-right', 'label': 'Bottom Right'},
        ],
    }

    return render(request, 'ems/payslip_designer.html', context)
