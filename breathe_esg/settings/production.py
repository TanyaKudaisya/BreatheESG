"""
Production settings for Breathe ESG Data Ingestion System.

Extends base settings with production-specific hardening:
- DEBUG = False
- Strict ALLOWED_HOSTS
- HTTPS security headers
- Secure cookies
- WhiteNoise for static files
"""

from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

DEBUG = False

# HTTPS enforcement
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Secure cookies
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Prevent clickjacking
X_FRAME_OPTIONS = "DENY"

# Content type sniffing protection
SECURE_CONTENT_TYPE_NOSNIFF = True

# XSS filter
SECURE_BROWSER_XSS_FILTER = True

# Proxy header (required when behind a load balancer / reverse proxy on Render/Railway)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Static files — WhiteNoise serves compressed, cached static assets
# ---------------------------------------------------------------------------

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# Email backend — configure for production SMTP
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# ---------------------------------------------------------------------------
# Logging — reduce verbosity in production
# ---------------------------------------------------------------------------

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
