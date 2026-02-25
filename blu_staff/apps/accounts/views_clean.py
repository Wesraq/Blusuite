from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models
from django.db.models import Q
from datetime import date
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator

User = get_user_model()

from .models import User, EmployeeProfile, EmployerProfile, Company, CompanyRegistrationRequest
from .serializers import (
    UserRegisterSerializer,
    UserLoginSerializer,
    UserSerializer,
    EmployeeProfileSerializer,
    EmployerProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)

@login_required
def company_list(request):
    """List all companies with approval workflow"""
    # Only SuperAdmins can access company management
    if request.user.role != 'SUPERADMIN':
        messages.error(request, f'Access denied. Your role ({request.user.role}) does not have permission to access company management.')
        return redirect('dashboard_redirect')

    # Get pending registration requests (not approved companies)
    pending_requests = CompanyRegistrationRequest.objects.filter(status='PENDING').order_by('-created_at')
    approved_companies = Company.objects.filter(is_approved=True, is_active=True).order_by('-created_at')
    rejected_companies = Company.objects.filter(is_approved=False, is_active=False).exclude(created_at__date=date.today()).order_by('-created_at')

    context = {
        'pending_companies': pending_requests,
        'approved_companies': approved_companies,
        'rejected_companies': rejected_companies,
        'total_pending': pending_requests.count(),
        'total_approved': approved_companies.count(),
        'is_superadmin': request.user.role == 'SUPERADMIN',  # Add flag for superadmin
        'user_role': request.user.role,  # Add user role for template logic
    }
    return render(request, 'ems/company_list.html', context)


def approve_company(request, request_id):
    """Approve a company registration request"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    # Get the registration request instead of company
    registration_request = get_object_or_404(CompanyRegistrationRequest, id=request_id, status='PENDING')

    if request.method == 'POST':
        try:
            # Create company from registration request
            company = Company.objects.create(
                name=registration_request.company_name,
                address=registration_request.company_address,
                phone=registration_request.company_phone,
                email=registration_request.company_email,
                website=registration_request.company_website,
                tax_id=registration_request.tax_id,
                subscription_plan=registration_request.subscription_plan,
                max_employees=registration_request.number_of_employees,
                registration_request=registration_request,
                is_approved=True,
                approved_by=request.user,
                approved_at=timezone.now()
            )

            # Create employer user account
            employer_user = User.objects.create_user(
                email=registration_request.contact_email,
                password=registration_request.generated_password,
                first_name=registration_request.contact_first_name,
                last_name=registration_request.contact_last_name,
                role='ADMINISTRATOR',
                company=company,
                must_change_password=True,  # Force password change on first login
                is_active=True
            )

            # Create employer profile
            EmployerProfile.objects.create(
                user=employer_user,
                company_name=registration_request.company_name,
                company_address=registration_request.company_address,
                company_phone=registration_request.company_phone,
                company_email=registration_request.company_email,
                tax_id=registration_request.tax_id,
                company=company
            )

            # Update registration request status
            registration_request.status = 'APPROVED'
            registration_request.reviewed_by = request.user
            registration_request.reviewed_at = timezone.now()
            registration_request.review_notes = request.POST.get('review_notes', '')
            registration_request.save()

            # Send approval email to employer
            try:
                subject = f'Company Registration Approved - {company.name}'
                message = render_to_string('emails/company_approved.html', {
                    'company': company,
                    'employer': employer_user,
                    'login_url': f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/",
                    'license_info': {
                        'plan': company.subscription_plan,
                        'license_key': company.license_key,
                        'max_employees': company.max_employees,
                        'expiry': company.license_expiry,
                    }
                })

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [registration_request.contact_email],
                    html_message=message
                )
            except Exception as e:
                print(f"Failed to send approval email: {e}")

            messages.success(
                request,
                f'Company registration approved! Login credentials sent to {registration_request.contact_email}'
            )
            return redirect('company_list')

        except Exception as e:
            messages.error(request, f'Error approving company registration: {str(e)}')
            return redirect('company_list')

    return render(request, 'ems/approve_company_registration.html', {
        'registration_request': registration_request
    })


def reject_company(request, request_id):
    """Reject a company registration request"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    # Get the registration request instead of company
    registration_request = get_object_or_404(CompanyRegistrationRequest, id=request_id, status='PENDING')

    if request.method == 'POST':
        try:
            registration_request.status = 'REJECTED'
            registration_request.reviewed_by = request.user
            registration_request.reviewed_at = timezone.now()
            registration_request.rejection_reason = request.POST.get('rejection_reason', '')
            registration_request.save()

            # Send rejection email
            try:
                subject = f'Company Registration Update - {registration_request.company_name}'
                message = render_to_string('emails/company_rejected.html', {
                    'request': registration_request,
                    'rejection_reason': registration_request.rejection_reason
                })

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [registration_request.contact_email],
                    html_message=message
                )
            except Exception as e:
                print(f"Failed to send rejection email: {e}")

            messages.success(request, 'Company registration rejected.')
            return redirect('company_list')

        except Exception as e:
            messages.error(request, f'Error rejecting company registration: {str(e)}')
            return redirect('company_list')

    return render(request, 'ems/reject_company_registration.html', {
        'registration_request': registration_request
    })


