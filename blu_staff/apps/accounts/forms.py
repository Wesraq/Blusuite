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
    SystemSettings,
)


class CompanyRegistrationForm(forms.ModelForm):
    """Form for company registration requests"""
    
    # Override subscription_plan to use plan names
    PLAN_CHOICES = [
        ('BASIC', 'Basic - Up to 25 employees'),
        ('STANDARD', 'Standard - Up to 100 employees'),
        ('PROFESSIONAL', 'Professional - Up to 500 employees'),
        ('ENTERPRISE', 'Enterprise - Unlimited employees'),
    ]
    
    # Country choices - African countries first, then others
    COUNTRY_CHOICES = [
        ('', 'Select Country'),
        # African Countries
        ('Algeria', 'Algeria'),
        ('Angola', 'Angola'),
        ('Botswana', 'Botswana'),
        ('Congo', 'Congo'),
        ('Egypt', 'Egypt'),
        ('Ethiopia', 'Ethiopia'),
        ('Ghana', 'Ghana'),
        ('Kenya', 'Kenya'),
        ('Malawi', 'Malawi'),
        ('Morocco', 'Morocco'),
        ('Mozambique', 'Mozambique'),
        ('Namibia', 'Namibia'),
        ('Nigeria', 'Nigeria'),
        ('South Africa', 'South Africa'),
        ('Tanzania', 'Tanzania'),
        ('Uganda', 'Uganda'),
        ('Zambia', 'Zambia'),
        ('Zimbabwe', 'Zimbabwe'),
        # Other Countries
        ('Afghanistan', 'Afghanistan'),
        ('Albania', 'Albania'),
        ('Argentina', 'Argentina'),
        ('Australia', 'Australia'),
        ('Austria', 'Austria'),
        ('Bangladesh', 'Bangladesh'),
        ('Belgium', 'Belgium'),
        ('Brazil', 'Brazil'),
        ('Canada', 'Canada'),
        ('Chile', 'Chile'),
        ('China', 'China'),
        ('Colombia', 'Colombia'),
        ('Denmark', 'Denmark'),
        ('Finland', 'Finland'),
        ('France', 'France'),
        ('Germany', 'Germany'),
        ('Greece', 'Greece'),
        ('India', 'India'),
        ('Indonesia', 'Indonesia'),
        ('Iran', 'Iran'),
        ('Iraq', 'Iraq'),
        ('Ireland', 'Ireland'),
        ('Israel', 'Israel'),
        ('Italy', 'Italy'),
        ('Japan', 'Japan'),
        ('Malaysia', 'Malaysia'),
        ('Mexico', 'Mexico'),
        ('Netherlands', 'Netherlands'),
        ('New Zealand', 'New Zealand'),
        ('Norway', 'Norway'),
        ('Pakistan', 'Pakistan'),
        ('Peru', 'Peru'),
        ('Philippines', 'Philippines'),
        ('Poland', 'Poland'),
        ('Portugal', 'Portugal'),
        ('Russia', 'Russia'),
        ('Saudi Arabia', 'Saudi Arabia'),
        ('Singapore', 'Singapore'),
        ('South Korea', 'South Korea'),
        ('Spain', 'Spain'),
        ('Sweden', 'Sweden'),
        ('Switzerland', 'Switzerland'),
        ('Thailand', 'Thailand'),
        ('Turkey', 'Turkey'),
        ('United Arab Emirates', 'United Arab Emirates'),
        ('United Kingdom', 'United Kingdom'),
        ('United States', 'United States'),
        ('Vietnam', 'Vietnam'),
    ]
    
    # Cities by country - focused on major African countries and others
    CITY_CHOICES = {
        'Zambia': [
            ('', 'Select City'),
            ('Lusaka', 'Lusaka'),
            ('Kitwe', 'Kitwe'),
            ('Ndola', 'Ndola'),
            ('Kabwe', 'Kabwe'),
            ("Solwezi", "Solwezi"),
            ("Mongu", "Mongu"),
            ('Chingola', 'Chingola'),
            ('Mufulira', 'Mufulira'),
            ('Livingstone', 'Livingstone'),
            ('Luanshya', 'Luanshya'),
            ('Kasama', 'Kasama'),
            ('Chipata', 'Chipata'),
        ],
        'South Africa': [
            ('', 'Select City'),
            ('Johannesburg', 'Johannesburg'),
            ('Cape Town', 'Cape Town'),
            ('Durban', 'Durban'),
            ('Pretoria', 'Pretoria'),
            ('Port Elizabeth', 'Port Elizabeth'),
            ('Bloemfontein', 'Bloemfontein'),
        ],
        'Kenya': [
            ('', 'Select City'),
            ('Nairobi', 'Nairobi'),
            ('Mombasa', 'Mombasa'),
            ('Kisumu', 'Kisumu'),
            ('Nakuru', 'Nakuru'),
            ('Eldoret', 'Eldoret'),
        ],
        'Malawi': [
            ('', 'Select City'),
            ('Lilongwe', 'Lilongwe'),
            ('Blantyre', 'Blantyre'),
            ('Mzuzu', 'Mzuzu'),
            ('Zomba', 'Zomba'),
            ('Mangochi', 'Mangochi'),
            ('Karonga', 'Karonga'),
        ],
        'Nigeria': [
            ('', 'Select City'),
            ('Lagos', 'Lagos'),
            ('Abuja', 'Abuja'),
            ('Kano', 'Kano'),
            ('Ibadan', 'Ibadan'),
            ('Port Harcourt', 'Port Harcourt'),
        ],
        'Ghana': [
            ('', 'Select City'),
            ('Accra', 'Accra'),
            ('Kumasi', 'Kumasi'),
            ('Tamale', 'Tamale'),
            ('Sekondi-Takoradi', 'Sekondi-Takoradi'),
        ],
        'Zimbabwe': [
            ('', 'Select City'),
            ('Harare', 'Harare'),
            ('Bulawayo', 'Bulawayo'),
            ('Mutare', 'Mutare'),
            ('Gweru', 'Gweru'),
        ],
        'Tanzania': [
            ('', 'Select City'),
            ('Dar es Salaam', 'Dar es Salaam'),
            ('Dodoma', 'Dodoma'),
            ('Mwanza', 'Mwanza'),
            ('Arusha', 'Arusha'),
        ],
        'Uganda': [
            ('', 'Select City'),
            ('Kampala', 'Kampala'),
            ('Entebbe', 'Entebbe'),
            ('Gulu', 'Gulu'),
            ('Mbarara', 'Mbarara'),
        ],
        'United States': [
            ('', 'Select City'),
            ('New York', 'New York'),
            ('Los Angeles', 'Los Angeles'),
            ('Chicago', 'Chicago'),
            ('Houston', 'Houston'),
            ('Phoenix', 'Phoenix'),
            ('Philadelphia', 'Philadelphia'),
            ('San Antonio', 'San Antonio'),
            ('San Diego', 'San Diego'),
            ('Dallas', 'Dallas'),
            ('San Jose', 'San Jose'),
        ],
        'United Kingdom': [
            ('', 'Select City'),
            ('London', 'London'),
            ('Birmingham', 'Birmingham'),
            ('Manchester', 'Manchester'),
            ('Glasgow', 'Glasgow'),
            ('Liverpool', 'Liverpool'),
            ('Edinburgh', 'Edinburgh'),
        ],
    }
    
    subscription_plan = forms.ChoiceField(
        choices=PLAN_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='BASIC'
    )
    
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_country',
            'onchange': 'updateCityOptions()'
        }),
        required=False
    )
    
    city = forms.ChoiceField(
        choices=[('', 'Select City')],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_city'
        }),
        required=False
    )

    class Meta:
        model = CompanyRegistrationRequest
        fields = [
            'company_name', 'company_address', 'company_phone', 'company_email',
            'company_website', 'country', 'city', 'contact_first_name', 'contact_last_name',
            'contact_email', 'contact_phone', 'contact_position', 'subscription_plan',
            'billing_preference', 'number_of_employees', 'business_type', 'company_size'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Full company address'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company phone number'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'company@domain.com'}),
            'company_website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://company.com'}),
            'contact_first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'contact_last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@company.com'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact phone number'}),
            'contact_position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Position/Title'}),
            'billing_preference': forms.Select(attrs={'class': 'form-control'}),
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


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            'name',
            'tax_id',
            'industry',
            'company_size',
            'phone',
            'alternative_phone',
            'email',
            'website',
            'address',
            'city',
            'province',
            'country',
            'postal_code',
            'logo',
            'company_stamp',
            'signature',
            'tax_certificate',
            'business_registration',
            'trade_license',
            'napsa_certificate',
            'nhima_certificate',
            'workers_compensation',
            'primary_color',
            'secondary_color',
            'text_color',
            'background_color',
            'card_header_color',
            'button_color',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Legal company name'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'TPIN / Registration number'}),
            'industry': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Technology, Healthcare'}),
            'company_size': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+260...'}),
            'alternative_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+260 XXX XXX XXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'admin@example.com'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://company.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'province': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Lusaka Province'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10101'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'text_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'background_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'card_header_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'button_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        file_fields = (
            'logo', 'company_stamp', 'signature',
            'tax_certificate', 'business_registration', 'trade_license',
            'napsa_certificate', 'nhima_certificate', 'workers_compensation',
        )
        for field_name in file_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False


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
            'smtp_use_ssl',
            'from_email',
            'from_name',
            'enable_email_notifications',
            'enable_performance_emails',
            'enable_leave_emails',
            'enable_attendance_emails',
            'enable_payroll_emails',
            'enable_training_emails',
            'enable_document_emails',
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


