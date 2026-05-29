"""
Serializers for the validation app.

Requirements: 9.1-9.5
"""

from rest_framework import serializers

from emissions.models import DataQualityFlag


class DataQualityFlagSerializer(serializers.ModelSerializer):
    """Serializer for DataQualityFlag model — all fields."""

    emission_record_id = serializers.UUIDField(source="emission_record.id", read_only=True)

    class Meta:
        model = DataQualityFlag
        fields = [
            "id",
            "emission_record_id",
            "flag_type",
            "severity",
            "message",
            "field_name",
            "is_resolved",
            "resolved_at",
            "resolved_by_user_id",
        ]
        read_only_fields = [
            "id",
            "emission_record_id",
            "resolved_at",
        ]
