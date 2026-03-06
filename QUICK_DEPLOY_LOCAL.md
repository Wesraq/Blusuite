# BLU Suite - Quick Local Deployment Reference

## 🚀 Quick Start (3 Steps)

### Step 1: Create Package (On Your Windows Machine)
```powershell
cd d:\projects\BLU_suite
.\scripts\create_deployment_package.ps1
```

### Step 2: Upload to Server
```powershell
scp blusuite_deploy_*.tar.gz root@YOUR_SERVER_IP:/tmp/
```

### Step 3: Deploy on Server
```bash
ssh root@YOUR_SERVER_IP
cd /tmp
tar -xzf blusuite_deploy_*.tar.gz
cd blusuite_deploy_*/scripts
chmod +x deploy_from_local.sh
sudo bash deploy_from_local.sh
```

---

## 📋 Post-Deployment Checklist

After the deployment script completes, run these commands **on the server**:

### 1. Configure Environment
```bash
nano /opt/blusuite/.env
```
Update: `SECRET_KEY`, `ALLOWED_HOSTS`, `DB_PASSWORD`, `EMAIL_HOST_PASSWORD`

### 2. Generate SECRET_KEY
```bash
sudo -u blusuite /opt/blusuite/venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3. Run Migrations
```bash
sudo -u blusuite /opt/blusuite/venv/bin/python /opt/blusuite/manage.py migrate
```

### 4. Collect Static Files
```bash
sudo -u blusuite /opt/blusuite/venv/bin/python /opt/blusuite/manage.py collectstatic --noinput
```

### 5. Create Superuser
```bash
sudo -u blusuite /opt/blusuite/venv/bin/python /opt/blusuite/manage.py createsuperuser
```

### 6. Start Services
```bash
mkdir -p /run/gunicorn
chown blusuite:blusuite /run/gunicorn
systemctl start blusuite
systemctl restart nginx
```

### 7. Setup Firewall
```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

### 8. Verify
```bash
curl -I http://localhost/health/
systemctl status blusuite
```

---

## 🔄 Quick Update Process

### On Local Machine:
```powershell
.\scripts\create_deployment_package.ps1
scp blusuite_deploy_*.tar.gz root@YOUR_SERVER_IP:/tmp/
```

### On Server:
```bash
cd /opt/blusuite
sudo -u blusuite tar -czf /opt/blusuite_backup_$(date +%Y%m%d).tar.gz .
tar -xzf /tmp/blusuite_deploy_*.tar.gz --strip-components=1
chown -R blusuite:blusuite /opt/blusuite
sudo -u blusuite /opt/blusuite/venv/bin/pip install -r requirements.txt
sudo -u blusuite /opt/blusuite/venv/bin/python manage.py migrate
sudo -u blusuite /opt/blusuite/venv/bin/python manage.py collectstatic --noinput
systemctl restart blusuite
```

---

## 🔍 Troubleshooting Quick Commands

### Check Status
```bash
systemctl status blusuite
systemctl status nginx
```

### View Logs
```bash
journalctl -u blusuite -n 50
tail -f /var/log/gunicorn/error.log
tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
systemctl restart blusuite
systemctl restart nginx
```

---

## 📁 Important Locations

| Item | Path |
|------|------|
| App Directory | `/opt/blusuite/` |
| Environment File | `/opt/blusuite/.env` |
| Logs | `/var/log/gunicorn/` |
| Service File | `/etc/systemd/system/blusuite.service` |

---

For detailed instructions, see `DEPLOYMENT_FROM_LOCAL.md`
