#!/usr/bin/env python
"""
Test script to verify CSV export functionality
"""
import os
import sys
import django

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from ems_project import frontend_views

User = get_user_model()

def test_exports():
    """Test all CSV export views"""
    print("\n" + "="*70)
    print("CSV EXPORT FUNCTIONALITY TEST")
    print("="*70)
    
    # Get an admin user
    admin = User.objects.filter(role__in=['ADMINISTRATOR', 'EMPLOYER_ADMIN']).first()
    
    if not admin:
        print("❌ No admin user found. Please create an admin user first.")
        return
    
    print(f"\n✅ Testing as: {admin.get_full_name()} ({admin.email})")
    print(f"   Role: {admin.role}")
    
    factory = RequestFactory()
    
    exports_to_test = [
        ('Employee Roster', 'export_employee_roster', '/reports/export/roster/'),
        ('Attendance Report', 'export_attendance_report', '/reports/export/attendance/'),
        ('Leave Report', 'export_leave_report', '/reports/export/leave/'),
        ('Documents Report', 'export_documents_report', '/reports/export/documents/'),
        ('Assets Report', 'export_assets_report', '/reports/export/assets/'),
    ]
    
    results = []
    
    for name, view_name, url in exports_to_test:
        print(f"\n📊 Testing: {name}")
        print(f"   URL: {url}")
        
        try:
            # Create request
            request = factory.get(url)
            request.user = admin
            
            # Get the view function
            view_func = getattr(frontend_views, view_name)
            
            # Call the view
            response = view_func(request)
            
            # Check response
            if response.status_code == 200:
                content_type = response.get('Content-Type', '')
                filename = response.get('Content-Disposition', '')
                
                if 'text/csv' in content_type:
                    print(f"   ✅ SUCCESS - CSV generated")
                    print(f"   📁 Content-Type: {content_type}")
                    print(f"   📁 Filename: {filename}")
                    
                    # Count lines
                    content = response.content.decode('utf-8')
                    lines = content.split('\n')
                    print(f"   📄 Rows: {len(lines)} (including header)")
                    
                    results.append((name, '✅ PASS', len(lines)))
                else:
                    print(f"   ⚠️  WARNING - Not CSV format")
                    print(f"   Content-Type: {content_type}")
                    results.append((name, '⚠️  WARN', 'Not CSV'))
            else:
                print(f"   ❌ FAILED - Status code: {response.status_code}")
                results.append((name, '❌ FAIL', f'Status {response.status_code}'))
                
        except Exception as e:
            print(f"   ❌ ERROR - {str(e)}")
            results.append((name, '❌ ERROR', str(e)))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for name, status, info in results:
        print(f"{status} {name}: {info}")
    
    passed = sum(1 for _, status, _ in results if '✅' in status)
    total = len(results)
    
    print(f"\n{'='*70}")
    print(f"TOTAL: {passed}/{total} exports working")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    test_exports()
