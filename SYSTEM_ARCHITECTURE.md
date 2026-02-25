# BLU Suite - Complete System Architecture

## System Overview
BLU Suite is a comprehensive multi-tenant Enterprise Management System (EMS) built with Django 4.2.24, featuring modular architecture with integrated suites for HR, Projects, Assets, Analytics, Billing, and Support.

## Technology Stack
- **Backend**: Django 4.2.24 (Python 3.13.3)
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Styling**: TailwindCSS (inline styles), Custom CSS
- **Authentication**: Django Auth with role-based access control
- **File Storage**: Django FileField (local/S3)
- **Email**: Django Email Backend (SMTP)

## Application Structure

### Core Applications

#### 1. **ems_project** (Main EMS Suite)
**Purpose**: Core HR and employee management functionality
**Location**: `/ems_project/`

**Key Models**:
- `User` - Custom user model with role field
- `EmployeeProfile` - Extended employee information
- `EmployerProfile` - Company/employer information
- `Attendance` - Daily attendance tracking
- `LeaveRequest` - Leave management
- `PerformanceReview` - Employee performance reviews
- `Department` - Organizational departments
- `Branch` - Company branches

**User Roles**:
- `EMPLOYEE` - Standard employee access
- `SUPERVISOR` - Team lead with approval rights
- `HR` - Human resources management
- `ACCOUNTANT` / `ACCOUNTS` - Financial/payroll access
- `ADMINISTRATOR` - Company admin
- `EMPLOYER_ADMIN` - Top-level company admin

**Key Features**:
- Employee dashboards (role-specific)
- Attendance management (clock in/out)
- Leave request workflow with approvals
- Document management
- Performance reviews
- Employee requests system
- Payroll integration
- Branch and department management

**Views**: 316 files including dashboards, forms, reports

#### 2. **blu_projects** (Project Management Suite - PMS)
**Purpose**: Project and task management
**Location**: `/blu_projects/`

**Key Models**:
- `Project` - Project information with team members
- `Task` - Individual tasks with assignments
- `Milestone` - Project milestones
- `ProjectActivity` - Activity tracking
- `ProjectDocument` - Project documentation

**Key Features**:
- Project creation and management
- Task assignment and tracking
- Timeline view with progress bars
- Calendar view with deadlines
- Team collaboration
- Project analytics
- Document management
- Client portal integration

**Views**: 29 files including timeline, calendar, kanban

#### 3. **blu_assets** (Asset Management Suite - AMS)
**Purpose**: Company asset tracking and management
**Location**: `/blu_assets/`

**Key Models**:
- `Asset` - Company assets (IT, furniture, vehicles, etc.)
- `EmployeeAsset` - Asset assignments to employees
- `AssetRequest` - Asset request workflow
- `AssetMaintenance` - Maintenance tracking
- `AssetCategory` - Asset categorization

**Key Features**:
- Asset inventory management
- Asset assignment to employees
- Request and approval workflow
- Maintenance scheduling
- Asset lifecycle tracking
- QR code generation
- Depreciation tracking

**Views**: 47 files including inventory, assignments, requests

#### 4. **blu_analytics** (Analytics Suite)
**Purpose**: Business intelligence and reporting
**Location**: `/blu_analytics/`

**Key Models**:
- `AnalyticsReport` - Saved reports
- `CustomReport` - User-defined reports
- `Dashboard` - Custom dashboards

**Key Features**:
- Employee analytics
- Project analytics
- Financial analytics
- Custom report builder
- Data visualization
- Export capabilities (CSV, PDF)

**Views**: 25 files including dashboards, reports

#### 5. **blu_billing** (Billing & Subscription)
**Purpose**: Multi-tenant subscription management
**Location**: `/blu_billing/`

**Key Models**:
- `Subscription` - Company subscriptions
- `Plan` - Subscription plans
- `Invoice` - Billing invoices
- `Payment` - Payment tracking

**Key Features**:
- Subscription tiers (Basic, Professional, Enterprise)
- Feature-based access control
- Billing and invoicing
- Payment processing integration
- Usage tracking

**Views**: 17 files including billing, subscriptions

#### 6. **blu_support** (Support & Ticketing)
**Purpose**: Customer support and helpdesk
**Location**: `/blu_support/`

**Key Models**:
- `Ticket` - Support tickets
- `TicketComment` - Ticket conversations
- `KnowledgeBase` - Help articles

**Key Features**:
- Ticket creation and tracking
- Priority management
- Knowledge base
- Support dashboard

**Views**: 32 files including tickets, knowledge base

#### 7. **tenant_management** (Multi-tenancy)
**Purpose**: Multi-tenant company isolation
**Location**: `/tenant_management/`

**Key Models**:
- `Company` - Tenant companies
- `CompanySettings` - Company-specific settings

**Key Features**:
- Company registration
- Data isolation by company
- Company-specific branding
- Settings management

**Views**: 35 files including company management

#### 8. **blu_staff** (Staff Management)
**Purpose**: Extended staff functionality
**Location**: `/blu_staff/`

