"""
Tests for the normalization app.

Covers:
- NormalizationService.normalize_date() — unit tests for all supported formats,
  edge cases, and error conditions.
"""

from datetime import date

import pytest

from normalization.exceptions import DateParseError
from normalization.services import NormalizationService


@pytest.fixture
def service():
    return NormalizationService()


# ---------------------------------------------------------------------------
# Happy-path: each supported format
# ---------------------------------------------------------------------------


class TestNormalizeDateFormats:
    """normalize_date() correctly parses each of the four supported formats."""

    def test_yyyymmdd_format(self, service):
        assert service.normalize_date("20231231") == date(2023, 12, 31)

    def test_yyyymmdd_format_start_of_year(self, service):
        assert service.normalize_date("20230101") == date(2023, 1, 1)

    def test_iso_8601_format(self, service):
        assert service.normalize_date("2023-12-31") == date(2023, 12, 31)

    def test_iso_8601_format_start_of_year(self, service):
        assert service.normalize_date("2023-01-01") == date(2023, 1, 1)

    def test_dd_dot_mm_dot_yyyy_format(self, service):
        assert service.normalize_date("31.12.2023") == date(2023, 12, 31)

    def test_dd_dot_mm_dot_yyyy_format_single_digit_day_month(self, service):
        assert service.normalize_date("01.01.2023") == date(2023, 1, 1)

    def test_dd_slash_mm_slash_yyyy_format(self, service):
        assert service.normalize_date("31/12/2023") == date(2023, 12, 31)

    def test_dd_slash_mm_slash_yyyy_format_single_digit_day_month(self, service):
        assert service.normalize_date("01/01/2023") == date(2023, 1, 1)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


class TestNormalizeDateReturnType:
    """normalize_date() always returns a datetime.date object."""

    def test_returns_date_object_for_yyyymmdd(self, service):
        result = service.normalize_date("20230615")
        assert isinstance(result, date)

    def test_returns_date_object_for_iso(self, service):
        result = service.normalize_date("2023-06-15")
        assert isinstance(result, date)

    def test_returns_date_object_for_dot_format(self, service):
        result = service.normalize_date("15.06.2023")
        assert isinstance(result, date)

    def test_returns_date_object_for_slash_format(self, service):
        result = service.normalize_date("15/06/2023")
        assert isinstance(result, date)


# ---------------------------------------------------------------------------
# Same calendar date across all formats
# ---------------------------------------------------------------------------


class TestNormalizeDateConsistency:
    """All four formats for the same calendar date produce the same date object."""

    def test_all_formats_produce_same_date(self, service):
        expected = date(2023, 6, 15)
        assert service.normalize_date("20230615") == expected
        assert service.normalize_date("2023-06-15") == expected
        assert service.normalize_date("15.06.2023") == expected
        assert service.normalize_date("15/06/2023") == expected


# ---------------------------------------------------------------------------
# Whitespace tolerance
# ---------------------------------------------------------------------------


class TestNormalizeDateWhitespace:
    """Leading/trailing whitespace is stripped before parsing."""

    def test_leading_whitespace(self, service):
        assert service.normalize_date("  20230615") == date(2023, 6, 15)

    def test_trailing_whitespace(self, service):
        assert service.normalize_date("20230615  ") == date(2023, 6, 15)

    def test_surrounding_whitespace(self, service):
        assert service.normalize_date("  2023-06-15  ") == date(2023, 6, 15)


# ---------------------------------------------------------------------------
# Error cases: unrecognized formats
# ---------------------------------------------------------------------------


