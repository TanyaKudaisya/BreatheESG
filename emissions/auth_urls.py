"""
URL patterns for session-based authentication endpoints.

Mounted at /api/v1/auth/ in breathe_esg/urls.py.

Requirements: 1.2
"""

from django.urls import path

from emissions.auth_views import LoginView, LogoutView, MeView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
]
