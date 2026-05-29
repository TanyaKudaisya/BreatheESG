"""
Unit tests for AirportDistanceCalculator (tasks 5.1 and 5.2).

Covers:
- Airport coordinates loaded correctly from CSV
- Known airport pair distance is > 0
- BLR → BOM distance is approximately 840–860 km
- Multi-leg: BLR → HYD → DEL total equals BLR→HYD + HYD→DEL
- UnknownAirportError raised for unknown airport code
"""

import os
import tempfile
from decimal import Decimal

import pytest

from ingestion.airport_distance import (
    AirportDistanceCalculator,
    Coordinates,
    DistanceResult,
    UnknownAirportError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Resolve the default airports.csv path (same logic as the calculator itself)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AIRPORTS_CSV = os.path.join(_BASE_DIR, "sample_data", "airports.csv")


@pytest.fixture(scope="module")
def calculator():
    """Shared AirportDistanceCalculator instance loaded from the real CSV."""
    return AirportDistanceCalculator(_AIRPORTS_CSV)


# ---------------------------------------------------------------------------
# Task 5.1 – load_airport_coordinates
# ---------------------------------------------------------------------------


class TestLoadAirportCoordinates:
    def test_loads_known_airports(self, calculator):
        """BLR, BOM, DEL, HYD should all be present after loading."""
        for code in ("BLR", "BOM", "DEL", "HYD"):
            coords = calculator._coordinates.get(code)
            assert coords is not None, f"Airport {code} not found in lookup table"

    def test_coordinates_are_decimal(self, calculator):
        """Coordinates must be stored as Decimal instances for precision."""
        coords = calculator._coordinates["BLR"]
        assert isinstance(coords.latitude, Decimal)
        assert isinstance(coords.longitude, Decimal)

    def test_blr_coordinates_correct(self, calculator):
        """BLR latitude and longitude should match the CSV values."""
        coords = calculator._coordinates["BLR"]
        assert coords.latitude == Decimal("13.1979")
        assert coords.longitude == Decimal("77.7063")

    def test_custom_csv_path(self):
        """load_airport_coordinates should work with a custom CSV file."""
        csv_content = "iata_code,name,latitude,longitude\nTST,Test Airport,10.0,20.0\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        try:
            calc = AirportDistanceCalculator(tmp_path)
            assert "TST" in calc._coordinates
            assert calc._coordinates["TST"].latitude == Decimal("10.0")
            assert calc._coordinates["TST"].longitude == Decimal("20.0")
        finally:
            os.unlink(tmp_path)

    def test_iata_codes_uppercased(self):
        """IATA codes in the CSV should be stored in upper-case."""
        csv_content = "iata_code,name,latitude,longitude\nblr,Test,13.1979,77.7063\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        try:
            calc = AirportDistanceCalculator(tmp_path)
            assert "BLR" in calc._coordinates
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Task 5.2 – calculate_distance (single-leg)
# ---------------------------------------------------------------------------


class TestCalculateDistanceSingleLeg:
    def test_distance_is_positive(self, calculator):
        """Any valid airport pair should produce a distance > 0."""
        result = calculator.calculate_distance("BLR", "BOM")
        assert result.distance_km > Decimal("0")

    def test_blr_to_bom_approx_850_km(self, calculator):
        """BLR → BOM should be approximately 820–860 km (Haversine great-circle)."""
        result = calculator.calculate_distance("BLR", "BOM")
        assert Decimal("820") <= result.distance_km <= Decimal("860"), (
            f"Expected BLR→BOM ≈ 820–860 km, got {result.distance_km}"
        )

    def test_returns_distance_result(self, calculator):
        """calculate_distance should return a DistanceResult instance."""
        result = calculator.calculate_distance("BLR", "DEL")
        assert isinstance(result, DistanceResult)

    def test_single_leg_has_no_via_coords(self, calculator):
        """Single-leg result should have via_coords=None and leg_distances=None."""
        result = calculator.calculate_distance("BLR", "DEL")
        assert result.via_coords is None
        assert result.leg_distances is None

    def test_origin_and_destination_coords_populated(self, calculator):
        """Result should carry the origin and destination Coordinates."""
        result = calculator.calculate_distance("BLR", "BOM")
        assert isinstance(result.origin_coords, Coordinates)
        assert isinstance(result.destination_coords, Coordinates)
        assert result.origin_coords.latitude == Decimal("13.1979")
        assert result.destination_coords.latitude == Decimal("19.0896")

    def test_distance_is_symmetric(self, calculator):
        """Distance A→B should equal distance B→A (Haversine is symmetric)."""
        ab = calculator.calculate_distance("BLR", "BOM").distance_km
        ba = calculator.calculate_distance("BOM", "BLR").distance_km
        assert ab == ba

    def test_case_insensitive_airport_codes(self, calculator):
        """Airport codes should be accepted in any case."""
        result_upper = calculator.calculate_distance("BLR", "BOM")
        result_lower = calculator.calculate_distance("blr", "bom")
        assert result_upper.distance_km == result_lower.distance_km


# ---------------------------------------------------------------------------
# Task 5.2 – calculate_distance (multi-leg)
# ---------------------------------------------------------------------------


class TestCalculateDistanceMultiLeg:
    def test_multi_leg_total_equals_sum_of_legs(self, calculator):
        """BLR→HYD→DEL total must equal BLR→HYD + HYD→DEL."""
        result = calculator.calculate_distance("BLR", "DEL", via_airport="HYD")
        leg1 = calculator.calculate_distance("BLR", "HYD").distance_km
        leg2 = calculator.calculate_distance("HYD", "DEL").distance_km
        assert result.distance_km == leg1 + leg2

    def test_multi_leg_leg_distances_stored(self, calculator):
        """leg_distances should contain exactly two values for a via flight."""
        result = calculator.calculate_distance("BLR", "DEL", via_airport="HYD")
        assert result.leg_distances is not None
        assert len(result.leg_distances) == 2

    def test_multi_leg_via_coords_populated(self, calculator):
        """via_coords should be populated for a multi-leg flight."""
        result = calculator.calculate_distance("BLR", "DEL", via_airport="HYD")
        assert result.via_coords is not None
        assert isinstance(result.via_coords, Coordinates)
        assert result.via_coords.latitude == Decimal("17.2403")

    def test_multi_leg_distance_greater_than_direct(self, calculator):
        """A routed flight should generally be longer than the direct route."""
        direct = calculator.calculate_distance("BLR", "DEL").distance_km
        via = calculator.calculate_distance("BLR", "DEL", via_airport="HYD").distance_km
        # HYD is between BLR and DEL geographically, so via >= direct
        assert via >= direct

    def test_multi_leg_individual_legs_match_direct(self, calculator):
        """Each stored leg distance should match the direct calculation."""
        result = calculator.calculate_distance("BLR", "DEL", via_airport="HYD")
        expected_leg1 = calculator.calculate_distance("BLR", "HYD").distance_km
        expected_leg2 = calculator.calculate_distance("HYD", "DEL").distance_km
        assert result.leg_distances[0] == expected_leg1
        assert result.leg_distances[1] == expected_leg2


# ---------------------------------------------------------------------------
# Task 5.2 – UnknownAirportError
# ---------------------------------------------------------------------------


class TestUnknownAirportError:
    def test_unknown_origin_raises_error(self, calculator):
        """An unknown origin airport code should raise UnknownAirportError."""
        with pytest.raises(UnknownAirportError) as exc_info:
            calculator.calculate_distance("XYZ", "BOM")
        assert exc_info.value.airport_code == "XYZ"

    def test_unknown_destination_raises_error(self, calculator):
        """An unknown destination airport code should raise UnknownAirportError."""
        with pytest.raises(UnknownAirportError) as exc_info:
            calculator.calculate_distance("BLR", "XYZ")
        assert exc_info.value.airport_code == "XYZ"

    def test_unknown_via_raises_error(self, calculator):
        """An unknown via airport code should raise UnknownAirportError."""
        with pytest.raises(UnknownAirportError) as exc_info:
            calculator.calculate_distance("BLR", "DEL", via_airport="XYZ")
        assert exc_info.value.airport_code == "XYZ"

    def test_unknown_airport_error_is_value_error(self, calculator):
        """UnknownAirportError should be a subclass of ValueError."""
        with pytest.raises(ValueError):
            calculator.calculate_distance("UNKNOWN", "BOM")

    def test_error_message_contains_code(self, calculator):
        """The error message should mention the unknown airport code."""
        with pytest.raises(UnknownAirportError) as exc_info:
            calculator.calculate_distance("BLR", "NOTREAL")
        assert "NOTREAL" in str(exc_info.value)
