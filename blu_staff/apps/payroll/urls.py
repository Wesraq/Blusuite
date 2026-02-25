from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    SalaryStructureViewSet,
    PayrollViewSet,
    BenefitViewSet,
    EmployeeBenefitViewSet,
    PayrollDeductionViewSet,
)

router = DefaultRouter()
router.register(r'salary-structures', SalaryStructureViewSet, basename='payroll-salary-structures')
router.register(r'payrolls', PayrollViewSet, basename='payroll-payrolls')
router.register(r'benefits', BenefitViewSet, basename='payroll-benefits')
router.register(r'employee-benefits', EmployeeBenefitViewSet, basename='payroll-employee-benefits')
router.register(r'deductions', PayrollDeductionViewSet, basename='payroll-deductions')

urlpatterns = [
    path('', include(router.urls)),
]
