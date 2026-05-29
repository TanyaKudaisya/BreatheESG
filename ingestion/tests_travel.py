"""
Integration tests for the Travel (Concur) ingestion pipeline.

Tests cover the full path from a Concur JSON payload through to persisted
EmissionRecord and DataQualityFlag model instances.

Requirements: 4.1 – 4.9, 17.2, 17.3, 17.4, 17.5, 18.6, 19.3
"""

from __future__ import annotations

import json
import os
from decimal import Decimal

import pytest

from emissions.models import DataQualityFlag, EmissionRecord, Tenant
from ingestion.ingestion_engine import IngestionEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sample_data",
    "concur_travel_export.json",
)


def _make_tenant(name: str = "Travel Corp", code: str = "TRAVELCORP") -> Tenant:
    """Create and return a Tenant for use in tests."""
    return Tenant.objects.create(name=name, code=code)


def _single_entry_payload(
    report_id: str = "RPT-TEST-0001",
    entry_id: str = "ENT-TEST-0001",
    expense_type: str = "AIRFARE",
    transaction_date: str = "2024-01-08",
    origin_airport: str = "BLR",
    destination_airport: str = "BOM",
    via_airport: str = None,
    cabin_class: str = "ECONOMY",
    distance_km=None,
    approval_status: str = "APPROVED",
    receipt_attached: bool = True,
    employee_id: str = "EMP-0001",
    employee_name: str = "Test Employee",
    department: str = "Engineering",
    city: str = "",
    country: str = "",
    check_in: str = "",
    check_out: str = "",
    nights: int = None,
    fuel_type: str = "",
) -> dict:
    """Build a minimal Concur JSON payload with a single report and entry."""
    entry = {
        "entry_id": entry_id,
        "expense_type": expense_type,
        "transaction_date": transaction_date,
        "receipt_attached": receipt_attached,
    }

    if expense_type == "AIRFARE":
        entry["origin_airport"] = origin_airport
        entry["destination_airport"] = destination_airport
        entry["cabin_class"] = cabin_class
        entry["distance_km"] = distance_km
        if via_airport:
            entry["via_airport"] = via_airport

    if expense_type == "HOTEL":
        entry["city"] = city
        entry["country"] = country
        entry["check_in"] = check_in
        entry["check_out"] = check_out
        entry["nights"] = nights

    if expense_type.startswith("GROUND_TRANSPORT"):
        entry["fuel_type"] = fuel_type
        entry["distance_km"] = distance_km

    return {
        "expense_reports": [
            {
                "report_id": report_id,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "department": department,
                "approval_status": approval_status,
                "entries": [entry],
            }
        ]
    }


