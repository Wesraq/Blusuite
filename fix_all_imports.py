import os
import re

# Define the import replacements
replacements = [
    (r'^from accounts\.models import', 'from blu_staff.apps.accounts.models import'),
    (r'^from accounts\.forms import', 'from blu_staff.apps.accounts.forms import'),
    (r'^from accounts\.integration_models import', 'from blu_staff.apps.accounts.integration_models import'),
    (r'^from attendance\.models import', 'from blu_staff.apps.attendance.models import'),
    (r'^from documents\.models import', 'from blu_staff.apps.documents.models import'),
    (r'^from payroll\.models import', 'from blu_staff.apps.payroll.models import'),
    (r'^from payroll\.forms import', 'from blu_staff.apps.payroll.forms import'),
    (r'^from training\.models import', 'from blu_staff.apps.training.models import'),
    (r'^from training\.forms import', 'from blu_staff.apps.training.forms import'),
    (r'^from onboarding\.models import', 'from blu_staff.apps.onboarding.models import'),
    (r'^from onboarding\.forms import', 'from blu_staff.apps.onboarding.forms import'),
    (r'^from notifications\.models import', 'from blu_staff.apps.notifications.models import'),
    (r'^from requests\.models import', 'from blu_staff.apps.requests.models import'),
    (r'^from communication\.models import', 'from blu_staff.apps.communication.models import'),
    (r'^from eforms\.models import', 'from blu_staff.apps.eforms.models import'),
]

def fix_file(filepath):
    """Fix imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            new_line = line
            for pattern, replacement in replacements:
                if re.match(pattern, line):
                    new_line = re.sub(pattern, replacement, line)
                    break
            new_lines.append(new_line)
        
        new_content = '\n'.join(new_lines)
        
        if new_content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

# Walk through the project and fix all Python files
fixed_count = 0
for root, dirs, files in os.walk('.'):
    # Skip venv and migrations
    if 'venv' in root or 'migrations' in root or '__pycache__' in root or 'node_modules' in root:
        continue
    
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            if fix_file(filepath):
                print(f'Fixed: {filepath}')
                fixed_count += 1

print(f'\nTotal files fixed: {fixed_count}')