**Key Models**:
- Extended employee features
- Staff-specific workflows

**Views**: 618 files (extensive staff management)

### Supporting Modules

#### 9. **payroll** (Payroll Management)
**Models**:
- `Payroll` - Payroll records
- `SalaryStructure` - Salary components
- `PayrollDeduction` - Deductions (NAPSA, NHIMA, tax)
- `PayrollDeductionSettings` - Deduction rules
- `EmployeeBenefit` - Employee benefits

**Features**:
- Payroll generation
- Payslip designer
- Deduction calculations
- Tax calculations
- Benefit management

#### 10. **attendance** (Attendance System)
**Models**:
- `Attendance` - Daily attendance
- `LeaveRequest` - Leave management
- `LeaveType` - Leave categories
- `Holiday` - Company holidays

**Features**:
- Clock in/out
- Leave approval workflow
- Attendance reports
- Leave balance tracking

#### 11. **documents** (Document Management)
**Models**:
- `EmployeeDocument` - Employee documents
- `DocumentType` - Document categories

**Features**:
- Document upload
- Approval workflow
- Document versioning
- Secure storage

#### 12. **notifications** (Notification System)
**Models**:
- `Notification` - User notifications

**Features**:
- Real-time notifications
- Email notifications
- In-app notifications
- Notification preferences

#### 13. **communication** (Internal Communication)
**Models**:
- `Announcement` - Company announcements
- `Message` - Internal messaging

**Features**:
- Company-wide announcements
- Internal messaging
- Communication history

#### 14. **training** (Training Management)
**Models**:
- `TrainingProgram` - Training programs
- `TrainingEnrollment` - Employee enrollments

**Features**:
- Training program management
- Enrollment tracking
- Completion tracking

#### 15. **onboarding** (Employee Onboarding)
**Models**:
- `OnboardingProcess` - Onboarding workflows
- `OnboardingTaskCompletion` - Task tracking

**Features**:
- Onboarding checklists
- Task assignments
- Progress tracking

## Data Flow Architecture

### Authentication Flow
```
User Login → Django Auth → Role Check → Dashboard Redirect
                                ↓
                    Role-Based Dashboard Selection
                                ↓
        ┌──────────────────────┼──────────────────────┐
        ↓                      ↓                      ↓
    EMPLOYEE              SUPERVISOR                 HR
    Dashboard             Dashboard              Dashboard
        ↓                      ↓                      ↓
    ACCOUNTANT           ADMINISTRATOR          EMPLOYER_ADMIN
    Dashboard             Dashboard              Dashboard
```

### Request Approval Workflow
```
Employee → Create Request → Pending
                ↓
        Supervisor Review
                ↓
        ┌───────┴───────┐
        ↓               ↓
    Approved        Rejected
        ↓               ↓
    HR Review       Employee
        ↓           Notified
    ┌───┴───┐
    ↓       ↓
Approved  Rejected
    ↓       ↓
Complete  Employee
         Notified
```

### Payroll Processing Flow
```
Salary Structure → Employee Assignment
        ↓
Attendance Data → Working Days Calculation
        ↓
Deductions (NAPSA, NHIMA, Tax) → Applied
        ↓
Benefits → Added
        ↓
Net Pay Calculation → Payroll Record
        ↓
Payslip Generation → Employee Access
```

### Cross-Suite Integration
```
Employee Dashboard
        ↓
    ┌───┴───┐
    ↓       ↓
  AMS     PMS
(Assets) (Projects)
    ↓       ↓
My Assets  My Projects
    ↓       ↓
My Suites Dashboard
```

## Database Schema Overview

### Core Tables
- `ems_project_user` - Users (custom auth)
- `ems_project_employeeprofile` - Employee details
- `ems_project_employerprofile` - Company details
- `tenant_management_company` - Multi-tenant companies

### Relationships
- User → EmployeeProfile (1:1)
- User → Company (M:1)
- Company → Employees (1:M)
- Project → Team Members (M:M)
- Asset → Employee (M:1 via EmployeeAsset)
- LeaveRequest → Approvals (1:M)

## Access Control Matrix

| Role | Attendance | Leave | Payroll | Documents | Projects | Assets | Analytics | Admin |
|------|-----------|-------|---------|-----------|----------|--------|-----------|-------|
| EMPLOYEE | View Own | Request | View Own | Upload | View Assigned | View Assigned | - | - |
| SUPERVISOR | View Team | Approve | - | View Team | Manage Team | - | Team Stats | - |
| HR | View All | Approve | - | Manage | View All | - | HR Stats | - |
| ACCOUNTANT | - | - | Manage | - | - | - | Financial | - |
| ADMINISTRATOR | Manage | Manage | View | Manage | Manage | Manage | Full | Company |
| EMPLOYER_ADMIN | Full | Full | Full | Full | Full | Full | Full | Full |

