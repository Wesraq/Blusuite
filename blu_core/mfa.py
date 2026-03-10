"""
Multi-Factor Authentication (MFA) for BluSuite
Supports TOTP (authenticator apps), Email OTP, and SMS OTP
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import pyotp
import qrcode
import io
import base64
import secrets
import string


User = get_user_model()


class MFAMethod(models.Model):
    """Store user's MFA configuration"""
    
    class MethodType(models.TextChoices):
        TOTP = 'TOTP', 'Authenticator App (TOTP)'
        EMAIL = 'EMAIL', 'Email OTP'
        SMS = 'SMS', 'SMS OTP'
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mfa_methods')
    method_type = models.CharField(max_length=10, choices=MethodType.choices)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # TOTP fields
    totp_secret = models.CharField(max_length=32, blank=True, help_text="Base32 encoded TOTP secret")
    
    # Email/SMS fields
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [('user', 'method_type')]
        ordering = ['-is_primary', 'method_type']
    
    def __str__(self):
        return f"{self.user.email} - {self.method_type}"
    
    def is_verified(self):
        return self.verified_at is not None


class BackupCode(models.Model):
    """Backup codes for account recovery when MFA device is lost"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='backup_codes')
    code = models.CharField(max_length=12, unique=True, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.email} - {'Used' if self.used_at else 'Unused'}"
    
    def is_used(self):
        return self.used_at is not None


class MFAChallenge(models.Model):
    """Temporary MFA challenges during login"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mfa_challenges')
    method_type = models.CharField(max_length=10, choices=MFAMethod.MethodType.choices)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.method_type} - {'Verified' if self.verified_at else 'Pending'}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def is_verified(self):
        return self.verified_at is not None


# ─────────────────────────────────────────────────────────────────────────────
# MFA Setup Functions
# ─────────────────────────────────────────────────────────────────────────────

def setup_totp(user):
    """Setup TOTP for user and return secret + QR code"""
    # Generate secret
    secret = pyotp.random_base32()
    
    # Create or update MFA method
    mfa_method, created = MFAMethod.objects.get_or_create(
        user=user,
        method_type=MFAMethod.MethodType.TOTP,
        defaults={'totp_secret': secret, 'is_primary': True}
    )
    
    if not created:
        mfa_method.totp_secret = secret
        mfa_method.save(update_fields=['totp_secret'])
    
    # Generate QR code
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.email,
        issuer_name='BluSuite'
    )
    
    # Create QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return {
        'secret': secret,
        'qr_code': qr_code_base64,
        'provisioning_uri': provisioning_uri,
        'mfa_method': mfa_method
    }


def verify_totp_setup(user, code):
    """Verify TOTP code during setup"""
    try:
        mfa_method = MFAMethod.objects.get(
            user=user,
            method_type=MFAMethod.MethodType.TOTP,
            verified_at__isnull=True
        )
        
        totp = pyotp.TOTP(mfa_method.totp_secret)
        if totp.verify(code, valid_window=1):
            mfa_method.verified_at = timezone.now()
            mfa_method.save(update_fields=['verified_at'])
            
            # Generate backup codes
            generate_backup_codes(user)
            
            return True, "TOTP verified successfully"
        else:
            return False, "Invalid code"
    except MFAMethod.DoesNotExist:
        return False, "TOTP not setup"


def setup_email_otp(user, email=None):
    """Setup email OTP for user"""
    if email is None:
        email = user.email
    
    mfa_method, created = MFAMethod.objects.get_or_create(
        user=user,
        method_type=MFAMethod.MethodType.EMAIL,
        defaults={'email': email, 'is_primary': not user.mfa_methods.exists()}
    )
    
    if not created:
        mfa_method.email = email
        mfa_method.save(update_fields=['email'])
    
    # Email OTP is auto-verified since we send to user's email
    mfa_method.verified_at = timezone.now()
    mfa_method.save(update_fields=['verified_at'])
    
    return mfa_method


def setup_sms_otp(user, phone_number):
    """Setup SMS OTP for user"""
    mfa_method, created = MFAMethod.objects.get_or_create(
        user=user,
        method_type=MFAMethod.MethodType.SMS,
        defaults={'phone_number': phone_number, 'is_primary': not user.mfa_methods.exists()}
    )
    
    if not created:
        mfa_method.phone_number = phone_number
        mfa_method.save(update_fields=['phone_number'])
    
    # SMS requires verification
    return mfa_method


def generate_backup_codes(user, count=10):
    """Generate backup codes for user"""
    # Delete existing unused codes
    BackupCode.objects.filter(user=user, used_at__isnull=True).delete()
    
    codes = []
    for _ in range(count):
        # Generate 12-character code (3 groups of 4)
        code = '-'.join([
            ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
            for _ in range(3)
        ])
        
        backup_code = BackupCode.objects.create(user=user, code=code)
        codes.append(code)
    
    return codes


# ─────────────────────────────────────────────────────────────────────────────
# MFA Verification Functions
# ─────────────────────────────────────────────────────────────────────────────

