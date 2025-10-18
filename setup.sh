#!/bin/bash

echo "🚀 EicomTech EMS - Supabase Setup Script"
echo "========================================"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please create a .env file with your Supabase credentials."
    echo ""
    echo "Example .env file:"
    echo "DB_NAME=postgres"
    echo "DB_USER=postgres"
    echo "DB_PASSWORD=your-supabase-password"
    echo "DB_HOST=db.mpldpvzuuptljxvmdihg.supabase.co"
    echo "DB_PORT=5432"
    echo "SECRET_KEY=your-secret-key"
    echo "DEBUG=True"
    exit 1
fi

echo "✅ .env file found"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate  # On Windows: venv\Scripts\activate

echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo "🔄 Running database migrations..."
python manage.py migrate

echo "📊 Creating database tables..."
python manage.py migrate --run-syncdb

echo "🎯 Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "✅ Setup Complete!"
echo ""
echo "To start the development server:"
echo "python manage.py runserver"
echo ""
echo "To create a superuser:"
echo "python manage.py createsuperuser"
echo ""
echo "🌐 Access the application at: http://127.0.0.1:8000/"
echo "📚 API Documentation: http://127.0.0.1:8000/api/docs/"
