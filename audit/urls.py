"""
URL routes for the audit app.

Registers AuditTrailView at /api/v1/audit-trail/{record_id}/.

Requirements: 12.4
"""

from django.urls import path

from audit.views import AuditTrailView

urlpatterns = [
    path(
        "audit-trail/<uuid:record_id>/",
        AuditTrailView.as_view(),
        name="audit-trail",
    ),
]
