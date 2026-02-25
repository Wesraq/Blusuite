#!/bin/bash

# BLU Suite EMS - Automated Droplet Setup Script
# Run this script on your Digital Ocean droplet

set -e  # Exit on error

echo "=========================================="
echo "BLU Suite EMS - Automated Deployment"
echo "=========================================="
echo ""

# Update system
echo "Step 1/8: Updating system packages..."
apt update && apt upgrade -y

# Install Docker
echo ""
echo "Step 2/8: Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo "✓ Docker installed"
else
    echo "✓ Docker already installed"
fi

# Install Docker Compose
echo ""
echo "Step 3/8: Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✓ Docker Compose installed"
else
    echo "✓ Docker Compose already installed"
fi

# Verify installations
docker --version
docker-compose --version

# Create application directory
echo ""
echo "Step 4/8: Creating application directory..."
mkdir -p /var/www/BLU_suite
cd /var/www/BLU_suite
echo "✓ Directory created: /var/www/BLU_suite"

# Configure firewall
echo ""
echo "Step 5/8: Configuring firewall..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable
echo "✓ Firewall configured"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Upload your application files to: /var/www/BLU_suite"
echo "2. Configure .env.production file"
echo "3. Run: docker-compose build && docker-compose up -d"
echo ""
echo "Ready for application upload!"
