from rest_framework import status, permissions, generics, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.http import Http404, JsonResponse, FileResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from .models import DocumentCategory, EmployeeDocument, DocumentTemplate, DocumentAccessLog
from .serializers import (
    DocumentCategorySerializer, EmployeeDocumentSerializer, DocumentTemplateSerializer,
    DocumentAccessLogSerializer, DocumentUploadSerializer, DocumentApprovalSerializer,
    DocumentStatsSerializer
)
from accounts.permissions import IsEmployerOrAdmin, IsEmployeeOrReadOnly, IsOwnerOrAdmin

User = get_user_model()


class DocumentCategoryListCreateView(generics.ListCreateAPIView):
    """View to list and create document categories"""
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']


class DocumentCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a document category"""
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]


class EmployeeDocumentListView(generics.ListAPIView):
    """View to list employee documents"""
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'employee__first_name', 'employee__last_name']
    ordering_fields = ['created_at', 'title', 'status', 'document_type']
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        queryset = EmployeeDocument.objects.all()

        # Filter based on user role
        if user.role == User.Role.EMPLOYEE:
            queryset = queryset.filter(employee=user)
        elif user.role == User.Role.EMPLOYER:
            queryset = queryset.filter(employee__employer_profile__user=user)
        elif user.role == User.Role.ADMIN:
            # Admin can see all documents
            pass

        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by document type
        doc_type = self.request.query_params.get('document_type')
        if doc_type:
            queryset = queryset.filter(document_type=doc_type)

        # Filter by category
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Filter by employee
        employee_id = self.request.query_params.get('employee')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        return queryset.order_by('-created_at')


class EmployeeDocumentCreateView(generics.CreateAPIView):
    """View to create employee documents"""
    serializer_class = DocumentUploadSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployeeOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        """Create the document"""
        file = self.request.FILES.get('file')
        if not file:
            raise serializers.ValidationError("No file provided")

        # Create the document
        EmployeeDocument.objects.create(
            employee=self.request.user,
            title=serializer.validated_data['title'],
            description=serializer.validated_data.get('description', ''),
            document_type=serializer.validated_data['document_type'],
            category=serializer.validated_data.get('category'),
            file=file,
            expiry_date=serializer.validated_data.get('expiry_date'),
            is_confidential=serializer.validated_data.get('is_confidential', False)
        )

        # Log the upload
        DocumentAccessLog.objects.create(
            document=document,
            user=self.request.user,
            access_type=DocumentAccessLog.AccessType.UPLOAD,
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )


class EmployeeDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete an employee document"""
    queryset = EmployeeDocument.objects.all()
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.EMPLOYEE:
            return self.queryset.filter(employee=user)
        elif user.role == User.Role.EMPLOYER:
            return self.queryset.filter(employee__employer_profile__user=user)
        return self.queryset

    def perform_update(self, serializer):
        """Update the document"""
        instance = self.get_object()
        old_status = instance.status

        # Update the document
        updated_instance = serializer.save()

        # If status changed, update approval info
        if 'status' in self.request.data and updated_instance.status != old_status:
            if updated_instance.status == 'APPROVED':
                updated_instance.approved_by = self.request.user
                updated_instance.approved_at = timezone.now()
                updated_instance.save()

            # Log the approval/rejection
            DocumentAccessLog.objects.create(
                document=updated_instance,
                user=self.request.user,
                access_type=DocumentAccessLog.AccessType.APPROVE if updated_instance.status == 'APPROVED' else DocumentAccessLog.AccessType.REJECT,
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )


