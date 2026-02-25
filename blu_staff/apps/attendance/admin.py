from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Attendance, LeaveRequest

User = get_user_model()


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    """Admin interface for Attendance model"""
    list_display = ['employee', 'date', 'check_in', 'check_out', 'status', 'working_hours']
    list_filter = ['status', 'date', 'employee__role']
    search_fields = ['employee__email', 'employee__first_name', 'employee__last_name']
    ordering = ['-date', '-check_in']
    readonly_fields = ['created_at', 'updated_at', 'working_hours']

    fieldsets = (
        ('Employee Information', {
            'fields': ('employee',)
        }),
        ('Attendance Details', {
            'fields': ('date', 'check_in', 'check_out', 'status', 'notes')
        }),
        ('Location Information', {
            'fields': ('location', 'latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at', 'working_hours'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter queryset based on user role"""
        qs = super().get_queryset(request)
        if request.user.role == 'EMPLOYEE':
            qs = qs.filter(employee=request.user)
        elif request.user.role == 'EMPLOYER':
            qs = qs.filter(employee__employer_profile__user=request.user)
        # Admin sees all records
        return qs


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    """Admin interface for LeaveRequest model"""
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'status', 'duration']
    list_filter = ['status', 'leave_type', 'start_date', 'employee__role']
    search_fields = ['employee__email', 'employee__first_name', 'employee__last_name', 'reason']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'duration', 'approved_at']

    fieldsets = (
        ('Employee Information', {
            'fields': ('employee',)
        }),
        ('Leave Details', {
            'fields': ('leave_type', 'start_date', 'end_date', 'reason')
        }),
        ('Approval Information', {
            'fields': ('status', 'approved_by', 'approved_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at', 'duration'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter queryset based on user role"""
        qs = super().get_queryset(request)
        if request.user.role == 'EMPLOYEE':
            qs = qs.filter(employee=request.user)
        elif request.user.role == 'EMPLOYER':
            qs = qs.filter(employee__employer_profile__user=request.user)
        # Admin sees all records
        return qs

    def save_model(self, request, obj, form, change):
        """Set approved_by when status is changed to approved"""
        if obj.status == 'APPROVED' and not obj.approved_by:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)
