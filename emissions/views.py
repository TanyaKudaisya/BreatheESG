"""
API views for the emissions app.

EmissionRecordViewSet provides:
  - list          GET  /api/v1/emissions/
  - retrieve      GET  /api/v1/emissions/{id}/
  - partial_update PATCH /api/v1/emissions/{id}/
  - approve       POST /api/v1/emissions/{id}/approve/
  - reject        POST /api/v1/emissions/{id}/reject/
  - bulk_approve  POST /api/v1/emissions/bulk-approve/
  - bulk_reject   POST /api/v1/emissions/bulk-reject/
  - lock          POST /api/v1/emissions/{id}/lock/
  - unlock        POST /api/v1/emissions/{id}/unlock/
  - override_scope POST /api/v1/emissions/{id}/override-scope/

Requirements: 8.1, 8.2, 10.1-10.6, 11.1, 11.2, 13.1-13.5
"""

from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from audit.services import AuditTrailStore
from emissions.filters import EmissionRecordFilter
from emissions.models import DataQualityFlag, EmissionRecord
from emissions.serializers import (
    EmissionRecordListSerializer,
    EmissionRecordSerializer,
)
from validation.services import ValidationService

logger = logging.getLogger(__name__)


class EmissionRecordViewSet(viewsets.GenericViewSet):
    """
    ViewSet for EmissionRecord CRUD and workflow actions.

    All queries are tenant-isolated: only records belonging to
    request.user.tenant are returned.

    Requirements: 8.1, 8.2, 10.1-10.6, 11.1, 11.2, 13.1-13.5
    """

    permission_classes = [IsAuthenticated]
    filterset_class = EmissionRecordFilter

    # ------------------------------------------------------------------
    # Queryset helpers
    # ------------------------------------------------------------------

    def get_queryset(self):
        """
        Return tenant-isolated queryset.

        Uses EmissionRecord._default_manager to bypass TenantManager's
        automatic thread-local filtering, then manually applies the
        tenant filter from the authenticated user.

        Requirements: 1.2, 1.4
        """
        user = self.request.user
        if not hasattr(user, "tenant") or user.tenant is None:
            return EmissionRecord._default_manager.none()
        return (
            EmissionRecord._default_manager.filter(tenant=user.tenant)
            .prefetch_related("quality_flags", "monthly_allocations")
            .order_by("-ingestion_timestamp")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return EmissionRecordListSerializer
        return EmissionRecordSerializer

    def _get_tenant_record(self, pk: str) -> EmissionRecord:
        """
        Retrieve a single record scoped to the current user's tenant.
        Raises 404 if not found.
        """
        from rest_framework.exceptions import NotFound

        qs = self.get_queryset()
        try:
            return qs.get(pk=pk)
        except EmissionRecord.DoesNotExist:
            raise NotFound(detail="Emission record not found.")

    # ------------------------------------------------------------------
    # Standard CRUD actions
    # ------------------------------------------------------------------

    def list(self, request: Request) -> Response:
        """
        GET /api/v1/emissions/

        Paginated, filtered list of emission records for the current tenant.

        Requirements: 8.1, 8.2
        """
        queryset = self.get_queryset()

        # Apply filters
        filterset = self.filterset_class(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return Response(filterset.errors, status=status.HTTP_400_BAD_REQUEST)
        queryset = filterset.qs

        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request: Request, pk: str = None) -> Response:
        """
        GET /api/v1/emissions/{id}/

        Retrieve a single emission record with full detail.

        Requirements: 8.4
        """
        record = self._get_tenant_record(pk)
        serializer = self.get_serializer(record)
        return Response(serializer.data)

    def partial_update(self, request: Request, pk: str = None) -> Response:
        """
        PATCH /api/v1/emissions/{id}/

        Edit quantity, unit, date, and/or location fields.
        Records an audit event and re-runs validation.

        Requirements: 11.1, 11.2, 11.5
        """
        record = self._get_tenant_record(pk)

        # Req 11.4: Prevent editing locked records
        if record.is_locked:
            return Response(
                {"detail": "This record is locked for audit and cannot be edited."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Only allow editing of the four permitted fields
        allowed_fields = {
            "original_quantity",
            "normalized_quantity",
            "original_unit",
            "normalized_unit",
            "transaction_date",
            "location",
        }
        data = {k: v for k, v in request.data.items() if k in allowed_fields}

        serializer = EmissionRecordSerializer(record, data=data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Attach audit user before save so the model's save() records the diff
        record._audit_user_id = str(request.user.id)
        serializer.save()

        # Req 11.5: Re-run validation after edit
        try:
            validator = ValidationService()
            record.refresh_from_db()
            new_flags = validator.validate_emission_record(
                {
                    "menge": str(record.original_quantity or ""),
                    "netpr": str(record.netpr or ""),
                    "meins": record.original_unit,
                    "reading_type": record.reading_type,
                },
                record.source_system,
            )
            for flag_data in new_flags:
                # Only create if not already present
                DataQualityFlag.objects.get_or_create(
                    emission_record=record,
                    flag_type=flag_data.flag_type,
                    is_resolved=False,
                    defaults={
                        "severity": flag_data.severity,
                        "message": flag_data.message,
                        "field_name": flag_data.field_name or "",
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Re-validation after edit failed: %s", exc)

        record.refresh_from_db()
        return Response(EmissionRecordSerializer(record).data)

    # ------------------------------------------------------------------
    # Approval workflow (Task 13.2)
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request: Request, pk: str = None) -> Response:
        """
        POST /api/v1/emissions/{id}/approve/

        Approve a single emission record.
        Blocked if ERROR-level flags are present.

        Requirements: 10.1, 10.3, 10.6
        """
        record = self._get_tenant_record(pk)

        if record.is_locked:
            return Response(
                {"detail": "Cannot approve a locked record."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Req 10.6: Block approval if ERROR flags present
        error_flags = record.quality_flags.filter(
            severity=DataQualityFlag.SEVERITY_ERROR,
            is_resolved=False,
        )
        if error_flags.exists():
            flag_types = list(error_flags.values_list("flag_type", flat=True))
            return Response(
                {
                    "detail": "Cannot approve: unresolved ERROR-level flags present.",
                    "error_flags": flag_types,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        record.approve(user_id=str(request.user.id))
        return Response(
            {"detail": "Record approved.", "id": str(record.id)},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request: Request, pk: str = None) -> Response:
        """
        POST /api/v1/emissions/{id}/reject/

        Reject a single emission record with a required reason.

        Requirements: 10.2, 10.4
        """
        record = self._get_tenant_record(pk)

        if record.is_locked:
            return Response(
                {"detail": "Cannot reject a locked record."},
                status=status.HTTP_403_FORBIDDEN,
            )

        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response(
                {"detail": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record.reject(user_id=str(request.user.id), reason=reason)
        return Response(
            {"detail": "Record rejected.", "id": str(record.id)},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="bulk-approve")
    def bulk_approve(self, request: Request) -> Response:
        """
        POST /api/v1/emissions/bulk-approve/

        Bulk approve a list of emission record IDs.
        Records with ERROR flags are skipped and reported.

        Requirements: 10.5
        """
        ids = request.data.get("ids", [])
        if not ids:
            return Response(
                {"detail": "No record IDs provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        approved = []
        skipped = []
        user_id = str(request.user.id)

        for record_id in ids:
            try:
                record = self._get_tenant_record(str(record_id))
            except Exception:  # noqa: BLE001
                skipped.append({"id": record_id, "reason": "Not found."})
                continue

            if record.is_locked:
                skipped.append({"id": record_id, "reason": "Record is locked."})
                continue

            error_flags = record.quality_flags.filter(
                severity=DataQualityFlag.SEVERITY_ERROR,
                is_resolved=False,
            )
            if error_flags.exists():
                flag_types = list(error_flags.values_list("flag_type", flat=True))
                skipped.append(
                    {
                        "id": record_id,
                        "reason": "Unresolved ERROR flags present.",
                        "error_flags": flag_types,
                    }
                )
                continue

            record.approve(user_id=user_id)
            approved.append(str(record.id))

        return Response(
            {
                "approved": approved,
                "skipped": skipped,
                "approved_count": len(approved),
                "skipped_count": len(skipped),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="bulk-reject")
    def bulk_reject(self, request: Request) -> Response:
        """
        POST /api/v1/emissions/bulk-reject/

        Bulk reject a list of emission record IDs with a shared reason.

        Requirements: 10.5
        """
        ids = request.data.get("ids", [])
        reason = request.data.get("reason", "").strip()

        if not ids:
            return Response(
                {"detail": "No record IDs provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not reason:
            return Response(
                {"detail": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rejected = []
        skipped = []
        user_id = str(request.user.id)

        for record_id in ids:
            try:
                record = self._get_tenant_record(str(record_id))
            except Exception:  # noqa: BLE001
                skipped.append({"id": record_id, "reason": "Not found."})
                continue

            if record.is_locked:
                skipped.append({"id": record_id, "reason": "Record is locked."})
                continue

            record.reject(user_id=user_id, reason=reason)
            rejected.append(str(record.id))

        return Response(
            {
                "rejected": rejected,
                "skipped": skipped,
                "rejected_count": len(rejected),
                "skipped_count": len(skipped),
            },
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # Audit lock (Task 13.3)
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="lock")
    def lock(self, request: Request, pk: str = None) -> Response:
        """
        POST /api/v1/emissions/{id}/lock/

        Lock a record for audit.

        Requirements: 13.1, 13.5
        """
        record = self._get_tenant_record(pk)

        if record.is_locked:
            return Response(
                {"detail": "Record is already locked."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record.lock(user_id=str(request.user.id))
        return Response(
            {"detail": "Record locked for audit.", "id": str(record.id)},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="unlock")
    def unlock(self, request: Request, pk: str = None) -> Response:
        """
        POST /api/v1/emissions/{id}/unlock/

        Unlock a record. Only users with the AUDITOR role may unlock.

        Requirements: 13.4
        """
        from emissions.models import User

        if request.user.role != User.ROLE_AUDITOR:
            return Response(
                {"detail": "Only users with the Auditor role can unlock records."},
                status=status.HTTP_403_FORBIDDEN,
            )

        record = self._get_tenant_record(pk)

        if not record.is_locked:
            return Response(
                {"detail": "Record is not locked."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record.unlock(user_id=str(request.user.id))
        return Response(
            {"detail": "Record unlocked.", "id": str(record.id)},
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # Scope override (Req 14.5)
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="override-scope")
    def override_scope(self, request: Request, pk: str = None) -> Response:
        """
        POST /api/v1/emissions/{id}/override-scope/

        Manually override the scope classification with a justification note.

        Requirements: 14.5
        """
        record = self._get_tenant_record(pk)

        if record.is_locked:
            return Response(
                {"detail": "Cannot override scope on a locked record."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_scope = request.data.get("scope")
        new_scope_category = request.data.get("scope_category")
        justification = request.data.get("justification", "").strip()

        if new_scope is None:
            return Response(
                {"detail": "A 'scope' value is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not justification:
            return Response(
                {"detail": "A 'justification' note is required for scope override."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_scope = record.scope
        old_category = record.scope_category

        record._audit_user_id = str(request.user.id)
        record.scope = int(new_scope)
        if new_scope_category is not None:
            record.scope_category = int(new_scope_category)
        record.save()

        # Record the override in the audit trail with justification
        AuditTrailStore().record_event(
            event_type="UPDATE",
            emission_record_id=str(record.id),
            user_id=str(request.user.id),
            tenant_id=str(request.user.tenant_id),
            field_name="scope",
            old_value=old_scope,
            new_value=record.scope,
            metadata={"justification": justification, "old_scope_category": old_category},
        )

        return Response(
            {
                "detail": "Scope classification overridden.",
                "id": str(record.id),
                "scope": record.scope,
                "scope_category": record.scope_category,
            },
            status=status.HTTP_200_OK,
        )
