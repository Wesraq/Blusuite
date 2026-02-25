"""
Custom Report Builder
Allows dynamic creation of reports with custom fields and filters
"""
from django.db.models import Q, Count, Sum, Avg, Min, Max
from django.contrib.auth import get_user_model
from datetime import datetime, date
import csv
from io import StringIO

User = get_user_model()


class CustomReportBuilder:
    """
    Build custom reports with dynamic field selection and filtering
    """
    
    # Available report sources
    REPORT_SOURCES = {
        'employees': {
            'name': 'Employees',
            'model': 'accounts.User',
            'fields': {
                'employee_id': 'Employee ID',
                'first_name': 'First Name',
                'last_name': 'Last Name',
                'email': 'Email',
                'phone_number': 'Phone',
                'department': 'Department',
                'job_title': 'Job Title',
                'employment_type': 'Employment Type',
                'date_hired': 'Date Hired',
                'salary': 'Salary',
                'status': 'Status',
            },
            'filters': ['department', 'employment_type', 'date_hired', 'status']
        },
        'attendance': {
            'name': 'Attendance',
            'model': 'attendance.Attendance',
            'fields': {
                'employee': 'Employee',
                'date': 'Date',
                'check_in': 'Check In',
                'check_out': 'Check Out',
                'status': 'Status',
                'hours_worked': 'Hours Worked',
                'notes': 'Notes',
            },
            'filters': ['date', 'status', 'employee']
        },
        'leave_requests': {
            'name': 'Leave Requests',
            'model': 'attendance.LeaveRequest',
            'fields': {
                'employee': 'Employee',
                'leave_type': 'Leave Type',
                'start_date': 'Start Date',
                'end_date': 'End Date',
                'duration': 'Duration',
                'status': 'Status',
                'reason': 'Reason',
                'approved_by': 'Approved By',
            },
            'filters': ['leave_type', 'status', 'start_date', 'employee']
        },
        'payroll': {
            'name': 'Payroll',
            'model': 'payroll.Payroll',
            'fields': {
                'employee': 'Employee',
                'period_start': 'Period Start',
                'period_end': 'Period End',
                'gross_salary': 'Gross Salary',
                'total_deductions': 'Total Deductions',
                'net_salary': 'Net Salary',
                'status': 'Status',
            },
            'filters': ['period_start', 'period_end', 'status', 'employee']
        },
        'documents': {
            'name': 'Documents',
            'model': 'documents.EmployeeDocument',
            'fields': {
                'employee': 'Employee',
                'document_type': 'Document Type',
                'verification_status': 'Status',
                'upload_date': 'Upload Date',
                'expiry_date': 'Expiry Date',
                'verified_by': 'Verified By',
            },
            'filters': ['document_type', 'verification_status', 'expiry_date', 'employee']
        },
        'benefits': {
            'name': 'Benefits',
            'model': 'payroll.EmployeeBenefit',
            'fields': {
                'employee': 'Employee',
                'benefit': 'Benefit Name',
                'benefit_type': 'Benefit Type',
                'enrollment_date': 'Enrollment Date',
                'effective_date': 'Effective Date',
                'status': 'Status',
                'company_contribution': 'Company Contribution',
                'employee_contribution': 'Employee Contribution',
            },
            'filters': ['benefit_type', 'status', 'enrollment_date', 'employee']
        },
        'training': {
            'name': 'Training',
            'model': 'training.TrainingEnrollment',
            'fields': {
                'employee': 'Employee',
                'program': 'Program Name',
                'enrollment_date': 'Enrollment Date',
                'completion_date': 'Completion Date',
                'status': 'Status',
                'score': 'Score',
            },
            'filters': ['program', 'status', 'enrollment_date', 'employee']
        },
    }
    
    def __init__(self, source, tenant=None):
        """
        Initialize report builder
        
        Args:
            source: Report source key (e.g., 'employees', 'attendance')
            tenant: Tenant instance for filtering
        """
        self.source = source
        self.tenant = tenant
        self.config = self.REPORT_SOURCES.get(source, {})
        self.queryset = None
    
    def build_queryset(self, filters=None):
        """
        Build queryset based on source and filters
        
        Args:
            filters: Dict of filter parameters
        
        Returns:
            QuerySet
        """
        model_path = self.config.get('model')
        if not model_path:
            return None
        
        # Import model dynamically
        app_label, model_name = model_path.split('.')
        from django.apps import apps
        model = apps.get_model(app_label, model_name)
        
        # Base queryset
        queryset = model.objects.all()
        
        # Apply tenant filter
        if self.tenant:
            tenant_filter_applied = False
            if hasattr(model, 'tenant'):
                queryset = queryset.filter(tenant=self.tenant)
                tenant_filter_applied = True
            elif hasattr(model, 'employee') and hasattr(model._meta.get_field('employee').related_model, 'company'):
                queryset = queryset.filter(employee__company__tenant=self.tenant)
                tenant_filter_applied = True
            elif hasattr(model, 'company'):
                queryset = queryset.filter(company__tenant=self.tenant)
                tenant_filter_applied = True
            elif model is User:
                queryset = queryset.filter(company__tenant=self.tenant)
                tenant_filter_applied = True

            # Fallback to empty queryset if tenant filter couldn't be applied safely
            if not tenant_filter_applied:
                queryset = queryset.none()

        # Apply custom filters
        if filters:
            queryset = self._apply_filters(queryset, filters)
        
        self.queryset = queryset
        return queryset
    
    def _apply_filters(self, queryset, filters):
        """
        Apply custom filters to queryset
        """
        for field, value in filters.items():
            if not value:
                continue
            
            if field.endswith('_from'):
                # Date range start
                base_field = field.replace('_from', '')
                queryset = queryset.filter(**{f'{base_field}__gte': value})
            
            elif field.endswith('_to'):
                # Date range end
                base_field = field.replace('_to', '')
                queryset = queryset.filter(**{f'{base_field}__lte': value})
            
            elif field == 'search':
                # Text search
                search_fields = ['first_name', 'last_name', 'email']
                q_objects = Q()
                for search_field in search_fields:
                    q_objects |= Q(**{f'{search_field}__icontains': value})
                queryset = queryset.filter(q_objects)
            
            else:
                # Exact match
                queryset = queryset.filter(**{field: value})
        
        return queryset
    
    def get_data(self, selected_fields=None):
        """
        Get report data
        
        Args:
            selected_fields: List of field keys to include
        
        Returns:
            List of dicts with report data
        """
        if not self.queryset:
            return []
        
        if not selected_fields:
            selected_fields = list(self.config.get('fields', {}).keys())
        
        data = []
        for obj in self.queryset:
            row = {}
            for field in selected_fields:
                row[field] = self._get_field_value(obj, field)
            data.append(row)
        
        return data
    
    def _get_field_value(self, obj, field):
        """
        Get field value from object
        """
        if field == 'employee':
            return obj.employee.get_full_name() if hasattr(obj, 'employee') else ''
        
        elif field in ['approved_by', 'verified_by']:
            approver = getattr(obj, field, None)
            return approver.get_full_name() if approver else 'N/A'
        
        elif field == 'benefit':
            return obj.benefit.name if hasattr(obj, 'benefit') else ''
        
        elif field == 'program':
            return obj.program.name if hasattr(obj, 'program') else ''
        
        elif field == 'benefit_type':
            if hasattr(obj, 'benefit') and hasattr(obj.benefit, 'get_benefit_type_display'):
                return obj.benefit.get_benefit_type_display()
            return ''
        
        elif field == 'company_contribution':
            if hasattr(obj, 'benefit'):
                return str(obj.benefit.company_contribution)
            return ''
        
        elif field == 'employee_contribution':
            if hasattr(obj, 'benefit'):
                return str(obj.benefit.employee_contribution)
            return ''
        
        elif hasattr(obj, 'employee_profile'):
            # Try to get from employee profile
            profile_value = getattr(obj.employee_profile, field, None)
            if profile_value is not None:
                return str(profile_value)
        
        # Get direct field value
        value = getattr(obj, field, '')
        
        # Format based on type
        if isinstance(value, date):
            return value.strftime('%Y-%m-%d')
        elif isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M')
        elif value is None:
            return ''
        
        return str(value)
    
    def export_to_csv(self, selected_fields=None):
        """
        Export report to CSV
        
        Returns:
            CSV string
        """
        data = self.get_data(selected_fields)
        if not data:
            return ''
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    def get_statistics(self):
        """
        Calculate statistics for the report
        
        Returns:
            Dict of statistics
        """
        if not self.queryset:
            return {}
        
        stats = {
            'total_records': self.queryset.count(),
        }
        
        # Source-specific statistics
        if self.source == 'employees':
            stats.update({
                'active_employees': self.queryset.filter(is_active=True).count(),
                'by_department': self.queryset.values('employee_profile__department').annotate(count=Count('id')),
            })
        
        elif self.source == 'attendance':
            stats.update({
                'present_count': self.queryset.filter(status='PRESENT').count(),
                'late_count': self.queryset.filter(status='LATE').count(),
                'absent_count': self.queryset.filter(status='ABSENT').count(),
            })
        
        elif self.source == 'leave_requests':
            stats.update({
                'approved': self.queryset.filter(status='APPROVED').count(),
                'pending': self.queryset.filter(status='PENDING').count(),
                'rejected': self.queryset.filter(status='REJECTED').count(),
                'total_days': self.queryset.aggregate(total=Sum('duration'))['total'] or 0,
            })
        
        elif self.source == 'payroll':
            stats.update({
                'total_gross': self.queryset.aggregate(total=Sum('gross_salary'))['total'] or 0,
                'total_deductions': self.queryset.aggregate(total=Sum('total_deductions'))['total'] or 0,
                'total_net': self.queryset.aggregate(total=Sum('net_salary'))['total'] or 0,
            })
        
        return stats


def generate_custom_report(source, tenant, filters=None, selected_fields=None):
    """
    Convenience function to generate a custom report
    
    Args:
        source: Report source
        tenant: Tenant instance used for scoping
        filters: Dict of filters
        selected_fields: List of fields to include
    
    Returns:
        Dict with data and statistics
    """
    builder = CustomReportBuilder(source, tenant)
    builder.build_queryset(filters)
    
    return {
        'data': builder.get_data(selected_fields),
        'statistics': builder.get_statistics(),
        'csv': builder.export_to_csv(selected_fields),
    }
