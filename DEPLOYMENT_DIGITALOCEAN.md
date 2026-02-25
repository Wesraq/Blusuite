# BLU Suite EMS - DigitalOcean Deployment Guide

**Platform**: DigitalOcean  
**Application**: Django-based BLU Suite EMS  
**Date**: February 15, 2026

---

## 📋 Prerequisites

### Required Accounts
- DigitalOcean account with billing enabled
- Domain name (optional but recommended)
- Git repository access (GitHub, GitLab, or Bitbucket)

### Local Requirements
- SSH key pair generated
- Git installed
- Database backup (if migrating existing data)

---

## 🚀 Deployment Options

### Option 1: App Platform (Recommended for Beginners)
**Pros**: Managed, auto-scaling, zero-config deployments  
**Cons**: Higher cost, less control  
**Best for**: Quick deployment, production apps

### Option 2: Droplet + Manual Setup (Recommended for Production)
**Pros**: Full control, cost-effective, customizable  
**Cons**: Requires server management knowledge  
**Best for**: Production apps, custom configurations

### Option 3: Kubernetes (Advanced)
**Pros**: High availability, auto-scaling, enterprise-grade  
**Cons**: Complex setup, higher cost  
**Best for**: Large-scale deployments

---

## 🎯 RECOMMENDED: Droplet Deployment Guide

This guide covers deploying BLU Suite EMS on a DigitalOcean Droplet with Ubuntu 22.04 LTS.

---

## Step 1: Create a Droplet

### 1.1 Droplet Specifications

**Minimum Requirements**:
- **CPU**: 2 vCPUs
- **RAM**: 4 GB
- **Storage**: 80 GB SSD
- **OS**: Ubuntu 22.04 LTS
- **Plan**: Basic ($24/month) or Premium ($48/month)

**Recommended for Production**:
- **CPU**: 4 vCPUs
- **RAM**: 8 GB
- **Storage**: 160 GB SSD
- **Plan**: Premium ($96/month)

### 1.2 Create Droplet via Dashboard

1. Log in to DigitalOcean
2. Click **Create** → **Droplets**
3. Choose **Ubuntu 22.04 LTS**
4. Select **Basic** or **Premium** plan
5. Choose datacenter region (closest to your users)
6. Add your SSH key
7. Enable **Monitoring** (free)
8. Add tags: `production`, `blu-suite`, `ems`
9. Click **Create Droplet**

### 1.3 Initial Access

```bash
# SSH into your droplet
ssh root@YOUR_DROPLET_IP

# Update system packages
apt update && apt upgrade -y

# Set timezone
timedatectl set-timezone Africa/Johannesburg  # Adjust as needed
```

---

## Step 2: Server Setup

### 2.1 Create Non-Root User

```bash
# Create deployment user
adduser deploy
usermod -aG sudo deploy

# Copy SSH keys
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy

# Switch to deploy user
su - deploy
```

### 2.2 Install System Dependencies

```bash
# Install Python and build tools
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib libpq-dev

# Install Nginx
sudo apt install -y nginx

# Install Redis (for caching and Celery)
sudo apt install -y redis-server

# Install additional tools
sudo apt install -y git curl wget build-essential supervisor
```

### 2.3 Configure PostgreSQL

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE blu_suite_db;
CREATE USER blu_suite_user WITH PASSWORD 'your_secure_password_here';
ALTER ROLE blu_suite_user SET client_encoding TO 'utf8';
ALTER ROLE blu_suite_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE blu_suite_user SET timezone TO 'Africa/Johannesburg';
GRANT ALL PRIVILEGES ON DATABASE blu_suite_db TO blu_suite_user;

# Exit psql
\q
```

### 2.4 Configure Redis

```bash
# Edit Redis config
sudo nano /etc/redis/redis.conf

# Set maxmemory policy (add these lines)
maxmemory 256mb
maxmemory-policy allkeys-lru

# Restart Redis
sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

---

## Step 3: Deploy Application

### 3.1 Clone Repository

