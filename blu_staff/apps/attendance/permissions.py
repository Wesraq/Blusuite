from rest_framework import permissions
from django.utils.translation import gettext_lazy as _

class IsEmployerOrAdmin(permissions.BasePermission):
    """
    Permission class to check if the user is an employer or admin.
    """
    message = _('You must be an employer or admin to perform this action.')
    
    def has_permission(self, request, view):
        allowed_roles = {'EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN', 'ADMINISTRATOR', 'SUPERADMIN'}
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role in allowed_roles
        )


class IsEmployeeOrReadOnly(permissions.BasePermission):
    """
    Permission class to allow only employees to perform write operations.
    Read operations are allowed for all authenticated users.
    """
    message = _('You must be an employee to perform this action.')
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role == 'EMPLOYEE'
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission class to check if the user is the owner of the object or an admin.
    """
    message = _('You do not have permission to perform this action.')
    
    def has_object_permission(self, request, view, obj):
        # Administrative roles can manage any record
        admin_roles = {'SUPERADMIN', 'ADMINISTRATOR', 'EMPLOYER_ADMIN', 'EMPLOYER_SUPERUSER'}
        if request.user.role in admin_roles:
            return True
            
        # For attendance and leave request objects
        if hasattr(obj, 'employee'):
            # Object has an employee field (Attendance, LeaveRequest)
            if obj.employee == request.user:
                return True
            
            # Check if the user is the employer of the employee
            if hasattr(obj.employee, 'employer_profile') and obj.employee.employer_profile.user == request.user:
                return True
                
        # For user objects
        if obj == request.user:
            return True
            
        return False
