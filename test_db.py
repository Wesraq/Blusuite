#!/usr/bin/env python
"""
Database Connection Test Script for Supabase
"""
import os
import sys
import django
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_project.settings')
django.setup()

from django.db import connection
from django.core.management.color import no_style

def test_database_connection():
    """Test database connection and display information"""
    try:
        # Test the connection
        cursor = connection.cursor()

        # Get database information
        cursor.execute("SELECT version()")
        db_version = cursor.fetchone()[0]

        cursor.execute("SELECT current_database()")
        db_name = cursor.fetchone()[0]

        cursor.execute("SELECT current_user")
        db_user = cursor.fetchone()[0]

        print("✅ Database Connection Successful!")
        print("=" * 40)
        print(f"📊 Database Name: {db_name}")
        print(f"👤 Current User: {db_user}")
        print(f"🔧 PostgreSQL Version: {db_version}")
        print(f"🌐 Host: {os.getenv('DB_HOST', 'Not configured')}")
        print(f"🔌 Port: {os.getenv('DB_PORT', 'Not configured')}")

        # Check if tables exist
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)

        tables = cursor.fetchall()
        print(f"\n📋 Tables in database ({len(tables)}):")
        for table in tables:
            print(f"  • {table[0]}")

        return True

    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        print("\n🔧 Troubleshooting Tips:")
        print("1. Check your .env file has correct Supabase credentials")
        print("2. Ensure your IP is whitelisted in Supabase")
        print("3. Verify the database password is correct")
        print("4. Make sure psycopg2-binary is installed")
        return False

if __name__ == "__main__":
    print("🔍 Testing Supabase Database Connection...")
    print("=" * 50)

    success = test_database_connection()

    if success:
        print("\n🎉 Database connection is working correctly!")
        print("You can now run: python manage.py runserver")
    else:
        print("\n⚠️  Please fix the connection issues before proceeding.")
        sys.exit(1)
