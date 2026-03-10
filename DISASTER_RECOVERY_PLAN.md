# BluSuite Disaster Recovery Plan

## Overview
This document outlines procedures for backing up, verifying, and restoring BluSuite data in case of system failure, data corruption, or security incidents.

---

## Backup Strategy

### Automated Daily Backups

**Schedule:** Daily at 3:00 AM UTC  
**Retention:** 30 days  
**Location:** `/opt/blusuite/backups/`  
**Format:** Compressed PostgreSQL dump (`.sql.gz`)

**Cron Configuration:**
```bash
# Edit crontab
crontab -e

# Add this line
0 3 * * * /opt/blusuite/scripts/cron_backup.sh
```

### Backup Components

1. **Database Backup** (Automated)
   - Full PostgreSQL dump
   - Compressed with gzip
   - Integrity verification
   - 30-day retention

2. **Media Files** (Manual/Periodic)
   - Employee documents
   - Company logos
   - Uploaded files
   - Location: `/opt/blusuite/media/`

3. **Configuration Files** (Version Controlled)
   - `settings_production.py`
   - `.env` files
   - Nginx configuration
   - Gunicorn configuration

---

## Backup Scripts

### 1. Create Backup
```bash
/opt/blusuite/scripts/backup_database.sh
```

**Features:**
- Compressed PostgreSQL dump
- Disk space validation
- Integrity verification
- Automatic cleanup of old backups
- Optional remote backup upload
- Detailed logging

**Output:**
- Backup file: `/opt/blusuite/backups/blusuite_YYYYMMDD_HHMMSS.sql.gz`
- Log file: `/opt/blusuite/backups/backup.log`

### 2. Verify Backup
```bash
/opt/blusuite/scripts/verify_backup.sh
```

**Tests:**
- File integrity (gzip test)
- Restoration to temporary database
- Table count verification
- Critical tables existence check

**Run Weekly:** Automated on Sundays via cron

### 3. Restore Backup
```bash
/opt/blusuite/scripts/restore_database.sh [backup_file]
```

**Safety Features:**
- Lists available backups
- Creates safety backup before restore
- Stops application during restore
- Verifies restored database
- Restarts application

**Interactive Mode:**
```bash
/opt/blusuite/scripts/restore_database.sh
# Will prompt to select from available backups
```

**Direct Mode:**
```bash
/opt/blusuite/scripts/restore_database.sh /opt/blusuite/backups/blusuite_20260310_030000.sql.gz
```

---

## Recovery Procedures

### Scenario 1: Data Corruption

**Symptoms:**
- Application errors
- Missing or corrupted records
- Database integrity errors

**Recovery Steps:**

1. **Identify Issue**
   ```bash
   # Check application logs
   tail -f /var/log/blusuite/gunicorn_error.log
   
   # Check database
   psql -U blusuite_user blusuite_db
   ```

2. **Stop Application**
   ```bash
   systemctl stop blusuite
   ```

3. **Restore from Latest Backup**
   ```bash
   /opt/blusuite/scripts/restore_database.sh
   # Select latest backup
   ```

4. **Verify Restoration**
   ```bash
   # Check table counts
   psql -U blusuite_user -d blusuite_db -c "SELECT COUNT(*) FROM auth_user;"
   
   # Test application
   systemctl start blusuite
   curl -I https://161.35.192.144/
   ```

**Recovery Time Objective (RTO):** 30 minutes  
**Recovery Point Objective (RPO):** 24 hours (daily backups)

---

### Scenario 2: Complete Server Failure

**Symptoms:**
- Server unreachable
- Hardware failure
- OS corruption

**Recovery Steps:**

1. **Provision New Server**
   - Ubuntu 24.04 LTS
   - Same specifications as original
   - Configure firewall and SSH

2. **Install Dependencies**
   ```bash
   sudo apt update
   sudo apt install -y postgresql python3-pip python3-venv nginx
   ```