```bash
# Create app directory
sudo mkdir -p /var/www/blu_suite
sudo chown deploy:deploy /var/www/blu_suite

# Clone repository
cd /var/www/blu_suite
git clone YOUR_REPOSITORY_URL .

# Or upload files via SCP
# scp -r /local/path/to/BLU_suite deploy@YOUR_DROPLET_IP:/var/www/blu_suite
```

### 3.2 Create Virtual Environment

```bash
cd /var/www/blu_suite

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### 3.3 Install Python Dependencies

```bash
# Install requirements
pip install -r requirements.txt

# Install production server
pip install gunicorn

# Install PostgreSQL adapter
pip install psycopg2-binary
```

### 3.4 Configure Environment Variables

```bash
# Create .env file
nano /var/www/blu_suite/.env
```

Add the following configuration:

```env
# Django Settings
SECRET_KEY=your_very_long_random_secret_key_here_generate_new_one
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,YOUR_DROPLET_IP

# Database
DATABASE_NAME=blu_suite_db
DATABASE_USER=blu_suite_user
DATABASE_PASSWORD=your_secure_password_here
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Email Configuration (for notifications)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Media and Static Files
MEDIA_ROOT=/var/www/blu_suite/media
STATIC_ROOT=/var/www/blu_suite/staticfiles

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Timezone
TIME_ZONE=Africa/Johannesburg
```

### 3.5 Update Django Settings

Edit `ems_project/settings.py`:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Security
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME'),
        'USER': os.getenv('DATABASE_USER'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD'),
        'HOST': os.getenv('DATABASE_HOST', 'localhost'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

# Static and Media Files
STATIC_ROOT = os.getenv('STATIC_ROOT', BASE_DIR / 'staticfiles')
MEDIA_ROOT = os.getenv('MEDIA_ROOT', BASE_DIR / 'media')
STATIC_URL = '/static/'
MEDIA_URL = '/media/'

# Security Settings (Production)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
```

### 3.6 Run Migrations and Collect Static Files

```bash
cd /var/www/blu_suite
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Create media directories
mkdir -p media/company_logos
mkdir -p media/employee_documents
mkdir -p media/signatures

# Set permissions
sudo chown -R deploy:www-data /var/www/blu_suite
sudo chmod -R 755 /var/www/blu_suite
sudo chmod -R 775 /var/www/blu_suite/media
```

---

## Step 4: Configure Gunicorn

### 4.1 Create Gunicorn Configuration

```bash
# Create gunicorn config directory
sudo mkdir -p /etc/gunicorn

# Create gunicorn config file
sudo nano /etc/gunicorn/blu_suite.py
```

Add the following:

```python
import multiprocessing

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "/var/log/gunicorn/blu_suite_access.log"
errorlog = "/var/log/gunicorn/blu_suite_error.log"
loglevel = "info"

# Process naming
proc_name = "blu_suite_gunicorn"

# Server mechanics
daemon = False
pidfile = "/var/run/gunicorn/blu_suite.pid"
user = "deploy"
group = "www-data"
umask = 0o007

# SSL (if terminating SSL at Gunicorn instead of Nginx)
# keyfile = "/path/to/ssl/key.pem"
# certfile = "/path/to/ssl/cert.pem"
```

### 4.2 Create Systemd Service

```bash
# Create log directory
sudo mkdir -p /var/log/gunicorn
sudo chown deploy:www-data /var/log/gunicorn

# Create pid directory
sudo mkdir -p /var/run/gunicorn
sudo chown deploy:www-data /var/run/gunicorn

# Create systemd service file
sudo nano /etc/systemd/system/blu_suite.service
```

Add the following:

```ini
[Unit]
Description=BLU Suite EMS Gunicorn Daemon
After=network.target

[Service]
Type=notify
User=deploy
Group=www-data
WorkingDirectory=/var/www/blu_suite
Environment="PATH=/var/www/blu_suite/venv/bin"
ExecStart=/var/www/blu_suite/venv/bin/gunicorn \
    --config /etc/gunicorn/blu_suite.py \
    ems_project.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4.3 Start Gunicorn Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable blu_suite

# Start service
sudo systemctl start blu_suite

# Check status
sudo systemctl status blu_suite

# View logs
sudo journalctl -u blu_suite -f
```

