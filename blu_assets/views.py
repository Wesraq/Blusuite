import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.contrib.auth.hashers import check_password
from django.contrib import messages

from .models import EmployeeAsset, AssetMaintenanceLog, AssetRequest, AssetCollectionRecord, AssetCategory
from .forms import EmployeeAssetForm, AssetMaintenanceLogForm, AssetCollectionForm
from blu_staff.apps.accounts.models import CompanyDepartment, EmployeeProfile
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden, HttpResponse

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
def ams_dashboard(request):
    """AMS Suite Dashboard - comprehensive overview with analytics"""
    user = request.user
    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)
    now = timezone.now()
    today = now.date()

    # Base queryset scoped to tenant/company — combine both paths to catch all assets
    base_qs = EmployeeAsset.objects.select_related('employee', 'department', 'category', 'custodian')
    if company:
        company_q = Q(department__company=company) | Q(employee__company=company)
        if tenant:
            assets = base_qs.filter(Q(tenant=tenant) | company_q).distinct()
        else:
            assets = base_qs.filter(company_q).distinct()
    elif tenant:
        assets = base_qs.filter(tenant=tenant)
    else:
        assets = base_qs.none()

    # Role-based scoping
    is_admin = user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']
    if is_admin:
        pass  # See all
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        if user_dept:
            assets = assets.filter(department=user_dept)
        else:
            assets = assets.none()
    else:
        assets = assets.filter(employee=user)

    # ── Core Stats ──
    total = assets.count()
    assigned = assets.filter(status='ASSIGNED').count()
    available = assets.filter(status='AVAILABLE').count()
    in_repair = assets.filter(status='IN_REPAIR').count()
    retired = assets.filter(status='RETIRED').count()
    lost = assets.filter(status='LOST').count()
    active_assets = total - retired - lost

    # Value stats
    from django.db.models import Avg, Max, Min
    value_agg = assets.exclude(purchase_price__isnull=True).aggregate(
        total_val=Sum('purchase_price'),
        avg_val=Avg('purchase_price'),
        max_val=Max('purchase_price'),
        min_val=Min('purchase_price'),
    )
    total_value = value_agg['total_val'] or 0
    avg_value = value_agg['avg_val'] or 0

    # Utilization rate (assigned / active assets)
    utilization_rate = round((assigned / active_assets * 100), 1) if active_assets > 0 else 0

    # ── Condition Breakdown ──
    condition_breakdown = list(
        assets.exclude(status__in=['RETIRED', 'LOST'])
        .values('condition')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    condition_display = dict(EmployeeAsset.Condition.choices)

    # ── Type Breakdown ──
    type_breakdown = list(assets.values('asset_type').annotate(count=Count('id')).order_by('-count')[:8])

    # ── Warranty Summary ──
    warranty_expiring = assets.filter(
        warranty_expiry__isnull=False,
        warranty_expiry__lte=today + timezone.timedelta(days=30),
        warranty_expiry__gte=today
    ).count()
    warranty_expired = assets.filter(
        warranty_expiry__isnull=False,
        warranty_expiry__lt=today
    ).count()
    warranty_valid = assets.filter(
        warranty_expiry__isnull=False,
        warranty_expiry__gt=today + timezone.timedelta(days=30)
    ).count()
    warranty_na = assets.filter(warranty_expiry__isnull=True).count()

    # ── Alerts ──
    alerts = []
    if warranty_expiring:
        alerts.append({'type': 'warning', 'message': f'{warranty_expiring} asset(s) with warranty expiring within 30 days'})
    if warranty_expired:
        alerts.append({'type': 'error', 'message': f'{warranty_expired} asset(s) with expired warranty'})
    if in_repair:
        alerts.append({'type': 'info', 'message': f'{in_repair} asset(s) currently in repair'})

    # Overdue assignments (assigned > 90 days without return)
    overdue_threshold = today - timezone.timedelta(days=90)
    overdue_count = assets.filter(
        status='ASSIGNED',
        assigned_date__isnull=False,
        assigned_date__lt=overdue_threshold
    ).count()
    if overdue_count:
        alerts.append({'type': 'warning', 'message': f'{overdue_count} asset(s) assigned for over 90 days'})

    # Poor condition assets
    poor_count = assets.filter(condition='POOR').exclude(status__in=['RETIRED', 'LOST']).count()
    if poor_count:
        alerts.append({'type': 'error', 'message': f'{poor_count} active asset(s) in poor condition'})

    # ── Pending Requests ──
    request_qs = AssetRequest.objects.all()
    if tenant:
        request_qs = request_qs.filter(tenant=tenant)
    elif company:
        request_qs = request_qs.filter(department__company=company)
    pending_requests_count = request_qs.filter(status='PENDING').count()
    approved_requests_count = request_qs.filter(status='APPROVED').count()
    total_requests_count = request_qs.count()
    if pending_requests_count:
        alerts.append({'type': 'warning', 'message': f'{pending_requests_count} pending asset request(s) awaiting approval'})

    # ── Recent Activity ──
    recent_assets = assets.order_by('-updated_at')[:8]

    # Recent maintenance
    maint_qs = AssetMaintenanceLog.objects.select_related('asset', 'created_by')
    if company:
        maint_qs = maint_qs.filter(
            Q(asset__department__company=company) | Q(asset__employee__company=company)
        )
    elif tenant:
        maint_qs = maint_qs.filter(tenant=tenant)
    recent_maintenance = maint_qs.order_by('-created_at')[:5]

    # Maintenance cost this month
    month_start = today.replace(day=1)
    maint_cost_month = maint_qs.filter(
        performed_date__gte=month_start
    ).aggregate(total=Sum('cost'))['total'] or 0
    maint_count_month = maint_qs.filter(performed_date__gte=month_start).count()

    # Recent requests
    recent_requests = request_qs.select_related('requested_by', 'department').order_by('-created_at')[:5]

    # ── Department Stats (admins only) ──
    department_stats = None
    dept_value_stats = None
    if is_admin and company:
        department_stats = list(assets.values('department__name').annotate(
            count=Count('id'),
            assigned_count=Count('id', filter=Q(status='ASSIGNED')),
            value=Sum('purchase_price'),
        ).order_by('-count')[:8])

    # ── Top Custodians ──
    top_custodians = None
    if is_admin:
        top_custodians = list(
            assets.filter(custodian__isnull=False)
            .values('custodian__first_name', 'custodian__last_name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

    # ── Recently Added (last 30 days) ──
    recently_added_count = assets.filter(created_at__gte=now - timezone.timedelta(days=30)).count()

    context = {
        'total': total,
        'assigned': assigned,
        'available': available,
        'in_repair': in_repair,
        'retired': retired,
        'lost': lost,
        'active_assets': active_assets,
        'total_value': total_value,
        'avg_value': avg_value,
        'utilization_rate': utilization_rate,
        'condition_breakdown': condition_breakdown,
        'condition_display': condition_display,
        'type_breakdown': type_breakdown,
        'warranty_valid': warranty_valid,
        'warranty_expiring': warranty_expiring,
        'warranty_expired': warranty_expired,
        'warranty_na': warranty_na,
        'alerts': alerts,
        'overdue_count': overdue_count,
        'poor_count': poor_count,
        'recent_assets': recent_assets,
        'recent_maintenance': recent_maintenance,
        'recent_requests': recent_requests,
        'pending_requests_count': pending_requests_count,
        'approved_requests_count': approved_requests_count,
        'total_requests_count': total_requests_count,
        'department_stats': department_stats,
        'top_custodians': top_custodians,
        'maint_cost_month': maint_cost_month,
        'maint_count_month': maint_count_month,
        'recently_added_count': recently_added_count,
        'asset_types_display': dict(EmployeeAsset.AssetType.choices),
        'is_admin': is_admin,
    }
    return render(request, 'assets/ams_dashboard.html', context)


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

    # Base queryset — combine tenant + company to catch all assets
    base_qs = EmployeeAsset.objects.select_related('employee', 'department', 'category', 'custodian')
    if company:
        company_q = Q(department__company=company) | Q(employee__company=company)
        if tenant:
            assets = base_qs.filter(Q(tenant=tenant) | company_q).distinct()
        else:
            assets = base_qs.filter(company_q).distinct()
    elif tenant:
        assets = base_qs.filter(tenant=tenant)
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
        'can_manage_assets': can_manage_assets,
    }
    
    return render(request, 'assets/asset_list.html', context)


@login_required
def assignment_list(request):
    """List assigned assets — dedicated view for Assignments sidebar link"""
    user = request.user
    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)

    base_qs = EmployeeAsset.objects.select_related('employee', 'department', 'category', 'custodian')
    if company:
        company_q = Q(department__company=company) | Q(employee__company=company)
        if tenant:
            assets = base_qs.filter(Q(tenant=tenant) | company_q).distinct()
        else:
            assets = base_qs.filter(company_q).distinct()
    elif tenant:
        assets = base_qs.filter(tenant=tenant)
    else:
        assets = base_qs.none()

    if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        view_scope = 'all'
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        if user_dept:
            assets = assets.filter(department=user_dept)
            view_scope = 'department'
        else:
            assets = assets.none()
            view_scope = 'none'
    else:
        assets = assets.filter(employee=user)
        view_scope = 'personal'

    # Only assigned assets
    assets = assets.filter(status='ASSIGNED')

    search = request.GET.get('search', '')
    if search:
        assets = assets.filter(
            Q(asset_tag__icontains=search) | Q(name__icontains=search) |
            Q(serial_number__icontains=search) | Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search)
        )

    department_filter = request.GET.get('department', '')
    if department_filter and view_scope == 'all':
        assets = assets.filter(department_id=department_filter)

    # Asset type filter
    type_filter = request.GET.get('asset_type', '')
    if type_filter:
        assets = assets.filter(asset_type=type_filter)

    assets = assets.order_by('-assigned_date', '-created_at')

    # ── Stats ──
    today = timezone.now().date()
    total_assigned = assets.count()
    overdue_threshold = today - timezone.timedelta(days=90)
    overdue_count = assets.filter(assigned_date__isnull=False, assigned_date__lt=overdue_threshold).count()
    recent_count = assets.filter(assigned_date__isnull=False, assigned_date__gte=today - timezone.timedelta(days=30)).count()

    # Avg days assigned
    from django.db.models import F, ExpressionWrapper, fields as model_fields
    avg_days = 0
    if total_assigned > 0:
        assigned_dates = list(
            assets.filter(assigned_date__isnull=False)
            .values_list('assigned_date', flat=True)[:100]
        )
        if assigned_dates:
            total_days = sum((today - d).days for d in assigned_dates)
            avg_days = round(total_days / len(assigned_dates))

    # Value of assigned assets
    assigned_value = assets.aggregate(val=Sum('purchase_price'))['val'] or 0

    paginator = Paginator(assets, 15)
    assets_page = paginator.get_page(request.GET.get('page'))

    departments = None
    if view_scope == 'all' and company:
        departments = CompanyDepartment.objects.filter(company=company)

    can_manage_assets = user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']

    context = {
        'assets': assets_page,
        'view_scope': view_scope,
        'departments': departments,
        'search': search,
        'department_filter': department_filter,
        'type_filter': type_filter,
        'asset_types': EmployeeAsset.AssetType.choices,
        'paginator': paginator,
        'page_obj': assets_page,
        'can_manage_assets': can_manage_assets,
        'page_mode': 'assignments',
        'total_assigned': total_assigned,
        'overdue_count': overdue_count,
        'recent_count': recent_count,
        'avg_days': avg_days,
        'assigned_value': assigned_value,
    }
    return render(request, 'assets/assignment_list.html', context)


