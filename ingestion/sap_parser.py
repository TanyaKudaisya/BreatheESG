"""
SAP Parser for the Breathe ESG Data Ingestion System.

Parses tab-separated SAP fuel procurement export files into structured
SAPRecord dataclasses, collecting ParseError objects for any rows that
cannot be fully parsed.

Requirements: 2.1, 2.2
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class SAPRecord:
    """
    A single parsed row from a SAP tab-separated export file.

    All fields are stored as raw strings; numeric conversion and date
    normalization are handled by the downstream normalization layer.

    Attributes:
        ebeln:    Purchase order number (SAP field EBELN).
        ebelp:    Purchase order item number (SAP field EBELP).
        bedat:    Document date as a raw string (SAP field BEDAT).
        werks:    Plant code (SAP field WERKS).
        menge:    Quantity as a raw string; may be blank (SAP field MENGE).
        meins:    Unit of measure code (SAP field MEINS).
        netpr:    Net price as a raw string (SAP field NETPR).
        txz01:    Material description text (SAP field TXZ01).
        matnr:    Material number (SAP field MATNR).
        waers:    Currency code (SAP field WAERS).
        raw_row:  The original row as a dict keyed by upper-cased column names.
    """

    ebeln: str
    ebelp: str
    bedat: str
    werks: str
    menge: str        # raw string; blank MENGE is valid at parse time
    meins: str
    netpr: str
    txz01: str
    matnr: str
    waers: str
    raw_row: dict = field(default_factory=dict)


@dataclass
class ParseError:
    """
    Describes a row-level parsing failure.

    Attributes:
        row_number: 1-based row number in the source file (header = row 1).
        message:    Human-readable description of the problem.
        raw_line:   The original raw line text (empty string if unavailable).
    """

    row_number: int
    message: str
    raw_line: str = ""


# ---------------------------------------------------------------------------
# SAPParser
# ---------------------------------------------------------------------------


class SAPParser:
    """
    Parses tab-separated SAP export files into :class:`SAPRecord` objects.

    Usage::

        parser = SAPParser()
        records, errors = parser.parse_file(file_bytes, "sap_export.txt")

    Requirements: 2.1
    """

    REQUIRED_COLUMNS = [
        "EBELN",
        "EBELP",
        "BEDAT",
        "WERKS",
        "MENGE",
        "MEINS",
        "NETPR",
        "TXZ01",
        "MATNR",
        "WAERS",
    ]

    def parse_file(
        self,
        file_content: bytes,
        filename: str = "",
    ) -> tuple[list[SAPRecord], list[ParseError]]:
        """
        Parse a tab-separated SAP export file.

        Decoding is attempted as UTF-8 first; if that fails, latin-1 is used
        as a fallback (common for SAP exports from European systems).

        The first non-empty line is treated as the header row.  Column names
        are matched case-insensitively so that files with mixed-case headers
        are handled correctly.

        Args:
            file_content: Raw bytes of the uploaded file.
            filename:     Original filename (used only for logging).

        Returns:
            A tuple ``(records, errors)`` where:
            - ``records`` is a list of successfully parsed :class:`SAPRecord`
              objects.
            - ``errors`` is a list of :class:`ParseError` objects describing
              rows that could not be parsed.

        If the header row is missing any required column, a single
        :class:`ParseError` is returned and ``records`` is empty.

        Requirements: 2.1
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

        lines = text.splitlines()

        # ------------------------------------------------------------------
        # 2. Find and parse the header row
        # ------------------------------------------------------------------
        header_line_index: Optional[int] = None
        header_map: dict[str, int] = {}  # upper-cased column name → column index

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Treat the first non-empty line as the header.
            parts = stripped.split("\t")
            header_map = {col.strip().upper(): idx for idx, col in enumerate(parts)}
            header_line_index = i
            break

        if header_line_index is None:
            return [], [ParseError(row_number=0, message="File is empty or contains only blank lines.")]

        # ------------------------------------------------------------------
        # 3. Validate that all required columns are present
        # ------------------------------------------------------------------
        missing_columns = [
            col for col in self.REQUIRED_COLUMNS if col not in header_map
        ]
        if missing_columns:
            return [], [
                ParseError(
                    row_number=1,
                    message=(
                        f"Missing required columns: {', '.join(missing_columns)}. "
                        f"Found columns: {', '.join(header_map.keys())}."
                    ),
                    raw_line=lines[header_line_index],
                )
            ]

        # ------------------------------------------------------------------
        # 4. Parse data rows
        # ------------------------------------------------------------------
        records: list[SAPRecord] = []
        errors: list[ParseError] = []

        for line_index in range(header_line_index + 1, len(lines)):
            raw_line = lines[line_index]
            row_number = line_index + 1  # 1-based, header is row 1

            # Skip blank lines silently.
            if not raw_line.strip():
                continue

            parts = raw_line.split("\t")

            # Build a raw_row dict using the header map.
            raw_row: dict[str, str] = {}
            for col_name, col_idx in header_map.items():
                raw_row[col_name] = parts[col_idx].strip() if col_idx < len(parts) else ""

            # Check for missing required fields (empty string for non-MENGE fields).
            missing_fields = []
            for col in self.REQUIRED_COLUMNS:
                if col == "MENGE":
                    # Blank MENGE is valid at parse time; skip this check.
                    continue
                value = raw_row.get(col, "")
                if not value:
                    missing_fields.append(col)

            if missing_fields:
                errors.append(
                    ParseError(
                        row_number=row_number,
                        message=f"Missing required fields: {', '.join(missing_fields)}.",
                        raw_line=raw_line,
                    )
                )
                continue

            # Build the SAPRecord.
            record = SAPRecord(
                ebeln=raw_row.get("EBELN", ""),
                ebelp=raw_row.get("EBELP", ""),
                bedat=raw_row.get("BEDAT", ""),
                werks=raw_row.get("WERKS", ""),
                menge=raw_row.get("MENGE", ""),   # may be blank — valid
                meins=raw_row.get("MEINS", ""),
                netpr=raw_row.get("NETPR", ""),
                txz01=raw_row.get("TXZ01", ""),
                matnr=raw_row.get("MATNR", ""),
                waers=raw_row.get("WAERS", ""),
                raw_row=raw_row,
            )
            records.append(record)

        logger.debug(
            "SAPParser: parsed %d records and %d errors from '%s'.",
            len(records),
            len(errors),
            filename,
        )
        return records, errors
