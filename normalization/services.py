"""
Normalization services for the Breathe ESG Data Ingestion system.

Converts heterogeneous units, dates, and data structures into standardized formats.
"""

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List

from .exceptions import DateParseError, UnknownUnitError


@dataclass
class MonthlyAllocation:
    """
    Proportional allocation of a utility billing period to a single calendar month.

    Attributes:
        year: The calendar year (e.g. 2023).
        month: The calendar month as an integer 1–12.
        allocated_quantity: The portion of the total consumption attributed to
            this month, proportional to the number of days in the billing period
            that fall within this month.
        unit: The unit of the allocated quantity (default "kwh").
    """

    year: int
    month: int
    allocated_quantity: Decimal
    unit: str = "kwh"


@dataclass
class NormalizedQuantity:
    """
    Holds both the original and normalized quantity/unit pair.

    Attributes:
        original_quantity: The quantity as received from the source system.
        original_unit: The unit code as received from the source system (e.g. "L", "LTR").
        normalized_quantity: The quantity after unit conversion (currently 1:1 for all
            supported units — no numeric conversion is applied).
        normalized_unit: The standardized unit name (e.g. "litres", "cubic_metres",
            "kilograms").
    """

    original_quantity: Decimal
    original_unit: str
    normalized_quantity: Decimal
    normalized_unit: str


# Mapping from upper-cased source unit codes to their standardized unit names.
# Quantities are preserved as-is (no numeric conversion factor needed for these units).
_UNIT_MAP: dict[str, str] = {
    "L": "litres",
    "LTR": "litres",
    "M3": "cubic_metres",
    "KG": "kilograms",
}


# Compiled regex patterns for each supported date format.
# Order matters: YYYYMMDD must be checked before YYYY-MM-DD to avoid ambiguity.
_DATE_PATTERNS = [
    # YYYYMMDD — eight consecutive digits, no separators
    (re.compile(r"^\d{8}$"), "%Y%m%d"),
    # YYYY-MM-DD — ISO 8601 with hyphens
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
    # DD.MM.YYYY — European format with period separators
    (re.compile(r"^\d{2}\.\d{2}\.\d{4}$"), "%d.%m.%Y"),
    # DD/MM/YYYY — European format with slash separators
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "%d/%m/%Y"),
]


class NormalizationService:
    """
    Service that normalizes dates, units, and billing periods from heterogeneous
    source systems into standardized formats.
    """

    def normalize_date(self, date_string: str) -> date:
        """
        Convert a date string from any supported format to a Python ``date`` object.

        Supported input formats:
        - ``YYYYMMDD``   — e.g. ``"20231231"``
        - ``YYYY-MM-DD`` — e.g. ``"2023-12-31"``
        - ``DD.MM.YYYY`` — e.g. ``"31.12.2023"``
        - ``DD/MM/YYYY`` — e.g. ``"31/12/2023"``

        Args:
            date_string: The raw date string from the source system.

        Returns:
            A ``datetime.date`` object representing the parsed date.

        Raises:
            DateParseError: If the string does not match any supported format,
                or if the matched format produces an invalid calendar date
                (e.g. month 13, day 32).
        """
        if not isinstance(date_string, str):
            raise DateParseError(str(date_string))

        stripped = date_string.strip()

        for pattern, fmt in _DATE_PATTERNS:
            if pattern.match(stripped):
                try:
                    from datetime import datetime

                    return datetime.strptime(stripped, fmt).date()
                except ValueError:
                    # Pattern matched structurally but the calendar date is invalid
                    # (e.g. "31.02.2023"). Raise a descriptive error.
                    raise DateParseError(date_string)

        raise DateParseError(date_string)

    def normalize_unit(self, quantity: Decimal, unit_code: str) -> NormalizedQuantity:
        """
        Convert a source unit code to a standardized unit name.

        Supported unit codes (case-insensitive):
        - ``L`` or ``LTR`` → ``litres``
        - ``M3``           → ``cubic_metres``
        - ``KG``           → ``kilograms``

        The numeric quantity is preserved unchanged; no conversion factor is applied
        because all supported mappings are aliases for the same physical unit.

        Args:
            quantity: The numeric quantity from the source system.
            unit_code: The raw unit code string (e.g. ``"L"``, ``"LTR"``, ``"M3"``,
                ``"KG"``).  Leading/trailing whitespace is stripped and the value is
                upper-cased before lookup.

        Returns:
            A :class:`NormalizedQuantity` dataclass containing both the original and
            normalized quantity/unit pair.

        Raises:
            UnknownUnitError: If the unit code is not in the recognized set.
        """
        normalized_code = unit_code.strip().upper()
        normalized_unit = _UNIT_MAP.get(normalized_code)
        if normalized_unit is None:
            raise UnknownUnitError(unit_code)

        return NormalizedQuantity(
            original_quantity=quantity,
            original_unit=unit_code,
            normalized_quantity=quantity,
            normalized_unit=normalized_unit,
        )

    def allocate_billing_period(
        self,
        consumption_kwh: Decimal,
        period_start: date,
        period_end: date,
    ) -> List[MonthlyAllocation]:
        """
        Proportionally allocate ``consumption_kwh`` across the calendar months
        covered by the billing period.

        The allocation for each month is proportional to the number of days in
        that month that fall within ``[period_start, period_end]`` (inclusive).
        Rounding is handled by adjusting the last month so that the sum of all
        allocated quantities equals exactly ``consumption_kwh``.

        Args:
            consumption_kwh: Total electricity consumption for the billing period.
            period_start: First day of the billing period (inclusive).
            period_end: Last day of the billing period (inclusive).

        Returns:
            A list of :class:`MonthlyAllocation` objects, one per calendar month
            touched by the billing period, ordered chronologically.

        Raises:
            ValueError: If ``period_end`` is before ``period_start``.

        Requirements: 20.1, 20.2, 20.3
        """
        if period_end < period_start:
            raise ValueError(
                f"period_end ({period_end}) must not be before period_start ({period_start})"
            )

        # Collect (year, month, days_in_period) tuples for each month touched.
        month_days: List[tuple[int, int, int]] = []

        current_year = period_start.year
        current_month = period_start.month

        while (current_year, current_month) <= (period_end.year, period_end.month):
            # First day of this month that falls within the billing period.
            month_start = date(current_year, current_month, 1)
            _, last_day = calendar.monthrange(current_year, current_month)
            month_end = date(current_year, current_month, last_day)

            overlap_start = max(period_start, month_start)
            overlap_end = min(period_end, month_end)

            days_in_period = (overlap_end - overlap_start).days + 1
            month_days.append((current_year, current_month, days_in_period))

            # Advance to the next month.
            if current_month == 12:
                current_year += 1
                current_month = 1
            else:
                current_month += 1

        total_days = sum(d for _, _, d in month_days)

        # Allocate proportionally, rounding to 6 decimal places.
        allocations: List[MonthlyAllocation] = []
        allocated_so_far = Decimal("0")
        quantize_target = Decimal("0.000001")

        for i, (year, month, days) in enumerate(month_days):
            is_last = i == len(month_days) - 1

            if is_last:
                # Assign the remainder to avoid accumulated rounding error.
                allocated_qty = consumption_kwh - allocated_so_far
            else:
                proportion = Decimal(days) / Decimal(total_days)
                allocated_qty = (consumption_kwh * proportion).quantize(
                    quantize_target, rounding=ROUND_HALF_UP
                )
                allocated_so_far += allocated_qty

            allocations.append(
                MonthlyAllocation(
                    year=year,
                    month=month,
                    allocated_quantity=allocated_qty,
                )
            )

        return allocations
