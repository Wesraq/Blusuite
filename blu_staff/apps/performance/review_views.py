"""
Views for Employee and Reviewer Performance Review Interfaces
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import date

from .models import (
    PerformanceReview, PerformanceGoal, PerformanceMetric, 
    PerformanceFeedback, CompetencyRating, Competency
)


@login_required
def employee_review_interface(request, review_id):
    """Employee self-assessment interface"""
    review = get_object_or_404(
        PerformanceReview.objects.select_related('employee', 'reviewer', 'cycle')
        .prefetch_related('goals', 'metrics', 'feedback', 'competency_ratings'),
        id=review_id
    )
    
    # Check if user is the employee
    if request.user != review.employee:
        messages.error(request, 'You can only access your own reviews.')
        return redirect('performance_reviews_list')
    
    # Check if review is still editable by employee
    if review.status not in ['DRAFT', 'UNDER_REVIEW']:
        messages.warning(request, 'This review has been completed and cannot be edited.')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save_draft':
            # Save employee self-assessment
            review.employee_comments = request.POST.get('employee_comments', '')
            review.self_rating = request.POST.get('self_rating', '')
            review.achievements = request.POST.get('achievements', '')
            review.challenges_faced = request.POST.get('challenges_faced', '')
            review.goals_next_period = request.POST.get('goals_next_period', '')
            review.training_needs = request.POST.get('training_needs', '')
            review.save()
            
            messages.success(request, 'Your self-assessment has been saved as draft.')
            return redirect('employee_review_interface', review_id=review.id)
        
        elif action == 'submit':
            # Validate required fields
            if not request.POST.get('employee_comments'):
                messages.error(request, 'Please provide your comments before submitting.')
                return redirect('employee_review_interface', review_id=review.id)
            
            # Save and submit
            review.employee_comments = request.POST.get('employee_comments', '')
            review.self_rating = request.POST.get('self_rating', '')
            review.achievements = request.POST.get('achievements', '')
            review.challenges_faced = request.POST.get('challenges_faced', '')
            review.goals_next_period = request.POST.get('goals_next_period', '')
            review.training_needs = request.POST.get('training_needs', '')
            review.status = 'SUBMITTED'
            review.employee_submitted_at = timezone.now()
            review.save()
            
            # Notify reviewer
            from blu_staff.apps.notifications.models import Notification
            if review.reviewer:
                Notification.objects.create(
                    recipient=review.reviewer,
                    sender=request.user,
                    title='Performance Review Submitted',
                    message=f'{review.employee.get_full_name()} has completed their self-assessment. Please review and provide your feedback.',
                    notification_type='INFO',
                    category='PERFORMANCE',
                    link=f'/performance/review/{review.id}/reviewer/'
                )
            
            messages.success(request, 'Your self-assessment has been submitted successfully!')
            return redirect('performance_reviews_list')
        
        elif action == 'add_goal':
            # Add performance goal
            goal_description = request.POST.get('goal_description')
            if goal_description:
                PerformanceGoal.objects.create(
                    review=review,
                    description=goal_description,
                    target_date=request.POST.get('goal_target_date'),
                    status='IN_PROGRESS'
                )
                messages.success(request, 'Goal added successfully.')
            return redirect('employee_review_interface', review_id=review.id)
    
    # Get competencies if available
    competencies = []
    if hasattr(review, 'cycle') and review.cycle and review.cycle.competency_framework:
        competencies = review.cycle.competency_framework.competencies.all()
        # Get existing ratings
        existing_ratings = {cr.competency_id: cr for cr in review.competency_ratings.all()}
        for comp in competencies:
            comp.existing_rating = existing_ratings.get(comp.id)
    
    context = {
        'review': review,
        'goals': review.goals.all(),
        'metrics': review.metrics.all(),
        'competencies': competencies,
        'self_rating_choices': PerformanceReview.OverallRating.choices,
        'can_edit': review.status in ['DRAFT', 'UNDER_REVIEW'],
    }
    
    return render(request, 'performance/employee_review_interface.html', context)


@login_required
def reviewer_interface(request, review_id):
    """Reviewer interface for completing performance reviews"""
    review = get_object_or_404(
        PerformanceReview.objects.select_related('employee', 'reviewer', 'cycle')
        .prefetch_related('goals', 'metrics', 'feedback', 'competency_ratings'),
        id=review_id
    )
    
    # Check if user is the reviewer or has HR access
    is_reviewer = request.user == review.reviewer
    has_hr_access = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_hr_access = has_hr_access or request.user.employee_profile.employee_role == 'HR'
    
    if not (is_reviewer or has_hr_access):
        messages.error(request, 'You do not have permission to review this employee.')
        return redirect('performance_reviews_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save_draft':
            # Save reviewer feedback
            review.overall_rating = request.POST.get('overall_rating', review.overall_rating)
            review.reviewer_comments = request.POST.get('reviewer_comments', '')
            review.strengths = request.POST.get('strengths', '')
            review.areas_for_improvement = request.POST.get('areas_for_improvement', '')
            review.development_plan = request.POST.get('development_plan', '')
            review.recommended_actions = request.POST.get('recommended_actions', '')
            review.save()
            
            messages.success(request, 'Review feedback saved as draft.')
            return redirect('reviewer_interface', review_id=review.id)
        
        elif action == 'complete':
            # Validate required fields
            if not request.POST.get('overall_rating'):
                messages.error(request, 'Please provide an overall rating before completing.')
                return redirect('reviewer_interface', review_id=review.id)
            
            if not request.POST.get('reviewer_comments'):
                messages.error(request, 'Please provide your comments before completing.')
                return redirect('reviewer_interface', review_id=review.id)
            
            # Save and complete
            review.overall_rating = request.POST.get('overall_rating')
            review.reviewer_comments = request.POST.get('reviewer_comments', '')
            review.strengths = request.POST.get('strengths', '')
            review.areas_for_improvement = request.POST.get('areas_for_improvement', '')
            review.development_plan = request.POST.get('development_plan', '')
            review.recommended_actions = request.POST.get('recommended_actions', '')
            review.status = 'COMPLETED'
            review.reviewer_completed_at = timezone.now()
            review.save()
            
            # Notify employee
            from blu_staff.apps.notifications.models import Notification
            Notification.objects.create(
                recipient=review.employee,
                sender=request.user,
                title='Performance Review Completed',
                message=f'Your performance review has been completed by {review.reviewer.get_full_name()}. You can now view the feedback.',
                notification_type='SUCCESS',
                category='PERFORMANCE',
                link=f'/performance/review/{review.id}/view/'
            )
            
            # Update cycle assignment status
            if hasattr(review, 'cycle_assignment'):
                review.cycle_assignment.status = 'COMPLETED'
                review.cycle_assignment.save()
            
            messages.success(request, 'Performance review completed successfully!')
            return redirect('performance_reviews_list')
        
        elif action == 'add_feedback':
            # Add performance feedback
            feedback_text = request.POST.get('feedback_text')
            if feedback_text:
                PerformanceFeedback.objects.create(
                    review=review,
                    feedback_by=request.user,
                    feedback=feedback_text,
                    feedback_type=request.POST.get('feedback_type', 'GENERAL')
                )
                messages.success(request, 'Feedback added successfully.')
            return redirect('reviewer_interface', review_id=review.id)
        
        elif action == 'rate_competency':
            # Rate a competency
            competency_id = request.POST.get('competency_id')
            rating = request.POST.get('rating')
            if competency_id and rating:
                competency = get_object_or_404(Competency, id=competency_id)
                CompetencyRating.objects.update_or_create(
                    review=review,
                    competency=competency,
                    defaults={
                        'rating': rating,
                        'comments': request.POST.get('competency_comments', ''),
                        'evidence': request.POST.get('competency_evidence', '')
                    }
                )
                messages.success(request, f'Competency "{competency.name}" rated successfully.')
            return redirect('reviewer_interface', review_id=review.id)
    
    # Get competencies if available
    competencies = []
    if hasattr(review, 'cycle') and review.cycle and review.cycle.competency_framework:
        competencies = review.cycle.competency_framework.competencies.all()
        # Get existing ratings
        existing_ratings = {cr.competency_id: cr for cr in review.competency_ratings.all()}
        for comp in competencies:
            comp.existing_rating = existing_ratings.get(comp.id)
    
    context = {
        'review': review,
        'goals': review.goals.all(),
        'metrics': review.metrics.all(),
        'feedback_list': review.feedback.all().order_by('-created_at'),
        'competencies': competencies,
        'rating_choices': PerformanceReview.OverallRating.choices,
        'competency_rating_choices': CompetencyRating.RatingLevel.choices,
        'can_edit': review.status in ['SUBMITTED', 'UNDER_REVIEW'],
    }
    
    return render(request, 'performance/reviewer_interface.html', context)


@login_required
def review_view_only(request, review_id):
    """View completed review (read-only)"""
    review = get_object_or_404(
        PerformanceReview.objects.select_related('employee', 'reviewer', 'cycle')
        .prefetch_related('goals', 'metrics', 'feedback', 'competency_ratings'),
        id=review_id
    )
    
    # Check if user has access
    is_employee = request.user == review.employee
    is_reviewer = request.user == review.reviewer
    has_hr_access = request.user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']
    if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
        has_hr_access = has_hr_access or request.user.employee_profile.employee_role == 'HR'
    
    if not (is_employee or is_reviewer or has_hr_access):
        messages.error(request, 'You do not have permission to view this review.')
        return redirect('performance_reviews_list')
    
    # Get competencies if available
    competencies = []
    if hasattr(review, 'cycle') and review.cycle and review.cycle.competency_framework:
        competencies = review.cycle.competency_framework.competencies.all()
        existing_ratings = {cr.competency_id: cr for cr in review.competency_ratings.all()}
        for comp in competencies:
            comp.existing_rating = existing_ratings.get(comp.id)
    
    context = {
        'review': review,
        'goals': review.goals.all(),
        'metrics': review.metrics.all(),
        'feedback_list': review.feedback.all().order_by('-created_at'),
        'competencies': competencies,
        'is_employee': is_employee,
        'is_reviewer': is_reviewer,
        'is_hr': has_hr_access,
    }
    
    return render(request, 'performance/review_view_only.html', context)
