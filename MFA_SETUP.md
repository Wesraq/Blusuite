# BluSuite Multi-Factor Authentication (MFA) Setup Guide

## Overview
Complete MFA implementation supporting TOTP (authenticator apps), Email OTP, and SMS OTP with backup codes for account recovery.

---

## Features Implemented

### 1. MFA Models

**File:** `blu_core/mfa.py`

**Models:**
- `MFAMethod` — User's configured MFA methods (TOTP, Email, SMS)
- `BackupCode` — Recovery codes for lost devices
- `MFAChallenge` — Temporary login challenges

**Functions:**
- `setup_totp(user)` — Generate TOTP secret and QR code
- `setup_email_otp(user, email)` — Configure email OTP
- `setup_sms_otp(user, phone)` — Configure SMS OTP
- `generate_backup_codes(user)` — Create 10 recovery codes
- `create_mfa_challenge(user, method_type)` — Start login verification
- `verify_mfa_challenge(challenge, code)` — Verify OTP code
- `verify_backup_code(user, code)` — Use recovery code
- `user_requires_mfa(user)` — Check company policy
- `user_has_mfa_enabled(user)` — Check user status

### 2. Company-Level MFA Policy

**Enforcement Levels:**
- `disabled` — MFA not available
- `optional` — Users can enable voluntarily
- `admins_only` — Required for ADMINISTRATOR, EMPLOYER_ADMIN, SUPERADMIN
- `required` — Required for all users

**Methods Supported:**
- `email` — 6-digit code sent via email
- `sms` — 6-digit code sent via SMS (requires SMS provider)
- `authenticator` — TOTP via Google Authenticator, Authy, etc.

### 3. Security Features

- **TOTP Secrets:** Base32 encoded, stored encrypted
- **Backup Codes:** 10 single-use recovery codes
- **Challenge Expiry:** 10 minutes for Email/SMS, 5 minutes for TOTP
- **Rate Limiting:** Max 5 attempts per challenge
- **IP Tracking:** Log IP address for each MFA attempt
- **Cooldown:** Prevent brute force attacks

---

## Deployment Steps

### Step 1: Install Dependencies

```bash
cd /opt/blusuite
source venv/bin/activate
pip install pyotp qrcode[pil]
```

### Step 2: Run Migration

```bash
python manage.py migrate blu_core --settings=ems_project.settings_production
```

**Creates:**
- `blu_core_mfamethod` table
- `blu_core_backupcode` table
- `blu_core_mfachallenge` table

### Step 3: Configure Company MFA Policy

**Via Settings UI:**
1. Login as company administrator
2. Go to Settings → Security
3. Scroll to "Two-Factor Authentication (2FA)"
4. Select enforcement level and method
5. Save settings

**Via Django Shell:**
```python
from blu_staff.apps.accounts.models import Company

company = Company.objects.get(name="Example Corp")
company.security_settings = {
    'twofa': {
        'enforcement': 'admins_only',  # or 'required', 'optional', 'disabled'
        'method': 'authenticator'      # or 'email', 'sms'
    }
}
company.save()
```

### Step 4: Test MFA Setup

**Setup TOTP for User:**
```python
from django.contrib.auth import get_user_model
from blu_core.mfa import setup_totp, verify_totp_setup, generate_backup_codes

User = get_user_model()
user = User.objects.get(email='admin@example.com')

# Setup TOTP
result = setup_totp(user)
print(f"Secret: {result['secret']}")
print(f"QR Code (base64): {result['qr_code'][:50]}...")

# User scans QR code with authenticator app and enters code
code = input("Enter code from authenticator app: ")
success, message = verify_totp_setup(user, code)
print(f"Verification: {message}")

# Generate backup codes
if success:
    codes = generate_backup_codes(user)
    print(f"Backup codes: {codes}")
```

---

## User Workflows

### Setup TOTP (Authenticator App)

**User Flow:**
1. User goes to Account Settings → Security
2. Clicks "Enable Two-Factor Authentication"
3. Selects "Authenticator App"
4. Scans QR code with Google Authenticator/Authy
5. Enters 6-digit code to verify
6. Downloads backup codes
7. MFA enabled

**Backend:**
```python
from blu_core.mfa import setup_totp, verify_totp_setup

# Step 1: Generate secret and QR code
result = setup_totp(user)
# Display QR code to user: result['qr_code']

# Step 2: User enters code from app
success, message = verify_totp_setup(user, user_entered_code)

# Step 3: Generate backup codes
if success:
    backup_codes = generate_backup_codes(user)
    # Display codes to user for download
```

