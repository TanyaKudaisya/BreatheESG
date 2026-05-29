"""
API views for the ingestion app.

Provides three upload/ingest endpoints:
  - POST /api/v1/ingest/sap/      — upload SAP tab-separated file
  - POST /api/v1/ingest/utility/  — upload utility CSV file
  - POST /api/v1/ingest/travel/   — post Concur JSON payload

Requirements: 15.1-15.5, 16.1-16.5
"""

from __future__ import annotations

import dataclasses
import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ingestion.ingestion_engine import IngestionEngine, IngestionResult

logger = logging.getLogger(__name__)


def _result_to_dict(result: IngestionResult) -> dict:
    """
    Convert an IngestionResult dataclass to a JSON-serializable dict.
    """
    return {
        "records_parsed": result.records_parsed,
        "records_with_errors": result.records_with_errors,
        "records_ingested": result.records_ingested,
        "errors": [
            {
                "row_number": e.row_number,
                "message": e.message,
            }
            for e in result.errors
        ],
    }


class SAPIngestionView(APIView):
    """
    POST /api/v1/ingest/sap/

    Accepts a SAP tab-separated file in multipart form data under the
    key ``file``.  Calls IngestionEngine.ingest_sap_file() and returns
    the IngestionResult as JSON.

    Requirements: 15.1-15.5
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response(
                {"detail": "No file provided. Send the file under the 'file' key."},
                status=400,
            )

        user = request.user
        if not hasattr(user, "tenant") or user.tenant is None:
            return Response(
                {"detail": "User is not associated with a tenant."},
                status=403,
            )

        tenant_id = str(user.tenant.id)
        filename = uploaded_file.name or "sap_upload.txt"

        try:
            engine = IngestionEngine()
            result = engine.ingest_sap_file(
                file_content=uploaded_file.read(),
                filename=filename,
                tenant_id=tenant_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("SAP ingestion failed: %s", exc)
            return Response(
                {"detail": f"Ingestion failed: {exc}"},
                status=500,
            )

        return Response(_result_to_dict(result), status=200)


class UtilityIngestionView(APIView):
    """
    POST /api/v1/ingest/utility/

    Accepts a utility CSV file in multipart form data under the key
    ``file``.  Calls IngestionEngine.ingest_utility_file() and returns
    the IngestionResult as JSON.

    Requirements: 15.1-15.5
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response(
                {"detail": "No file provided. Send the file under the 'file' key."},
                status=400,
            )

        user = request.user
        if not hasattr(user, "tenant") or user.tenant is None:
            return Response(
                {"detail": "User is not associated with a tenant."},
                status=403,
            )

        tenant_id = str(user.tenant.id)
        filename = uploaded_file.name or "utility_upload.csv"

        try:
            engine = IngestionEngine()
            result = engine.ingest_utility_file(
                file_content=uploaded_file.read(),
                filename=filename,
                tenant_id=tenant_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Utility ingestion failed: %s", exc)
            return Response(
                {"detail": f"Ingestion failed: {exc}"},
                status=500,
            )

        return Response(_result_to_dict(result), status=200)


class TravelIngestionView(APIView):
    """
    POST /api/v1/ingest/travel/

    Accepts a Concur JSON payload in the request body.
    Calls IngestionEngine.ingest_travel_json() and returns the
    IngestionResult as JSON.

    Requirements: 16.1-16.5
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = request.user
        if not hasattr(user, "tenant") or user.tenant is None:
            return Response(
                {"detail": "User is not associated with a tenant."},
                status=403,
            )

        tenant_id = str(user.tenant.id)
        payload = request.data

        if not isinstance(payload, dict):
            return Response(
                {"detail": "Request body must be a JSON object."},
                status=400,
            )

        try:
            engine = IngestionEngine()
            result = engine.ingest_travel_json(
                payload=payload,
                tenant_id=tenant_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Travel ingestion failed: %s", exc)
            return Response(
                {"detail": f"Ingestion failed: {exc}"},
                status=500,
            )

        return Response(_result_to_dict(result), status=200)
