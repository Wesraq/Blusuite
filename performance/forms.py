from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import PerformanceReview, PerformanceGoal, PerformanceFeedback

class PerformanceReviewForm(forms.ModelForm):
    class Meta:
        model = PerformanceReview
        fields = [
            'employee', 'review_type', 'review_period_start', 'review_period_end',
            'review_date', 'overall_rating', 'title', 'objectives', 'achievements',
            'strengths', 'areas_for_improvement', 'development_plan',
            'goals_next_period', 'additional_comments', 'status', 'is_confidential'
        ]
        widgets = {
            'review_period_start': forms.DateInput(attrs={'type': 'date'}),
            'review_period_end': forms.DateInput(attrs={'type': 'date'}),
            'review_date': forms.DateInput(attrs={'type': 'date', 'value': timezone.now().date()}),
            'objectives': forms.Textarea(attrs={'rows': 3}),
            'achievements': forms.Textarea(attrs={'rows': 3}),
            'strengths': forms.Textarea(attrs={'rows': 3}),
            'areas_for_improvement': forms.Textarea(attrs={'rows': 3}),
            'development_plan': forms.Textarea(attrs={'rows': 3}),
            'goals_next_period': forms.Textarea(attrs={'rows': 3}),
            'additional_comments': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Limit employee choices based on user role
        if user and user.role in ['EMPLOYER', 'EMPLOYER_ADMIN']:
            self.fields['employee'].queryset = user.company.employees.all()


class PerformanceGoalForm(forms.ModelForm):
    class Meta:
        model = PerformanceGoal
        fields = [
            'title', 'description', 'category', 'priority', 'status',
            'target_completion_date', 'success_criteria', 'challenges', 'support_needed'
        ]
        widgets = {
            'target_completion_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'success_criteria': forms.Textarea(attrs={'rows': 2}),
            'challenges': forms.Textarea(attrs={'rows': 2}),
            'support_needed': forms.Textarea(attrs={'rows': 2}),
        }


class PerformanceFeedbackForm(forms.ModelForm):
    class Meta:
        model = PerformanceFeedback
        fields = [
            'feedback_type', 'rating', 'strengths', 'areas_for_improvement',
            'overall_comments', 'suggestions', 'is_anonymous'
        ]
        widgets = {
            'strengths': forms.Textarea(attrs={'rows': 3}),
            'areas_for_improvement': forms.Textarea(attrs={'rows': 3}),
            'overall_comments': forms.Textarea(attrs={'rows': 3}),
            'suggestions': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rating'].widget.attrs.update({'min': '1', 'max': '5'})
