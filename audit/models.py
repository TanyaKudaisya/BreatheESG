"""
Audit trail models for the Breathe ESG Data Ingestion System.

AuditEvent records are immutable — they are append-only and must never
be updated or deleted.  Tenant isolation is enforced via TenantManager.

Requirements: 7.5, 12.1, 12.2, 12.3, 1.3
"""

import uuid

from django.db import models

from emissions.managers import TenantManager


class AuditEvent(models.Model):
    """
    An immutable record of a change to an EmissionRecord.

    Events are created by the AuditTrailStore service and are never
    modified after creation.  The tenant_id is stored directly on the
    event so that audit trail queries remain efficient even after the
    associated EmissionRecord is deleted.

    Requirements:
        1.3  — Audit_Trail_Store SHALL enforce tenant isolation.
        7.5  — Record original value, new value, timestamp, user_id.
        12.1 — Record every create, update, delete operation.
        12.2 — Record user_id, timestamp, operation type, field changes.
        12.3 — Preserve audit trail even after EmissionRecord deletion.
    """

    # ------------------------------------------------------------------
    # Event type constants
    # ------------------------------------------------------------------

    EVENT_CREATE = "CREATE"
    EVENT_UPDATE = "UPDATE"
    EVENT_APPROVE = "APPROVE"
    EVENT_REJECT = "REJECT"
    EVENT_LOCK = "LOCK"
    EVENT_UNLOCK = "UNLOCK"

    EVENT_TYPE_CHOICES = [
        (EVENT_CREATE, "Record Created"),
        (EVENT_UPDATE, "Field Updated"),
        (EVENT_APPROVE, "Record Approved"),
        (EVENT_REJECT, "Record Rejected"),
        (EVENT_LOCK, "Record Locked for Audit"),
        (EVENT_UNLOCK, "Record Unlocked"),
    ]

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Stored directly (not as FK) so the audit trail survives record deletion.
    emission_record_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the EmissionRecord this event relates to.",
    )

    # tenant_id stored directly for efficient tenant-scoped queries.
    tenant_id = models.UUIDField(
        db_index=True,
        help_text="The Client_Tenant this audit event belongs to.",
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)

    user_id = models.UUIDField(
        help_text="UUID of the user who triggered this event.",
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="UTC timestamp when this event was recorded.",
    )

    # Field-level change tracking (populated for UPDATE events)
    field_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Name of the field that was changed (UPDATE events only).",
    )
    old_value = models.JSONField(
        null=True,
        blank=True,
        help_text="Previous field value, JSON-serialized.",
    )
    new_value = models.JSONField(
        null=True,
        blank=True,
        help_text="New field value, JSON-serialized.",
    )

    # Arbitrary extra context (e.g., rejection reason, lock reason)
    metadata = models.JSONField(
        default=dict,
        help_text="Additional context for this event.",
    )

    # ------------------------------------------------------------------
    # Manager
    # ------------------------------------------------------------------

    objects = TenantManager()

    # ------------------------------------------------------------------
    # Immutability enforcement
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs) -> None:
        """
        Prevent updates to existing audit events.

        Audit events are append-only.  Attempting to save an event that
        already has a primary key (i.e., an update) raises ValueError.
        """
        if self._state.adding is False:
            raise ValueError(
                "AuditEvent records are immutable and cannot be updated. "
                "Create a new event instead."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Prevent deletion of audit events.

        Requirement 12.3: Audit trail entries must be preserved even
        after the associated EmissionRecord is deleted.
        """
        raise ValueError(
            "AuditEvent records are immutable and cannot be deleted."
        )

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    class Meta:
        db_table = "audit_auditevent"
        ordering = ["-timestamp"]
        indexes = [
            # Primary tenant isolation index
            models.Index(fields=["tenant_id"], name="ae_tenant_idx"),
            # Composite index for "get all events for a record within a tenant"
            models.Index(
                fields=["tenant_id", "emission_record_id"],
                name="ae_tenant_record_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"AuditEvent({self.event_type}, record={self.emission_record_id}, "
            f"user={self.user_id}, ts={self.timestamp})"
        )
