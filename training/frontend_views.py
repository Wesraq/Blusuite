from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.utils import timezone
from .models import TrainingProgram, TrainingEnrollment, Certification, TrainingRequest
from accounts.models import CompanyDepartment


@login_required
def training_list(request):
    """
    List training programs based on user role:
    - Admin: All programs
    - Dept Manager/Supervisor: Department + Company-wide programs
    - Employee: Programs available to them
    """
    user = request.user
    
    # Base queryset
    programs = TrainingProgram.objects.filter(is_active=True).select_related('department', 'created_by')
    
    # Apply filtering based on role
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        # Admins see all programs
        programs = programs.filter(created_by__company=user.company)
        view_scope = 'all'
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        # Dept managers see their department programs + company-wide
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        if user_dept:
            programs = programs.filter(
                Q(department=user_dept) | Q(department__isnull=True)
            )
            view_scope = 'department'
        else:
            programs = programs.filter(department__isnull=True)
            view_scope = 'company'
            messages.warning(request, 'You are not assigned to any department.')
    else:
        # Regular employees see company-wide programs
        programs = programs.filter(department__isnull=True)
        view_scope = 'available'
    
    # Search and filters
    search = request.GET.get('search', '')
    program_type_filter = request.GET.get('program_type', '')
    department_filter = request.GET.get('department', '')
    
    if search:
        programs = programs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(provider__icontains=search)
        )
    
    if program_type_filter:
        programs = programs.filter(program_type=program_type_filter)
    
    if department_filter and view_scope == 'all':
        programs = programs.filter(department_id=department_filter)
    
    # Get departments for filter (only for admins)
    departments = None
    if view_scope == 'all':
        departments = CompanyDepartment.objects.filter(company=user.company)
    
    # Get user's enrollments
    user_enrollments = TrainingEnrollment.objects.filter(employee=user).values_list('program_id', flat=True)
    
    # Statistics
    stats = {
        'total': programs.count(),
        'mandatory': programs.filter(is_mandatory=True).count(),
        'enrolled': programs.filter(id__in=user_enrollments).count(),
    }
    
    context = {
        'programs': programs,
        'view_scope': view_scope,
        'stats': stats,
        'departments': departments,
        'program_types': TrainingProgram.ProgramType.choices,
        'search': search,
        'program_type_filter': program_type_filter,
        'department_filter': department_filter,
        'user_enrollments': list(user_enrollments),
    }
    
    return render(request, 'training/training_list.html', context)


@login_required
def training_detail(request, program_id):
    """View training program details"""
    program = get_object_or_404(TrainingProgram, id=program_id)
    user = request.user
    
    # Permission check
    can_view = False
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        can_view = True
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        can_view = program.department == user_dept or program.department is None
    else:
        # Employees can only view company-wide programs
        can_view = program.department is None
    
    if not can_view:
        messages.error(request, 'You do not have permission to view this training program.')
        return redirect('training_list')
    
    # Check if user is enrolled
    user_enrollment = TrainingEnrollment.objects.filter(
        employee=user,
        program=program
    ).first()
    
    # Get all enrollments (for managers/admins)
    can_view_enrollments = user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR', 'DEPARTMENT_MANAGER', 'SUPERVISOR']
    enrollments = program.enrollments.select_related('employee').order_by('-enrollment_date') if can_view_enrollments else []
    
    # Statistics
    enrollment_stats = {
        'total': program.enrollments.count(),
        'completed': program.enrollments.filter(status='COMPLETED').count(),
        'in_progress': program.enrollments.filter(status='IN_PROGRESS').count(),
        'avg_score': program.enrollments.filter(score__isnull=False).aggregate(Avg('score'))['score__avg'],
    }
    
    context = {
        'program': program,
        'user_enrollment': user_enrollment,
        'can_view_enrollments': can_view_enrollments,
        'enrollments': enrollments,
        'enrollment_stats': enrollment_stats,
    }
    
    return render(request, 'training/training_detail.html', context)