class SystemSettingsForm(forms.ModelForm):
    """Form for editing global system settings (System Owner only)."""

    class Meta:
        model = SystemSettings
        fields = [
            'allow_public_company_registration',
            'default_subscription_plan',
            'registration_admin_email',
            'maintenance_mode',
            'maintenance_message',
            'enable_billing_module',
            'enable_support_module',
            'enable_analytics_module',
        ]
        widgets = {
            'registration_admin_email': forms.EmailInput(
                attrs={'class': 'form-control', 'placeholder': 'admin@example.com'}
            ),
            'maintenance_message': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional maintenance message shown to users.'}
            ),
        }

class CompanyRegistrationRequestForm(forms.ModelForm):
    """Form for company registration requests"""
    class Meta:
        model = CompanyRegistrationRequest
        fields = [
            'company_name', 'company_address', 'company_phone', 'company_email',
            'company_website', 'country', 'city', 'contact_first_name', 'contact_last_name',
            'contact_email', 'contact_phone', 'contact_position', 'subscription_plan',
            'billing_preference', 'number_of_employees', 'business_type', 'company_size'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_address': forms.TextInput(attrs={'class': 'form-control'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'company_website': forms.URLInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-control', 'id': 'id_country', 'onchange': 'updateCityOptions()'}),
            'city': forms.Select(attrs={'class': 'form-control', 'id': 'id_city'}),
            'contact_first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_position': forms.TextInput(attrs={'class': 'form-control'}),
            'subscription_plan': forms.Select(attrs={'class': 'form-control'}),
            'billing_preference': forms.Select(attrs={'class': 'form-control'}),
            'number_of_employees': forms.NumberInput(attrs={'class': 'form-control'}),
            'business_type': forms.Select(attrs={'class': 'form-control'}),
            'company_size': forms.Select(attrs={'class': 'form-control'}),
        }

    COUNTRY_CHOICES = [
        ('', 'Select Country'),
        ('Algeria', 'Algeria'), ('Angola', 'Angola'), ('Botswana', 'Botswana'),
        ('Cameroon', 'Cameroon'), ('Congo', 'Congo'), ('Egypt', 'Egypt'),
        ('Ethiopia', 'Ethiopia'), ('Ghana', 'Ghana'), ('Kenya', 'Kenya'),
        ('Malawi', 'Malawi'), ('Morocco', 'Morocco'), ('Mozambique', 'Mozambique'),
        ('Namibia', 'Namibia'), ('Nigeria', 'Nigeria'), ('Rwanda', 'Rwanda'),
        ('Senegal', 'Senegal'), ('South Africa', 'South Africa'),
        ('Tanzania', 'Tanzania'), ('Uganda', 'Uganda'), ('Zambia', 'Zambia'),
        ('Zimbabwe', 'Zimbabwe'),
    ]

    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_country',
            'onchange': 'updateCityOptions()'
        }),
        required=False
    )

    city = forms.ChoiceField(
        choices=[('', 'Select City')],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_city'
        }),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate city choices based on selected country
        from blu_staff.apps.accounts.forms import CompanyRegistrationForm
        city_choices_map = getattr(CompanyRegistrationForm, 'CITY_CHOICES', {})
        if self.data.get('country') and self.data['country'] in city_choices_map:
            self.fields['city'].choices = city_choices_map[self.data['country']]
        else:
            self.fields['city'].choices = [('', 'Select City')]
