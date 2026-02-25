"""
BLU Projects - Project Management Models
Comprehensive project management with tasks, milestones, time tracking, and team collaboration.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class Project(models.Model):
    """Main project model"""
    STATUS_CHOICES = [
        ('PLANNING', 'Planning'),
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, help_text="Unique project code (e.g., PROJ-001)")
    description = models.TextField(blank=True)
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='projects')
    
    # Project Details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNING')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Budget
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Progress
    progress_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Team
    project_manager = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='managed_projects'
    )
    team_members = models.ManyToManyField(User, related_name='project_memberships', blank=True)
    
    # Client Information
    client_name = models.CharField(max_length=200, blank=True)
    client_contact = models.CharField(max_length=200, blank=True)
    client_email = models.EmailField(blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def is_overdue(self):
        """Check if project is overdue"""
        if self.status in ['COMPLETED', 'CANCELLED']:
            return False
        return timezone.now().date() > self.end_date
    
    def days_remaining(self):
        """Calculate days remaining"""
        if self.status in ['COMPLETED', 'CANCELLED']:
            return 0
        delta = self.end_date - timezone.now().date()
        return max(0, delta.days)
    
    def update_progress(self):
        """Auto-calculate progress based on tasks"""
        tasks = self.tasks.all()
        if not tasks.exists():
            self.progress_percentage = 0
        else:
            completed = tasks.filter(status='COMPLETED').count()
            self.progress_percentage = int((completed / tasks.count()) * 100)
        self.save()


class ProjectMilestone(models.Model):
    """Project milestones/phases"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('DELAYED', 'Delayed'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    due_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['project', 'order', 'due_date']
    
    def __str__(self):
        return f"{self.project.code} - {self.name}"
    
    def is_overdue(self):
        if self.status == 'COMPLETED':
            return False
        return timezone.now().date() > self.due_date


class Task(models.Model):
    """Project tasks"""
    STATUS_CHOICES = [
        ('TODO', 'To Do'),
        ('IN_PROGRESS', 'In Progress'),
        ('IN_REVIEW', 'In Review'),
        ('COMPLETED', 'Completed'),
        ('BLOCKED', 'Blocked'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    milestone = models.ForeignKey(
        ProjectMilestone, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='tasks'
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )
    
    # Dates
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Effort estimation
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # Dependencies
    depends_on = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='blocking_tasks')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'due_date']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"{self.project.code} - {self.title}"
    
    def is_overdue(self):
        if self.status == 'COMPLETED' or not self.due_date:
            return False
        return timezone.now().date() > self.due_date


class TimeEntry(models.Model):
    """Time tracking for tasks"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='time_entries')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_entries')
    
    date = models.DateField(default=timezone.now)
    hours = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0.1)])
    description = models.TextField(blank=True)
    
    # Billing
    is_billable = models.BooleanField(default=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['task', 'date']),
            models.Index(fields=['user', 'date']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.hours}h on {self.task.title}"
    
    def calculate_cost(self):
        """Calculate cost based on hourly rate"""
        if self.hourly_rate:
            return self.hours * self.hourly_rate
        return 0


class TaskComment(models.Model):
    """Comments on tasks"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    comment = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.user.get_full_name()} on {self.task.title}"


