from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from tenant_management.models import TenantScopedModel

User = get_user_model()


class Task(TenantScopedModel):
    """Personal / team to-do task."""

    class Priority(models.TextChoices):
        LOW    = 'LOW',    _('Low')
        MEDIUM = 'MEDIUM', _('Medium')
        HIGH   = 'HIGH',   _('High')
        URGENT = 'URGENT', _('Urgent')

    class Status(models.TextChoices):
        TODO       = 'TODO',       _('To Do')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        DONE       = 'DONE',       _('Done')

    title       = models.CharField(_('title'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    created_by  = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='ems_created_tasks',
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ems_assigned_tasks',
    )
    due_date   = models.DateField(_('due date'), null=True, blank=True)
    priority   = models.CharField(
        _('priority'), max_length=10, choices=Priority.choices, default=Priority.MEDIUM,
    )
    status     = models.CharField(
        _('status'), max_length=20, choices=Status.choices, default=Status.TODO,
    )
    is_private = models.BooleanField(_('private (only visible to creator)'), default=False)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('task')
        verbose_name_plural = _('tasks')
        ordering = ['status', '-priority', 'due_date']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        from datetime import date
        return (self.due_date and self.due_date < date.today()
                and self.status != 'DONE')


class CalendarEvent(TenantScopedModel):
    """Company-wide or personal calendar event."""

    class EventType(models.TextChoices):
        MEETING    = 'MEETING',    _('Meeting')
        DEADLINE   = 'DEADLINE',   _('Deadline')
        REMINDER   = 'REMINDER',   _('Reminder')
        HOLIDAY    = 'HOLIDAY',    _('Holiday')
        OTHER      = 'OTHER',      _('Other')

    title       = models.CharField(_('title'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    event_type  = models.CharField(
        _('type'), max_length=20, choices=EventType.choices, default=EventType.OTHER,
    )
    start       = models.DateTimeField(_('start'))
    end         = models.DateTimeField(_('end'), null=True, blank=True)
    all_day     = models.BooleanField(_('all-day event'), default=False)
    color       = models.CharField(_('colour'), max_length=20, default='#1d4ed8')
    created_by  = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_events',
    )
    attendees   = models.ManyToManyField(
        User, blank=True, related_name='calendar_events',
    )
    is_company_wide = models.BooleanField(
        _('company-wide (visible to all)'), default=False,
    )
    location    = models.CharField(_('location'), max_length=200, blank=True)
    created_at  = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at  = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('calendar event')
        verbose_name_plural = _('calendar events')
        ordering = ['start']

    def __str__(self):
        return f"{self.title} ({self.start:%Y-%m-%d})"


class FileFolder(TenantScopedModel):
    """Folder hierarchy for the company File Manager."""
    name        = models.CharField(_('name'), max_length=120)
    parent      = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children',
    )
    created_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='file_folders',
    )
    is_shared   = models.BooleanField(_('shared with all employees'), default=True)
    color       = models.CharField(_('colour'), max_length=20, default='#1d4ed8')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('folder')
        verbose_name_plural = _('folders')
        ordering = ['name']
        unique_together = ['tenant', 'parent', 'name']

    def __str__(self):
        return self.name

    @property
    def path(self):
        parts = []
        node = self
        while node:
            parts.insert(0, node.name)
            node = node.parent
        return ' / '.join(parts)


class CompanyFile(TenantScopedModel):
    """Company-level file (not employee-scoped) for the File Manager."""
    folder      = models.ForeignKey(
        FileFolder, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='files',
    )
    name        = models.CharField(_('display name'), max_length=255)
    file        = models.FileField(_('file'), upload_to='company_files/')
    original_filename = models.CharField(max_length=255, blank=True)
    file_size   = models.PositiveIntegerField(default=0)
    mime_type   = models.CharField(max_length=100, default='application/octet-stream')
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='company_files',
    )
    is_shared   = models.BooleanField(_('visible to all employees'), default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('company file')
        verbose_name_plural = _('company files')
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            import os
            self.original_filename = os.path.basename(self.file.name)
            self.file_size = getattr(self.file, 'size', 0)
            self.mime_type = getattr(self.file, 'content_type', 'application/octet-stream')
        super().save(*args, **kwargs)

    @property
    def extension(self):
        import os
        return os.path.splitext(self.original_filename or self.name)[1].lower()

    @property
    def size_display(self):
        s = self.file_size
        if s < 1024:
            return f"{s} B"
        if s < 1024 ** 2:
            return f"{s/1024:.1f} KB"
        return f"{s/1024**2:.1f} MB"


class FeedPost(TenantScopedModel):
    """User-generated post in the company social feed / whiteboard."""

    author      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feed_posts')
    body        = models.TextField(_('body'))
    image       = models.ImageField(_('image'), upload_to='feed/images/', blank=True, null=True)
    attachment  = models.FileField(_('attachment'), upload_to='feed/attachments/', blank=True, null=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    is_pinned   = models.BooleanField(_('pinned'), default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('feed post')
        verbose_name_plural = _('feed posts')
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"{self.author}: {self.body[:60]}"


class FeedPostReaction(TenantScopedModel):
    """Emoji reaction on a FeedPost."""
    post  = models.ForeignKey(FeedPost, on_delete=models.CASCADE, related_name='reactions')
    user  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_reactions')
    emoji = models.CharField(max_length=10, default='👍')

    class Meta:
        unique_together = ['tenant', 'post', 'user', 'emoji']

    def __str__(self):
        return f"{self.user} {self.emoji} on post {self.post_id}"


class FeedPostComment(TenantScopedModel):
    """Comment on a FeedPost."""
    post       = models.ForeignKey(FeedPost, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_comments')
    body       = models.TextField(_('comment'))
    parent     = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('feed comment')
        verbose_name_plural = _('feed comments')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author} on post {self.post_id}"


class FeedReaction(TenantScopedModel):
    """Emoji reaction on an Announcement used as a social feed post."""
    announcement = models.ForeignKey(
        'communication.Announcement', on_delete=models.CASCADE,
        related_name='reactions',
    )
    user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feed_reactions')
    emoji  = models.CharField(max_length=10, default='👍')

    class Meta:
        unique_together = ['tenant', 'announcement', 'user', 'emoji']

    def __str__(self):
        return f"{self.user} {self.emoji}"


class FeedComment(TenantScopedModel):
    """Comment on an Announcement used as a social feed post."""
    announcement = models.ForeignKey(
        'communication.Announcement', on_delete=models.CASCADE,
        related_name='feed_comments',
    )
    author  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feed_comments')
    body    = models.TextField(_('comment'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('feed comment')
        verbose_name_plural = _('feed comments')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author} on {self.announcement}"
