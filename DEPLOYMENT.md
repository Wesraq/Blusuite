# BLU Suite EMS - Digital Ocean Deployment Guide

This guide will help you deploy the BLU Suite EMS application to Digital Ocean using Docker and Docker Compose.

## Prerequisites

- Digital Ocean account
- A droplet with at least 2GB RAM (recommended: 4GB RAM, 2 vCPUs)
- SSH access to your droplet
- Git installed on your droplet

## Step 1: Create a Digital Ocean Droplet

1. Log in to your Digital Ocean account
2. Click "Create" → "Droplets"
3. Choose an image: **Ubuntu 22.04 LTS**
4. Choose a plan: **Basic** (Recommended: $24/month - 4GB RAM, 2 vCPUs, 80GB SSD)
5. Choose a datacenter region (closest to your users)
6. Add your SSH key or use password authentication
7. Choose a hostname (e.g., `blusuite-production`)
8. Click "Create Droplet"
9. Note your droplet's IP address (e.g., `123.45.67.89`)

## Step 2: Connect to Your Droplet

```bash
ssh root@YOUR_DROPLET_IP
```

## Step 3: Install Docker and Docker Compose

```bash
# Update package list
apt update && apt upgrade -y

# Install required packages
apt install -y apt-transport-https ca-certificates curl software-properties-common git

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version
```

## Step 4: Clone Your Repository

```bash
# Create application directory
mkdir -p /var/www
cd /var/www

# Clone your repository (replace with your actual repository URL)
git clone https://github.com/YOUR_USERNAME/BLU_suite.git
cd BLU_suite
```

**OR** if you're uploading files manually:

```bash
# On your local machine, create a tar archive
cd d:\2025\systems\BLU_suite
tar -czf blusuite.tar.gz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' --exclude='staticfiles' --exclude='media' .

# Upload to droplet
scp blusuite.tar.gz root@YOUR_DROPLET_IP:/var/www/

# On droplet, extract
cd /var/www
mkdir BLU_suite
tar -xzf blusuite.tar.gz -C BLU_suite
cd BLU_suite
```

## Step 5: Configure Environment Variables

```bash
# Copy the example environment file
cp .env.production.example .env.production

# Edit the environment file
nano .env.production
```

**Important configurations to update:**

```bash
# Generate a new secret key (run this command to generate one)
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Update these values in .env.production:
SECRET_KEY=your-generated-secret-key-from-above
DEBUG=False
ALLOWED_HOSTS=YOUR_DROPLET_IP,localhost,127.0.0.1

# Database credentials (change these!)
DB_PASSWORD=your-very-secure-password-here

# Update database URL with the same password
DATABASE_URL=postgresql://blusuite_user:your-very-secure-password-here@db:5432/blusuite_db
```

Save and exit (Ctrl+X, then Y, then Enter)

## Step 6: Build and Start the Application

```bash
# Build Docker images
docker-compose build

# Start all services
docker-compose up -d

# Check if containers are running
docker-compose ps
```

You should see 4 services running:
- `db` (PostgreSQL)
- `redis` (Redis)
- `web` (Django application)
- `nginx` (Web server)

## Step 7: Initialize the Database

```bash
# Run database migrations
docker-compose exec web python manage.py migrate

# Create a superuser account
docker-compose exec web python manage.py createsuperuser

# Collect static files (if not done automatically)
docker-compose exec web python manage.py collectstatic --noinput
```

## Step 8: Configure Firewall

```bash
# Enable UFW firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Check firewall status
ufw status
```

## Step 9: Access Your Application

Open your browser and navigate to:
```
http://YOUR_DROPLET_IP
```

You should see the BLU Suite EMS login page!

**Admin panel:**
```
http://YOUR_DROPLET_IP/admin
```

## Step 10: Create Your First Tenant/Company

1. Log in to the admin panel with your superuser credentials
2. Navigate to "Tenant Management" → "Companies"
3. Click "Add Company"
4. Fill in the company details
5. Save

## Monitoring and Maintenance

### View Logs

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs web
docker-compose logs nginx
docker-compose logs db

# Follow logs in real-time
docker-compose logs -f web
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart web
docker-compose restart nginx
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: This deletes database data!)
docker-compose down -v
```

### Update Application

```bash
cd /var/www/BLU_suite

# Pull latest changes (if using Git)
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
```

### Backup Database

```bash
# Create backup directory
mkdir -p /var/backups/blusuite

# Backup database
docker-compose exec db pg_dump -U blusuite_user blusuite_db > /var/backups/blusuite/backup_$(date +%Y%m%d_%H%M%S).sql

