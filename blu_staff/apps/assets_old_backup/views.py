import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.hashers import check_password
from django.contrib import messages

from .models import EmployeeAsset, AssetMaintenanceLog, AssetRequest, AssetCollectionRecord
from .forms import EmployeeAssetForm, AssetMaintenanceLogForm, AssetCollectionForm
from blu_staff.apps.accounts.models import CompanyDepartment, EmployeeProfile
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden

User = get_user_model()


def _get_asset_or_404(asset_id, request):
    """Resolve asset by id. Tries tenant, then company, then bare lookup."""
    from django.http import Http404
    tenant = getattr(request, 'tenant', None)
    company = getattr(request.user, 'company', None)
    # Try tenant-scoped lookup first
    if tenant:
        asset = EmployeeAsset.objects.filter(id=asset_id, tenant=tenant).first()
        if asset:
            return asset
    # Fall back to company-scoped lookup
    if company:
        asset = EmployeeAsset.objects.filter(
            Q(id=asset_id),
            Q(department__company=company) | Q(employee__company=company)
        ).first()
        if asset:
            return asset
    # Last resort: bare lookup (for superadmins with no company)
    if not tenant and not company:
        return get_object_or_404(EmployeeAsset, id=asset_id)
    raise Http404('No EmployeeAsset matches the given query.')


@login_required
def asset_list(request):
    """
    List assets based on user role:
    - Admin/SuperAdmin: All assets
    - Dept Manager/Supervisor: Department assets only
    - Employee: Only assets assigned to them
    """
    user = request.user
    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)

    # Base queryset — try tenant first, fall back to company
    base_qs = EmployeeAsset.objects.select_related('employee', 'department', 'category', 'custodian')
    if tenant:
        assets = base_qs.filter(tenant=tenant)
        if not assets.exists() and company:
            # Tenant has no assets — fall back to company scope
            assets = base_qs.filter(
                Q(department__company=company) | Q(employee__company=company)
            )
    elif company:
        assets = base_qs.filter(
            Q(department__company=company) | Q(employee__company=company)
        )
    else:
        assets = base_qs.none()
    
    # Apply department filtering based on role
    if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        # Admins see all company assets (already filtered above)
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
    custodian_filter = request.GET.get('custodian', '')
    sort = request.GET.get('sort', '-created_at')
    
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

    if custodian_filter:
        assets = assets.filter(custodian_id=custodian_filter)

    # Sort whitelist
    sort_fields = {
        'created': '-created_at',
        'assigned': '-assigned_date',
        'name': 'name',
        'status': 'status',
        'type': 'asset_type',
    }
    assets = assets.order_by(sort_fields.get(sort, '-created_at'))

    paginator = Paginator(assets, 15)
    page_number = request.GET.get('page')
    assets_page = paginator.get_page(page_number)

    # Get department list for filter (only for admins)
    departments = None
    if view_scope == 'all' and company:
        departments = CompanyDepartment.objects.filter(company=company)
    custodians = User.objects.filter(
        role__in=['ADMIN', 'EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN', 'DEPARTMENT_MANAGER', 'SUPERVISOR'],
        company=user.company
    )
    
    # Statistics
    stats = {
        'total': assets.count(),
        'assigned': assets.filter(status='ASSIGNED').count(),
        'available': assets.filter(status='AVAILABLE').count(),
        'in_repair': assets.filter(status='IN_REPAIR').count(),
    }
    
    # Determine base template based on user role
    if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        base_template = 'ems/base_employer.html'
    else:
        base_template = 'ems/base_employee.html'

    # Determine if user can manage assets (edit/assign/repair/return)
    can_manage_assets = user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']

    context = {
        'assets': assets_page,
        'view_scope': view_scope,
        'stats': stats,
        'departments': departments,
        'custodians': custodians,
        'asset_statuses': EmployeeAsset.Status.choices,
        'asset_types': EmployeeAsset.AssetType.choices,
        'search': search,
        'status_filter': status_filter,
        'asset_type_filter': asset_type_filter,
        'department_filter': department_filter,
        'custodian_filter': custodian_filter,
        'sort': sort,
        'paginator': paginator,
        'page_obj': assets_page,
        'base_template': base_template,
        'can_manage_assets': can_manage_assets,
    }
    
    return render(request, 'assets/asset_list.html', context)