class TestNormalizeDateErrors:
    """normalize_date() raises DateParseError for unrecognized or invalid input."""

    def test_raises_for_mm_dd_yyyy_slash(self, service):
        """American MM/DD/YYYY format is NOT supported."""
        with pytest.raises(DateParseError):
            service.normalize_date("12/31/2023")

    def test_raises_for_empty_string(self, service):
        with pytest.raises(DateParseError):
            service.normalize_date("")

    def test_raises_for_whitespace_only(self, service):
        with pytest.raises(DateParseError):
            service.normalize_date("   ")

    def test_raises_for_plain_text(self, service):
        with pytest.raises(DateParseError):
            service.normalize_date("not-a-date")

    def test_raises_for_partial_date(self, service):
        with pytest.raises(DateParseError):
            service.normalize_date("2023-12")

    def test_raises_for_invalid_calendar_date_dot_format(self, service):
        """Day 32 does not exist."""
        with pytest.raises(DateParseError):
            service.normalize_date("32.01.2023")

    def test_raises_for_invalid_month_dot_format(self, service):
        """Month 13 does not exist."""
        with pytest.raises(DateParseError):
            service.normalize_date("01.13.2023")

    def test_raises_for_invalid_calendar_date_yyyymmdd(self, service):
        """February 30 does not exist."""
        with pytest.raises(DateParseError):
            service.normalize_date("20230230")

    def test_raises_for_invalid_calendar_date_iso(self, service):
        with pytest.raises(DateParseError):
            service.normalize_date("2023-13-01")

    def test_raises_for_yyyy_mm_dd_with_slashes(self, service):
        """YYYY/MM/DD is not a supported format."""
        with pytest.raises(DateParseError):
            service.normalize_date("2023/12/31")

    def test_error_message_contains_original_string(self, service):
        bad_input = "99-99-9999"
        with pytest.raises(DateParseError) as exc_info:
            service.normalize_date(bad_input)
        assert bad_input in str(exc_info.value)

    def test_raises_for_non_string_input(self, service):
        with pytest.raises(DateParseError):
            service.normalize_date(20231231)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DateParseError exception class
# ---------------------------------------------------------------------------


class TestDateParseError:
    """DateParseError is a subclass of ValueError and carries the bad input."""

    def test_is_value_error(self):
        err = DateParseError("bad")
        assert isinstance(err, ValueError)

    def test_stores_date_string(self):
        err = DateParseError("bad-date")
        assert err.date_string == "bad-date"

    def test_message_contains_date_string(self):
        err = DateParseError("bad-date")
        assert "bad-date" in str(err)


# ===========================================================================
# Unit tests for NormalizationService.normalize_unit()
# ===========================================================================

from decimal import Decimal

from normalization.exceptions import UnknownUnitError
from normalization.services import NormalizedQuantity


class TestNormalizeUnitReturnType:
    """normalize_unit() always returns a NormalizedQuantity dataclass."""

    def test_returns_normalized_quantity_instance(self, service):
        result = service.normalize_unit(Decimal("10"), "L")
        assert isinstance(result, NormalizedQuantity)


class TestNormalizeUnitLToLitres:
    """Unit code 'L' is normalized to 'litres'."""

    def test_l_normalized_unit(self, service):
        result = service.normalize_unit(Decimal("100"), "L")
        assert result.normalized_unit == "litres"

    def test_l_original_unit_preserved(self, service):
        result = service.normalize_unit(Decimal("100"), "L")
        assert result.original_unit == "L"

    def test_l_quantity_preserved(self, service):
        qty = Decimal("123.456")
        result = service.normalize_unit(qty, "L")
        assert result.original_quantity == qty
        assert result.normalized_quantity == qty


class TestNormalizeUnitLTRToLitres:
    """Unit code 'LTR' is normalized to 'litres'."""

    def test_ltr_normalized_unit(self, service):
        result = service.normalize_unit(Decimal("50"), "LTR")
        assert result.normalized_unit == "litres"

    def test_ltr_original_unit_preserved(self, service):
        result = service.normalize_unit(Decimal("50"), "LTR")
        assert result.original_unit == "LTR"

    def test_ltr_quantity_preserved(self, service):
        qty = Decimal("999.99")
        result = service.normalize_unit(qty, "LTR")
        assert result.original_quantity == qty
        assert result.normalized_quantity == qty


class TestNormalizeUnitM3ToCubicMetres:
    """Unit code 'M3' is normalized to 'cubic_metres'."""

    def test_m3_normalized_unit(self, service):
        result = service.normalize_unit(Decimal("5"), "M3")
        assert result.normalized_unit == "cubic_metres"

    def test_m3_original_unit_preserved(self, service):
        result = service.normalize_unit(Decimal("5"), "M3")
        assert result.original_unit == "M3"

    def test_m3_quantity_preserved(self, service):
        qty = Decimal("0.001")
        result = service.normalize_unit(qty, "M3")
        assert result.original_quantity == qty
        assert result.normalized_quantity == qty


