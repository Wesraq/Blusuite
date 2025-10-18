from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from .models import EmployeeAsset, AssetCategory, AssetMaintenanceLog, AssetRequest
from accounts.models import CompanyDepartment


@login_required
def asset_list(request):
    """
    List assets based on user role:
    - Admin/SuperAdmin: All assets
    - Dept Manager/Supervisor: Department assets only
    - Employee: Only assets assigned to them
    """
    user = request.user
    
    # Base queryset
    assets = EmployeeAsset.objects.select_related('employee', 'department', 'category', 'custodian')
    
    # Apply department filtering based on role
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        # Admins see all assets
        assets = assets.filter(employee__company=user.company)
        view_scope = 'all'
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        # Department managers see only their department's assets
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        if user_dept:
            assets = assets.filter(department=user_dept)
            view_scope = 'department'
        else:
            assets = assets.none()
            view_scope = 'none'
            messages.warning(request, 'You are not assigned to any department.')
    else:
        # Regular employees see only their own assets
        assets = assets.filter(employee=user)
        view_scope = 'personal'
    
    # Search and filters
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    asset_type_filter = request.GET.get('asset_type', '')
    department_filter = request.GET.get('department', '')
    
    if search:
        assets = assets.filter(
            Q(asset_tag__icontains=search) |
            Q(name__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search)
        )
    
    if status_filter:
        assets = assets.filter(status=status_filter)
    
    if asset_type_filter:
        assets = assets.filter(asset_type=asset_type_filter)
    
    if department_filter and view_scope == 'all':
        assets = assets.filter(department_id=department_filter)
    
    # Get department list for filter (only for admins)
    departments = None
    if view_scope == 'all':
        departments = CompanyDepartment.objects.filter(company=user.company)
    
    # Statistics
    stats = {
        'total': assets.count(),
        'assigned': assets.filter(status='ASSIGNED').count(),
        'available': assets.filter(status='AVAILABLE').count(),
        'in_repair': assets.filter(status='IN_REPAIR').count(),
    }
    
    context = {
        'assets': assets,
        'view_scope': view_scope,
        'stats': stats,
        'departments': departments,
        'asset_statuses': EmployeeAsset.Status.choices,
        'asset_types': EmployeeAsset.AssetType.choices,
        'search': search,
        'status_filter': status_filter,
        'asset_type_filter': asset_type_filter,
        'department_filter': department_filter,
    }
    
    return render(request, 'assets/asset_list.html', context)


@login_required
def asset_detail(request, asset_id):
    """View asset details with permission check"""
    asset = get_object_or_404(EmployeeAsset, id=asset_id)
    user = request.user
    
    # Permission check
    can_view = False
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        can_view = True
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        can_view = asset.department == user_dept
    else:
        can_view = asset.employee == user
    
    if not can_view:
        messages.error(request, 'You do not have permission to view this asset.')
        return redirect('asset_list')
    
    # Get maintenance history
    maintenance_logs = asset.maintenance_logs.all()
    
    context = {
        'asset': asset,
        'maintenance_logs': maintenance_logs,
    }
    
    return render(request, 'assets/asset_detail.html', context)


@login_required
def asset_request_list(request):
    """
    List asset requests:
    - Admin: All requests
    - Dept Manager: Their department's requests
    """
    user = request.user
    
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        # Admins see all requests
        requests_list = AssetRequest.objects.filter(department__company=user.company)
        can_approve = True
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        # Dept managers see their own requests
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        if user_dept:
            requests_list = AssetRequest.objects.filter(department=user_dept)
        else:
            requests_list = AssetRequest.objects.none()
        can_approve = False
    else:
        messages.error(request, 'You do not have permission to view asset requests.')
        return redirect('asset_list')
    
    requests_list = requests_list.select_related('department', 'requested_by', 'approved_by').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    
    context = {
        'requests': requests_list,
        'can_approve': can_approve,
        'status_filter': status_filter,
        'statuses': AssetRequest.Status.choices,
    }
    
    return render(request, 'assets/asset_request_list.html', context)


