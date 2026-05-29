"""
Validation service for the Breathe ESG Data Ingestion System.

Provides data quality checks and duplicate detection for emission records
before they are persisted to the database.

Requirements: 2.5, 3.3, 4.7, 4.8, 6.5, 18.x, 19.1, 19.2, 19.3, 19.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flag type constants
# ---------------------------------------------------------------------------

FLAG_ESTIMATED_READING = "estimated_reading"
FLAG_MISSING_RECEIPT = "missing_receipt"
FLAG_ZERO_PRICE = "zero_price"
FLAG_BLANK_QUANTITY = "blank_quantity"
FLAG_PENDING_APPROVAL = "pending_approval"
FLAG_UNKNOWN_AIRPORT = "unknown_airport"
FLAG_UNKNOWN_UNIT = "unknown_unit"
FLAG_POTENTIAL_DUPLICATE = "potential_duplicate"

SEVERITY_WARNING = "WARNING"
SEVERITY_ERROR = "ERROR"

# Unit codes recognised by the normalization service
_KNOWN_UNIT_CODES = frozenset({"L", "LTR", "M3", "KG"})


# ---------------------------------------------------------------------------
# Data transfer object returned by detect_duplicate()
# ---------------------------------------------------------------------------


@dataclass
class DataQualityFlagData:
    """
    Lightweight dataclass representing a data quality flag.

    This is a plain Python object (not a Django model instance) so that
    the ValidationService can be called before a record is saved to the
    database.  The caller is responsible for persisting this as a
    DataQualityFlag model instance if required.
    """

    flag_type: str
    severity: str
    message: str
    field_name: Optional[str] = None


# ---------------------------------------------------------------------------
# ValidationService
# ---------------------------------------------------------------------------


class ValidationService:
    """
    Applies data quality rules and duplicate detection to emission records.

    All methods are stateless and can be called without instantiating a
    persistent object.  The service queries the database only when needed
    (e.g. duplicate detection).
    """

    # ------------------------------------------------------------------
    # Data quality validation (Requirements 2.5, 3.3, 4.7, 4.8, 6.5, 18.x)
    # ------------------------------------------------------------------

    def validate_emission_record(
        self,
        record: dict,
        source_system: str,
    ) -> List[DataQualityFlagData]:
        """
        Apply all data quality rules to a parsed emission record dict.

        Args:
            record: Parsed record as a plain dict (not a Django model).
            source_system: One of "SAP", "UTILITY", or "CONCUR".

        Returns:
            List of DataQualityFlagData objects (empty if no issues found).
        """
        source_upper = source_system.strip().upper()
        flags: List[DataQualityFlagData] = []

        if source_upper == "SAP":
            flags.extend(self._validate_sap(record))
        elif source_upper == "UTILITY":
            flags.extend(self._validate_utility(record))
        elif source_upper == "CONCUR":
            flags.extend(self._validate_concur(record))
        else:
            logger.warning(
                "validate_emission_record called with unknown source_system=%r; "
                "skipping validation.",
                source_system,
            )

        return flags

    # ------------------------------------------------------------------
    # SAP validation rules
    # ------------------------------------------------------------------

    def _validate_sap(self, record: dict) -> List[DataQualityFlagData]:
        flags: List[DataQualityFlagData] = []

        # Blank quantity (MENGE empty) → ERROR  (Req 2.5, 18.4)
        menge = record.get("menge")
        if menge is None or (isinstance(menge, str) and not menge.strip()):
            flags.append(DataQualityFlagData(
                flag_type=FLAG_BLANK_QUANTITY,
                severity=SEVERITY_ERROR,
                message="SAP MENGE (quantity) is blank or missing.",
                field_name="menge",
            ))

        # Zero price (NETPR = 0.00) → ERROR  (Req 18.3)
        netpr = record.get("netpr")
        if netpr is not None:
            try:
                if float(netpr) == 0.0:
                    flags.append(DataQualityFlagData(
                        flag_type=FLAG_ZERO_PRICE,
                        severity=SEVERITY_ERROR,
                        message="SAP NETPR (net price) is zero.",
                        field_name="netpr",
                    ))
            except (TypeError, ValueError):
                pass

        # Unknown unit code (MEINS) → WARNING  (Req 6.5, 18.7)
        meins = record.get("meins")
        if meins is not None:
            if meins.strip().upper() not in _KNOWN_UNIT_CODES:
                flags.append(DataQualityFlagData(
                    flag_type=FLAG_UNKNOWN_UNIT,
                    severity=SEVERITY_WARNING,
                    message=f"SAP MEINS unit code '{meins}' is not recognised.",
                    field_name="meins",
                ))

        return flags

    # ------------------------------------------------------------------
    # Utility validation rules
    # ------------------------------------------------------------------

    def _validate_utility(self, record: dict) -> List[DataQualityFlagData]:
        flags: List[DataQualityFlagData] = []

        # Estimated reading → WARNING  (Req 3.3, 18.1)
        reading_type = record.get("reading_type")
        if reading_type is not None:
            if str(reading_type).strip().upper() == "ESTIMATED":
                flags.append(DataQualityFlagData(
                    flag_type=FLAG_ESTIMATED_READING,
                    severity=SEVERITY_WARNING,
                    message="Utility reading_type is ESTIMATED (not an actual meter read).",
                    field_name="reading_type",
                ))

        return flags

    # ------------------------------------------------------------------
    # Concur / Travel validation rules
    # ------------------------------------------------------------------

    def _validate_concur(self, record: dict) -> List[DataQualityFlagData]:
        flags: List[DataQualityFlagData] = []

        # Missing receipt → WARNING  (Req 4.8, 18.2)
        receipt_attached = record.get("receipt_attached")
        if receipt_attached is False:
            flags.append(DataQualityFlagData(
                flag_type=FLAG_MISSING_RECEIPT,
                severity=SEVERITY_WARNING,
                message="Travel expense has no receipt attached.",
                field_name="receipt_attached",
            ))

        # Pending approval → WARNING  (Req 4.7, 18.5)
        approval_status = record.get("approval_status")
        if approval_status is not None:
            if str(approval_status).strip().upper() == "PENDING_APPROVAL":
                flags.append(DataQualityFlagData(
                    flag_type=FLAG_PENDING_APPROVAL,
                    severity=SEVERITY_WARNING,
                    message="Travel expense approval_status is PENDING_APPROVAL.",
                    field_name="approval_status",
                ))

        return flags

    # ------------------------------------------------------------------
    # Duplicate detection (Requirements 19.1 – 19.4)
    # ------------------------------------------------------------------

    def detect_duplicate(
        self,
        record: dict,
        source_system: str,
        tenant_id: str,
    ) -> Optional[DataQualityFlagData]:
        """
        Check whether an existing EmissionRecord with the same natural key
        already exists for this tenant.

        Natural keys per source system:
        - SAP:     (ebeln, ebelp, tenant_id)          — Req 19.1
        - UTILITY: (account_number, meter_id,
                    billing_period_start, tenant_id)   — Req 19.2
        - CONCUR:  (report_id, entry_id, tenant_id)   — Req 19.3

        Returns:
            DataQualityFlagData with flag_type="potential_duplicate" and
            severity="WARNING" if a duplicate is found, otherwise None.

        Requirements: 19.1, 19.2, 19.3, 19.4
        """
        # Import here to avoid circular imports at module load time.
        from emissions.models import EmissionRecord

        source_upper = source_system.upper()

        if source_upper == "SAP":
            return self._detect_sap_duplicate(record, tenant_id, EmissionRecord)
        elif source_upper == "UTILITY":
            return self._detect_utility_duplicate(record, tenant_id, EmissionRecord)
        elif source_upper == "CONCUR":
            return self._detect_concur_duplicate(record, tenant_id, EmissionRecord)
        else:
            logger.warning(
                "detect_duplicate called with unknown source_system=%r; "
                "skipping duplicate check.",
                source_system,
            )
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_sap_duplicate(
        self,
        record: dict,
        tenant_id: str,
        EmissionRecord,
    ) -> Optional[DataQualityFlagData]:
        """
        SAP natural key: (EBELN, EBELP, tenant_id).

        Requirement 19.1
        """
        ebeln = record.get("ebeln", "")
        ebelp = record.get("ebelp", "")

        if not ebeln or not ebelp:
            # Cannot perform a meaningful duplicate check without the key fields.
            return None

        exists = (
            EmissionRecord.objects
            .filter(
                tenant_id=tenant_id,
                source_system="SAP",
                ebeln=ebeln,
                ebelp=ebelp,
            )
            .exists()
        )

        if exists:
            message = (
                f"Duplicate SAP record detected: a record with "
                f"EBELN={ebeln!r} and EBELP={ebelp!r} already exists "
                f"for this tenant."
            )
            logger.info(message)
            return DataQualityFlagData(
                flag_type="potential_duplicate",
                severity="WARNING",
                message=message,
                field_name="ebeln,ebelp",
            )
        return None

    def _detect_utility_duplicate(
        self,
        record: dict,
        tenant_id: str,
        EmissionRecord,
    ) -> Optional[DataQualityFlagData]:
        """
        Utility natural key: (account_number, meter_id, billing_period_start, tenant_id).

        Requirement 19.2
        """
        account_number = record.get("account_number", "")
        meter_id = record.get("meter_id", "")
        billing_period_start = record.get("billing_period_start")

        if not account_number or not meter_id or billing_period_start is None:
            return None

        exists = (
            EmissionRecord.objects
            .filter(
                tenant_id=tenant_id,
                source_system="UTILITY",
                account_number=account_number,
                meter_id=meter_id,
                billing_period_start=billing_period_start,
            )
            .exists()
        )

        if exists:
            message = (
                f"Duplicate utility record detected: a record with "
                f"account_number={account_number!r}, meter_id={meter_id!r}, "
                f"billing_period_start={billing_period_start} already exists "
                f"for this tenant."
            )
            logger.info(message)
            return DataQualityFlagData(
                flag_type="potential_duplicate",
                severity="WARNING",
                message=message,
                field_name="account_number,meter_id,billing_period_start",
            )
        return None

    def _detect_concur_duplicate(
        self,
        record: dict,
        tenant_id: str,
        EmissionRecord,
    ) -> Optional[DataQualityFlagData]:
        """
        Travel (Concur) natural key: (report_id, entry_id, tenant_id).

        Requirement 19.3
        """
        report_id = record.get("report_id", "")
        entry_id = record.get("entry_id", "")

        if not report_id or not entry_id:
            return None

        exists = (
            EmissionRecord.objects
            .filter(
                tenant_id=tenant_id,
                source_system="CONCUR",
                report_id=report_id,
                entry_id=entry_id,
            )
            .exists()
        )

        if exists:
            message = (
                f"Duplicate travel record detected: a record with "
                f"report_id={report_id!r} and entry_id={entry_id!r} already "
                f"exists for this tenant."
            )
            logger.info(message)
            return DataQualityFlagData(
                flag_type="potential_duplicate",
                severity="WARNING",
                message=message,
                field_name="report_id,entry_id",
            )
        return None
