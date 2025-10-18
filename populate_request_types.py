"""
Script to populate default request types
Run with: python populate_request_types.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from requests.models import RequestType

def populate_request_types():
    request_types_data = [
        {
            'name': '💵 Petty Cash Request',
            'code': 'PETTY_CASH',
            'icon': '💵',
            'description': 'Request for petty cash for office expenses',
            'requires_amount': True,
            'requires_approval': True,
            'approval_levels': 1,
            'max_amount': 5000.00,
        },
        {
            'name': '💰 Salary Advance',
            'code': 'ADVANCE',
            'icon': '💰',
            'description': 'Request for salary advance',
            'requires_amount': True,
            'requires_approval': True,
            'approval_levels': 2,
            'max_amount': 10000.00,
        },
        {
            'name': '🧾 Expense Reimbursement',
            'code': 'REIMBURSEMENT',
            'icon': '🧾',
            'description': 'Request for reimbursement of expenses',
            'requires_amount': True,
            'requires_approval': True,
            'requires_attachment': True,
            'approval_levels': 1,
        },
        {
            'name': '💻 IT Support',
            'code': 'IT_SUPPORT',
            'icon': '💻',
            'description': 'Request for IT support or equipment',
            'requires_amount': False,
            'requires_approval': True,
            'approval_levels': 1,
        },
        {
            'name': '📝 Stationery Request',
            'code': 'STATIONERY',
            'icon': '📝',
            'description': 'Request for office stationery and supplies',
            'requires_amount': False,
            'requires_approval': True,
            'approval_levels': 1,
        },
        {
            'name': '🏠 Work From Home',
            'code': 'WFH',
            'icon': '🏠',
            'description': 'Request to work from home',
            'requires_amount': False,
            'requires_approval': True,
            'approval_levels': 1,
        },
        {
            'name': '📄 Document Request',
            'code': 'DOCUMENT',
            'icon': '📄',
            'description': 'Request for official documents (certificates, letters, etc.)',
            'requires_amount': False,
            'requires_approval': True,
            'approval_levels': 1,
        },
        {
            'name': '🎓 Training Request',
            'code': 'TRAINING',
            'icon': '🎓',
            'description': 'Request for training or development programs',
            'requires_amount': True,
            'requires_approval': True,
            'approval_levels': 2,
        },
        {
            'name': '🚗 Transportation',
            'code': 'TRANSPORT',
            'icon': '🚗',
            'description': 'Request for transportation or fuel allowance',
            'requires_amount': True,
            'requires_approval': True,
            'approval_levels': 1,
        },
        {
            'name': '🏥 Medical Leave Certificate',
            'code': 'MEDICAL_CERT',
            'icon': '🏥',
            'description': 'Request for medical leave certificate',
            'requires_amount': False,
            'requires_approval': True,
            'approval_levels': 1,
        },
        {
            'name': '📋 Other Request',
            'code': 'OTHER',
            'icon': '📋',
            'description': 'General request for other matters',
            'requires_amount': False,
            'requires_approval': True,
            'approval_levels': 1,
        },
    ]
    
    created_count = 0
    updated_count = 0
    
    for data in request_types_data:
        request_type, created = RequestType.objects.update_or_create(
            code=data['code'],
            defaults=data
        )
        if created:
            created_count += 1
            print(f"✅ Created: {request_type.name}")
        else:
            updated_count += 1
            print(f"🔄 Updated: {request_type.name}")
    
    print(f"\n✅ Summary: {created_count} created, {updated_count} updated")
    print(f"📊 Total Request Types: {RequestType.objects.count()}")

if __name__ == '__main__':
    populate_request_types()
