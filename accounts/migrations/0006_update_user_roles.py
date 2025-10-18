# Generated migration to update user roles

import secrets
import string
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_company_registration_system'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Update existing ADMIN roles to SUPERADMIN
            UPDATE accounts_user SET role = 'SUPERADMIN' WHERE role = 'ADMIN';

            -- Update existing EMPLOYER_SUPERUSER roles to ADMINISTRATOR
            UPDATE accounts_user SET role = 'ADMINISTRATOR' WHERE role = 'EMPLOYER_SUPERUSER';
            """,
            reverse_sql="""
            -- Reverse migration - restore old role names
            UPDATE accounts_user SET role = 'ADMIN' WHERE role = 'SUPERADMIN';
            UPDATE accounts_user SET role = 'EMPLOYER_SUPERUSER' WHERE role = 'ADMINISTRATOR';
            """
        ),
    ]
