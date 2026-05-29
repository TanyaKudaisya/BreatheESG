"""
Tests for normalization.scope_classifier.ScopeClassifier.

Covers:
- SAP Scope 1 classification for all six fuel keywords
- SAP lubricating oil exclusion
- Case-insensitive keyword matching
- Utility Scope 2 classification
- Concur Scope 3 Category 6 classification
- ScopeClassification dataclass field defaults
- Unrecognised source system raises ValueError
"""

import pytest

from normalization.scope_classifier import (
    ScopeClassification,
    ScopeClassifier,
)


@pytest.fixture
def classifier():
    return ScopeClassifier()


# ---------------------------------------------------------------------------
# ScopeClassification dataclass
# ---------------------------------------------------------------------------


class TestScopeClassificationDataclass:
    """ScopeClassification has the expected fields and defaults."""

    def test_fields_present(self):
        sc = ScopeClassification(scope=1, category=None, justification="test")
        assert sc.scope == 1
        assert sc.category is None
        assert sc.justification == "test"
        assert sc.is_excluded is False
        assert sc.is_manual_override is False

    def test_is_excluded_default_false(self):
        sc = ScopeClassification(scope=2, category=None, justification="x")
        assert sc.is_excluded is False

    def test_is_manual_override_default_false(self):
        sc = ScopeClassification(scope=3, category=6, justification="x")
        assert sc.is_manual_override is False

    def test_can_set_is_excluded_true(self):
        sc = ScopeClassification(
            scope=None, category=None, justification="excluded", is_excluded=True
        )
        assert sc.is_excluded is True

    def test_can_set_is_manual_override_true(self):
        sc = ScopeClassification(
            scope=1, category=None, justification="override", is_manual_override=True
        )
        assert sc.is_manual_override is True


# ---------------------------------------------------------------------------
# SAP — Scope 1 fuel keywords
# ---------------------------------------------------------------------------


class TestSAPScope1Classification:
    """SAP records with recognised fuel keywords are classified as Scope 1."""

    def test_diesel_is_scope_1(self, classifier):
        result = classifier.classify_scope("SAP", "Diesel HSD 50 ppm")
        assert result.scope == 1

    def test_petrol_is_scope_1(self, classifier):
        result = classifier.classify_scope("SAP", "Petrol unleaded 95 RON")
        assert result.scope == 1

    def test_png_is_scope_1(self, classifier):
        result = classifier.classify_scope("SAP", "PNG piped natural gas")
        assert result.scope == 1

    def test_furnace_oil_is_scope_1(self, classifier):
        result = classifier.classify_scope("SAP", "Furnace Oil Grade A")
        assert result.scope == 1

    def test_lpg_is_scope_1(self, classifier):
        result = classifier.classify_scope("SAP", "LPG cylinder 14.2 kg")
        assert result.scope == 1

    def test_coal_is_scope_1(self, classifier):
        result = classifier.classify_scope("SAP", "Coal bituminous grade B")
        assert result.scope == 1

    def test_scope_1_category_is_none(self, classifier):
        result = classifier.classify_scope("SAP", "Diesel")
        assert result.category is None

    def test_scope_1_is_not_excluded(self, classifier):
        result = classifier.classify_scope("SAP", "Diesel")
        assert result.is_excluded is False

    def test_scope_1_justification_is_non_empty(self, classifier):
        result = classifier.classify_scope("SAP", "LPG")
        assert len(result.justification) > 0


# ---------------------------------------------------------------------------
# SAP — lubricating oil exclusion
# ---------------------------------------------------------------------------


class TestSAPLubricatingOilExclusion:
    """SAP records with 'lubricating oil' in the description are excluded."""

    def test_lubricating_oil_is_excluded(self, classifier):
        result = classifier.classify_scope("SAP", "Lubricating Oil SAE 40")
        assert result.is_excluded is True

    def test_lubricating_oil_scope_is_none(self, classifier):
        result = classifier.classify_scope("SAP", "Lubricating Oil SAE 40")
        assert result.scope is None

    def test_lubricating_oil_category_is_none(self, classifier):
        result = classifier.classify_scope("SAP", "Lubricating Oil SAE 40")
        assert result.category is None

    def test_lubricating_oil_justification_is_non_empty(self, classifier):
        result = classifier.classify_scope("SAP", "Lubricating Oil SAE 40")
        assert len(result.justification) > 0

    def test_lubricating_oil_takes_priority_over_scope_1_keywords(self, classifier):
        """
        A description containing both 'lubricating oil' and a Scope 1 keyword
        should be excluded, not classified as Scope 1.
        """
        result = classifier.classify_scope(
            "SAP", "Lubricating Oil with diesel additive"
        )
        assert result.is_excluded is True
        assert result.scope is None


# ---------------------------------------------------------------------------
# SAP — case-insensitive matching
# ---------------------------------------------------------------------------