@login_required
def company_create(request):
    """Create new company request (public access)"""
    # Anyone can create a company request, but it needs approval

    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        website = request.POST.get('website')
        tax_id = request.POST.get('tax_id')

        if name and address and email:
            try:
                # Check if company with this name or email already exists
                existing_company = Company.objects.filter(
                    models.Q(name=name) | models.Q(email=email)
                ).first()

                if existing_company:
                    if existing_company.is_approved:
                        messages.error(request, 'A company with this name or email already exists.')
                    else:
                        messages.info(request, 'Your company request is already pending approval.')
                    return redirect('company_create')

                # Create company request (not approved yet)
                company = Company.objects.create(
                    name=name,
                    address=address,
                    phone=phone,
                    email=email,
                    website=website,
                    tax_id=tax_id,
                    is_active=False,  # Requires approval
                    is_approved=False
                )

                messages.success(request, 'Company request submitted successfully! You will receive an email when approved.')
                return redirect('/')
            except Exception as e:
                messages.error(request, f'Error creating company request: {str(e)}')
        else:
            messages.error(request, 'Company name, address, and email are required.')

    return render(request, 'ems/company_request_form.html', {'action': 'Request Company'})


@login_required
def company_edit(request, company_id):
    """Edit existing company"""
    if request.user.role not in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    company = get_object_or_404(Company, id=company_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        website = request.POST.get('website')
        tax_id = request.POST.get('tax_id')

        if name and address:
            try:
                company.name = name
                company.address = address
                company.phone = phone
                company.email = email
                company.website = website
                company.tax_id = tax_id
                company.save()

                messages.success(request, f'Company "{company.name}" updated successfully!')
                return redirect('company_list')
            except Exception as e:
                messages.error(request, f'Error updating company: {str(e)}')
        else:
            messages.error(request, 'Company name and address are required.')

    context = {
        'company': company,
        'action': 'Edit'
    }
    return render(request, 'ems/company_form.html', context)


@login_required
def company_delete(request, company_id):
    """Delete company"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('/')

    company = get_object_or_404(Company, id=company_id)

    if request.method == 'POST':
        try:
            company_name = company.name
            company.delete()
            messages.success(request, f'Company "{company_name}" deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting company: {str(e)}')

@login_required
def approve_company(request, company_id):
    """Approve an existing company or resend credentials"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    company = get_object_or_404(Company, id=company_id)

    if request.method == 'POST':
        # Get password from form or generate new one
        admin_password = request.POST.get('admin_password')
        if admin_password:
            # Use admin-provided password
            final_password = admin_password
        else:
            # Generate new password
            import random, string
            final_password = ''.join(random.choices(string.ascii_letters + string.digits + '!@#$%', k=12))

        # Check if company is already approved
        if company.is_approved:
            # Company already approved - just resend credentials
            employer_user = User.objects.filter(
                company=company,
                role='ADMINISTRATOR'
            ).first()

            if not employer_user:
                messages.error(request, f'No employer account found for {company.name}')
                return redirect('company_list')
        else:
            # Approve the company
            company.is_approved = True
            company.is_active = True
            company.approved_by = request.user
            company.approved_at = timezone.now()
            company.save()

            # Create employer user account
            employer_user = User.objects.create_user(
                email=company.email,
                password=final_password,
                first_name=company.contact_first_name if hasattr(company, 'contact_first_name') else 'Company',
                last_name=company.contact_last_name if hasattr(company, 'contact_last_name') else 'Admin',
                role='ADMINISTRATOR',
                company=company,
                must_change_password=True,
                is_active=True
            )

            # Create employer profile
            EmployerProfile.objects.create(
                user=employer_user,
                company_name=company.name,
                company_address=company.address,
                company_phone=company.phone,
                company_email=company.email,
                tax_id=company.tax_id,
                company=company
            )

        # Send approval email
        try:
            subject = f'Company Registration Approved - {company.name}'
            message = render_to_string('emails/company_approved.html', {
                'company': company,
                'employer': employer_user,
                'password': final_password,
                'login_url': f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/",
                'license_info': {
                    'plan': company.subscription_plan,
                    'license_key': company.license_key,
                    'max_employees': company.max_employees,
                    'expiry': company.license_expiry,
                }
            })

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [company.email],
                html_message=message
            )
        except Exception as e:
            print(f"Failed to send approval email: {e}")

        if company.is_approved:
            messages.success(
                request,
                f'Login credentials resent for {company.name}! Email sent to {company.email}'
            )
        else:
            messages.success(
                request,
                f'Company "{company.name}" approved! Login credentials sent to {company.email}'
            )
        return redirect('company_list')

    return render(request, 'ems/approve_company_registration.html', {
        'company': company
    })

