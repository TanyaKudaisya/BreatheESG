"""
Utility CSV Parser for the Breathe ESG Data Ingestion System.

Parses utility electricity CSV files into structured UtilityRecord dataclasses,
collecting ParseError objects for any rows that cannot be fully parsed.

Non-consumption financial columns (power_factor_penalty_inr, fuel_adjustment_inr)
are intentionally ignored per Requirement 3.4.

Requirements: 3.1, 3.2, 3.4
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

# Re-export ParseError from sap_parser so callers can import from one place.
from ingestion.sap_parser import ParseError  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------


@dataclass
class UtilityRecord:
    """
    A single parsed row from a utility electricity CSV file.

    All fields are stored as raw strings; numeric conversion and date
    normalization are handled by the downstream normalization layer.

    Attributes:
        account_number:       Utility account identifier.
        meter_id:             Individual meter identifier within the account.
        service_address:      Physical address of the metered premises.
        billing_period_start: Start date of the billing period (raw string).
        billing_period_end:   End date of the billing period (raw string).
        consumption_kwh:      Total electricity consumed (raw string).
        reading_type:         "ACTUAL" or "ESTIMATED".
        tariff_code:          Tariff/rate schedule code.
        demand_kw:            Peak demand in kW (raw string; may be empty).
        raw_row:              Original CSV row as a dict keyed by column name.
    """

    account_number: str
    meter_id: str
    service_address: str
    billing_period_start: str   # raw date string
    billing_period_end: str     # raw date string
    consumption_kwh: str        # raw string
    reading_type: str           # ACTUAL or ESTIMATED
    tariff_code: str
    demand_kw: str              # raw string, may be empty
    raw_row: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# UtilityParser
# ---------------------------------------------------------------------------


class UtilityParser:
    """
    Parses utility electricity CSV files into :class:`UtilityRecord` objects.

    Usage::

        parser = UtilityParser()
        records, errors = parser.parse_file(file_bytes, "utility_electricity.csv")

    Requirements: 3.1, 3.2, 3.4
    """

    REQUIRED_COLUMNS = [
        "account_number",
        "meter_id",
        "billing_period_start",
        "billing_period_end",
        "consumption_kwh",
        "reading_type",
        "tariff_code",
    ]

    # Columns that are present in the CSV but should be silently ignored.
    # Requirement 3.4: ignore non-consumption financial charges.
    _IGNORED_COLUMNS = frozenset(
        ["power_factor_penalty_inr", "fuel_adjustment_inr"]
    )

    def parse_file(
        self,
        file_content: bytes,
        filename: str = "",
    ) -> tuple[list[UtilityRecord], list[ParseError]]:
        """
        Parse a utility electricity CSV file.

        Decoding is attempted as UTF-8 first; if that fails, latin-1 is used
        as a fallback.  The first non-empty line is treated as the header row.
        Column names are matched case-insensitively.

        Args:
            file_content: Raw bytes of the uploaded CSV file.
            filename:     Original filename (used only for logging).

        Returns:
            A tuple ``(records, errors)`` where:
            - ``records`` is a list of successfully parsed :class:`UtilityRecord`
              objects.
            - ``errors`` is a list of :class:`ParseError` objects describing
              rows that could not be parsed.

        If the header row is missing any required column, a single
        :class:`ParseError` is returned and ``records`` is empty.

        Requirements: 3.1, 3.2, 3.4
        """
        # ------------------------------------------------------------------
        # 1. Decode bytes
        # ------------------------------------------------------------------
        try:
            text = file_content.decode("utf-8")
        except UnicodeDecodeError:
            logger.debug(
                "UTF-8 decode failed for '%s'; falling back to latin-1.", filename
            )
            text = file_content.decode("latin-1")

        # ------------------------------------------------------------------
        # 2. Parse CSV using the csv module (handles quoted fields, etc.)
        # ------------------------------------------------------------------
        reader = csv.DictReader(io.StringIO(text))

        # csv.DictReader reads the header automatically; fieldnames may be None
        # if the file is empty.
        try:
            fieldnames = reader.fieldnames
        except Exception:
            fieldnames = None

        if not fieldnames:
            return [], [
                ParseError(
                    row_number=0,
                    message="File is empty or contains only blank lines.",
                )
            ]

        # Normalise header names to lower-case for case-insensitive matching.
        lower_fieldnames = [f.strip().lower() for f in fieldnames]

        # ------------------------------------------------------------------
        # 3. Validate that all required columns are present
        # ------------------------------------------------------------------
        missing_columns = [
            col for col in self.REQUIRED_COLUMNS if col not in lower_fieldnames
        ]
        if missing_columns:
            return [], [
                ParseError(
                    row_number=1,
                    message=(
                        f"Missing required columns: {', '.join(missing_columns)}. "
                        f"Found columns: {', '.join(lower_fieldnames)}."
                    ),
                )
            ]

        # ------------------------------------------------------------------
        # 4. Parse data rows
        # ------------------------------------------------------------------
        records: list[UtilityRecord] = []
        errors: list[ParseError] = []

        for row_index, raw_row_dict in enumerate(reader, start=2):  # row 1 = header
            # Normalise keys to lower-case.
            row: dict[str, str] = {
                k.strip().lower(): (v.strip() if v is not None else "")
                for k, v in raw_row_dict.items()
                if k is not None
            }

            # Skip entirely blank rows.
            if not any(row.values()):
                continue

            # Check required fields are non-empty.
            missing_fields = [
                col for col in self.REQUIRED_COLUMNS if not row.get(col, "")
            ]
            if missing_fields:
                errors.append(
                    ParseError(
                        row_number=row_index,
                        message=f"Missing required fields: {', '.join(missing_fields)}.",
                        raw_line=",".join(raw_row_dict.values()),
                    )
                )
                continue

            # Build the UtilityRecord.  demand_kw is optional (may be empty).
            record = UtilityRecord(
                account_number=row.get("account_number", ""),
                meter_id=row.get("meter_id", ""),
                service_address=row.get("service_address", ""),
                billing_period_start=row.get("billing_period_start", ""),
                billing_period_end=row.get("billing_period_end", ""),
                consumption_kwh=row.get("consumption_kwh", ""),
                reading_type=row.get("reading_type", ""),
                tariff_code=row.get("tariff_code", ""),
                demand_kw=row.get("demand_kw", ""),
                raw_row=row,
            )
            records.append(record)

        logger.debug(
            "UtilityParser: parsed %d records and %d errors from '%s'.",
            len(records),
            len(errors),
            filename,
        )
        return records, errors
