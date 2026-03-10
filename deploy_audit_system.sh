#!/bin/bash
# Deploy BLU Suite Audit System, RBAC, and Tenant Isolation fixes
# Run from: root@161.35.192.144

set -e

SERVER_ROOT="/opt/blusuite"
VENV="$SERVER_ROOT/venv/bin/python"
MANAGE="$VENV $SERVER_ROOT/manage.py"
SETTINGS="ems_project.settings_production"

echo "=== BLU Suite Security Audit Deployment ==="

# 1. Apply migrations
echo "[1/4] Running migrations..."
cd $SERVER_ROOT
$MANAGE migrate blu_core --settings=$SETTINGS

# 2. Collect static
echo "[2/4] Collecting static files..."
$MANAGE collectstatic --noinput --settings=$SETTINGS

# 3. Verify audit log model is accessible
echo "[3/4] Verifying AuditLog model..."
$VENV -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = '$SETTINGS'
import sys; sys.path.insert(0, '$SERVER_ROOT')
django.setup()
from blu_core.audit import AuditLog
count = AuditLog.objects.count()
print(f'  AuditLog table OK — {count} records')
"

# 4. Restart service
echo "[4/4] Restarting blusuite service..."
systemctl restart blusuite
sleep 5
systemctl status blusuite | grep -E "Active:|Main PID"

echo ""
echo "=== Deployment Complete ==="
echo "Audit log available at: https://161.35.192.144/audit-log/"
