from django import forms
from django.contrib.auth import get_user_model
from .models import (
    Company,
    CompanyBiometricSettings,
    CompanyDepartment,
    CompanyEmailSettings,
    CompanyPayGrade,
    CompanyPosition,
    CompanyRegistrationRequest,
    EmployeeIdConfiguration,
    EmployeeProfile,
    CompanyNotificationSettings,
    CompanyAPIKey,
)


class CompanyRegistrationForm(forms.ModelForm):
    """Form for company registration requests"""

    class Meta:
        model = CompanyRegistrationRequest
        fields = [
            'company_name', 'company_address', 'company_phone', 'company_email',
            'company_website', 'tax_id', 'contact_first_name', 'contact_last_name',
            'contact_email', 'contact_phone', 'contact_position', 'subscription_plan',
            'number_of_employees', 'business_type', 'company_size'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Full company address'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company phone number'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'company@domain.com'}),
            'company_website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://company.com'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tax identification number'}),
            'contact_first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'contact_last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@company.com'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact phone number'}),
            'contact_position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Position/Title'}),
            'subscription_plan': forms.Select(attrs={'class': 'form-control'}),
            'number_of_employees': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'business_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Technology, Healthcare, Finance'}),
            'company_size': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Startup, SME, Enterprise'}),
        }

    def clean_contact_email(self):
        """Ensure contact email is different from company email"""
        contact_email = self.cleaned_data.get('contact_email')
        company_email = self.cleaned_data.get('company_email')

        if contact_email and company_email and contact_email == company_email:
            raise forms.ValidationError('Contact email must be different from company email.')

        return contact_email


class EmployeeRegistrationForm(forms.ModelForm):
    """Form for registering new employees"""
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'employee@company.com'})
    )
    first_name = forms.CharField(
        label='First Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'})
    )
    last_name = forms.CharField(
        label='Last Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'})
    )
    position = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Position'})
    )
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department'})
    )
    phone_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'})
    )
    
    class Meta:
        model = get_user_model()
        fields = ['email', 'first_name', 'last_name']
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if get_user_model().objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email
    
    def save(self, commit=True):
        # Generate a random password
        import random
        import string
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        # Create the user
        user = super().save(commit=False)
        user.set_password(password)
        user.role = 'EMPLOYEE'
        user.is_active = True
        
        if commit:
            user.save()
            
            # Create employee profile
            EmployeeProfile.objects.create(
                user=user,
                company=self.company,
                position=self.cleaned_data.get('position', ''),
                department=self.cleaned_data.get('department', ''),
                phone_number=self.cleaned_data.get('phone_number', '')
            )
            
            # Send welcome email with credentials (implement this function)
            # self._send_welcome_email(user, password)
        
        return user

    def clean(self):
        """Custom validation"""
        cleaned_data = super().clean()
        company_email = cleaned_data.get('company_email')
        contact_email = cleaned_data.get('contact_email')

        # Check if emails are already registered
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if company_email and User.objects.filter(email=company_email).exists():
            raise forms.ValidationError(f'Company email {company_email} is already registered.')

        if contact_email and User.objects.filter(email=contact_email).exists():
            raise forms.ValidationError(f'Contact email {contact_email} is already registered.')

        return cleaned_data


class EmployeeIdConfigurationForm(forms.ModelForm):
    class Meta:
        model = EmployeeIdConfiguration
        fields = ['prefix', 'suffix', 'padding']
        widgets = {
            'prefix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prefix e.g. EMP-'}),
            'suffix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Suffix'}),
            'padding': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 8}),
        }


class CompanyDepartmentForm(forms.ModelForm):
    class Meta:
        model = CompanyDepartment
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department name'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        department = super().save(commit=False)
        if self.company:
            department.company = self.company
        if commit:
            department.save()
        return department


class CompanyPositionForm(forms.ModelForm):
    department = forms.ModelChoiceField(
        queryset=CompanyDepartment.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CompanyPosition
        fields = ['name', 'department']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Position title'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if self.company:
            self.fields['department'].queryset = CompanyDepartment.objects.filter(company=self.company).order_by('name')

    def save(self, commit=True):
        position = super().save(commit=False)
        if self.company:
            position.company = self.company
        if commit:
            position.save()
        return position


class CompanyPayGradeForm(forms.ModelForm):
    class Meta:
        model = CompanyPayGrade
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pay grade name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        pay_grade = super().save(commit=False)
        if self.company:
            pay_grade.company = self.company
        if commit:
            pay_grade.save()
        return pay_grade


class CompanyEmailSettingsForm(forms.ModelForm):
    smtp_use_tls = forms.TypedChoiceField(
        choices=((True, 'Yes'), (False, 'No')),
        coerce=lambda value: str(value).lower() in ('1', 'true', 'yes', 'on'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CompanyEmailSettings
        fields = [
            'smtp_host',
            'smtp_port',
            'smtp_username',
            'smtp_password',
            'smtp_sender_name',
            'smtp_use_tls',
        ]
        widgets = {
            'smtp_host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'smtp.example.com'}),
            'smtp_port': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'smtp_username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'noreply@example.com'}),
            'smtp_password': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '********'}, render_value=False),
            'smtp_sender_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company HR'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial.setdefault('smtp_use_tls', self.instance.smtp_use_tls)

    def clean_smtp_password(self):
        password = self.cleaned_data.get('smtp_password')
        if not password and self.instance and self.instance.pk:
            return self.instance.smtp_password
        return password


class CompanyBiometricSettingsForm(forms.ModelForm):
    class Meta:
        model = CompanyBiometricSettings
        fields = [
            'provider',
            'device_name',
            'device_serial',
            'endpoint',
            'device_ip',
            'api_key',
            'api_secret',
            'webhook_url',
            'location',
            'timezone',
            'sync_interval',
        ]
        widgets = {
            'provider': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ZKTeco, Suprema, etc.'}),
            'device_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lobby Scanner'}),
            'device_serial': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial number'}),
            'endpoint': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'http://device-ip/api'}),
            'device_ip': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '192.168.1.10'}),
            'api_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'API key'}),
            'api_secret': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'API secret'}),
            'webhook_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com/webhook'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Head Office'}),
            'timezone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Africa/Johannesburg'}),
            'sync_interval': forms.NumberInput(attrs={'class': 'form-control', 'min': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'sync_interval' in self.fields:
            self.fields['sync_interval'].initial = self.instance.sync_interval or 15


class CompanyNotificationSettingsForm(forms.ModelForm):
    """Form for notification preferences"""
    
    class Meta:
        model = CompanyNotificationSettings
        fields = [
            'email_leave_requests',
            'email_leave_approvals',
            'email_document_uploads',
            'email_performance_reminders',
            'email_training_assignments',
            'inapp_realtime',
            'inapp_sound_alerts',
            'inapp_desktop_notifications',
            'digest_time',
            'digest_frequency',
        ]
        widgets = {
            'digest_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'digest_frequency': forms.Select(attrs={'class': 'form-control'}),
        }


class CompanyAPIKeyForm(forms.ModelForm):
    """Form for creating API keys"""
    
    class Meta:
        model = CompanyAPIKey
        fields = ['name', 'webhook_url']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'API Key Name'}),
            'webhook_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://your-app.com/webhook'}),
        }
