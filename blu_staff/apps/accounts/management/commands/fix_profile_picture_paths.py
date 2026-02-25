"""
Management command to fix duplicate profile_pics path in profile pictures
Usage: python manage.py fix_profile_picture_paths
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Fix duplicate profile_pics path in profile picture URLs'

    def handle(self, *args, **options):
        users_with_pictures = User.objects.exclude(profile_picture='').exclude(profile_picture__isnull=True)
        
        fixed_count = 0
        for user in users_with_pictures:
            old_path = user.profile_picture.name
            
            # Check if path has duplicate profile_pics
            if 'profile_pics/profile_pictures/' in old_path:
                # Remove the duplicate
                new_path = old_path.replace('profile_pics/profile_pictures/', 'profile_pics/')
                
                self.stdout.write(f"Fixing {user.get_full_name()}: {old_path} -> {new_path}")
                
                # Update the path
                user.profile_picture.name = new_path
                user.save(update_fields=['profile_picture'])
                
                fixed_count += 1
        
        if fixed_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully fixed {fixed_count} profile picture paths'))
        else:
            self.stdout.write(self.style.SUCCESS('No profile pictures needed fixing'))
