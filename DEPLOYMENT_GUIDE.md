# EMS Suite - DigitalOcean Deployment Guide

**Server Details:**
- Droplet: ubuntu-s-2vcpu-2gb-90gb-intel-fra-01
- IP: 104.248.21.180
- OS: Ubuntu 24.04 (LTS) x64
- Memory: 2 GB
- vCPUs: 2 Intel
- Disk: 90 GB SSD

---

## Prerequisites

1. SSH access to your droplet
2. Domain name (optional but recommended)
3. SSL certificate (Let's Encrypt - free)

---

## Step 1: Connect to Your Droplet

```bash
ssh root@104.248.21.180
```

---

## Step 2: Initial Server Setup

### Update System
```bash
apt update && apt upgrade -y
```

### Install Required Packages
```bash
apt install -y python3.12 python3.12-venv python3-pip postgresql postgresql-contrib nginx git supervisor redis-server
```

### Create Application User
```bash
adduser --disabled-password --gecos "" emsuser
usermod -aG sudo emsuser
```

---

## Step 3: Setup PostgreSQL Database

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE ems_production;
CREATE USER emsuser WITH PASSWORD 'your_secure_password_here';
ALTER ROLE emsuser SET client_encoding TO 'utf8';
ALTER ROLE emsuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE emsuser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE ems_production TO emsuser;
\q
```

---

## Step 4: Deploy Application Code

### Switch to Application User
```bash
su - emsuser
```

### Clone Repository (or Upload Code)
```bash
# Option 1: If using Git
git clone https://github.com/yourusername/BLU_suite.git /home/emsuser/BLU_suite

# Option 2: Upload via SCP from your local machine
# From your local machine:
# scp -r d:\projects\BLU_suite root@104.248.21.180:/home/emsuser/
# Then: chown -R emsuser:emsuser /home/emsuser/BLU_suite
```

### Navigate to Project
```bash
cd /home/emsuser/BLU_suite
```

---

## Step 5: Setup Python Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 6: Configure Environment Variables

Create `.env` file:
```bash
nano /home/emsuser/BLU_suite/.env
```

Add the following (replace with your actual values):
```env
# Django Settings
SECRET_KEY=your-super-secret-key-here-change-this-in-production
DEBUG=False
ALLOWED_HOSTS=104.248.21.180,yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgres://emsuser:your_secure_password_here@localhost:5432/ems_production

# Email (AWS SES or SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# AWS S3 (for media files - optional)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=eu-central-1

# Redis (for caching and Celery)
REDIS_URL=redis://localhost:6379/0

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

Save and exit (Ctrl+X, Y, Enter)

---

## Step 7: Run Database Migrations

```bash
source venv/bin/activate
cd /home/emsuser/BLU_suite

python manage.py makemigrations
python manage.py migrate
python manage.py migrate --database=default
```

---

## Step 8: Create Superuser

```bash
python manage.py createsuperuser
```

---

## Step 9: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

---

## Step 10: Setup Gunicorn

Create Gunicorn config:
```bash
nano /home/emsuser/BLU_suite/gunicorn_config.py
```

Add:
```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
errorlog = "/home/emsuser/BLU_suite/logs/gunicorn_error.log"
accesslog = "/home/emsuser/BLU_suite/logs/gunicorn_access.log"
loglevel = "info"
```

Create logs directory:
```bash
mkdir -p /home/emsuser/BLU_suite/logs
```

---

## Step 11: Setup Supervisor (Process Manager)

Exit to root user:
```bash
exit
```

Create supervisor config:
```bash
nano /etc/supervisor/conf.d/ems.conf
```

Add:
```ini
[program:ems_gunicorn]
command=/home/emsuser/BLU_suite/venv/bin/gunicorn ems_project.wsgi:application -c /home/emsuser/BLU_suite/gunicorn_config.py
directory=/home/emsuser/BLU_suite
user=emsuser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/emsuser/BLU_suite/logs/supervisor.log
environment=PATH="/home/emsuser/BLU_suite/venv/bin"

[program:ems_celery]
command=/home/emsuser/BLU_suite/venv/bin/celery -A ems_project worker -l info
directory=/home/emsuser/BLU_suite
user=emsuser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/emsuser/BLU_suite/logs/celery.log
environment=PATH="/home/emsuser/BLU_suite/venv/bin"
```

Update supervisor:
```bash
supervisorctl reread
supervisorctl update
supervisorctl start all
```

Check status:
```bash
supervisorctl status
```

---

## Step 12: Configure Nginx

Create Nginx config:
```bash
nano /etc/nginx/sites-available/ems
```

Add:
```nginx
upstream ems_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name 104.248.21.180 yourdomain.com www.yourdomain.com;

    client_max_body_size 100M;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Static files
    location /static/ {
        alias /home/emsuser/BLU_suite/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/emsuser/BLU_suite/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://ems_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

Enable site:
```bash
ln -s /etc/nginx/sites-available/ems /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

---

## Step 13: Setup SSL with Let's Encrypt (Optional but Recommended)

```bash
apt install -y certbot python3-certbot-nginx

# Replace yourdomain.com with your actual domain
certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal test
certbot renew --dry-run
```

---

## Step 14: Configure Firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
ufw status
```

---

## Step 15: Final Checks

### Check Gunicorn
```bash
supervisorctl status ems_gunicorn
```

### Check Nginx
```bash
systemctl status nginx
```

### Check PostgreSQL
```bash
systemctl status postgresql
```

### Check Redis
```bash
systemctl status redis
```

### View Logs
```bash
tail -f /home/emsuser/BLU_suite/logs/gunicorn_error.log
tail -f /home/emsuser/BLU_suite/logs/supervisor.log
tail -f /var/log/nginx/error.log
```

---

## Step 16: Access Your Application

Open browser and navigate to:
- **HTTP:** `http://104.248.21.180`
- **HTTPS (if SSL configured):** `https://yourdomain.com`

Admin panel:
- `http://104.248.21.180/admin/`

---

## Maintenance Commands

### Restart Application
```bash
supervisorctl restart ems_gunicorn
```

### Update Code
```bash
su - emsuser
cd /home/emsuser/BLU_suite
git pull  # or upload new files
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
exit
supervisorctl restart ems_gunicorn
```

### View Logs
```bash
# Application logs
tail -f /home/emsuser/BLU_suite/logs/gunicorn_error.log

# Nginx logs
tail -f /var/log/nginx/error.log

# Supervisor logs
tail -f /home/emsuser/BLU_suite/logs/supervisor.log
```

### Database Backup
```bash
pg_dump -U emsuser ems_production > /home/emsuser/backups/ems_$(date +%Y%m%d).sql
```

---

## Troubleshooting

### Application won't start
```bash
# Check supervisor status
supervisorctl status

# Check logs
tail -100 /home/emsuser/BLU_suite/logs/gunicorn_error.log

# Restart services
supervisorctl restart all
```

### 502 Bad Gateway
```bash
# Check if Gunicorn is running
supervisorctl status ems_gunicorn

# Check Nginx config
nginx -t

# Restart Nginx
systemctl restart nginx
```

### Database connection errors
```bash
# Check PostgreSQL status
systemctl status postgresql

# Test database connection
sudo -u postgres psql -d ems_production
```

### Static files not loading
```bash
# Re-collect static files
su - emsuser
cd /home/emsuser/BLU_suite
source venv/bin/activate
python manage.py collectstatic --noinput
```

---

## Security Checklist

- [ ] Changed SECRET_KEY in .env
- [ ] Set DEBUG=False
- [ ] Configured ALLOWED_HOSTS
- [ ] Setup SSL certificate
- [ ] Enabled firewall (ufw)
- [ ] Strong database password
- [ ] Regular backups configured
- [ ] Updated all packages
- [ ] Configured proper file permissions
- [ ] Setup monitoring (optional: Sentry)

---

## Performance Optimization

### Enable Gzip Compression (Nginx)
Add to `/etc/nginx/nginx.conf`:
```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;
```

### Database Connection Pooling
Install pgbouncer for better database performance:
```bash
apt install -y pgbouncer
```

### Redis Caching
Already configured in requirements.txt - ensure Redis is running:
```bash
systemctl enable redis-server
systemctl start redis-server
```

---

## Monitoring Setup (Optional)

### Install Sentry
Already in requirements.txt. Add to settings.py:
```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True
)
```

---

## Next Steps

1. Configure your domain DNS to point to `104.248.21.180`
2. Setup SSL certificate with Let's Encrypt
3. Configure email settings for notifications
4. Setup automated backups
5. Configure monitoring and alerts
6. Test all functionality thoroughly

---

## Support

For issues or questions:
- Check logs in `/home/emsuser/BLU_suite/logs/`
- Review Django documentation: https://docs.djangoproject.com/
- Check Nginx logs: `/var/log/nginx/`

---

**Deployment Date:** February 25, 2026  
**Server Location:** Frankfurt (FRA1)  
**Application:** BLU Suite EMS