### Setup Email OTP

**User Flow:**
1. User goes to Account Settings → Security
2. Clicks "Enable Two-Factor Authentication"
3. Selects "Email OTP"
4. Confirms email address
5. MFA enabled (no verification needed)

**Backend:**
```python
from blu_core.mfa import setup_email_otp

mfa_method = setup_email_otp(user, email=user.email)
# Auto-verified since we send to user's registered email
```

### Login with MFA

**User Flow:**
1. User enters email and password
2. If MFA required, redirected to MFA verification page
3. User enters 6-digit code from authenticator app or email
4. If correct, logged in
5. If incorrect, shows error (max 5 attempts)

**Backend:**
```python
from blu_core.mfa import create_mfa_challenge, verify_mfa_challenge, user_requires_mfa

# After successful password authentication
if user_requires_mfa(user):
    # Create MFA challenge
    challenge, error = create_mfa_challenge(
        user,
        method_type='TOTP',  # or 'EMAIL', 'SMS'
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Store challenge ID in session
    request.session['mfa_challenge_id'] = challenge.id
    
    # Redirect to MFA verification page
    return redirect('mfa_verify')

# On MFA verification page
challenge = MFAChallenge.objects.get(id=request.session['mfa_challenge_id'])
success, message = verify_mfa_challenge(challenge, user_entered_code)

if success:
    # Complete login
    login(request, user)
    return redirect('dashboard')
else:
    # Show error
    messages.error(request, message)
```

### Use Backup Code

**User Flow:**
1. User lost authenticator device
2. On MFA verification page, clicks "Use backup code"
3. Enters one of the 10 backup codes
4. If valid, logged in
5. Backup code marked as used

**Backend:**
```python
from blu_core.mfa import verify_backup_code

success, message = verify_backup_code(user, user_entered_code)

if success:
    login(request, user)
    messages.warning(request, "You used a backup code. Please setup MFA again.")
    return redirect('dashboard')
```

---

## Admin Management

### View User MFA Status

**Django Admin:**
1. Go to `/admin/blu_core/mfamethod/`
2. Filter by user, method type, verification status
3. See last used timestamp

**Programmatically:**
```python
from blu_core.mfa import get_user_mfa_status

status = get_user_mfa_status(user)
print(status)
# {
#     'enabled': True,
#     'required': True,
#     'methods': [
#         {
#             'type': 'TOTP',
#             'is_primary': True,
#             'last_used': datetime(...),
#             'email': None,
#             'phone': None
#         }
#     ],
#     'backup_codes_remaining': 8
# }
```

### Disable MFA for User

**Emergency Access:**
```python
from blu_core.mfa import disable_mfa

# Disable all MFA methods for user
disable_mfa(user)

# User can now login without MFA
# Recommend they setup MFA again immediately
```

### View MFA Challenges

**Django Admin:**
1. Go to `/admin/blu_core/mfachallenge/`
2. See all login attempts with MFA
3. Filter by user, method, verification status
4. Check IP addresses for suspicious activity

---

## SMS Integration (Optional)

### Twilio Setup

**Install Twilio:**
```bash
pip install twilio
```

**Configure in `.env`:**
```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

**Update `blu_core/mfa.py`:**
```python
def _send_sms_otp(user, phone_number, code):
    """Send OTP code via SMS using Twilio"""
    from twilio.rest import Client
    from django.conf import settings
    
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    message = client.messages.create(
        body=f"Your BluSuite login code is: {code}. Valid for 10 minutes.",
        from_=settings.TWILIO_PHONE_NUMBER,
        to=phone_number
    )
    
    return message.sid
```

### AWS SNS Setup

**Install boto3:**
```bash
pip install boto3
```

**Configure in `.env`:**
```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
```

**Update `blu_core/mfa.py`:**
```python
def _send_sms_otp(user, phone_number, code):
    """Send OTP code via SMS using AWS SNS"""
    import boto3
    from django.conf import settings
    
    sns = boto3.client(
        'sns',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )
    
    sns.publish(
        PhoneNumber=phone_number,
        Message=f"Your BluSuite login code is: {code}. Valid for 10 minutes."
    )
```

---

## Security Best Practices

### 1. Enforce MFA for Admins

**Minimum Requirement:**
```python
company.security_settings = {
    'twofa': {
        'enforcement': 'admins_only',
        'method': 'authenticator'
    }
}
```

### 2. Rotate Backup Codes

**After Each Use:**
- User uses backup code → prompt to generate new codes
- Implement in login flow after backup code verification

### 3. Monitor MFA Challenges

**Check for Suspicious Activity:**
```python
from blu_core.models import MFAChallenge
from datetime import timedelta
from django.utils import timezone

