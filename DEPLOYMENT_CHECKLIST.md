# BLU Suite EMS - Production Deployment Checklist

## Pre-Deployment Security Checklist

### 1. Environment Configuration ✅

- [ ] Create `.env` file from `.env.example`
- [ ] Generate new `SECRET_KEY` using:
  ```bash
  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
  ```
- [ ] Set `DEBUG=False` in production environment
- [ ] Configure `ALLOWED_HOSTS` with your production domain(s)
- [ ] Set `CSRF_TRUSTED_ORIGINS` with your production URLs
- [ ] Set `CORS_ALLOWED_ORIGINS` with approved frontend domains
- [ ] Configure email credentials (Gmail/SMTP)
- [ ] Configure Stripe API keys (production keys, not test keys)
- [ ] Set database credentials securely

### 2. Security Settings Verification ✅

- [ ] Verify `SECRET_KEY` is not hardcoded
- [ ] Verify `DEBUG = False` in production
- [ ] Verify `SECURE_SSL_REDIRECT = True`
- [ ] Verify `SESSION_COOKIE_SECURE = True`
- [ ] Verify `CSRF_COOKIE_SECURE = True`
- [ ] Verify `SECURE_HSTS_SECONDS` is set (recommended: 31536000)
- [ ] Verify `X_FRAME_OPTIONS = 'DENY'`
- [ ] Verify `SECURE_CONTENT_TYPE_NOSNIFF = True`
- [ ] Verify `SECURE_BROWSER_XSS_FILTER = True`

### 3. Dependencies Installation

```bash
# Install all required packages
pip install -r requirements.txt

# Verify django-axes is installed
pip show django-axes

# Verify all security packages are present
pip list | grep -E "django-axes|django-cors-headers"
```

### 4. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create axes tables
python manage.py migrate axes

# Create superuser (if needed)
python manage.py createsuperuser
```

### 5. Static Files

```bash
# Collect static files
python manage.py collectstatic --noinput

# Verify static files are served correctly
```

### 6. Logging Configuration

- [ ] Create `logs` directory:
  ```bash
  mkdir logs
  ```
- [ ] Set appropriate permissions:
  ```bash
  chmod 755 logs
  ```
- [ ] Verify log files can be written:
  - `logs/security.log`
  - `logs/axes.log`
  - `logs/django.log`

### 7. Security Audit

```bash
# Run Django's deployment check
python manage.py check --deploy

