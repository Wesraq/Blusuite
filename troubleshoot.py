#!/usr/bin/env python
"""
Supabase Connection Troubleshooting Script
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_supabase_config():
    """Check Supabase configuration"""
    print("🔍 Checking Supabase Configuration...")
    print("=" * 40)

    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_PORT']
    missing_vars = []

    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)

    if missing_vars:
        print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        return False

    print("
✅ All required environment variables are set!"    print("
🔧 Your Supabase Configuration:"    print(f"   Host: {os.getenv('DB_HOST')}")
    print(f"   Database: {os.getenv('DB_NAME')}")
    print(f"   User: {os.getenv('DB_USER')}")
    print(f"   Port: {os.getenv('DB_PORT')}")
    print(f"   Password: {'*' * len(os.getenv('DB_PASSWORD', ''))}")

    return True

def test_connection():
    """Test database connection"""
    try:
        import psycopg2
        print("
🔌 Testing database connection..."        print("=" * 40)

        conn_params = {
            'host': os.getenv('DB_HOST'),
            'database': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'port': os.getenv('DB_PORT'),
            'sslmode': 'require'
        }

        print("Connecting to PostgreSQL...")
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()

        # Test basic queries
        cursor.execute("SELECT version()")
        db_version = cursor.fetchone()[0]

        cursor.execute("SELECT current_database()")
        db_name = cursor.fetchone()[0]

        cursor.execute("SELECT current_user")
        db_user = cursor.fetchone()[0]

        print("✅ Connection successful!")
        print(f"📊 Database: {db_name}")
        print(f"👤 User: {db_user}")
        print(f"🔧 PostgreSQL: {db_version}")

        # Check if we can create tables
        cursor.execute("SELECT schemaname FROM pg_tables WHERE schemaname = 'public'")
        schemas = cursor.fetchall()

        print(f"📋 Available schemas: {len(schemas)}")

        conn.close()
        return True

    except ImportError:
        print("❌ psycopg2-binary not installed. Run: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n🔧 Possible solutions:")
        print("1. Check your password in .env file")
        print("2. Whitelist your IP in Supabase dashboard")
        print("3. Verify database settings in Supabase")
        print("4. Check if your Supabase project is active")
        return False

if __name__ == "__main__":
    print("🚀 Supabase Connection Troubleshooting")
    print("=" * 50)

    if check_supabase_config():
        success = test_connection()

        if success:
            print("\n🎉 Database connection successful!")
            print("You can now run: python manage.py migrate")
        else:
            print("\n⚠️  Please fix the connection issues above.")
    else:
        print("\n❌ Please fix your environment configuration first.")
