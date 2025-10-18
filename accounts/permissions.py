from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()

class IsEmployerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow employers or admins to access the view.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            (request.user.role in ['ADMIN', 'EMPLOYER_SUPERUSER', 'EMPLOYER_ADMIN'])
        )


class IsEmployeeOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow employees to edit their own data.
    Read only is allowed for unauthenticated users.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to authenticated employees.
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'EMPLOYEE'
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to edit it.
    Assumes the model instance has an `employee` attribute.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to the owner of the object or admin.
        is_owner = False
        if hasattr(obj, 'employee'):
            is_owner = obj.employee == request.user
        elif hasattr(obj, 'user'):
            is_owner = obj.user == request.user
            
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (is_owner or request.user.role == 'ADMIN')
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    Read only is allowed for unauthenticated users.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to admins.
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'ADMIN'
        )
