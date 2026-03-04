# BLU Suite EMS — Bare-Metal Deployment Guide

**Target:** DigitalOcean Droplet `161.35.79.174` (Ubuntu 24.04 LTS x64, 2 GB RAM, 60 GB SSD)
**Stack:** Nginx → Gunicorn → Django + WhiteNoise · PostgreSQL (Supabase) · Python 3.11+

---

## ⚠️ Before You Start — Rotate Exposed Credentials

The following credentials were previously committed to git and **must be rotated before going live**:

1. **Django SECRET_KEY** — generate a new one:
   ```bash
   python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
2. **Supabase DB Password** — reset in Supabase Dashboard → Settings → Database
3. **Gmail App Password** — revoke at https://myaccount.google.com/apppasswords and create a new one

---

## Step 1 — Connect to the Droplet

```bash
ssh root@161.35.79.174
```

---

## Step 2 — System Setup

```bash
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip nginx git libpq-dev build-essential

# Create app user
adduser --system --group --home /opt/blusuite blusuite
mkdir -p /opt/blusuite /var/log/gunicorn /run/gunicorn
chown blusuite:blusuite /opt/blusuite /var/log/gunicorn /run/gunicorn
```

---

## Step 3 — Deploy Code

```bash
cd /opt/blusuite
git clone https://github.com/Wesraq/Blusuite.git .

# Python virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 4 — Environment File

```bash
cp .env.production.example .env
nano .env   # Fill in all values — see .env.production.example for reference
```

Key values to set:
```
SECRET_KEY=<new 50-char random key>
DEBUG=False
ALLOWED_HOSTS=161.35.79.174,localhost
SITE_URL=http://161.35.79.174
DB_PASSWORD=<new Supabase password>
EMAIL_HOST_PASSWORD=<new Gmail app password>
```

---

## Step 5 — Django Setup

```bash
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

---

## Step 6 — Gunicorn (systemd service)

```bash
# Copy the service file
cp blusuite.service /etc/systemd/system/
# Edit WorkingDirectory / ExecStart paths if needed
systemctl daemon-reload
systemctl enable blusuite
systemctl start blusuite
systemctl status blusuite   # should show "active (running)"
```

Create gunicorn runtime dir on each boot:

```bash
mkdir -p /run/gunicorn
chown blusuite:blusuite /run/gunicorn
# Add to /etc/tmpfiles.d/blusuite.conf:
echo "d /run/gunicorn 0755 blusuite blusuite -" > /etc/tmpfiles.d/blusuite.conf
```

---

## Step 7 — Nginx

```bash
cp nginx/conf.d/blusuite.conf /etc/nginx/conf.d/blusuite.conf
nginx -t          # must print "syntax is ok"
systemctl enable nginx
systemctl restart nginx
```

---

## Step 8 — Firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
ufw status
```

---

## Step 9 — Verify

```bash
curl -I http://161.35.79.174/health/
# Expected: HTTP/1.1 200 OK
```

Open `http://161.35.79.174` in your browser — the BLU Suite login page should load.

---

## Logs

```bash
journalctl -u blusuite -f            # gunicorn app logs
tail -f /var/log/gunicorn/error.log  # gunicorn error log
tail -f /var/log/nginx/error.log     # nginx errors
```

---

## Updates / Redeploy

```bash
cd /opt/blusuite
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart blusuite
```

