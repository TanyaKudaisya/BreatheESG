"""
Configuration API views for the ingestion app.

Provides read-only endpoints for the currently loaded emission factors
and unit conversion rates.

Requirements: 21.5
"""

from __future__ import annotations

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ingestion.config_loader import ConfigurationLoader

logger = logging.getLogger(__name__)


class EmissionFactorsView(APIView):
    """
    GET /api/v1/config/emission-factors/

    Returns the currently loaded emission factors mapping
    (fuel_type → kg CO₂e per unit).

    Requirements: 21.5
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            loader = ConfigurationLoader()
            config = loader.load_config()
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Failed to load emission factors config: %s", exc)
            return Response(
                {"detail": f"Configuration unavailable: {exc}"},
                status=503,
            )

        return Response({"emission_factors": config.emission_factors})


class UnitConversionsView(APIView):
    """
    GET /api/v1/config/unit-conversions/

    Returns the currently loaded unit conversion rates mapping
    (source_unit → {target_unit, factor}).

    Requirements: 21.5
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            loader = ConfigurationLoader()
            config = loader.load_config()
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Failed to load unit conversions config: %s", exc)
            return Response(
                {"detail": f"Configuration unavailable: {exc}"},
                status=503,
            )

        return Response({"unit_conversions": config.unit_conversions})
