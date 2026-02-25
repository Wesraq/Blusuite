from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid

class SupportTicket(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        NORMAL = 'NORMAL', 'Normal'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'

    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_tickets',
    )
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_support_tickets',
    )
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    category = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=20, unique=True, editable=False)
    contact_email = models.EmailField(blank=True)
    last_response_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.reference}] {self.subject}" if self.reference else self.subject

    def save(self, *args, **kwargs):
        if not self.reference:
            # Simple human-friendly reference like ST-000123
            prefix = 'ST-'
            last_id = (
                SupportTicket.objects.order_by('-id').values_list('id', flat=True).first()
            ) or 0
            self.reference = f"{prefix}{last_id + 1:06d}"
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        if self.priority == self.Priority.URGENT:
            return self.status not in [self.Status.RESOLVED, self.Status.CLOSED] and \
                   (timezone.now() - self.created_at).hours > 2
        elif self.priority == self.Priority.HIGH:
            return self.status not in [self.Status.RESOLVED, self.Status.CLOSED] and \
                   (timezone.now() - self.created_at).hours > 8
        elif self.priority == self.Priority.NORMAL:
            return self.status not in [self.Status.RESOLVED, self.Status.CLOSED] and \
                   (timezone.now() - self.created_at).days > 2
        return False


class TicketResponse(models.Model):
    """Responses and updates to support tickets"""
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='responses')
    author = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    response_type = models.CharField(
        max_length=20,
        choices=[
            ('INTERNAL', 'Internal Note'),
            ('CUSTOMER', 'Customer Response'),
            ('SYSTEM', 'System Update')
        ],
        default='CUSTOMER'
    )
    message = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        
    def __str__(self):
        return f"Response to {self.ticket.reference} by {self.author}"


class SupportCategory(models.Model):
    """Categories for organizing support tickets"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)  # Icon class
    color = models.CharField(max_length=7, default='#64748b')  # Hex color
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Support Categories'
        
    def __str__(self):
        return self.name


class SupportTeam(models.Model):
    """Support team members and their assignments"""
    
    class Role(models.TextChoices):
        AGENT = 'AGENT', 'Support Agent'
        LEAD = 'LEAD', 'Team Lead'
        MANAGER = 'MANAGER', 'Support Manager'
        
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='support_profile'
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.AGENT)
    specialties = models.ManyToManyField(SupportCategory, blank=True)
    max_tickets = models.PositiveIntegerField(default=20)
    is_available = models.BooleanField(default=True)
    avg_response_time = models.DurationField(null=True, blank=True)
    tickets_resolved = models.PositiveIntegerField(default=0)
    satisfaction_score = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Average satisfaction rating (1-5)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['role', 'user__email']
        
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role}"
    
    @property
    def current_workload(self):
        """Current number of open tickets assigned to this agent"""
        return SupportTicket.objects.filter(
            assigned_to=self.user,
            status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS]
        ).count()
    
    @property
    def workload_percentage(self):
        """Percentage of max tickets currently assigned"""
        if self.max_tickets > 0:
            return (self.current_workload / self.max_tickets) * 100
        return 0


class ServiceLevelAgreement(models.Model):
    """SLA configurations for different priority levels"""
    
    priority = models.CharField(
        max_length=10,
        choices=SupportTicket.Priority.choices,
        unique=True
    )
    response_time_hours = models.PositiveIntegerField(
        help_text="Maximum hours to first response"
    )
    resolution_time_hours = models.PositiveIntegerField(
        help_text="Maximum hours to resolve"
    )
    business_hours_only = models.BooleanField(
        default=True,
        help_text="Count only business hours for SLA calculation"
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['priority']
        
    def __str__(self):
        return f"SLA for {self.priority} priority"


class SatisfactionSurvey(models.Model):
    """Customer satisfaction surveys for resolved tickets"""
    
    ticket = models.OneToOneField(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='satisfaction_survey'
    )
    rating = models.PositiveIntegerField(
        choices=[(1, 'Very Poor'), (2, 'Poor'), (3, 'Average'), (4, 'Good'), (5, 'Excellent')]
    )
    feedback = models.TextField(blank=True)
    would_recommend = models.BooleanField(null=True, blank=True)
    surveyed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-surveyed_at']
        
    def __str__(self):
        return f"Survey for {self.ticket.reference} - {self.rating}/5"


class KnowledgeArticle(models.Model):
    """Knowledge base article for tenant/company portals."""

    class Visibility(models.TextChoices):
        TENANTS = 'TENANTS', 'All Tenants'
        INTERNAL = 'INTERNAL', 'Internal Only'

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    summary = models.TextField(blank=True)
    content = models.TextField()
    video_url = models.URLField(blank=True, help_text="Optional link to a training video or external resource.")
    media_file = models.FileField(
        upload_to='knowledge_base/',
        blank=True,
        null=True,
        help_text="Optional uploaded media (video, image or PDF) stored in the platform.",
    )
    category = models.CharField(max_length=100, blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.TENANTS,
    )
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='knowledge_articles',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
