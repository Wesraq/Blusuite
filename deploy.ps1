# BLU Suite EMS - Deployment Script for Windows
# This script helps prepare your application for deployment

Write-Host "======================================" -ForegroundColor Green
Write-Host "BLU Suite EMS - Deployment Preparation" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""

# Check if .env.production exists
if (-not (Test-Path ".env.production")) {
    Write-Host "Creating .env.production from example..." -ForegroundColor Yellow
    Copy-Item ".env.production.example" ".env.production"
    Write-Host "✓ Created .env.production" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Edit .env.production and update:" -ForegroundColor Red
    Write-Host "   - SECRET_KEY (generate a new one)" -ForegroundColor Red
    Write-Host "   - ALLOWED_HOSTS (add your server IP)" -ForegroundColor Red
    Write-Host "   - DB_PASSWORD (set a secure password)" -ForegroundColor Red
    Write-Host "   - DATABASE_URL (update with your password)" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter after you've updated .env.production"
} else {
    Write-Host "✓ .env.production already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "Checking Docker installation..." -ForegroundColor Blue
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed" -ForegroundColor Red
    Write-Host "Please install Docker Desktop for Windows: https://docs.docker.com/desktop/windows/install/" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker is installed" -ForegroundColor Green

if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker Compose is not installed" -ForegroundColor Red
    Write-Host "Please install Docker Compose" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker Compose is installed" -ForegroundColor Green

Write-Host ""
Write-Host "Building Docker images..." -ForegroundColor Blue
docker-compose build

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Docker images built successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to build Docker images" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Blue
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Services started successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to start services" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Waiting for database to be ready..." -ForegroundColor Blue
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "Running database migrations..." -ForegroundColor Blue
docker-compose exec -T web python manage.py migrate

Write-Host ""
Write-Host "Collecting static files..." -ForegroundColor Blue
docker-compose exec -T web python manage.py collectstatic --noinput

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your application should be running at:" -ForegroundColor Cyan
Write-Host "http://localhost (if running locally)" -ForegroundColor Cyan
Write-Host "http://YOUR_SERVER_IP (if deployed)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Create a superuser: docker-compose exec web python manage.py createsuperuser" -ForegroundColor White
Write-Host "2. Access admin panel: http://YOUR_IP/admin" -ForegroundColor White
Write-Host "3. Create your first company/tenant" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "- View logs: docker-compose logs -f web" -ForegroundColor White
Write-Host "- Stop services: docker-compose down" -ForegroundColor White
Write-Host "- Restart services: docker-compose restart" -ForegroundColor White
Write-Host ""