@login_required
def training_enroll(request, program_id):
    """Enroll user in training program"""
    program = get_object_or_404(TrainingProgram, id=program_id, is_active=True)
    user = request.user
    
    # Check if program is available to user
    if program.department and user.role not in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR', 'DEPARTMENT_MANAGER', 'SUPERVISOR']:
        messages.error(request, 'This training is only available to specific departments.')
        return redirect('training_detail', program_id=program_id)
    
    # Check if already enrolled
    existing = TrainingEnrollment.objects.filter(employee=user, program=program).exists()
    if existing:
        messages.warning(request, 'You are already enrolled in this training program.')
        return redirect('training_detail', program_id=program_id)
    
    # Create enrollment
    TrainingEnrollment.objects.create(
        employee=user,
        program=program,
        enrollment_date=timezone.now().date(),
        status='ENROLLED'
    )
    
    messages.success(request, f'Successfully enrolled in "{program.title}"!')
    return redirect('training_detail', program_id=program_id)


@login_required
def training_request_list(request):
    """List training requests"""
    user = request.user
    
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        # Admins see all requests
        requests_list = TrainingRequest.objects.filter(department__company=user.company)
        can_approve = True
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        # Dept managers see their own requests
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        if user_dept:
            requests_list = TrainingRequest.objects.filter(department=user_dept)
        else:
            requests_list = TrainingRequest.objects.none()
        can_approve = False
    else:
        messages.error(request, 'You do not have permission to view training requests.')
        return redirect('training_list')
    
    requests_list = requests_list.select_related('department', 'requested_by', 'approved_by').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    
    context = {
        'requests': requests_list,
        'can_approve': can_approve,
        'status_filter': status_filter,
        'statuses': TrainingRequest.Status.choices,
    }
    
    return render(request, 'training/training_request_list.html', context)


