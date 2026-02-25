from rest_framework import status, permissions, generics, filters, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db.models import Avg
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from tenant_management.permissions import IsTenantMember, IsTenantAdmin

from .models import (
    PerformanceReview, PerformanceGoal, PerformanceMetric,
    PerformanceFeedback, PerformanceTemplate
)
from .serializers import (
    PerformanceReviewSerializer, PerformanceGoalSerializer,
    PerformanceMetricSerializer, PerformanceFeedbackSerializer,
    PerformanceTemplateSerializer, PerformanceStatsSerializer
)

User = get_user_model()


class PerformanceReviewListCreateView(generics.ListCreateAPIView):
    """View to list and create performance reviews"""
    serializer_class = PerformanceReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'employee__first_name', 'employee__last_name']
    ordering_fields = ['review_date', 'created_at', 'overall_rating']
    ordering = ['-review_date']

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, 'tenant', None)
        queryset = PerformanceReview.objects.filter(tenant=tenant) if tenant else PerformanceReview.objects.none()

        # Filter based on user role
        if user.role == User.Role.EMPLOYEE:
            queryset = queryset.filter(employee=user)
        elif user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            queryset = queryset.filter(employee__company=user.company)

        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by review type
        review_type = self.request.query_params.get('review_type')
        if review_type:
            queryset = queryset.filter(review_type=review_type)

        # Filter by employee
        employee_id = self.request.query_params.get('employee')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        return queryset

    def perform_create(self, serializer):
        """Set the reviewer to current user"""
        serializer.save(reviewer=self.request.user)


class PerformanceReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a performance review"""
    serializer_class = PerformanceReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, 'tenant', None)
        queryset = PerformanceReview.objects.filter(tenant=tenant) if tenant else PerformanceReview.objects.none()
        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(employee=user)
        if user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            return queryset.filter(employee__company=user.company)
        return queryset


class PerformanceGoalListCreateView(generics.ListCreateAPIView):
    """View to list and create performance goals"""
    serializer_class = PerformanceGoalSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        review_id = self.kwargs.get('review_pk')
        tenant = getattr(self.request, 'tenant', None)
        return PerformanceGoal.objects.filter(review_id=review_id, tenant=tenant)

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_pk')
        review = PerformanceReview.objects.get(pk=review_id)
        serializer.save(review=review)


class PerformanceGoalDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a performance goal"""
    serializer_class = PerformanceGoalSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        return PerformanceGoal.objects.filter(tenant=tenant) if tenant else PerformanceGoal.objects.none()


class PerformanceMetricListCreateView(generics.ListCreateAPIView):
    """View to list and create performance metrics"""
    serializer_class = PerformanceMetricSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        review_id = self.kwargs.get('review_pk')
        tenant = getattr(self.request, 'tenant', None)
        return PerformanceMetric.objects.filter(review_id=review_id, tenant=tenant)

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_pk')
        review = PerformanceReview.objects.get(pk=review_id)
        serializer.save(review=review)


class PerformanceMetricDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a performance metric"""
    serializer_class = PerformanceMetricSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        return PerformanceMetric.objects.filter(tenant=tenant) if tenant else PerformanceMetric.objects.none()


class PerformanceFeedbackListCreateView(generics.ListCreateAPIView):
    """View to list and create performance feedback"""
    serializer_class = PerformanceFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        review_id = self.kwargs.get('review_pk')
        tenant = getattr(self.request, 'tenant', None)
        return PerformanceFeedback.objects.filter(review_id=review_id, tenant=tenant)

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_pk')
        review = PerformanceReview.objects.get(pk=review_id)
        serializer.save(review=review, provided_by=self.request.user)


class PerformanceFeedbackDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete performance feedback"""
    serializer_class = PerformanceFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        return PerformanceFeedback.objects.filter(tenant=tenant) if tenant else PerformanceFeedback.objects.none()


class PerformanceTemplateListCreateView(generics.ListCreateAPIView):
    """View to list and create performance templates"""
    queryset = PerformanceTemplate.objects.filter(is_active=True)
    serializer_class = PerformanceTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        return self.queryset.filter(tenant=tenant) if tenant else PerformanceTemplate.objects.none()

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        serializer.save(created_by=self.request.user, tenant=tenant)


class PerformanceTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a performance template"""
    queryset = PerformanceTemplate.objects.all()
    serializer_class = PerformanceTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        base_queryset = self.queryset
        return base_queryset.filter(tenant=tenant) if tenant else PerformanceTemplate.objects.none()


class PerformanceStatsView(APIView):
    """View to get performance statistics"""
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def get(self, request):
        user = request.user
        tenant = getattr(request, 'tenant', None)

        # Base queryset
        if not tenant:
            return Response(PerformanceStatsSerializer({}).data)
        if user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            reviews = PerformanceReview.objects.filter(tenant=tenant, employee__company=user.company)
        else:  # Superadmin within tenant
            reviews = PerformanceReview.objects.filter(tenant=tenant)

        # Calculate statistics
        stats = {
            'total_reviews': reviews.count(),
            'completed_reviews': reviews.filter(status='COMPLETED').count(),
            'pending_reviews': reviews.filter(status__in=['DRAFT', 'SUBMITTED', 'UNDER_REVIEW']).count(),
            'average_rating': reviews.filter(overall_rating__isnull=False).aggregate(
                avg_rating=Avg('overall_rating')
            )['avg_rating'] or 0,
            'reviews_this_month': reviews.filter(
                review_date__year=timezone.now().year,
                review_date__month=timezone.now().month
            ).count(),
            'upcoming_reviews': reviews.filter(
                review_date__gte=timezone.now().date(),
                status__in=['DRAFT', 'SUBMITTED']
            ).count()
        }

        serializer = PerformanceStatsSerializer(stats)
        return Response(serializer.data)


class PerformanceDashboardView(APIView):
    """View to get performance dashboard data"""
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        user = request.user
        tenant = getattr(request, 'tenant', None)

        # Base queryset based on user role
        if not tenant:
            return Response({})
        if user.role == User.Role.EMPLOYEE:
            reviews = PerformanceReview.objects.filter(tenant=tenant, employee=user)
            goals = PerformanceGoal.objects.filter(tenant=tenant, review__employee=user)
            feedback = PerformanceFeedback.objects.filter(tenant=tenant, review__employee=user)
        elif user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            reviews = PerformanceReview.objects.filter(tenant=tenant, employee__company=user.company)
            goals = PerformanceGoal.objects.filter(tenant=tenant, review__employee__company=user.company)
            feedback = PerformanceFeedback.objects.filter(tenant=tenant, review__employee__company=user.company)
        else:  # Superadmin scoped to tenant
            reviews = PerformanceReview.objects.filter(tenant=tenant)
            goals = PerformanceGoal.objects.filter(tenant=tenant)
            feedback = PerformanceFeedback.objects.filter(tenant=tenant)

        # Calculate dashboard statistics
        dashboard_data = {
            # Review statistics
            'reviews': {
                'total': reviews.count(),
                'completed': reviews.filter(status='COMPLETED').count(),
                'pending': reviews.filter(status__in=['DRAFT', 'SUBMITTED', 'UNDER_REVIEW']).count(),
                'overdue': reviews.filter(
                    review_date__lt=timezone.now().date(),
                    status__in=['DRAFT', 'SUBMITTED']
                ).count(),
                'average_rating': reviews.filter(overall_rating__isnull=False).aggregate(
                    avg_rating=Avg('overall_rating')
                )['avg_rating'] or 0,
            },
            
            # Goal statistics
            'goals': {
                'total': goals.count(),
                'completed': goals.filter(status='COMPLETED').count(),
                'in_progress': goals.filter(status='IN_PROGRESS').count(),
                'overdue': goals.filter(
                    due_date__lt=timezone.now().date(),
                    status__in=['NOT_STARTED', 'IN_PROGRESS']
                ).count(),
            },
            
            # Feedback statistics
            'feedback': {
                'total': feedback.count(),
                'recent': feedback.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).count(),
            },
            
            # Recent activity
            'recent_reviews': PerformanceReviewSerializer(
                reviews.order_by('-created_at')[:5], many=True
            ).data,
            'upcoming_reviews': PerformanceReviewSerializer(
                reviews.filter(
                    review_date__gte=timezone.now().date(),
                    status__in=['DRAFT', 'SUBMITTED']
                ).order_by('review_date')[:5], many=True
            ).data,
            
            'recent_goals': PerformanceGoalSerializer(
                goals.order_by('-created_at')[:5], many=True
            ).data,
            'upcoming_goals': PerformanceGoalSerializer(
                goals.filter(
                    due_date__gte=timezone.now().date(),
                    status__in=['NOT_STARTED', 'IN_PROGRESS']
                ).order_by('due_date')[:5], many=True
            ).data,
        }

        return Response(dashboard_data)


# ViewSets for API endpoints
class PerformanceReviewViewSet(viewsets.ModelViewSet):
    """API endpoint for performance reviews"""
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'employee__first_name', 'employee__last_name']
    ordering_fields = ['review_date', 'created_at', 'overall_rating']
    ordering = ['-review_date']

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, 'tenant', None)
        queryset = PerformanceReview.objects.filter(tenant=tenant) if tenant else PerformanceReview.objects.none()

        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(employee=user)
        if user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            return queryset.filter(employee__company=user.company)
        return queryset


class PerformanceGoalViewSet(viewsets.ModelViewSet):
    """API endpoint for performance goals"""
    queryset = PerformanceGoal.objects.all()
    serializer_class = PerformanceGoalSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['due_date', 'created_at', 'status']
    ordering = ['-due_date']

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, 'tenant', None)
        queryset = PerformanceGoal.objects.filter(tenant=tenant) if tenant else PerformanceGoal.objects.none()

        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(review__employee=user)
        if user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            return queryset.filter(review__employee__company=user.company)
        return queryset


class PerformanceFeedbackViewSet(viewsets.ModelViewSet):
    """API endpoint for performance feedback"""
    queryset = PerformanceFeedback.objects.all()
    serializer_class = PerformanceFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, 'tenant', None)
        queryset = PerformanceFeedback.objects.filter(tenant=tenant) if tenant else PerformanceFeedback.objects.none()

        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(review__employee=user)
        if user.role in [User.Role.ADMINISTRATOR, User.Role.EMPLOYER_ADMIN]:
            return queryset.filter(review__employee__company=user.company)
        return queryset


class PerformanceTemplateViewSet(viewsets.ModelViewSet):
    """API endpoint for performance templates"""
    queryset = PerformanceTemplate.objects.filter(is_active=True)
    serializer_class = PerformanceTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        return self.queryset.filter(tenant=tenant) if tenant else PerformanceTemplate.objects.none()

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        serializer.save(created_by=self.request.user, tenant=tenant)