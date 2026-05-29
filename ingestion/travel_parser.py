"""
Travel (Concur) JSON Parser for the Breathe ESG Data Ingestion System.

Parses Concur Expense v3 API JSON payloads into structured TravelRecord
dataclasses by flattening the nested expense_reports → entries arrays.
One TravelRecord is produced per entry.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ingestion.sap_parser import ParseError  # reuse ParseError from sap_parser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TravelRecord dataclass
# ---------------------------------------------------------------------------


@dataclass
class TravelRecord:
    """
    A single flattened travel expense entry from a Concur JSON export.

    One TravelRecord is created per entry in the nested
    expense_reports → entries structure.

    Attributes:
        report_id:            Concur expense report ID (from parent report).
        entry_id:             Concur expense entry ID.
        expense_type:         AIRFARE, HOTEL, GROUND_TRANSPORT_TAXI, etc.
        employee_id:          Employee identifier (from parent report).
        employee_name:        Employee full name (from parent report).
        department:           Department name (from parent report).
        approval_status:      APPROVED or PENDING_APPROVAL (from parent report).
        receipt_attached:     Whether a receipt is attached to this entry.
        transaction_date:     Raw date string from the entry.

        # Flight-specific
        origin_airport:       IATA code of departure airport.
        destination_airport:  IATA code of arrival airport.
        via_airport:          IATA code of connecting airport (multi-leg flights).
        cabin_class:          ECONOMY or BUSINESS.
        distance_km:          Pre-calculated distance (may be null; calculated later).

        # Hotel-specific
        city:                 City of the hotel.
        country:              Country code of the hotel.
        check_in:             Raw check-in date string.
        check_out:            Raw check-out date string.
        nights:               Number of nights stayed.

        # Ground transport-specific
        fuel_type:            Fuel type for rental cars (e.g. PETROL, DIESEL).

        raw_entry:            The original entry dict preserved for audit purposes.
    """

    report_id: str
    entry_id: str
    expense_type: str
    employee_id: str
    employee_name: str
    department: str
    approval_status: str
    receipt_attached: bool
    transaction_date: str

    # Flight-specific
    origin_airport: str
    destination_airport: str
    via_airport: str
    cabin_class: str
    distance_km: Optional[float]

    # Hotel-specific
    city: str
    country: str
    check_in: str
    check_out: str
    nights: Optional[int]

    # Ground transport-specific
    fuel_type: str

    raw_entry: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TravelParser
# ---------------------------------------------------------------------------


class TravelParser:
    """
    Parses Concur Expense v3 JSON payloads into :class:`TravelRecord` objects.

    The Concur JSON structure is:
    {
        "expense_reports": [
            {
                "report_id": "...",
                "employee_id": "...",
                ...
                "entries": [
                    { "entry_id": "...", "expense_type": "AIRFARE", ... },
                    ...
                ]
            },
            ...
        ]
    }

    Each entry is flattened into a TravelRecord that inherits report-level
    fields (report_id, employee_id, employee_name, department, approval_status).

    Requirements: 4.1
    """

    def parse_json(
        self,
        payload: dict,
    ) -> tuple[list[TravelRecord], list[ParseError]]:
        """
        Parse a Concur JSON payload and flatten nested entries into TravelRecords.

        Args:
            payload: Parsed JSON dict matching the Concur Expense v3 API schema.

        Returns:
            A tuple ``(records, errors)`` where:
            - ``records`` is a list of :class:`TravelRecord` objects, one per entry.
            - ``errors`` is a list of :class:`ParseError` objects for entries that
              could not be parsed.

        Requirements: 4.1
        """
        records: list[TravelRecord] = []
        errors: list[ParseError] = []

        if not isinstance(payload, dict):
            errors.append(ParseError(
                row_number=0,
                message="Payload must be a JSON object (dict).",
            ))
            return records, errors

        expense_reports = payload.get("expense_reports", [])
        if not isinstance(expense_reports, list):
            errors.append(ParseError(
                row_number=0,
                message="'expense_reports' must be a list.",
            ))
            return records, errors

        entry_index = 0  # global entry counter for error row numbers

        for report_index, report in enumerate(expense_reports):
            if not isinstance(report, dict):
                errors.append(ParseError(
                    row_number=report_index + 1,
                    message=f"expense_reports[{report_index}] is not a dict; skipping.",
                ))
                continue

            # Extract report-level fields (inherited by all entries in this report).
            report_id = str(report.get("report_id", "")).strip()
            employee_id = str(report.get("employee_id", "")).strip()
            employee_name = str(report.get("employee_name", "")).strip()
            department = str(report.get("department", "")).strip()
            approval_status = str(report.get("approval_status", "")).strip()

            entries = report.get("entries", [])
            if not isinstance(entries, list):
                errors.append(ParseError(
                    row_number=report_index + 1,
                    message=(
                        f"Report '{report_id}': 'entries' field is not a list; "
                        "skipping all entries for this report."
                    ),
                ))
                continue

            for entry in entries:
                entry_index += 1

                if not isinstance(entry, dict):
                    errors.append(ParseError(
                        row_number=entry_index,
                        message=(
                            f"Report '{report_id}': entry at index {entry_index} "
                            "is not a dict; skipping."
                        ),
                    ))
                    continue

                try:
                    record = self._parse_entry(
                        entry=entry,
                        report_id=report_id,
                        employee_id=employee_id,
                        employee_name=employee_name,
                        department=department,
                        approval_status=approval_status,
                        entry_index=entry_index,
                    )
                    records.append(record)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "TravelParser: failed to parse entry %d in report '%s': %s",
                        entry_index,
                        report_id,
                        exc,
                    )
                    errors.append(ParseError(
                        row_number=entry_index,
                        message=(
                            f"Report '{report_id}', entry_id="
                            f"'{entry.get('entry_id', '?')}': {exc}"
                        ),
                    ))

        logger.debug(
            "TravelParser: parsed %d records and %d errors.",
            len(records),
            len(errors),
        )
        return records, errors

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_entry(
        self,
        entry: dict,
        report_id: str,
        employee_id: str,
        employee_name: str,
        department: str,
        approval_status: str,
        entry_index: int,
    ) -> TravelRecord:
        """
        Parse a single entry dict into a :class:`TravelRecord`.

        Missing optional fields default to empty strings or None.
        """
        entry_id = str(entry.get("entry_id", "")).strip()
        expense_type = str(entry.get("expense_type", "")).strip()
        transaction_date = str(entry.get("transaction_date", "")).strip()

        # receipt_attached: default to False if missing (conservative)
        receipt_attached_raw = entry.get("receipt_attached")
        if isinstance(receipt_attached_raw, bool):
            receipt_attached = receipt_attached_raw
        else:
            receipt_attached = False

        # Flight-specific fields
        origin_airport = str(entry.get("origin_airport", "") or "").strip()
        destination_airport = str(entry.get("destination_airport", "") or "").strip()
        via_airport = str(entry.get("via_airport", "") or "").strip()
        cabin_class = str(entry.get("cabin_class", "") or "").strip()

        # distance_km: may be null in source; keep as float or None
        distance_km_raw = entry.get("distance_km")
        if distance_km_raw is not None:
            try:
                distance_km: Optional[float] = float(distance_km_raw)
            except (TypeError, ValueError):
                distance_km = None
        else:
            distance_km = None

        # Hotel-specific fields
        city = str(entry.get("city", "") or "").strip()
        country = str(entry.get("country", "") or "").strip()
        check_in = str(entry.get("check_in", "") or "").strip()
        check_out = str(entry.get("check_out", "") or "").strip()

        nights_raw = entry.get("nights")
        if nights_raw is not None:
            try:
                nights: Optional[int] = int(nights_raw)
            except (TypeError, ValueError):
                nights = None
        else:
            nights = None

        # Ground transport-specific fields
        fuel_type = str(entry.get("fuel_type", "") or "").strip()

        return TravelRecord(
            report_id=report_id,
            entry_id=entry_id,
            expense_type=expense_type,
            employee_id=employee_id,
            employee_name=employee_name,
            department=department,
            approval_status=approval_status,
            receipt_attached=receipt_attached,
            transaction_date=transaction_date,
            origin_airport=origin_airport,
            destination_airport=destination_airport,
            via_airport=via_airport,
            cabin_class=cabin_class,
            distance_km=distance_km,
            city=city,
            country=country,
            check_in=check_in,
            check_out=check_out,
            nights=nights,
            fuel_type=fuel_type,
            raw_entry=dict(entry),
        )
