"""
Serializers for the audit app.

Requirements: 12.4
"""

from rest_framework import serializers

from audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    """Serializer for AuditEvent model — all fields."""

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "emission_record_id",
            "tenant_id",
            "event_type",
            "user_id",
            "timestamp",
            "field_name",
            "old_value",
            "new_value",
            "metadata",
        ]
        read_only_fields = fields