def create_mfa_challenge(user, method_type, ip_address=None):
    """Create MFA challenge for login"""
    # Get user's MFA method
    try:
        mfa_method = MFAMethod.objects.get(
            user=user,
            method_type=method_type,
            is_active=True,
            verified_at__isnull=False
        )
    except MFAMethod.DoesNotExist:
        return None, "MFA method not configured"
    
    # For TOTP, no challenge needed (user enters code from app)
    if method_type == MFAMethod.MethodType.TOTP:
        challenge = MFAChallenge.objects.create(
            user=user,
            method_type=method_type,
            code='',  # No code for TOTP
            expires_at=timezone.now() + timedelta(minutes=5),
            ip_address=ip_address
        )
        return challenge, None
    
    # For Email/SMS, generate and send code
    code = ''.join(secrets.choice(string.digits) for _ in range(6))
    
    challenge = MFAChallenge.objects.create(
        user=user,
        method_type=method_type,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=10),
        ip_address=ip_address
    )
    
    # Send code
    if method_type == MFAMethod.MethodType.EMAIL:
        _send_email_otp(user, mfa_method.email, code)
    elif method_type == MFAMethod.MethodType.SMS:
        _send_sms_otp(user, mfa_method.phone_number, code)
    
    return challenge, None


def verify_mfa_challenge(challenge, code):
    """Verify MFA challenge code"""
    if challenge.is_expired():
        return False, "Code expired"
    
    if challenge.is_verified():
        return False, "Code already used"
    
    challenge.attempts += 1
    challenge.save(update_fields=['attempts'])
    
    if challenge.attempts > 5:
        return False, "Too many attempts"
    
    # For TOTP, verify against user's secret
    if challenge.method_type == MFAMethod.MethodType.TOTP:
        try:
            mfa_method = MFAMethod.objects.get(
                user=challenge.user,
                method_type=MFAMethod.MethodType.TOTP
            )
            totp = pyotp.TOTP(mfa_method.totp_secret)
            if totp.verify(code, valid_window=1):
                challenge.verified_at = timezone.now()
                challenge.save(update_fields=['verified_at'])
                
                mfa_method.last_used_at = timezone.now()
                mfa_method.save(update_fields=['last_used_at'])
                
                return True, "Verified"
            else:
                return False, "Invalid code"
        except MFAMethod.DoesNotExist:
            return False, "TOTP not configured"
    
    # For Email/SMS, verify against challenge code
    if code == challenge.code:
        challenge.verified_at = timezone.now()
        challenge.save(update_fields=['verified_at'])
        
        try:
            mfa_method = MFAMethod.objects.get(
                user=challenge.user,
                method_type=challenge.method_type
            )
            mfa_method.last_used_at = timezone.now()
            mfa_method.save(update_fields=['last_used_at'])
        except MFAMethod.DoesNotExist:
            pass
        
        return True, "Verified"
    else:
        return False, "Invalid code"


def verify_backup_code(user, code):
    """Verify backup code for account recovery"""
    try:
        backup_code = BackupCode.objects.get(
            user=user,
            code=code.upper().replace(' ', ''),
            used_at__isnull=True
        )
        
        backup_code.used_at = timezone.now()
        backup_code.save(update_fields=['used_at'])
        
        return True, "Backup code verified"
    except BackupCode.DoesNotExist:
        return False, "Invalid or already used backup code"


def user_requires_mfa(user):
    """Check if user is required to use MFA based on company policy"""
    if not hasattr(user, 'company') or not user.company:
        return False
    
    company = user.company
    if not hasattr(company, 'security_settings') or not company.security_settings:
        return False
    
    twofa_config = company.security_settings.get('twofa', {})
    enforcement = twofa_config.get('enforcement', 'disabled')
    
    if enforcement == 'disabled':
        return False
    elif enforcement == 'required':
        return True
    elif enforcement == 'admins_only':
        return user.role in ['ADMINISTRATOR', 'EMPLOYER_ADMIN', 'SUPERADMIN']
    elif enforcement == 'optional':
        # Check if user has enabled MFA voluntarily
        return user.mfa_methods.filter(is_active=True, verified_at__isnull=False).exists()
    
    return False


def user_has_mfa_enabled(user):
    """Check if user has any MFA method enabled"""
    return user.mfa_methods.filter(is_active=True, verified_at__isnull=False).exists()


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def _send_email_otp(user, email, code):
    """Send OTP code via email"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = 'BluSuite - Your Login Code'
        message = f"""
Hello {user.get_full_name() or user.email},

Your BluSuite login code is: {code}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email and contact your administrator.

Best regards,
BluSuite Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send email OTP: {e}")


def _send_sms_otp(user, phone_number, code):
    """Send OTP code via SMS (requires SMS provider integration)"""
    # TODO: Integrate with SMS provider (Twilio, AWS SNS, etc.)
    # For now, just log it
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"SMS OTP for {user.email} to {phone_number}: {code}")
    
    # Example Twilio integration (commented out):
    # from twilio.rest import Client
    # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # message = client.messages.create(
    #     body=f"Your BluSuite login code is: {code}",
    #     from_=settings.TWILIO_PHONE_NUMBER,
    #     to=phone_number
    # )


def disable_mfa(user):
    """Disable all MFA methods for user"""
    user.mfa_methods.update(is_active=False)
    BackupCode.objects.filter(user=user, used_at__isnull=True).delete()


def get_user_mfa_status(user):
    """Get comprehensive MFA status for user"""
    methods = user.mfa_methods.filter(is_active=True, verified_at__isnull=False)
    backup_codes = user.backup_codes.filter(used_at__isnull=True).count()
    
    return {
        'enabled': methods.exists(),
        'required': user_requires_mfa(user),
        'methods': [
            {
                'type': m.method_type,
                'is_primary': m.is_primary,
                'last_used': m.last_used_at,
                'email': m.email if m.method_type == 'EMAIL' else None,
                'phone': m.phone_number if m.method_type == 'SMS' else None,
            }
            for m in methods
        ],
        'backup_codes_remaining': backup_codes,
    }
