"""
Integration tests for the Utility ingestion pipeline.

Tests cover the full path from raw CSV bytes through to persisted
EmissionRecord, MonthlyAllocation, and DataQualityFlag model instances.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 20.1, 20.2, 20.3
"""

from __future__ import annotations

import os

import pytest

from emissions.models import DataQualityFlag, EmissionRecord, MonthlyAllocation, Tenant
from ingestion.ingestion_engine import IngestionEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant(name: str = "Utility Corp", code: str = "UTILITYCORP") -> Tenant:
    """Create and return a Tenant for use in tests."""
    return Tenant.objects.create(name=name, code=code)


def _csv_file(*rows: str) -> bytes:
    """
    Build a utility CSV file from a sequence of row strings.

    The first row must be the header.
    """
    content = "\n".join(rows)
    return content.encode("utf-8")


HEADER = (
    "account_number,meter_id,service_address,billing_period_start,"
    "billing_period_end,bill_date,due_date,reading_type,prev_reading_kwh,"
    "curr_reading_kwh,consumption_kwh,demand_kw,supply_charge_inr,"
    "distribution_charge_inr,fuel_adjustment_inr,tod_peak_kwh,tod_offpeak_kwh,"
    "power_factor_penalty_inr,electricity_duty_inr,total_amount_inr,"
    "tariff_code,rate_per_kwh,currency"
)

SAMPLE_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sample_data",
    "utility_electricity.csv",
)