@login_required
def asset_detail(request, asset_id):
    """View asset details with permission check"""
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    user = request.user
    latest_collection = AssetCollectionRecord.objects.filter(asset=asset).order_by('-signed_at').first()
    
    # Permission check
    can_view = False
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
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

    assign_form = EmployeeAssetForm(instance=asset, request=request)
    maintenance_form = AssetMaintenanceLogForm(request=request)
    initial_employee = ''
    initial_position = ''
    if asset.employee:
        full_name = asset.employee.get_full_name()
        position = getattr(getattr(asset.employee, 'employee_profile', None), 'job_title', '') or getattr(getattr(asset.employee, 'employee_profile', None), 'department', None)
        dept_name = ''
        if position and hasattr(position, 'name'):
            dept_name = position.name
            position = ''
        initial_employee = full_name
        initial_position = position or dept_name
    collection_form = AssetCollectionForm(initial={'employee': initial_employee, 'position': initial_position})
    # E-form UX tweaks: prefill and lock when assigned
    if asset.employee:
        collection_form.fields['employee'].widget.attrs.update({'readonly': 'readonly'})
        collection_form.fields['position'].widget.attrs.update({'readonly': 'readonly'})
    collection_form.fields['employee'].widget.attrs.update({'placeholder': 'Employee full name'})
    collection_form.fields['position'].widget.attrs.update({'placeholder': 'Position or Department'})
    collection_form.fields['notes'].widget.attrs.update({'placeholder': 'Notes about handover (optional)'})
    employees = User.objects.filter(role='EMPLOYEE', company=user.company)
    
    # Determine base template based on user role
    if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        base_template = 'ems/base_employer.html'
    else:
        base_template = 'ems/base_employee.html'

    # Determine if user can manage assets (edit/assign/repair/return)
    can_manage_assets = user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']

    context = {
        'asset': asset,
        'maintenance_logs': maintenance_logs,
        'assign_form': assign_form,
        'maintenance_form': maintenance_form,
        'collection_form': collection_form,
        'employees': employees,
        'latest_collection': latest_collection,
        'base_template': base_template,
        'can_manage_assets': can_manage_assets,
    }
    
    return render(request, 'assets/asset_detail.html', context)


@login_required
def asset_create(request):
    tenant = getattr(request, 'tenant', None)
    user = request.user

    if request.method == 'POST':
        form = EmployeeAssetForm(request.POST, request=request)
        if form.is_valid():
            asset = form.save()
            messages.success(request, 'Asset created successfully.')
            return redirect('asset_detail', asset_id=asset.id)
    else:
        form = EmployeeAssetForm(request=request)

    return render(request, 'assets/asset_form.html', {'form': form, 'is_edit': False})


