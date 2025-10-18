from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

User = get_user_model()


class PerformanceReview(models.Model):
    """Model for employee performance reviews"""

    class ReviewType(models.TextChoices):
        QUARTERLY = 'QUARTERLY', _('Quarterly Review')
        MID_YEAR = 'MID_YEAR', _('Mid-Year Review')
        ANNUAL = 'ANNUAL', _('Annual Review')
        PROBATION = 'PROBATION', _('Probation Review')
        SPECIAL = 'SPECIAL', _('Special Review')

    class OverallRating(models.TextChoices):
        OUTSTANDING = 'OUTSTANDING', _('Outstanding')
        EXCEEDS_EXPECTATIONS = 'EXCEEDS_EXPECTATIONS', _('Exceeds Expectations')
        MEETS_EXPECTATIONS = 'MEETS_EXPECTATIONS', _('Meets Expectations')
        BELOW_EXPECTATIONS = 'BELOW_EXPECTATIONS', _('Below Expectations')
        UNSATISFACTORY = 'UNSATISFACTORY', _('Unsatisfactory')

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='performance_reviews',
        limit_choices_to={'role': 'EMPLOYEE'}
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='conducted_reviews',
        limit_choices_to={'role__in': ['ADMIN', 'EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN']}
    )
    review_type = models.CharField(
        _('review type'),
        max_length=20,
        choices=ReviewType.choices,
        default=ReviewType.QUARTERLY
    )
    review_period_start = models.DateField(_('review period start'))
    review_period_end = models.DateField(_('review period end'))
    review_date = models.DateField(_('review date'), default=timezone.now)
    overall_rating = models.CharField(
        _('overall rating'),
        max_length=25,
        choices=OverallRating.choices,
        default=OverallRating.MEETS_EXPECTATIONS
    )
    title = models.CharField(_('review title'), max_length=200)
    objectives = models.TextField(_('review objectives'), blank=True)
    achievements = models.TextField(_('achievements'), blank=True)
    strengths = models.TextField(_('strengths'), blank=True)
    areas_for_improvement = models.TextField(_('areas for improvement'), blank=True)
    development_plan = models.TextField(_('development plan'), blank=True)
    goals_next_period = models.TextField(_('goals for next period'), blank=True)
    additional_comments = models.TextField(_('additional comments'), blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=[
            ('DRAFT', _('Draft')),
            ('SUBMITTED', _('Submitted')),
            ('UNDER_REVIEW', _('Under Review')),
            ('COMPLETED', _('Completed')),
            ('APPROVED', _('Approved'))
        ],
        default='DRAFT'
    )
    is_confidential = models.BooleanField(_('confidential'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('performance review')
        verbose_name_plural = _('performance reviews')
        ordering = ['-review_date', '-created_at']
        unique_together = ['employee', 'review_type', 'review_period_start', 'review_period_end']

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.get_review_type_display()} - {self.review_date}"

    def clean(self):
        """Validate the performance review"""
        if self.review_period_start >= self.review_period_end:
            raise ValidationError(_("Review period end must be after start"))

        if self.review_date < self.review_period_end:
            raise ValidationError(_("Review date cannot be before the end of review period"))

    def get_rating_score(self):
        """Convert rating to numeric score"""
        rating_scores = {
            'OUTSTANDING': 5,
            'EXCEEDS_EXPECTATIONS': 4,
            'MEETS_EXPECTATIONS': 3,
            'BELOW_EXPECTATIONS': 2,
            'UNSATISFACTORY': 1
        }
        return rating_scores.get(self.overall_rating, 3)


class PerformanceGoal(models.Model):
    """Model for individual performance goals"""

    class Status(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', _('Not Started')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    class Priority(models.TextChoices):
        LOW = 'LOW', _('Low')
        MEDIUM = 'MEDIUM', _('Medium')
        HIGH = 'HIGH', _('High')
        CRITICAL = 'CRITICAL', _('Critical')

    review = models.ForeignKey(
        PerformanceReview,
        on_delete=models.CASCADE,
        related_name='goals'
    )
    title = models.CharField(_('goal title'), max_length=200)
    description = models.TextField(_('goal description'), blank=True)
    category = models.CharField(_('category'), max_length=100, blank=True)
    priority = models.CharField(
        _('priority'),
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED
    )
    progress_percentage = models.PositiveIntegerField(
        _('progress percentage'),
        default=0,
        help_text=_('Progress from 0 to 100%')
    )
    target_completion_date = models.DateField(_('target completion date'), null=True, blank=True)
    actual_completion_date = models.DateField(_('actual completion date'), null=True, blank=True)
    success_criteria = models.TextField(_('success criteria'), blank=True)
    challenges = models.TextField(_('challenges faced'), blank=True)
    support_needed = models.TextField(_('support needed'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('performance goal')
        verbose_name_plural = _('performance goals')
        ordering = ['priority', 'created_at']

    def __str__(self):
        return f"{self.review.employee.get_full_name()} - {self.title}"

    def clean(self):
        """Validate the goal"""
        if self.progress_percentage > 100:
            raise ValidationError(_("Progress percentage cannot exceed 100%"))

        if self.status == 'COMPLETED' and self.actual_completion_date is None:
            raise ValidationError(_("Actual completion date is required for completed goals"))


class PerformanceMetric(models.Model):
    """Model for quantitative performance metrics"""

    class MetricType(models.TextChoices):
        NUMERIC = 'NUMERIC', _('Numeric')
        PERCENTAGE = 'PERCENTAGE', _('Percentage')
        CURRENCY = 'CURRENCY', _('Currency')
        TIME = 'TIME', _('Time-based')

    review = models.ForeignKey(
        PerformanceReview,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    name = models.CharField(_('metric name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    metric_type = models.CharField(
        _('metric type'),
        max_length=20,
        choices=MetricType.choices,
        default=MetricType.NUMERIC
    )
    target_value = models.DecimalField(_('target value'), max_digits=15, decimal_places=2)
    actual_value = models.DecimalField(
        _('actual value'),
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    unit = models.CharField(_('unit'), max_length=50, blank=True)
    weight = models.PositiveIntegerField(
        _('weight'),
        default=100,
        help_text=_('Relative weight of this metric in the overall review')
    )
    is_achieved = models.BooleanField(_('achieved'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('performance metric')
        verbose_name_plural = _('performance metrics')
        ordering = ['weight', 'name']

    def __str__(self):
        return f"{self.review.employee.get_full_name()} - {self.name}"

    def clean(self):
        """Validate the metric"""
        if self.weight > 1000:
            raise ValidationError(_("Weight cannot exceed 1000"))

    @property
    def achievement_percentage(self):
        """Calculate achievement percentage"""
        if self.target_value and self.actual_value is not None:
            if self.target_value != 0:
                return min((self.actual_value / self.target_value) * 100, 1000)
        return 0

    @property
    def is_target_achieved(self):
        """Check if target is achieved"""
        if self.actual_value is not None and self.target_value:
            return self.actual_value >= self.target_value
        return False


class PerformanceFeedback(models.Model):
    """Model for feedback from colleagues and managers"""

    class FeedbackType(models.TextChoices):
        SELF_ASSESSMENT = 'SELF', _('Self Assessment')
        MANAGER_FEEDBACK = 'MANAGER', _('Manager Feedback')
        PEER_FEEDBACK = 'PEER', _('Peer Feedback')
        SUBORDINATE_FEEDBACK = 'SUBORDINATE', _('Subordinate Feedback')
        CUSTOMER_FEEDBACK = 'CUSTOMER', _('Customer Feedback')

    review = models.ForeignKey(
        PerformanceReview,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    feedback_type = models.CharField(
        _('feedback type'),
        max_length=20,
        choices=FeedbackType.choices,
        default=FeedbackType.MANAGER_FEEDBACK
    )
    provided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='provided_feedback'
    )
    relationship_to_employee = models.CharField(
        _('relationship to employee'),
        max_length=100,
        blank=True,
        help_text=_('e.g., Direct Manager, Colleague, Team Member')
    )
    rating = models.PositiveIntegerField(
        _('rating'),
        help_text=_('Rating from 1 to 5')
    )
    strengths = models.TextField(_('strengths'), blank=True)
    areas_for_improvement = models.TextField(_('areas for improvement'), blank=True)
    overall_comments = models.TextField(_('overall comments'), blank=True)
    suggestions = models.TextField(_('suggestions'), blank=True)
    is_anonymous = models.BooleanField(_('anonymous'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('performance feedback')
        verbose_name_plural = _('performance feedback')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_feedback_type_display()} - {self.review.employee.get_full_name()}"

    def clean(self):
        """Validate the feedback"""
        if self.rating < 1 or self.rating > 5:
            raise ValidationError(_("Rating must be between 1 and 5"))

        # Prevent self-feedback for non-self assessment
        if (self.feedback_type != self.FeedbackType.SELF_ASSESSMENT and
            self.provided_by == self.review.employee):
            raise ValidationError(_("Cannot provide non-self assessment feedback for yourself"))


class PerformanceTemplate(models.Model):
    """Model for performance review templates"""

    name = models.CharField(_('template name'), max_length=200, unique=True)
    description = models.TextField(_('description'), blank=True)
    review_type = models.CharField(
        _('review type'),
        max_length=20,
        choices=PerformanceReview.ReviewType.choices,
        default=PerformanceReview.ReviewType.QUARTERLY
    )
    is_default = models.BooleanField(_('default template'), default=False)
    sections = models.JSONField(
        _('template sections'),
        default=dict,
        help_text=_('JSON structure defining template sections and fields')
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_performance_templates'
    )
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('performance template')
        verbose_name_plural = _('performance templates')
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_review_type_display()})"

    def save(self, *args, **kwargs):
        """Ensure only one default template per review type"""
        if self.is_default:
            # Set other templates of same type to non-default
            PerformanceTemplate.objects.filter(
                review_type=self.review_type,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