@login_required
def asset_request_create(request):
    """Create new asset request (for dept managers)"""
    user = request.user
    
    if user.role not in ['DEPARTMENT_MANAGER', 'SUPERVISOR', 'ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        messages.error(request, 'Only department managers can request assets.')
        return redirect('asset_list')
    
    # Get user's department
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        departments = CompanyDepartment.objects.filter(company=user.company)
        user_dept = None
    else:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        departments = [user_dept] if user_dept else []
        
        if not user_dept:
            messages.error(request, 'You are not assigned to any department.')
            return redirect('asset_list')
    
    if request.method == 'POST':
        department_id = request.POST.get('department')
        asset_type = request.POST.get('asset_type')
        asset_name = request.POST.get('asset_name')
        description = request.POST.get('description')
        quantity = request.POST.get('quantity', 1)
        estimated_cost = request.POST.get('estimated_cost', None)
        priority = request.POST.get('priority', 'MEDIUM')
        urgency_reason = request.POST.get('urgency_reason', '')
        
        # Get department
        if user_dept:
            department = user_dept
        else:
            department = get_object_or_404(CompanyDepartment, id=department_id, company=user.company)
        
        # Create request
        asset_request = AssetRequest.objects.create(
            department=department,
            requested_by=user,
            asset_type=asset_type,
            asset_name=asset_name,
            description=description,
            quantity=int(quantity),
            estimated_cost=estimated_cost if estimated_cost else None,
            priority=priority,
            urgency_reason=urgency_reason,
            status='PENDING'
        )
        
        messages.success(request, f'Asset request submitted successfully! Request ID: {asset_request.id}')
        return redirect('asset_request_list')
    
    context = {
        'departments': departments,
        'user_dept': user_dept,
        'asset_types': EmployeeAsset.AssetType.choices,
        'priorities': AssetRequest.Priority.choices,
    }
    
    return render(request, 'assets/asset_request_create.html', context)


@login_required
def asset_request_approve(request, request_id):
    """Approve or reject asset request (admin only)"""
    user = request.user
    
    if user.role not in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR']:
        messages.error(request, 'Only administrators can approve asset requests.')
        return redirect('asset_request_list')
    
    asset_request = get_object_or_404(AssetRequest, id=request_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        if action == 'approve':
            asset_request.status = 'APPROVED'
            asset_request.approved_by = user
            asset_request.approval_date = timezone.now()
            asset_request.admin_notes = admin_notes
            asset_request.save()
            
            messages.success(request, f'Asset request approved successfully!')
        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '')
            asset_request.status = 'REJECTED'
            asset_request.approved_by = user
            asset_request.approval_date = timezone.now()
            asset_request.rejection_reason = rejection_reason
            asset_request.admin_notes = admin_notes
            asset_request.save()
            
            messages.warning(request, f'Asset request rejected.')
        
        return redirect('asset_request_list')
    
    context = {
        'asset_request': asset_request,
    }
    
    return render(request, 'assets/asset_request_approve.html', context)


@login_required
def department_asset_dashboard(request):
    """Dashboard for department managers to see their asset overview"""
    user = request.user
    
    if user.role not in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        messages.error(request, 'Only department managers can access this dashboard.')
        return redirect('asset_list')
    
    user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
    
    if not user_dept:
        messages.error(request, 'You are not assigned to any department.')
        return redirect('asset_list')
    
    # Get department assets
    dept_assets = EmployeeAsset.objects.filter(department=user_dept)
    
    # Statistics
    stats = {
        'total_assets': dept_assets.count(),
        'assigned': dept_assets.filter(status='ASSIGNED').count(),
        'available': dept_assets.filter(status='AVAILABLE').count(),
        'in_repair': dept_assets.filter(status='IN_REPAIR').count(),
        'by_type': dept_assets.values('asset_type').annotate(count=Count('id')),
    }
    
    # Recent assets
    recent_assets = dept_assets.order_by('-created_at')[:10]
    
    # Pending requests
    pending_requests = AssetRequest.objects.filter(
        department=user_dept,
        status='PENDING'
    ).count()
    
    context = {
        'department': user_dept,
        'stats': stats,
        'recent_assets': recent_assets,
        'pending_requests': pending_requests,
    }
    
    return render(request, 'assets/department_dashboard.html', context)
