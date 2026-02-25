from django.contrib import admin

# Register your models here.

from .models import SupportTicket, KnowledgeArticle


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'subject',
        'company',
        'priority',
        'status',
        'created_at',
    )
    list_filter = ('status', 'priority', 'company')
    search_fields = ('reference', 'subject', 'description', 'company__name')


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'visibility', 'is_published', 'created_at')
    list_filter = ('visibility', 'is_published', 'category')
    search_fields = ('title', 'summary', 'content', 'category')
    prepopulated_fields = {"slug": ("title",)}
