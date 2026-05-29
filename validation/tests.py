"""
Tests for the ValidationService in the validation app.

Covers all flag types and severity levels:
- blank_quantity  (SAP MENGE empty)          → ERROR
- zero_price      (SAP NETPR = 0.00)         → ERROR
- unknown_unit    (SAP MEINS unrecognised)   → WARNING
- estimated_reading (Utility ESTIMATED)      → WARNING
- missing_receipt   (Travel receipt=False)   → WARNING
- pending_approval  (Travel PENDING_APPROVAL)→ WARNING

Requirements: 2.5, 3.3, 4.7, 4.8, 6.5, 18.1, 18.2, 18.3, 18.4, 18.5, 18.7
"""

import pytest

from validation.services import (
    DataQualityFlagData,
    ValidationService,
    FLAG_BLANK_QUANTITY,
    FLAG_ZERO_PRICE,
    FLAG_UNKNOWN_UNIT,
    FLAG_ESTIMATED_READING,
    FLAG_MISSING_RECEIPT,
    FLAG_PENDING_APPROVAL,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service():
    return ValidationService()


# ---------------------------------------------------------------------------
# Helper builders for minimal valid records
# ---------------------------------------------------------------------------


def sap_record(menge=100.0, netpr=50.0, meins="L"):
    """Return a minimal SAP record dict with sensible defaults."""
    return {"menge": menge, "netpr": netpr, "meins": meins}


def utility_record(reading_type="ACTUAL"):
    """Return a minimal UTILITY record dict."""
    return {"reading_type": reading_type}


def concur_record(receipt_attached=True, approval_status="APPROVED"):
    """Return a minimal CONCUR record dict."""
    return {"receipt_attached": receipt_attached, "approval_status": approval_status}


# ===========================================================================
# Return type
# ===========================================================================


class TestValidateEmissionRecordReturnType:
    """validate_emission_record() always returns a list."""

    def test_returns_list_for_sap(self, service):
        result = service.validate_emission_record(sap_record(), "SAP")
        assert isinstance(result, list)

    def test_returns_list_for_utility(self, service):
        result = service.validate_emission_record(utility_record(), "UTILITY")
        assert isinstance(result, list)

    def test_returns_list_for_concur(self, service):
        result = service.validate_emission_record(concur_record(), "CONCUR")
        assert isinstance(result, list)

    def test_elements_are_data_quality_flag_data(self, service):
        record = sap_record(menge=None)
        result = service.validate_emission_record(record, "SAP")
        for item in result:
            assert isinstance(item, DataQualityFlagData)


# ===========================================================================
# Clean records produce no flags
# ===========================================================================


class TestCleanRecordsProduceNoFlags:
    """Valid records with no issues return an empty list."""

    def test_clean_sap_record(self, service):
        result = service.validate_emission_record(sap_record(), "SAP")
        assert result == []

    def test_clean_utility_record(self, service):
        result = service.validate_emission_record(utility_record("ACTUAL"), "UTILITY")
        assert result == []

    def test_clean_concur_record(self, service):
        result = service.validate_emission_record(concur_record(), "CONCUR")
        assert result == []

    def test_unknown_source_system_returns_empty(self, service):
        """Unrecognised source systems are silently ignored (no flags)."""
        result = service.validate_emission_record({}, "UNKNOWN_SOURCE")
        assert result == []


# ===========================================================================
# SAP — blank_quantity (ERROR)
# ===========================================================================


class TestSAPBlankQuantity:
    """Blank MENGE produces a blank_quantity ERROR flag. (Req 2.5, 18.4)"""

    def test_none_menge_creates_flag(self, service):
        record = sap_record(menge=None)
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY in flag_types

    def test_empty_string_menge_creates_flag(self, service):
        record = sap_record(menge="")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY in flag_types

    def test_whitespace_only_menge_creates_flag(self, service):
        record = sap_record(menge="   ")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY in flag_types

    def test_blank_quantity_severity_is_error(self, service):
        record = sap_record(menge=None)
        flags = service.validate_emission_record(record, "SAP")
        blank_flags = [f for f in flags if f.flag_type == FLAG_BLANK_QUANTITY]
        assert len(blank_flags) == 1
        assert blank_flags[0].severity == SEVERITY_ERROR

    def test_blank_quantity_field_name_is_menge(self, service):
        record = sap_record(menge=None)
        flags = service.validate_emission_record(record, "SAP")
        blank_flags = [f for f in flags if f.flag_type == FLAG_BLANK_QUANTITY]
        assert blank_flags[0].field_name == "menge"

    def test_nonzero_menge_does_not_create_flag(self, service):
        record = sap_record(menge=100.0)
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY not in flag_types

    def test_zero_menge_does_not_create_blank_quantity_flag(self, service):
        """Zero is a valid (non-blank) quantity; only None/empty triggers the flag."""
        record = sap_record(menge=0.0)
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY not in flag_types


# ===========================================================================
# SAP — zero_price (ERROR)
# ===========================================================================


class TestSAPZeroPrice:
    """NETPR == 0.0 produces a zero_price ERROR flag. (Req 18.3)"""

    def test_zero_netpr_creates_flag(self, service):
        record = sap_record(netpr=0.0)
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ZERO_PRICE in flag_types

    def test_zero_netpr_as_string_zero_creates_flag(self, service):
        record = sap_record(netpr="0.00")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ZERO_PRICE in flag_types

    def test_zero_price_severity_is_error(self, service):
        record = sap_record(netpr=0.0)
        flags = service.validate_emission_record(record, "SAP")
        zero_flags = [f for f in flags if f.flag_type == FLAG_ZERO_PRICE]
        assert len(zero_flags) == 1
        assert zero_flags[0].severity == SEVERITY_ERROR

    def test_zero_price_field_name_is_netpr(self, service):
        record = sap_record(netpr=0.0)
        flags = service.validate_emission_record(record, "SAP")
        zero_flags = [f for f in flags if f.flag_type == FLAG_ZERO_PRICE]
        assert zero_flags[0].field_name == "netpr"

    def test_positive_netpr_does_not_create_flag(self, service):
        record = sap_record(netpr=50.0)
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ZERO_PRICE not in flag_types

    def test_none_netpr_does_not_create_zero_price_flag(self, service):
        """Missing NETPR is not the same as zero price."""
        record = {"menge": 100.0, "meins": "L"}  # no netpr key
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ZERO_PRICE not in flag_types


# ===========================================================================
# SAP — unknown_unit (WARNING)
# ===========================================================================


class TestSAPUnknownUnit:
    """Unrecognised MEINS produces an unknown_unit WARNING flag. (Req 6.5, 18.7)"""

    def test_unknown_unit_creates_flag(self, service):
        record = sap_record(meins="GAL")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_UNKNOWN_UNIT in flag_types

    def test_unknown_unit_severity_is_warning(self, service):
        record = sap_record(meins="BARREL")
        flags = service.validate_emission_record(record, "SAP")
        unit_flags = [f for f in flags if f.flag_type == FLAG_UNKNOWN_UNIT]
        assert len(unit_flags) == 1
        assert unit_flags[0].severity == SEVERITY_WARNING

    def test_unknown_unit_field_name_is_meins(self, service):
        record = sap_record(meins="TON")
        flags = service.validate_emission_record(record, "SAP")
        unit_flags = [f for f in flags if f.flag_type == FLAG_UNKNOWN_UNIT]
        assert unit_flags[0].field_name == "meins"

    def test_known_unit_l_does_not_create_flag(self, service):
        record = sap_record(meins="L")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_UNKNOWN_UNIT not in flag_types

    def test_known_unit_ltr_does_not_create_flag(self, service):
        record = sap_record(meins="LTR")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_UNKNOWN_UNIT not in flag_types

    def test_known_unit_m3_does_not_create_flag(self, service):
        record = sap_record(meins="M3")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_UNKNOWN_UNIT not in flag_types

    def test_known_unit_kg_does_not_create_flag(self, service):
        record = sap_record(meins="KG")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_UNKNOWN_UNIT not in flag_types

    def test_lowercase_known_unit_does_not_create_flag(self, service):
        """Unit codes are normalised to uppercase before lookup."""
        record = sap_record(meins="kg")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_UNKNOWN_UNIT not in flag_types

    def test_empty_meins_creates_unknown_unit_flag(self, service):
        record = sap_record(meins="")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_UNKNOWN_UNIT in flag_types


# ===========================================================================
# UTILITY — estimated_reading (WARNING)
# ===========================================================================


class TestUtilityEstimatedReading:
    """reading_type == ESTIMATED produces an estimated_reading WARNING. (Req 3.3, 18.1)"""

    def test_estimated_reading_type_creates_flag(self, service):
        record = utility_record(reading_type="ESTIMATED")
        flags = service.validate_emission_record(record, "UTILITY")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ESTIMATED_READING in flag_types

    def test_estimated_reading_severity_is_warning(self, service):
        record = utility_record(reading_type="ESTIMATED")
        flags = service.validate_emission_record(record, "UTILITY")
        est_flags = [f for f in flags if f.flag_type == FLAG_ESTIMATED_READING]
        assert len(est_flags) == 1
        assert est_flags[0].severity == SEVERITY_WARNING

    def test_estimated_reading_field_name_is_reading_type(self, service):
        record = utility_record(reading_type="ESTIMATED")
        flags = service.validate_emission_record(record, "UTILITY")
        est_flags = [f for f in flags if f.flag_type == FLAG_ESTIMATED_READING]
        assert est_flags[0].field_name == "reading_type"

    def test_actual_reading_type_does_not_create_flag(self, service):
        record = utility_record(reading_type="ACTUAL")
        flags = service.validate_emission_record(record, "UTILITY")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ESTIMATED_READING not in flag_types

    def test_lowercase_estimated_creates_flag(self, service):
        """reading_type comparison is case-insensitive."""
        record = utility_record(reading_type="estimated")
        flags = service.validate_emission_record(record, "UTILITY")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ESTIMATED_READING in flag_types

    def test_missing_reading_type_does_not_create_flag(self, service):
        """A record without reading_type should not raise or create a flag."""
        record = {}
        flags = service.validate_emission_record(record, "UTILITY")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ESTIMATED_READING not in flag_types


# ===========================================================================
# CONCUR — missing_receipt (WARNING)
# ===========================================================================


class TestConcurMissingReceipt:
    """receipt_attached == False produces a missing_receipt WARNING. (Req 4.8, 18.2)"""

    def test_false_receipt_attached_creates_flag(self, service):
        record = concur_record(receipt_attached=False)
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_MISSING_RECEIPT in flag_types

    def test_missing_receipt_severity_is_warning(self, service):
        record = concur_record(receipt_attached=False)
        flags = service.validate_emission_record(record, "CONCUR")
        receipt_flags = [f for f in flags if f.flag_type == FLAG_MISSING_RECEIPT]
        assert len(receipt_flags) == 1
        assert receipt_flags[0].severity == SEVERITY_WARNING

    def test_missing_receipt_field_name_is_receipt_attached(self, service):
        record = concur_record(receipt_attached=False)
        flags = service.validate_emission_record(record, "CONCUR")
        receipt_flags = [f for f in flags if f.flag_type == FLAG_MISSING_RECEIPT]
        assert receipt_flags[0].field_name == "receipt_attached"

    def test_true_receipt_attached_does_not_create_flag(self, service):
        record = concur_record(receipt_attached=True)
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_MISSING_RECEIPT not in flag_types

    def test_none_receipt_attached_does_not_create_flag(self, service):
        """None means the field is absent/unknown — not the same as False."""
        record = concur_record(receipt_attached=None)
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_MISSING_RECEIPT not in flag_types

    def test_missing_key_does_not_create_flag(self, service):
        """A record without receipt_attached key should not raise or create a flag."""
        record = {"approval_status": "APPROVED"}
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_MISSING_RECEIPT not in flag_types


# ===========================================================================
# CONCUR — pending_approval (WARNING)
# ===========================================================================


class TestConcurPendingApproval:
    """approval_status == PENDING_APPROVAL produces a pending_approval WARNING. (Req 4.7, 18.5)"""

    def test_pending_approval_status_creates_flag(self, service):
        record = concur_record(approval_status="PENDING_APPROVAL")
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_PENDING_APPROVAL in flag_types

    def test_pending_approval_severity_is_warning(self, service):
        record = concur_record(approval_status="PENDING_APPROVAL")
        flags = service.validate_emission_record(record, "CONCUR")
        pending_flags = [f for f in flags if f.flag_type == FLAG_PENDING_APPROVAL]
        assert len(pending_flags) == 1
        assert pending_flags[0].severity == SEVERITY_WARNING

    def test_pending_approval_field_name_is_approval_status(self, service):
        record = concur_record(approval_status="PENDING_APPROVAL")
        flags = service.validate_emission_record(record, "CONCUR")
        pending_flags = [f for f in flags if f.flag_type == FLAG_PENDING_APPROVAL]
        assert pending_flags[0].field_name == "approval_status"

    def test_approved_status_does_not_create_flag(self, service):
        record = concur_record(approval_status="APPROVED")
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_PENDING_APPROVAL not in flag_types

    def test_lowercase_pending_approval_creates_flag(self, service):
        """approval_status comparison is case-insensitive."""
        record = concur_record(approval_status="pending_approval")
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_PENDING_APPROVAL in flag_types

    def test_missing_approval_status_does_not_create_flag(self, service):
        """A record without approval_status key should not raise or create a flag."""
        record = {"receipt_attached": True}
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_PENDING_APPROVAL not in flag_types


# ===========================================================================
# Multiple flags on a single record
# ===========================================================================


class TestMultipleFlagsOnSingleRecord:
    """A single record can produce multiple flags simultaneously."""

    def test_sap_blank_menge_and_zero_price_both_flagged(self, service):
        record = sap_record(menge=None, netpr=0.0)
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY in flag_types
        assert FLAG_ZERO_PRICE in flag_types

    def test_sap_all_three_issues_flagged(self, service):
        record = sap_record(menge=None, netpr=0.0, meins="BARREL")
        flags = service.validate_emission_record(record, "SAP")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY in flag_types
        assert FLAG_ZERO_PRICE in flag_types
        assert FLAG_UNKNOWN_UNIT in flag_types
        assert len(flags) == 3

    def test_concur_both_issues_flagged(self, service):
        record = concur_record(receipt_attached=False, approval_status="PENDING_APPROVAL")
        flags = service.validate_emission_record(record, "CONCUR")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_MISSING_RECEIPT in flag_types
        assert FLAG_PENDING_APPROVAL in flag_types
        assert len(flags) == 2


# ===========================================================================
# Severity levels
# ===========================================================================


class TestSeverityLevels:
    """ERROR flags block approval; WARNING flags allow approval."""

    def test_blank_quantity_is_error(self, service):
        record = sap_record(menge=None)
        flags = service.validate_emission_record(record, "SAP")
        blank_flags = [f for f in flags if f.flag_type == FLAG_BLANK_QUANTITY]
        assert blank_flags[0].severity == SEVERITY_ERROR

    def test_zero_price_is_error(self, service):
        record = sap_record(netpr=0.0)
        flags = service.validate_emission_record(record, "SAP")
        zero_flags = [f for f in flags if f.flag_type == FLAG_ZERO_PRICE]
        assert zero_flags[0].severity == SEVERITY_ERROR

    def test_estimated_reading_is_warning(self, service):
        record = utility_record(reading_type="ESTIMATED")
        flags = service.validate_emission_record(record, "UTILITY")
        est_flags = [f for f in flags if f.flag_type == FLAG_ESTIMATED_READING]
        assert est_flags[0].severity == SEVERITY_WARNING

    def test_missing_receipt_is_warning(self, service):
        record = concur_record(receipt_attached=False)
        flags = service.validate_emission_record(record, "CONCUR")
        receipt_flags = [f for f in flags if f.flag_type == FLAG_MISSING_RECEIPT]
        assert receipt_flags[0].severity == SEVERITY_WARNING

    def test_pending_approval_is_warning(self, service):
        record = concur_record(approval_status="PENDING_APPROVAL")
        flags = service.validate_emission_record(record, "CONCUR")
        pending_flags = [f for f in flags if f.flag_type == FLAG_PENDING_APPROVAL]
        assert pending_flags[0].severity == SEVERITY_WARNING

    def test_unknown_unit_is_warning(self, service):
        record = sap_record(meins="GAL")
        flags = service.validate_emission_record(record, "SAP")
        unit_flags = [f for f in flags if f.flag_type == FLAG_UNKNOWN_UNIT]
        assert unit_flags[0].severity == SEVERITY_WARNING


# ===========================================================================
# Source system case-insensitivity
# ===========================================================================


class TestSourceSystemCaseInsensitivity:
    """source_system argument is normalised to uppercase before dispatch."""

    def test_lowercase_sap_dispatches_correctly(self, service):
        record = sap_record(menge=None)
        flags = service.validate_emission_record(record, "sap")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY in flag_types

    def test_lowercase_utility_dispatches_correctly(self, service):
        record = utility_record(reading_type="ESTIMATED")
        flags = service.validate_emission_record(record, "utility")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_ESTIMATED_READING in flag_types

    def test_lowercase_concur_dispatches_correctly(self, service):
        record = concur_record(receipt_attached=False)
        flags = service.validate_emission_record(record, "concur")
        flag_types = [f.flag_type for f in flags]
        assert FLAG_MISSING_RECEIPT in flag_types


# ===========================================================================
# DataQualityFlagData dataclass
# ===========================================================================


class TestDataQualityFlagDataClass:
    """DataQualityFlagData is a plain dataclass with the expected fields."""

    def test_has_flag_type(self):
        flag = DataQualityFlagData(
            flag_type=FLAG_BLANK_QUANTITY,
            severity=SEVERITY_ERROR,
            message="test",
        )
        assert flag.flag_type == FLAG_BLANK_QUANTITY

    def test_has_severity(self):
        flag = DataQualityFlagData(
            flag_type=FLAG_ZERO_PRICE,
            severity=SEVERITY_ERROR,
            message="test",
        )
        assert flag.severity == SEVERITY_ERROR

    def test_has_message(self):
        flag = DataQualityFlagData(
            flag_type=FLAG_ESTIMATED_READING,
            severity=SEVERITY_WARNING,
            message="some message",
        )
        assert flag.message == "some message"

    def test_field_name_defaults_to_none(self):
        flag = DataQualityFlagData(
            flag_type=FLAG_MISSING_RECEIPT,
            severity=SEVERITY_WARNING,
            message="test",
        )
        assert flag.field_name is None

    def test_field_name_can_be_set(self):
        flag = DataQualityFlagData(
            flag_type=FLAG_PENDING_APPROVAL,
            severity=SEVERITY_WARNING,
            message="test",
            field_name="approval_status",
        )
        assert flag.field_name == "approval_status"
