from django.urls import path, include
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken import views as auth_views
from . import views as account_views
from ems_project.views import (
    UserViewSet, EmployeeProfileViewSet, EmployerProfileViewSet
)
from .views import employee_list, create_employee

# Create router for viewsets
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'employee-profiles', EmployeeProfileViewSet)
router.register(r'employer-profiles', EmployerProfileViewSet)

urlpatterns = [
    # Authentication - Custom login that returns role info
    path('login/', account_views.CustomLoginView.as_view(), name='login'),
    # Legacy endpoint (kept for backward compatibility)
    path('register/', auth_views.obtain_auth_token, name='register'),

    # Include router URLs
    path('', include(router.urls)),
    
    # Employees list
    path('employees/', employee_list, name='employee_list'),
    path('employees/create/', create_employee, name='create_employee'),

    path('company/<int:company_id>/', account_views.company_profile, name='company_profile'),
]
