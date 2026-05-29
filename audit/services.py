"""
Audit Trail Store service for the Breathe ESG Data Ingestion System.

AuditTrailStore is the single point of entry for recording and querying
audit events.  All events are immutable once created (enforced by the
AuditEvent model's save() override).

Requirements: 7.5, 12.1, 12.2, 12.3, 12.5
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from audit.models import AuditEvent


def _to_uuid(value: str) -> uuid.UUID:
    """
    Convert a string to UUID. If the string is not a valid UUID
    (e.g. an integer PK), use a deterministic UUID5 in the DNS namespace.
    """
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        # Integer user IDs — convert deterministically
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(value))


class AuditTrailStore:
    """
    Service for recording and querying immutable audit events.

    Design decisions:
    - No update or delete methods — audit events are append-only.
    - old_value / new_value are stored as JSON (the JSONField handles
      serialization automatically; we accept any JSON-serializable value).
    - Tenant isolation is enforced in every query method.

    Requirements: 7.5, 12.1, 12.2, 12.3, 12.5
    """

    # ------------------------------------------------------------------
    # Task 11.1 — Record an audit event
    # ------------------------------------------------------------------

    def record_event(
        self,
        event_type: str,
        emission_record_id: str,
        user_id: str,
        tenant_id: str,
        field_name: str = "",
        old_value: Any = None,
        new_value: Any = None,
        metadata: Optional[dict] = None,
    ) -> AuditEvent:
        """
        Persist a single audit event and return the saved instance.

        Args:
            event_type:          One of CREATE, UPDATE, APPROVE, REJECT,
                                 LOCK, UNLOCK.
            emission_record_id:  UUID string of the related EmissionRecord.
            user_id:             UUID string of the acting user.
            tenant_id:           UUID string of the owning tenant.
            field_name:          Name of the changed field (UPDATE events).
            old_value:           Previous value — stored as JSON.
            new_value:           New value — stored as JSON.
            metadata:            Arbitrary extra context (e.g. rejection
                                 reason, lock reason).

        Returns:
            The newly created, immutable AuditEvent instance.

        Requirements: 7.5, 12.1, 12.2
        """
        event = AuditEvent(
            event_type=event_type,
            emission_record_id=uuid.UUID(str(emission_record_id)),
            user_id=_to_uuid(user_id),
            tenant_id=uuid.UUID(str(tenant_id)),
            field_name=field_name or "",
            old_value=old_value,
            new_value=new_value,
            metadata=metadata or {},
        )
        event.save()
        return event

    # ------------------------------------------------------------------
    # Task 11.2 — Query audit events
    # ------------------------------------------------------------------

    def get_audit_trail(
        self,
        emission_record_id: str,
        tenant_id: str,
    ) -> list[AuditEvent]:
        """
        Return all audit events for a single emission record.

        Tenant isolation is enforced: only events whose tenant_id matches
        the supplied tenant_id are returned.

        Args:
            emission_record_id: UUID string of the EmissionRecord.
            tenant_id:          UUID string of the requesting tenant.

        Returns:
            List of AuditEvent instances ordered by timestamp descending.

        Requirements: 12.3, 12.5
        """
        return list(
            AuditEvent.objects.for_tenant(uuid.UUID(str(tenant_id))).filter(
                emission_record_id=uuid.UUID(str(emission_record_id))
            )
        )

    def query_audit_events(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[AuditEvent]:
        """
        Query audit events for a tenant with optional filters.

        Args:
            tenant_id:   UUID string of the tenant (required).
            user_id:     Optional UUID string — filter to events by this user.
            start_date:  Optional datetime — include events at or after this
                         timestamp.
            end_date:    Optional datetime — include events at or before this
                         timestamp.

        Returns:
            List of AuditEvent instances ordered by timestamp descending.

        Requirements: 12.5
        """
        qs = AuditEvent.objects.for_tenant(uuid.UUID(str(tenant_id)))

        if user_id is not None:
            qs = qs.filter(user_id=uuid.UUID(str(user_id)))

        if start_date is not None:
            qs = qs.filter(timestamp__gte=start_date)

        if end_date is not None:
            qs = qs.filter(timestamp__lte=end_date)

        return list(qs)
