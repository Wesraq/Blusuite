#!/bin/bash

# BLU Suite EMS - Complete Deployment Script
# Run this on your Digital Ocean droplet

set -e

echo "=========================================="
echo "BLU Suite EMS - Deployment"
echo "=========================================="

cd /var/www/BLU_suite

# Stop and remove everything
echo "Cleaning up old containers..."
docker-compose down -v 2>/dev/null || true

# Create fresh .env.production with matching passwords
echo "Creating environment configuration..."
cat > .env.production << 'EOF'
# Django Settings
SECRET_KEY=q6xKzf2C_IrJuTRNc-OiY6ZXyKdLzEJY-CmBBOxRnQnA_RSfV-dXk1mwY3dNySVBGbw
DEBUG=False
ALLOWED_HOSTS=209.38.225.139,localhost,127.0.0.1

# Database Configuration
DB_NAME=blusuite_db
DB_USER=blusuite_user
DB_PASSWORD=BLU_Suite_Secure_2026!
DB_HOST=db
DB_PORT=5432
DATABASE_URL=postgresql://blusuite_user:BLU_Suite_Secure_2026!@db:5432/blusuite_db

# Redis
REDIS_URL=redis://redis:6379/0

# Email (Console for now)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Security
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
EOF

echo "Starting services..."
docker-compose up -d

echo "Waiting for database to be ready..."
sleep 15

echo "Running migrations..."
docker-compose exec -T web python manage.py migrate --noinput

echo "Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Your application is running at:"
echo "http://209.38.225.139"
echo ""
echo "Next step: Create superuser"
echo "Run: docker-compose exec web python manage.py createsuperuser"
echo ""
