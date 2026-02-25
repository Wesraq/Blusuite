# Quick Deployment to DigitalOcean - EMS Suite

**Your Droplet:** `104.248.21.180` (Frankfurt - FRA1)

---

## Option 1: Quick Deploy (Recommended for Testing)

### Step 1: Upload Your Code

From your local machine (Windows):

```powershell
# Using SCP (install Git Bash or use WSL)
scp -r d:\projects\BLU_suite root@104.248.21.180:/root/

# Or use WinSCP (GUI tool) to upload the folder
```

### Step 2: SSH into Your Droplet

```bash
ssh root@104.248.21.180
```

### Step 3: Run Quick Setup Script

```bash
cd /root/BLU_suite

# Make script executable
chmod +x quick_setup.sh

# Run setup
./quick_setup.sh
```

This will:
- Install all dependencies
- Setup PostgreSQL database
- Create virtual environment
- Run migrations
- Collect static files
- Setup Nginx and Gunicorn
- Start the application

### Step 4: Access Your Application

Open browser: `http://104.248.21.180`

---

## Option 2: Manual Deployment

Follow the comprehensive guide in `DEPLOYMENT_GUIDE.md`

---

## Post-Deployment Tasks

### 1. Create Superuser
```bash
ssh root@104.248.21.180
su - emsuser
cd /home/emsuser/BLU_suite
source venv/bin/activate
python manage.py createsuperuser
```

### 2. Access Admin Panel
`http://104.248.21.180/admin/`

### 3. Create First Company
Login and create your first company/tenant

---

## Important Files to Update Before Deployment

1. **`.env`** - Update these values:
   - `SECRET_KEY` - Generate new: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
   - `DEBUG=False`
   - `ALLOWED_HOSTS=104.248.21.180,yourdomain.com`
   - `DATABASE_URL` - Update password

2. **`requirements.txt`** - Already configured ✓

3. **`settings.py`** - Already configured for production ✓

---

## Monitoring

### Check Application Status
```bash
ssh root@104.248.21.180
supervisorctl status
```

### View Logs
```bash
# Application logs
tail -f /home/emsuser/BLU_suite/logs/gunicorn_error.log

# Nginx logs
tail -f /var/log/nginx/error.log
```

### Restart Application
```bash
supervisorctl restart ems_gunicorn
```

---

## Troubleshooting

### Application not accessible
1. Check firewall: `ufw status`
2. Check Nginx: `systemctl status nginx`
3. Check Gunicorn: `supervisorctl status ems_gunicorn`

### Database errors
1. Check PostgreSQL: `systemctl status postgresql`
2. Verify credentials in `.env`

### 502 Bad Gateway
1. Check Gunicorn logs: `tail -f /home/emsuser/BLU_suite/logs/gunicorn_error.log`
2. Restart services: `supervisorctl restart all`

---

## Next Steps

1. ✅ Deploy application
2. ⬜ Setup domain name (optional)
3. ⬜ Configure SSL certificate
4. ⬜ Setup automated backups
5. ⬜ Configure email settings
6. ⬜ Test all functionality

---

**Need Help?** Check `DEPLOYMENT_GUIDE.md` for detailed instructions.
