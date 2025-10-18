from django.core.management.base import BaseCommand
from accounts.models import User
from django.contrib.auth.hashers import make_password


class Command(BaseCommand):
    help = 'Create a SuperAdmin user for EMS frontend'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='Email for the SuperAdmin')
        parser.add_argument('--password', required=True, help='Password for the SuperAdmin')
        parser.add_argument('--first-name', default='Super', help='First name')
        parser.add_argument('--last-name', default='Admin', help='Last name')

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'User with email {email} already exists'))
            return

        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='SUPERADMIN',  # Fixed: Use SUPERADMIN role, not ADMIN
            is_superuser=True,
            is_active=True,
            is_staff=False,  # SuperAdmin should NOT have staff access
        )
        user.set_password(password)
        user.save()

        self.stdout.write(
            self.style.SUCCESS(f'SuperAdmin user {email} created successfully!')
        )
        self.stdout.write(
            self.style.SUCCESS('This user can only access the EMS frontend via /login/')
        )
