#!/bin/bash
# Cron script for BluSuite billing automation
# Add to crontab: 0 2 * * * /opt/blusuite/blu_billing/cron_billing.sh

cd /opt/blusuite
source venv/bin/activate

# Run billing automation daily at 2 AM
python manage.py run_billing_automation --settings=ems_project.settings_production >> /var/log/blusuite/billing_automation.log 2>&1

# Deactivate virtual environment
deactivate
