"""
Core emission data models for the Breathe ESG Data Ingestion System.

These models implement multi-tenant row-level security via TenantManager.
The Tenant model is the root of the multi-tenancy hierarchy; every
EmissionRecord, DataQualityFlag, and User is scoped to exactly one Tenant.

Requirements: 1.1, 1.2, 1.3, 1.4, 7.5, 12.1, 12.2
"""

import uuid
from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from emissions.managers import TenantManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_json_value(value: object) -> object:
    """
    Convert a model field value to a JSON-serializable form.

    Django's JSONField handles most types natively, but date/datetime
    objects need to be converted to strings first.
    """
    import datetime as _dt  # noqa: PLC0415

    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return value


def _user_id_to_uuid(user_id) -> uuid.UUID:
    """
    Convert a user identifier to UUID.

    Handles both UUID strings and integer PKs (Django's default BigAutoField).
    Integer PKs are converted to a deterministic UUID5.
    """
    try:
        return uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id))


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------


class Tenant(models.Model):
    """
    A distinct client company with isolated data.

    All emission records, users, and audit events are scoped to a Tenant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Short identifier used in API paths and reports.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "emissions_tenant"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(AbstractUser):
    """
    Custom user model that extends Django's AbstractUser with tenant
    association and role-based access control.

    The ``tenant`` FK links each user to exactly one Client_Tenant,
    enabling TenantMiddleware to set the correct tenant context on every
    authenticated request.

    Requirements: 1.2, 1.4
    """

    ROLE_ANALYST = "ANALYST"
    ROLE_AUDITOR = "AUDITOR"
    ROLE_ADMIN = "ADMIN"
    ROLE_CHOICES = [
        (ROLE_ANALYST, "Sustainability Analyst"),
        (ROLE_AUDITOR, "Auditor"),
        (ROLE_ADMIN, "Administrator"),
    ]

    # Nullable to allow superusers / admin accounts not scoped to a tenant.
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text="The Client_Tenant this user belongs to.",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_ANALYST,
    )

    class Meta:
        db_table = "emissions_user"

    @property
    def tenant_id(self):
        """
        Convenience property so TenantMiddleware can read ``user.tenant_id``
        regardless of whether the underlying field is a UUID or a FK.
        """
        return None if self.tenant is None else self.tenant.id

    def __str__(self) -> str:
        return f"{self.username} (tenant={self.tenant}, role={self.role})"


# ---------------------------------------------------------------------------
# EmissionRecord
# ---------------------------------------------------------------------------


class EmissionRecord(models.Model):
    """
    A single normalized emission activity record.

    Every record is scoped to exactly one Tenant.  The TenantManager
    ensures that all ORM queries are automatically filtered to the current
    request's tenant when a tenant context is active.

    Requirements: 1.1 — every EmissionRecord must have exactly one
    non-null tenant.
    """

    # ------------------------------------------------------------------
    # Primary key & tenant association
    # ------------------------------------------------------------------

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="emission_records",
        help_text="The Client_Tenant this record belongs to.",
    )

    # ------------------------------------------------------------------
    # Source tracking (Req 7.1 – 7.4)
    # ------------------------------------------------------------------

    SOURCE_SAP = "SAP"
    SOURCE_UTILITY = "UTILITY"
    SOURCE_CONCUR = "CONCUR"
    SOURCE_SYSTEM_CHOICES = [
        (SOURCE_SAP, "SAP Fuel Procurement"),
        (SOURCE_UTILITY, "Utility Electricity"),
        (SOURCE_CONCUR, "Concur Travel"),
    ]

    source_system = models.CharField(
        max_length=20,
        choices=SOURCE_SYSTEM_CHOICES,
        help_text="Originating source system.",
    )
    ingestion_timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="UTC timestamp when this record was ingested.",
    )
    original_filename = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Original filename or API endpoint that produced this record.",
    )
    raw_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Original raw payload preserved for audit purposes.",
    )

    # ------------------------------------------------------------------
    # Core emission fields
    # ------------------------------------------------------------------

    transaction_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of the underlying transaction (ISO 8601).",
    )
    location = models.CharField(max_length=255, blank=True, default="")
    fuel_type = models.CharField(max_length=255, blank=True, default="")

    original_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        null=True,
        blank=True,
    )
    original_unit = models.CharField(max_length=50, blank=True, default="")
    normalized_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        null=True,
        blank=True,
    )
    normalized_unit = models.CharField(max_length=50, blank=True, default="")

    # ------------------------------------------------------------------
    # GHG scope classification (Req 14.1 – 14.4)
    # ------------------------------------------------------------------

    scope = models.IntegerField(null=True, blank=True)
    scope_category = models.IntegerField(null=True, blank=True)

    # ------------------------------------------------------------------
    # Approval workflow (Req 10.x)
    # ------------------------------------------------------------------

    APPROVAL_PENDING = "PENDING"
    APPROVAL_APPROVED = "APPROVED"
    APPROVAL_REJECTED = "REJECTED"
    APPROVAL_STATUS_CHOICES = [
        (APPROVAL_PENDING, "Pending Review"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default=APPROVAL_PENDING,
    )
    approved_by_user_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")

    # ------------------------------------------------------------------
    # Audit lock (Req 13.x)
    # ------------------------------------------------------------------

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by_user_id = models.UUIDField(null=True, blank=True)

    # ------------------------------------------------------------------
    # SAP-specific fields (Req 2.1, 2.3)
    # ------------------------------------------------------------------

    ebeln = models.CharField(max_length=20, blank=True, default="", help_text="SAP Purchase Order number")
    ebelp = models.CharField(max_length=10, blank=True, default="", help_text="SAP Purchase Order item")
    bedat = models.DateField(null=True, blank=True, help_text="SAP document date")
    werks = models.CharField(max_length=10, blank=True, default="", help_text="SAP plant code")
    plant_name = models.CharField(max_length=255, blank=True, default="")
    plant_location = models.CharField(max_length=255, blank=True, default="")
    plant_state = models.CharField(max_length=100, blank=True, default="")
    plant_country = models.CharField(max_length=100, blank=True, default="")
    matnr = models.CharField(max_length=40, blank=True, default="", help_text="SAP material number")
    material_description = models.CharField(max_length=255, blank=True, default="", help_text="SAP TXZ01 field")
    netpr = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, help_text="SAP net price")
    currency = models.CharField(max_length=10, blank=True, default="", help_text="SAP WAERS currency code")

    # ------------------------------------------------------------------
    # Utility-specific fields (Req 3.1, 3.2)
    # ------------------------------------------------------------------

    account_number = models.CharField(max_length=100, blank=True, default="")
    meter_id = models.CharField(max_length=100, blank=True, default="")
    service_address = models.CharField(max_length=512, blank=True, default="")
    billing_period_start = models.DateField(null=True, blank=True)
    billing_period_end = models.DateField(null=True, blank=True)
    consumption_kwh = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    reading_type = models.CharField(max_length=20, blank=True, default="", help_text="ACTUAL or ESTIMATED")
    tariff_code = models.CharField(max_length=50, blank=True, default="")
    demand_kw = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    # ------------------------------------------------------------------
    # Travel-specific fields (Req 4.1 – 4.9)
    # ------------------------------------------------------------------

    report_id = models.CharField(max_length=100, blank=True, default="", help_text="Concur expense report ID")
    entry_id = models.CharField(max_length=100, blank=True, default="", help_text="Concur expense entry ID")
    expense_type = models.CharField(max_length=50, blank=True, default="", help_text="AIRFARE, HOTEL, GROUND_TRANSPORT_*")
    employee_id = models.CharField(max_length=100, blank=True, default="")
    employee_name = models.CharField(max_length=255, blank=True, default="")
    department = models.CharField(max_length=255, blank=True, default="")
    travel_approval_status = models.CharField(max_length=50, blank=True, default="", help_text="Concur approval status")
    receipt_attached = models.BooleanField(null=True, blank=True)
    origin_airport = models.CharField(max_length=10, blank=True, default="")
    destination_airport = models.CharField(max_length=10, blank=True, default="")
    via_airport = models.CharField(max_length=10, blank=True, default="")
    cabin_class = models.CharField(max_length=20, blank=True, default="", help_text="ECONOMY or BUSINESS")
    distance_km = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    hotel_city = models.CharField(max_length=255, blank=True, default="")
    hotel_country = models.CharField(max_length=100, blank=True, default="")
    check_in = models.DateField(null=True, blank=True)
    check_out = models.DateField(null=True, blank=True)
    nights = models.IntegerField(null=True, blank=True)
    ground_fuel_type = models.CharField(max_length=100, blank=True, default="")

    # ------------------------------------------------------------------
    # Manager (EmissionRecord)
    # ------------------------------------------------------------------

    objects = TenantManager()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        """
        Validate that tenant is set before saving.

        Requirement 1.1: Every EmissionRecord must be associated with
        exactly one Client_Tenant identifier.
        """
        super().clean()
        if self.tenant_id is None:
            raise ValidationError(
                {"tenant": "An EmissionRecord must be associated with a tenant."}
            )

    def save(self, *args, **kwargs) -> None:
        """
        Call full_clean() before persisting to enforce tenant validation
        and any other model-level constraints.

        Records a CREATE audit event on first save and an UPDATE audit
        event (with changed fields) on subsequent saves.

        The ``_audit_user_id`` attribute may be set on the instance before
        calling save() to attribute the change to a specific user.  When
        not set, a nil UUID is used as a sentinel for system-generated
        changes (e.g. ingestion engine).

        Requirements: 7.5, 12.1, 12.2
        """
        # Determine whether this is a new record or an update.
        is_new = self._state.adding

        # Capture the pre-save state for UPDATE diff (only for existing records).
        changed_fields: list[tuple[str, object, object]] = []
        if not is_new and self.pk:
            try:
                old = EmissionRecord.objects.get(pk=self.pk)
                # Fields that analysts can edit and that we want to track.
                tracked_fields = [
                    "original_quantity",
                    "original_unit",
                    "normalized_quantity",
                    "normalized_unit",
                    "transaction_date",
                    "location",
                    "fuel_type",
                    "scope",
                    "scope_category",
                    "approval_status",
                    "rejection_reason",
                    "is_locked",
                ]
                for field in tracked_fields:
                    old_val = getattr(old, field, None)
                    new_val = getattr(self, field, None)
                    if old_val != new_val:
                        changed_fields.append((field, old_val, new_val))
            except EmissionRecord.DoesNotExist:
                # Record was deleted between the check and the save — treat
                # as a new record.
                is_new = True

        self.full_clean()
        super().save(*args, **kwargs)

        # Record audit events after the save so the record definitely exists.
        self._record_save_audit_events(is_new, changed_fields)

    def _record_save_audit_events(
        self,
        is_new: bool,
        changed_fields: list[tuple[str, object, object]],
    ) -> None:
        """
        Internal helper — records CREATE or UPDATE audit events after save.

        Imported lazily to avoid a circular import between emissions and audit.
        """
        # Lazy import to avoid circular dependency (audit.services imports
        # audit.models which is fine, but audit.models does not import
        # emissions.models — the circular risk is the other direction).
        from audit.services import AuditTrailStore  # noqa: PLC0415

        store = AuditTrailStore()
        user_id = str(getattr(self, "_audit_user_id", uuid.UUID(int=0)))
        tenant_id = str(self.tenant_id)
        record_id = str(self.pk)

        if is_new:
            store.record_event(
                event_type="CREATE",
                emission_record_id=record_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        else:
            for field_name, old_val, new_val in changed_fields:
                # Coerce values to JSON-serializable types.
                store.record_event(
                    event_type="UPDATE",
                    emission_record_id=record_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    field_name=field_name,
                    old_value=_to_json_value(old_val),
                    new_value=_to_json_value(new_val),
                )

    # ------------------------------------------------------------------
    # Approval / rejection workflow (Req 10.x, 12.1, 12.2)
    # ------------------------------------------------------------------

    def approve(self, user_id: str) -> None:
        """
        Mark this record as approved and record an APPROVE audit event.

        Args:
            user_id: UUID string of the approving user.

        Requirements: 10.3, 12.1, 12.2
        """
        from audit.services import AuditTrailStore  # noqa: PLC0415

        self.approval_status = self.APPROVAL_APPROVED
        self.approved_by_user_id = _user_id_to_uuid(user_id)
        self.approved_at = timezone.now()
        # Bypass audit-diff logic for this targeted update.
        self._audit_user_id = user_id
        self.full_clean()
        EmissionRecord.objects.filter(pk=self.pk).update(
            approval_status=self.approval_status,
            approved_by_user_id=self.approved_by_user_id,
            approved_at=self.approved_at,
        )
        # Refresh from DB so instance state is consistent.
        self.refresh_from_db()

        AuditTrailStore().record_event(
            event_type="APPROVE",
            emission_record_id=str(self.pk),
            user_id=str(user_id),
            tenant_id=str(self.tenant_id),
        )

    def reject(self, user_id: str, reason: str = "") -> None:
        """
        Mark this record as rejected and record a REJECT audit event.

        Args:
            user_id: UUID string of the rejecting user.
            reason:  Human-readable rejection reason.

        Requirements: 10.4, 12.1, 12.2
        """
        from audit.services import AuditTrailStore  # noqa: PLC0415

        self.approval_status = self.APPROVAL_REJECTED
        self.rejection_reason = reason
        self.full_clean()
        EmissionRecord.objects.filter(pk=self.pk).update(
            approval_status=self.approval_status,
            rejection_reason=self.rejection_reason,
        )
        self.refresh_from_db()

        AuditTrailStore().record_event(
            event_type="REJECT",
            emission_record_id=str(self.pk),
            user_id=str(user_id),
            tenant_id=str(self.tenant_id),
            metadata={"reason": reason},
        )

    # ------------------------------------------------------------------
    # Audit lock / unlock (Req 13.x, 12.1, 12.2)
    # ------------------------------------------------------------------

    def lock(self, user_id: str) -> None:
        """
        Lock this record for audit and record a LOCK audit event.

        Args:
            user_id: UUID string of the user locking the record.

        Requirements: 13.1, 13.5, 12.1, 12.2
        """
        from audit.services import AuditTrailStore  # noqa: PLC0415

        self.is_locked = True
        self.locked_at = timezone.now()
        self.locked_by_user_id = _user_id_to_uuid(user_id)
        self.full_clean()
        EmissionRecord.objects.filter(pk=self.pk).update(
            is_locked=self.is_locked,
            locked_at=self.locked_at,
            locked_by_user_id=self.locked_by_user_id,
        )
        self.refresh_from_db()

        AuditTrailStore().record_event(
            event_type="LOCK",
            emission_record_id=str(self.pk),
            user_id=str(user_id),
            tenant_id=str(self.tenant_id),
        )

    def unlock(self, user_id: str) -> None:
        """
        Unlock this record and record an UNLOCK audit event.

        Args:
            user_id: UUID string of the user unlocking the record
                     (must have auditor role — enforced at the API layer).

        Requirements: 13.4, 12.1, 12.2
        """
        from audit.services import AuditTrailStore  # noqa: PLC0415

        self.is_locked = False
        self.full_clean()
        EmissionRecord.objects.filter(pk=self.pk).update(is_locked=False)
        self.refresh_from_db()

        AuditTrailStore().record_event(
            event_type="UNLOCK",
            emission_record_id=str(self.pk),
            user_id=str(user_id),
            tenant_id=str(self.tenant_id),
        )

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    class Meta:
        db_table = "emissions_emissionrecord"
        ordering = ["-ingestion_timestamp"]
        indexes = [
            # Primary tenant isolation index
            models.Index(fields=["tenant_id"], name="er_tenant_idx"),
            # Composite indexes for common dashboard query patterns
            models.Index(
                fields=["tenant_id", "source_system"],
                name="er_tenant_source_idx",
            ),
            models.Index(
                fields=["tenant_id", "transaction_date"],
                name="er_tenant_date_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"EmissionRecord({self.id}, tenant={self.tenant_id}, "
            f"source={self.source_system}, date={self.transaction_date})"
        )


# ---------------------------------------------------------------------------
# DataQualityFlag
# ---------------------------------------------------------------------------


class DataQualityFlag(models.Model):
    """
    A data quality issue marker attached to an EmissionRecord.

    Flags are created by the ValidationService and reviewed by analysts
    before records can be approved.

    Requirements: 2.5, 3.3, 4.7, 4.8, 6.5, 18.x
    """

    # ------------------------------------------------------------------
    # Flag type constants
    # ------------------------------------------------------------------

    FLAG_ESTIMATED_READING = "estimated_reading"
    FLAG_MISSING_RECEIPT = "missing_receipt"
    FLAG_ZERO_PRICE = "zero_price"
    FLAG_BLANK_QUANTITY = "blank_quantity"
    FLAG_PENDING_APPROVAL = "pending_approval"
    FLAG_UNKNOWN_AIRPORT = "unknown_airport"
    FLAG_UNKNOWN_UNIT = "unknown_unit"
    FLAG_POTENTIAL_DUPLICATE = "potential_duplicate"

    FLAG_TYPE_CHOICES = [
        (FLAG_ESTIMATED_READING, "Estimated Reading"),
        (FLAG_MISSING_RECEIPT, "Missing Receipt"),
        (FLAG_ZERO_PRICE, "Zero Price"),
        (FLAG_BLANK_QUANTITY, "Blank Quantity"),
        (FLAG_PENDING_APPROVAL, "Pending Approval"),
        (FLAG_UNKNOWN_AIRPORT, "Unknown Airport"),
        (FLAG_UNKNOWN_UNIT, "Unknown Unit"),
        (FLAG_POTENTIAL_DUPLICATE, "Potential Duplicate"),
    ]

    SEVERITY_WARNING = "WARNING"
    SEVERITY_ERROR = "ERROR"
    SEVERITY_CHOICES = [
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_ERROR, "Error"),
    ]

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emission_record = models.ForeignKey(
        EmissionRecord,
        on_delete=models.CASCADE,
        related_name="quality_flags",
    )
    flag_type = models.CharField(max_length=50, choices=FLAG_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    message = models.TextField()
    field_name = models.CharField(max_length=100, blank=True, default="")
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_user_id = models.UUIDField(null=True, blank=True)

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    class Meta:
        db_table = "emissions_dataqualityflag"
        indexes = [
            # Composite index for the common "show unresolved flags for record" query
            models.Index(
                fields=["emission_record_id", "is_resolved"],
                name="dqf_record_resolved_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"DataQualityFlag({self.flag_type}/{self.severity}, "
            f"record={self.emission_record_id})"
        )


# ---------------------------------------------------------------------------
# MonthlyAllocation
# ---------------------------------------------------------------------------


class MonthlyAllocation(models.Model):
    """
    Proportional allocation of a utility billing period across calendar months.

    Requirements: 20.2, 20.3
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emission_record = models.ForeignKey(
        EmissionRecord,
        on_delete=models.CASCADE,
        related_name="monthly_allocations",
    )
    year = models.IntegerField()
    month = models.IntegerField()
    allocated_quantity = models.DecimalField(max_digits=20, decimal_places=6)
    unit = models.CharField(max_length=50)

    class Meta:
        db_table = "emissions_monthlyallocation"
        ordering = ["year", "month"]
        unique_together = [("emission_record", "year", "month")]

    def __str__(self) -> str:
        return (
            f"MonthlyAllocation({self.year}-{self.month:02d}, "
            f"qty={self.allocated_quantity} {self.unit})"
        )
