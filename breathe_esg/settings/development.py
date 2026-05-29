"""
Development settings for Breathe ESG Data Ingestion System.

Extends base settings with development-specific overrides:
- DEBUG = True
- Browsable API renderer enabled
- Relaxed CORS for local frontend dev server
- Django Debug Toolbar (optional)
"""

from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------

DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# ---------------------------------------------------------------------------
# Django REST Framework — enable browsable API in development
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    # Relax throttling in development
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/min",
    },
}

# ---------------------------------------------------------------------------
# CORS — allow all origins in development
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# Email backend — print to console in development
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Development-only: show SQL queries in logs
# ---------------------------------------------------------------------------

LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "DEBUG",
    "propagate": False,
}
