"""
ASGI config for Breathe ESG Data Ingestion System.

Exposes the ASGI callable as a module-level variable named ``application``.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "breathe_esg.settings.production")

application = get_asgi_application()
