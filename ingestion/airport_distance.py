"""
Airport Distance Calculator

Computes great-circle distances between airport codes using the Haversine formula.
Supports single-leg and multi-leg (via_airport) flights.
"""

import csv
import math
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional


# Earth's mean radius in kilometres (per design spec)
EARTH_RADIUS_KM = Decimal("6371")


@dataclass
class Coordinates:
    """Geographic coordinates for an airport."""
    latitude: Decimal
    longitude: Decimal


@dataclass
class DistanceResult:
    """Result of a distance calculation between airports."""
    distance_km: Decimal
    origin_coords: Coordinates
    destination_coords: Coordinates
    via_coords: Optional[Coordinates] = None
    leg_distances: Optional[List[Decimal]] = None


class UnknownAirportError(ValueError):
    """Raised when an airport code is not found in the lookup table."""

    def __init__(self, airport_code: str):
        self.airport_code = airport_code
        super().__init__(
            f"Airport code '{airport_code}' not found in the airport lookup table."
        )


class AirportDistanceCalculator:
    """
    Calculates great-circle distances between airports using the Haversine formula.

    Loads airport coordinates from a CSV file (default: sample_data/airports.csv)
    and provides distance calculation for single-leg and multi-leg flights.
    """

    def __init__(self, airports_csv_path: str = None):
        if airports_csv_path is None:
            # Default: resolve relative to this file's location
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            airports_csv_path = os.path.join(base_dir, "sample_data", "airports.csv")

        self._coordinates: Dict[str, Coordinates] = self.load_airport_coordinates(
            airports_csv_path
        )

    # ------------------------------------------------------------------
    # Task 5.1 – Airport coordinate lookup service
    # ------------------------------------------------------------------

    def load_airport_coordinates(self, csv_path: str) -> Dict[str, Coordinates]:
        """
        Load airport code → Coordinates mapping from a CSV file.

        Expected CSV columns: iata_code, name, latitude, longitude

        Args:
            csv_path: Absolute or relative path to the airports CSV file.

        Returns:
            Dictionary mapping IATA code (upper-case) to Coordinates.

        Raises:
            FileNotFoundError: If the CSV file does not exist.
        """
        coordinates: Dict[str, Coordinates] = {}

        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                iata_code = row["iata_code"].strip().upper()
                latitude = Decimal(row["latitude"].strip())
                longitude = Decimal(row["longitude"].strip())
                coordinates[iata_code] = Coordinates(
                    latitude=latitude, longitude=longitude
                )

        return coordinates

    # ------------------------------------------------------------------
    # Task 5.2 – Haversine distance calculation
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine(coord1: Coordinates, coord2: Coordinates) -> Decimal:
        """
        Compute the great-circle distance between two points using the
        Haversine formula.

        Formula:
            a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
            c = 2 × atan2(√a, √(1−a))
            distance = 6371 × c

        Args:
            coord1: Origin coordinates.
            coord2: Destination coordinates.

        Returns:
            Distance in kilometres as a Decimal rounded to 2 decimal places.
        """
        # Convert Decimal degrees to float radians for math functions
        lat1 = math.radians(float(coord1.latitude))
        lat2 = math.radians(float(coord2.latitude))
        delta_lat = math.radians(float(coord2.latitude - coord1.latitude))
        delta_lon = math.radians(float(coord2.longitude - coord1.longitude))

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance_km = float(EARTH_RADIUS_KM) * c

        return Decimal(str(round(distance_km, 2)))

    def _get_coordinates(self, airport_code: str) -> Coordinates:
        """
        Retrieve coordinates for an airport code.

        Args:
            airport_code: IATA airport code (case-insensitive).

        Returns:
            Coordinates for the airport.

        Raises:
            UnknownAirportError: If the code is not in the lookup table.
        """
        code = airport_code.strip().upper()
        if code not in self._coordinates:
            raise UnknownAirportError(code)
        return self._coordinates[code]

    def calculate_distance(
        self,
        origin_airport: str,
        destination_airport: str,
        via_airport: Optional[str] = None,
    ) -> DistanceResult:
        """
        Calculate great-circle distance between airports.

        For single-leg flights (no via_airport):
            Returns origin → destination distance.

        For multi-leg flights (via_airport provided):
            Calculates origin → via and via → destination separately.
            Returns the sum of both legs with individual leg distances stored.

        Args:
            origin_airport: IATA code of the departure airport.
            destination_airport: IATA code of the arrival airport.
            via_airport: Optional IATA code of a connecting airport.

        Returns:
            DistanceResult with distance_km, coordinates, and leg details.

        Raises:
            UnknownAirportError: If any airport code is not in the lookup table.
        """
        origin_coords = self._get_coordinates(origin_airport)
        destination_coords = self._get_coordinates(destination_airport)

        if via_airport is None:
            # Single-leg flight
            distance = self._haversine(origin_coords, destination_coords)
            return DistanceResult(
                distance_km=distance,
                origin_coords=origin_coords,
                destination_coords=destination_coords,
            )
        else:
            # Multi-leg flight: origin → via → destination
            via_coords = self._get_coordinates(via_airport)

            leg1 = self._haversine(origin_coords, via_coords)
            leg2 = self._haversine(via_coords, destination_coords)
            total = leg1 + leg2

            return DistanceResult(
                distance_km=total,
                origin_coords=origin_coords,
                destination_coords=destination_coords,
                via_coords=via_coords,
                leg_distances=[leg1, leg2],
            )