class TestNormalizeUnitKGToKilograms:
    """Unit code 'KG' is preserved as 'kilograms'."""

    def test_kg_normalized_unit(self, service):
        result = service.normalize_unit(Decimal("200"), "KG")
        assert result.normalized_unit == "kilograms"

    def test_kg_original_unit_preserved(self, service):
        result = service.normalize_unit(Decimal("200"), "KG")
        assert result.original_unit == "KG"

    def test_kg_quantity_preserved(self, service):
        qty = Decimal("1500")
        result = service.normalize_unit(qty, "KG")
        assert result.original_quantity == qty
        assert result.normalized_quantity == qty


class TestNormalizeUnitOriginalValuesPreserved:
    """Both original quantity and original unit are always stored on the result."""

    def test_original_quantity_stored_for_l(self, service):
        qty = Decimal("42")
        result = service.normalize_unit(qty, "L")
        assert result.original_quantity == qty

    def test_original_unit_stored_for_ltr(self, service):
        result = service.normalize_unit(Decimal("1"), "LTR")
        assert result.original_unit == "LTR"

    def test_original_unit_stored_for_m3(self, service):
        result = service.normalize_unit(Decimal("1"), "M3")
        assert result.original_unit == "M3"

    def test_original_unit_stored_for_kg(self, service):
        result = service.normalize_unit(Decimal("1"), "KG")
        assert result.original_unit == "KG"


class TestNormalizeUnitNormalizedUnitValues:
    """Normalized unit is always one of {litres, cubic_metres, kilograms}."""

    VALID_NORMALIZED_UNITS = {"litres", "cubic_metres", "kilograms"}

    def test_l_in_valid_set(self, service):
        result = service.normalize_unit(Decimal("1"), "L")
        assert result.normalized_unit in self.VALID_NORMALIZED_UNITS

    def test_ltr_in_valid_set(self, service):
        result = service.normalize_unit(Decimal("1"), "LTR")
        assert result.normalized_unit in self.VALID_NORMALIZED_UNITS

    def test_m3_in_valid_set(self, service):
        result = service.normalize_unit(Decimal("1"), "M3")
        assert result.normalized_unit in self.VALID_NORMALIZED_UNITS

    def test_kg_in_valid_set(self, service):
        result = service.normalize_unit(Decimal("1"), "KG")
        assert result.normalized_unit in self.VALID_NORMALIZED_UNITS


class TestNormalizeUnitUnknownUnitError:
    """normalize_unit() raises UnknownUnitError for unrecognized unit codes."""

    def test_raises_for_unknown_code(self, service):
        with pytest.raises(UnknownUnitError):
            service.normalize_unit(Decimal("1"), "GAL")

    def test_raises_for_empty_string(self, service):
        with pytest.raises(UnknownUnitError):
            service.normalize_unit(Decimal("1"), "")

    def test_raises_for_lowercase_l(self, service):
        """Lowercase 'l' is accepted — the service normalizes unit codes to uppercase."""
        result = service.normalize_unit(Decimal("1"), "l")
        assert result.normalized_unit == "litres"

    def test_raises_for_lowercase_kg(self, service):
        """Lowercase 'kg' is accepted — the service normalizes unit codes to uppercase."""
        result = service.normalize_unit(Decimal("1"), "kg")
        assert result.normalized_unit == "kilograms"

    def test_raises_for_whitespace_only(self, service):
        with pytest.raises(UnknownUnitError):
            service.normalize_unit(Decimal("1"), "   ")

    def test_error_stores_unit_code(self, service):
        bad_code = "BARREL"
        with pytest.raises(UnknownUnitError) as exc_info:
            service.normalize_unit(Decimal("1"), bad_code)
        assert exc_info.value.unit_code == bad_code

    def test_error_message_contains_unit_code(self, service):
        bad_code = "TON"
        with pytest.raises(UnknownUnitError) as exc_info:
            service.normalize_unit(Decimal("1"), bad_code)
        assert bad_code in str(exc_info.value)

    def test_is_value_error(self, service):
        with pytest.raises(ValueError):
            service.normalize_unit(Decimal("1"), "UNKNOWN")


