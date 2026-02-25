from django import forms

from .models import KnowledgeArticle, SupportTicket


class KnowledgeArticleForm(forms.ModelForm):
    """Form for creating and editing Knowledge Base articles for tenants."""

    class Meta:
        model = KnowledgeArticle
        fields = [
            "title",
            "slug",
            "summary",
            "content",
            "video_url",
            "media_file",
            "category",
            "visibility",
            "is_published",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Article title"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional URL slug (leave blank to auto-fill)"}),
            "summary": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Short summary shown in the list"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 8, "placeholder": "Full training content, links, notes..."}),
            "video_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "Optional training video URL (YouTube, Vimeo or file link)"}),
            "media_file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "category": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Getting Started, Updates, Training"}),
            "visibility": forms.Select(attrs={"class": "form-control"}),
        }

    def save(self, commit=True):
        article = super().save(commit=False)
        if not article.slug:
            # Basic slug auto-fill from title if not provided
            from django.utils.text import slugify

            article.slug = slugify(article.title)[:220]
        if commit:
            article.save()
        return article


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = [
            "subject",
            "category",
            "priority",
            "description",
            "contact_email",
        ]
        widgets = {
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Brief summary of the issue"}
            ),
            "category": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Payroll, Attendance, Access"}
            ),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Describe the issue, steps taken and impact.",
                }
            ),
            "contact_email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "Where we can reach you"}
            ),
        }
