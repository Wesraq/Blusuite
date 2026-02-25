from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from blu_staff.apps.accounts.models import User, EmployeeProfile, EmployerProfile
from blu_staff.apps.attendance.models import Attendance, LeaveRequest
from blu_staff.apps.documents.models import EmployeeDocument
from blu_staff.apps.performance.models import PerformanceReview


class DashboardAdminSite(admin.AdminSite):
    """Custom admin site with dashboard"""

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
        ]
        return custom_urls + urls

    def dashboard_view(self, request):
        """Custom dashboard view with statistics"""

        # Get statistics
        user_count = User.objects.count()
        employee_count = User.objects.filter(role='EMPLOYEE').count()
        employer_count = User.objects.filter(role='EMPLOYER_ADMIN').count()
        admin_count = User.objects.filter(role='ADMINISTRATOR').count()
        superadmin_count = User.objects.filter(role='SUPERADMIN').count()

        # Attendance stats
        attendance_count = Attendance.objects.count()
        today_attendance = Attendance.objects.filter(date=timezone.now().date()).count()
        present_today = Attendance.objects.filter(
            date=timezone.now().date(),
            status='PRESENT'
        ).count()

        # Document stats
        document_count = EmployeeDocument.objects.count()
        approved_docs = EmployeeDocument.objects.filter(status='APPROVED').count()
        pending_docs = EmployeeDocument.objects.filter(status='PENDING').count()

        # Performance stats
        review_count = PerformanceReview.objects.count()
        completed_reviews = PerformanceReview.objects.filter(status='COMPLETED').count()
        in_progress_reviews = PerformanceReview.objects.filter(status='IN_PROGRESS').count()

        # Leave requests
        leave_count = LeaveRequest.objects.count()
        pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()
        approved_leaves = LeaveRequest.objects.filter(status='APPROVED').count()

        # Recent activity
        recent_attendance = Attendance.objects.order_by('-created_at')[:5]
        recent_reviews = PerformanceReview.objects.order_by('-created_at')[:5]
        recent_documents = EmployeeDocument.objects.order_by('-created_at')[:5]

        context = {
            'title': 'EMS Dashboard',
            'user_count': user_count,
            'employee_count': employee_count,
            'employer_count': employer_count,
            'admin_count': admin_count,
            'superadmin_count': superadmin_count,
            'attendance_count': attendance_count,
            'today_attendance': today_attendance,
            'present_today': present_today,
            'document_count': document_count,
            'approved_docs': approved_docs,
            'pending_docs': pending_docs,
            'review_count': review_count,
            'completed_reviews': completed_reviews,
            'in_progress_reviews': in_progress_reviews,
            'leave_count': leave_count,
            'pending_leaves': pending_leaves,
            'approved_leaves': approved_leaves,
            'recent_attendance': recent_attendance,
            'recent_reviews': recent_reviews,
            'recent_documents': recent_documents,
            'server_time': timezone.now(),
        }

        return render(request, 'admin/dashboard.html', context)


# Create custom admin site instance
dashboard_admin = DashboardAdminSite(name='dashboard_admin')
