"""
WSGI config for Breathe ESG Data Ingestion System.

Exposes the WSGI callable as a module-level variable named ``application``.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "breathe_esg.settings.production")

application = get_wsgi_application()