class TestSAPCaseInsensitiveMatching:
    """Keyword matching is case-insensitive for both fuel and exclusion keywords."""

    def test_diesel_uppercase(self, classifier):
        result = classifier.classify_scope("SAP", "DIESEL HSD")
        assert result.scope == 1

    def test_diesel_mixed_case(self, classifier):
        result = classifier.classify_scope("SAP", "DiEsEl")
        assert result.scope == 1

    def test_lpg_lowercase(self, classifier):
        result = classifier.classify_scope("SAP", "lpg cylinder")
        assert result.scope == 1

    def test_coal_uppercase(self, classifier):
        result = classifier.classify_scope("SAP", "COAL BITUMINOUS")
        assert result.scope == 1

    def test_furnace_oil_uppercase(self, classifier):
        result = classifier.classify_scope("SAP", "FURNACE OIL GRADE A")
        assert result.scope == 1

    def test_lubricating_oil_uppercase_excluded(self, classifier):
        result = classifier.classify_scope("SAP", "LUBRICATING OIL SAE 40")
        assert result.is_excluded is True

    def test_lubricating_oil_mixed_case_excluded(self, classifier):
        result = classifier.classify_scope("SAP", "Lubricating Oil")
        assert result.is_excluded is True

    def test_png_uppercase(self, classifier):
        result = classifier.classify_scope("SAP", "PNG NATURAL GAS")
        assert result.scope == 1

    def test_petrol_uppercase(self, classifier):
        result = classifier.classify_scope("SAP", "PETROL UNLEADED")
        assert result.scope == 1


# ---------------------------------------------------------------------------
# SAP — no matching keyword
# ---------------------------------------------------------------------------


class TestSAPNoMatchingKeyword:
    """SAP records with no recognised keyword return scope=None (manual review)."""

    def test_unknown_material_scope_is_none(self, classifier):
        result = classifier.classify_scope("SAP", "Office Stationery")
        assert result.scope is None

    def test_unknown_material_is_not_excluded(self, classifier):
        result = classifier.classify_scope("SAP", "Office Stationery")
        assert result.is_excluded is False

    def test_none_description_scope_is_none(self, classifier):
        result = classifier.classify_scope("SAP", None)
        assert result.scope is None

    def test_empty_description_scope_is_none(self, classifier):
        result = classifier.classify_scope("SAP", "")
        assert result.scope is None


# ---------------------------------------------------------------------------
# Utility — Scope 2
# ---------------------------------------------------------------------------


class TestUtilityScope2Classification:
    """All UTILITY records are classified as Scope 2."""

    def test_utility_is_scope_2(self, classifier):
        result = classifier.classify_scope("UTILITY")
        assert result.scope == 2

    def test_utility_category_is_none(self, classifier):
        result = classifier.classify_scope("UTILITY")
        assert result.category is None

    def test_utility_is_not_excluded(self, classifier):
        result = classifier.classify_scope("UTILITY")
        assert result.is_excluded is False

    def test_utility_justification_is_non_empty(self, classifier):
        result = classifier.classify_scope("UTILITY")
        assert len(result.justification) > 0

    def test_utility_material_description_ignored(self, classifier):
        """material_description is irrelevant for UTILITY records."""
        result = classifier.classify_scope("UTILITY", "some description")
        assert result.scope == 2


# ---------------------------------------------------------------------------
# Concur — Scope 3 Category 6
# ---------------------------------------------------------------------------


class TestConcurScope3Classification:
    """All CONCUR records are classified as Scope 3 Category 6."""

    def test_concur_is_scope_3(self, classifier):
        result = classifier.classify_scope("CONCUR")
        assert result.scope == 3

    def test_concur_category_is_6(self, classifier):
        result = classifier.classify_scope("CONCUR")
        assert result.category == 6

    def test_concur_is_not_excluded(self, classifier):
        result = classifier.classify_scope("CONCUR")
        assert result.is_excluded is False

    def test_concur_justification_is_non_empty(self, classifier):
        result = classifier.classify_scope("CONCUR")
        assert len(result.justification) > 0

    def test_concur_material_description_ignored(self, classifier):
        """material_description is irrelevant for CONCUR records."""
        result = classifier.classify_scope("CONCUR", "AIRFARE")
        assert result.scope == 3
        assert result.category == 6


# ---------------------------------------------------------------------------
# Source system case-insensitivity
# ---------------------------------------------------------------------------


class TestSourceSystemCaseHandling:
    """source_system argument is normalised to uppercase before matching."""

    def test_lowercase_utility(self, classifier):
        result = classifier.classify_scope("utility")
        assert result.scope == 2

    def test_lowercase_concur(self, classifier):
        result = classifier.classify_scope("concur")
        assert result.scope == 3

    def test_lowercase_sap(self, classifier):
        result = classifier.classify_scope("sap", "diesel")
        assert result.scope == 1

    def test_mixed_case_sap(self, classifier):
        result = classifier.classify_scope("Sap", "LPG")
        assert result.scope == 1


# ---------------------------------------------------------------------------
# Unrecognised source system
# ---------------------------------------------------------------------------


class TestUnrecognisedSourceSystem:
    """An unrecognised source_system raises ValueError."""

    def test_raises_for_unknown_source(self, classifier):
        with pytest.raises(ValueError):
            classifier.classify_scope("UNKNOWN_SYSTEM")

    def test_raises_for_empty_source(self, classifier):
        with pytest.raises(ValueError):
            classifier.classify_scope("")

    def test_error_message_contains_source(self, classifier):
        bad_source = "ORACLE"
        with pytest.raises(ValueError, match=bad_source):
            classifier.classify_scope(bad_source)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


class TestReturnType:
    """classify_scope() always returns a ScopeClassification instance."""

    def test_returns_scope_classification_for_sap(self, classifier):
        result = classifier.classify_scope("SAP", "diesel")
        assert isinstance(result, ScopeClassification)

    def test_returns_scope_classification_for_utility(self, classifier):
        result = classifier.classify_scope("UTILITY")
        assert isinstance(result, ScopeClassification)

    def test_returns_scope_classification_for_concur(self, classifier):
        result = classifier.classify_scope("CONCUR")
        assert isinstance(result, ScopeClassification)
