#!/bin/bash

# BLU Suite EMS - Quick Deployment Script for Digital Ocean
# This script helps prepare your application for deployment

echo "======================================"
echo "BLU Suite EMS - Deployment Preparation"
echo "======================================"
echo ""

# Check if .env.production exists
if [ ! -f .env.production ]; then
    echo "Creating .env.production from example..."
    cp .env.production.example .env.production
    echo "✓ Created .env.production"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env.production and update:"
    echo "   - SECRET_KEY (generate a new one)"
    echo "   - ALLOWED_HOSTS (add your droplet IP)"
    echo "   - DB_PASSWORD (set a secure password)"
    echo "   - DATABASE_URL (update with your password)"
    echo ""
    read -p "Press Enter after you've updated .env.production..."
else
    echo "✓ .env.production already exists"
fi

echo ""
echo "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "Please install Docker first: https://docs.docker.com/engine/install/"
    exit 1
fi
echo "✓ Docker is installed"

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    echo "Please install Docker Compose first"
    exit 1
fi
echo "✓ Docker Compose is installed"

echo ""
echo "Building Docker images..."
docker-compose build

if [ $? -eq 0 ]; then
    echo "✓ Docker images built successfully"
else
    echo "❌ Failed to build Docker images"
    exit 1
fi

echo ""
echo "Starting services..."
docker-compose up -d

if [ $? -eq 0 ]; then
    echo "✓ Services started successfully"
else
    echo "❌ Failed to start services"
    exit 1
fi

echo ""
echo "Waiting for database to be ready..."
sleep 10

echo ""
echo "Running database migrations..."
docker-compose exec -T web python manage.py migrate

echo ""
echo "Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput

echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo ""
echo "Your application should be running at:"
echo "http://localhost (if running locally)"
echo "http://YOUR_DROPLET_IP (if on Digital Ocean)"
echo ""
echo "Next steps:"
echo "1. Create a superuser: docker-compose exec web python manage.py createsuperuser"
echo "2. Access admin panel: http://YOUR_IP/admin"
echo "3. Create your first company/tenant"
echo ""
echo "Useful commands:"
echo "- View logs: docker-compose logs -f web"
echo "- Stop services: docker-compose down"
echo "- Restart services: docker-compose restart"
echo ""