def _make_row(
    account_number: str = "MSEDCL-ENT-00451",
    meter_id: str = "MTR-PNE-001",
    service_address: str = "Plot 42 Bhosari MIDC Pune 411026",
    billing_period_start: str = "2024-01-04",
    billing_period_end: str = "2024-02-03",
    reading_type: str = "ACTUAL",
    consumption_kwh: str = "16270",
    demand_kw: str = "142.5",
    tariff_code: str = "HT-1A",
) -> str:
    """Return a single CSV data row with sensible defaults."""
    return (
        f"{account_number},{meter_id},{service_address},"
        f"{billing_period_start},{billing_period_end},"
        f"2024-02-05,2024-02-20,{reading_type},"
        f"1482350,1498620,{consumption_kwh},{demand_kw},"
        f"1200.00,138295.00,4072.50,9762,6508,0.00,14236.75,157804.25,"
        f"{tariff_code},8.51,INR"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIngestValidUtilityCSV:
    """
    test_ingest_valid_utility_csv

    Ingest sample_data/utility_electricity.csv and verify that at least one
    EmissionRecord is created.

    Requirements: 3.1, 3.2, 7.1, 7.2, 7.3, 7.4
    """

    def test_ingest_valid_utility_csv(self):
        tenant = _make_tenant()
        engine = IngestionEngine()

        with open(SAMPLE_DATA_PATH, "rb") as fh:
            file_content = fh.read()

        result = engine.ingest_utility_file(
            file_content=file_content,
            filename="utility_electricity.csv",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested > 0, (
            f"Expected at least one ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )
        db_count = EmissionRecord._default_manager.filter(
            tenant=tenant, source_system="UTILITY"
        ).count()
        assert db_count == result.records_ingested


@pytest.mark.django_db
class TestEstimatedReadingCreatesWarningFlag:
    """
    test_estimated_reading_creates_warning_flag

    A row with reading_type=ESTIMATED should be ingested but must produce a
    DataQualityFlag of type estimated_reading with severity WARNING.

    Requirements: 3.3, 18.1
    """

    def test_estimated_reading_creates_warning_flag(self):
        tenant = _make_tenant(name="Estimated Corp", code="ESTIMATED")
        engine = IngestionEngine()

        row = _make_row(
            account_number="TNEB-ENT-00812",
            meter_id="MTR-CHN-002",
            reading_type="ESTIMATED",
        )
        file_content = _csv_file(HEADER, row)

        result = engine.ingest_utility_file(
            file_content=file_content,
            filename="estimated_test.csv",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            account_number="TNEB-ENT-00812",
            meter_id="MTR-CHN-002",
        ).first()
        assert emission_record is not None

        flag = DataQualityFlag.objects.filter(
            emission_record=emission_record,
            flag_type=DataQualityFlag.FLAG_ESTIMATED_READING,
        ).first()
        assert flag is not None, (
            "Expected an estimated_reading DataQualityFlag but none was created."
        )
        assert flag.severity == DataQualityFlag.SEVERITY_WARNING, (
            f"Expected severity=WARNING but got {flag.severity}."
        )


@pytest.mark.django_db
class TestBillingPeriodSpanningTwoMonthsCreatesTwoAllocations:
    """
    test_billing_period_spanning_two_months_creates_two_allocations

    A billing period from Jan 4 to Feb 3 spans two calendar months and
    should produce exactly 2 MonthlyAllocation records.

    Requirements: 20.1, 20.2, 20.3
    """

    def test_billing_period_spanning_two_months_creates_two_allocations(self):
        tenant = _make_tenant(name="Two Month Corp", code="TWOMONTH")
        engine = IngestionEngine()

        row = _make_row(
            account_number="MSEDCL-ENT-00451",
            meter_id="MTR-PNE-001",
            billing_period_start="2024-01-04",
            billing_period_end="2024-02-03",
            consumption_kwh="16270",
        )
        file_content = _csv_file(HEADER, row)

        result = engine.ingest_utility_file(
            file_content=file_content,
            filename="two_month_test.csv",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            account_number="MSEDCL-ENT-00451",
            meter_id="MTR-PNE-001",
        ).first()
        assert emission_record is not None

        allocations = MonthlyAllocation.objects.filter(
            emission_record=emission_record
        ).order_by("year", "month")

        assert allocations.count() == 2, (
            f"Expected 2 MonthlyAllocation records for a Jan–Feb billing period; "
            f"got {allocations.count()}."
        )

        months = [(a.year, a.month) for a in allocations]
        assert (2024, 1) in months, "Expected a January 2024 allocation."
        assert (2024, 2) in months, "Expected a February 2024 allocation."

        # Verify the sum of allocations equals the original consumption.
        from decimal import Decimal
        total_allocated = sum(a.allocated_quantity for a in allocations)
        assert total_allocated == Decimal("16270"), (
            f"Expected total allocated = 16270 but got {total_allocated}."
        )


@pytest.mark.django_db
class TestDuplicateCreatesPotentialDuplicateFlag:
    """
    test_duplicate_creates_potential_duplicate_flag

    When the same account_number + meter_id + billing_period_start is ingested
    twice for the same tenant, the second ingestion should produce a
    DataQualityFlag of type potential_duplicate.

    Requirements: 19.2
    """

    def test_duplicate_creates_potential_duplicate_flag(self):
        tenant = _make_tenant(name="Dup Utility Corp", code="DUPUTILITY")
        engine = IngestionEngine()

        row = _make_row(
            account_number="MSEDCL-ENT-00451",
            meter_id="MTR-PNE-001",
            billing_period_start="2024-01-04",
            billing_period_end="2024-02-03",
        )
        file_content = _csv_file(HEADER, row)

        # First ingestion — no duplicate flag expected.
        result1 = engine.ingest_utility_file(
            file_content=file_content,
            filename="dup_utility_first.csv",
            tenant_id=str(tenant.id),
        )
        assert result1.records_ingested == 1, (
            f"First ingestion: expected 1 record; got {result1.records_ingested}. "
            f"Errors: {result1.errors}"
        )

        first_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            account_number="MSEDCL-ENT-00451",
            meter_id="MTR-PNE-001",
        ).first()
        assert first_record is not None
        assert not DataQualityFlag.objects.filter(
            emission_record=first_record,
            flag_type=DataQualityFlag.FLAG_POTENTIAL_DUPLICATE,
        ).exists(), "First ingestion should not have a potential_duplicate flag."

        # Second ingestion of the same row — duplicate flag expected.
        result2 = engine.ingest_utility_file(
            file_content=file_content,
            filename="dup_utility_second.csv",
            tenant_id=str(tenant.id),
        )
        assert result2.records_ingested == 1, (
            f"Second ingestion: expected 1 record; got {result2.records_ingested}. "
            f"Errors: {result2.errors}"
        )

        second_record = EmissionRecord._default_manager.filter(
            tenant=tenant,
            account_number="MSEDCL-ENT-00451",
            meter_id="MTR-PNE-001",
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


@pytest.mark.django_db
class TestMultipleMetersSameAccountCreateSeparateRecords:
    """
    test_multiple_meters_same_account_create_separate_records

    Two rows with the same account_number but different meter_id values
    should each produce a separate EmissionRecord.

    Requirements: 3.6
    """

    def test_multiple_meters_same_account_create_separate_records(self):
        tenant = _make_tenant(name="Multi Meter Corp", code="MULTIMETER")
        engine = IngestionEngine()

        row1 = _make_row(
            account_number="MSEDCL-ENT-00451",
            meter_id="MTR-PNE-001",
            billing_period_start="2024-01-04",
            billing_period_end="2024-02-03",
            consumption_kwh="16270",
        )
        row2 = _make_row(
            account_number="MSEDCL-ENT-00451",
            meter_id="MTR-PNE-002",
            billing_period_start="2024-01-04",
            billing_period_end="2024-02-03",
            consumption_kwh="9240",
        )
        file_content = _csv_file(HEADER, row1, row2)

        result = engine.ingest_utility_file(
            file_content=file_content,
            filename="multi_meter_test.csv",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 2, (
            f"Expected 2 ingested records for 2 meters; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        meter_ids = list(
            EmissionRecord._default_manager.filter(
                tenant=tenant,
                account_number="MSEDCL-ENT-00451",
                source_system="UTILITY",
            ).values_list("meter_id", flat=True)
        )
        assert "MTR-PNE-001" in meter_ids, "Expected EmissionRecord for MTR-PNE-001."
        assert "MTR-PNE-002" in meter_ids, "Expected EmissionRecord for MTR-PNE-002."
