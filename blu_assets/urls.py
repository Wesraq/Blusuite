from django.urls import path
from . import views

urlpatterns = [
    # AMS Dashboard
    path('', views.ams_dashboard, name='ams_dashboard'),
    
    # Asset Registry
    path('registry/', views.asset_list, name='asset_list'),
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('<int:asset_id>/', views.asset_detail, name='asset_detail'),
    path('create/', views.asset_create, name='asset_create'),
    path('<int:asset_id>/edit/', views.asset_edit, name='asset_edit'),
    path('<int:asset_id>/assign/', views.asset_assign, name='asset_assign'),
    path('<int:asset_id>/unassign/', views.asset_unassign, name='asset_unassign'),
    path('<int:asset_id>/return/', views.asset_return, name='asset_return'),
    path('<int:asset_id>/repair/', views.asset_send_to_repair, name='asset_send_to_repair'),
    path('<int:asset_id>/maintenance/add/', views.maintenance_create, name='asset_maintenance_add'),
    path('<int:asset_id>/assignment-document/', views.asset_assignment_document, name='asset_assignment_document'),
    path('<int:asset_id>/collection/add/', views.asset_collection_create, name='asset_collection_add'),
    path('<int:asset_id>/collection/<int:collection_id>/print/', views.asset_collection_print, name='asset_collection_print'),
    
    # Asset Requests
    path('requests/', views.asset_request_list, name='asset_request_list'),
    path('requests/create/', views.asset_request_create, name='asset_request_create'),
    path('requests/<int:request_id>/', views.asset_request_detail, name='asset_request_detail'),
    path('requests/<int:request_id>/approve/', views.asset_request_approve, name='asset_request_approve'),
    
    # Department Dashboard
    path('department/dashboard/', views.department_asset_dashboard, name='department_asset_dashboard'),

    # Settings
    path('settings/', views.ams_settings, name='ams_settings'),
]
