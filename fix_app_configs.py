import os

apps_to_fix = [
    'attendance',
    'documents', 
    'payroll',
    'training',
    'onboarding',
    'notifications',
    'requests',
    'communication',
    'eforms'
]

for app in apps_to_fix:
    app_config_path = f'blu_staff/apps/{app}/apps.py'
    if os.path.exists(app_config_path):
        with open(app_config_path, 'r') as f:
            content = f.read()
        
        # Update the name field
        old_name = f"name = '{app}'"
        new_name = f"name = 'blu_staff.apps.{app}'\n    label = '{app}'"
        
        if old_name in content:
            content = content.replace(old_name, new_name)
            with open(app_config_path, 'w') as f:
                f.write(content)
            print(f'Fixed {app}')
        else:
            print(f'Skipped {app} - already fixed or different format')
    else:
        print(f'Not found: {app}')

print('Done!')
