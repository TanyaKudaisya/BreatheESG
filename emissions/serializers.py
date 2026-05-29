"""
Serializers for the emissions app.

Provides full and list-optimized serializers for EmissionRecord,
DataQualityFlag, and MonthlyAllocation.

Requirements: 8.1, 8.2, 11.1, 11.2
"""

from rest_framework import serializers

from emissions.models import DataQualityFlag, EmissionRecord, MonthlyAllocation


class DataQualityFlagSerializer(serializers.ModelSerializer):
    """Serializer for DataQualityFlag model."""

    class Meta:
        model = DataQualityFlag
        fields = [
            "id",
            "flag_type",
            "severity",
            "message",
            "field_name",
            "is_resolved",
            "resolved_at",
            "resolved_by_user_id",
        ]
        read_only_fields = ["id", "resolved_at"]


class MonthlyAllocationSerializer(serializers.ModelSerializer):
    """Serializer for MonthlyAllocation model."""

    class Meta:
        model = MonthlyAllocation
        fields = [
            "id",
            "year",
            "month",
            "allocated_quantity",
            "unit",
        ]
        read_only_fields = ["id"]


class EmissionRecordSerializer(serializers.ModelSerializer):
    """
    Full serializer for EmissionRecord with nested quality_flags and
    monthly_allocations.  Used for retrieve and partial_update.

    Requirements: 8.4, 11.1
    """

    quality_flags = DataQualityFlagSerializer(many=True, read_only=True)
    monthly_allocations = MonthlyAllocationSerializer(many=True, read_only=True)

    # Editable fields (Req 11.1): quantity, unit, date, location
    class Meta:
        model = EmissionRecord
        fields = [
            # Identity
            "id",
            "tenant",
            # Source tracking
            "source_system",
            "ingestion_timestamp",
            "original_filename",
            "raw_data",
            # Core emission fields
            "transaction_date",
            "location",
            "fuel_type",
            "original_quantity",
            "original_unit",
            "normalized_quantity",
            "normalized_unit",
            # Scope
            "scope",
            "scope_category",
            # Approval workflow
            "approval_status",
            "approved_by_user_id",
            "approved_at",
            "rejection_reason",
            # Audit lock
            "is_locked",
            "locked_at",
            "locked_by_user_id",
            # SAP-specific
            "ebeln",
            "ebelp",
            "bedat",
            "werks",
            "plant_name",
            "plant_location",
            "plant_state",
            "plant_country",
            "matnr",
            "material_description",
            "netpr",
            "currency",
            # Utility-specific
            "account_number",
            "meter_id",
            "service_address",
            "billing_period_start",
            "billing_period_end",
            "consumption_kwh",
            "reading_type",
            "tariff_code",
            "demand_kw",
            # Travel-specific
            "report_id",
            "entry_id",
            "expense_type",
            "employee_id",
            "employee_name",
            "department",
            "travel_approval_status",
            "receipt_attached",
            "origin_airport",
            "destination_airport",
            "via_airport",
            "cabin_class",
            "distance_km",
            "hotel_city",
            "hotel_country",
            "check_in",
            "check_out",
            "nights",
            "ground_fuel_type",
            # Nested
            "quality_flags",
            "monthly_allocations",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "source_system",
            "ingestion_timestamp",
            "original_filename",
            "raw_data",
            "approval_status",
            "approved_by_user_id",
            "approved_at",
            "rejection_reason",
            "is_locked",
            "locked_at",
            "locked_by_user_id",
            "quality_flags",
            "monthly_allocations",
        ]


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """
    Lighter serializer for list view — omits raw_data and nested objects
    to keep response payloads small.

    Requirements: 8.1, 8.2
    """

    has_flags = serializers.SerializerMethodField()
    flag_count = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            "id",
            "source_system",
            "transaction_date",
            "location",
            "fuel_type",
            "original_quantity",
            "original_unit",
            "normalized_quantity",
            "normalized_unit",
            "scope",
            "scope_category",
            "approval_status",
            "is_locked",
            "ingestion_timestamp",
            "has_flags",
            "flag_count",
        ]

    def get_has_flags(self, obj: EmissionRecord) -> bool:
        """Return True if the record has any unresolved quality flags."""
        return obj.quality_flags.filter(is_resolved=False).exists()

    def get_flag_count(self, obj: EmissionRecord) -> int:
        """Return the count of unresolved quality flags."""
        return obj.quality_flags.filter(is_resolved=False).count()
