from django.urls import path
from . import views

urlpatterns = [
    # Asset Management
    path('', views.asset_list, name='asset_list'),
    path('<int:asset_id>/', views.asset_detail, name='asset_detail'),
    
    # Asset Requests
    path('requests/', views.asset_request_list, name='asset_request_list'),
    path('requests/create/', views.asset_request_create, name='asset_request_create'),
    path('requests/<int:request_id>/approve/', views.asset_request_approve, name='asset_request_approve'),
    
    # Department Dashboard
    path('department/dashboard/', views.department_asset_dashboard, name='department_asset_dashboard'),
]
