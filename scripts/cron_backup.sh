#!/bin/bash
# Cron script for automated BluSuite database backups
# Add to crontab: 0 3 * * * /opt/blusuite/scripts/cron_backup.sh

cd /opt/blusuite
/opt/blusuite/scripts/backup_database.sh

# Weekly backup verification (runs on Sundays)
if [ $(date +%u) -eq 7 ]; then
    /opt/blusuite/scripts/verify_backup.sh
fi