@login_required
def maintenance_list(request):
    """List assets in repair + maintenance logs — dedicated view for Maintenance sidebar link"""
    user = request.user
    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)

    base_qs = EmployeeAsset.objects.select_related('employee', 'department', 'category', 'custodian')
    if company:
        company_q = Q(department__company=company) | Q(employee__company=company)
        if tenant:
            assets = base_qs.filter(Q(tenant=tenant) | company_q).distinct()
        else:
            assets = base_qs.filter(company_q).distinct()
    elif tenant:
        assets = base_qs.filter(tenant=tenant)
    else:
        assets = base_qs.none()

    if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        view_scope = 'all'
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        if user_dept:
            assets = assets.filter(department=user_dept)
            view_scope = 'department'
        else:
            assets = assets.none()
            view_scope = 'none'
    else:
        assets = assets.filter(employee=user)
        view_scope = 'personal'

    # Only in-repair assets
    repair_assets = assets.filter(status='IN_REPAIR')

    search = request.GET.get('search', '')
    if search:
        repair_assets = repair_assets.filter(
            Q(asset_tag__icontains=search) | Q(name__icontains=search) |
            Q(serial_number__icontains=search)
        )

    repair_assets = repair_assets.order_by('-updated_at')

    # ── Maintenance Logs ──
    maint_qs = AssetMaintenanceLog.objects.select_related('asset', 'created_by')
    if company:
        maint_qs = maint_qs.filter(
            Q(asset__department__company=company) | Q(asset__employee__company=company)
        )
    elif tenant:
        maint_qs = maint_qs.filter(tenant=tenant)

    # Filter logs by type
    maint_type_filter = request.GET.get('maint_type', '')
    filtered_logs = maint_qs
    if maint_type_filter:
        filtered_logs = filtered_logs.filter(maintenance_type=maint_type_filter)

    # Search in logs too
    log_search = request.GET.get('search', '')
    if log_search:
        filtered_logs = filtered_logs.filter(
            Q(asset__name__icontains=log_search) | Q(asset__asset_tag__icontains=log_search) |
            Q(description__icontains=log_search)
        )

    filtered_logs = filtered_logs.order_by('-performed_date', '-created_at')

    # ── Stats ──
    today = timezone.now().date()
    month_start = today.replace(day=1)
    in_repair_count = repair_assets.count()
    total_logs = maint_qs.count()
    logs_this_month = maint_qs.filter(performed_date__gte=month_start).count()
    total_cost = maint_qs.aggregate(val=Sum('cost'))['val'] or 0
    cost_this_month = maint_qs.filter(performed_date__gte=month_start).aggregate(val=Sum('cost'))['val'] or 0

    # Type breakdown for logs
    maint_type_breakdown = list(
        maint_qs.values('maintenance_type').annotate(count=Count('id')).order_by('-count')
    )
    maint_type_choices = dict(AssetMaintenanceLog.MaintenanceType.choices) if hasattr(AssetMaintenanceLog, 'MaintenanceType') else {}
    if not maint_type_choices:
        # Fallback: try to get choices from the field
        try:
            maint_type_choices = dict(AssetMaintenanceLog._meta.get_field('maintenance_type').choices)
        except Exception:
            maint_type_choices = {}

    # Paginate logs (not repair assets)
    log_paginator = Paginator(filtered_logs, 15)
    logs_page = log_paginator.get_page(request.GET.get('page'))

    can_manage_assets = user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']

    context = {
        'repair_assets': repair_assets[:10],
        'maintenance_logs': logs_page,
        'view_scope': view_scope,
        'search': log_search,
        'maint_type_filter': maint_type_filter,
        'maint_type_choices': maint_type_choices,
        'maint_type_breakdown': maint_type_breakdown,
        'paginator': log_paginator,
        'page_obj': logs_page,
        'can_manage_assets': can_manage_assets,
        'page_mode': 'maintenance',
        'in_repair_count': in_repair_count,
        'total_logs': total_logs,
        'logs_this_month': logs_this_month,
        'total_cost': total_cost,
        'cost_this_month': cost_this_month,
    }
    return render(request, 'assets/maintenance_list.html', context)


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
        return redirect('assets:asset_list')
    
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

    # Cross-suite notification
    if employee:
        try:
            from ems_project.cross_suite_notifications import notify_asset_assigned
            notify_asset_assigned(asset, assigned_by=user)
        except Exception:
            pass

    messages.success(request, f'Asset assigned to {employee.get_full_name()}' if employee else 'Asset unassigned.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def asset_unassign(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    prev_employee = asset.employee
    asset.employee = None
    asset.return_date = timezone.now().date()
    asset.save()

    # Cross-suite notification
    if prev_employee:
        try:
            from ems_project.cross_suite_notifications import notify_asset_unassigned
            notify_asset_unassigned(asset, prev_employee, unassigned_by=request.user)
        except Exception:
            pass

    messages.success(request, 'Asset unassigned and marked available.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def asset_return(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    prev_employee = asset.employee
    asset.employee = None
    asset.status = EmployeeAsset.Status.AVAILABLE
    asset.return_date = timezone.now().date()
    asset.save()

    # Cross-suite notification
    if prev_employee:
        try:
            from ems_project.cross_suite_notifications import notify_asset_unassigned
            notify_asset_unassigned(asset, prev_employee, unassigned_by=request.user)
        except Exception:
            pass

    messages.success(request, 'Asset marked as returned and available.')
    return redirect('asset_detail', asset_id=asset.id)


@login_required
def asset_send_to_repair(request, asset_id):
    tenant = getattr(request, 'tenant', None)
    asset = _get_asset_or_404(asset_id, request)
    prev_employee = asset.employee
    asset.employee = None
    asset.status = EmployeeAsset.Status.IN_REPAIR
    asset.return_date = timezone.now().date()
    asset.save()

    # Cross-suite notification
    if prev_employee:
        try:
            from ems_project.cross_suite_notifications import notify_asset_maintenance
            # Temporarily set employee back so the helper can read it
            asset.employee = prev_employee
            notify_asset_maintenance(asset)
            asset.employee = None
        except Exception:
            pass

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
    from ems_project.context_processors import get_company_currency
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

    company = getattr(user, 'company', None)
    currency = get_company_currency(company) if company else {'symbol': 'ZMW'}

    # Company logo as base64
    logo_b64 = ''
    if company and company.logo:
        try:
            with open(company.logo.path, 'rb') as f:
                import mimetypes
                mime = mimetypes.guess_type(company.logo.path)[0] or 'image/png'
                logo_b64 = f'data:{mime};base64,{base64.b64encode(f.read()).decode()}'
        except Exception:
            logo_b64 = ''

    # Employee profile info
    employee = asset.employee
    emp_profile = None
    if employee:
        try:
            emp_profile = employee.employee_profile
        except Exception:
            pass

    context = {
        'asset': asset,
        'collection': collection,
        'employee': employee,
        'emp_profile': emp_profile,
        'company': company,
        'logo_b64': logo_b64,
        'currency_symbol': currency.get('symbol', 'ZMW'),
        'custodian': asset.custodian,
        'assigned_by': asset.assigned_by,
        'now': timezone.now(),
        'today': timezone.now().date(),
    }
    return render(request, 'assets/asset_handover_document.html', context)

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
        # Admins see all requests scoped to company
        if company:
            requests_list = AssetRequest.objects.filter(department__company=company)
        elif tenant:
            requests_list = AssetRequest.objects.filter(tenant=tenant)
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
    
    # ── Stats (before filtering) ──
    total_count = requests_list.count()
    pending_count = requests_list.filter(status='PENDING').count()
    approved_count = requests_list.filter(status='APPROVED').count()
    rejected_count = requests_list.filter(status='REJECTED').count()
    fulfilled_count = requests_list.filter(status='FULFILLED').count()

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)

    # Search filter
    search = request.GET.get('search', '')
    if search:
        requests_list = requests_list.filter(
            Q(asset_name__icontains=search) |
            Q(requested_by__first_name__icontains=search) |
            Q(requested_by__last_name__icontains=search) |
            Q(department__name__icontains=search)
        )

    # Priority filter
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        requests_list = requests_list.filter(priority=priority_filter)

    # Calculate pending approvals for current user
    pending_my_approval = []
    for req in requests_list:
        if req.can_user_approve(user):
            pending_my_approval.append(req.id)

    # Admins and managers can approve
    can_approve = user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'DEPARTMENT_MANAGER', 'SUPERVISOR']

    # Paginate
    paginator = Paginator(requests_list, 15)
    requests_page = paginator.get_page(request.GET.get('page'))

    context = {
        'requests': requests_page,
        'pending_my_approval': pending_my_approval,
        'view_scope': view_scope,
        'status_filter': status_filter,
        'search': search,
        'priority_filter': priority_filter,
        'statuses': AssetRequest.Status.choices,
        'priorities': AssetRequest.Priority.choices if hasattr(AssetRequest, 'Priority') else [],
        'can_approve': can_approve,
        'total_count': total_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'fulfilled_count': fulfilled_count,
        'paginator': paginator,
        'page_obj': requests_page,
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
            return redirect('assets:asset_list')
    
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
        
        return redirect('assets:asset_request_list')
    
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
    
    context = {
        'asset_request': asset_request,
        'timeline': timeline,
        'can_approve': can_approve,
    }
    
    return render(request, 'assets/asset_request_detail.html', context)


@login_required
def department_asset_dashboard(request):
    """Dashboard for department managers and admins to see department asset overview"""
    user = request.user
    company = getattr(user, 'company', None)
    
    # Admins can view all departments; managers/supervisors see their own
    if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        # Admin: show all departments, pick first or use query param
        from accounts.models import CompanyDepartment
        dept_id = request.GET.get('department')
        if dept_id:
            user_dept = CompanyDepartment.objects.filter(id=dept_id, company=company).first()
        else:
            user_dept = CompanyDepartment.objects.filter(company=company).first() if company else None
        all_departments = CompanyDepartment.objects.filter(company=company) if company else CompanyDepartment.objects.none()
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        all_departments = None
    else:
        messages.error(request, 'You do not have permission to access this dashboard.')
        return redirect('assets:asset_list')
    
    if not user_dept:
        messages.error(request, 'No department found.')
        return redirect('assets:asset_list')
    
    # Get department assets
    tenant = getattr(request, 'tenant', None)
    dept_assets = EmployeeAsset.objects.filter(department=user_dept).select_related('employee', 'category', 'custodian')

    # ── Core Stats ──
    total_assets = dept_assets.count()
    assigned = dept_assets.filter(status='ASSIGNED').count()
    available = dept_assets.filter(status='AVAILABLE').count()
    in_repair = dept_assets.filter(status='IN_REPAIR').count()
    retired = dept_assets.filter(status='RETIRED').count()

    # Utilization rate
    active_assets = dept_assets.exclude(status__in=['RETIRED', 'LOST']).count()
    utilization_rate = round((assigned / active_assets * 100), 1) if active_assets > 0 else 0

    # Value stats
    total_value = dept_assets.aggregate(val=Sum('purchase_price'))['val'] or 0
    assigned_value = dept_assets.filter(status='ASSIGNED').aggregate(val=Sum('purchase_price'))['val'] or 0

    # By type
    by_type = list(dept_assets.values('asset_type').annotate(count=Count('id')).order_by('-count'))

    # Condition breakdown
    condition_breakdown = list(
        dept_assets.exclude(status__in=['RETIRED', 'LOST'])
        .values('condition').annotate(count=Count('id')).order_by('-count')
    )

    # Top custodians in department
    top_custodians = list(
        dept_assets.filter(employee__isnull=False)
        .values('employee__first_name', 'employee__last_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Recent assets
    recent_assets = dept_assets.order_by('-created_at')[:10]

    # Recent maintenance
    dept_maintenance = AssetMaintenanceLog.objects.filter(
        asset__department=user_dept
    ).select_related('asset', 'created_by').order_by('-performed_date', '-created_at')[:5]
    dept_maint_cost = AssetMaintenanceLog.objects.filter(
        asset__department=user_dept
    ).aggregate(val=Sum('cost'))['val'] or 0

    # Pending requests
    pending_requests = AssetRequest.objects.filter(
        department=user_dept, status='PENDING'
    ).count()
    total_requests = AssetRequest.objects.filter(department=user_dept).count()

    context = {
        'department': user_dept,
        'total_assets': total_assets,
        'assigned': assigned,
        'available': available,
        'in_repair': in_repair,
        'retired': retired,
        'utilization_rate': utilization_rate,
        'total_value': total_value,
        'assigned_value': assigned_value,
        'by_type': by_type,
        'condition_breakdown': condition_breakdown,
        'top_custodians': top_custodians,
        'recent_assets': recent_assets,
        'dept_maintenance': dept_maintenance,
        'dept_maint_cost': dept_maint_cost,
        'pending_requests': pending_requests,
        'total_requests': total_requests,
        'all_departments': all_departments if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN'] else None,
    }

    return render(request, 'assets/department_dashboard.html', context)


@login_required
def ams_settings(request):
    """AMS Settings — manage asset categories and view configuration"""
    user = request.user
    if user.role not in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        return HttpResponseForbidden('You do not have permission to access AMS settings.')

    tenant = getattr(request, 'tenant', None)
    company = getattr(user, 'company', None)

    # Get categories scoped to tenant or all if superadmin
    if tenant:
        categories = AssetCategory.objects.filter(tenant=tenant).order_by('name')
    else:
        categories = AssetCategory.objects.all().order_by('name')

    # Handle category create
    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create_category':
            name = request.POST.get('category_name', '').strip()
            description = request.POST.get('category_description', '').strip()
            if name:
                cat_kwargs = {'name': name, 'description': description}
                if tenant:
                    cat_kwargs['tenant'] = tenant
                # Check for duplicate
                exists = categories.filter(name__iexact=name).exists()
                if exists:
                    messages.warning(request, f'Category "{name}" already exists.')
                else:
                    AssetCategory.objects.create(**cat_kwargs)
                    messages.success(request, f'Category "{name}" created successfully.')
            else:
                messages.error(request, 'Category name is required.')

        elif action == 'delete_category':
            cat_id = request.POST.get('category_id')
            try:
                cat = categories.get(id=cat_id)
                asset_count = EmployeeAsset.objects.filter(category=cat).count()
                if asset_count > 0:
                    messages.warning(request, f'Cannot delete "{cat.name}" — {asset_count} asset(s) are using this category.')
                else:
                    cat_name = cat.name
                    cat.delete()
                    messages.success(request, f'Category "{cat_name}" deleted.')
            except AssetCategory.DoesNotExist:
                messages.error(request, 'Category not found.')

        elif action == 'edit_category':
            cat_id = request.POST.get('category_id')
            name = request.POST.get('category_name', '').strip()
            description = request.POST.get('category_description', '').strip()
            try:
                cat = categories.get(id=cat_id)
                if name:
                    cat.name = name
                    cat.description = description
                    cat.save()
                    messages.success(request, f'Category "{name}" updated.')
                else:
                    messages.error(request, 'Category name is required.')
            except AssetCategory.DoesNotExist:
                messages.error(request, 'Category not found.')

        return redirect('assets:ams_settings')

    # Stats for settings page
    total_assets = 0
    if company:
        company_q = Q(department__company=company) | Q(employee__company=company)
        if tenant:
            total_assets = EmployeeAsset.objects.filter(Q(tenant=tenant) | company_q).distinct().count()
        else:
            total_assets = EmployeeAsset.objects.filter(company_q).distinct().count()
    elif tenant:
        total_assets = EmployeeAsset.objects.filter(tenant=tenant).count()

    # Category usage counts
    cat_usage = {}
    for cat in categories:
        cat_usage[cat.id] = EmployeeAsset.objects.filter(category=cat).count()

    context = {
        'categories': categories,
        'cat_usage': cat_usage,
        'asset_types': EmployeeAsset.AssetType.choices,
        'statuses': EmployeeAsset.Status.choices,
        'conditions': EmployeeAsset.Condition.choices,
        'total_assets': total_assets,
        'total_categories': categories.count(),
    }
    return render(request, 'assets/ams_settings.html', context)


@login_required
def asset_assignment_document(request, asset_id):
    """Generate PDF assignment/inventory document for an assigned asset."""
    import weasyprint
    from django.template.loader import render_to_string
    from ems_project.context_processors import get_company_currency

    asset = _get_asset_or_404(asset_id, request)
    user = request.user

    # Permission check
    can_view = False
    if user.role in ['SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN']:
        can_view = True
    elif user.role in ['DEPARTMENT_MANAGER', 'SUPERVISOR']:
        user_dept = user.employee_profile.department if hasattr(user, 'employee_profile') else None
        can_view = asset.department == user_dept
    else:
        can_view = asset.employee == user

    if not can_view:
        return HttpResponseForbidden('You do not have permission to view this document.')

    if asset.status != 'ASSIGNED' or not asset.employee:
        messages.warning(request, 'This asset is not currently assigned. No assignment document available.')
        return redirect('assets:asset_detail', asset_id=asset.id)

    # Get company info
    company = getattr(user, 'company', None)
    currency = get_company_currency(company) if company else {'symbol': 'ZMW'}

    # Company logo as base64 for embedding in PDF
    logo_b64 = ''
    if company and company.logo:
        try:
            with open(company.logo.path, 'rb') as f:
                import mimetypes
                mime = mimetypes.guess_type(company.logo.path)[0] or 'image/png'
                logo_b64 = f'data:{mime};base64,{base64.b64encode(f.read()).decode()}'
        except Exception:
            logo_b64 = ''

    # Employee profile info
    employee = asset.employee
    emp_profile = None
    try:
        emp_profile = employee.employee_profile
    except Exception:
        pass

    # Get latest collection record with signature if available
    collection = AssetCollectionRecord.objects.filter(asset=asset).order_by('-signed_at').first()

    context = {
        'asset': asset,
        'employee': employee,
        'emp_profile': emp_profile,
        'company': company,
        'logo_b64': logo_b64,
        'currency_symbol': currency.get('symbol', 'ZMW'),
        'custodian': asset.custodian,
        'assigned_by': asset.assigned_by,
        'collection': collection,
        'now': timezone.now(),
        'today': timezone.now().date(),
        'is_pdf': True,
    }

    html_string = render_to_string('assets/asset_handover_document.html', context)
    pdf = weasyprint.HTML(string=html_string).write_pdf()

    filename = f'Asset_Handover_{asset.asset_tag}_{employee.get_full_name().replace(" ", "_")}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')

    # Check if user wants inline view or download
    if request.GET.get('view') == '1':
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response
