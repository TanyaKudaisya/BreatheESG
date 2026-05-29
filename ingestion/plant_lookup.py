"""
Plant Lookup Service for the Breathe ESG Data Ingestion System.

Resolves SAP plant codes (WERKS) to human-readable location details using
a reference CSV file.  When a plant code is not found, a fallback
PlantDetails object is returned alongside a DataQualityFlagData warning.

Requirements: 2.3
"""

from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class PlantDetails:
    """
    Location details for a SAP plant code.

    Attributes:
        werks:       The SAP plant code (e.g. "WRK1").
        plant_name:  Human-readable plant name.
        location:    City or site name.
        state:       State or province.
        country:     Country code or name.
    """

    werks: str
    plant_name: str
    location: str
    state: str
    country: str


# ---------------------------------------------------------------------------
# PlantLookupService
# ---------------------------------------------------------------------------


class PlantLookupService:
    """
    Resolves SAP WERKS plant codes to :class:`PlantDetails` using a CSV
    reference file.

    The CSV file is expected to have the following columns (case-insensitive):
    ``WERKS``, ``PLANT_NAME``, ``LOCATION``, ``STATE``, ``COUNTRY``.

    Usage::

        service = PlantLookupService()
        details, flag = service.resolve_plant("WRK1")

    Requirements: 2.3
    """

    def __init__(self, csv_path: str = None):
        """
        Initialise the service and load the plant lookup table.

        Args:
            csv_path: Absolute path to the plant lookup CSV file.
                      Defaults to ``<project_root>/sample_data/sap_plant_lookup.csv``.
        """
        if csv_path is None:
            # Resolve relative to this file: ingestion/ → project root → sample_data/
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            csv_path = os.path.join(base_dir, "sample_data", "sap_plant_lookup.csv")

        self._csv_path = csv_path
        self._lookup: dict[str, PlantDetails] = self._load_csv(csv_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_plant(
        self, werks: str
    ) -> tuple[PlantDetails, Optional[object]]:
        """
        Resolve a SAP plant code to :class:`PlantDetails`.

        If the plant code is found in the lookup table, returns
        ``(PlantDetails, None)``.

        If the plant code is **not** found, returns a fallback
        :class:`PlantDetails` (where all location fields are set to the
        WERKS code itself) together with a :class:`DataQualityFlagData`
        warning of type ``"unknown_unit"`` (re-used per task specification)
        with message "Plant code <WERKS> not found in lookup table".

        Args:
            werks: The SAP plant code to resolve (case-insensitive lookup).

        Returns:
            A tuple ``(plant_details, flag_or_none)``.

        Requirements: 2.3
        """
        # Import here to avoid circular imports at module load time.
        from validation.services import DataQualityFlagData

        normalised = werks.strip().upper()
        details = self._lookup.get(normalised)

        if details is not None:
            return details, None

        # Plant code not found — return fallback + warning flag.
        logger.warning(
            "PlantLookupService: WERKS '%s' not found in lookup table '%s'.",
            werks,
            self._csv_path,
        )
        fallback = PlantDetails(
            werks=werks,
            plant_name=werks,
            location=werks,
            state="",
            country="",
        )
        flag = DataQualityFlagData(
            flag_type="unknown_unit",
            severity="WARNING",
            message=f"Plant code {werks} not found in lookup table",
            field_name="werks",
        )
        return fallback, flag

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_csv(self, csv_path: str) -> dict[str, PlantDetails]:
        """
        Load the plant lookup CSV into an in-memory dictionary.

        The dictionary is keyed by upper-cased WERKS code for
        case-insensitive lookups.

        Args:
            csv_path: Path to the CSV file.

        Returns:
            Dictionary mapping upper-cased WERKS → :class:`PlantDetails`.
        """
        lookup: dict[str, PlantDetails] = {}

        if not os.path.exists(csv_path):
            logger.warning(
                "PlantLookupService: CSV file not found at '%s'. "
                "All plant lookups will return fallback values.",
                csv_path,
            )
            return lookup

        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            # Normalise header names to upper-case for case-insensitive access.
            for row in reader:
                normalised_row = {k.strip().upper(): v.strip() for k, v in row.items()}
                werks_key = normalised_row.get("WERKS", "").upper()
                if not werks_key:
                    continue
                lookup[werks_key] = PlantDetails(
                    werks=normalised_row.get("WERKS", ""),
                    plant_name=normalised_row.get("PLANT_NAME", ""),
                    location=normalised_row.get("LOCATION", ""),
                    state=normalised_row.get("STATE", ""),
                    country=normalised_row.get("COUNTRY", ""),
                )

        logger.debug(
            "PlantLookupService: loaded %d plant entries from '%s'.",
            len(lookup),
            csv_path,
        )
        return lookup
