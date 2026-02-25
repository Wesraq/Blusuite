#!/bin/bash

# BLU Suite EMS - Complete Automated Deployment Script
# This script will set up everything on your Digital Ocean droplet

set -e

echo "=========================================="
echo "BLU Suite EMS - Complete Deployment"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use: sudo bash auto_deploy.sh)"
    exit 1
fi

# Update system
echo "Step 1/10: Updating system..."
apt update && apt upgrade -y

# Install required packages
echo ""
echo "Step 2/10: Installing required packages..."
apt install -y curl wget git nano ufw netcat-openbsd

# Install Docker
echo ""
echo "Step 3/10: Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
    echo "✓ Docker installed and started"
else
    echo "✓ Docker already installed"
fi

# Install Docker Compose
echo ""
echo "Step 4/10: Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✓ Docker Compose installed"
else
    echo "✓ Docker Compose already installed"
fi

# Verify installations
echo ""
echo "Verifying installations..."
docker --version
docker-compose --version

# Create application directory
echo ""
echo "Step 5/10: Creating application directory..."
mkdir -p /var/www/BLU_suite
cd /var/www/BLU_suite
echo "✓ Created: /var/www/BLU_suite"

# Configure firewall
echo ""
echo "Step 6/10: Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
echo "✓ Firewall configured and enabled"

echo ""
echo "=========================================="
echo "Initial Setup Complete!"
echo "=========================================="
echo ""
echo "Current directory: /var/www/BLU_suite"
echo ""
echo "Next: Upload your application files here"
echo "Then run the deployment commands"
echo ""
