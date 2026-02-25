"""
Communication Models
Handles employee messaging, groups, and announcements
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

from tenant_management.models import TenantScopedModel

User = get_user_model()


class ChatGroup(TenantScopedModel):
    """Groups for employee communication"""
    
    class GroupType(models.TextChoices):
        DEPARTMENT = 'DEPARTMENT', 'Department'
        PROJECT = 'PROJECT', 'Project'
        TEAM = 'TEAM', 'Team'
        SOCIAL = 'SOCIAL', 'Social'
        ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'
        CUSTOM = 'CUSTOM', 'Custom'
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    group_type = models.CharField(max_length=20, choices=GroupType.choices, default=GroupType.CUSTOM)
    
    # Group ownership
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='chat_groups')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_groups')
    admins = models.ManyToManyField(User, related_name='administered_groups', blank=True)
    members = models.ManyToManyField(User, related_name='chat_groups', blank=True)
    
    # Group image
    group_image = models.ImageField(upload_to='group_images/', null=True, blank=True)
    
    # Settings
    is_private = models.BooleanField(default=False, help_text="Requires approval to join")
    allow_member_posts = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_activity']
        unique_together = ['tenant', 'name']
    
    def __str__(self):
        return self.name
    
    def get_member_count(self):
        return self.members.count()
    
    def get_unread_count(self, user):
        """Get count of unread messages for a user"""
        if user not in self.members.all():
            return 0
        
        last_read = GroupMessageRead.objects.filter(
            user=user,
            group=self
        ).first()
        
        if not last_read:
            return self.messages.count()
        
        return self.messages.filter(
            created_at__gt=last_read.last_read_at
        ).count()


class GroupMessage(TenantScopedModel):
    """Messages in groups"""
    
    class MessageType(models.TextChoices):
        TEXT = 'TEXT', 'Text'
        FILE = 'FILE', 'File'
        IMAGE = 'IMAGE', 'Image'
        ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'
    
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_group_messages')
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT)
    content = models.TextField()
    
    # Attachments
    attachment = models.FileField(upload_to='group_attachments/', null=True, blank=True)
    
    # Reply/Thread
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    # Message status
    is_pinned = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.sender.get_full_name() if self.sender else 'System'} in {self.group.name}"
    
    def get_reply_count(self):
        return self.replies.filter(is_deleted=False).count()


class GroupMessageRead(TenantScopedModel):
    """Track read status of group messages"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE)
    last_read_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = [['tenant', 'user', 'group']]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.group.name}"


class DirectMessage(TenantScopedModel):
    """One-on-one direct messages between employees"""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_direct_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_direct_messages')
    
    # Message content
    content = models.TextField()
    attachment = models.FileField(upload_to='direct_message_attachments/', null=True, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_recipient = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sender.get_full_name()} to {self.recipient.get_full_name()}"


class Announcement(TenantScopedModel):
    """Company-wide or department-specific announcements"""
    
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'
    
    class Audience(models.TextChoices):
        ALL_EMPLOYEES = 'ALL', 'All Employees'
        DEPARTMENT = 'DEPARTMENT', 'Specific Department'
        BRANCH = 'BRANCH', 'Specific Branch'
        CUSTOM = 'CUSTOM', 'Custom Group'
    
    # Announcement details
    title = models.CharField(max_length=255)
    content = models.TextField()
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    
    # Target audience
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='announcements')
    audience_type = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ALL_EMPLOYEES)
    target_department = models.CharField(max_length=100, blank=True)
    target_branch = models.ForeignKey('accounts.CompanyBranch', on_delete=models.SET_NULL, null=True, blank=True)
    specific_users = models.ManyToManyField(User, related_name='specific_announcements', blank=True)
    
    # Attachments
    attachment = models.FileField(upload_to='announcement_attachments/', null=True, blank=True)
    
    # Publishing
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='published_announcements')
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiry date")
    
    # Settings
    requires_acknowledgment = models.BooleanField(default=False, help_text="Employees must acknowledge reading")
    send_email = models.BooleanField(default=False)
    send_notification = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def is_active(self):
        """Check if announcement is currently active"""
        if not self.is_published:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
    
    def get_target_users(self):
        """Get all users who should see this announcement"""
        if self.audience_type == self.Audience.ALL_EMPLOYEES:
            return User.objects.filter(company=self.company, role='EMPLOYEE')
        elif self.audience_type == self.Audience.DEPARTMENT:
            return User.objects.filter(
                company=self.company,
                employee_profile__department=self.target_department,
                role='EMPLOYEE'
            )
        elif self.audience_type == self.Audience.BRANCH:
            return User.objects.filter(
                company=self.company,
                employee_profile__branch=self.target_branch,
                role='EMPLOYEE'
            )
        elif self.audience_type == self.Audience.CUSTOM:
            return self.specific_users.all()
        return User.objects.none()


class AnnouncementRead(TenantScopedModel):
    """Track who has read/acknowledged announcements"""
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='read_by')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['tenant', 'announcement', 'user']]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.announcement.title}"
