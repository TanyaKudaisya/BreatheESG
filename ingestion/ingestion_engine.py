"""
Ingestion Engine for the Breathe ESG Data Ingestion System.

Orchestrates the full ingestion pipeline for all source systems:
  SAP:     Parse raw bytes with SAPParser
  Utility: Parse raw bytes with UtilityParser
  Travel:  Parse JSON payload with TravelParser

Each pipeline:
  1. Parses the source data into structured records
  2. Normalizes dates and units with NormalizationService
  3. Classifies scope with ScopeClassifier
  4. Validates records with ValidationService
  5. Detects duplicates with ValidationService
  6. Persists EmissionRecord and DataQualityFlag model instances

Requirements: 2.1 – 2.7, 3.1 – 3.6, 4.1 – 4.9, 7.1 – 7.4, 14.1, 17.x, 18.x, 19.1 – 19.3
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class IngestionError:
    """
    Describes a record-level error encountered during ingestion.

    Attributes:
        row_number: 1-based row number in the source file, or None for
                    file-level errors.
        message:    Human-readable description of the error.
    """

    row_number: Optional[int]
    message: str


@dataclass
class IngestionResult:
    """
    Summary of a completed ingestion run.

    Attributes:
        records_parsed:      Total rows successfully parsed from the file.
        records_with_errors: Rows that produced parse or ingestion errors.
        records_ingested:    Rows successfully persisted as EmissionRecords.
        errors:              List of :class:`IngestionError` objects.
    """

    records_parsed: int = 0
    records_with_errors: int = 0
    records_ingested: int = 0
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# IngestionEngine
# ---------------------------------------------------------------------------


class IngestionEngine:
    """
    Orchestrates the end-to-end SAP file ingestion pipeline.

    All service dependencies are instantiated lazily inside ``__init__``
    to keep import-time side-effects minimal and to allow easy substitution
    in tests.

    Requirements: 2.1 – 2.7, 7.1 – 7.4
    """

    def __init__(self):
        from normalization.services import NormalizationService
        from normalization.scope_classifier import ScopeClassifier
        from validation.services import ValidationService
        from ingestion.sap_parser import SAPParser
        from ingestion.plant_lookup import PlantLookupService
        from ingestion.airport_distance import AirportDistanceCalculator
        from ingestion.utility_parser import UtilityParser
        from ingestion.travel_parser import TravelParser

        self.normalizer = NormalizationService()
        self.classifier = ScopeClassifier()
        self.validator = ValidationService()
        self.sap_parser = SAPParser()
        self.plant_lookup = PlantLookupService()
        self.airport_calc = AirportDistanceCalculator()
        self.utility_parser = UtilityParser()
        self.travel_parser = TravelParser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_sap_file(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: str,
    ) -> IngestionResult:
        """
        Parse a SAP tab-separated file and persist the resulting emission
        records for the given tenant.

        Pipeline per row:
        a. Resolve plant with PlantLookupService
        b. Normalize date (DateParseError → skip row, add error)
        c. Normalize unit (UnknownUnitError → proceed, validation will flag)
        d. Classify scope with ScopeClassifier
        e. Validate with ValidationService
        f. Detect duplicate with ValidationService
        g. Create EmissionRecord (bypassing TenantManager)
        h. Create DataQualityFlag instances for each flag

        Args:
            file_content: Raw bytes of the uploaded SAP file.
            filename:     Original filename for source tracking.
            tenant_id:    UUID string of the owning tenant.

        Returns:
            :class:`IngestionResult` with counts and error details.

        Requirements: 2.1 – 2.7, 7.1 – 7.4
        """
        from normalization.exceptions import DateParseError, UnknownUnitError
        from emissions.models import EmissionRecord, DataQualityFlag, Tenant

        result = IngestionResult()

        # ------------------------------------------------------------------
        # Step 1: Parse the file
        # ------------------------------------------------------------------
        records, parse_errors = self.sap_parser.parse_file(file_content, filename)

        # Collect file-level / row-level parse errors.
        for pe in parse_errors:
            result.errors.append(IngestionError(row_number=pe.row_number, message=pe.message))
            result.records_with_errors += 1

        result.records_parsed = len(records)

        # Resolve the Tenant FK object once.
        try:
            tenant_obj = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            result.errors.append(
                IngestionError(
                    row_number=None,
                    message=f"Tenant with id '{tenant_id}' does not exist.",
                )
            )
            result.records_with_errors = len(records)
            return result

        # ------------------------------------------------------------------
        # Step 2: Process each parsed record
        # ------------------------------------------------------------------
        for record in records:
            try:
                self._process_sap_record(
                    record=record,
                    filename=filename,
                    tenant_id=tenant_id,
                    tenant_obj=tenant_obj,
                    result=result,
                    EmissionRecord=EmissionRecord,
                    DataQualityFlag=DataQualityFlag,
                    DateParseError=DateParseError,
                    UnknownUnitError=UnknownUnitError,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Unexpected error processing SAP record EBELN=%s EBELP=%s: %s",
                    record.ebeln,
                    record.ebelp,
                    exc,
                )
                result.errors.append(
                    IngestionError(
                        row_number=None,
                        message=f"Unexpected error for EBELN={record.ebeln} EBELP={record.ebelp}: {exc}",
                    )
                )
                result.records_with_errors += 1

        return result

    def ingest_utility_file(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: str,
    ) -> IngestionResult:
        """
        Parse a utility electricity CSV file and persist the resulting emission
        records for the given tenant.

        Pipeline per row:
        a. Normalize billing_period_start and billing_period_end dates
           (DateParseError → skip row, add error)
        b. Parse consumption_kwh as Decimal
        c. Allocate billing period with NormalizationService.allocate_billing_period()
        d. Classify scope as Scope 2 using ScopeClassifier
        e. Validate with ValidationService (checks ESTIMATED reading_type)
        f. Detect duplicate: (account_number, meter_id, billing_period_start)
        g. Create EmissionRecord with utility-specific fields
        h. Create MonthlyAllocation instances for each allocation
        i. Create DataQualityFlag instances for each flag

        Args:
            file_content: Raw bytes of the uploaded utility CSV file.
            filename:     Original filename for source tracking.
            tenant_id:    UUID string of the owning tenant.

        Returns:
            :class:`IngestionResult` with counts and error details.

        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 20.1, 20.2, 20.3
        """
        from normalization.exceptions import DateParseError
        from emissions.models import EmissionRecord, DataQualityFlag, MonthlyAllocation, Tenant

        result = IngestionResult()

        # ------------------------------------------------------------------
        # Step 1: Parse the file
        # ------------------------------------------------------------------
        records, parse_errors = self.utility_parser.parse_file(file_content, filename)

        for pe in parse_errors:
            result.errors.append(IngestionError(row_number=pe.row_number, message=pe.message))
            result.records_with_errors += 1

        result.records_parsed = len(records)

        # Resolve the Tenant FK object once.
        try:
            tenant_obj = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            result.errors.append(
                IngestionError(
                    row_number=None,
                    message=f"Tenant with id '{tenant_id}' does not exist.",
                )
            )
            result.records_with_errors = len(records)
            return result

        # ------------------------------------------------------------------
        # Step 2: Process each parsed record
        # ------------------------------------------------------------------
        for record in records:
            try:
                self._process_utility_record(
                    record=record,
                    filename=filename,
                    tenant_id=tenant_id,
                    tenant_obj=tenant_obj,
                    result=result,
                    EmissionRecord=EmissionRecord,
                    DataQualityFlag=DataQualityFlag,
                    MonthlyAllocation=MonthlyAllocation,
                    DateParseError=DateParseError,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Unexpected error processing utility record account=%s meter=%s: %s",
                    record.account_number,
                    record.meter_id,
                    exc,
                )
                result.errors.append(
                    IngestionError(
                        row_number=None,
                        message=(
                            f"Unexpected error for account={record.account_number} "
                            f"meter={record.meter_id}: {exc}"
                        ),
                    )
                )
                result.records_with_errors += 1

        return result

    def ingest_travel_json(
        self,
        payload: dict,
        tenant_id: str,
    ) -> IngestionResult:
        """
        Parse a Concur JSON payload and persist the resulting emission records
        for the given tenant.

        Pipeline per record:
        1. Normalize transaction_date (DateParseError → skip row)
        2. For AIRFARE with no distance_km: calculate with AirportDistanceCalculator
           (UnknownAirportError → create unknown_airport WARNING flag, leave distance_km null)
        3. Apply cabin class multiplier: BUSINESS → distance_km × 3.0
        4. Classify scope as Scope 3 Category 6 using ScopeClassifier
        5. Validate with ValidationService (receipt_attached, approval_status)
        6. Detect duplicates: (report_id, entry_id) with source "CONCUR"
        7. Create EmissionRecord with all travel-specific fields
        8. Create DataQualityFlag instances for each flag

        Args:
            payload:   Parsed Concur JSON dict.
            tenant_id: UUID string of the owning tenant.

        Returns:
            :class:`IngestionResult` with counts and error details.

        Requirements: 4.1 – 4.9, 7.1 – 7.4, 17.2, 17.3, 17.4, 17.5, 18.6
        """
        from normalization.exceptions import DateParseError
        from emissions.models import EmissionRecord, DataQualityFlag, Tenant

        result = IngestionResult()

        # ------------------------------------------------------------------
        # Step 1: Parse the JSON payload
        # ------------------------------------------------------------------
        records, parse_errors = self.travel_parser.parse_json(payload)

        for pe in parse_errors:
            result.errors.append(IngestionError(row_number=pe.row_number, message=pe.message))
            result.records_with_errors += 1

        result.records_parsed = len(records)

        # Resolve the Tenant FK object once.
        try:
            tenant_obj = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            result.errors.append(
                IngestionError(
                    row_number=None,
                    message=f"Tenant with id '{tenant_id}' does not exist.",
                )
            )
            result.records_with_errors = len(records)
            return result

        # ------------------------------------------------------------------
        # Step 2: Process each parsed record
        # ------------------------------------------------------------------
        for record in records:
            try:
                self._process_travel_record(
                    record=record,
                    tenant_id=tenant_id,
                    tenant_obj=tenant_obj,
                    result=result,
                    EmissionRecord=EmissionRecord,
                    DataQualityFlag=DataQualityFlag,
                    DateParseError=DateParseError,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Unexpected error processing travel record report=%s entry=%s: %s",
                    record.report_id,
                    record.entry_id,
                    exc,
                )
                result.errors.append(
                    IngestionError(
                        row_number=None,
                        message=(
                            f"Unexpected error for report_id={record.report_id} "
                            f"entry_id={record.entry_id}: {exc}"
                        ),
                    )
                )
                result.records_with_errors += 1

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_utility_record(
        self,
        record,
        filename: str,
        tenant_id: str,
        tenant_obj,
        result: IngestionResult,
        EmissionRecord,
        DataQualityFlag,
        MonthlyAllocation,
        DateParseError,
    ) -> None:
        """
        Process a single :class:`UtilityRecord` through the full pipeline and
        persist the resulting :class:`EmissionRecord` with monthly allocations.

        Modifies ``result`` in-place.
        """
        flags_to_create = []

        # ------------------------------------------------------------------
        # a. Normalize dates
        # ------------------------------------------------------------------
        try:
            period_start = self.normalizer.normalize_date(record.billing_period_start)
        except DateParseError as exc:
            result.errors.append(
                IngestionError(
                    row_number=None,
                    message=(
                        f"account={record.account_number} meter={record.meter_id}: "
                        f"date parse error for billing_period_start="
                        f"'{record.billing_period_start}': {exc}"
                    ),
                )
            )
            result.records_with_errors += 1
            return

        try:
            period_end = self.normalizer.normalize_date(record.billing_period_end)
        except DateParseError as exc:
            result.errors.append(
                IngestionError(
                    row_number=None,
                    message=(
                        f"account={record.account_number} meter={record.meter_id}: "
                        f"date parse error for billing_period_end="
                        f"'{record.billing_period_end}': {exc}"
                    ),
                )
            )
            result.records_with_errors += 1
            return

        # ------------------------------------------------------------------
        # b. Parse consumption_kwh as Decimal
        # ------------------------------------------------------------------
        try:
            consumption_kwh = Decimal(record.consumption_kwh)
        except InvalidOperation:
            result.errors.append(
                IngestionError(
                    row_number=None,
                    message=(
                        f"account={record.account_number} meter={record.meter_id}: "
                        f"invalid consumption_kwh='{record.consumption_kwh}'"
                    ),
                )
            )
            result.records_with_errors += 1
            return

        # ------------------------------------------------------------------
        # c. Allocate billing period
        # ------------------------------------------------------------------
        allocations = self.normalizer.allocate_billing_period(
            consumption_kwh=consumption_kwh,
            period_start=period_start,
            period_end=period_end,
        )

        # ------------------------------------------------------------------
        # d. Classify scope (always Scope 2 for utility)
        # ------------------------------------------------------------------
        scope_classification = self.classifier.classify_scope("UTILITY")

        # ------------------------------------------------------------------
        # e. Validate record
        # ------------------------------------------------------------------
        validation_flags = self.validator.validate_emission_record(
            {"reading_type": record.reading_type},
            "UTILITY",
        )
        flags_to_create.extend(validation_flags)

        # ------------------------------------------------------------------
        # f. Detect duplicate
        # ------------------------------------------------------------------
        duplicate_flag = self.validator.detect_duplicate(
            {
                "account_number": record.account_number,
                "meter_id": record.meter_id,
                "billing_period_start": period_start,
            },
            "UTILITY",
            tenant_id,
        )
        if duplicate_flag is not None:
            flags_to_create.append(duplicate_flag)

        # ------------------------------------------------------------------
        # g. Parse demand_kw (optional)
        # ------------------------------------------------------------------
        demand_kw_decimal: Optional[Decimal] = None
        if record.demand_kw.strip():
            try:
                demand_kw_decimal = Decimal(record.demand_kw)
            except InvalidOperation:
                demand_kw_decimal = None

        # ------------------------------------------------------------------
        # h. Persist EmissionRecord
        # ------------------------------------------------------------------
        emission_record = EmissionRecord._default_manager.create(
            tenant=tenant_obj,
            source_system="UTILITY",
            original_filename=filename,
            raw_data=record.raw_row,
            transaction_date=period_start,
            location=record.service_address,
            # Utility-specific fields
            account_number=record.account_number,
            meter_id=record.meter_id,
            service_address=record.service_address,
            billing_period_start=period_start,
            billing_period_end=period_end,
            consumption_kwh=consumption_kwh,
            reading_type=record.reading_type,
            tariff_code=record.tariff_code,
            demand_kw=demand_kw_decimal,
            # Scope
            scope=scope_classification.scope,
            scope_category=scope_classification.category,
        )

        # ------------------------------------------------------------------
        # i. Persist MonthlyAllocation instances
        # ------------------------------------------------------------------
        for alloc in allocations:
            MonthlyAllocation.objects.create(
                emission_record=emission_record,
                year=alloc.year,
                month=alloc.month,
                allocated_quantity=alloc.allocated_quantity,
                unit=alloc.unit,
            )

        # ------------------------------------------------------------------
        # j. Persist DataQualityFlag instances
        # ------------------------------------------------------------------
        for flag_data in flags_to_create:
            DataQualityFlag.objects.create(
                emission_record=emission_record,
                flag_type=flag_data.flag_type,
                severity=flag_data.severity,
                message=flag_data.message,
                field_name=flag_data.field_name or "",
            )

        result.records_ingested += 1
        logger.debug(
            "Ingested utility record account=%s meter=%s → EmissionRecord %s",
            record.account_number,
            record.meter_id,
            emission_record.id,
        )

    def _process_sap_record(
        self,
        record,
        filename: str,
        tenant_id: str,
        tenant_obj,
        result: IngestionResult,
        EmissionRecord,
        DataQualityFlag,
        DateParseError,
        UnknownUnitError,
    ) -> None:
        """
        Process a single :class:`SAPRecord` through the full pipeline and
        persist the resulting :class:`EmissionRecord`.

        Modifies ``result`` in-place.
        """
        flags_to_create = []  # list of DataQualityFlagData

        # ------------------------------------------------------------------
        # a. Resolve plant
        # ------------------------------------------------------------------
        plant_details, plant_flag = self.plant_lookup.resolve_plant(record.werks)
        if plant_flag is not None:
            flags_to_create.append(plant_flag)

        # ------------------------------------------------------------------
        # b. Normalize date
        # ------------------------------------------------------------------
        try:
            transaction_date = self.normalizer.normalize_date(record.bedat)
        except DateParseError as exc:
            result.errors.append(
                IngestionError(
                    row_number=None,
                    message=(
                        f"EBELN={record.ebeln} EBELP={record.ebelp}: "
                        f"date parse error for BEDAT='{record.bedat}': {exc}"
                    ),
                )
            )
            result.records_with_errors += 1
            return  # Skip this record

        # ------------------------------------------------------------------
        # c. Normalize unit (UnknownUnitError → proceed; validation will flag)
        # ------------------------------------------------------------------
        normalized_qty = None
        if record.menge.strip():
            try:
                menge_decimal = Decimal(record.menge)
                normalized_qty = self.normalizer.normalize_unit(menge_decimal, record.meins)
            except (UnknownUnitError, InvalidOperation):
                # Proceed without normalized quantity; validation will flag it.
                normalized_qty = None

        # ------------------------------------------------------------------
        # d. Classify scope
        # ------------------------------------------------------------------
        scope_classification = self.classifier.classify_scope("SAP", record.txz01)

        # ------------------------------------------------------------------
        # e. Validate record
        # ------------------------------------------------------------------
        validation_flags = self.validator.validate_emission_record(
            {
                "menge": record.menge,
                "netpr": record.netpr,
                "meins": record.meins,
            },
            "SAP",
        )
        flags_to_create.extend(validation_flags)

        # ------------------------------------------------------------------
        # f. Detect duplicate
        # ------------------------------------------------------------------
        duplicate_flag = self.validator.detect_duplicate(
            {"ebeln": record.ebeln, "ebelp": record.ebelp},
            "SAP",
            tenant_id,
        )
        if duplicate_flag is not None:
            flags_to_create.append(duplicate_flag)

        # ------------------------------------------------------------------
        # g. Build EmissionRecord field values
        # ------------------------------------------------------------------
        original_quantity: Optional[Decimal] = None
        original_unit: str = record.meins
        norm_quantity: Optional[Decimal] = None
        norm_unit: str = ""

        if normalized_qty is not None:
            original_quantity = normalized_qty.original_quantity
            original_unit = normalized_qty.original_unit
            norm_quantity = normalized_qty.normalized_quantity
            norm_unit = normalized_qty.normalized_unit
        elif record.menge.strip():
            # Quantity present but unit unknown — store raw quantity, no normalized unit.
            try:
                original_quantity = Decimal(record.menge)
            except InvalidOperation:
                original_quantity = None

        netpr_decimal: Optional[Decimal] = None
        try:
            netpr_decimal = Decimal(record.netpr)
        except InvalidOperation:
            pass

        # ------------------------------------------------------------------
        # h. Persist EmissionRecord (bypass TenantManager with _default_manager)
        # ------------------------------------------------------------------
        emission_record = EmissionRecord._default_manager.create(
            tenant=tenant_obj,
            source_system="SAP",
            original_filename=filename,
            raw_data=record.raw_row,
            transaction_date=transaction_date,
            location=plant_details.location,
            fuel_type=record.txz01,
            original_quantity=original_quantity,
            original_unit=original_unit,
            normalized_quantity=norm_quantity,
            normalized_unit=norm_unit,
            scope=scope_classification.scope,
            scope_category=scope_classification.category,
            # SAP-specific fields
            ebeln=record.ebeln,
            ebelp=record.ebelp,
            bedat=transaction_date,
            werks=record.werks,
            plant_name=plant_details.plant_name,
            plant_location=plant_details.location,
            plant_state=plant_details.state,
            plant_country=plant_details.country,
            matnr=record.matnr,
            material_description=record.txz01,
            netpr=netpr_decimal,
            currency=record.waers,
        )

        # ------------------------------------------------------------------
        # i. Persist DataQualityFlag instances
        # ------------------------------------------------------------------
        for flag_data in flags_to_create:
            DataQualityFlag.objects.create(
                emission_record=emission_record,
                flag_type=flag_data.flag_type,
                severity=flag_data.severity,
                message=flag_data.message,
                field_name=flag_data.field_name or "",
            )

        result.records_ingested += 1
        logger.debug(
            "Ingested SAP record EBELN=%s EBELP=%s → EmissionRecord %s",
            record.ebeln,
            record.ebelp,
            emission_record.id,
        )

    def _process_travel_record(
        self,
        record,
        tenant_id: str,
        tenant_obj,
        result: IngestionResult,
        EmissionRecord,
        DataQualityFlag,
        DateParseError,
    ) -> None:
        """
        Process a single :class:`TravelRecord` through the full pipeline and
        persist the resulting :class:`EmissionRecord`.

        Pipeline:
        1. Normalize transaction_date (DateParseError → skip row)
        2. For AIRFARE with no distance_km: calculate with AirportDistanceCalculator
           (UnknownAirportError → unknown_airport WARNING flag, distance_km stays null)
        3. Apply cabin class multiplier: BUSINESS → effective_distance_km = distance_km × 3.0
        4. Classify scope as Scope 3 Category 6
        5. Validate (receipt_attached, approval_status)
        6. Detect duplicate (report_id, entry_id)
        7. Persist EmissionRecord
        8. Persist DataQualityFlag instances

        Modifies ``result`` in-place.

        Requirements: 4.1 – 4.9, 17.2, 17.3, 17.4, 17.5, 18.6
        """
        from ingestion.airport_distance import UnknownAirportError
        from decimal import Decimal

        flags_to_create = []

        # ------------------------------------------------------------------
        # 1. Normalize transaction_date
        # ------------------------------------------------------------------
        try:
            transaction_date = self.normalizer.normalize_date(record.transaction_date)
        except DateParseError as exc:
            result.errors.append(
                IngestionError(
                    row_number=None,
                    message=(
                        f"report_id={record.report_id} entry_id={record.entry_id}: "
                        f"date parse error for transaction_date="
                        f"'{record.transaction_date}': {exc}"
                    ),
                )
            )
            result.records_with_errors += 1
            return

        # ------------------------------------------------------------------
        # 2. Distance calculation for AIRFARE with no distance_km
        # ------------------------------------------------------------------
        distance_km: Optional[Decimal] = None
        if record.distance_km is not None:
            distance_km = Decimal(str(record.distance_km))

        if record.expense_type == "AIRFARE" and distance_km is None:
            if record.origin_airport and record.destination_airport:
                try:
                    via = record.via_airport if record.via_airport else None
                    dist_result = self.airport_calc.calculate_distance(
                        origin_airport=record.origin_airport,
                        destination_airport=record.destination_airport,
                        via_airport=via,
                    )
                    distance_km = dist_result.distance_km
                except UnknownAirportError as exc:
                    flags_to_create.append(
                        _make_unknown_airport_flag(str(exc))
                    )
                    distance_km = None

        # ------------------------------------------------------------------
        # 3. Apply cabin class multiplier (BUSINESS = 3.0x)
        # ------------------------------------------------------------------
        effective_distance_km: Optional[Decimal] = None
        if distance_km is not None:
            if record.cabin_class == "BUSINESS":
                effective_distance_km = distance_km * Decimal("3.0")
            else:
                effective_distance_km = distance_km

        # ------------------------------------------------------------------
        # 4. Classify scope (always Scope 3 Category 6 for CONCUR)
        # ------------------------------------------------------------------
        scope_classification = self.classifier.classify_scope("CONCUR")

        # ------------------------------------------------------------------
        # 5. Validate record
        # ------------------------------------------------------------------
        validation_flags = self.validator.validate_emission_record(
            {
                "receipt_attached": record.receipt_attached,
                "approval_status": record.approval_status,
            },
            "CONCUR",
        )
        flags_to_create.extend(validation_flags)

        # ------------------------------------------------------------------
        # 6. Detect duplicate
        # ------------------------------------------------------------------
        duplicate_flag = self.validator.detect_duplicate(
            {
                "report_id": record.report_id,
                "entry_id": record.entry_id,
            },
            "CONCUR",
            tenant_id,
        )
        if duplicate_flag is not None:
            flags_to_create.append(duplicate_flag)

        # ------------------------------------------------------------------
        # 7. Normalize hotel check_in / check_out dates (optional)
        # ------------------------------------------------------------------
        check_in_date = None
        check_out_date = None
        if record.check_in:
            try:
                check_in_date = self.normalizer.normalize_date(record.check_in)
            except DateParseError:
                check_in_date = None
        if record.check_out:
            try:
                check_out_date = self.normalizer.normalize_date(record.check_out)
            except DateParseError:
                check_out_date = None

        # ------------------------------------------------------------------
        # 8. Persist EmissionRecord
        # ------------------------------------------------------------------
        emission_record = EmissionRecord._default_manager.create(
            tenant=tenant_obj,
            source_system="CONCUR",
            original_filename="",
            raw_data=record.raw_entry,
            transaction_date=transaction_date,
            # Scope
            scope=scope_classification.scope,
            scope_category=scope_classification.category,
            # Travel-specific fields
            report_id=record.report_id,
            entry_id=record.entry_id,
            expense_type=record.expense_type,
            employee_id=record.employee_id,
            employee_name=record.employee_name,
            department=record.department,
            travel_approval_status=record.approval_status,
            receipt_attached=record.receipt_attached,
            origin_airport=record.origin_airport,
            destination_airport=record.destination_airport,
            via_airport=record.via_airport,
            cabin_class=record.cabin_class,
            # Store the effective (cabin-class-adjusted) distance
            distance_km=effective_distance_km,
            hotel_city=record.city,
            hotel_country=record.country,
            check_in=check_in_date,
            check_out=check_out_date,
            nights=record.nights,
            ground_fuel_type=record.fuel_type,
        )

        # ------------------------------------------------------------------
        # 9. Persist DataQualityFlag instances
        # ------------------------------------------------------------------
        for flag_data in flags_to_create:
            DataQualityFlag.objects.create(
                emission_record=emission_record,
                flag_type=flag_data.flag_type,
                severity=flag_data.severity,
                message=flag_data.message,
                field_name=flag_data.field_name or "",
            )

        result.records_ingested += 1
        logger.debug(
            "Ingested travel record report=%s entry=%s → EmissionRecord %s",
            record.report_id,
            record.entry_id,
            emission_record.id,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _make_unknown_airport_flag(message: str):
    """Return a DataQualityFlagData for an unknown airport code."""
    from validation.services import DataQualityFlagData
    return DataQualityFlagData(
        flag_type="unknown_airport",
        severity="WARNING",
        message=message,
        field_name="origin_airport,destination_airport",
    )
