# BLU Suite — Local Deployment Guide (Without GitHub)

This guide explains how to deploy BLU Suite directly from your local machine to a server, without using GitHub or any version control system.

---

## Overview

**Deployment Method:** Direct file transfer from local machine  
**Target Server:** DigitalOcean Droplet (or any Ubuntu 24.04 LTS server)  
**Stack:** Nginx → Gunicorn → Django + WhiteNoise · PostgreSQL (Supabase) · Python 3.11+

---

## Prerequisites

### On Your Local Machine (Windows)
- PowerShell or WSL/Git Bash
- SCP client (built into Windows 10+, or use WinSCP/FileZilla)
- SSH client

### On Your Server
- Ubuntu 24.04 LTS (or similar)
- Root or sudo access
- Minimum 2GB RAM, 2 vCPUs, 60GB storage

---

## Part 1: Create Deployment Package (On Your Local Machine)

### Step 1: Run the Package Creation Script

**For Windows (PowerShell):**
```powershell
cd d:\projects\BLU_suite
.\scripts\create_deployment_package.ps1
```

**For Linux/Mac/WSL:**
```bash
cd /d/projects/BLU_suite
chmod +x scripts/create_deployment_package.sh
./scripts/create_deployment_package.sh
```

This will create a file like `blusuite_deploy_20260306_141530.tar.gz` in your project root.

### Step 2: Verify Package Creation

The script will display:
- Package location
- Package size
- Next steps

Example output:
```
✓ DEPLOYMENT PACKAGE CREATED
Package Location: d:\projects\BLU_suite\blusuite_deploy_20260306_141530.tar.gz
Package Size: 15.3 MB
```

---

## Part 2: Upload Package to Server

### Step 3: Upload via SCP

**From Windows PowerShell:**
```powershell
scp d:\projects\BLU_suite\blusuite_deploy_*.tar.gz root@YOUR_SERVER_IP:/tmp/
```

**From Linux/Mac/WSL:**
```bash
scp blusuite_deploy_*.tar.gz root@YOUR_SERVER_IP:/tmp/
```

Replace `YOUR_SERVER_IP` with your actual server IP address (e.g., `161.35.79.174`).

**Alternative: Using WinSCP or FileZilla**
1. Connect to your server via SFTP
2. Upload the `.tar.gz` file to `/tmp/` directory

---

## Part 3: Deploy on Server

### Step 4: Connect to Your Server

```bash
ssh root@YOUR_SERVER_IP
```

### Step 5: Run the Deployment Script

```bash
# Make the deployment script executable
cd /tmp
tar -xzf blusuite_deploy_*.tar.gz
cd blusuite_deploy_*/scripts
chmod +x deploy_from_local.sh

# Run the deployment script
sudo bash deploy_from_local.sh
```

This script will:
- Install system packages (Python, Nginx, PostgreSQL libraries)
- Create application user (`blusuite`)
- Extract your deployment package to `/opt/blusuite`
- Setup Python virtual environment
- Install Python dependencies
- Configure systemd service
- Setup Nginx

---

## Part 4: Configure Environment

### Step 6: Edit Environment Variables

```bash
nano /opt/blusuite/.env
```

**Critical settings to configure:**

```env
# Django Settings
SECRET_KEY=<generate-new-secret-key>
DEBUG=False
ALLOWED_HOSTS=YOUR_SERVER_IP,yourdomain.com

# Site URL
SITE_URL=http://YOUR_SERVER_IP

# Database (Supabase)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=<new-secure-password>
DB_HOST=your-supabase-host.supabase.co
DB_PORT=5432

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=<new-gmail-app-password>
```

### Step 7: Generate New SECRET_KEY

```bash
sudo -u blusuite /opt/blusuite/venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output and paste it into your `.env` file as the `SECRET_KEY` value.

---

## Part 5: Initialize Django Application

### Step 8: Run Database Migrations

```bash
sudo -u blusuite /opt/blusuite/venv/bin/python /opt/blusuite/manage.py migrate
```

### Step 9: Collect Static Files

```bash
sudo -u blusuite /opt/blusuite/venv/bin/python /opt/blusuite/manage.py collectstatic --noinput
```

### Step 10: Create Superuser

```bash
sudo -u blusuite /opt/blusuite/venv/bin/python /opt/blusuite/manage.py createsuperuser
```

Follow the prompts to create your admin account.

---

## Part 6: Start Services

### Step 11: Start Gunicorn Service

```bash
# Create runtime directory
mkdir -p /run/gunicorn
chown blusuite:blusuite /run/gunicorn

# Start the service
systemctl start blusuite
systemctl status blusuite
```

Expected output: `active (running)`

### Step 12: Start Nginx

```bash
systemctl restart nginx
systemctl status nginx
```

---

## Part 7: Configure Firewall

### Step 13: Setup UFW Firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
ufw status
```