# ---------------------------------------------------------------------------
# Test 1: Ingest valid Concur JSON
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIngestValidConcurJson:
    """
    test_ingest_valid_concur_json

    Load sample_data/concur_travel_export.json, ingest it, and verify that
    records_ingested equals the total number of entries across all reports.

    Requirements: 4.1, 7.1, 7.2, 7.3, 7.4
    """

    def test_ingest_valid_concur_json(self):
        tenant = _make_tenant()
        engine = IngestionEngine()

        with open(SAMPLE_DATA_PATH, "r", encoding="utf-8") as fh:
            payload = json.load(fh)

        # Count total entries across all reports in the JSON.
        total_entries = sum(
            len(report.get("entries", []))
            for report in payload.get("expense_reports", [])
        )

        result = engine.ingest_travel_json(
            payload=payload,
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == total_entries, (
            f"Expected {total_entries} ingested records (one per entry); "
            f"got {result.records_ingested}. Errors: {result.errors}"
        )

        db_count = EmissionRecord._default_manager.filter(
            tenant=tenant, source_system="CONCUR"
        ).count()
        assert db_count == total_entries


# ---------------------------------------------------------------------------
# Test 2: Pending approval creates WARNING flag
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPendingApprovalCreatesWarningFlag:
    """
    test_pending_approval_creates_warning_flag

    An AIRFARE entry with approval_status=PENDING_APPROVAL should be ingested
    but must produce a DataQualityFlag of type pending_approval with severity WARNING.

    Requirements: 4.7, 18.5
    """

    def test_pending_approval_creates_warning_flag(self):
        tenant = _make_tenant(name="Pending Corp", code="PENDINGCORP")
        engine = IngestionEngine()

        payload = _single_entry_payload(
            report_id="RPT-PENDING-001",
            entry_id="ENT-PENDING-001",
            expense_type="AIRFARE",
            origin_airport="BLR",
            destination_airport="BOM",
            cabin_class="ECONOMY",
            approval_status="PENDING_APPROVAL",
            receipt_attached=True,
        )

        result = engine.ingest_travel_json(
            payload=payload,
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            report_id="RPT-PENDING-001",
            entry_id="ENT-PENDING-001",
        ).first()
        assert emission_record is not None

        flag = DataQualityFlag.objects.filter(
            emission_record=emission_record,
            flag_type=DataQualityFlag.FLAG_PENDING_APPROVAL,
        ).first()
        assert flag is not None, (
            "Expected a pending_approval DataQualityFlag but none was created."
        )
        assert flag.severity == DataQualityFlag.SEVERITY_WARNING, (
            f"Expected severity=WARNING but got {flag.severity}."
        )


# ---------------------------------------------------------------------------
# Test 3: Missing receipt creates WARNING flag
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMissingReceiptCreatesWarningFlag:
    """
    test_missing_receipt_creates_warning_flag

    An entry with receipt_attached=False should be ingested but must produce
    a DataQualityFlag of type missing_receipt with severity WARNING.

    Requirements: 4.8, 18.2
    """

    def test_missing_receipt_creates_warning_flag(self):
        tenant = _make_tenant(name="No Receipt Corp", code="NORECEIPTCORP")
        engine = IngestionEngine()

        payload = _single_entry_payload(
            report_id="RPT-NORECEIPT-001",
            entry_id="ENT-NORECEIPT-001",
            expense_type="AIRFARE",
            origin_airport="BLR",
            destination_airport="BOM",
            cabin_class="ECONOMY",
            approval_status="APPROVED",
            receipt_attached=False,
        )

        result = engine.ingest_travel_json(
            payload=payload,
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            report_id="RPT-NORECEIPT-001",
            entry_id="ENT-NORECEIPT-001",
        ).first()
        assert emission_record is not None

        flag = DataQualityFlag.objects.filter(
            emission_record=emission_record,
            flag_type=DataQualityFlag.FLAG_MISSING_RECEIPT,
        ).first()
        assert flag is not None, (
            "Expected a missing_receipt DataQualityFlag but none was created."
        )
        assert flag.severity == DataQualityFlag.SEVERITY_WARNING, (
            f"Expected severity=WARNING but got {flag.severity}."
        )


# ---------------------------------------------------------------------------
# Test 4: Unknown airport creates WARNING flag and distance_km is None
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnknownAirportCreatesWarningFlag:
    """
    test_unknown_airport_creates_warning_flag

    An AIRFARE entry with an unknown airport code (e.g. "ZZZ") should be
    ingested with a DataQualityFlag of type unknown_airport (WARNING) and
    distance_km should be None on the EmissionRecord.

    Requirements: 4.5, 17.4, 18.6
    """

    def test_unknown_airport_creates_warning_flag(self):
        tenant = _make_tenant(name="Unknown Airport Corp", code="UNKNOWNAIRPORT")
        engine = IngestionEngine()

        payload = _single_entry_payload(
            report_id="RPT-UNKNOWNAIR-001",
            entry_id="ENT-UNKNOWNAIR-001",
            expense_type="AIRFARE",
            origin_airport="ZZZ",
            destination_airport="BOM",
            cabin_class="ECONOMY",
            approval_status="APPROVED",
            receipt_attached=True,
            distance_km=None,
        )

        result = engine.ingest_travel_json(
            payload=payload,
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            report_id="RPT-UNKNOWNAIR-001",
            entry_id="ENT-UNKNOWNAIR-001",
        ).first()
        assert emission_record is not None

        # distance_km should be None because the airport was unknown.
        assert emission_record.distance_km is None, (
            f"Expected distance_km=None for unknown airport but got "
            f"{emission_record.distance_km}."
        )

        flag = DataQualityFlag.objects.filter(
            emission_record=emission_record,
            flag_type=DataQualityFlag.FLAG_UNKNOWN_AIRPORT,
        ).first()
        assert flag is not None, (
            "Expected an unknown_airport DataQualityFlag but none was created."
        )
        assert flag.severity == DataQualityFlag.SEVERITY_WARNING, (
            f"Expected severity=WARNING but got {flag.severity}."
        )


# ---------------------------------------------------------------------------
# Test 5: Business cabin class multiplier
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBusinessCabinClassMultiplier:
    """
    test_business_cabin_class_multiplier

    An AIRFARE entry with known airports (BLR→BOM) and cabin_class=BUSINESS
    should have distance_km on the EmissionRecord equal to
    haversine(BLR, BOM) * 3.0.

    Requirements: 4.6
    """

    def test_business_cabin_class_multiplier(self):
        tenant = _make_tenant(name="Business Class Corp", code="BUSINESSCLASS")
        engine = IngestionEngine()

        payload = _single_entry_payload(
            report_id="RPT-BUSINESS-001",
            entry_id="ENT-BUSINESS-001",
            expense_type="AIRFARE",
            origin_airport="BLR",
            destination_airport="BOM",
            cabin_class="BUSINESS",
            approval_status="APPROVED",
            receipt_attached=True,
            distance_km=None,
        )

        result = engine.ingest_travel_json(
            payload=payload,
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            report_id="RPT-BUSINESS-001",
            entry_id="ENT-BUSINESS-001",
        ).first()
        assert emission_record is not None
        assert emission_record.distance_km is not None, (
            "Expected distance_km to be set for a BUSINESS class flight with known airports."
        )

        # Calculate the expected distance using the same calculator.
        from ingestion.airport_distance import AirportDistanceCalculator
        calc = AirportDistanceCalculator()
        direct_result = calc.calculate_distance("BLR", "BOM")
        expected_distance = direct_result.distance_km * Decimal("3.0")

        assert emission_record.distance_km == expected_distance, (
            f"Expected distance_km={expected_distance} (haversine * 3.0) "
            f"but got {emission_record.distance_km}."
        )


# ---------------------------------------------------------------------------
# Test 6: Duplicate report+entry creates potential_duplicate flag
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDuplicateReportEntryCreatesPotentialDuplicateFlag:
    """
    test_duplicate_report_entry_creates_potential_duplicate_flag

    When the same report_id + entry_id combination is ingested twice for the
    same tenant, the second ingestion should produce a DataQualityFlag of
    type potential_duplicate.

    Requirements: 19.3, 19.4
    """

    def test_duplicate_report_entry_creates_potential_duplicate_flag(self):
        tenant = _make_tenant(name="Dup Travel Corp", code="DUPTRAVELCORP")
        engine = IngestionEngine()

        payload = _single_entry_payload(
            report_id="RPT-DUP-001",
            entry_id="ENT-DUP-001",
            expense_type="AIRFARE",
            origin_airport="BLR",
            destination_airport="BOM",
            cabin_class="ECONOMY",
            approval_status="APPROVED",
            receipt_attached=True,
        )

        # First ingestion — no duplicate flag expected.
        result1 = engine.ingest_travel_json(
            payload=payload,
            tenant_id=str(tenant.id),
        )
        assert result1.records_ingested == 1, (
            f"First ingestion: expected 1 record; got {result1.records_ingested}. "
            f"Errors: {result1.errors}"
        )

        first_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            report_id="RPT-DUP-001",
            entry_id="ENT-DUP-001",
        ).first()
        assert first_record is not None
        assert not DataQualityFlag.objects.filter(
            emission_record=first_record,
            flag_type=DataQualityFlag.FLAG_POTENTIAL_DUPLICATE,
        ).exists(), "First ingestion should not have a potential_duplicate flag."

        # Second ingestion of the same entry — duplicate flag expected.
        result2 = engine.ingest_travel_json(
            payload=payload,
            tenant_id=str(tenant.id),
        )
        assert result2.records_ingested == 1, (
            f"Second ingestion: expected 1 record; got {result2.records_ingested}. "
            f"Errors: {result2.errors}"
        )

        second_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            report_id="RPT-DUP-001",
            entry_id="ENT-DUP-001",
        ).order_by("-ingestion_timestamp").first()
        assert second_record is not None

        dup_flags = DataQualityFlag.objects.filter(
            emission_record=second_record,
            flag_type=DataQualityFlag.FLAG_POTENTIAL_DUPLICATE,
        )
        assert dup_flags.exists(), (
            "Expected a potential_duplicate DataQualityFlag on the second ingestion "
            "but none was created."
        )


