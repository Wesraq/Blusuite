from datetime import date

from django import forms

from blu_staff.apps.accounts.models import User
from .models import TrainingProgram, TrainingEnrollment


class TrainingProgramForm(forms.ModelForm):
    # Additional fields for enhanced training program management
    max_capacity = forms.IntegerField(
        label="Maximum Capacity",
        required=False,
        min_value=1,
        help_text="Maximum number of participants (leave blank for unlimited)",
        widget=forms.NumberInput(attrs={'placeholder': 'e.g., 20'})
    )
    location = forms.CharField(
        label="Location/Venue",
        required=False,
        max_length=200,
        help_text="Physical location or online platform (e.g., Zoom, Teams)",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., Conference Room A or Zoom'})
    )
    prerequisites = forms.CharField(
        label="Prerequisites",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Required skills or prior training'}),
        help_text="List any required prerequisites for this training"
    )
    learning_objectives = forms.CharField(
        label="Learning Objectives",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'What participants will learn'}),
        help_text="Key learning outcomes and objectives"
    )
    materials_required = forms.CharField(
        label="Materials/Resources",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Books, software, equipment, etc.'}),
        help_text="Materials or resources needed for the training"
    )
    start_date = forms.DateField(
        label="Start Date",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="When the training program begins"
    )
    end_date = forms.DateField(
        label="End Date",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="When the training program ends"
    )
    certification_offered = forms.BooleanField(
        label="Offers Certification",
        required=False,
        initial=False,
        help_text="Check if this training provides a certificate upon completion"
    )
    certification_name = forms.CharField(
        label="Certification Name",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., Certified Project Manager'}),
        help_text="Name of the certification (if applicable)"
    )
    
    class Meta:
        model = TrainingProgram
        fields = [
            "title",
            "description",
            "program_type",
            "department",
            "duration_hours",
            "is_mandatory",
            "cost",
            "provider",
            "instructor",
            "requires_approval",
        ]

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.instance.tenant = tenant

        if company is not None:
            department_field = self.fields.get("department")
            if department_field is not None:
                dept_qs = department_field.queryset.filter(company=company)
                if tenant is not None and hasattr(department_field.queryset.model, 'tenant_id'):
                    dept_qs = dept_qs.filter(tenant=tenant)
                department_field.queryset = dept_qs

        # Apply consistent styling to all fields
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} control-input".strip()

        # Enhanced field configurations
        self.fields["description"].widget = forms.Textarea(attrs={"rows": 4, "placeholder": "Detailed description of the training program"})
        self.fields["title"].widget.attrs['placeholder'] = "e.g., Advanced Excel Training"
        self.fields["duration_hours"].widget.attrs['placeholder'] = "e.g., 8.0"
        self.fields["cost"].widget.attrs['placeholder'] = "0.00"
        self.fields["provider"].widget.attrs['placeholder'] = "e.g., LinkedIn Learning"
        self.fields["instructor"].widget.attrs['placeholder'] = "e.g., John Smith"
        
        # Set helpful labels
        self.fields["duration_hours"].label = "Duration (Hours)"
        self.fields["is_mandatory"].label = "Mandatory Training"
        self.fields["requires_approval"].label = "Requires Approval"
        
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        certification_offered = cleaned_data.get('certification_offered')
        certification_name = cleaned_data.get('certification_name')
        
        # Validate date range
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("End date must be after start date")
        
        # Validate certification name if certification is offered
        if certification_offered and not certification_name:
            self.add_error('certification_name', 'Please provide a certification name if certification is offered')
        
        return cleaned_data


class TrainingEnrollmentForm(forms.ModelForm):
    class Meta:
        model = TrainingEnrollment
        fields = [
            "employee",
            "program",
            "enrollment_date",
            "start_date",
            "status",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.instance.tenant = tenant

        employee_field = self.fields.get("employee")
        program_field = self.fields.get("program")

        if employee_field is not None:
            qs = User.objects.filter(role=User.Role.EMPLOYEE)
            if company is not None:
                qs = qs.filter(company=company)
            employee_field.queryset = qs.order_by("first_name", "last_name")

        if program_field is not None:
            qs = TrainingProgram.objects.filter(is_active=True)
            if tenant is not None:
                qs = qs.filter(tenant=tenant)
            program_field.queryset = qs.order_by("title")

        self.fields["enrollment_date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["start_date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["notes"].widget = forms.Textarea(attrs={"rows": 3})
        self.fields["status"].initial = TrainingEnrollment.Status.ENROLLED
        self.fields["enrollment_date"].initial = date.today()

        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} control-input".strip()

    def clean(self):
        cleaned = super().clean()
        program = cleaned.get("program")
        if program and not program.is_active:
            self.add_error("program", "Cannot enroll into an inactive program.")
        return cleaned
