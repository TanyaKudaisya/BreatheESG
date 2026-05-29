"""
API views for the validation app.

DataQualityFlagViewSet provides:
  - list     GET  /api/v1/quality-flags/
  - retrieve GET  /api/v1/quality-flags/{id}/
  - resolve  POST /api/v1/quality-flags/{id}/resolve/

Requirements: 9.1-9.5
"""

from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from emissions.models import DataQualityFlag
from validation.serializers import DataQualityFlagSerializer

logger = logging.getLogger(__name__)


class DataQualityFlagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for DataQualityFlag with a custom resolve action.

    All queries are tenant-isolated via emission_record__tenant.

    Requirements: 9.1-9.5
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DataQualityFlagSerializer

    def get_queryset(self):
        """
        Return flags scoped to the current user's tenant.

        Supports optional ?flag_type= query parameter for filtering.

        Requirements: 9.3, 1.2
        """
        user = self.request.user
        if not hasattr(user, "tenant") or user.tenant is None:
            return DataQualityFlag.objects.none()

        qs = DataQualityFlag.objects.filter(
            emission_record__tenant=user.tenant
        ).select_related("emission_record").order_by("-emission_record__ingestion_timestamp")

        # Optional filter by flag_type (Req 9.3)
        flag_type = self.request.query_params.get("flag_type")
        if flag_type:
            qs = qs.filter(flag_type=flag_type)

        return qs

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request: Request, pk: str = None) -> Response:
        """
        POST /api/v1/quality-flags/{id}/resolve/

        Mark a data quality flag as resolved.

        Requirements: 9.5
        """
        try:
            flag = self.get_queryset().get(pk=pk)
        except DataQualityFlag.DoesNotExist:
            return Response(
                {"detail": "Data quality flag not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if flag.is_resolved:
            return Response(
                {"detail": "Flag is already resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        flag.is_resolved = True
        flag.resolved_at = timezone.now()
        flag.resolved_by_user_id = request.user.id
        flag.save(update_fields=["is_resolved", "resolved_at", "resolved_by_user_id"])

        logger.info(
            "DataQualityFlag %s resolved by user %s",
            flag.id,
            request.user.id,
        )

        return Response(
            DataQualityFlagSerializer(flag).data,
            status=status.HTTP_200_OK,
        )
