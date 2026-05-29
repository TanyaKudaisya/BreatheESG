"""
Scope classifier for the Breathe ESG Data Ingestion System.

Categorizes emission records into GHG Protocol Scope 1, 2, or 3 categories
based on source system and material description.

Requirements: 2.6, 2.7, 3.5, 4.2, 4.3, 4.4, 14.1, 14.2, 14.3
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Source system constants
# ---------------------------------------------------------------------------

SOURCE_SAP = "SAP"
SOURCE_UTILITY = "UTILITY"
SOURCE_CONCUR = "CONCUR"

# ---------------------------------------------------------------------------
# SAP material keyword sets
# ---------------------------------------------------------------------------

# Materials containing any of these keywords (case-insensitive) are Scope 1.
# Requirements: 2.6, 14.1
_SCOPE_1_KEYWORDS = frozenset(
    ["diesel", "petrol", "png", "furnace oil", "lpg", "coal"]
)

# Materials containing this keyword (case-insensitive) are excluded entirely.
# Requirement: 2.7
_EXCLUDED_KEYWORD = "lubricating oil"


# ---------------------------------------------------------------------------
# ScopeClassification dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScopeClassification:
    """
    Result of a scope classification decision.

    Attributes:
        scope: GHG Protocol scope number (1, 2, or 3), or None if excluded.
        category: Scope 3 category number (e.g. 6 for Business Travel), or None.
        justification: Human-readable explanation of the classification decision.
        is_excluded: True when the record should be excluded from emission
            calculations (e.g. lubricating oil).
        is_manual_override: True when an analyst has manually overridden the
            automatic classification.
    """

    scope: Optional[int]
    category: Optional[int]
    justification: str
    is_excluded: bool = False
    is_manual_override: bool = False


# ---------------------------------------------------------------------------
# ScopeClassifier
# ---------------------------------------------------------------------------


class ScopeClassifier:
    """
    Rule-based classifier that assigns GHG Protocol scope categories to
    emission records based on their source system and material description.

    Classification rules (in priority order):
    1. SAP + material contains "lubricating oil"  → excluded (is_excluded=True)
    2. SAP + material contains any Scope 1 keyword → Scope 1
    3. UTILITY                                     → Scope 2
    4. CONCUR                                      → Scope 3, Category 6
    """

    def classify_scope(
        self,
        source_system: str,
        material_description: Optional[str] = None,
    ) -> ScopeClassification:
        """
        Classify an emission record into a GHG Protocol scope.

        Args:
            source_system: The originating system — one of "SAP", "UTILITY",
                or "CONCUR".
            material_description: The SAP TXZ01 material description text.
                Only relevant when source_system is "SAP".  Case-insensitive
                keyword matching is applied.

        Returns:
            A :class:`ScopeClassification` dataclass describing the scope,
            optional category, justification, and exclusion/override flags.

        Raises:
            ValueError: If source_system is not one of the recognised values
                and no classification rule applies.
        """
        normalised_source = source_system.strip().upper()

        if normalised_source == SOURCE_SAP:
            return self._classify_sap(material_description)

        if normalised_source == SOURCE_UTILITY:
            return ScopeClassification(
                scope=2,
                category=None,
                justification=(
                    "Utility electricity records are classified as Scope 2 "
                    "(purchased energy) per GHG Protocol."
                ),
            )

        if normalised_source == SOURCE_CONCUR:
            return ScopeClassification(
                scope=3,
                category=6,
                justification=(
                    "Corporate travel expense records are classified as "
                    "Scope 3 Category 6 (Business Travel) per GHG Protocol."
                ),
            )

        raise ValueError(
            f"Unrecognised source_system '{source_system}'. "
            f"Expected one of: {SOURCE_SAP}, {SOURCE_UTILITY}, {SOURCE_CONCUR}."
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify_sap(
        self, material_description: Optional[str]
    ) -> ScopeClassification:
        """Apply SAP-specific classification rules."""
        desc_lower = (material_description or "").lower()

        # Exclusion check takes priority over Scope 1 assignment.
        if _EXCLUDED_KEYWORD in desc_lower:
            return ScopeClassification(
                scope=None,
                category=None,
                justification=(
                    f"Material description contains '{_EXCLUDED_KEYWORD}'; "
                    "excluded from emission calculations per business rules."
                ),
                is_excluded=True,
            )

        # Check for Scope 1 fuel keywords.
        for keyword in _SCOPE_1_KEYWORDS:
            if keyword in desc_lower:
                return ScopeClassification(
                    scope=1,
                    category=None,
                    justification=(
                        f"SAP material description contains '{keyword}'; "
                        "classified as Scope 1 (stationary/mobile combustion) "
                        "per GHG Protocol."
                    ),
                )

        # SAP material with no recognised fuel keyword — cannot auto-classify.
        return ScopeClassification(
            scope=None,
            category=None,
            justification=(
                "SAP material description does not match any known Scope 1 "
                "fuel keyword. Manual review required."
            ),
        )
