from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # Support Center
    path('center/', views.superadmin_support_center, name='superadmin_support_center'),
    
    # Ticket Management
    path('tickets/', views.SupportTicketListView.as_view(), name='superadmin_tickets'),
    path('tickets/<int:pk>/', views.SupportTicketDetailView.as_view(), name='superadmin_ticket_detail'),
    path('tickets/<int:ticket_id>/assign/', views.assign_ticket, name='assign_ticket'),
    path('tickets/<int:ticket_id>/update-status/', views.update_ticket_status, name='update_ticket_status'),
    
    # Team Management
    path('team/', views.SupportTeamListView.as_view(), name='superadmin_support_team'),
    
    # Categories
    path('categories/', views.SupportCategoryListView.as_view(), name='superadmin_categories'),
    
    # Analytics
    path('analytics/', views.support_analytics, name='support_analytics'),
]
