"""
Property tests for the ValidationService.

Property 7: Data quality flag generation

Requirements: 2.5, 3.3, 4.7, 4.8, 6.5
"""

import pytest
from validation.services import (
    ValidationService,
    FLAG_BLANK_QUANTITY, FLAG_ZERO_PRICE, FLAG_UNKNOWN_UNIT,
    FLAG_ESTIMATED_READING, FLAG_MISSING_RECEIPT, FLAG_PENDING_APPROVAL,
    SEVERITY_ERROR, SEVERITY_WARNING,
)

service = ValidationService()


class TestBlankQuantityAlwaysError:
    """Blank MENGE always produces blank_quantity ERROR."""

    @pytest.mark.parametrize("menge", [None, "", "   ", "  \t  "])
    def test_blank_menge_produces_error_flag(self, menge):
        flags = service.validate_emission_record(
            {"menge": menge, "netpr": "50.00", "meins": "L"}, "SAP"
        )
        types = [f.flag_type for f in flags]
        assert FLAG_BLANK_QUANTITY in types
        error_flags = [f for f in flags if f.flag_type == FLAG_BLANK_QUANTITY]
        assert error_flags[0].severity == SEVERITY_ERROR


class TestZeroPriceAlwaysError:
    """Zero NETPR always produces zero_price ERROR."""

    @pytest.mark.parametrize("netpr", ["0.00", "0", "0.0", 0, 0.0])
    def test_zero_netpr_produces_error_flag(self, netpr):
        flags = service.validate_emission_record(
            {"menge": "100", "netpr": netpr, "meins": "L"}, "SAP"
        )
        types = [f.flag_type for f in flags]
        assert FLAG_ZERO_PRICE in types
        error_flags = [f for f in flags if f.flag_type == FLAG_ZERO_PRICE]
        assert error_flags[0].severity == SEVERITY_ERROR


class TestEstimatedReadingAlwaysWarning:
    """ESTIMATED reading_type always produces estimated_reading WARNING."""

    @pytest.mark.parametrize("reading_type", ["ESTIMATED", "estimated", "Estimated"])
    def test_estimated_produces_warning_flag(self, reading_type):
        flags = service.validate_emission_record(
            {"reading_type": reading_type}, "UTILITY"
        )
        types = [f.flag_type for f in flags]
        assert FLAG_ESTIMATED_READING in types
        warn_flags = [f for f in flags if f.flag_type == FLAG_ESTIMATED_READING]
        assert warn_flags[0].severity == SEVERITY_WARNING


class TestMissingReceiptAlwaysWarning:
    """receipt_attached=False always produces missing_receipt WARNING."""

    def test_false_receipt_produces_warning_flag(self):
        flags = service.validate_emission_record(
            {"receipt_attached": False, "approval_status": "APPROVED"}, "CONCUR"
        )
        types = [f.flag_type for f in flags]
        assert FLAG_MISSING_RECEIPT in types
        warn_flags = [f for f in flags if f.flag_type == FLAG_MISSING_RECEIPT]
        assert warn_flags[0].severity == SEVERITY_WARNING


class TestPendingApprovalAlwaysWarning:
    """PENDING_APPROVAL always produces pending_approval WARNING."""

    @pytest.mark.parametrize("status", ["PENDING_APPROVAL", "pending_approval"])
    def test_pending_approval_produces_warning_flag(self, status):
        flags = service.validate_emission_record(
            {"receipt_attached": True, "approval_status": status}, "CONCUR"
        )
        types = [f.flag_type for f in flags]
        assert FLAG_PENDING_APPROVAL in types
        warn_flags = [f for f in flags if f.flag_type == FLAG_PENDING_APPROVAL]
        assert warn_flags[0].severity == SEVERITY_WARNING


class TestUnknownUnitAlwaysWarning:
    """Unrecognized unit codes always produce unknown_unit WARNING."""

    @pytest.mark.parametrize("unit", ["GAL", "BARREL", "TON", "BBL", ""])
    def test_unknown_unit_produces_warning_flag(self, unit):
        flags = service.validate_emission_record(
            {"menge": "100", "netpr": "50.00", "meins": unit}, "SAP"
        )
        types = [f.flag_type for f in flags]
        assert FLAG_UNKNOWN_UNIT in types
        warn_flags = [f for f in flags if f.flag_type == FLAG_UNKNOWN_UNIT]
        assert warn_flags[0].severity == SEVERITY_WARNING