3. **Restore Application Code**
   ```bash
   cd /opt
   git clone https://github.com/Wesraq/Blusuite.git blusuite
   cd blusuite
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Restore Database**
   ```bash
   # Create database
   sudo -u postgres createuser blusuite_user
   sudo -u postgres createdb -O blusuite_user blusuite_db
   
   # Restore from backup (retrieve from remote storage)
   zcat blusuite_backup.sql.gz | psql -U blusuite_user blusuite_db
   ```

5. **Configure Services**
   ```bash
   # Copy systemd service file
   sudo cp /opt/blusuite/deploy/blusuite.service /etc/systemd/system/
   
   # Copy nginx config
   sudo cp /opt/blusuite/deploy/nginx.conf /etc/nginx/sites-available/blusuite
   sudo ln -s /etc/nginx/sites-available/blusuite /etc/nginx/sites-enabled/
   
   # Start services
   sudo systemctl daemon-reload
   sudo systemctl enable blusuite
   sudo systemctl start blusuite
   sudo systemctl restart nginx
   ```

**Recovery Time Objective (RTO):** 4 hours  
**Recovery Point Objective (RPO):** 24 hours

---

### Scenario 3: Security Breach

**Symptoms:**
- Unauthorized access detected
- Suspicious audit log entries
- Data exfiltration alerts

**Recovery Steps:**

1. **Immediate Isolation**
   ```bash
   # Stop application
   systemctl stop blusuite
   
   # Block all incoming traffic (except SSH)
   ufw default deny incoming
   ufw allow 22/tcp
   ufw enable
   ```

2. **Assess Damage**
   ```bash
   # Review audit logs
   psql -U blusuite_user -d blusuite_db -c "SELECT * FROM blu_core_auditlog WHERE timestamp > NOW() - INTERVAL '24 hours' ORDER BY timestamp DESC;"
   
   # Check for unauthorized users
   psql -U blusuite_user -d blusuite_db -c "SELECT * FROM auth_user WHERE last_login > NOW() - INTERVAL '24 hours';"
   ```

3. **Restore to Clean State**
   ```bash
   # Restore from backup BEFORE breach
   /opt/blusuite/scripts/restore_database.sh
   # Select backup from before breach date
   ```

4. **Security Hardening**
   ```bash
   # Reset all passwords
   python manage.py shell
   >>> from django.contrib.auth import get_user_model
   >>> User = get_user_model()
   >>> for user in User.objects.filter(is_active=True):
   ...     user.set_unusable_password()
   ...     user.save()
   
   # Force password reset on next login
   # Rotate SECRET_KEY in settings
   # Update all API keys
   ```

5. **Restore Service**
   ```bash
   # Re-enable firewall rules
   ufw allow 80/tcp
   ufw allow 443/tcp
   
   # Start application
   systemctl start blusuite
   ```

**Recovery Time Objective (RTO):** 2 hours  
**Recovery Point Objective (RPO):** Variable (restore to pre-breach state)

---

## Backup Verification Schedule

### Daily (Automated)
- ✅ Backup creation
- ✅ Integrity check (gzip test)
- ✅ Disk space monitoring

### Weekly (Automated - Sundays)
- ✅ Full restoration test to temporary database
- ✅ Critical tables verification
- ✅ Table count validation

### Monthly (Manual)
- 📋 Review backup logs
- 📋 Test remote backup retrieval
- 📋 Verify backup retention policy
- 📋 Update disaster recovery documentation

### Quarterly (Manual)
- 📋 Full disaster recovery drill
- 📋 Test complete server rebuild
- 📋 Verify RTO/RPO targets
- 📋 Update contact lists and procedures

---

## Off-Site Backup Configuration

### Option 1: DigitalOcean Spaces (S3-Compatible)

```bash
# Install s3cmd
apt install s3cmd

# Configure
s3cmd --configure

# Upload backup
s3cmd put /opt/blusuite/backups/blusuite_*.sql.gz s3://blusuite-backups/
```

### Option 2: Rsync to Remote Server

```bash
# In backup_database.sh, set:
REMOTE_BACKUP_ENABLED=true
REMOTE_BACKUP_HOST="backup@backup-server.example.com"
REMOTE_BACKUP_PATH="/backups/blusuite"

