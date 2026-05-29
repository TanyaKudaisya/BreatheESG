"""
URL routes for the ingestion app.

Registers ingestion endpoints and configuration endpoints.

Requirements: 15.1-15.5, 16.1-16.5, 21.5
"""

from django.urls import path

from ingestion.views import SAPIngestionView, UtilityIngestionView, TravelIngestionView
from ingestion.config_views import EmissionFactorsView, UnitConversionsView

urlpatterns = [
    # Ingestion endpoints (Task 13.6)
    path("ingest/sap/", SAPIngestionView.as_view(), name="ingest-sap"),
    path("ingest/utility/", UtilityIngestionView.as_view(), name="ingest-utility"),
    path("ingest/travel/", TravelIngestionView.as_view(), name="ingest-travel"),

    # Configuration endpoints (Task 13.7)
    path("config/emission-factors/", EmissionFactorsView.as_view(), name="config-emission-factors"),
    path("config/unit-conversions/", UnitConversionsView.as_view(), name="config-unit-conversions"),
]
