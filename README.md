# EicomTech Employee Management System (EMS)

A comprehensive Django-based Employee Management System with company registration, user management, and email notifications.

## Features

- ✅ Company Registration & Approval System
- ✅ Multi-role User Management (SuperAdmin, Employer, HR, Payroll, Employee)
- ✅ Email Notifications with Login Credentials
- ✅ Resend Credentials Functionality
- ✅ RESTful API with Swagger Documentation
- ✅ PostgreSQL Database Support (Supabase)
- ✅ Modern Responsive UI
- ✅ Attendance Tracking
- ✅ Leave Management
- ✅ Performance Management
- ✅ Payroll Management

## Prerequisites

- Python 3.8+
- PostgreSQL (Supabase)
- Git

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd EMS
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Supabase Database Configuration
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your-supabase-password-here
DB_HOST=db.mpldpvzuuptljxvmdihg.supabase.co
DB_PORT=5432

# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True

# Email Configuration (for production)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@eiscomtech.com

# Site URL
SITE_URL=https://your-domain.com
```

### 5. Get Supabase Credentials

1. Go to your Supabase project: https://supabase.com/dashboard/project/mpldpvzuuptljxvmdihg
2. Navigate to **Settings** → **Database**
3. Copy the connection details:
   - **Host**: `db.mpldpvzuuptljxvmdihg.supabase.co`
   - **Database**: `postgres`
   - **Port**: `5432`
   - **Username**: `postgres`
   - **Password**: Get from the database settings

### 6. Run Database Migrations

```bash
python manage.py migrate
```

### 7. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 8. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 9. Run the Development Server

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## Usage

### SuperAdmin Features

1. **Access SuperAdmin Dashboard**: `http://127.0.0.1:8000/`
2. **Company Registration Requests**: View and approve/reject company registrations
3. **Approved Companies**: Manage approved companies and users
4. **Resend Credentials**: Resend login credentials to company contacts

### Company Registration

1. Companies can register at the registration form
2. SuperAdmin reviews and approves requests
3. Automatic email sent with login credentials upon approval

### API Documentation

- **Swagger UI**: `http://127.0.0.1:8000/api/docs/`
- **ReDoc**: `http://127.0.0.1:8000/api/redoc/`

## Project Structure

```
EMS/
├── accounts/           # User management and authentication
├── attendance/         # Attendance tracking system
├── documents/          # Document management
├── performance/        # Performance management
├── payroll/            # Payroll management
├── ems_project/        # Main Django project settings
├── templates/          # HTML templates
├── static/             # Static files (CSS, JS, images)
├── media/              # User uploaded files
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_NAME` | Supabase database name | `postgres` |
| `DB_USER` | Supabase database user | `postgres` |
| `DB_PASSWORD` | Supabase database password | `your-supabase-password` |
| `DB_HOST` | Supabase database host | `db.mpldpvzuuptljxvmdihg.supabase.co` |
| `DB_PORT` | Supabase database port | `5432` |
| `SECRET_KEY` | Django secret key | `django-insecure-...` |
| `DEBUG` | Debug mode | `True` |
| `EMAIL_BACKEND` | Email backend | `django.core.mail.backends.console.EmailBackend` |
| `DEFAULT_FROM_EMAIL` | Default from email | `noreply@eiscomtech.com` |
| `SITE_URL` | Site URL for email links | `http://127.0.0.1:8000` |

## Database Schema

The application uses the following main models:

- **User**: Custom user model with roles
- **Company**: Company information and settings
- **CompanyRegistrationRequest**: Pending company registrations
- **EmployeeProfile**: Employee-specific information
- **EmployerProfile**: Employer-specific information

## Deployment

### Production Deployment

1. Set `DEBUG=False` in environment variables
2. Configure production email settings
3. Set up proper ALLOWED_HOSTS
4. Use a production WSGI server (Gunicorn + Nginx)
5. Set up SSL/TLS certificates
6. Configure static file serving

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
RUN python manage.py migrate
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "ems_project.wsgi:application"]
```

## Troubleshooting

### Common Issues

1. **Database Connection Error**: Check Supabase credentials in `.env`
2. **Email Not Sending**: Configure SMTP settings or use console backend for testing
3. **Static Files Not Loading**: Run `collectstatic` command
4. **Migrations Error**: Ensure all dependencies are installed

### Development Tips

- Use console email backend for testing: `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`
- Enable debug mode for development: `DEBUG=True`
- Use SQLite for local development if needed

## Support

For support or questions, please contact the development team or check the Supabase documentation for database-related issues.

## License

This project is proprietary software developed by EicomTech.
