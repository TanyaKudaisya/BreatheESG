"""
Django-filter FilterSet for EmissionRecord.

Provides filtering by source_system, scope, date range, approval_status,
and a has_flags annotation.

Requirements: 8.2
"""

import django_filters
from django.db.models import QuerySet

from emissions.models import DataQualityFlag, EmissionRecord


class EmissionRecordFilter(django_filters.FilterSet):
    """
    FilterSet for EmissionRecord list endpoint.

    Supported filters:
    - source_system   — exact match (SAP, UTILITY, CONCUR)
    - scope           — exact integer match (1, 2, 3)
    - date_from       — transaction_date >= value
    - date_to         — transaction_date <= value
    - approval_status — exact match (PENDING, APPROVED, REJECTED)
    - has_flags       — boolean; True returns only records with unresolved flags
    """

    source_system = django_filters.ChoiceFilter(
        choices=EmissionRecord.SOURCE_SYSTEM_CHOICES,
    )
    scope = django_filters.NumberFilter(field_name="scope")
    date_from = django_filters.DateFilter(
        field_name="transaction_date",
        lookup_expr="gte",
    )
    date_to = django_filters.DateFilter(
        field_name="transaction_date",
        lookup_expr="lte",
    )
    approval_status = django_filters.ChoiceFilter(
        choices=EmissionRecord.APPROVAL_STATUS_CHOICES,
    )
    has_flags = django_filters.BooleanFilter(method="filter_has_flags")

    class Meta:
        model = EmissionRecord
        fields = [
            "source_system",
            "scope",
            "date_from",
            "date_to",
            "approval_status",
            "has_flags",
        ]

    def filter_has_flags(
        self, queryset: QuerySet, name: str, value: bool
    ) -> QuerySet:
        """
        Filter records by whether they have unresolved data quality flags.

        Args:
            queryset: The base queryset to filter.
            name:     Field name (unused — method filter).
            value:    True → only records with flags; False → only without.
        """
        records_with_flags = (
            DataQualityFlag.objects.filter(is_resolved=False)
            .values_list("emission_record_id", flat=True)
            .distinct()
        )
        if value:
            return queryset.filter(id__in=records_with_flags)
        return queryset.exclude(id__in=records_with_flags)