class ProjectDocument(models.Model):
    """Project-related documents"""
    CATEGORY_CHOICES = [
        ('REQUIREMENT', 'Requirement'),
        ('DESIGN', 'Design'),
        ('SPECIFICATION', 'Specification'),
        ('REPORT', 'Report'),
        ('CONTRACT', 'Contract'),
        ('OTHER', 'Other'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='documents')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    
    file = models.FileField(upload_to='projects/documents/%Y/%m/')
    file_size = models.IntegerField(default=0)  # in bytes
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.project.code} - {self.title}"
    
    def get_file_size_display(self):
        """Human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class ProjectActivity(models.Model):
    """Activity log for projects"""
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('TASK_ADDED', 'Task Added'),
        ('TASK_COMPLETED', 'Task Completed'),
        ('MEMBER_ADDED', 'Member Added'),
        ('MEMBER_REMOVED', 'Member Removed'),
        ('DOCUMENT_UPLOADED', 'Document Uploaded'),
        ('COMMENT_ADDED', 'Comment Added'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    description = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Project activities'
    
    def __str__(self):
        return f"{self.project.code} - {self.action}"


# ============================================================================
# CLIENT PORTAL MODELS
# ============================================================================

class ProjectSLA(models.Model):
    """SLA terms for a project"""
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='sla')
    
    # Response Times (in hours)
    critical_response_time = models.IntegerField(default=2, help_text="Hours to respond to critical issues")
    high_response_time = models.IntegerField(default=8, help_text="Hours to respond to high priority issues")
    medium_response_time = models.IntegerField(default=24, help_text="Hours to respond to medium priority issues")
    low_response_time = models.IntegerField(default=48, help_text="Hours to respond to low priority issues")
    
    # Resolution Times (in hours)
    critical_resolution_time = models.IntegerField(default=8, help_text="Hours to resolve critical issues")
    high_resolution_time = models.IntegerField(default=24, help_text="Hours to resolve high priority issues")
    medium_resolution_time = models.IntegerField(default=72, help_text="Hours to resolve medium priority issues")
    low_resolution_time = models.IntegerField(default=120, help_text="Hours to resolve low priority issues")
    
    # Support Terms
    support_hours = models.CharField(max_length=100, default="9 AM - 5 PM, Mon-Fri", help_text="Support availability hours")
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=50, blank=True)
    
    # Maintenance Period
    maintenance_start_date = models.DateField(null=True, blank=True, help_text="Start of maintenance/warranty period")
    maintenance_end_date = models.DateField(null=True, blank=True, help_text="End of maintenance/warranty period")
    maintenance_terms = models.TextField(blank=True, help_text="Maintenance contract terms")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"SLA for {self.project.name}"
    
    def is_maintenance_active(self):
        """Check if project is in maintenance period"""
        if not self.maintenance_start_date or not self.maintenance_end_date:
            return False
        today = timezone.now().date()
        return self.maintenance_start_date <= today <= self.maintenance_end_date


class ClientIssue(models.Model):
    """Client-reported issues/tickets"""
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('WAITING_CLIENT', 'Waiting for Client'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    CATEGORY_CHOICES = [
        ('BUG', 'Bug/Error'),
        ('FEATURE', 'Feature Request'),
        ('SUPPORT', 'Support Question'),
        ('MAINTENANCE', 'Maintenance'),
        ('PERFORMANCE', 'Performance Issue'),
        ('OTHER', 'Other'),
    ]
    
    # Basic Information
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='client_issues')
    issue_number = models.CharField(max_length=50, unique=True, help_text="Auto-generated issue number")
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Classification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='SUPPORT')
    
    # People
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_issues')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_issues')
    
    # SLA Tracking
    reported_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # SLA Breach Flags
    response_sla_breached = models.BooleanField(default=False)
    resolution_sla_breached = models.BooleanField(default=False)
    
    # Additional Info
    attachments_count = models.IntegerField(default=0)
    is_maintenance_issue = models.BooleanField(default=False, help_text="Issue during maintenance period")
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-reported_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['issue_number']),
        ]
    
    def __str__(self):
        return f"{self.issue_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.issue_number:
            # Generate issue number: PROJ-001-ISS-001
            last_issue = ClientIssue.objects.filter(project=self.project).order_by('-id').first()
            if last_issue and last_issue.issue_number:
                try:
                    last_num = int(last_issue.issue_number.split('-')[-1])
                    new_num = last_num + 1
                except:
                    new_num = 1
            else:
                new_num = 1
            self.issue_number = f"{self.project.code}-ISS-{new_num:03d}"
        super().save(*args, **kwargs)
    
    def check_sla_breach(self):
        """Check if SLA has been breached"""
        if not hasattr(self.project, 'sla'):
            return
        
        sla = self.project.sla
        now = timezone.now()
        
        # Get response time based on priority
        response_times = {
            'CRITICAL': sla.critical_response_time,
            'HIGH': sla.high_response_time,
            'MEDIUM': sla.medium_response_time,
            'LOW': sla.low_response_time,
        }
        
        resolution_times = {
            'CRITICAL': sla.critical_resolution_time,
            'HIGH': sla.high_resolution_time,
            'MEDIUM': sla.medium_resolution_time,
            'LOW': sla.low_resolution_time,
        }
        
        response_time = response_times.get(self.priority, 24)
        resolution_time = resolution_times.get(self.priority, 72)
        
        # Check response SLA
        if not self.acknowledged_at:
            hours_since_report = (now - self.reported_at).total_seconds() / 3600
            if hours_since_report > response_time:
                self.response_sla_breached = True
        
        # Check resolution SLA
        if self.status not in ['RESOLVED', 'CLOSED']:
            hours_since_report = (now - self.reported_at).total_seconds() / 3600
            if hours_since_report > resolution_time:
                self.resolution_sla_breached = True
        
        self.save()
    
    def time_to_response(self):
        """Calculate time taken to respond"""
        if self.acknowledged_at:
            delta = self.acknowledged_at - self.reported_at
            return delta.total_seconds() / 3600  # Return hours
        return None
    
    def time_to_resolution(self):
        """Calculate time taken to resolve"""
        if self.resolved_at:
            delta = self.resolved_at - self.reported_at
            return delta.total_seconds() / 3600  # Return hours
        return None


class IssueComment(models.Model):
    """Comments on client issues"""
    issue = models.ForeignKey(ClientIssue, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    comment = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Internal note, not visible to client")
    is_resolution = models.BooleanField(default=False, help_text="This comment contains the resolution")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment on {self.issue.issue_number} by {self.user}"


class IssueAttachment(models.Model):
    """File attachments for issues"""
    issue = models.ForeignKey(ClientIssue, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    file = models.FileField(upload_to='issue_attachments/%Y/%m/')
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes")
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.filename} - {self.issue.issue_number}"


class ClientAccess(models.Model):
    """Track which clients have access to which projects"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_projects')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='client_users')
    
    ACCESS_LEVEL_CHOICES = [
        ('VIEW', 'View Only'),
        ('REPORT', 'Can Report Issues'),
        ('FULL', 'Full Access'),
    ]
    
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='REPORT')
    can_view_internal_notes = models.BooleanField(default=False)
    
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_access')
    
    class Meta:
        unique_together = ['user', 'project']
        verbose_name_plural = 'Client access'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.project.name}"
