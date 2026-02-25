from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from blu_staff.apps.accounts.models import User
from .models import Benefit, EmployeeBenefit


class BenefitForm(forms.ModelForm):
    class Meta:
        model = Benefit
        fields = [
            "name",
            "benefit_type",
            "description",
            "company_contribution",
            "employee_contribution",
            "is_mandatory",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget = forms.Textarea(attrs={"rows": 3})
        self.fields["company_contribution"].widget = forms.NumberInput(attrs={"step": "0.01"})
        self.fields["employee_contribution"].widget = forms.NumberInput(attrs={"step": "0.01"})
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} control-input".strip()

    def clean_company_contribution(self):
        value = self.cleaned_data.get("company_contribution", Decimal("0"))
        if value < 0:
            raise forms.ValidationError(
                _("Company contribution cannot be negative.")
            )
        return value

    def clean_employee_contribution(self):
        value = self.cleaned_data.get("employee_contribution", Decimal("0"))
        if value < 0:
            raise forms.ValidationError(
                _("Employee contribution cannot be negative.")
            )
        return value


class BenefitEnrollmentForm(forms.ModelForm):
    class Meta:
        model = EmployeeBenefit
        fields = [
            "employee",
            "benefit",
            "enrollment_date",
            "effective_date",
            "status",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)

        self.fields["status"].initial = EmployeeBenefit.Status.ACTIVE
        self.fields["enrollment_date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["effective_date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["notes"].widget = forms.Textarea(attrs={"rows": 3})

        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} control-input".strip()

        employee_qs = User.objects.filter(role=User.Role.EMPLOYEE)
        benefit_qs = Benefit.objects.filter(is_active=True)

        if company:
            employee_qs = employee_qs.filter(company=company)
        if tenant:
            benefit_qs = benefit_qs.filter(tenant=tenant)

        self.fields["employee"].queryset = employee_qs.order_by("first_name", "last_name")
        self.fields["benefit"].queryset = benefit_qs.order_by("name")

    def clean(self):
        cleaned = super().clean()
        benefit = cleaned.get("benefit")
        if benefit and not benefit.is_active:
            self.add_error("benefit", _("Cannot enroll in an inactive benefit."))
        return cleaned
