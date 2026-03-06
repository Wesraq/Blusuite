#!/bin/bash
# ============================================================
# BLU Suite - Server Deployment Script (From Local Package)
# ============================================================
# Run this script ON THE SERVER after uploading the deployment package
# Usage: sudo bash deploy_from_local.sh

set -e

echo "========================================"
echo "BLU Suite - Server Deployment"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run as root (use sudo)"
    exit 1
fi

# Configuration
APP_USER="blusuite"
APP_DIR="/opt/blusuite"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="/var/log/gunicorn"
RUN_DIR="/run/gunicorn"

echo "Configuration:"
echo "  App User: $APP_USER"
echo "  App Directory: $APP_DIR"
echo "  Virtual Environment: $VENV_DIR"
echo ""

# Step 1: System packages
echo "[1/10] Installing system packages..."
apt update
apt install -y python3.11 python3.11-venv python3-pip nginx git libpq-dev build-essential curl

# Step 2: Create app user if doesn't exist
echo "[2/10] Setting up application user..."
if ! id "$APP_USER" &>/dev/null; then
    adduser --system --group --home "$APP_DIR" "$APP_USER"
    echo "  ✓ User $APP_USER created"
else
    echo "  ✓ User $APP_USER already exists"
fi

# Step 3: Create directories
echo "[3/10] Creating directories..."
mkdir -p "$APP_DIR" "$LOG_DIR" "$RUN_DIR"
mkdir -p "$APP_DIR/media" "$APP_DIR/staticfiles" "$APP_DIR/logs"
chown -R "$APP_USER:$APP_USER" "$APP_DIR" "$LOG_DIR" "$RUN_DIR"

# Step 4: Check if deployment package exists
echo "[4/10] Checking for deployment package..."
PACKAGE_FILE=$(find /tmp -name "blusuite_deploy_*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -f2- -d" ")

if [ -z "$PACKAGE_FILE" ]; then
    echo "ERROR: No deployment package found in /tmp/"
    echo "Please upload your package first:"
    echo "  scp blusuite_deploy_*.tar.gz root@YOUR_SERVER_IP:/tmp/"
    exit 1
fi

echo "  Found package: $PACKAGE_FILE"

# Step 5: Extract package
echo "[5/10] Extracting deployment package..."
cd "$APP_DIR"
tar -xzf "$PACKAGE_FILE" --strip-components=1
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
echo "  ✓ Package extracted to $APP_DIR"

# Step 6: Setup Python virtual environment
echo "[6/10] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    sudo -u "$APP_USER" python3.11 -m venv "$VENV_DIR"
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
echo "  ✓ Python packages installed"

# Step 7: Setup environment file
echo "[7/10] Setting up environment file..."
if [ ! -f "$APP_DIR/.env" ]; then
    if [ -f "$APP_DIR/.env.production.example" ]; then
        cp "$APP_DIR/.env.production.example" "$APP_DIR/.env"
        chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
        chmod 600 "$APP_DIR/.env"
        echo "  ⚠ .env file created from example - YOU MUST EDIT IT!"
        echo "  Edit: nano $APP_DIR/.env"
    else
        echo "  ⚠ WARNING: No .env file found. You need to create one!"
    fi
else
    echo "  ✓ .env file already exists"
fi

# Step 8: Django setup
echo "[8/10] Running Django setup..."
echo "  Note: You may need to run these manually after configuring .env:"
echo "    sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/manage.py migrate"
echo "    sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/manage.py collectstatic --noinput"
echo "    sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/manage.py createsuperuser"

# Step 9: Setup systemd service
echo "[9/10] Setting up systemd service..."
if [ -f "$APP_DIR/blusuite.service" ]; then
    cp "$APP_DIR/blusuite.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable blusuite
    echo "  ✓ Systemd service configured"
    echo "  Note: Start service after configuring .env with: systemctl start blusuite"
else
    echo "  ⚠ WARNING: blusuite.service file not found"
fi

# Create tmpfiles.d config for /run/gunicorn
echo "d /run/gunicorn 0755 $APP_USER $APP_USER -" > /etc/tmpfiles.d/blusuite.conf
echo "  ✓ tmpfiles.d configured"

# Step 10: Setup Nginx
echo "[10/10] Setting up Nginx..."
if [ -f "$APP_DIR/nginx/conf.d/blusuite.conf" ]; then
    cp "$APP_DIR/nginx/conf.d/blusuite.conf" /etc/nginx/conf.d/
    nginx -t
    systemctl enable nginx
    echo "  ✓ Nginx configured"
    echo "  Note: Restart nginx after configuring .env with: systemctl restart nginx"
else
    echo "  ⚠ WARNING: Nginx config file not found"
fi

# Summary
echo ""
echo "========================================"
echo "✓ DEPLOYMENT SETUP COMPLETED"
echo "========================================"
echo ""
echo "IMPORTANT - Next Steps:"
echo ""
echo "1. Configure your .env file:"
echo "   nano $APP_DIR/.env"
echo ""
echo "2. Generate a new SECRET_KEY:"
echo "   sudo -u $APP_USER $VENV_DIR/bin/python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
echo ""
echo "3. Run Django migrations:"
echo "   sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/manage.py migrate"
echo ""
echo "4. Collect static files:"
echo "   sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/manage.py collectstatic --noinput"
echo ""
echo "5. Create superuser:"
echo "   sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/manage.py createsuperuser"
echo ""
echo "6. Start the application:"
echo "   systemctl start blusuite"
echo "   systemctl status blusuite"
echo ""
echo "7. Restart Nginx:"
echo "   systemctl restart nginx"
echo ""
echo "8. Setup firewall:"
echo "   ufw allow OpenSSH"
echo "   ufw allow 'Nginx Full'"
echo "   ufw enable"
echo ""
echo "9. Check logs if needed:"
echo "   journalctl -u blusuite -f"
echo "   tail -f $LOG_DIR/error.log"
echo ""
