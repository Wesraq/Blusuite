from django.urls import path
from . import frontend_views as views

urlpatterns = [
    # Training Programs
    path('', views.training_list, name='training_list'),
    path('<int:program_id>/', views.training_detail, name='training_detail'),
    path('<int:program_id>/enroll/', views.training_enroll, name='training_enroll'),
    path('my-training/', views.my_training, name='my_training'),
    
    # Training Requests
    path('requests/', views.training_request_list, name='training_request_list'),
    path('requests/create/', views.training_request_create, name='training_request_create'),
    path('requests/<int:request_id>/approve/', views.training_request_approve, name='training_request_approve'),
    
    # Department Dashboard
    path('department/dashboard/', views.department_training_dashboard, name='department_training_dashboard'),
]
