# Deploy BLU Suite EMS to 167.71.41.220

**Server IP**: 167.71.41.220 (DigitalOcean Droplet)  
**Date**: March 3, 2026  

---

## 🚀 Quick Deployment Steps

### 1. Server Setup (SSH into your server)

```bash
# SSH into your DigitalOcean droplet
ssh root@167.71.41.220

# Update system packages
apt update && apt upgrade -y

# Install required packages
apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib supervisor

# Create application user
adduser blusuite
usermod -aG sudo blusuite
```

### 2. Database Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE blusuite_db;
CREATE USER blusuite_user WITH PASSWORD 'your_secure_password';
ALTER ROLE blusuite_user SET client_encoding TO 'utf8';
ALTER ROLE blusuite_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE blusuite_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE blusuite_db TO blusuite_user;
\q
```

### 3. Application Setup

```bash
# Switch to blusuite user
su - blusuite

# Clone the repository
git clone https://github.com/Wesraq/Blusuite.git
cd Blusuite

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

# Create production .env file
cp .env.example .env
nano .env
```

### 4. Production Environment Configuration

Edit `.env` file with production settings:

```env
# Django Settings
DJANGO_ENV=production
SECRET_KEY=your-new-generated-secret-key-here
DEBUG=False
ALLOWED_HOSTS=167.71.41.220

# Database (PostgreSQL)
DB_NAME=blusuite_db
DB_USER=blusuite_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# CORS and CSRF for production
CORS_ALLOWED_ORIGINS=http://167.71.41.220
CSRF_TRUSTED_ORIGINS=http://167.71.41.220

# Email Configuration
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Site URL
SITE_URL=http://167.71.41.220
```

### 5. Generate New SECRET_KEY

```bash
# Generate secure SECRET_KEY
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 6. Run Migrations

```bash
# Apply database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Create logs directory
mkdir logs
```

### 7. Gunicorn Configuration

Create gunicorn service file:

```bash
sudo nano /etc/systemd/system/blusuite.service
```

Add this content:

```ini
[Unit]
Description=BLU Suite EMS Gunicorn daemon
After=network.target

[Service]
User=blusuite
Group=blusuite
WorkingDirectory=/home/blusuite/Blusuite
Environment="PATH=/home/blusuite/Blusuite/venv/bin"
EnvironmentFile=/home/blusuite/Blusuite/.env
ExecStart=/home/blusuite/Blusuite/venv/bin/gunicorn --workers 3 --bind unix:/home/blusuite/Blusuite/blusuite.sock ems_project.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Start and enable the service:

```bash
sudo systemctl start blusuite
sudo systemctl enable blusuite
sudo systemctl status blusuite
```

### 8. Nginx Configuration

Create Nginx config:

```bash
sudo nano /etc/nginx/sites-available/blusuite
```

Add this content:

```nginx
server {
    listen 80;
    server_name 167.71.41.220;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /home/blusuite/Blusuite;
    }
    location /media/ {
        root /home/blusuite/Blusuite;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/blusuite/Blusuite/blusuite.sock;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/blusuite /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 9. Firewall Setup

```bash
# Configure UFW firewall
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 10. SSL Certificate (Optional but Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d 167.71.41.220

# Auto-renewal
sudo crontab -e
# Add this line:
0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 🧪 Testing the Deployment

### 1. Check Service Status

```bash
# Check Gunicorn
sudo systemctl status blusuite

# Check Nginx
sudo systemctl status nginx

# Check logs
sudo journalctl -u blusuite
tail -f /home/blusuite/Blusuite/logs/security.log
```

### 2. Test in Browser

Visit: `http://167.71.41.220`

### 3. Test Security Features

1. **Brute Force Protection**: Try 5 failed logins
2. **Password Complexity**: Create user with weak password
3. **Session Security**: Check cookies in browser dev tools
4. **File Upload**: Try uploading >10MB file

---

## 🔒 Security Verification

```bash
# Run Django security check
python manage.py check --deploy

# Expected warnings (OK for now):
# - SECURE_SSL_REDIRECT (if not using HTTPS)
# - SESSION_COOKIE_SECURE (if not using HTTPS)
# - CSRF_COOKIE_SECURE (if not using HTTPS)
```

---

## 📊 Monitoring

### Check Logs

```bash
# Security logs
tail -f /home/blusuite/Blusuite/logs/security.log

# Axes (brute force) logs
tail -f /home/blusuite/Blusuite/logs/axes.log

# Django logs
tail -f /home/blusuite/Blusuite/logs/django.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### System Monitoring

```bash
# Check system resources
htop
df -h
free -h

# Check network connections
netstat -tulpn
```

---

## 🚨 Troubleshooting

### Common Issues

1. **502 Bad Gateway**: Gunicorn not running
   ```bash
   sudo systemctl restart blusuite
   ```

2. **Database Connection Error**: Check DB credentials in `.env`
   ```bash
   python manage.py dbshell --database=default
   ```

3. **Static Files Not Loading**: Check permissions
   ```bash
   sudo chown -R blusuite:blusuite /home/blusuite/Blusuite/static/
   ```

4. **Permission Denied**: Check file permissions
   ```bash
   sudo chown -R blusuite:blusuite /home/blusuite/Blusuite/
   chmod +x /home/blusuite/Blusuite/manage.py
   ```

---

## 🔄 Updates and Maintenance

### Update Application

```bash
cd /home/blusuite/Blusuite
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart blusuite
```

### Backup Database

```bash
# Create backup script
sudo nano /home/blusuite/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/blusuite/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -h localhost -U blusuite_user blusuite_db > $BACKUP_DIR/blusuite_db_$DATE.sql

# Media files backup
tar -czf $BACKUP_DIR/media_$DATE.tar.gz /home/blusuite/Blusuite/media/

# Clean old backups (keep last 7 days)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

```bash
chmod +x /home/blusuite/backup.sh
crontab -e
# Add daily backup at 2 AM:
0 2 * * * /home/blusuite/backup.sh
```

---

## 📞 Support

If you encounter issues:

1. Check logs: `sudo journalctl -u blusuite`
2. Verify configuration: `python manage.py check --deploy`
3. Test database: `python manage.py dbshell`
4. Review deployment checklist: `DEPLOYMENT_CHECKLIST.md`

---

## ✅ Deployment Checklist

- [ ] Server updated and secured
- [ ] PostgreSQL database created
- [ ] Application cloned and configured
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Environment variables configured
- [ ] Migrations applied
- [ ] Superuser created
- [ ] Static files collected
- [ ] Gunicorn service configured
- [ ] Nginx configured and running
- [ ] Firewall configured
- [ ] SSL certificate installed (optional)
- [ ] Security features tested
- [ ] Monitoring and backup configured

---

**Deployment URL**: http://167.71.41.220  
**Status**: Ready for deployment  
**Security Level**: HIGH (with all implemented fixes)
