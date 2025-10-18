from rest_framework import status, permissions, generics, filters, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import (
    PerformanceReview, PerformanceGoal, PerformanceMetric,
    PerformanceFeedback, PerformanceTemplate
)
from .serializers import (
    PerformanceReviewSerializer, PerformanceGoalSerializer,
    PerformanceMetricSerializer, PerformanceFeedbackSerializer,
    PerformanceTemplateSerializer, PerformanceStatsSerializer
)
from accounts.permissions import IsEmployerOrAdmin, IsEmployeeOrReadOnly, IsOwnerOrAdmin

User = get_user_model()


class PerformanceReviewListCreateView(generics.ListCreateAPIView):
    """View to list and create performance reviews"""
    serializer_class = PerformanceReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'employee__first_name', 'employee__last_name']
    ordering_fields = ['review_date', 'created_at', 'overall_rating']
    ordering = ['-review_date']

    def get_queryset(self):
        user = self.request.user
        queryset = PerformanceReview.objects.all()

        # Filter based on user role
        if user.role == User.Role.EMPLOYEE:
            queryset = queryset.filter(employee=user)
        elif user.role == User.Role.EMPLOYER:
            queryset = queryset.filter(employee__employer_profile__user=user)
        elif user.role == User.Role.ADMIN:
            # Admin can see all reviews
            pass

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
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.EMPLOYEE:
            return self.queryset.filter(employee=user)
        elif user.role == User.Role.EMPLOYER:
            return self.queryset.filter(employee__employer_profile__user=user)
        return self.queryset


class PerformanceGoalListCreateView(generics.ListCreateAPIView):
    """View to list and create performance goals"""
    serializer_class = PerformanceGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        review_id = self.kwargs.get('review_pk')
        return PerformanceGoal.objects.filter(review_id=review_id)

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_pk')
        review = PerformanceReview.objects.get(pk=review_id)
        serializer.save(review=review)


class PerformanceGoalDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a performance goal"""
    queryset = PerformanceGoal.objects.all()
    serializer_class = PerformanceGoalSerializer
    permission_classes = [permissions.IsAuthenticated]


class PerformanceMetricListCreateView(generics.ListCreateAPIView):
    """View to list and create performance metrics"""
    serializer_class = PerformanceMetricSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        review_id = self.kwargs.get('review_pk')
        return PerformanceMetric.objects.filter(review_id=review_id)

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_pk')
        review = PerformanceReview.objects.get(pk=review_id)
        serializer.save(review=review)


class PerformanceMetricDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a performance metric"""
    queryset = PerformanceMetric.objects.all()
    serializer_class = PerformanceMetricSerializer
    permission_classes = [permissions.IsAuthenticated]


class PerformanceFeedbackListCreateView(generics.ListCreateAPIView):
    """View to list and create performance feedback"""
    serializer_class = PerformanceFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        review_id = self.kwargs.get('review_pk')
        return PerformanceFeedback.objects.filter(review_id=review_id)

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_pk')
        review = PerformanceReview.objects.get(pk=review_id)
        serializer.save(review=review, provided_by=self.request.user)


class PerformanceFeedbackDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete performance feedback"""
    queryset = PerformanceFeedback.objects.all()
    serializer_class = PerformanceFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]


class PerformanceTemplateListCreateView(generics.ListCreateAPIView):
    """View to list and create performance templates"""
    queryset = PerformanceTemplate.objects.filter(is_active=True)
    serializer_class = PerformanceTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']


class PerformanceTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a performance template"""
    queryset = PerformanceTemplate.objects.all()
    serializer_class = PerformanceTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]


class PerformanceStatsView(APIView):
    """View to get performance statistics"""
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]

    def get(self, request):
        user = request.user

        # Base queryset
        if user.role == User.Role.EMPLOYER:
            reviews = PerformanceReview.objects.filter(employee__employer_profile__user=user)
        else:  # Admin
            reviews = PerformanceReview.objects.all()

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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # Base queryset based on user role
        if user.role == User.Role.EMPLOYEE:
            reviews = PerformanceReview.objects.filter(employee=user)
            goals = PerformanceGoal.objects.filter(employee=user)
            feedback = PerformanceFeedback.objects.filter(reviewee=user)
        elif user.role in [User.Role.EMPLOYER, User.Role.EMPLOYER_ADMIN]:
            if hasattr(user, 'company') and user.company:
                reviews = PerformanceReview.objects.filter(employee__company=user.company)
                goals = PerformanceGoal.objects.filter(employee__company=user.company)
                feedback = PerformanceFeedback.objects.filter(reviewee__company=user.company)
            else:
                # Fallback for employers without company attribute
                reviews = PerformanceReview.objects.filter(employee__employer_profile__user=user)
                goals = PerformanceGoal.objects.none()
                feedback = PerformanceFeedback.objects.none()
        else:  # Admin
            reviews = PerformanceReview.objects.all()
            goals = PerformanceGoal.objects.all()
            feedback = PerformanceFeedback.objects.all()

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
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'employee__first_name', 'employee__last_name']
    ordering_fields = ['review_date', 'created_at', 'overall_rating']
    ordering = ['-review_date']

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(employee=user)
        elif user.role in [User.Role.EMPLOYER, User.Role.EMPLOYER_ADMIN]:
            if hasattr(user, 'company') and user.company:
                return queryset.filter(employee__company=user.company)
            else:
                # Fallback for employers without company attribute
                return queryset.filter(employee__employer_profile__user=user)
        return queryset


class PerformanceGoalViewSet(viewsets.ModelViewSet):
    """API endpoint for performance goals"""
    queryset = PerformanceGoal.objects.all()
    serializer_class = PerformanceGoalSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['due_date', 'created_at', 'status']
    ordering = ['-due_date']

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(employee=user)
        elif user.role in [User.Role.EMPLOYER, User.Role.EMPLOYER_ADMIN]:
            if hasattr(user, 'company') and user.company:
                return queryset.filter(employee__company=user.company)
            else:
                # Fallback - return empty queryset if no company
                return queryset.none()
        return queryset


class PerformanceFeedbackViewSet(viewsets.ModelViewSet):
    """API endpoint for performance feedback"""
    queryset = PerformanceFeedback.objects.all()
    serializer_class = PerformanceFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        if user.role == User.Role.EMPLOYEE:
            return queryset.filter(reviewee=user)
        elif user.role in [User.Role.EMPLOYER, User.Role.EMPLOYER_ADMIN]:
            if hasattr(user, 'company') and user.company:
                return queryset.filter(reviewee__company=user.company)
            else:
                # Fallback - return empty queryset if no company
                return queryset.none()
        return queryset


class PerformanceTemplateViewSet(viewsets.ModelViewSet):
    """API endpoint for performance templates"""
    queryset = PerformanceTemplate.objects.filter(is_active=True)
    serializer_class = PerformanceTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_queryset(self):
        user = self.request.user
        if user.role in [User.Role.EMPLOYER, User.Role.EMPLOYER_ADMIN]:
            if hasattr(user, 'company') and user.company:
                return self.queryset.filter(company=user.company)
            else:
                # Return empty queryset if no company
                return self.queryset.none()
        return self.queryset.none()