class TestUnknownUnitErrorClass:
    """UnknownUnitError is a subclass of ValueError and carries the bad unit code."""

    def test_is_value_error(self):
        err = UnknownUnitError("GAL")
        assert isinstance(err, ValueError)

    def test_stores_unit_code(self):
        err = UnknownUnitError("BARREL")
        assert err.unit_code == "BARREL"

    def test_message_contains_unit_code(self):
        err = UnknownUnitError("TON")
        assert "TON" in str(err)


# ===========================================================================
# Unit tests for NormalizationService.allocate_billing_period()
# ===========================================================================

from normalization.services import MonthlyAllocation


class TestAllocateBillingPeriodSingleMonth:
    """A billing period entirely within one month allocates 100% to that month."""

    def test_single_month_returns_one_allocation(self, service):
        result = service.allocate_billing_period(
            Decimal("300"),
            date(2023, 1, 1),
            date(2023, 1, 31),
        )
        assert len(result) == 1

    def test_single_month_full_allocation(self, service):
        result = service.allocate_billing_period(
            Decimal("300"),
            date(2023, 1, 1),
            date(2023, 1, 31),
        )
        assert result[0].allocated_quantity == Decimal("300")

    def test_single_month_correct_year_and_month(self, service):
        result = service.allocate_billing_period(
            Decimal("300"),
            date(2023, 6, 1),
            date(2023, 6, 30),
        )
        assert result[0].year == 2023
        assert result[0].month == 6

    def test_single_month_default_unit_is_kwh(self, service):
        result = service.allocate_billing_period(
            Decimal("100"),
            date(2023, 3, 1),
            date(2023, 3, 31),
        )
        assert result[0].unit == "kwh"

    def test_single_month_partial_period(self, service):
        """A period within a single month (not full month) still allocates 100%."""
        result = service.allocate_billing_period(
            Decimal("150"),
            date(2023, 5, 10),
            date(2023, 5, 20),
        )
        assert len(result) == 1
        assert result[0].allocated_quantity == Decimal("150")
        assert result[0].month == 5


class TestAllocateBillingPeriodTwoMonths:
    """A billing period spanning two months splits proportionally."""

    def test_two_month_returns_two_allocations(self, service):
        result = service.allocate_billing_period(
            Decimal("310"),
            date(2023, 1, 1),
            date(2023, 2, 28),
        )
        assert len(result) == 2

    def test_two_month_chronological_order(self, service):
        result = service.allocate_billing_period(
            Decimal("310"),
            date(2023, 1, 1),
            date(2023, 2, 28),
        )
        assert result[0].month == 1
        assert result[1].month == 2

    def test_two_month_proportional_split(self, service):
        """Jan has 31 days, Feb 2023 has 28 days → total 59 days.
        Jan share = 31/59, Feb share = 28/59."""
        consumption = Decimal("590")
        result = service.allocate_billing_period(
            consumption,
            date(2023, 1, 1),
            date(2023, 2, 28),
        )
        total_days = 59
        expected_jan = (consumption * Decimal(31) / Decimal(total_days)).quantize(
            Decimal("0.000001")
        )
        # Jan allocation should be close to expected (last month gets remainder)
        assert result[0].allocated_quantity == expected_jan
        # Feb gets the remainder
        assert result[0].allocated_quantity + result[1].allocated_quantity == consumption

    def test_two_month_sum_equals_original(self, service):
        consumption = Decimal("123.456789")
        result = service.allocate_billing_period(
            consumption,
            date(2023, 3, 15),
            date(2023, 4, 14),
        )
        total = sum(a.allocated_quantity for a in result)
        assert total == consumption


