import os
import re

# Template files to update
files = [
    'asset_list.html',
    'asset_detail.html', 
    'asset_form.html',
    'asset_request_create.html',
    'asset_request_list.html',
    'asset_request_detail.html',
    'asset_request_approve.html',
    'department_dashboard.html'
]

# URL name replacements
url_replacements = [
    ("'asset_list'", "'assets:asset_list'"),
    ("'asset_create'", "'assets:asset_create'"),
    ("'asset_edit'", "'assets:asset_edit'"),
    ("'asset_detail'", "'assets:asset_detail'"),
    ("'asset_send_to_repair'", "'assets:asset_send_to_repair'"),
    ("'asset_return'", "'assets:asset_return'"),
    ("'asset_unassign'", "'assets:asset_unassign'"),
    ("'asset_request_create'", "'assets:asset_request_create'"),
    ("'asset_request_list'", "'assets:asset_request_list'"),
    ("'asset_request_detail'", "'assets:asset_request_detail'"),
    ("'asset_request_approve'", "'assets:asset_request_approve'"),
    ("'asset_maintenance_add'", "'assets:asset_maintenance_add'"),
    ("'asset_collection_add'", "'assets:asset_collection_add'"),
    ("'asset_collection_print'", "'assets:asset_collection_print'"),
    ("'department_asset_dashboard'", "'assets:department_asset_dashboard'"),
]

base_path = 'ems_project/templates/assets/'
updated_count = 0

for filename in files:
    filepath = os.path.join(base_path, filename)
    if not os.path.exists(filepath):
        print(f"Skipping {filename} - file not found")
        continue
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all replacements
        for old_url, new_url in url_replacements:
            content = content.replace(old_url, new_url)
        
        # Only write if content changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[OK] Updated {filename}")
            updated_count += 1
        else:
            print(f"[SKIP] No changes needed for {filename}")
    
    except Exception as e:
        print(f"[ERROR] Error updating {filename}: {e}")

print(f"\nCompleted: Updated {updated_count} template files with namespaced URLs")