# Setup SSH key authentication
ssh-keygen -t ed25519
ssh-copy-id backup@backup-server.example.com
```

### Option 3: Cloud Storage (Google Drive, Dropbox)

```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Configure
rclone config

# Upload
rclone copy /opt/blusuite/backups/ remote:blusuite-backups/
```

---

## Monitoring & Alerts

### Backup Success Monitoring

Create `/opt/blusuite/scripts/check_backup_health.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/blusuite/backups"
LATEST_BACKUP=$(find "$BACKUP_DIR" -name "blusuite_*.sql.gz" -type f -mtime -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "CRITICAL: No backup created in last 24 hours"
    # Send alert email or notification
    exit 1
else
    echo "OK: Backup created successfully"
    exit 0
fi
```

### Integration with Notification System

Add to `blu_billing/billing_automation.py`:

```python
def notify_backup_failed():
    """Notify admins when backup fails"""
    from blu_staff.apps.notifications.utils import bulk_notify
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    superadmins = User.objects.filter(role='SUPERADMIN')
    
    bulk_notify(
        recipients=superadmins,
        title='Database Backup Failed',
        message='Automated database backup failed. Immediate action required.',
        notification_type='ERROR',
        category='SYSTEM',
        send_email=True
    )
```

---

## Contact Information

### Emergency Contacts

**System Administrator:**  
Name: [Your Name]  
Email: admin@blusuite.com  
Phone: +XXX-XXX-XXXX

**Database Administrator:**  
Name: [DBA Name]  
Email: dba@blusuite.com  
Phone: +XXX-XXX-XXXX

**Hosting Provider:**  
DigitalOcean Support  
Email: support@digitalocean.com  
Phone: +1-888-890-6714

---

## Testing & Validation

### Monthly Backup Test Checklist

- [ ] Verify latest backup exists
- [ ] Check backup file size (should be > 10MB)
- [ ] Run integrity check: `gzip -t backup.sql.gz`
- [ ] Test restoration to temporary database
- [ ] Verify table counts match production
- [ ] Check critical tables exist
- [ ] Document test results

### Quarterly DR Drill Checklist

- [ ] Simulate server failure
- [ ] Provision new test server
- [ ] Restore application from backup
- [ ] Verify all functionality works
- [ ] Measure actual RTO vs target
- [ ] Document lessons learned
- [ ] Update procedures as needed

---

## Compliance & Audit

### Backup Audit Trail

All backup operations are logged:
- `/opt/blusuite/backups/backup.log` - Backup creation
- `/opt/blusuite/backups/restore.log` - Restoration events
- `/opt/blusuite/backups/verify.log` - Verification tests

### Retention Policy

- **Daily Backups:** 30 days
- **Weekly Backups:** 12 weeks (keep Sunday backups)
- **Monthly Backups:** 12 months (keep 1st of month)
- **Yearly Backups:** 7 years (compliance requirement)

### Data Protection

- Backups contain sensitive employee and financial data
- Encrypt backups at rest: `gpg --encrypt backup.sql.gz`
- Secure backup storage with restricted access
- Audit backup access logs regularly

---

## Appendix

### Backup File Naming Convention

Format: `blusuite_YYYYMMDD_HHMMSS.sql.gz`

Example: `blusuite_20260310_030000.sql.gz`
- Date: 2026-03-10
- Time: 03:00:00 UTC

### Estimated Backup Sizes

| Database Size | Backup Size (Compressed) | Backup Time |
|---------------|--------------------------|-------------|
| 1 GB | ~200 MB | 2-3 minutes |
| 5 GB | ~1 GB | 5-10 minutes |
| 10 GB | ~2 GB | 10-15 minutes |

### Recovery Time Estimates

| Scenario | RTO Target | Actual Time |
|----------|------------|-------------|
| Database restore | 30 min | 15-20 min |
| Full server rebuild | 4 hours | 2-3 hours |
| Security incident recovery | 2 hours | 1-2 hours |

---

**Document Version:** 1.0  
**Last Updated:** March 10, 2026  
**Next Review:** June 10, 2026
