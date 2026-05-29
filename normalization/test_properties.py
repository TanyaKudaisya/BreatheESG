"""
Property-based tests for the normalization services.

Property 2: Date normalization round-trip
Property 3: Unit normalization preservation
Property 9: Billing period allocation sum invariant

Requirements: 2.2, 5.1-5.4, 2.4, 6.1-6.4, 20.2, 20.3
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from normalization.services import NormalizationService

service = NormalizationService()

# ---------------------------------------------------------------------------
# Property 2: Date normalization round-trip
# ---------------------------------------------------------------------------

VALID_DATES = st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31))


@given(VALID_DATES)
@settings(max_examples=100)
def test_date_round_trip_yyyymmdd(d: date):
    """YYYYMMDD format round-trips correctly."""
    formatted = d.strftime("%Y%m%d")
    assert service.normalize_date(formatted) == d


@given(VALID_DATES)
@settings(max_examples=100)
def test_date_round_trip_iso(d: date):
    """YYYY-MM-DD format round-trips correctly."""
    formatted = d.strftime("%Y-%m-%d")
    assert service.normalize_date(formatted) == d


@given(VALID_DATES)
@settings(max_examples=100)
def test_date_round_trip_dot(d: date):
    """DD.MM.YYYY format round-trips correctly."""
    formatted = d.strftime("%d.%m.%Y")
    assert service.normalize_date(formatted) == d


@given(VALID_DATES)
@settings(max_examples=100)
def test_date_round_trip_slash(d: date):
    """DD/MM/YYYY format round-trips correctly."""
    formatted = d.strftime("%d/%m/%Y")
    assert service.normalize_date(formatted) == d


# ---------------------------------------------------------------------------
# Property 3: Unit normalization preservation
# ---------------------------------------------------------------------------

UNIT_CODES = st.sampled_from(["L", "LTR", "M3", "KG"])
QUANTITIES = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
VALID_NORMALIZED_UNITS = {"litres", "cubic_metres", "kilograms"}


@given(QUANTITIES, UNIT_CODES)
@settings(max_examples=100)
def test_unit_normalization_preserves_original(qty: Decimal, unit: str):
    """Original quantity and unit are always preserved."""
    result = service.normalize_unit(qty, unit)
    assert result.original_quantity == qty
    assert result.original_unit == unit


@given(QUANTITIES, UNIT_CODES)
@settings(max_examples=100)
def test_unit_normalization_valid_output(qty: Decimal, unit: str):
    """Normalized unit is always one of the valid set."""
    result = service.normalize_unit(qty, unit)
    assert result.normalized_unit in VALID_NORMALIZED_UNITS


# ---------------------------------------------------------------------------
# Property 9: Billing period allocation sum invariant
# ---------------------------------------------------------------------------

START_DATES = st.dates(min_value=date(2020, 1, 1), max_value=date(2025, 12, 1))
PERIOD_LENGTHS = st.integers(min_value=1, max_value=90)
CONSUMPTIONS = st.decimals(
    min_value=Decimal("1"),
    max_value=Decimal("99999"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)


@given(START_DATES, PERIOD_LENGTHS, CONSUMPTIONS)
@settings(max_examples=100)
def test_billing_allocation_sum_invariant(
    start: date, length: int, consumption: Decimal
):
    """Sum of monthly allocations always equals original consumption."""
    end = start + timedelta(days=length)
    allocations = service.allocate_billing_period(consumption, start, end)
    total = sum(a.allocated_quantity for a in allocations)
    assert total == consumption, (
        f"Sum {total} != consumption {consumption} for period {start}–{end}"
    )


@given(START_DATES, PERIOD_LENGTHS, CONSUMPTIONS)
@settings(max_examples=50)
def test_billing_allocation_non_negative(
    start: date, length: int, consumption: Decimal
):
    """All monthly allocations are non-negative."""
    end = start + timedelta(days=length)
    allocations = service.allocate_billing_period(consumption, start, end)
    for alloc in allocations:
        assert alloc.allocated_quantity >= 0
