#!/bin/bash

# BLU Suite EMS - Quick Setup Script for DigitalOcean Ubuntu 24.04
# This script automates the entire deployment process

set -e  # Exit on any error

echo "=========================================="
echo "BLU Suite EMS - Quick Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${GREEN}Step 1: Updating system packages...${NC}"
apt update && apt upgrade -y

echo ""
echo -e "${GREEN}Step 2: Installing required packages...${NC}"
apt install -y python3.12 python3.12-venv python3-pip postgresql postgresql-contrib \
    nginx git supervisor redis-server certbot python3-certbot-nginx

echo ""
echo -e "${GREEN}Step 3: Creating application user...${NC}"
if id "emsuser" &>/dev/null; then
    echo "User emsuser already exists"
else
    adduser --disabled-password --gecos "" emsuser
    echo "User emsuser created"
fi

echo ""
echo -e "${GREEN}Step 4: Setting up PostgreSQL database...${NC}"
sudo -u postgres psql -c "SELECT 1 FROM pg_database WHERE datname = 'ems_production'" | grep -q 1 || \
sudo -u postgres psql <<EOF
CREATE DATABASE ems_production;
CREATE USER emsuser WITH PASSWORD 'ems_secure_pass_2026';
ALTER ROLE emsuser SET client_encoding TO 'utf8';
ALTER ROLE emsuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE emsuser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE ems_production TO emsuser;
EOF

echo -e "${GREEN}Database setup complete${NC}"

echo ""
echo -e "${GREEN}Step 5: Copying application files...${NC}"
if [ -d "/home/emsuser/BLU_suite" ]; then
    echo "Backing up existing installation..."
    mv /home/emsuser/BLU_suite /home/emsuser/BLU_suite_backup_$(date +%Y%m%d_%H%M%S)
fi

cp -r /root/BLU_suite /home/emsuser/
chown -R emsuser:emsuser /home/emsuser/BLU_suite

echo ""
echo -e "${GREEN}Step 6: Setting up Python virtual environment...${NC}"
sudo -u emsuser bash <<'EOF'
cd /home/emsuser/BLU_suite
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
EOF

echo ""
echo -e "${GREEN}Step 7: Creating .env file...${NC}"
cat > /home/emsuser/BLU_suite/.env <<'EOF'
# Django Settings
SECRET_KEY=django-insecure-production-key-change-this-immediately-$(openssl rand -base64 32)
DEBUG=False
ALLOWED_HOSTS=104.248.21.180,localhost,127.0.0.1

# Database
DATABASE_URL=postgres://emsuser:ems_secure_pass_2026@localhost:5432/ems_production

# Email (Update with your SMTP settings)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
EOF

chown emsuser:emsuser /home/emsuser/BLU_suite/.env

echo ""
echo -e "${GREEN}Step 8: Running database migrations...${NC}"
sudo -u emsuser bash <<'EOF'
cd /home/emsuser/BLU_suite
source venv/bin/activate
python manage.py migrate
python manage.py migrate --database=default
EOF

echo ""
echo -e "${GREEN}Step 9: Collecting static files...${NC}"
sudo -u emsuser bash <<'EOF'
cd /home/emsuser/BLU_suite
source venv/bin/activate
python manage.py collectstatic --noinput
EOF

echo ""
echo -e "${GREEN}Step 10: Creating logs directory...${NC}"
mkdir -p /home/emsuser/BLU_suite/logs
chown -R emsuser:emsuser /home/emsuser/BLU_suite/logs

echo ""
echo -e "${GREEN}Step 11: Setting up Gunicorn config...${NC}"
cat > /home/emsuser/BLU_suite/gunicorn_config.py <<'EOF'
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
errorlog = "/home/emsuser/BLU_suite/logs/gunicorn_error.log"
accesslog = "/home/emsuser/BLU_suite/logs/gunicorn_access.log"
loglevel = "info"
EOF

chown emsuser:emsuser /home/emsuser/BLU_suite/gunicorn_config.py

echo ""
echo -e "${GREEN}Step 12: Setting up Supervisor...${NC}"
cat > /etc/supervisor/conf.d/ems.conf <<'EOF'
[program:ems_gunicorn]
command=/home/emsuser/BLU_suite/venv/bin/gunicorn ems_project.wsgi:application -c /home/emsuser/BLU_suite/gunicorn_config.py
directory=/home/emsuser/BLU_suite
user=emsuser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/emsuser/BLU_suite/logs/supervisor.log
environment=PATH="/home/emsuser/BLU_suite/venv/bin"
EOF

supervisorctl reread
supervisorctl update
supervisorctl start ems_gunicorn

echo ""
echo -e "${GREEN}Step 13: Configuring Nginx...${NC}"
cat > /etc/nginx/sites-available/ems <<'EOF'
upstream ems_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name 104.248.21.180;

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
        
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/ems /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo ""
echo -e "${GREEN}Step 14: Configuring firewall...${NC}"
ufw --force enable
ufw allow OpenSSH
ufw allow 'Nginx Full'

echo ""
echo -e "${GREEN}Step 15: Starting services...${NC}"
systemctl enable nginx
systemctl enable supervisor
systemctl enable postgresql
systemctl enable redis-server

systemctl start nginx
systemctl start supervisor
systemctl start postgresql
systemctl start redis-server

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo -e "${YELLOW}Your EMS application is now running at:${NC}"
echo -e "${GREEN}http://104.248.21.180${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Create superuser:"
echo "   su - emsuser"
echo "   cd /home/emsuser/BLU_suite"
echo "   source venv/bin/activate"
echo "   python manage.py createsuperuser"
echo ""
echo "2. Access admin panel: http://104.248.21.180/admin/"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "- Check status: supervisorctl status"
echo "- View logs: tail -f /home/emsuser/BLU_suite/logs/gunicorn_error.log"
echo "- Restart app: supervisorctl restart ems_gunicorn"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- Update SECRET_KEY in /home/emsuser/BLU_suite/.env"
echo "- Configure email settings in .env"
echo "- Setup SSL certificate (optional): certbot --nginx"
echo ""
