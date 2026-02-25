from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from tenant_management.permissions import IsTenantMember

from .serializers import ReportGenerationSerializer, ReportResponseSerializer
from .custom_report_builder import generate_custom_report


class ReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    http_method_names = ['post']

    def create(self, request):
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            raise ValidationError('Tenant could not be resolved for this request.')

        serializer = ReportGenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report_data = generate_custom_report(
            serializer.validated_data['source'],
            tenant,
            filters=serializer.validated_data.get('filters'),
            selected_fields=serializer.validated_data.get('fields'),
        )

        response_serializer = ReportResponseSerializer(report_data)
        return Response(response_serializer.data)
