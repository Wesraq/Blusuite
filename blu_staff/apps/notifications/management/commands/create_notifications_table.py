from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Manually create notifications tables if they do not exist'

    def handle(self, *args, **options):
        self.stdout.write('Creating notifications tables...')
        
        with connection.cursor() as cursor:
            # Create NotificationPreference table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "blu_staff_notificationpreference" (
                    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "email_attendance" bool NOT NULL,
                    "email_leave" bool NOT NULL,
                    "email_document" bool NOT NULL,
                    "email_performance" bool NOT NULL,
                    "email_payroll" bool NOT NULL,
                    "email_training" bool NOT NULL,
                    "inapp_attendance" bool NOT NULL,
                    "inapp_leave" bool NOT NULL,
                    "inapp_document" bool NOT NULL,
                    "inapp_performance" bool NOT NULL,
                    "inapp_payroll" bool NOT NULL,
                    "inapp_training" bool NOT NULL,
                    "created_at" datetime NOT NULL,
                    "updated_at" datetime NOT NULL,
                    "user_id" bigint NOT NULL UNIQUE REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "tenant_id" bigint NULL REFERENCES "tenant_management_tenant" ("id") DEFERRABLE INITIALLY DEFERRED
                )
            """)
            
            # Create Notification table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "blu_staff_notification" (
                    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "title" varchar(200) NOT NULL,
                    "message" text NOT NULL,
                    "notification_type" varchar(20) NOT NULL,
                    "category" varchar(50) NOT NULL,
                    "link" varchar(500) NOT NULL DEFAULT '',
                    "is_read" bool NOT NULL DEFAULT 0,
                    "read_at" datetime NULL,
                    "is_email_sent" bool NOT NULL DEFAULT 0,
                    "created_at" datetime NOT NULL,
                    "recipient_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "sender_id" bigint NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "tenant_id" bigint NULL REFERENCES "tenant_management_tenant" ("id") DEFERRABLE INITIALLY DEFERRED
                )
            """)
            
            # Create indexes
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS "blu_staff_notification_recipient_id_d055f3f0" ON "blu_staff_notification" ("recipient_id")')
                cursor.execute('CREATE INDEX IF NOT EXISTS "blu_staff_notification_sender_id_feea9ca3" ON "blu_staff_notification" ("sender_id")')
                cursor.execute('CREATE INDEX IF NOT EXISTS "blu_staff_notif_recipie_a972ce_idx" ON "blu_staff_notification" ("recipient_id", "created_at" DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS "blu_staff_notif_recipie_4e3567_idx" ON "blu_staff_notification" ("recipient_id", "is_read")')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Some indexes may already exist: {e}'))
        
        self.stdout.write(self.style.SUCCESS('Notifications tables created successfully!'))