class TestAllocateBillingPeriodThreeMonths:
    """A billing period spanning three months splits proportionally across all three."""

    def test_three_month_returns_three_allocations(self, service):
        result = service.allocate_billing_period(
            Decimal("900"),
            date(2023, 1, 1),
            date(2023, 3, 31),
        )
        assert len(result) == 3

    def test_three_month_correct_months(self, service):
        result = service.allocate_billing_period(
            Decimal("900"),
            date(2023, 1, 1),
            date(2023, 3, 31),
        )
        assert result[0].month == 1
        assert result[1].month == 2
        assert result[2].month == 3

    def test_three_month_sum_equals_original(self, service):
        consumption = Decimal("999.999999")
        result = service.allocate_billing_period(
            consumption,
            date(2023, 4, 1),
            date(2023, 6, 30),
        )
        total = sum(a.allocated_quantity for a in result)
        assert total == consumption

    def test_three_month_year_boundary(self, service):
        """Billing period spanning Nov–Jan crosses a year boundary."""
        result = service.allocate_billing_period(
            Decimal("300"),
            date(2022, 11, 1),
            date(2023, 1, 31),
        )
        assert len(result) == 3
        assert result[0].year == 2022
        assert result[0].month == 11
        assert result[1].year == 2022
        assert result[1].month == 12
        assert result[2].year == 2023
        assert result[2].month == 1


class TestAllocateBillingPeriodSumInvariant:
    """Sum of all allocated quantities always equals the original consumption."""

    def test_sum_invariant_single_month(self, service):
        consumption = Decimal("500")
        result = service.allocate_billing_period(
            consumption, date(2023, 7, 1), date(2023, 7, 31)
        )
        assert sum(a.allocated_quantity for a in result) == consumption

    def test_sum_invariant_two_months(self, service):
        consumption = Decimal("1234.567890")
        result = service.allocate_billing_period(
            consumption, date(2023, 8, 15), date(2023, 9, 14)
        )
        assert sum(a.allocated_quantity for a in result) == consumption

    def test_sum_invariant_three_months(self, service):
        consumption = Decimal("0.000001")
        result = service.allocate_billing_period(
            consumption, date(2023, 1, 1), date(2023, 3, 31)
        )
        assert sum(a.allocated_quantity for a in result) == consumption

    def test_sum_invariant_large_value(self, service):
        consumption = Decimal("99999.999999")
        result = service.allocate_billing_period(
            consumption, date(2023, 6, 1), date(2023, 8, 31)
        )
        assert sum(a.allocated_quantity for a in result) == consumption


class TestAllocateBillingPeriodSingleDay:
    """Edge case: period_start == period_end (single day)."""

    def test_single_day_returns_one_allocation(self, service):
        result = service.allocate_billing_period(
            Decimal("50"),
            date(2023, 6, 15),
            date(2023, 6, 15),
        )
        assert len(result) == 1

    def test_single_day_full_allocation(self, service):
        consumption = Decimal("50")
        result = service.allocate_billing_period(
            consumption,
            date(2023, 6, 15),
            date(2023, 6, 15),
        )
        assert result[0].allocated_quantity == consumption

    def test_single_day_correct_month(self, service):
        result = service.allocate_billing_period(
            Decimal("10"),
            date(2023, 12, 31),
            date(2023, 12, 31),
        )
        assert result[0].year == 2023
        assert result[0].month == 12


class TestAllocateBillingPeriodReturnType:
    """allocate_billing_period() returns a list of MonthlyAllocation objects."""

    def test_returns_list(self, service):
        result = service.allocate_billing_period(
            Decimal("100"), date(2023, 1, 1), date(2023, 1, 31)
        )
        assert isinstance(result, list)

    def test_elements_are_monthly_allocation(self, service):
        result = service.allocate_billing_period(
            Decimal("100"), date(2023, 1, 1), date(2023, 2, 28)
        )
        for item in result:
            assert isinstance(item, MonthlyAllocation)


class TestAllocateBillingPeriodInvalidInput:
    """allocate_billing_period() raises ValueError when period_end < period_start."""

    def test_raises_for_end_before_start(self, service):
        with pytest.raises(ValueError):
            service.allocate_billing_period(
                Decimal("100"),
                date(2023, 6, 30),
                date(2023, 6, 1),
            )
