"""
Tests for the audit app — AuditTrailStore service and EmissionRecord
lifecycle integration.

Requirements: 7.5, 12.1, 12.2, 12.3, 12.5
"""

import uuid

import pytest

from audit.models import AuditEvent
from audit.services import AuditTrailStore
from emissions.models import EmissionRecord, Tenant


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_a(db):
    """A primary test tenant."""
    return Tenant.objects.create(name="Tenant Alpha", code="ALPHA")


@pytest.fixture
def tenant_b(db):
    """A secondary test tenant for isolation tests."""
    return Tenant.objects.create(name="Tenant Beta", code="BETA")


@pytest.fixture
def user_id():
    """A stable UUID representing a test user."""
    return str(uuid.uuid4())


def _make_record(tenant, **kwargs):
    """
    Helper: create and save a minimal EmissionRecord for the given tenant.
    Bypasses audit recording by using the raw super().save() path via
    a direct ORM call after construction.
    """
    defaults = dict(
        source_system=EmissionRecord.SOURCE_SAP,
        location="Test Plant",
        fuel_type="diesel",
        scope=1,
        raw_data={},
    )
    defaults.update(kwargs)
    record = EmissionRecord(tenant=tenant, **defaults)
    # Call full_clean + save (which will record a CREATE event).
    record.save()
    return record


# ---------------------------------------------------------------------------
# Task 11.4 tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_event_recorded_on_save(tenant_a, user_id):
    """
    Saving a new EmissionRecord creates exactly one CREATE audit event.

    Requirements: 12.1, 12.2
    """
    record = _make_record(tenant_a)

    events = AuditEvent.objects.filter(
        emission_record_id=record.pk,
        event_type=AuditEvent.EVENT_CREATE,
    )
    assert events.count() == 1, (
        "Expected exactly one CREATE event after first save."
    )
    event = events.first()
    assert event.tenant_id == tenant_a.id
    assert event.emission_record_id == record.pk


@pytest.mark.django_db
def test_update_event_recorded_on_field_change(tenant_a, user_id):
    """
    Changing a tracked field on an existing EmissionRecord creates an
    UPDATE audit event capturing the old and new values.

    Requirements: 7.5, 12.1, 12.2
    """
    record = _make_record(tenant_a)

    old_location = record.location
    record.location = "New Plant"
    record._audit_user_id = user_id
    record.save()

    update_events = AuditEvent.objects.filter(
        emission_record_id=record.pk,
        event_type=AuditEvent.EVENT_UPDATE,
        field_name="location",
    )
    assert update_events.count() == 1, (
        "Expected one UPDATE event for the location field change."
    )
    event = update_events.first()
    assert event.old_value == old_location
    assert event.new_value == "New Plant"
    assert event.user_id == uuid.UUID(user_id)


@pytest.mark.django_db
def test_audit_trail_enforces_tenant_isolation(tenant_a, tenant_b, user_id):
    """
    get_audit_trail() only returns events belonging to the requested tenant.

    Requirements: 1.3, 12.5
    """
    record_a = _make_record(tenant_a)
    record_b = _make_record(tenant_b)

    store = AuditTrailStore()

    trail_a = store.get_audit_trail(
        emission_record_id=str(record_a.pk),
        tenant_id=str(tenant_a.id),
    )
    trail_b = store.get_audit_trail(
        emission_record_id=str(record_b.pk),
        tenant_id=str(tenant_b.id),
    )

    # Each trail should contain only its own record's events.
    record_ids_in_a = {e.emission_record_id for e in trail_a}
    record_ids_in_b = {e.emission_record_id for e in trail_b}

    assert record_a.pk in record_ids_in_a
    assert record_b.pk not in record_ids_in_a

    assert record_b.pk in record_ids_in_b
    assert record_a.pk not in record_ids_in_b

    # Cross-tenant query: asking for record_b's trail under tenant_a should
    # return nothing.
    cross_trail = store.get_audit_trail(
        emission_record_id=str(record_b.pk),
        tenant_id=str(tenant_a.id),
    )
    assert cross_trail == [], (
        "Cross-tenant audit trail query must return an empty list."
    )


@pytest.mark.django_db
def test_audit_events_persist_after_record_deletion(tenant_a, user_id):
    """
    Audit events remain in the database after the associated EmissionRecord
    is deleted.

    Requirements: 12.3
    """
    record = _make_record(tenant_a)
    record_pk = record.pk

    # Confirm the CREATE event exists.
    assert AuditEvent.objects.filter(emission_record_id=record_pk).exists()

    # Delete the emission record directly via the ORM (bypassing the model's
    # delete() override if any).
    EmissionRecord.objects.filter(pk=record_pk).delete()

    # Audit events must still be present.
    surviving_events = AuditEvent.objects.filter(emission_record_id=record_pk)
    assert surviving_events.exists(), (
        "Audit events must persist after the EmissionRecord is deleted."
    )


@pytest.mark.django_db
def test_approve_records_audit_event(tenant_a, user_id):
    """
    Calling approve() on an EmissionRecord creates an APPROVE audit event
    attributed to the supplied user_id.

    Requirements: 10.3, 12.1, 12.2
    """
    record = _make_record(tenant_a)

    record.approve(user_id=user_id)

    approve_events = AuditEvent.objects.filter(
        emission_record_id=record.pk,
        event_type=AuditEvent.EVENT_APPROVE,
    )
    assert approve_events.count() == 1, (
        "Expected exactly one APPROVE event after calling approve()."
    )
    event = approve_events.first()
    assert event.user_id == uuid.UUID(user_id)
    assert event.tenant_id == tenant_a.id

    # Verify the model state was updated.
    record.refresh_from_db()
    assert record.approval_status == EmissionRecord.APPROVAL_APPROVED
    assert record.approved_by_user_id == uuid.UUID(user_id)
    assert record.approved_at is not None
