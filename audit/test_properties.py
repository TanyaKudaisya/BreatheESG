"""
Property tests for audit trail completeness.

Property 11: Audit trail completeness

Requirements: 7.5, 12.1, 12.2, 12.3
"""

import uuid
import pytest

from audit.models import AuditEvent
from audit.services import AuditTrailStore
from emissions.models import EmissionRecord, Tenant


def _make_tenant(code: str) -> Tenant:
    return Tenant.objects.create(name=f"Tenant {code}", code=code)


def _make_record(tenant: Tenant) -> EmissionRecord:
    return EmissionRecord._default_manager.create(
        tenant=tenant,
        source_system="SAP",
        location="Test Plant",
        fuel_type="diesel",
        scope=1,
        raw_data={},
    )


@pytest.mark.django_db
def test_create_event_has_required_fields():
    """CREATE event contains all required fields."""
    tenant = _make_tenant("PROP11A")
    record = _make_record(tenant)

    events = AuditEvent.objects.filter(
        emission_record_id=record.pk,
        event_type=AuditEvent.EVENT_CREATE,
    )
    assert events.count() == 1
    event = events.first()
    assert event.emission_record_id == record.pk
    assert event.tenant_id == tenant.id
    assert event.timestamp is not None
    assert event.user_id is not None


@pytest.mark.django_db
def test_update_event_captures_field_changes():
    """UPDATE event captures field_name, old_value, new_value."""
    tenant = _make_tenant("PROP11B")
    record = _make_record(tenant)
    user_id = str(uuid.uuid4())

    old_location = record.location
    record.location = "Updated Plant"
    record._audit_user_id = user_id
    record.save()

    update_events = AuditEvent.objects.filter(
        emission_record_id=record.pk,
        event_type=AuditEvent.EVENT_UPDATE,
        field_name="location",
    )
    assert update_events.count() == 1
    event = update_events.first()
    assert event.field_name == "location"
    assert event.old_value == old_location
    assert event.new_value == "Updated Plant"
    assert event.user_id == uuid.UUID(user_id)


@pytest.mark.django_db
def test_audit_events_persist_after_record_deletion():
    """Audit events remain after EmissionRecord is deleted."""
    tenant = _make_tenant("PROP11C")
    record = _make_record(tenant)
    record_pk = record.pk

    assert AuditEvent.objects.filter(emission_record_id=record_pk).exists()

    EmissionRecord.objects.filter(pk=record_pk).delete()

    assert AuditEvent.objects.filter(emission_record_id=record_pk).exists(), (
        "Audit events must persist after EmissionRecord deletion."
    )


@pytest.mark.django_db
def test_audit_trail_tenant_isolation():
    """get_audit_trail enforces tenant isolation."""
    tenant_a = _make_tenant("PROP11D")
    tenant_b = _make_tenant("PROP11E")
    record_a = _make_record(tenant_a)
    record_b = _make_record(tenant_b)

    store = AuditTrailStore()

    trail_a = store.get_audit_trail(str(record_a.pk), str(tenant_a.id))
    trail_b = store.get_audit_trail(str(record_b.pk), str(tenant_b.id))

    ids_in_a = {e.emission_record_id for e in trail_a}
    ids_in_b = {e.emission_record_id for e in trail_b}

    assert record_a.pk in ids_in_a
    assert record_b.pk not in ids_in_a
    assert record_b.pk in ids_in_b
    assert record_a.pk not in ids_in_b
