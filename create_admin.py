#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from blu_staff.apps.accounts.models import User

# Create superuser if doesn't exist
if not User.objects.filter(email='admin@blusuite.com').exists():
    user = User.objects.create_superuser(
        email='admin@blusuite.com',
        password='admin123',
        first_name='Admin',
        last_name='User',
        role='ADMINISTRATOR'
    )
    print('Superuser created successfully!')
    print('Email: admin@blusuite.com')
    print('Password: admin123')
    print('IMPORTANT: Change this password after first login!')
else:
    print('Superuser already exists')