# Failed attempts in last hour
recent_failures = MFAChallenge.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=1),
    verified_at__isnull=True,
    attempts__gte=5
).select_related('user')

for challenge in recent_failures:
    print(f"Suspicious: {challenge.user.email} from {challenge.ip_address}")
```

### 4. Audit MFA Events

**Log to AuditLog:**
```python
from blu_core.audit import log_action

# When MFA is enabled
log_action(
    user=user,
    action='CREATE',
    model_name='MFAMethod',
    object_repr=f'TOTP for {user.email}',
    company=user.company
)

# When MFA is disabled
log_action(
    user=user,
    action='DELETE',
    model_name='MFAMethod',
    object_repr=f'All MFA methods for {user.email}',
    company=user.company
)
```

---

## Troubleshooting

### TOTP Codes Not Working

**Check Time Sync:**
- TOTP relies on synchronized time
- Server and user device must have accurate time
- Use NTP on server: `sudo timedatectl set-ntp true`

**Verify Secret:**
```python
from blu_core.models import MFAMethod
import pyotp

mfa = MFAMethod.objects.get(user=user, method_type='TOTP')
totp = pyotp.TOTP(mfa.totp_secret)
print(f"Current valid code: {totp.now()}")
```

### Email OTP Not Received

**Check Email Configuration:**
```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
```

**Check Logs:**
```bash
tail -f /var/log/blusuite/django.log | grep "email"
```

### User Locked Out

**Disable MFA Temporarily:**
```python
from django.contrib.auth import get_user_model
from blu_core.mfa import disable_mfa

User = get_user_model()
user = User.objects.get(email='locked_user@example.com')
disable_mfa(user)

# Notify user to setup MFA again after login
```

### Backup Codes Not Working

**Check Code Format:**
- Codes are case-insensitive
- Spaces and dashes are ignored
- Format: `XXXX-XXXX-XXXX`

**Verify Code Exists:**
```python
from blu_core.models import BackupCode

code = 'ABCD-1234-EFGH'
BackupCode.objects.filter(
    user=user,
    code=code.upper().replace(' ', '').replace('-', ''),
    used_at__isnull=True
).exists()
```

---

## Migration from Non-MFA System

### Gradual Rollout

**Phase 1: Optional (Week 1-2)**
```python
company.security_settings['twofa']['enforcement'] = 'optional'
# Educate users, provide setup guides
```

**Phase 2: Admins Only (Week 3-4)**
```python
company.security_settings['twofa']['enforcement'] = 'admins_only'
# Force admins to setup MFA
```

**Phase 3: All Users (Week 5+)**
```python
company.security_settings['twofa']['enforcement'] = 'required'
# All users must setup MFA on next login
```

### Bulk MFA Setup

**Generate Setup Links:**
```python
from django.contrib.auth import get_user_model
from blu_core.mfa import setup_email_otp

User = get_user_model()
users = User.objects.filter(company=company, role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN'])

for user in users:
    # Auto-setup email OTP
    setup_email_otp(user)
    
    # Send notification
    # notify_user_mfa_enabled(user)
```

---

## Compliance & Audit

### GDPR Considerations

- **Data Stored:** TOTP secrets, phone numbers, email addresses
- **Retention:** Delete MFA data when user account deleted
- **Export:** Include MFA status in user data export

### SOC 2 Requirements

- ✅ MFA for privileged accounts (admins)
- ✅ Audit trail of MFA events
- ✅ Backup codes for account recovery
- ✅ Rate limiting on MFA attempts
- ✅ IP address logging

### PCI DSS Compliance

- ✅ Multi-factor authentication for admin access
- ✅ Unique authentication credentials
- ✅ Lockout after failed attempts
- ✅ Session timeout enforcement

---

## Future Enhancements

1. **WebAuthn/FIDO2 Support:**
   - Hardware security keys (YubiKey)
   - Biometric authentication (Touch ID, Face ID)

2. **Push Notifications:**
   - Approve login from mobile app
   - No code entry required

3. **Risk-Based Authentication:**
   - Skip MFA for trusted devices
   - Require MFA for new locations/devices

4. **Remember Device:**
   - Trust device for 30 days
   - Reduce MFA friction

5. **MFA Analytics:**
   - Dashboard showing MFA adoption rate
   - Failed attempt trends
   - Device usage statistics

---

**Document Version:** 1.0  
**Last Updated:** March 10, 2026  
**Next Review:** June 10, 2026
