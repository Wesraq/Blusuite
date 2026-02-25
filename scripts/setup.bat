@echo off
echo 🚀 EicomTech EMS - Supabase Setup Script
echo ========================================
echo.

REM Check if .env file exists
if not exist ".env" (
    echo ❌ .env file not found!
    echo Please create a .env file with your Supabase credentials.
    echo.
    echo Example .env file:
    echo DB_NAME=postgres
    echo DB_USER=postgres
    echo DB_PASSWORD=your-supabase-password
    echo DB_HOST=db.mpldpvzuuptljxvmdihg.supabase.co
    echo DB_PORT=5432
    echo SECRET_KEY=your-secret-key
    echo DEBUG=True
    pause
    exit /b 1
)

echo ✅ .env file found

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

echo 📥 Installing dependencies...
pip install -r requirements.txt

echo 🔄 Running database migrations...
python manage.py migrate

echo 📊 Creating database tables...
python manage.py migrate --run-syncdb

echo 🎯 Collecting static files...
python manage.py collectstatic --noinput

echo.
echo ✅ Setup Complete!
echo.
echo To start the development server:
echo python manage.py runserver
echo.
echo To create a superuser:
echo python manage.py createsuperuser
echo.
echo 🌐 Access the application at: http://127.0.0.1:8000/
echo 📚 API Documentation: http://127.0.0.1:8000/api/docs/
echo.
pause
