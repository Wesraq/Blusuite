from rest_framework import serializers

from .custom_report_builder import CustomReportBuilder


class ReportGenerationSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=[(key, cfg['name']) for key, cfg in CustomReportBuilder.REPORT_SOURCES.items()])
    filters = serializers.DictField(child=serializers.JSONField(), required=False)
    fields = serializers.ListField(child=serializers.CharField(), required=False)

    def validate_fields(self, value):
        source = self.initial_data.get('source')
        if not source:
            return value
        config = CustomReportBuilder.REPORT_SOURCES.get(source, {})
        valid_fields = set(config.get('fields', {}).keys())
        invalid = [field for field in value if field not in valid_fields]
        if invalid:
            raise serializers.ValidationError(f"Invalid fields for source '{source}': {', '.join(invalid)}")
        return value


class ReportResponseSerializer(serializers.Serializer):
    data = serializers.ListField(child=serializers.DictField(), read_only=True)
    statistics = serializers.DictField(read_only=True)
    csv = serializers.CharField(read_only=True)