@login_required
def training_request_create(request):
    """Create new training request (for dept managers)"""
    user = request.user
    
    if user.role not in ['DEPARTMENT_MANAGER', 'SUPERVISOR', 'ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        messages.error(request, 'Only department managers can request training programs.')
        return redirect('training_list')
    
    # Get user's department
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        departments = CompanyDepartment.objects.filter(company=user.company)
        user_dept = None
    else:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        departments = [user_dept] if user_dept else []
        
        if not user_dept:
            messages.error(request, 'You are not assigned to any department.')
            return redirect('training_list')
    
    if request.method == 'POST':
        department_id = request.POST.get('department')
        training_title = request.POST.get('training_title')
        program_type = request.POST.get('program_type')
        description = request.POST.get('description')
        target_employees = request.POST.get('target_employees', 1)
        duration_hours = request.POST.get('duration_hours')
        estimated_cost = request.POST.get('estimated_cost', None)
        preferred_provider = request.POST.get('preferred_provider', '')
        priority = request.POST.get('priority', 'MEDIUM')
        business_justification = request.POST.get('business_justification')
        urgency_reason = request.POST.get('urgency_reason', '')
        
        # Get department
        if user_dept:
            department = user_dept
        else:
            department = get_object_or_404(CompanyDepartment, id=department_id, company=user.company)
        
        # Create request
        training_request = TrainingRequest.objects.create(
            department=department,
            requested_by=user,
            training_title=training_title,
            program_type=program_type,
            description=description,
            target_employees=int(target_employees),
            duration_hours=duration_hours,
            estimated_cost=estimated_cost if estimated_cost else None,
            preferred_provider=preferred_provider,
            priority=priority,
            business_justification=business_justification,
            urgency_reason=urgency_reason,
            status='PENDING'
        )
        
        messages.success(request, f'Training request submitted successfully! Request ID: {training_request.id}')
        return redirect('training_request_list')
    
    context = {
        'departments': departments,
        'user_dept': user_dept,
        'program_types': TrainingProgram.ProgramType.choices,
        'priorities': TrainingRequest.Priority.choices,
    }
    
    return render(request, 'training/training_request_create.html', context)


@login_required
def training_request_approve(request, request_id):
    """Approve or reject training request (admin only)"""
    user = request.user
    
    if user.role not in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        messages.error(request, 'Only administrators can approve training requests.')
        return redirect('training_request_list')
    
    training_request = get_object_or_404(TrainingRequest, id=request_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        if action == 'approve':
            training_request.status = 'APPROVED'
            training_request.approved_by = user
            training_request.approval_date = timezone.now()
            training_request.admin_notes = admin_notes
            training_request.save()
            
            messages.success(request, f'Training request approved successfully!')
        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '')
            training_request.status = 'REJECTED'
            training_request.approved_by = user
            training_request.approval_date = timezone.now()
            training_request.rejection_reason = rejection_reason
            training_request.admin_notes = admin_notes
            training_request.save()
            
            messages.warning(request, f'Training request rejected.')
        
        return redirect('training_request_list')
    
    context = {
        'training_request': training_request,
    }
    
    return render(request, 'training/training_request_approve.html', context)


@login_required
def my_training(request):
    """View user's enrolled training programs"""
    user = request.user
    
    enrollments = TrainingEnrollment.objects.filter(
        employee=user
    ).select_related('program').order_by('-enrollment_date')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        enrollments = enrollments.filter(status=status_filter)
    
    # Calculate total hours
    total_hours = sum([e.program.duration_hours for e in enrollments if e.status == 'COMPLETED'])
    
    # Statistics
    stats = {
        'total_enrolled': enrollments.count() if not status_filter else TrainingEnrollment.objects.filter(employee=user).count(),
        'completed': enrollments.filter(status='COMPLETED').count() if not status_filter else TrainingEnrollment.objects.filter(employee=user, status='COMPLETED').count(),
        'in_progress': enrollments.filter(status='IN_PROGRESS').count() if not status_filter else TrainingEnrollment.objects.filter(employee=user, status='IN_PROGRESS').count(),
        'total_hours': total_hours,
    }
    
    context = {
        'enrollments': enrollments,
        'stats': stats,
        'current_filter': status_filter,
    }
    
    return render(request, 'training/my_training.html', context)


@login_required
def department_training_dashboard(request):
    """Dashboard for department managers to see training overview"""
    user = request.user
    
    if user.role not in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        messages.error(request, 'Only department managers can access this dashboard.')
        return redirect('training_list')
    
    user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
    
    if not user_dept:
        messages.error(request, 'You are not assigned to any department.')
        return redirect('training_list')
    
    # Get department programs
    dept_programs = TrainingProgram.objects.filter(department=user_dept)
    active_programs = dept_programs.filter(is_active=True)
    
    # Get department employees
    dept_employees = user.company.users.filter(
        employee_profile__department=user_dept
    )
    
    # Get enrollments for dept employees
    dept_enrollments = TrainingEnrollment.objects.filter(
        employee__in=dept_employees
    ).select_related('employee', 'program')
    
    # Get training requests
    dept_requests = TrainingRequest.objects.filter(
        department=user_dept
    ).select_related('requested_by', 'approved_by')
    
    # Statistics
    completed_count = dept_enrollments.filter(status='COMPLETED').count()
    in_progress_count = dept_enrollments.filter(status='IN_PROGRESS').count()
    total_enrolled = dept_enrollments.count()
    
    stats = {
        'total_programs': dept_programs.count(),
        'active_programs': active_programs.count(),
        'total_enrolled': total_enrolled,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'pending_requests': dept_requests.filter(status='PENDING').count(),
        'completion_rate': (completed_count / total_enrolled * 100) if total_enrolled > 0 else 0,
    }
    
    # Recent data
    active_programs_list = active_programs.order_by('-created_at')[:5]
    recent_requests = dept_requests.order_by('-created_at')[:5]
    
    context = {
        'department': user_dept,
        'stats': stats,
        'active_programs': active_programs_list,
        'recent_requests': recent_requests,
    }
    
    return render(request, 'training/department_training_dashboard.html', context)