@login_required
def resend_credentials(request, company_id):
    """Resend login credentials for an approved company"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    company = get_object_or_404(Company, id=company_id, is_approved=True)

    if request.method == 'POST':
        try:
            # Find the employer user account for this company
            employer_user = User.objects.filter(
                company=company,
                role='ADMINISTRATOR'
            ).first()

            if not employer_user:
                messages.error(request, f'No employer account found for {company.name}')
                return redirect('company_list')

            # Send credentials email
            try:
                subject = f'Company Registration Approved - {company.name}'
                message = render_to_string('emails/company_approved.html', {
                    'company': company,
                    'employer': employer_user,
                    'login_url': f"{settings.SITE_URL or 'http://127.0.0.1:8000'}/login/",
                    'license_info': {
                        'plan': company.subscription_plan,
                        'license_key': company.license_key,
                        'max_employees': company.max_employees,
                        'expiry': company.license_expiry,
                    }
                })

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [company.email],  # Send to company email
                    html_message=message
                )
            except Exception as e:
                print(f"Failed to send resend credentials email: {e}")

            messages.success(
                request,
                f'Login credentials resent for {company.name}! Email sent to {company.email}'
            )
            return redirect('company_list')

        except Exception as e:
            messages.error(request, f'Error resending credentials: {str(e)}')
            return redirect('company_list')

    return redirect('company_list')


@login_required
def company_users(request, company_id):
    """Manage users for a specific company"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('company_list')

    company = get_object_or_404(Company, id=company_id)
    users = User.objects.filter(company=company).order_by('role', 'email')

    # Group users by role
    hr_users = users.filter(role='HR')
    payroll_users = users.filter(role='PAYROLL')
    payslip_users = users.filter(role='PAYSLIP')
    employees = users.filter(role='EMPLOYEE')

    context = {
        'company': company,
        'hr_users': hr_users,
        'payroll_users': payroll_users,
        'payslip_users': payslip_users,
        'employees': employees,
    }
    return render(request, 'ems/company_users.html', context)


