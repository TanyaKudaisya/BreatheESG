"""
URL routes for the validation app.

Registers DataQualityFlagViewSet at /api/v1/quality-flags/.

Requirements: 9.1-9.5
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from validation.views import DataQualityFlagViewSet

router = DefaultRouter()
router.register(r"quality-flags", DataQualityFlagViewSet, basename="quality-flag")

urlpatterns = [
    path("", include(router.urls)),
]
