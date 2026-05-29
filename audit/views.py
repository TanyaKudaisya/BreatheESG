"""
API views for the audit app.

AuditTrailView provides:
  - GET /api/v1/audit-trail/{record_id}/

Requirements: 12.4
"""

from __future__ import annotations

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.serializers import AuditEventSerializer
from audit.services import AuditTrailStore

logger = logging.getLogger(__name__)


class AuditTrailView(APIView):
    """
    GET /api/v1/audit-trail/{record_id}/

    Returns the complete audit trail for a single emission record.
    Tenant isolation is enforced: only events belonging to the
    authenticated user's tenant are returned.

    Requirements: 12.4
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, record_id: str) -> Response:
        """
        Retrieve the audit trail for the given emission record.

        Args:
            record_id: UUID of the EmissionRecord.

        Returns:
            List of AuditEvent objects ordered by timestamp descending.
        """
        user = request.user
        if not hasattr(user, "tenant") or user.tenant is None:
            return Response(
                {"detail": "User is not associated with a tenant."},
                status=403,
            )

        tenant_id = str(user.tenant.id)

        store = AuditTrailStore()
        try:
            events = store.get_audit_trail(
                emission_record_id=str(record_id),
                tenant_id=tenant_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Error retrieving audit trail for record %s: %s",
                record_id,
                exc,
            )
            return Response(
                {"detail": "Unable to retrieve audit trail."},
                status=500,
            )

        serializer = AuditEventSerializer(events, many=True)
        return Response(serializer.data)
