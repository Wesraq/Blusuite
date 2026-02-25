from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for viewsets
router = DefaultRouter()
# router.register(r'categories', DocumentCategoryViewSet)
# router.register(r'documents', EmployeeDocumentViewSet)
# router.register(r'templates', DocumentTemplateViewSet)
# router.register(r'access-logs', DocumentAccessLogViewSet)

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Document upload URLs
    path('company/upload/', views.upload_company_document, name='upload_company_document'),
    path('employee/upload/', views.upload_employee_document, name='upload_employee_document'),
]