@login_required
def asset_edit(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    if request.method == 'POST':
        form = EmployeeAssetForm(request.POST, instance=asset, request=request)
        if form.is_valid():
            asset = form.save()
            messages.success(request, 'Asset updated successfully.')
            return redirect('asset_detail', asset_id=asset.id)
    else:
        form = EmployeeAssetForm(instance=asset, request=request)

    return render(request, 'assets/asset_form.html', {'form': form, 'is_edit': True, 'asset': asset})


@login_required
def asset_assign(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    user = request.user

    if asset.status in ['IN_REPAIR', 'RETIRED', 'LOST']:
        messages.error(request, f'Cannot assign while status is {asset.get_status_display()}.')
        return redirect('asset_detail', asset_id=asset.id)

    employee_id = request.POST.get('employee')
    notes = request.POST.get('notes', '')
    employee = None
    if employee_id:
        employee = get_object_or_404(User, id=employee_id, company=user.company, role='EMPLOYEE')

    asset.employee = employee
    asset.notes = notes if notes else asset.notes
    asset.assigned_by = user
    
    # Update status based on assignment
    if employee:
        asset.status = EmployeeAsset.Status.ASSIGNED
        asset.assigned_date = timezone.now().date()
    else:
        asset.status = EmployeeAsset.Status.AVAILABLE
        asset.assigned_date = None
    
    asset.save()
    messages.success(request, f'Asset assigned to {employee.get_full_name()}' if employee else 'Asset unassigned.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def asset_unassign(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    asset.employee = None
    asset.return_date = timezone.now().date()
    asset.save()
    messages.success(request, 'Asset unassigned and marked available.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def asset_return(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    asset.employee = None
    asset.status = EmployeeAsset.Status.AVAILABLE
    asset.return_date = timezone.now().date()
    asset.save()
    messages.success(request, 'Asset marked as returned and available.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def asset_send_to_repair(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    asset.employee = None
    asset.status = EmployeeAsset.Status.IN_REPAIR
    asset.return_date = timezone.now().date()
    asset.save()
    messages.success(request, 'Asset sent to repair and unassigned.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def maintenance_create(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    if request.method == 'POST':
        form = AssetMaintenanceLogForm(request.POST, request=request)
        if form.is_valid():
            log = form.save(commit=False)
            log.asset = asset
            log.tenant = tenant
            log.save()
            messages.success(request, 'Maintenance log added.')
        else:
            messages.error(request, 'Could not save maintenance log. Please check the form.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def asset_collection_create(request, asset_id):
    """Collect handover/collection signature record."""
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    user = request.user

    if request.method == 'POST':
        form = AssetCollectionForm(request.POST)
        if form.is_valid():
            use_saved = form.cleaned_data.get('use_saved_signature')
            pin = form.cleaned_data.get('pin')
            signature_data = form.cleaned_data.get('signature_data')

            # If user wants to use saved signature, validate PIN and load signature image
            if use_saved:
                profile = getattr(user, 'employee_profile', None)
                if not profile or not profile.signature_image or not profile.signature_pin_hash:
                    messages.error(request, 'No saved signature or PIN found on your profile.')
                    return redirect('asset_detail', asset_id=asset.id)
                if not pin or not check_password(pin, profile.signature_pin_hash):
                    messages.error(request, 'Invalid PIN for signature.')
                    return redirect('asset_detail', asset_id=asset.id)
                # Convert signature image to base64 data URI
                try:
                    image_content = profile.signature_image.read()
                    encoded = base64.b64encode(image_content).decode('utf-8')
                    signature_data = f"data:image/png;base64,{encoded}"
                except Exception:
                    messages.error(request, 'Could not load saved signature image.')
                    return redirect('asset_detail', asset_id=asset.id)
            else:
                if not signature_data:
                    messages.error(request, 'Signature is required.')
                    return redirect('asset_detail', asset_id=asset.id)

            AssetCollectionRecord.objects.create(
                tenant=tenant,
                asset=asset,
                employee_name=form.cleaned_data['employee'],
                position=form.cleaned_data.get('position') or '',
                notes=form.cleaned_data.get('notes') or '',
                signature_data=signature_data,
                signed_by=user,
            )
            messages.success(request, 'Collection record saved with signature.')
        else:
            messages.error(request, 'Please correct the collection form.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def asset_collection_print(request, asset_id, collection_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    collection = get_object_or_404(AssetCollectionRecord, id=collection_id, asset=asset)
    user = request.user

    # Basic permission alignment with asset_detail
    can_view = False
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        can_view = True
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        can_view = asset.department == user_dept
    else:
        can_view = asset.employee == user or collection.signed_by == user

    if not can_view:
        return HttpResponseForbidden("You do not have permission to view this collection record.")

    context = {
        'asset': asset,
        'collection': collection,
        'now': timezone.now(),
    }
    return render(request, 'assets/asset_collection_print.html', context)

@login_required
def asset_request_list(request):
    """
    List asset requests with multi-level approval filtering:
    - Admin: All requests + requests pending admin approval
    - HR: Requests pending HR approval
    - Dept Manager/Supervisor: Department requests + requests pending their approval
    - Employee: Their own requests
    """
    user = request.user
    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)
    user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None

    # Determine what requests user can see
    if user.role in ['ADMIN', 'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        # Admins see all requests scoped to tenant or company
        if tenant:
            requests_list = AssetRequest.objects.filter(department__company=company, tenant=tenant)
            if not requests_list.exists() and company:
                requests_list = AssetRequest.objects.filter(department__company=company)
        elif company:
            requests_list = AssetRequest.objects.filter(department__company=company)
        else:
            requests_list = AssetRequest.objects.none()
        view_scope = 'all'
        
    elif hasattr(user, 'employee_profile') and user.employee_profile.employee_type == 'HR':
        # HR sees all requests, especially those pending HR approval
        if company:
            requests_list = AssetRequest.objects.filter(department__company=company)
        else:
            requests_list = AssetRequest.objects.none()
        view_scope = 'hr'
        
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        # Managers/Supervisors see their department's requests
        if user_dept:
            requests_list = AssetRequest.objects.filter(department=user_dept)
        else:
            requests_list = AssetRequest.objects.none()
        view_scope = 'department'
        
    else:
        # Regular employees see only their own requests
        requests_list = AssetRequest.objects.filter(requested_by=user)
        view_scope = 'personal'
    
    requests_list = requests_list.select_related(
        'department', 'requested_by', 'approved_by',
        'supervisor_approved_by', 'manager_approved_by', 'hr_approved_by'
    ).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    
    # Calculate pending approvals for current user
    pending_my_approval = []
    for req in requests_list:
        if req.can_user_approve(user):
            pending_my_approval.append(req.id)
    
    # Determine base template
    if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        base_template = 'ems/base_employer.html'
    else:
        base_template = 'ems/base_employee.html'
    
    context = {
        'requests': requests_list,
        'pending_my_approval': pending_my_approval,
        'view_scope': view_scope,
        'status_filter': status_filter,
        'statuses': AssetRequest.Status.choices,
        'base_template': base_template,
    }
    
    return render(request, 'assets/asset_request_list.html', context)


@login_required
def asset_request_create(request):
    """Create new asset request (for all employees)"""
    user = request.user
    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)

    # Get user's department
    if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        departments = CompanyDepartment.objects.filter(company=company) if company else CompanyDepartment.objects.none()
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
            department = get_object_or_404(CompanyDepartment, id=department_id, company=company)
        
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
        
        # Initialize approval workflow based on department
        workflow = asset_request.get_approval_workflow()
        if workflow:
            asset_request.current_approval_level = workflow[0]
            asset_request.save()
        
        pending_approver = asset_request.get_pending_approver_role()
        messages.success(request, f'Asset request submitted successfully! Request ID: {asset_request.id}. Pending approval from: {pending_approver}')
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
    """Multi-level approval for asset requests with department-based workflow"""
    user = request.user
    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)
    
    # Get asset request with proper scoping
    asset_request = AssetRequest.objects.filter(id=request_id)
    if tenant:
        scoped = asset_request.filter(tenant=tenant)
        if scoped.exists():
            asset_request = scoped.first()
        elif company:
            asset_request = asset_request.filter(department__company=company).first()
        else:
            asset_request = asset_request.first()
    elif company:
        asset_request = asset_request.filter(department__company=company).first()
    else:
        asset_request = asset_request.first()
    
    if not asset_request:
        from django.http import Http404
        raise Http404('No AssetRequest matches the given query.')
    
    # Check if user can approve at current level
    if not asset_request.can_user_approve(user):
        messages.error(request, 'You do not have permission to approve this request at the current level.')
        return redirect('asset_request_detail', request_id=asset_request.id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            current_level = asset_request.current_approval_level
            
            # Record approval at current level
            if current_level == AssetRequest.ApprovalLevel.SUPERVISOR:
                asset_request.supervisor_approved = True
                asset_request.supervisor_approved_by = user
                asset_request.supervisor_approval_date = timezone.now()
                messages.success(request, 'Request approved at Supervisor level.')
                
            elif current_level == AssetRequest.ApprovalLevel.MANAGER:
                asset_request.manager_approved = True
                asset_request.manager_approved_by = user
                asset_request.manager_approval_date = timezone.now()
                messages.success(request, 'Request approved at Manager level.')
                
            elif current_level == AssetRequest.ApprovalLevel.HR:
                asset_request.hr_approved = True
                asset_request.hr_approved_by = user
                asset_request.hr_approval_date = timezone.now()
                messages.success(request, 'Request approved at HR level.')
                
            elif current_level == AssetRequest.ApprovalLevel.ADMIN:
                # Final approval
                asset_request.status = AssetRequest.Status.APPROVED
                asset_request.approved_by = user
                asset_request.approval_date = timezone.now()
                messages.success(request, 'Request fully approved! Ready for procurement.')
            
            # Add notes if provided
            if notes:
                if asset_request.admin_notes:
                    asset_request.admin_notes += f"\n[{user.get_full_name()} - {timezone.now().strftime('%Y-%m-%d %H:%M')}]: {notes}"
                else:
                    asset_request.admin_notes = f"[{user.get_full_name()} - {timezone.now().strftime('%Y-%m-%d %H:%M')}]: {notes}"
            
            # Move to next approval level
            next_level = asset_request.get_next_approval_level()
            if next_level:
                asset_request.current_approval_level = next_level
                next_approver = asset_request.get_pending_approver_role()
                messages.info(request, f'Request forwarded to {next_approver} for approval.')
            
            asset_request.save()
            
        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '')
            if not rejection_reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('asset_request_detail', request_id=asset_request.id)
            
            asset_request.status = AssetRequest.Status.REJECTED
            asset_request.approved_by = user
            asset_request.approval_date = timezone.now()
            asset_request.rejection_reason = rejection_reason
            
            if notes:
                asset_request.admin_notes = notes
            asset_request.save()
            
            messages.warning(request, f'Asset request rejected.')
        
        return redirect('asset_request_list')
    
    context = {
        'asset_request': asset_request,
    }
    
    return render(request, 'assets/asset_request_approve.html', context)


@login_required
def asset_request_detail(request, request_id):
    """View detailed asset request with approval timeline"""
    user = request.user
    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)
    
    # Get asset request with proper scoping
    asset_request = AssetRequest.objects.filter(id=request_id)
    if tenant:
        scoped = asset_request.filter(tenant=tenant)
        if scoped.exists():
            asset_request = scoped.first()
        elif company:
            asset_request = asset_request.filter(department__company=company).first()
        else:
            asset_request = asset_request.first()
    elif company:
        asset_request = asset_request.filter(department__company=company).first()
    else:
        asset_request = asset_request.first()
    
    if not asset_request:
        from django.http import Http404
        raise Http404('No AssetRequest matches the given query.')
    
    # Check permissions - user must be requester, approver, or admin
    can_view = False
    if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        can_view = True
    elif asset_request.requested_by == user:
        can_view = True
    elif asset_request.can_user_approve(user):
        can_view = True
    elif hasattr(user, 'employee_profile'):
        # Department managers and supervisors can view their department's requests
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        if user_dept == asset_request.department and user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
            can_view = True
        # HR can view all requests
        if user.employee_profile.employee_type == 'HR':
            can_view = True
    
    if not can_view:
        messages.error(request, 'You do not have permission to view this request.')
        return redirect('asset_request_list')
    
    # Build approval timeline
    workflow = asset_request.get_approval_workflow()
    timeline = []
    
    for level in workflow:
        step = {
            'level': level,
            'label': asset_request.ApprovalLevel(level).label,
            'approved': False,
            'approver': None,
            'date': None,
            'is_current': level == asset_request.current_approval_level,
            'is_pending': False
        }
        
        if level == AssetRequest.ApprovalLevel.SUPERVISOR:
            step['approved'] = asset_request.supervisor_approved
            step['approver'] = asset_request.supervisor_approved_by
            step['date'] = asset_request.supervisor_approval_date
        elif level == AssetRequest.ApprovalLevel.MANAGER:
            step['approved'] = asset_request.manager_approved
            step['approver'] = asset_request.manager_approved_by
            step['date'] = asset_request.manager_approval_date
        elif level == AssetRequest.ApprovalLevel.HR:
            step['approved'] = asset_request.hr_approved
            step['approver'] = asset_request.hr_approved_by
            step['date'] = asset_request.hr_approval_date
        elif level == AssetRequest.ApprovalLevel.ADMIN:
            step['approved'] = asset_request.status == AssetRequest.Status.APPROVED
            step['approver'] = asset_request.approved_by
            step['date'] = asset_request.approval_date
        
        # Mark as pending if it's current and not approved
        if step['is_current'] and not step['approved'] and asset_request.status == AssetRequest.Status.PENDING:
            step['is_pending'] = True
        
        timeline.append(step)
    
    # Check if current user can approve
    can_approve = asset_request.can_user_approve(user)
    
    # Determine base template
    if user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        base_template = 'ems/base_employer.html'
    else:
        base_template = 'ems/base_employee.html'
    
    context = {
        'asset_request': asset_request,
        'timeline': timeline,
        'can_approve': can_approve,
        'base_template': base_template,
    }
    
    return render(request, 'assets/asset_request_detail.html', context)


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
    tenant = getattr(request, 'tenant', None)
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