---

## Step 5: Configure Nginx

### 5.1 Create Nginx Configuration

```bash
# Create nginx config
sudo nano /etc/nginx/sites-available/blu_suite
```

Add the following:

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=blu_suite_limit:10m rate=10r/s;

# Upstream Gunicorn
upstream blu_suite_app {
    server 127.0.0.1:8000 fail_timeout=0;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com www.your-domain.com;
    
    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    # Redirect all HTTP to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    # SSL certificates (will be configured with Certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Client body size (for file uploads)
    client_max_body_size 10M;
    
    # Logging
    access_log /var/log/nginx/blu_suite_access.log;
    error_log /var/log/nginx/blu_suite_error.log;
    
    # Static files
    location /static/ {
        alias /var/www/blu_suite/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /var/www/blu_suite/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Favicon
    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }
    
    # Robots.txt
    location = /robots.txt {
        access_log off;
        log_not_found off;
    }
    
    # Main application
    location / {
        # Rate limiting
        limit_req zone=blu_suite_limit burst=20 nodelay;
        
        # Proxy headers
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Proxy settings
        proxy_redirect off;
        proxy_buffering off;
        proxy_pass http://blu_suite_app;
    }
}
```

### 5.2 Enable Nginx Configuration

```bash
# Test nginx configuration
sudo nginx -t

# Create symbolic link
sudo ln -s /etc/nginx/sites-available/blu_suite /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Restart nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## Step 6: SSL Certificate with Let's Encrypt

### 6.1 Install Certbot

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Create webroot directory
sudo mkdir -p /var/www/certbot
```

### 6.2 Obtain SSL Certificate

```bash
# Stop nginx temporarily
sudo systemctl stop nginx

# Obtain certificate
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Start nginx
sudo systemctl start nginx

# Test auto-renewal
sudo certbot renew --dry-run
```

### 6.3 Auto-Renewal Setup

Certbot automatically creates a systemd timer. Verify:

```bash
# Check timer status
sudo systemctl status certbot.timer

# Enable timer
sudo systemctl enable certbot.timer
```

---

## Step 7: Configure Firewall

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow OpenSSH

# Allow HTTP and HTTPS
sudo ufw allow 'Nginx Full'

# Check status
sudo ufw status
```

---

## Step 8: Monitoring and Logging

### 8.1 Install Monitoring Tools

```bash
# Install monitoring tools
sudo apt install -y htop iotop nethogs

# Install log rotation
sudo apt install -y logrotate
```

### 8.2 Configure Log Rotation

```bash
# Create logrotate config
sudo nano /etc/logrotate.d/blu_suite
```

Add:

```
/var/log/gunicorn/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 deploy www-data
    sharedscripts
    postrotate
        systemctl reload blu_suite > /dev/null 2>&1 || true
    endscript
}

/var/log/nginx/blu_suite*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        systemctl reload nginx > /dev/null 2>&1 || true
    endscript
}
```

---

## Step 9: Backup Configuration

### 9.1 Database Backup Script

```bash
# Create backup directory
sudo mkdir -p /var/backups/blu_suite
sudo chown deploy:deploy /var/backups/blu_suite

# Create backup script
nano /home/deploy/backup_database.sh
```

Add:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/blu_suite"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="blu_suite_db_$DATE.sql.gz"

# Dump database
pg_dump -U blu_suite_user blu_suite_db | gzip > "$BACKUP_DIR/$FILENAME"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "blu_suite_db_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $FILENAME"
```

Make executable:

```bash
chmod +x /home/deploy/backup_database.sh
```

### 9.2 Schedule Backups with Cron

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /home/deploy/backup_database.sh >> /var/log/blu_suite_backup.log 2>&1
```

---

## Step 10: DigitalOcean Managed Database (Optional)

For better reliability, consider using DigitalOcean Managed PostgreSQL:

### 10.1 Create Managed Database

1. Go to **Databases** in DigitalOcean dashboard
2. Click **Create Database**
3. Choose **PostgreSQL 15**
4. Select plan (Basic $15/month minimum)
5. Choose same datacenter as Droplet
6. Create database

