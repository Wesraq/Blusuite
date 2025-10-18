from django.urls import path
from . import views

urlpatterns = [
    # Check-in/Check-out endpoints
    path('checkin/', views.CheckInView.as_view(), name='checkin'),
    path('checkout/', views.CheckOutView.as_view(), name='checkout'),

    # Attendance management
    path('list/', views.AttendanceListView.as_view(), name='attendance_list'),
    path('<int:pk>/', views.AttendanceDetailView.as_view(), name='attendance_detail'),

    # Leave requests
    path('leave-requests/', views.LeaveRequestListView.as_view(), name='leave_request_list'),
    path('leave-requests/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='leave_request_detail'),

    # Reports and analytics
    path('reports/', views.AttendanceReportView.as_view(), name='attendance_report'),
    path('dashboard-stats/', views.DashboardStatsView.as_view(), name='dashboard_stats'),
]
