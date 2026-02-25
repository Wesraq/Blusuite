from rest_framework import status, permissions, generics, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from datetime import timedelta

from tenant_management.permissions import IsTenantMember, IsTenantAdmin

from .models import Attendance, LeaveRequest
from .serializers import (
    AttendanceSerializer,
    LeaveRequestSerializer,
    AttendanceReportSerializer,
    CheckInOutSerializer
)

User = get_user_model()


class CheckInView(APIView):
    """View for employees to check in"""
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    
    def post(self, request):
        user = request.user
        today = timezone.now().date()
        
        # Check if user has already checked in today
        tenant = getattr(request, 'tenant', None)
        existing_attendance = Attendance.objects.filter(
            employee=user,
            date=today
        ).first()
        
        if existing_attendance and existing_attendance.check_in:
            return Response(
                {"detail": _("You have already checked in today.")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = CheckInOutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Create or update attendance record
        attendance_data = {
            'check_in': timezone.now(),
            'location': serializer.validated_data.get('location', ''),
            'latitude': serializer.validated_data.get('latitude'),
            'longitude': serializer.validated_data.get('longitude'),
        }
        
        if existing_attendance:
            serializer = AttendanceSerializer(existing_attendance, data=attendance_data, partial=True, context={'request': request})
        else:
            attendance_data['employee'] = user.id
            attendance_data['date'] = today
            serializer = AttendanceSerializer(data=attendance_data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckOutView(APIView):
    """View for employees to check out"""
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    
    def post(self, request):
        user = request.user
        today = timezone.now().date()
        
        # Get today's attendance record
        attendance = Attendance.objects.filter(
            employee=user,
            date=today
        ).first()
        
        if not attendance:
            return Response(
                {"detail": _("You need to check in first.")},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if attendance.check_out:
            return Response(
                {"detail": _("You have already checked out today.")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = CheckInOutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Update attendance with check-out time
        attendance.check_out = timezone.now()
        attendance.save()
        
        return Response(
            AttendanceSerializer(attendance, context={'request': request}).data,
            status=status.HTTP_200_OK
        )


class AttendanceListView(generics.ListAPIView):
    """View to list attendance records"""
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employee__first_name', 'employee__last_name', 'status']
    ordering_fields = ['date', 'check_in', 'check_out', 'status']
    
    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, 'tenant', None)
        queryset = Attendance.objects.filter(tenant=tenant) if tenant else Attendance.objects.none()

        if user.role == User.Role.EMPLOYEE:
            queryset = queryset.filter(employee=user)
        elif user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            queryset = queryset.filter(employee__company=user.company)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        return queryset.order_by('-date', '-check_in')


class AttendanceDetailView(generics.RetrieveUpdateAPIView):
    """View to retrieve or update an attendance record"""
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        user = self.request.user
        queryset = Attendance.objects.filter(tenant=tenant) if tenant else Attendance.objects.none()
        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(employee=user)
        if user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            return queryset.filter(employee__company=user.company)
        return queryset


class LeaveRequestListView(generics.ListCreateAPIView):
    """View to list and create leave requests"""
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employee__first_name', 'employee__last_name', 'status', 'leave_type']
    ordering_fields = ['start_date', 'end_date', 'status', 'created_at']
    
    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, 'tenant', None)
        queryset = LeaveRequest.objects.filter(tenant=tenant) if tenant else LeaveRequest.objects.none()
        if user.role == User.Role.EMPLOYEE:
            queryset = queryset.filter(employee=user)
        elif user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            queryset = queryset.filter(employee__company=user.company)
        
        # Filter by status if provided
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
            
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date and end_date:
            queryset = queryset.filter(
                Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
            )
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(employee=self.request.user)


class LeaveRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a leave request"""
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        user = self.request.user
        queryset = LeaveRequest.objects.filter(tenant=tenant) if tenant else LeaveRequest.objects.none()
        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(employee=user)
        if user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            return queryset.filter(employee__company=user.company)
        return queryset
    
    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        
        # Only allow status update for employers/admins
        if user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN] and 'status' in self.request.data:
            status = self.request.data['status']
            if status == 'APPROVED':
                serializer.save(
                    status=status,
                    approved_by=user,
                    approved_at=timezone.now()
                )
                return
            elif status == 'REJECTED' and 'rejection_reason' in self.request.data:
                serializer.save(
                    status=status,
                    approved_by=user,
                    rejection_reason=self.request.data['rejection_reason']
                )
                return
        
        # Employees can only update their own leave requests if status is PENDING
        if instance.status == 'PENDING' and 'status' not in self.request.data:
            serializer.save()


class AttendanceReportView(APIView):
    """View to generate attendance reports"""
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    
    def post(self, request):
        user = request.user
        serializer = AttendanceReportSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee = serializer.validated_data['employee']
        start_date = serializer.validated_data['start_date']
        end_date = serializer.validated_data['end_date']
        
        # Check permissions
        if user.role == User.Role.EMPLOYEE and user != employee:
            return Response(
                {"detail": _("You can only view your own attendance.")},
                status=status.HTTP_403_FORBIDDEN
            )
        elif user.role == User.Role.EMPLOYER and employee.employer_profile.user != user:
            return Response(
                {"detail": _("You can only view attendance of your employees.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get attendance data
        tenant = getattr(request, 'tenant', None)
        attendance_data = Attendance.objects.filter(
            employee=employee,
            tenant=tenant,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Calculate summary statistics
        total_days = (end_date - start_date).days + 1
        present_days = attendance_data.filter(status='PRESENT').count()
        late_days = attendance_data.filter(status='LATE').count()
        absent_days = attendance_data.filter(status='ABSENT').count()
        leave_days = attendance_data.filter(status='ON_LEAVE').count()
        half_days = attendance_data.filter(status='HALF_DAY').count()
        
        # Calculate working hours
        working_hours = sum(
            att.working_hours for att in attendance_data 
            if att.working_hours is not None
        )
        
        # Prepare response
        response_data = {
            'employee': f"{employee.get_full_name()} ({employee.email})",
            'period': f"{start_date} to {end_date}",
            'total_days': total_days,
            'present_days': present_days,
            'late_days': late_days,
            'absent_days': absent_days,
            'leave_days': leave_days,
            'half_days': half_days,
            'working_hours': round(working_hours, 2),
            'attendance': AttendanceSerializer(attendance_data, many=True).data
        }
        
        return Response(response_data)


class DashboardStatsView(APIView):
    """View to get dashboard statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        
        if user.role == User.Role.EMPLOYEE:
            # Employee dashboard stats
            attendance_today = Attendance.objects.filter(
                employee=user,
                date=today
            ).first()
            
            # Weekly attendance
            weekly_attendance = Attendance.objects.filter(
                employee=user,
                date__range=[start_of_week, today]
            ).order_by('date')
            
            # Pending leave requests
            pending_leaves = LeaveRequest.objects.filter(
                employee=user,
                status='PENDING'
            ).count()
            
            # Prepare response
            response_data = {
                'today_status': AttendanceSerializer(attendance_today).data if attendance_today else None,
                'weekly_summary': {
                    'present': weekly_attendance.filter(status='PRESENT').count(),
                    'late': weekly_attendance.filter(status='LATE').count(),
                    'absent': weekly_attendance.filter(status='ABSENT').count(),
                    'on_leave': weekly_attendance.filter(status='ON_LEAVE').count(),
                },
                'pending_leaves': pending_leaves,
                'upcoming_leaves': LeaveRequestSerializer(
                    LeaveRequest.objects.filter(
                        employee=user,
                        status='APPROVED',
                        start_date__gte=today
                    ).order_by('start_date')[:5],
                    many=True
                ).data
            }
            
        else:  # Employer/Admin dashboard
            # Get employees
            if user.role == User.Role.EMPLOYER:
                employees = User.objects.filter(
                    role=User.Role.EMPLOYEE,
                    employer_profile__user=user
                )
            else:  # Admin
                employees = User.objects.filter(role=User.Role.EMPLOYEE)
            
            # Today's attendance
            today_attendance = Attendance.objects.filter(
                employee__in=employees,
                date=today
            ).select_related('employee')
            
            # Pending leave requests
            pending_leaves = LeaveRequest.objects.filter(
                employee__in=employees,
                status='PENDING'
            ).count()
            
            # Prepare response
            response_data = {
                'total_employees': employees.count(),
                'present_today': today_attendance.filter(
                    status__in=['PRESENT', 'LATE', 'HALF_DAY']
                ).count(),
                'on_leave_today': today_attendance.filter(
                    status='ON_LEAVE'
                ).count(),
                'absent_today': employees.count() - today_attendance.count(),
                'pending_leaves': pending_leaves,
                'recent_activities': {
                    'late_arrivals': AttendanceSerializer(
                        Attendance.objects.filter(
                            employee__in=employees,
                            status='LATE',
                            date__gte=start_of_month
                        ).order_by('-date')[:5],
                        many=True
                    ).data,
                    'pending_approvals': LeaveRequestSerializer(
                        LeaveRequest.objects.filter(
                            employee__in=employees,
                            status='PENDING'
                        ).order_by('-created_at')[:5],
                        many=True
                    ).data
                }
            }
        
        return Response(response_data)