# Expected output: No critical issues
```

### 8. Test Security Features

#### Test 1: Brute Force Protection
1. Attempt to login with wrong password 5 times
2. Verify account is locked for 1 hour
3. Check `logs/axes.log` for lockout events

#### Test 2: Password Complexity
1. Try to create user with weak password (e.g., "password123")
2. Should fail with validation errors
3. Create user with strong password (12+ chars, mixed case, numbers, special)
4. Should succeed

#### Test 3: Session Security
1. Login to application
2. Check browser cookies - verify `Secure`, `HttpOnly`, `SameSite=Strict` flags
3. Close browser and reopen after 1 hour
4. Should be logged out (session expired)

#### Test 4: CSRF Protection
1. Attempt POST request without CSRF token
2. Should receive 403 Forbidden error

#### Test 5: File Upload Limits
1. Try to upload file > 10MB
2. Should be rejected
3. Try to upload disallowed file type (e.g., .exe)
4. Should be rejected

### 9. SSL/HTTPS Configuration

- [ ] Obtain SSL certificate (Let's Encrypt, Cloudflare, etc.)
- [ ] Configure web server (Nginx/Apache) for HTTPS
- [ ] Verify `SECURE_SSL_REDIRECT = True` redirects HTTP to HTTPS
- [ ] Test HTTPS connection
- [ ] Verify HSTS header is present

### 10. Firewall & Network Security

- [ ] Configure firewall to allow only ports 80, 443
- [ ] Block direct access to port 8000 (Django dev server)
- [ ] Configure database to accept connections only from app server
- [ ] Set up fail2ban or similar intrusion prevention

### 11. Backup Strategy

- [ ] Set up automated database backups
- [ ] Set up media files backup
- [ ] Test backup restoration process
- [ ] Document backup retention policy

### 12. Monitoring & Alerts

- [ ] Set up error monitoring (Sentry, Rollbar, etc.)
- [ ] Configure email alerts for critical errors
- [ ] Set up uptime monitoring
- [ ] Configure log rotation for `logs/` directory

### 13. Performance Optimization

- [ ] Enable database query optimization
- [ ] Configure caching (Redis/Memcached)
- [ ] Enable gzip compression
- [ ] Optimize static file serving (CDN)

### 14. Documentation

- [ ] Document all environment variables
- [ ] Document deployment process
- [ ] Document rollback procedure
- [ ] Document incident response plan

---

## Post-Deployment Verification

### Immediate Checks (within 1 hour)

1. **Application Health**
   - [ ] Homepage loads correctly
   - [ ] Login works for all user types (SuperAdmin, Admin, Employee)
   - [ ] No 500 errors in logs

2. **Security Headers**
   ```bash
   curl -I https://yourdomain.com
   ```
   Verify headers:
   - `Strict-Transport-Security`
   - `X-Frame-Options: DENY`
   - `X-Content-Type-Options: nosniff`
   - `X-XSS-Protection: 1; mode=block`

3. **SSL/TLS**
   - [ ] Test SSL configuration: https://www.ssllabs.com/ssltest/
   - [ ] Aim for A+ rating

4. **Database Connectivity**
   - [ ] Verify database connections are working
   - [ ] Check for connection pool exhaustion

### Daily Checks (first week)

1. **Log Review**
   ```bash
   tail -f logs/security.log
   tail -f logs/axes.log
   ```
   - [ ] Review for suspicious activity
   - [ ] Check for failed login attempts
   - [ ] Monitor for unusual patterns

2. **Performance**
   - [ ] Monitor response times
   - [ ] Check database query performance
   - [ ] Review memory usage

3. **Error Rates**
   - [ ] Check error logs for 500 errors
   - [ ] Review 404 patterns
   - [ ] Monitor exception rates

### Weekly Checks

1. **Security Updates**
   - [ ] Check for Django security releases
   - [ ] Update dependencies with security patches
   - [ ] Review CVE databases for affected packages

2. **Backup Verification**
   - [ ] Verify backups are running
   - [ ] Test backup restoration
   - [ ] Check backup storage capacity

3. **Access Review**
   - [ ] Review user accounts
   - [ ] Disable inactive accounts
   - [ ] Audit admin/superadmin access

---

## Emergency Rollback Procedure

If critical issues are discovered:

1. **Immediate Actions**
   ```bash
   # Revert to previous deployment
   git checkout <previous-commit-hash>
   
   # Restart application
   sudo systemctl restart gunicorn
   sudo systemctl restart nginx
   ```

2. **Database Rollback** (if needed)
   ```bash
   # Restore from backup
   python manage.py migrate <app_name> <migration_number>
   ```

3. **Communication**
   - Notify stakeholders
   - Document the issue
   - Create incident report

---

## Security Incident Response

### If Breach Detected

1. **Isolate**
   - Take affected systems offline
   - Block suspicious IP addresses
   - Disable compromised accounts

2. **Assess**
   - Review logs for entry point
   - Identify scope of breach
   - Document all findings

3. **Contain**
   - Patch vulnerabilities
   - Reset all passwords
   - Rotate API keys and secrets

4. **Recover**
   - Restore from clean backup
   - Verify system integrity
   - Monitor for re-infection

5. **Report**
   - Notify affected users
   - File incident report
   - Implement preventive measures

---

## Compliance & Audit

### Data Protection (GDPR/CCPA)

- [ ] Implement data retention policies
- [ ] Provide user data export functionality
- [ ] Implement right to be forgotten
- [ ] Document data processing activities
- [ ] Obtain necessary consents

### Audit Trail

- [ ] Enable comprehensive logging
- [ ] Log all authentication events
- [ ] Log all data modifications
- [ ] Implement log integrity checks
- [ ] Set up log archival (7+ years)

---

## Performance Benchmarks

### Expected Metrics

- **Page Load Time**: < 2 seconds
- **API Response Time**: < 500ms
- **Database Query Time**: < 100ms
- **Uptime**: 99.9%
- **Error Rate**: < 0.1%

### Load Testing

```bash
# Use tools like Apache Bench, Locust, or JMeter
ab -n 1000 -c 10 https://yourdomain.com/
```

---

## Support Contacts

- **Development Team**: dev@blusuite.com
- **Security Team**: security@blusuite.com
- **Infrastructure**: ops@blusuite.com
- **Emergency Hotline**: +1-XXX-XXX-XXXX

---

## Version History

| Version | Date | Changes | Deployed By |
|---------|------|---------|-------------|
| 1.0.0 | 2026-03-03 | Initial security hardening | DevOps Team |

---

## Sign-Off

- [ ] Development Lead: _________________ Date: _______
- [ ] Security Officer: _________________ Date: _______
- [ ] Operations Lead: _________________ Date: _______
- [ ] Product Owner: ___________________ Date: _______

---

**Last Updated**: March 3, 2026  
**Next Review**: April 3, 2026