class DocumentApprovalView(APIView):
    """View to approve or reject documents"""
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]

    def post(self, request, pk):
        """Approve or reject a document"""
        try:
            document = EmployeeDocument.objects.get(pk=pk)
        except EmployeeDocument.DoesNotExist:
            return Response(
                {"detail": _("Document not found")},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = DocumentApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Update document status
        old_status = document.status
        document.status = serializer.validated_data['status']

        if document.status == 'APPROVED':
            document.approved_by = request.user
            document.approved_at = timezone.now()
        elif document.status == 'REJECTED':
            document.rejection_reason = serializer.validated_data.get('rejection_reason', '')

        document.save()

        # Log the action
        DocumentAccessLog.objects.create(
            document=document,
            user=request.user,
            access_type=DocumentAccessLog.AccessType.APPROVE if document.status == 'APPROVED' else DocumentAccessLog.AccessType.REJECT,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response({
            "message": _("Document status updated successfully"),
            "document": EmployeeDocumentSerializer(document).data
        })


class DocumentTemplateListCreateView(generics.ListCreateAPIView):
    """View to list and create document templates"""
    queryset = DocumentTemplate.objects.filter(is_active=True)
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']
    parser_classes = [MultiPartParser, FormParser]


class DocumentTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update or delete a document template"""
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]
    parser_classes = [MultiPartParser, FormParser]


class DocumentAccessLogListView(generics.ListAPIView):
    """View to list document access logs"""
    serializer_class = DocumentAccessLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['document__title', 'user__first_name', 'user__last_name']
    ordering_fields = ['accessed_at', 'access_type']
    ordering = ['-accessed_at']

    def get_queryset(self):
        queryset = DocumentAccessLog.objects.all()

        # Filter by document
        document_id = self.request.query_params.get('document')
        if document_id:
            queryset = queryset.filter(document_id=document_id)

        # Filter by user
        user_id = self.request.query_params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by access type
        access_type = self.request.query_params.get('access_type')
        if access_type:
            queryset = queryset.filter(access_type=access_type)

        return queryset


class DocumentStatsView(APIView):
    """View to get document statistics"""
    permission_classes = [permissions.IsAuthenticated, IsEmployerOrAdmin]

    def get(self, request):
        user = request.user

        # Base queryset
        if user.role == User.Role.EMPLOYER:
            documents = EmployeeDocument.objects.filter(employee__employer_profile__user=user)
        else:  # Admin
            documents = EmployeeDocument.objects.all()

        # Calculate statistics
        stats = {
            'total_documents': documents.count(),
            'pending_documents': documents.filter(status='PENDING').count(),
            'approved_documents': documents.filter(status='APPROVED').count(),
            'rejected_documents': documents.filter(status='REJECTED').count(),
            'expired_documents': documents.filter(is_expired=True).count(),
            'total_size': documents.aggregate(Sum('file_size'))['file_size__sum'] or 0
        }

        serializer = DocumentStatsSerializer(stats)
        return Response(serializer.data)


class DocumentDownloadView(APIView):
    """View to download a document"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        """Download a document"""
        try:
            document = EmployeeDocument.objects.get(pk=pk)
        except EmployeeDocument.DoesNotExist:
            return Response(
                {"detail": _("Document not found")},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check permissions
        if request.user.role == User.Role.EMPLOYEE and document.employee != request.user:
            return Response(
                {"detail": _("You can only download your own documents")},
                status=status.HTTP_403_FORBIDDEN
            )
        elif request.user.role == User.Role.EMPLOYER and document.employee.employer_profile.user != request.user:
            return Response(
                {"detail": _("You can only download documents of your employees")},
                status=status.HTTP_403_FORBIDDEN
            )

        # Log the download
        DocumentAccessLog.objects.create(
            document=document,
            user=request.user,
            access_type=DocumentAccessLog.AccessType.DOWNLOAD,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        # Return file response
        from django.http import FileResponse
        try:
            response = FileResponse(document.file, as_attachment=True, filename=document.original_filename)
            return response
        except FileNotFoundError:
            return Response(
                {"detail": _("File not found")},
                status=status.HTTP_404_NOT_FOUND
            )


@login_required
def upload_company_document(request):
    """View to handle company document uploads"""
    if request.method == 'POST':
        try:
            from .models import Document
            
            file = request.FILES.get('file')
            name = request.POST.get('name')
            is_public = request.POST.get('is_public', 'false').lower() == 'true'
            
            if not file or not name:
                messages.error(request, 'Please provide both a file and a name.')
                return redirect('documents_list')
                
            # Create document record
            document = Document.objects.create(
                name=name,
                company=request.user.company,
                uploaded_by=request.user,
                is_public=is_public
            )
            
            # Save the file
            file_name = f"company_{request.user.company.id}/{file.name}"
            file_path = default_storage.save(file_name, ContentFile(file.read()))
            document.file = file_path
            document.save()
            
            messages.success(request, 'Document uploaded successfully!')
            return redirect('documents_list')
            
        except Exception as e:
            messages.error(request, f'Error uploading document: {str(e)}')
            return redirect('documents_list')
    
    return redirect('documents_list')


@login_required
def upload_employee_document(request):
    """View to handle employee document uploads"""
    if request.method == 'POST':
        try:
            file = request.FILES.get('file')
            document_type = request.POST.get('document_type')
            notes = request.POST.get('notes', '')
            
            if not file or not document_type:
                messages.error(request, 'Please provide both a file and document type.')
                return redirect('documents_list')
                
            # Create employee document record
            document = EmployeeDocument.objects.create(
                employee=request.user.employee_profile,
                document_type=document_type,
                notes=notes,
                uploaded_by=request.user,
                status='PENDING_REVIEW'
            )
            
            # Save the file
            file_name = f"employee_{request.user.id}/{file.name}"
            file_path = default_storage.save(file_name, ContentFile(file.read()))
            document.file = file_path
            document.save()
            
            messages.success(request, 'Document uploaded successfully and is pending review!')
            return redirect('documents_list')
            
        except Exception as e:
            messages.error(request, f'Error uploading document: {str(e)}')
            return redirect('documents_list')
    
    return redirect('documents_list')
