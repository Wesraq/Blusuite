# BLU Suite EMS - Quick Start Guide (No Domain)

This is a simplified guide for deploying BLU Suite EMS to Digital Ocean **without a domain name**. You'll access the application using your droplet's IP address.

## What You'll Need

- Digital Ocean account
- 15-30 minutes of your time
- Basic command line knowledge

## Step 1: Create Your Droplet (5 minutes)

1. Go to [Digital Ocean](https://cloud.digitalocean.com/)
2. Click **Create** → **Droplets**
3. Select:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic - $24/month (4GB RAM, 2 vCPUs) - Recommended
   - **Region**: Choose closest to you
   - **Authentication**: SSH key (recommended) or Password
   - **Hostname**: `blusuite-prod`
4. Click **Create Droplet**
5. **Copy your droplet's IP address** (e.g., `165.227.123.45`)

## Step 2: Connect to Your Droplet (2 minutes)

Open your terminal/PowerShell and connect:

```bash
ssh root@YOUR_DROPLET_IP
```

Replace `YOUR_DROPLET_IP` with your actual IP address.

## Step 3: Install Docker (5 minutes)

Copy and paste these commands one by one:

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

## Step 4: Upload Your Application (5 minutes)

### Option A: Using Git (if your code is on GitHub/GitLab)

```bash
cd /var/www
git clone YOUR_REPOSITORY_URL BLU_suite
cd BLU_suite
```

### Option B: Upload Files Manually

**On your Windows machine:**

```powershell
# Navigate to your project
cd d:\2025\systems\BLU_suite

# Create archive (install 7-Zip if needed)
tar -czf blusuite.tar.gz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' --exclude='staticfiles' --exclude='media' .

# Upload to droplet (replace YOUR_DROPLET_IP)
scp blusuite.tar.gz root@YOUR_DROPLET_IP:/var/www/
```

**On your droplet:**

```bash
cd /var/www
mkdir BLU_suite
tar -xzf blusuite.tar.gz -C BLU_suite
cd BLU_suite
```

## Step 5: Configure Environment (3 minutes)

```bash
# Copy environment template
cp .env.production.example .env.production

# Generate a secret key
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

**Copy the generated key**, then edit the environment file:

```bash
nano .env.production
```

Update these values:

```bash
SECRET_KEY=paste-your-generated-key-here
DEBUG=False
ALLOWED_HOSTS=YOUR_DROPLET_IP,localhost,127.0.0.1

DB_PASSWORD=YourSecurePassword123!
DATABASE_URL=postgresql://blusuite_user:YourSecurePassword123!@db:5432/blusuite_db
```

**Important**: Replace `YOUR_DROPLET_IP` with your actual IP (e.g., `165.227.123.45`)

Save and exit: `Ctrl+X`, then `Y`, then `Enter`

## Step 6: Deploy! (5 minutes)

```bash
# Build and start all services
docker-compose build
docker-compose up -d

# Wait 30 seconds for services to start
sleep 30

# Run database migrations
docker-compose exec web python manage.py migrate

# Create admin account
docker-compose exec web python manage.py createsuperuser
```

Follow the prompts to create your admin account.

## Step 7: Configure Firewall (2 minutes)

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

## Step 8: Access Your Application! 🎉

Open your browser and go to:

```
http://YOUR_DROPLET_IP
```

**Admin Panel:**
```
http://YOUR_DROPLET_IP/admin
```

## First Time Setup

1. **Log in to admin panel** with your superuser credentials
2. **Create a company/tenant**:
   - Go to "Tenant Management" → "Companies"
   - Click "Add Company"
   - Fill in details and save
3. **Start using BLU Suite!**

## Common Commands

```bash
# View logs
docker-compose logs -f web

# Restart application
docker-compose restart web

# Stop everything
docker-compose down

# Start everything
docker-compose up -d

# Access Django shell
docker-compose exec web python manage.py shell

# Create backup
docker-compose exec db pg_dump -U blusuite_user blusuite_db > backup.sql
```

## Troubleshooting

### Can't access the application?

```bash
# Check if services are running
docker-compose ps

# All services should show "Up"
# If not, check logs:
docker-compose logs web
docker-compose logs nginx
```

### "Bad Gateway" error?

```bash
# Wait a bit longer (services might still be starting)
sleep 30

# Check web service
docker-compose logs web

# Restart if needed
docker-compose restart web
```

### Forgot admin password?

```bash
docker-compose exec web python manage.py changepassword your-username
```

## Next Steps

1. ✅ **Create your first company** in the admin panel
2. ✅ **Add employees** to your company
3. ✅ **Explore the EMS features**
4. 📧 **Configure email** (optional - edit .env.production)
5. 🔒 **Get a domain name** and add SSL (see DEPLOYMENT.md)
6. 💾 **Set up automated backups**

## Getting a Domain Later

When you're ready to add a domain:

1. Buy a domain from any registrar (Namecheap, GoDaddy, etc.)
2. Point domain to your droplet IP (A record)
3. Update `.env.production` with your domain
4. Get free SSL certificate with Let's Encrypt
5. See full instructions in `DEPLOYMENT.md`

## Support

- **View logs**: `docker-compose logs -f web`
- **Check status**: `docker-compose ps`
- **Restart**: `docker-compose restart`

---

**Your BLU Suite EMS is now live at:** `http://YOUR_DROPLET_IP`

Enjoy! 🚀
