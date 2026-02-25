from datetime import date, timedelta

from django import forms

from blu_staff.apps.accounts.models import User
from .models import (
    OnboardingChecklist,
    EmployeeOnboarding,
    EmployeeOffboarding,
    OffboardingChecklist,
)


class EmployeeOnboardingForm(forms.ModelForm):
    class Meta:
        model = EmployeeOnboarding
        fields = [
            "employee",
            "checklist",
            "start_date",
            "expected_completion_date",
            "buddy",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.instance.tenant = tenant

        employee_qs = User.objects.filter(role=User.Role.EMPLOYEE)
        if company is not None:
            employee_qs = employee_qs.filter(company=company)
        employee_qs = employee_qs.filter(onboarding__isnull=True).order_by("first_name", "last_name")
        self.fields["employee"].queryset = employee_qs

        checklist_qs = OnboardingChecklist.objects.all()
        if tenant is not None:
            checklist_qs = checklist_qs.filter(tenant=tenant, is_active=True)
        self.fields["checklist"].queryset = checklist_qs.order_by("name")

        buddy_qs = User.objects.filter(role=User.Role.EMPLOYEE)
        if company is not None:
            buddy_qs = buddy_qs.filter(company=company)
        self.fields["buddy"].queryset = buddy_qs.order_by("first_name", "last_name")

        self.fields["start_date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["expected_completion_date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["notes"].widget = forms.Textarea(attrs={"rows": 3})
        self.fields["start_date"].initial = date.today()
        self.fields["expected_completion_date"].initial = date.today() + timedelta(days=30)

        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} control-input".strip()

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        expected = cleaned.get("expected_completion_date")
        if start_date and expected and expected < start_date:
            self.add_error("expected_completion_date", "Expected completion must be on or after the start date.")
        return cleaned


class EmployeeOffboardingForm(forms.ModelForm):
    class Meta:
        model = EmployeeOffboarding
        fields = [
            "employee",
            "checklist",
            "last_working_date",
            "reason",
            "notes",
            "exit_interview_completed",
        ]

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.instance.tenant = tenant

        employee_qs = User.objects.filter(role=User.Role.EMPLOYEE)
        if company is not None:
            employee_qs = employee_qs.filter(company=company)
        employee_qs = employee_qs.filter(offboarding__isnull=True).order_by("first_name", "last_name")
        self.fields["employee"].queryset = employee_qs

        checklist_qs = OffboardingChecklist.objects.all()
        if tenant is not None:
            checklist_qs = checklist_qs.filter(tenant=tenant, is_active=True)
        self.fields["checklist"].queryset = checklist_qs.order_by("name")

        self.fields["last_working_date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["notes"].widget = forms.Textarea(attrs={"rows": 3})
        self.fields["last_working_date"].initial = date.today()

        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} control-input".strip()
