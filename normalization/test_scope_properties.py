"""
Property-based tests for the scope classifier.

Property 4: SAP Scope 1 classification
Property 5: Utility Scope 2 classification
Property 6: Travel Scope 3 classification

Requirements: 2.6, 2.7, 3.5, 4.2, 4.3, 4.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from normalization.scope_classifier import ScopeClassifier

classifier = ScopeClassifier()

SCOPE_1_KEYWORDS = ["diesel", "petrol", "PNG", "furnace oil", "LPG", "coal"]
TRAVEL_EXPENSE_TYPES = [
    "AIRFARE", "HOTEL",
    "GROUND_TRANSPORT_TAXI", "GROUND_TRANSPORT_RENTAL_CAR",
    "GROUND_TRANSPORT_METRO", "GROUND_TRANSPORT_RAIL",
]


# ---------------------------------------------------------------------------
# Property 4: SAP Scope 1
# ---------------------------------------------------------------------------

@given(st.sampled_from(SCOPE_1_KEYWORDS))
@settings(max_examples=50)
def test_sap_scope_1_for_fuel_keywords(keyword: str):
    """SAP records with fuel keywords are classified as Scope 1."""
    result = classifier.classify_scope("SAP", keyword)
    assert result.scope == 1
    assert not result.is_excluded


def test_sap_lubricating_oil_excluded():
    """Lubricating oil is excluded from emission calculations."""
    result = classifier.classify_scope("SAP", "Lubricating Oil SAE 40")
    assert result.is_excluded
    assert result.scope is None


@given(st.sampled_from(SCOPE_1_KEYWORDS))
@settings(max_examples=50)
def test_sap_scope_1_case_insensitive(keyword: str):
    """Scope 1 keyword matching is case-insensitive."""
    result = classifier.classify_scope("SAP", keyword.upper())
    assert result.scope == 1


# ---------------------------------------------------------------------------
# Property 5: Utility Scope 2
# ---------------------------------------------------------------------------

@given(st.text(min_size=0, max_size=50))
@settings(max_examples=100)
def test_utility_always_scope_2(description: str):
    """All utility records are Scope 2 regardless of description."""
    result = classifier.classify_scope("UTILITY", description)
    assert result.scope == 2
    assert not result.is_excluded


# ---------------------------------------------------------------------------
# Property 6: Travel Scope 3 Category 6
# ---------------------------------------------------------------------------

@given(st.sampled_from(TRAVEL_EXPENSE_TYPES))
@settings(max_examples=50)
def test_travel_always_scope_3_cat_6(expense_type: str):
    """All Concur travel records are Scope 3 Category 6."""
    result = classifier.classify_scope("CONCUR", expense_type)
    assert result.scope == 3
    assert result.category == 6
    assert not result.is_excluded
