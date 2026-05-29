"""
URL configuration for Breathe ESG Data Ingestion System.

API routes are versioned under /api/v1/ as specified in the design document.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.generic import TemplateView

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # Authentication endpoints
    path("api/v1/auth/", include("emissions.auth_urls")),

    # API v1 — each app registers its own router in its urls.py
    path("api/v1/", include("emissions.urls")),
    path("api/v1/", include("ingestion.urls")),
    path("api/v1/", include("audit.urls")),
    path("api/v1/", include("validation.urls")),
]

# Serve React frontend in production (catch-all for SPA routing)
if not settings.DEBUG:
    from django.contrib.staticfiles.views import serve
    from django.views.static import serve as static_serve
    import os
    FRONTEND_BUILD = os.path.join(settings.BASE_DIR, "frontend", "dist")
    if os.path.exists(FRONTEND_BUILD):
        urlpatterns += [
            path("", TemplateView.as_view(template_name="index.html")),
        ]
        from django.conf.urls.static import static
        urlpatterns += static("/assets/", document_root=os.path.join(FRONTEND_BUILD, "assets"))
