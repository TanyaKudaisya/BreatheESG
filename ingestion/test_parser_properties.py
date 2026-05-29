"""
Property-based tests for parsers and airport distance calculator.

Property 12: Airport distance calculation
Property 14: Column parsing completeness (SAP and Utility)
Property 15: Nested JSON flattening

Requirements: 4.5, 4.9, 17.2, 17.5, 2.1, 3.1, 3.2, 4.1
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ingestion.airport_distance import AirportDistanceCalculator
from ingestion.sap_parser import SAPParser
from ingestion.utility_parser import UtilityParser
from ingestion.travel_parser import TravelParser

calc = AirportDistanceCalculator()
sap_parser = SAPParser()
utility_parser = UtilityParser()
travel_parser = TravelParser()

KNOWN_AIRPORTS = ["BLR", "BOM", "DEL", "SIN", "LHR", "HYD", "COK", "MAA", "NAG", "RPR"]


# ---------------------------------------------------------------------------
# Property 12: Airport distance calculation
# ---------------------------------------------------------------------------

@given(
    st.sampled_from(KNOWN_AIRPORTS),
    st.sampled_from(KNOWN_AIRPORTS),
)
@settings(max_examples=50)
def test_airport_distance_positive(origin: str, destination: str):
    """Distance between any two airports is >= 0."""
    result = calc.calculate_distance(origin, destination)
    assert result.distance_km >= 0


@given(st.sampled_from(KNOWN_AIRPORTS))
@settings(max_examples=20)
def test_multi_leg_equals_sum_of_legs(via: str):
    """Multi-leg distance equals sum of individual legs."""
    origin, destination = "BLR", "DEL"
    if via in (origin, destination):
        return  # skip degenerate case
    multi = calc.calculate_distance(origin, destination, via_airport=via)
    leg1 = calc.calculate_distance(origin, via)
    leg2 = calc.calculate_distance(via, destination)
    assert multi.distance_km == leg1.distance_km + leg2.distance_km


# ---------------------------------------------------------------------------
# Property 14: SAP column parsing completeness
# ---------------------------------------------------------------------------

SAP_HEADER = "EBELN\tEBELP\tBEDAT\tWERKS\tMENGE\tMEINS\tNETPR\tTXZ01\tMATNR\tWAERS"
SAP_ROW = "4500012301\t00010\t20240103\tWRK1\t5000.000\tL\t89.50\tDiesel HSD\tMAT-001\tINR"
SAP_BLANK_MENGE = "4500012302\t00010\t20240103\tWRK1\t\tL\t89.50\tDiesel HSD\tMAT-001\tINR"


def test_sap_all_required_columns_extracted():
    """All required SAP columns are extracted from a valid file."""
    content = f"{SAP_HEADER}\n{SAP_ROW}".encode()
    records, errors = sap_parser.parse_file(content, "test.txt")
    assert len(records) == 1
    assert errors == []
    r = records[0]
    assert r.ebeln == "4500012301"
    assert r.ebelp == "00010"
    assert r.bedat == "20240103"
    assert r.werks == "WRK1"
    assert r.meins == "L"
    assert r.netpr == "89.50"
    assert r.txz01 == "Diesel HSD"
    assert r.matnr == "MAT-001"
    assert r.waers == "INR"


def test_sap_blank_menge_allowed():
    """Blank MENGE is allowed at parse time (not a parse error)."""
    content = f"{SAP_HEADER}\n{SAP_BLANK_MENGE}".encode()
    records, errors = sap_parser.parse_file(content, "test.txt")
    assert len(records) == 1
    assert records[0].menge == ""


@given(st.integers(min_value=1, max_value=10))
@settings(max_examples=20)
def test_sap_parses_n_rows(n: int):
    """Parser returns exactly N records for N valid data rows."""
    rows = "\n".join([SAP_ROW] * n)
    content = f"{SAP_HEADER}\n{rows}".encode()
    records, errors = sap_parser.parse_file(content, "test.txt")
    assert len(records) == n


# ---------------------------------------------------------------------------
# Property 14: Utility column parsing completeness
# ---------------------------------------------------------------------------

UTILITY_HEADER = (
    "account_number,meter_id,service_address,billing_period_start,"
    "billing_period_end,bill_date,due_date,reading_type,prev_reading_kwh,"
    "curr_reading_kwh,consumption_kwh,demand_kw,supply_charge_inr,"
    "distribution_charge_inr,fuel_adjustment_inr,tod_peak_kwh,tod_offpeak_kwh,"
    "power_factor_penalty_inr,electricity_duty_inr,total_amount_inr,"
    "tariff_code,rate_per_kwh,currency"
)
UTILITY_ROW = (
    "MSEDCL-001,MTR-001,Plot 42 Pune,2024-01-04,2024-02-03,"
    "2024-02-05,2024-02-20,ACTUAL,1000,2000,1000,100,"
    "1200,8500,400,600,400,0,900,11000,HT-1A,8.51,INR"
)


def test_utility_all_required_columns_extracted():
    """All required utility columns are extracted."""
    content = f"{UTILITY_HEADER}\n{UTILITY_ROW}".encode()
    records, errors = utility_parser.parse_file(content, "test.csv")
    assert len(records) == 1
    assert errors == []
    r = records[0]
    assert r.account_number == "MSEDCL-001"
    assert r.meter_id == "MTR-001"
    assert r.consumption_kwh == "1000"
    assert r.reading_type == "ACTUAL"
    assert r.tariff_code == "HT-1A"


def test_utility_ignored_columns_not_on_record():
    """power_factor_penalty_inr and fuel_adjustment_inr are not on the record."""
    content = f"{UTILITY_HEADER}\n{UTILITY_ROW}".encode()
    records, _ = utility_parser.parse_file(content, "test.csv")
    r = records[0]
    assert not hasattr(r, "power_factor_penalty_inr")
    assert not hasattr(r, "fuel_adjustment_inr")


# ---------------------------------------------------------------------------
# Property 15: Nested JSON flattening
# ---------------------------------------------------------------------------

def _make_concur_payload(n_reports: int, entries_per_report: int) -> dict:
    reports = []
    for i in range(n_reports):
        entries = []
        for j in range(entries_per_report):
            entries.append({
                "entry_id": f"ENT-{i}-{j}",
                "expense_type": "AIRFARE",
                "transaction_date": "2024-01-08",
                "receipt_attached": True,
                "origin_airport": "BLR",
                "destination_airport": "BOM",
                "cabin_class": "ECONOMY",
                "distance_km": None,
            })
        reports.append({
            "report_id": f"RPT-{i}",
            "employee_id": "EMP-001",
            "employee_name": "Test User",
            "department": "Engineering",
            "approval_status": "APPROVED",
            "entries": entries,
        })
    return {"expense_reports": reports}


@given(st.integers(min_value=1, max_value=4), st.integers(min_value=1, max_value=5))
@settings(max_examples=30)
def test_concur_flattening_count(n_reports: int, entries_per_report: int):
    """Total records equals sum of all entries across all reports."""
    payload = _make_concur_payload(n_reports, entries_per_report)
    records, errors = travel_parser.parse_json(payload)
    assert len(records) == n_reports * entries_per_report
    assert errors == []
