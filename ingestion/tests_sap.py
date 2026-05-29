"""
Integration tests for the SAP ingestion pipeline.

Tests cover the full path from raw file bytes through to persisted
EmissionRecord and DataQualityFlag model instances.

Requirements: 2.1 – 2.7, 7.1 – 7.4, 14.1, 18.x, 19.1
"""

from __future__ import annotations

import os
import textwrap

import pytest

from emissions.models import DataQualityFlag, EmissionRecord, Tenant
from ingestion.ingestion_engine import IngestionEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tenant(name: str = "Test Corp", code: str = "TESTCORP") -> Tenant:
    """Create and return a Tenant for use in tests."""
    return Tenant.objects.create(name=name, code=code)


def _tab_file(*rows: str) -> bytes:
    """
    Build a tab-separated SAP file from a sequence of row strings.

    The first row must be the header.  Each row string should already
    contain tab-separated values.
    """
    content = "\n".join(rows)
    return content.encode("utf-8")


HEADER = "EBELN\tEBELP\tBEDAT\tWERKS\tMENGE\tMEINS\tNETPR\tTXZ01\tMATNR\tWAERS"

SAMPLE_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sample_data",
    "sap_fuel_procurement.txt",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIngestValidSAPFile:
    """
    test_ingest_valid_sap_file

    Ingest the sample_data/sap_fuel_procurement.txt file and verify that
    at least one EmissionRecord is created.

    Requirements: 2.1, 7.1, 7.2, 7.3, 7.4
    """

    def test_ingest_valid_sap_file(self):
        tenant = _make_tenant()
        engine = IngestionEngine()

        with open(SAMPLE_DATA_PATH, "rb") as fh:
            file_content = fh.read()

        result = engine.ingest_sap_file(
            file_content=file_content,
            filename="sap_fuel_procurement.txt",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested > 0, (
            f"Expected at least one ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )
        # Verify records are actually in the database.
        db_count = EmissionRecord._default_manager.filter(
            tenant=tenant, source_system="SAP"
        ).count()
        assert db_count == result.records_ingested


@pytest.mark.django_db
class TestBlankMengeCreatesErrorFlag:
    """
    test_blank_menge_creates_error_flag

    A row with a blank MENGE field should be ingested (blank MENGE is valid
    at parse time) but must produce a DataQualityFlag of type blank_quantity.

    Requirements: 2.5, 18.4
    """

    def test_blank_menge_creates_error_flag(self):
        tenant = _make_tenant(name="Blank Menge Corp", code="BLANKMENGE")
        engine = IngestionEngine()

        # MENGE is intentionally blank (empty string between tabs).
        row = "4500099001\t00010\t20240101\tWRK1\t\tL\t89.50\tDiesel HSD\tMAT-DIESEL-001\tINR"
        file_content = _tab_file(HEADER, row)

        result = engine.ingest_sap_file(
            file_content=file_content,
            filename="blank_menge_test.txt",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant, ebeln="4500099001"
        ).first()
        assert emission_record is not None

        flags = DataQualityFlag.objects.filter(
            emission_record=emission_record,
            flag_type=DataQualityFlag.FLAG_BLANK_QUANTITY,
        )
        assert flags.exists(), (
            "Expected a blank_quantity DataQualityFlag but none was created."
        )


@pytest.mark.django_db
class TestZeroNetprCreatesErrorFlag:
    """
    test_zero_netpr_creates_error_flag

    A row with NETPR = 0.00 should be ingested but must produce a
    DataQualityFlag of type zero_price.

    Requirements: 18.3
    """

    def test_zero_netpr_creates_error_flag(self):
        tenant = _make_tenant(name="Zero Price Corp", code="ZEROPRICE")
        engine = IngestionEngine()

        row = "4500099002\t00010\t20240101\tWRK1\t1000.000\tL\t0.00\tDiesel HSD\tMAT-DIESEL-001\tINR"
        file_content = _tab_file(HEADER, row)

        result = engine.ingest_sap_file(
            file_content=file_content,
            filename="zero_netpr_test.txt",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant, ebeln="4500099002"
        ).first()
        assert emission_record is not None

        flags = DataQualityFlag.objects.filter(
            emission_record=emission_record,
            flag_type=DataQualityFlag.FLAG_ZERO_PRICE,
        )
        assert flags.exists(), (
            "Expected a zero_price DataQualityFlag but none was created."
        )


@pytest.mark.django_db
class TestUnknownWerksUsesFallbackLocation:
    """
    test_unknown_werks_uses_fallback_location

    When a WERKS code is not in the plant lookup table, the ingestion engine
    should use the WERKS code itself as the location (fallback behaviour).

    Requirements: 2.3
    """

    def test_unknown_werks_uses_fallback_location(self):
        tenant = _make_tenant(name="Unknown Plant Corp", code="UNKNOWNPLANT")
        engine = IngestionEngine()

        unknown_werks = "ZZZUNKNOWN"
        row = f"4500099003\t00010\t20240101\t{unknown_werks}\t500.000\tL\t89.50\tDiesel HSD\tMAT-DIESEL-001\tINR"
        file_content = _tab_file(HEADER, row)

        result = engine.ingest_sap_file(
            file_content=file_content,
            filename="unknown_werks_test.txt",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant, ebeln="4500099003"
        ).first()
        assert emission_record is not None

        # The location should fall back to the WERKS code itself.
        assert emission_record.location == unknown_werks, (
            f"Expected location='{unknown_werks}' but got '{emission_record.location}'."
        )
        assert emission_record.plant_location == unknown_werks


@pytest.mark.django_db
class TestLubricatingOilExcluded:
    """
    test_lubricating_oil_excluded

    A row with a material description containing "lubricating oil" should be
    ingested but classified as excluded (scope=None, is_excluded=True in the
    classifier).  The EmissionRecord's scope field should be None.

    Requirements: 2.7, 14.1
    """

    def test_lubricating_oil_excluded(self):
        tenant = _make_tenant(name="Lube Oil Corp", code="LUBEOIL")
        engine = IngestionEngine()

        row = "4500099004\t00010\t20240101\tWRK1\t200.000\tKG\t310.00\tLubricating Oil SAE 40\tMAT-LUBEOIL-004\tINR"
        file_content = _tab_file(HEADER, row)

        result = engine.ingest_sap_file(
            file_content=file_content,
            filename="lube_oil_test.txt",
            tenant_id=str(tenant.id),
        )

        assert result.records_ingested == 1, (
            f"Expected 1 ingested record; got {result.records_ingested}. "
            f"Errors: {result.errors}"
        )

        emission_record = EmissionRecord._default_manager.filter(
            tenant=tenant, ebeln="4500099004"
        ).first()
        assert emission_record is not None

        # Scope should be None because lubricating oil is excluded.
        assert emission_record.scope is None, (
            f"Expected scope=None for lubricating oil but got scope={emission_record.scope}."
        )


@pytest.mark.django_db
class TestDuplicateEbelnEbelpCreatesPotentialDuplicateFlag:
    """
    test_duplicate_ebeln_ebelp_creates_potential_duplicate_flag

    When the same EBELN+EBELP combination is ingested twice for the same
    tenant, the second ingestion should produce a DataQualityFlag of type
    potential_duplicate.

    Requirements: 19.1
    """

    def test_duplicate_ebeln_ebelp_creates_potential_duplicate_flag(self):
        tenant = _make_tenant(name="Duplicate Test Corp", code="DUPTEST")
        engine = IngestionEngine()

        row = "4500099005\t00010\t20240101\tWRK1\t1000.000\tL\t89.50\tDiesel HSD\tMAT-DIESEL-001\tINR"
        file_content = _tab_file(HEADER, row)

        # First ingestion — no duplicate flag expected.
        result1 = engine.ingest_sap_file(
            file_content=file_content,
            filename="dup_test_first.txt",
            tenant_id=str(tenant.id),
        )
        assert result1.records_ingested == 1, (
            f"First ingestion: expected 1 record; got {result1.records_ingested}. "
            f"Errors: {result1.errors}"
        )

        first_record = EmissionRecord._default_manager.filter(
            tenant=tenant, ebeln="4500099005"
        ).first()
        assert first_record is not None
        assert not DataQualityFlag.objects.filter(
            emission_record=first_record,
            flag_type=DataQualityFlag.FLAG_POTENTIAL_DUPLICATE,
        ).exists(), "First ingestion should not have a potential_duplicate flag."

        # Second ingestion of the same row — duplicate flag expected.
        result2 = engine.ingest_sap_file(
            file_content=file_content,
            filename="dup_test_second.txt",
            tenant_id=str(tenant.id),
        )
        assert result2.records_ingested == 1, (
            f"Second ingestion: expected 1 record; got {result2.records_ingested}. "
            f"Errors: {result2.errors}"
        )

        # The second EmissionRecord should carry a potential_duplicate flag.
        second_record = EmissionRecord._default_manager.filter(
            tenant=tenant, ebeln="4500099005"
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