@login_required
def create_company_user(request, company_id, role):
    """Create user for a specific company with specific role"""
    if request.user.role != 'SUPERADMIN':
        messages.error(request, 'Access denied. SuperAdmin privileges required.')
        return redirect('/')

    company = get_object_or_404(Company, id=company_id)

    # Validate role
    valid_roles = ['EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN', 'HR', 'PAYROLL', 'PAYSLIP', 'EMPLOYEE']
    if role not in valid_roles:
        messages.error(request, 'Invalid user role.')
        return redirect('company_users', company_id=company_id)

    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        password = request.POST.get('password')

        if email and first_name and password:
            try:
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    role=role,
                    company=company
                )

                # Create appropriate profile
                if role == 'EMPLOYEE':
                    EmployeeProfile.objects.create(user=user)
                elif role in ['EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN', 'HR', 'PAYROLL', 'PAYSLIP']:
                    EmployerProfile.objects.create(user=user)

                messages.success(request, f'User "{user.email}" created successfully!')
                return redirect('company_users', company_id=company_id)
            except Exception as e:
                messages.error(request, f'Error creating user: {str(e)}')
        else:
            messages.error(request, 'Email, first name, and password are required.')

    context = {
        'company': company,
        'role': role,
        'role_display': dict(User.Role.choices)[role]
    }
    return render(request, 'ems/company_user_form.html', context)


# Dashboard redirect based on user role
@login_required
def dashboard_redirect(request):
    """Redirect users to appropriate dashboard based on their role"""
    if request.user.role == 'SUPERADMIN':
        # Get dashboard statistics for Superuser Admin
        companies = Company.objects.filter(is_approved=True, is_active=True)
        users = User.objects.all()

        context = {
            'user': request.user,
            'total_companies': companies.count(),
            'total_users': users.count(),
            'employer_superusers': users.filter(role='EMPLOYER_SUPERUSER').count(),
            'employer_admins': users.filter(role='EMPLOYER_ADMIN').count(),
            'employees': users.filter(role='EMPLOYEE').count(),
        }
        return render(request, 'ems/superadmin_dashboard.html', context)
    elif request.user.is_administrator or request.user.role == 'ADMINISTRATOR':
        return render(request, 'ems/employer_superuser_dashboard.html')
    elif request.user.is_employer_admin or request.user.role == 'EMPLOYER_ADMIN':
        return render(request, 'ems/employer_admin_dashboard.html')
    elif request.user.is_employee or request.user.role == 'EMPLOYEE':
        return render(request, 'ems/employee_dashboard.html')
    else:
        messages.error(request, 'Invalid user role. Please contact administrator.')
        return redirect('/')

@login_required
def employer_superuser_dashboard(request):
    """Dashboard for Employer Superuser (Company Owner)"""
    if not request.user.is_employer_superuser:
        messages.error(request, 'Access denied. Employer Superuser privileges required.')
        return redirect('/')

    # Get the company this user owns
    try:
        company = request.user.employer_profile.company
    except:
        messages.error(request, 'Company profile not found. Please contact support.')
        return redirect('/')

    from attendance.models import Attendance
    from datetime import date, timedelta

    today = date.today()

    # Get all sub-companies/branches
    branches = Company.objects.filter(parent_company=company)

    # Get all users in this company and its branches
    company_users = User.objects.filter(
        company__in=[company] + list(branches)
    )

    # Statistics
    total_employees = company_users.filter(role='EMPLOYEE').count()
    total_branches = branches.count()
    total_admins = company_users.filter(
        role__in=['EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN']
    ).count()

    # Today's attendance
    active_today = Attendance.objects.filter(
        date=today,
        user__company__in=[company] + list(branches)
    ).count()

    # Recent activities (placeholder - would be from activity log)
    recent_activities = [
        {
            'title': 'New employee joined',
            'description': 'John Doe joined Marketing department',
            'timestamp': timezone.now() - timedelta(hours=2),
            'type': 'employee'
        },
        {
            'title': 'Branch created',
            'description': 'New branch "Downtown Office" was created',
            'timestamp': timezone.now() - timedelta(days=1),
            'type': 'branch'
        },
        {
            'title': 'Payroll processed',
            'description': 'Monthly payroll for 25 employees processed',
            'timestamp': timezone.now() - timedelta(days=2),
            'type': 'payroll'
        }
    ][:5]  # Show only last 5

    # Admin users (other employer superusers and admins)
    admin_users = company_users.filter(
        role__in=['EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN']
    ).exclude(id=request.user.id)[:5]  # Exclude current user, limit to 5

    context = {
        'user': request.user,
        'company': company,
        'total_employees': total_employees,
        'total_branches': total_branches,
        'total_admins': total_admins,
        'active_today': active_today,
        'recent_activities': recent_activities,
        'branches': branches[:5],  # Show only first 5 branches
        'admin_users': admin_users,
    }

    return render(request, 'ems/employer_superuser_dashboard.html', context)

