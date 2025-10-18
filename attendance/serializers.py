from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Attendance, LeaveRequest

User = get_user_model()


class AttendanceSerializer(serializers.ModelSerializer):
    """Serializer for the Attendance model"""
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    working_hours = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'employee', 'employee_name', 'date', 'check_in', 'check_out',
            'status', 'notes', 'location', 'latitude', 'longitude', 'working_hours',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['employee', 'status', 'created_at', 'updated_at']
    
    def validate_date(self, value):
        """Validate that the attendance date is not in the future"""
        if value > timezone.now().date():
            raise serializers.ValidationError("Attendance date cannot be in the future.")
        return value
    
    def validate_check_in(self, value):
        """Validate check-in time"""
        if value and value > timezone.now():
            raise serializers.ValidationError("Check-in time cannot be in the future.")
        return value
    
    def validate_check_out(self, value):
        """Validate check-out time"""
        if value and 'check_in' in self.initial_data and value < self.initial_data['check_in']:
            raise serializers.ValidationError("Check-out time must be after check-in time.")
        return value
    
    def create(self, validated_data):
        """Set the employee to the current user"""
        validated_data['employee'] = self.context['request'].user
        return super().create(validated_data)


class LeaveRequestSerializer(serializers.ModelSerializer):
    """Serializer for the LeaveRequest model"""
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    duration_days = serializers.IntegerField(source='duration', read_only=True)
    
    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_name', 'leave_type', 'start_date', 'end_date',
            'reason', 'status', 'approved_by', 'approved_by_name', 'approved_at',
            'rejection_reason', 'duration_days', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'employee', 'status', 'approved_by', 'approved_at', 'created_at', 'updated_at'
        ]
    
    def validate_start_date(self, value):
        """Validate start date"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Start date cannot be in the past.")
        return value
    
    def validate(self, data):
        """Validate that end date is after start date"""
        if 'start_date' in data and 'end_date' in data and data['start_date'] > data['end_date']:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        return data
    
    def create(self, validated_data):
        """Set the employee to the current user"""
        validated_data['employee'] = self.context['request'].user
        return super().create(validated_data)


class AttendanceReportSerializer(serializers.Serializer):
    """Serializer for attendance reports"""
    employee = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.EMPLOYEE))
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    def validate(self, data):
        """Validate date range"""
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("End date must be after start date.")
        
        # Limit date range to 1 year
        if (data['end_date'] - data['start_date']).days > 365:
            raise serializers.ValidationError("Date range cannot exceed 1 year.")
            
        return data


class CheckInOutSerializer(serializers.Serializer):
    """Serializer for check-in/check-out operations"""
    latitude = serializers.DecimalField(
        max_digits=9, 
        decimal_places=6,
        required=False,
        allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, 
        decimal_places=6,
        required=False,
        allow_null=True
    )
    location = serializers.CharField(
        max_length=255, 
        required=False, 
        allow_blank=True
    )
    
    def validate(self, data):
        """Validate that either both or none of latitude/longitude are provided"""
        has_lat = 'latitude' in data and data['latitude'] is not None
        has_lng = 'longitude' in data and data['longitude'] is not None
        
        if has_lat != has_lng:
            raise serializers.ValidationError(
                "Both latitude and longitude must be provided together."
            )
            
        return data