# Backup media files
tar -czf /var/backups/blusuite/media_$(date +%Y%m%d_%H%M%S).tar.gz media/
```

### Restore Database

```bash
# Restore from backup
docker-compose exec -T db psql -U blusuite_user blusuite_db < /var/backups/blusuite/backup_YYYYMMDD_HHMMSS.sql
```

## Adding a Domain Name (When Ready)

When you get a domain name, follow these steps:

### 1. Point Domain to Droplet

In your domain registrar's DNS settings:
- Add an **A Record** pointing to your droplet's IP address
- Example: `blusuite.com` → `YOUR_DROPLET_IP`
- Add a **CNAME Record** for `www` pointing to your domain
- Example: `www.blusuite.com` → `blusuite.com`

### 2. Update Configuration

```bash
# Update .env.production
nano .env.production

# Change ALLOWED_HOSTS to include your domain
ALLOWED_HOSTS=YOUR_DROPLET_IP,localhost,127.0.0.1,blusuite.com,www.blusuite.com
```

### 3. Update Nginx Configuration

```bash
# Edit nginx config
nano nginx/conf.d/blusuite.conf

# Change server_name from _ to your domain
server_name blusuite.com www.blusuite.com;
```

### 4. Install SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
apt install -y certbot python3-certbot-nginx

# Stop nginx container temporarily
docker-compose stop nginx

# Get SSL certificate
certbot certonly --standalone -d blusuite.com -d www.blusuite.com

# Certificates will be in /etc/letsencrypt/live/blusuite.com/

# Update docker-compose.yml to mount certificates
# Add to nginx volumes:
#   - /etc/letsencrypt:/etc/letsencrypt:ro

# Restart services
docker-compose up -d

# Enable HTTPS in .env.production
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
```

## Troubleshooting

### Application won't start

```bash
# Check logs
docker-compose logs web

# Common issues:
# 1. Database not ready - wait a few seconds and try again
# 2. Port already in use - check with: netstat -tulpn | grep :80
# 3. Permission issues - check file ownership
```

### Can't connect to database

```bash
# Check if database is running
docker-compose ps db

# Check database logs
docker-compose logs db

# Verify database credentials in .env.production
```

### Static files not loading

```bash
# Collect static files again
docker-compose exec web python manage.py collectstatic --noinput

# Check nginx logs
docker-compose logs nginx

# Verify static files volume is mounted correctly
docker-compose exec nginx ls -la /app/staticfiles/
```

### Out of memory

```bash
# Check memory usage
free -h

# Check Docker container memory
docker stats

# Consider upgrading droplet or optimizing worker count in docker-compose.yml
```

## Performance Optimization

### Enable Redis Caching

Already configured in docker-compose.yml. Redis is used for:
- Session storage
- Cache backend
- Celery task queue

### Database Optimization

```bash
# Access PostgreSQL
docker-compose exec db psql -U blusuite_user blusuite_db

# Run VACUUM to optimize
VACUUM ANALYZE;
```

### Monitor Resource Usage

```bash
# Install monitoring tools
apt install -y htop

# Monitor in real-time
htop

# Check disk usage
df -h

# Check Docker disk usage
docker system df
```

## Security Best Practices

1. **Change default passwords** - Update all passwords in .env.production
2. **Keep system updated** - Run `apt update && apt upgrade` regularly
3. **Enable firewall** - Only allow necessary ports (22, 80, 443)
4. **Use SSH keys** - Disable password authentication
5. **Regular backups** - Set up automated daily backups
6. **Monitor logs** - Check logs regularly for suspicious activity
7. **SSL/TLS** - Always use HTTPS in production (add domain first)
8. **Update dependencies** - Keep Python packages and Docker images updated

## Support

For issues or questions:
- Check application logs: `docker-compose logs web`
- Check nginx logs: `docker-compose logs nginx`
- Check database logs: `docker-compose logs db`
- Review Django error pages (if DEBUG=True temporarily)

## Quick Reference Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f web

# Run Django management commands
docker-compose exec web python manage.py <command>

# Access Django shell
docker-compose exec web python manage.py shell

# Access database
docker-compose exec db psql -U blusuite_user blusuite_db

# Restart a service
docker-compose restart web

# Rebuild after code changes
docker-compose down && docker-compose build && docker-compose up -d
```

---

**Your application should now be running at:** `http://YOUR_DROPLET_IP`

**Next steps:**
1. Create your first company/tenant
2. Add employees
3. Configure email settings (optional)
4. Set up automated backups
5. Add a domain name and SSL certificate
