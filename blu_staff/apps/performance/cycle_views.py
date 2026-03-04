"""
Views for Performance Review Cycles Management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.utils import timezone
from datetime import date, timedelta
from django.contrib.auth import get_user_model

from .models import (
    PerformanceReviewCycle, ReviewCycleAssignment, PerformanceReview,
    PerformanceTemplate, CompetencyFramework, Competency, CompetencyRating
)

User = get_user_model()


@login_required
def review_cycles_list(request):
    """List all performance review cycles"""
    # Check if user has HR access
    has_access = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_access = has_access or request.user.employee_profile.employee_role == 'HR'
    
    if not has_access:
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(request.user, 'company', None)
    if not company:
        messages.error(request, 'No company associated with your account.')
        return redirect('employer_dashboard')
    
    # Get cycles for this company only
    cycles = PerformanceReviewCycle.objects.filter(company=company).order_by('-start_date')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        cycles = cycles.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        cycles = cycles.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Calculate statistics
    total_cycles = cycles.count()
    active_cycles = cycles.filter(status='ACTIVE').count()
    in_progress_cycles = cycles.filter(status='IN_PROGRESS').count()
    completed_cycles = cycles.filter(status='COMPLETED').count()
    
    context = {
        'cycles': cycles,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_cycles': total_cycles,
        'active_cycles': active_cycles,
        'in_progress_cycles': in_progress_cycles,
        'completed_cycles': completed_cycles,
        'status_choices': PerformanceReviewCycle.CycleStatus.choices,
    }
    
    return render(request, 'performance/review_cycles_list.html', context)


@login_required
def review_cycle_create(request):
    """Create a new review cycle"""
    # Check if user has HR access
    has_access = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR', 'HR']
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_access = has_access or request.user.employee_profile.employee_role == 'HR'
    
    if not has_access:
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(request.user, 'company', None)
    if not company:
        messages.error(request, 'No company associated with your account.')
        return redirect('employer_dashboard')
    
    if request.method == 'POST':
        try:
            # Create the cycle
            cycle = PerformanceReviewCycle.objects.create(
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                review_type=request.POST.get('review_type'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                review_period_start=request.POST.get('review_period_start'),
                review_period_end=request.POST.get('review_period_end'),
                deadline=request.POST.get('deadline'),
                template_id=request.POST.get('template') if request.POST.get('template') else None,
                auto_assign_reviewers=request.POST.get('auto_assign_reviewers') == 'on',
                send_reminders=request.POST.get('send_reminders') == 'on',
                reminder_days_before=request.POST.get('reminder_days_before', 7),
                created_by=request.user,
            )
            
            messages.success(request, f'Review cycle "{cycle.name}" created successfully!')
            return redirect('performance:review_cycle_detail', cycle_id=cycle.id)
            
        except Exception as e:
            messages.error(request, f'Error creating review cycle: {str(e)}')
    
    # Get templates for selection
    templates = PerformanceTemplate.objects.filter(is_active=True)
    
    context = {
        'templates': templates,
        'review_types': PerformanceReview.ReviewType.choices,
    }
    
    return render(request, 'performance/review_cycle_create.html', context)


@login_required
def review_cycle_detail(request, cycle_id):
    """View and manage a review cycle"""
    # Check if user has HR access
    has_access = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR', 'HR']
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_access = has_access or request.user.employee_profile.employee_role == 'HR'
    
    if not has_access:
        return render(request, 'ems/unauthorized.html')
    
    cycle = get_object_or_404(PerformanceReviewCycle, id=cycle_id)
    
    # Get assignments
    assignments = cycle.assignments.select_related('employee', 'reviewer', 'review').order_by('employee__last_name')
    
    # Filter assignments
    status_filter = request.GET.get('assignment_status', '')
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    
    search_query = request.GET.get('search', '')
    if search_query:
        assignments = assignments.filter(
            Q(employee__first_name__icontains=search_query) |
            Q(employee__last_name__icontains=search_query) |
            Q(employee__email__icontains=search_query)
        )
    
    # Statistics
    total_assignments = cycle.total_assignments
    completed_count = cycle.completed_reviews
    pending_count = assignments.filter(status='PENDING').count()
    in_progress_count = assignments.filter(status='IN_PROGRESS').count()
    
    context = {
        'cycle': cycle,
        'assignments': assignments,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_assignments': total_assignments,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'completion_percentage': cycle.completion_percentage,
        'assignment_status_choices': ReviewCycleAssignment.AssignmentStatus.choices,
    }
    
    return render(request, 'performance/review_cycle_detail.html', context)


@login_required
def bulk_assign_employees(request, cycle_id):
    """Bulk assign employees to a review cycle"""
    # Check if user has HR access
    has_access = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR', 'HR']
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_access = has_access or request.user.employee_profile.employee_role == 'HR'
    
    if not has_access:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    cycle = get_object_or_404(PerformanceReviewCycle, id=cycle_id)
    company = getattr(request.user, 'company', None)
    
    if request.method == 'POST':
        try:
            employee_ids = request.POST.getlist('employee_ids[]')
            auto_assign_reviewers = request.POST.get('auto_assign_reviewers') == 'true'
            
            created_count = 0
            skipped_count = 0
            
            for emp_id in employee_ids:
                employee = User.objects.get(id=emp_id, role='EMPLOYEE', company=company)
                
                # Check if already assigned
                if ReviewCycleAssignment.objects.filter(cycle=cycle, employee=employee).exists():
                    skipped_count += 1
                    continue
                
                # Determine reviewer
                reviewer = None
                if auto_assign_reviewers:
                    # Try to get supervisor from employee profile
                    if hasattr(employee, 'employee_profile') and employee.employee_profile:
                        reviewer = employee.employee_profile.supervisor
                
                # Create assignment
                ReviewCycleAssignment.objects.create(
                    cycle=cycle,
                    employee=employee,
                    reviewer=reviewer,
                    status='PENDING'
                )
                created_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Assigned {created_count} employees. Skipped {skipped_count} (already assigned).',
                'created': created_count,
                'skipped': skipped_count
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    # GET request - show employee selection
    employees = User.objects.filter(role='EMPLOYEE', company=company).select_related('employee_profile')
    
    # Exclude already assigned
    assigned_ids = cycle.assignments.values_list('employee_id', flat=True)
    employees = employees.exclude(id__in=assigned_ids)
    
    context = {
        'cycle': cycle,
        'employees': employees,
    }
    
    return render(request, 'performance/bulk_assign_employees.html', context)


@login_required
def initiate_cycle_reviews(request, cycle_id):
    """Initiate reviews for all assignments in a cycle"""
    # Check if user has HR access
    has_access = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR', 'HR']
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_access = has_access or request.user.employee_profile.employee_role == 'HR'
    
    if not has_access:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    cycle = get_object_or_404(PerformanceReviewCycle, id=cycle_id)
    
    if request.method == 'POST':
        try:
            # Get pending assignments
            assignments = cycle.assignments.filter(status='PENDING', review__isnull=True)
            
            created_count = 0
            for assignment in assignments:
                # Create review
                review = PerformanceReview.objects.create(
                    cycle=cycle,
                    employee=assignment.employee,
                    reviewer=assignment.reviewer,
                    review_type=cycle.review_type,
                    review_period_start=cycle.review_period_start,
                    review_period_end=cycle.review_period_end,
                    review_date=date.today(),
                    title=f"{cycle.name} - {assignment.employee.get_full_name()}",
                    status='DRAFT'
                )
                
                # Link review to assignment
                assignment.review = review
                assignment.status = 'IN_PROGRESS'
                assignment.save()
                
                created_count += 1
                
                # Send notification to employee - NO EMAIL DEPENDENCY
                from blu_staff.apps.notifications.utils import create_notification
                try:
                    notif = create_notification(
                        recipient=assignment.employee,
                        sender=request.user,
                        title='New Performance Review - Action Required',
                        message=f'Your performance review for {cycle.name} is ready. Please complete your self-assessment by {cycle.deadline}.',
                        notification_type='INFO',
                        category='PERFORMANCE',
                        link=f'/performance/review/{review.id}/employee/',
                        send_email=False  # Disable email to prevent errors
                    )
                except Exception as notif_error:
                    import traceback
                
                # Send notification to reviewer - NO EMAIL DEPENDENCY
                if assignment.reviewer:
                    try:
                        notif = create_notification(
                            recipient=assignment.reviewer,
                            sender=request.user,
                            title='Performance Review Assignment',
                            message=f'You have been assigned to review {assignment.employee.get_full_name()} for {cycle.name}. Deadline: {cycle.deadline}',
                            notification_type='INFO',
                            category='PERFORMANCE',
                            link=f'/performance/review/{review.id}/reviewer/',
                            send_email=False  # Disable email to prevent errors
                        )
                    except Exception as notif_error:
                        import traceback
            
            # Update cycle status
            if cycle.status == 'DRAFT':
                cycle.status = 'IN_PROGRESS'
                cycle.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Initiated {created_count} reviews successfully!',
                'created': created_count
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)


@login_required
def performance_analytics_dashboard(request):
    """Comprehensive performance analytics dashboard"""
    # Check if user has HR access
    has_access = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_access = has_access or request.user.employee_profile.employee_role == 'HR'
    
    if not has_access:
        return render(request, 'ems/unauthorized.html')
    
    company = getattr(request.user, 'company', None)
    if not company:
        messages.error(request, 'No company associated with your account.')
        return redirect('employer_dashboard')
    
    # Get all reviews for the company
    all_reviews = PerformanceReview.objects.filter(employee__company=company)
    
    # Time period filter
    period = request.GET.get('period', 'all')
    if period == 'ytd':
        all_reviews = all_reviews.filter(review_date__year=date.today().year)
    elif period == 'last_quarter':
        three_months_ago = date.today() - timedelta(days=90)
        all_reviews = all_reviews.filter(review_date__gte=three_months_ago)
    elif period == 'last_year':
        one_year_ago = date.today() - timedelta(days=365)
        all_reviews = all_reviews.filter(review_date__gte=one_year_ago)
    
    # Overall statistics
    total_reviews = all_reviews.count()
    completed_reviews = all_reviews.filter(status__in=['COMPLETED', 'APPROVED']).count()
    avg_rating_data = all_reviews.aggregate(avg=Avg('overall_rating'))
    
    # Rating distribution with percentages
    outstanding_count = all_reviews.filter(overall_rating='OUTSTANDING').count()
    exceeds_count = all_reviews.filter(overall_rating='EXCEEDS_EXPECTATIONS').count()
    meets_count = all_reviews.filter(overall_rating='MEETS_EXPECTATIONS').count()
    below_count = all_reviews.filter(overall_rating='BELOW_EXPECTATIONS').count()
    unsatisfactory_count = all_reviews.filter(overall_rating='UNSATISFACTORY').count()
    
    rating_distribution = {
        'OUTSTANDING': outstanding_count,
        'EXCEEDS_EXPECTATIONS': exceeds_count,
        'MEETS_EXPECTATIONS': meets_count,
        'BELOW_EXPECTATIONS': below_count,
        'UNSATISFACTORY': unsatisfactory_count,
    }
    
    # Calculate percentages
    rating_percentages = {
        'OUTSTANDING': round((outstanding_count / total_reviews * 100), 1) if total_reviews > 0 else 0,
        'EXCEEDS_EXPECTATIONS': round((exceeds_count / total_reviews * 100), 1) if total_reviews > 0 else 0,
        'MEETS_EXPECTATIONS': round((meets_count / total_reviews * 100), 1) if total_reviews > 0 else 0,
        'BELOW_EXPECTATIONS': round((below_count / total_reviews * 100), 1) if total_reviews > 0 else 0,
        'UNSATISFACTORY': round((unsatisfactory_count / total_reviews * 100), 1) if total_reviews > 0 else 0,
    }
    
    # Department breakdown
    department_stats = []
    employees = User.objects.filter(role='EMPLOYEE', company=company).select_related('employee_profile')
    departments = set(emp.employee_profile.department for emp in employees if hasattr(emp, 'employee_profile') and emp.employee_profile and emp.employee_profile.department)
    
    for dept in departments:
        dept_employees = employees.filter(employee_profile__department=dept)
        dept_reviews = all_reviews.filter(employee__in=dept_employees)
        dept_avg = dept_reviews.aggregate(avg=Avg('overall_rating'))['avg']
        
        department_stats.append({
            'name': dept,
            'total_employees': dept_employees.count(),
            'total_reviews': dept_reviews.count(),
            'avg_rating': round(dept_avg, 2) if dept_avg else 0,
        })
    
    # Top performers
    top_performers = all_reviews.filter(
        overall_rating__in=['OUTSTANDING', 'EXCEEDS_EXPECTATIONS'],
        status__in=['COMPLETED', 'APPROVED']
    ).select_related('employee', 'employee__employee_profile').order_by('-review_date')[:10]
    
    # Review trends (last 12 months)
    review_trends = []
    for i in range(12):
        month_date = date.today() - timedelta(days=30*i)
        month_reviews = all_reviews.filter(
            review_date__year=month_date.year,
            review_date__month=month_date.month
        )
        review_trends.append({
            'month': month_date.strftime('%b %Y'),
            'count': month_reviews.count(),
            'avg_rating': month_reviews.aggregate(avg=Avg('overall_rating'))['avg'] or 0
        })
    
    review_trends.reverse()
    
    # Active cycles
    active_cycles = PerformanceReviewCycle.objects.filter(
        status__in=['ACTIVE', 'IN_PROGRESS']
    ).order_by('-start_date')[:5]
    
    context = {
        'total_reviews': total_reviews,
        'completed_reviews': completed_reviews,
        'avg_rating': avg_rating_data['avg'],
        'rating_distribution': rating_distribution,
        'rating_percentages': rating_percentages,
        'department_stats': department_stats,
        'top_performers': top_performers,
        'review_trends': review_trends,
        'active_cycles': active_cycles,
        'period': period,
    }
    
    return render(request, 'performance/analytics_dashboard.html', context)
