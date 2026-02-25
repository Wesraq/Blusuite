"""
Script to fix all inline imports in frontend_views.py
"""
import re

# Read the file
with open('ems_project/frontend_views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define replacements for inline imports
replacements = [
    (r'from accounts\.models import', 'from blu_staff.apps.accounts.models import'),
    (r'from accounts\.forms import', 'from blu_staff.apps.accounts.forms import'),
    (r'from accounts\.integration_models import', 'from blu_staff.apps.accounts.integration_models import'),
    (r'from accounts import', 'from blu_staff.apps.accounts import'),
    (r'from attendance\.models import', 'from blu_staff.apps.attendance.models import'),
    (r'from attendance import', 'from blu_staff.apps.attendance import'),
    (r'from leave\.models import', 'from blu_staff.apps.attendance.models import'),
    (r'from documents\.models import', 'from blu_staff.apps.documents.models import'),
    (r'from documents import', 'from blu_staff.apps.documents import'),
    (r'from payroll\.models import', 'from blu_staff.apps.payroll.models import'),
    (r'from payroll\.forms import', 'from blu_staff.apps.payroll.forms import'),
    (r'from payroll import', 'from blu_staff.apps.payroll import'),
    (r'from training\.models import', 'from blu_staff.apps.training.models import'),
    (r'from training\.forms import', 'from blu_staff.apps.training.forms import'),
    (r'from training import', 'from blu_staff.apps.training import'),
    (r'from communication\.models import', 'from blu_staff.apps.communication.models import'),
    (r'from communication import', 'from blu_staff.apps.communication import'),
    (r'from requests\.models import', 'from blu_staff.apps.requests.models import'),
    (r'from onboarding\.models import', 'from blu_staff.apps.onboarding.models import'),
    (r'from onboarding import', 'from blu_staff.apps.onboarding import'),
    (r'from eforms\.models import', 'from blu_staff.apps.eforms.models import'),
    (r'from eforms import', 'from blu_staff.apps.eforms import'),
]

# Apply replacements
original_content = content
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Write back
if content != original_content:
    with open('ems_project/frontend_views.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed all inline imports in frontend_views.py')
    
    # Count changes
    changes = sum(1 for p, r in replacements if re.search(p, original_content))
    print(f'Applied {changes} different import pattern fixes')
else:
    print('No changes needed')
