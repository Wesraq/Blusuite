import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from blu_staff.apps.notifications.models import Notification
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Get Pamela
pamela = User.objects.filter(first_name='Pamela', last_name='Tembo').first()
if not pamela:
    print("Pamela not found!")
else:
    print(f"Found Pamela: {pamela.email}")
    
    # Get an admin user to be the sender
    admin = User.objects.filter(role='ADMINISTRATOR').first()
    if not admin:
        admin = User.objects.filter(role='EMPLOYER_ADMIN').first()
    
    # Create a test notification
    notification = Notification.objects.create(
        recipient=pamela,
        sender=admin if admin else pamela,
        title='Test Notification',
        message='This is a test notification to verify the system is working.',
        notification_type='INFO',
        category='SYSTEM',
        link='/employee/',
    )
    
    print(f"Created notification ID: {notification.id}")
    print(f"Notification created at: {notification.created_at}")
    
    # Check total notifications for Pamela
    total = Notification.objects.filter(recipient=pamela).count()
    unread = Notification.objects.filter(recipient=pamela, is_read=False).count()
    
    print(f"\nPamela's notifications:")
    print(f"  Total: {total}")
    print(f"  Unread: {unread}")
    
    # List all notifications
    print("\nAll notifications for Pamela:")
    for n in Notification.objects.filter(recipient=pamela).order_by('-created_at'):
        print(f"  - {n.title} ({n.notification_type}) - Read: {n.is_read}")
