from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone

from .models import PerformanceReview, PerformanceGoal, PerformanceFeedback
from .forms import PerformanceReviewForm, PerformanceGoalForm, PerformanceFeedbackForm

class CompanyContextMixin:
    """Provide 'company' in context so templates extending base_employer work consistently."""
    def get_company_for_user(self, user):
        company = None
        try:
            # Administrator has company directly
            if getattr(user, 'role', None) == 'ADMINISTRATOR':
                company = getattr(user, 'company', None)
            # Employer admin via employer_profile
            elif getattr(user, 'role', None) == 'EMPLOYER_ADMIN':
                try:
                    company = user.employer_profile.company
                except Exception:
                    company = getattr(user, 'company', None)
            else:
                # Employees and others may have company directly
                company = getattr(user, 'company', None)
        except Exception:
            company = getattr(user, 'company', None)
        return company

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = self.get_company_for_user(self.request.user)
        return context


class ReviewListView(LoginRequiredMixin, CompanyContextMixin, ListView):
    model = PerformanceReview
    template_name = 'performance/review_list.html'
    context_object_name = 'reviews'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter based on user role
        if user.role == 'EMPLOYEE':
            queryset = queryset.filter(employee=user)
        elif user.role in ['EMPLOYER', 'EMPLOYER_ADMIN']:
            queryset = queryset.filter(employee__company=user.company)
            
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status.upper())
            
        review_type = self.request.GET.get('review_type')
        if review_type:
            queryset = queryset.filter(review_type=review_type)
            
        return queryset.order_by('-review_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['review_types'] = PerformanceReview.ReviewType.choices
        return context


class ReviewDetailView(LoginRequiredMixin, CompanyContextMixin, DetailView):
    model = PerformanceReview
    template_name = 'performance/review_detail.html'
    context_object_name = 'review'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter based on user role
        if user.role == 'EMPLOYEE':
            return queryset.filter(employee=user)
        elif user.role in ['EMPLOYER', 'EMPLOYER_ADMIN']:
            return queryset.filter(employee__company=user.company)
        return queryset


class ReviewCreateView(LoginRequiredMixin, UserPassesTestMixin, CompanyContextMixin, CreateView):
    model = PerformanceReview
    form_class = PerformanceReviewForm
    template_name = 'performance/review_form.html'
    
    def test_func(self):
        return self.request.user.role in ['EMPLOYER', 'EMPLOYER_ADMIN', 'ADMIN']
    
    def form_valid(self, form):
        form.instance.reviewer = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        messages.success(self.request, 'Performance review created successfully.')
        return reverse_lazy('performance:review_detail', kwargs={'pk': self.object.id})


class ReviewUpdateView(LoginRequiredMixin, UserPassesTestMixin, CompanyContextMixin, UpdateView):
    model = PerformanceReview
    form_class = PerformanceReviewForm
    template_name = 'performance/review_form.html'

    def test_func(self):
        review = self.get_object()
        return (
            self.request.user == review.reviewer or
            self.request.user.role in ['EMPLOYER', 'EMPLOYER_ADMIN', 'ADMIN']
        )

    def get_success_url(self):
        messages.success(self.request, 'Performance review updated successfully.')
        return reverse_lazy('performance:review_detail', kwargs={'pk': self.object.id})


class ReviewDeleteView(LoginRequiredMixin, UserPassesTestMixin, CompanyContextMixin, DeleteView):
    model = PerformanceReview
    template_name = 'performance/review_confirm_delete.html'
    success_url = reverse_lazy('performance:review_list')
    
    def test_func(self):
        review = self.get_object()
        return self.request.user.role in ['EMPLOYER', 'EMPLOYER_ADMIN']
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Performance review has been deleted successfully.')
        return super().delete(request, *args, **kwargs)


def review_submit(request, pk):
    review = get_object_or_404(PerformanceReview, pk=pk)
    review.status = 'SUBMITTED'
    review.submitted_at = timezone.now()
    review.save()
    messages.success(request, 'Performance review submitted successfully.')
    return redirect('performance:review_detail', pk=review.id)


# Goal Views
class GoalListView(LoginRequiredMixin, CompanyContextMixin, ListView):
    model = PerformanceGoal
    template_name = 'performance/goal_list.html'
    context_object_name = 'goals'
    
    def get_queryset(self):
        return super().get_queryset().filter(
            review__employee__company=self.request.user.company
        )


class GoalCreateView(LoginRequiredMixin, CompanyContextMixin, CreateView):
    model = PerformanceGoal
    form_class = PerformanceGoalForm
    template_name = 'performance/goal_form.html'
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        messages.success(self.request, 'Goal created successfully.')
        return reverse_lazy('performance:goal_list')


class GoalDetailView(LoginRequiredMixin, CompanyContextMixin, DetailView):
    model = PerformanceGoal
    template_name = 'performance/goal_detail.html'
    context_object_name = 'goal'


class GoalUpdateView(LoginRequiredMixin, CompanyContextMixin, UpdateView):
    model = PerformanceGoal
    form_class = PerformanceGoalForm
    template_name = 'performance/goal_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Goal updated successfully.')
        return reverse_lazy('performance:goal_detail', kwargs={'pk': self.object.id})


class GoalDeleteView(LoginRequiredMixin, CompanyContextMixin, DeleteView):
    model = PerformanceGoal
    template_name = 'performance/goal_confirm_delete.html'
    success_url = reverse_lazy('performance:goal_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Goal deleted successfully.')
        return super().delete(request, *args, **kwargs)


class FeedbackCreateView(LoginRequiredMixin, CompanyContextMixin, CreateView):
    model = PerformanceFeedback
    form_class = PerformanceFeedbackForm
    template_name = 'performance/feedback_form.html'

    def form_valid(self, form):
        form.instance.provided_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, 'Feedback submitted successfully.')
        return reverse_lazy('performance:feedback_detail', kwargs={'pk': self.object.id})


class FeedbackDetailView(LoginRequiredMixin, CompanyContextMixin, DetailView):
    model = PerformanceFeedback
    template_name = 'performance/feedback_detail.html'
    context_object_name = 'feedback'


# Dashboard View
def performance_dashboard(request):
    if not hasattr(request.user, 'company'):
        return redirect('home')
        
    context = {
        'recent_reviews': PerformanceReview.objects.filter(
            employee__company=request.user.company
        ).order_by('-review_date')[:5],
        'pending_reviews': PerformanceReview.objects.filter(
            employee__company=request.user.company,
            status='DRAFT'
        ).count(),
        'completed_reviews': PerformanceReview.objects.filter(
            employee__company=request.user.company,
            status='COMPLETED'
        ).count(),
    }
    return render(request, 'performance/dashboard.html', context)
