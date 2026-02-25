from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .serializers import (
    UserSerializer, EmployeeProfileSerializer, EmployerProfileSerializer,
    AttendanceSerializer, LeaveRequestSerializer,
    DocumentCategorySerializer, EmployeeDocumentSerializer, DocumentTemplateSerializer, DocumentAccessLogSerializer,
    PerformanceReviewSerializer, PerformanceGoalSerializer, PerformanceMetricSerializer,
    PerformanceFeedbackSerializer, PerformanceTemplateSerializer
)

from blu_staff.apps.accounts.models import EmployeeProfile, EmployerProfile
from blu_staff.apps.attendance.models import Attendance, LeaveRequest
from blu_staff.apps.documents.models import DocumentCategory, EmployeeDocument, DocumentTemplate, DocumentAccessLog
from blu_staff.apps.performance.models import (
    PerformanceReview, PerformanceGoal, PerformanceMetric,
    PerformanceFeedback, PerformanceTemplate
)

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter users based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(id=user.id)
        elif user.role == 'EMPLOYER':
            return queryset.filter(
                Q(employer_profile__user=user) |
                Q(employee_profile__user__employer_profile__user=user)
            )
        # Admin sees all users
        return queryset

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for Employee Profile"""
    queryset = EmployeeProfile.objects.all()
    serializer_class = EmployeeProfileSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter employee profiles based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(user=user)
        elif user.role == 'EMPLOYER':
            return queryset.filter(user__employer_profile__user=user)
        # Admin sees all profiles
        return queryset


class EmployerProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for Employer Profile"""
    queryset = EmployerProfile.objects.all()
    serializer_class = EmployerProfileSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter employer profiles based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYER':
            return queryset.filter(user=user)
        # Admin sees all profiles
        return queryset


class AttendanceViewSet(viewsets.ModelViewSet):
    """ViewSet for Attendance model"""
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter attendance records based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(employee=user)
        elif user.role == 'EMPLOYER':
            return queryset.filter(employee__employer_profile__user=user)
        # Admin sees all records
        return queryset

    @action(detail=False, methods=['post'])
    def check_in(self, request):
        """Check in employee"""
        if request.user.role != 'EMPLOYEE':
            return Response(
                {'error': 'Only employees can check in'},
                status=status.HTTP_403_FORBIDDEN
            )

        today = timezone.now().date()
        existing = self.get_queryset().filter(
            employee=request.user,
            date=today,
            check_in__isnull=False
        ).first()

        if existing:
            return Response(
                {'error': 'Already checked in today'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attendance = Attendance.objects.create(
            employee=request.user,
            date=today,
            check_in=timezone.now()
        )

        serializer = self.get_serializer(attendance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def check_out(self, request):
        """Check out employee"""
        if request.user.role != 'EMPLOYEE':
            return Response(
                {'error': 'Only employees can check out'},
                status=status.HTTP_403_FORBIDDEN
            )

        today = timezone.now().date()
        attendance = self.get_queryset().filter(
            employee=request.user,
            date=today,
            check_in__isnull=False,
            check_out__isnull=True
        ).first()

        if not attendance:
            return Response(
                {'error': 'No check-in found for today'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attendance.check_out = timezone.now()
        attendance.working_hours = (
            attendance.check_out - attendance.check_in
        ).total_seconds() / 3600
        attendance.save()

        serializer = self.get_serializer(attendance)
        return Response(serializer.data)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for Leave Request model"""
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter leave requests based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(employee=user)
        elif user.role == 'EMPLOYER':
            return queryset.filter(employee__employer_profile__user=user)
        # Admin sees all requests
        return queryset

    def perform_create(self, serializer):
        """Set employee when creating leave request"""
        serializer.save(employee=self.request.user)


class DocumentCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Document Category"""
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for Employee Document"""
    queryset = EmployeeDocument.objects.all()
    serializer_class = EmployeeDocumentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter documents based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(employee=user)
        elif user.role == 'EMPLOYER':
            return queryset.filter(employee__employer_profile__user=user)
        # Admin sees all documents
        return queryset

    def perform_create(self, serializer):
        """Set uploaded_by when creating document"""
        serializer.save(uploaded_by=self.request.user)


class DocumentTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for Document Template"""
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter templates based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYER':
            return queryset.filter(created_by=user)
        # Admin sees all templates
        return queryset

    def perform_create(self, serializer):
        """Set created_by when creating template"""
        serializer.save(created_by=self.request.user)


class PerformanceReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for Performance Review"""
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter reviews based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(employee=user)
        elif user.role == 'EMPLOYER':
            return queryset.filter(employee__employer_profile__user=user)
        # Admin sees all reviews
        return queryset

    def perform_create(self, serializer):
        """Set reviewer when creating review"""
        serializer.save(reviewer=self.request.user)


class PerformanceGoalViewSet(viewsets.ModelViewSet):
    """ViewSet for Performance Goal"""
    queryset = PerformanceGoal.objects.all()
    serializer_class = PerformanceGoalSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter goals based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(review__employee=user)
        elif user.role == 'EMPLOYER':
            return queryset.filter(review__employee__employer_profile__user=user)
        # Admin sees all goals
        return queryset


class PerformanceMetricViewSet(viewsets.ModelViewSet):
    """ViewSet for Performance Metric"""
    queryset = PerformanceMetric.objects.all()
    serializer_class = PerformanceMetricSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter metrics based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(review__employee=user)
        elif user.role == 'EMPLOYER':
            return queryset.filter(review__employee__employer_profile__user=user)
        # Admin sees all metrics
        return queryset


class PerformanceFeedbackViewSet(viewsets.ModelViewSet):
    """ViewSet for Performance Feedback"""
    queryset = PerformanceFeedback.objects.all()
    serializer_class = PerformanceFeedbackSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter feedback based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYEE':
            return queryset.filter(review__employee=user)
        elif user.role == 'EMPLOYER':
            return queryset.filter(review__employee__employer_profile__user=user)
        # Admin sees all feedback
        return queryset

    def perform_create(self, serializer):
        """Set provided_by when creating feedback"""
        serializer.save(provided_by=self.request.user)


class PerformanceTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for Performance Template"""
    queryset = PerformanceTemplate.objects.all()
    serializer_class = PerformanceTemplateSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter templates based on role"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'EMPLOYER':
            return queryset.filter(created_by=user)
        # Admin sees all templates
        return queryset

    def perform_create(self, serializer):
        """Set created_by when creating template"""
        serializer.save(created_by=self.request.user)