## File Structure
```
BLU_suite/
├── ems_project/          # Main EMS application
│   ├── models.py         # Core models
│   ├── frontend_views.py # Dashboard views (15,616 lines)
│   ├── views.py          # API views
│   ├── urls.py           # URL routing
│   ├── templates/ems/    # 316 templates
│   └── static/           # Static assets
├── blu_projects/         # Project management
├── blu_assets/           # Asset management
├── blu_analytics/        # Analytics
├── blu_billing/          # Billing
├── blu_support/          # Support
├── tenant_management/    # Multi-tenancy
├── payroll/              # Payroll module
├── attendance/           # Attendance module
├── documents/            # Document management
├── notifications/        # Notifications
├── communication/        # Communication
├── training/             # Training
├── onboarding/           # Onboarding
├── media/                # Uploaded files
├── static/               # Static files
├── staticfiles/          # Collected static files
└── manage.py             # Django management
```

## API Endpoints

### Authentication
- `/login/` - User login
- `/logout/` - User logout
- `/register/` - Company registration

### Employee Management
- `/employee/` - Employee dashboard
- `/employee/profile/` - Employee profile
- `/employee/attendance/` - Attendance
- `/employee/leave/` - Leave requests
- `/employee/documents/` - Documents
- `/employee/suites/` - Cross-suite dashboard

### HR Management
- `/hr/dashboard/` - HR dashboard
- `/hr/employees/` - Employee list
- `/hr/attendance/` - Attendance management
- `/hr/leave/` - Leave approvals
- `/hr/performance/` - Performance reviews

### Payroll
- `/payroll/` - Payroll list
- `/payroll/generate/` - Generate payroll
- `/payroll/<id>/` - Payroll detail
- `/payroll/settings/` - Payroll settings

### Projects
- `/projects/` - Project list
- `/projects/<id>/` - Project detail
- `/projects/timeline/` - Timeline view
- `/projects/calendar/` - Calendar view
- `/projects/tasks/` - Task management

### Assets
- `/assets/` - Asset list
- `/assets/<id>/` - Asset detail
- `/assets/my-assets/` - Employee assets
- `/assets/requests/` - Asset requests

## Security Features

### Authentication
- Django session-based authentication
- Password hashing (PBKDF2)
- Login required decorators
- Role-based access control

### Data Protection
- Company data isolation (multi-tenancy)
- User-level permissions
- CSRF protection
- SQL injection protection (ORM)
- XSS protection (template escaping)

### File Security
- Validated file uploads
- File type restrictions
- Size limits
- Secure file storage

## Performance Considerations

### Database Optimization
- Indexed fields (employee_id, company, dates)
- Select_related for foreign keys
- Prefetch_related for M2M
- Query optimization with annotations

### Caching Strategy
- Static file caching
- Template fragment caching (future)
- Database query caching (future)

### Static Files
- Collected in `/staticfiles/`
- CDN ready (future)
- Compressed assets (future)

## Deployment Architecture (AWS)

### Recommended AWS Services
- **EC2**: Application server
- **RDS**: PostgreSQL database
- **S3**: Media and static file storage
- **CloudFront**: CDN for static files
- **Route 53**: DNS management
- **ELB**: Load balancing
- **CloudWatch**: Monitoring and logs
- **SES**: Email service

### Environment Configuration
- Development: SQLite, DEBUG=True
- Staging: PostgreSQL, DEBUG=True
- Production: PostgreSQL, DEBUG=False, HTTPS

## Monitoring & Logging

### Application Logs
- Django logging framework
- Error tracking
- User activity logs
- Audit trails

### Metrics
- User activity
- System performance
- Database queries
- API response times

## Backup Strategy

### Database Backups
- Daily automated backups
- Point-in-time recovery
- Backup retention: 30 days

### Media Files
- S3 versioning
- Cross-region replication

## Scalability

### Horizontal Scaling
- Stateless application design
- Load balancer ready
- Session storage (Redis/Memcached)

### Vertical Scaling
- Database optimization
- Query performance tuning
- Connection pooling

## Future Enhancements

### Planned Features
- Real-time notifications (WebSockets)
- Mobile app (React Native)
- Advanced analytics (ML/AI)
- API v2 (REST/GraphQL)
- Microservices architecture
- Kubernetes deployment

### Integration Opportunities
- Third-party payroll systems
- Biometric attendance devices
- Calendar sync (Google/Outlook)
- SSO (SAML, OAuth)
- Accounting software integration

## Development Workflow

### Version Control
- Git repository
- Feature branches
- Pull request reviews
- Semantic versioning

### Testing
- Unit tests (Django TestCase)
- Integration tests
- End-to-end tests (Selenium)
- Load testing

### CI/CD Pipeline
- Automated testing
- Code quality checks
- Automated deployment
- Rollback capability

## Documentation

### Code Documentation
- Docstrings for functions/classes
- Inline comments for complex logic
- README files per module

### User Documentation
- User guides per role
- Admin documentation
- API documentation
- Deployment guides

---

**Last Updated**: February 14, 2026
**Version**: 1.0
**Maintained By**: BLU Suite Development Team