---

## Part 8: Verify Deployment

### Step 14: Test the Application

```bash
# Test health endpoint
curl -I http://localhost/health/

# Expected: HTTP/1.1 200 OK
```

### Step 15: Access from Browser

Open your browser and navigate to:
- **Main Site:** `http://YOUR_SERVER_IP`
- **Admin Panel:** `http://YOUR_SERVER_IP/admin/`

Login with the superuser credentials you created.

---

## Updating Your Deployment

When you need to deploy updates:

### On Your Local Machine:

1. **Create new deployment package:**
   ```powershell
   .\scripts\create_deployment_package.ps1
   ```

2. **Upload to server:**
   ```powershell
   scp blusuite_deploy_*.tar.gz root@YOUR_SERVER_IP:/tmp/
   ```

### On Your Server:

3. **Extract and update:**
   ```bash
   cd /opt/blusuite
   
   # Backup current version
   sudo -u blusuite tar -czf /opt/blusuite_backup_$(date +%Y%m%d).tar.gz .
   
   # Extract new version
   tar -xzf /tmp/blusuite_deploy_*.tar.gz --strip-components=1
   chown -R blusuite:blusuite /opt/blusuite
   
   # Update dependencies
   sudo -u blusuite /opt/blusuite/venv/bin/pip install -r requirements.txt
   
   # Run migrations
   sudo -u blusuite /opt/blusuite/venv/bin/python manage.py migrate
   
   # Collect static files
   sudo -u blusuite /opt/blusuite/venv/bin/python manage.py collectstatic --noinput
   
   # Restart service
   systemctl restart blusuite
   ```

---

## Troubleshooting

### Application Won't Start

```bash
# Check service status
systemctl status blusuite

# View logs
journalctl -u blusuite -n 50 --no-pager

# Check Gunicorn error log
tail -50 /var/log/gunicorn/error.log
```

### 502 Bad Gateway

```bash
# Check if Gunicorn is running
systemctl status blusuite

# Check Nginx configuration
nginx -t

# Restart both services
systemctl restart blusuite
systemctl restart nginx
```

### Static Files Not Loading

```bash
# Re-collect static files
sudo -u blusuite /opt/blusuite/venv/bin/python /opt/blusuite/manage.py collectstatic --noinput

# Check permissions
ls -la /opt/blusuite/staticfiles/
```

### Database Connection Errors

```bash
# Test database connection
sudo -u blusuite /opt/blusuite/venv/bin/python /opt/blusuite/manage.py dbshell

# Check .env file
cat /opt/blusuite/.env | grep DB_
```

---

## Important Security Notes

### ⚠️ Before Going Live

1. **Rotate all credentials** that may have been exposed:
   - Generate new `SECRET_KEY`
   - Reset Supabase database password
   - Create new Gmail app password
   - Update all values in `.env`

2. **Verify security settings:**
   - `DEBUG=False` in `.env`
   - Proper `ALLOWED_HOSTS` configuration
   - Firewall enabled and configured
   - SSL certificate installed (recommended)

3. **Setup SSL with Let's Encrypt (Recommended):**
   ```bash
   apt install -y certbot python3-certbot-nginx
   certbot --nginx -d yourdomain.com -d www.yourdomain.com
   certbot renew --dry-run
   ```

---

## Useful Commands

### View Logs
```bash
# Application logs
journalctl -u blusuite -f

# Gunicorn error log
tail -f /var/log/gunicorn/error.log

# Nginx error log
tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
# Restart application
systemctl restart blusuite

# Restart Nginx
systemctl restart nginx

# Restart both
systemctl restart blusuite nginx
```

### Check Status
```bash
# Service status
systemctl status blusuite
systemctl status nginx

# Check if ports are listening
netstat -tlnp | grep -E ':(80|8000)'
```

---

## File Locations Reference

| Item | Location |
|------|----------|
| Application Code | `/opt/blusuite/` |
| Virtual Environment | `/opt/blusuite/venv/` |
| Environment File | `/opt/blusuite/.env` |
| Static Files | `/opt/blusuite/staticfiles/` |
| Media Files | `/opt/blusuite/media/` |
| Gunicorn Logs | `/var/log/gunicorn/` |
| Systemd Service | `/etc/systemd/system/blusuite.service` |
| Nginx Config | `/etc/nginx/conf.d/blusuite.conf` |

---

## Support

For issues or questions:
- Check application logs in `/var/log/gunicorn/`
- Review Nginx logs in `/var/log/nginx/`
- Verify `.env` configuration
- Check Django documentation: https://docs.djangoproject.com/

---

**Deployment Method:** Local Package Transfer  
**Last Updated:** March 6, 2026  
**Application:** BLU Suite EMS
