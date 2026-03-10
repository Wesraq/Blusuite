#!/bin/bash
# Cron script for BluSuite system monitoring
# Add to crontab: */5 * * * * /opt/blusuite/scripts/cron_monitoring.sh

cd /opt/blusuite
source venv/bin/activate

# Collect metrics every 5 minutes
python manage.py collect_metrics --settings=ems_project.settings_production >> /var/log/blusuite/monitoring.log 2>&1

# Weekly cleanup (runs on Sundays at midnight)
if [ $(date +%u) -eq 7 ] && [ $(date +%H) -eq 0 ]; then
    python manage.py collect_metrics --cleanup --settings=ems_project.settings_production >> /var/log/blusuite/monitoring.log 2>&1
fi

deactivate