@login_required
def employee_dashboard(request):
    """Dashboard for Employee (Self-service portal)"""
    if not request.user.is_employee:
        messages.error(request, 'Access denied. Employee access required.')
        return redirect('/')

    from attendance.models import Attendance
    from leave.models import LeaveRequest
    from datetime import date, timedelta

    today = date.today()
    current_month = today.replace(day=1)

    # Get employee profile
    try:
        profile = request.user.employee_profile
    except:
        messages.error(request, 'Employee profile not found. Please contact HR.')
        return redirect('/')

    # Statistics
    present_days = Attendance.objects.filter(
        user=request.user,
        status='PRESENT',
        date__gte=current_month
    ).count()

    pending_leaves = LeaveRequest.objects.filter(
        user=request.user,
        status='PENDING'
    ).count()

    working_days = 22  # Standard working days in a month

    # Recent activities (placeholder)
    recent_activities = [
        {
            'title': 'Profile updated',
            'description': 'Your profile information was updated',
            'timestamp': timezone.now() - timedelta(hours=2),
            'status': 'completed'
        },
        {
            'title': 'Payslip generated',
            'description': f'Monthly payslip for {today.strftime("%B %Y")} is available',
            'timestamp': timezone.now() - timedelta(days=1),
            'status': 'completed'
        }
    ][:3]

    # Today's schedule (placeholder)
    today_schedule = [
        {
            'title': 'Regular Work Day',
            'time': '9:00 AM - 5:00 PM',
            'location': 'Office',
            'status': 'active'
        }
    ]

    # Upcoming approved leave
    upcoming_leave = LeaveRequest.objects.filter(
        user=request.user,
        status='APPROVED',
        start_date__gte=today
    ).order_by('start_date')[:3]

    # Total payslips (placeholder - would be from payroll app)
    total_payslips = 12  # Example number

    context = {
        'user': request.user,
        'profile': profile,
        'present_days': present_days,
        'pending_leaves': pending_leaves,
        'working_days': working_days,
        'total_payslips': total_payslips,
        'recent_activities': recent_activities,
        'today_schedule': today_schedule,
        'upcoming_leave': upcoming_leave,
        'today_date': today.strftime('%B %d, %Y'),
    }

    return render(request, 'ems/employee_dashboard.html', context)

@login_required
def employer_admin_dashboard(request):
    """Dashboard for Employer Admin (Branch/Company Admin)"""
    if not request.user.is_employer_admin:
        messages.error(request, 'Access denied. Employer Admin privileges required.')
        return redirect('/')

    # Get the company this admin manages
    try:
        company = request.user.company
    except:
        messages.error(request, 'Company not assigned. Please contact your Employer Superuser.')
        return redirect('/')

    from attendance.models import Attendance
    from leave.models import LeaveRequest
    from datetime import date, timedelta

    today = date.today()

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


def company_profile(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    # Add any additional context you need
    return render(request, 'ems/company_profile.html', {
        'company': company,
    })
    
    return render(request, 'ems/employer_admin_dashboard.html', context)
