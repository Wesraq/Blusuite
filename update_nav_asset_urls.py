import os

# Files to update (paths relative to repo root)
files = [
    'ems_project/frontend_views.py',
    'ems_project/templates/ems/settings_hub.html',
    'ems_project/templates/ems/partials/sidebar_employer.html',
    'ems_project/templates/ems/partials/sidebar_employer_new.html',
    'ems_project/templates/ems/base_superadmin.html',
    'ems_project/templates/ems/base_employee.html',
    'ems_project/templates/ems/asset_create.html',
    'ems_project/templates/ems/admin_dashboard_new.html',
]

replacements = [
    ("reverse('asset_list')", "reverse('assets:asset_list')"),
    ("{% url 'asset_list' %}", "{% url 'assets:asset_list' %}"),
]

updated = 0
for rel_path in files:
    if not os.path.exists(rel_path):
        print(f"[SKIP] {rel_path} not found")
        continue
    try:
        with open(rel_path, 'r', encoding='utf-8') as f:
            content = f.read()
        original = content
        for old, new in replacements:
            content = content.replace(old, new)
        if content != original:
            with open(rel_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[OK] Updated {rel_path}")
            updated += 1
        else:
            print(f"[SKIP] No changes for {rel_path}")
    except Exception as e:
        print(f"[ERROR] {rel_path}: {e}")

print(f"Done. Files updated: {updated}")