### 10.2 Configure Connection

Update `.env`:

```env
DATABASE_HOST=your-db-cluster.db.ondigitalocean.com
DATABASE_PORT=25060
DATABASE_NAME=blu_suite_db
DATABASE_USER=doadmin
DATABASE_PASSWORD=provided_by_digitalocean
DATABASE_SSLMODE=require
```

---

## 📊 Post-Deployment Checklist

- [ ] Application accessible via domain
- [ ] SSL certificate installed and working
- [ ] Static files loading correctly
- [ ] Media uploads working
- [ ] Database migrations applied
- [ ] Superuser account created
- [ ] Email notifications working
- [ ] Firewall configured
- [ ] Backups scheduled
- [ ] Monitoring enabled
- [ ] Log rotation configured
- [ ] Performance tested

---

## 🔧 Maintenance Commands

### Application Updates

```bash
cd /var/www/blu_suite
source venv/bin/activate

# Pull latest code
git pull origin main

# Install new dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart application
sudo systemctl restart blu_suite
```

### View Logs

```bash
# Application logs
sudo journalctl -u blu_suite -f

# Nginx access logs
sudo tail -f /var/log/nginx/blu_suite_access.log

# Nginx error logs
sudo tail -f /var/log/nginx/blu_suite_error.log

# Gunicorn logs
sudo tail -f /var/log/gunicorn/blu_suite_error.log
```

### Database Management

```bash
# Access database
sudo -u postgres psql blu_suite_db

# Create backup manually
/home/deploy/backup_database.sh

# Restore from backup
gunzip < /var/backups/blu_suite/backup.sql.gz | sudo -u postgres psql blu_suite_db
```

---

## 💰 Cost Estimation

### Basic Setup (Small Team, <50 users)
- Droplet (4GB RAM): $24/month
- Managed Database (Basic): $15/month
- Backups: $1/month
- **Total**: ~$40/month

### Production Setup (Medium Team, 50-200 users)
- Droplet (8GB RAM): $48/month
- Managed Database (Professional): $60/month
- Load Balancer: $12/month
- Backups: $5/month
- **Total**: ~$125/month

### Enterprise Setup (Large Team, 200+ users)
- Droplet (16GB RAM) x2: $192/month
- Managed Database (Business): $180/month
- Load Balancer: $12/month
- Spaces (Object Storage): $5/month
- Backups: $10/month
- **Total**: ~$400/month

---

## 🚨 Troubleshooting

### Application Won't Start

```bash
# Check service status
sudo systemctl status blu_suite

# Check logs
sudo journalctl -u blu_suite -n 50

# Test Gunicorn manually
cd /var/www/blu_suite
source venv/bin/activate
gunicorn --bind 0.0.0.0:8000 ems_project.wsgi:application
```

### 502 Bad Gateway

```bash
# Check if Gunicorn is running
sudo systemctl status blu_suite

# Check Nginx error logs
sudo tail -f /var/log/nginx/blu_suite_error.log

# Restart services
sudo systemctl restart blu_suite
sudo systemctl restart nginx
```

### Static Files Not Loading

```bash
# Collect static files again
cd /var/www/blu_suite
source venv/bin/activate
python manage.py collectstatic --noinput

# Check permissions
sudo chown -R deploy:www-data /var/www/blu_suite/staticfiles
sudo chmod -R 755 /var/www/blu_suite/staticfiles
```

### Database Connection Issues

```bash
# Test database connection
sudo -u postgres psql -U blu_suite_user -d blu_suite_db -h localhost

# Check PostgreSQL status
sudo systemctl status postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql
```

---

## 📞 Support Resources

- **DigitalOcean Docs**: https://docs.digitalocean.com/
- **Django Deployment**: https://docs.djangoproject.com/en/stable/howto/deployment/
- **Gunicorn Docs**: https://docs.gunicorn.org/
- **Nginx Docs**: https://nginx.org/en/docs/

---

**Deployment Guide Version**: 1.0  
**Last Updated**: February 15, 2026  
**Platform**: DigitalOcean  
**Status**: Production Ready ✓