# ---------------------------------------------------------------------------
# Test 7: Multi-leg flight calculates total distance
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMultiLegFlightCalculatesTotalDistance:
    """
    test_multi_leg_flight_calculates_total_distance

    An AIRFARE entry with via_airport (RPR→HYD→BLR) should have distance_km
    equal to the sum of both legs: haversine(RPR, HYD) + haversine(HYD, BLR).

    Requirements: 4.9, 17.5
    """

    def test_multi_leg_flight_calculates_total_distance(self):
        tenant = _make_tenant(name="Multi Leg Corp", code="MULTILEGCORP")
        engine = IngestionEngine()

        payload = _single_entry_payload(
            report_id="RPT-MULTILEG-001",
            entry_id="ENT-MULTILEG-001",
            expense_type="AIRFARE",
            origin_airport="RPR",
            destination_airport="BLR",
            via_airport="HYD",
            cabin_class="ECONOMY",
            approval_status="APPROVED",
            receipt_attached=True,
            distance_km=None,
        )

        result = engine.ingest_travel_json(
            payload=payload,
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            report_id="RPT-MULTILEG-001",
            entry_id="ENT-MULTILEG-001",
        ).first()
        assert emission_record is not None
        assert emission_record.distance_km is not None, (
            "Expected distance_km to be set for a multi-leg flight with known airports."
        )

        # Calculate expected total distance: RPR→HYD + HYD→BLR.
        from ingestion.airport_distance import AirportDistanceCalculator
        calc = AirportDistanceCalculator()
        leg1 = calc.calculate_distance("RPR", "HYD").distance_km
        leg2 = calc.calculate_distance("HYD", "BLR").distance_km
        expected_total = leg1 + leg2

        assert emission_record.distance_km == expected_total, (
            f"Expected distance_km={expected_total} (RPR→HYD + HYD→BLR) "
            f"but got {emission_record.distance_km}."
        )
