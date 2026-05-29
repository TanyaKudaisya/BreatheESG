"""
Integration tests for Django REST API endpoints.

Task 13.8: Integration tests for API endpoints

Requirements: 8.1, 8.2, 10.6, 13.2
"""

import pytest
from rest_framework.test import APIClient

from emissions.models import DataQualityFlag, EmissionRecord, Tenant, User


def _make_tenant(code: str) -> Tenant:
    return Tenant.objects.create(name=f"Tenant {code}", code=code)


def _make_user(tenant: Tenant, role: str = "ANALYST") -> User:
    user = User.objects.create_user(
        username=f"user_{tenant.code}_{role}",
        email=f"user_{tenant.code}_{role}@test.com",
        password="testpass123",
        role=role,
        tenant=tenant,
    )
    return user


def _make_record(tenant: Tenant, **kwargs) -> EmissionRecord:
    defaults = dict(
        source_system="SAP",
        location="Test Plant",
        fuel_type="diesel",
        scope=1,
        raw_data={},
    )
    defaults.update(kwargs)
    return EmissionRecord._default_manager.create(tenant=tenant, **defaults)


@pytest.mark.django_db
class TestEmissionsListTenantIsolation:
    """GET /api/v1/emissions/ returns only the authenticated user's tenant records."""

    def test_list_returns_only_own_tenant_records(self):
        tenant_a = _make_tenant("INTEG_A")
        tenant_b = _make_tenant("INTEG_B")
        user_a = _make_user(tenant_a)

        # Create records for both tenants
        record_a = _make_record(tenant_a)
        _make_record(tenant_b)

        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.get("/api/v1/emissions/")
        assert response.status_code == 200

        ids = [r["id"] for r in response.data["results"]]
        assert str(record_a.id) in ids
        # Tenant B's record should NOT appear
        tenant_b_records = EmissionRecord._default_manager.filter(tenant=tenant_b)
        for rec in tenant_b_records:
            assert str(rec.id) not in ids

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get("/api/v1/emissions/")
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestApprovalBlockedByErrorFlags:
    """POST /api/v1/emissions/{id}/approve/ is blocked if ERROR flags present."""

    def test_approve_blocked_with_error_flags(self):
        tenant = _make_tenant("INTEG_C")
        user = _make_user(tenant)
        record = _make_record(tenant)

        # Add an ERROR flag
        DataQualityFlag.objects.create(
            emission_record=record,
            flag_type=DataQualityFlag.FLAG_BLANK_QUANTITY,
            severity=DataQualityFlag.SEVERITY_ERROR,
            message="Blank quantity",
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(f"/api/v1/emissions/{record.id}/approve/")
        assert response.status_code in (400, 403), (
            f"Expected 400/403 when ERROR flags present, got {response.status_code}"
        )

    def test_approve_succeeds_without_error_flags(self):
        tenant = _make_tenant("INTEG_D")
        user = _make_user(tenant)
        record = _make_record(tenant)

        # Add only a WARNING flag (should not block)
        DataQualityFlag.objects.create(
            emission_record=record,
            flag_type=DataQualityFlag.FLAG_ESTIMATED_READING,
            severity=DataQualityFlag.SEVERITY_WARNING,
            message="Estimated reading",
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(f"/api/v1/emissions/{record.id}/approve/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestAuditLockPreventsEditing:
    """POST /api/v1/emissions/{id}/lock/ prevents subsequent PATCH edits."""

    def test_locked_record_cannot_be_edited(self):
        tenant = _make_tenant("INTEG_E")
        user = _make_user(tenant)
        record = _make_record(tenant)

        client = APIClient()
        client.force_authenticate(user=user)

        # Lock the record
        lock_response = client.post(f"/api/v1/emissions/{record.id}/lock/")
        assert lock_response.status_code == 200

        # Attempt to edit — should be blocked
        edit_response = client.patch(
            f"/api/v1/emissions/{record.id}/",
            {"location": "New Location"},
            format="json",
        )
        assert edit_response.status_code in (400, 403), (
            f"Expected 400/403 for locked record edit, got {edit_response.status_code}"
        )
