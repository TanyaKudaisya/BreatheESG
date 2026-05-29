"""
URL routes for the emissions app.

Registers EmissionRecordViewSet at /api/v1/emissions/ with all standard
CRUD routes plus custom workflow actions.

Requirements: 8.1, 8.2, 10.1-10.6, 11.1, 11.2, 13.1-13.5
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from emissions.views import EmissionRecordViewSet

router = DefaultRouter()
router.register(r"emissions", EmissionRecordViewSet, basename="emission")

urlpatterns = [
    path("", include(router.urls)),
]
