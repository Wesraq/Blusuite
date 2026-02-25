from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    RequestTypeViewSet,
    EmployeeRequestViewSet,
    RequestApprovalViewSet,
    RequestCommentViewSet,
    PettyCashRequestViewSet,
    AdvanceRequestViewSet,
    ReimbursementRequestViewSet,
)

router = DefaultRouter()
router.register(r'types', RequestTypeViewSet, basename='requests-types')
router.register(r'employee', EmployeeRequestViewSet, basename='requests-employee')
router.register(r'approvals', RequestApprovalViewSet, basename='requests-approvals')
router.register(r'comments', RequestCommentViewSet, basename='requests-comments')
router.register(r'petty-cash', PettyCashRequestViewSet, basename='requests-petty-cash')
router.register(r'advances', AdvanceRequestViewSet, basename='requests-advances')
router.register(r'reimbursements', ReimbursementRequestViewSet, basename='requests-reimbursements')

urlpatterns = [
    path('', include(router.urls)),
]
