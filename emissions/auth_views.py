"""
Session-based authentication views for the Breathe ESG Data Ingestion System.

Provides login, logout, and current-user endpoints.

Requirements: 1.2
"""

from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


def _user_payload(user) -> dict:
    """Return a consistent user info dict."""
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
    }


class LoginView(APIView):
    """
    POST /api/v1/auth/login/

    Authenticate with email + password, create a Django session, and return
    the session key alongside basic user info.

    Request body:
        {"email": "...", "password": "..."}

    Response (200):
        {"token": "<session_key>", "user": {"id": ..., "email": ..., "role": ..., "tenant_id": ...}}

    Requirements: 1.2
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # No auth required for login

    def post(self, request: Request) -> Response:
        email = request.data.get("email", "").strip()
        password = request.data.get("password", "")

        if not email or not password:
            return Response(
                {"detail": "Both 'email' and 'password' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Django's authenticate() accepts username; our User model uses email
        # as the primary login identifier but stores it in both email and username.
        # Try authenticating by username (which equals email for seeded users),
        # then fall back to a direct email lookup.
        user = authenticate(request, username=email, password=password)

        if user is None:
            # Try looking up by email field directly
            from emissions.models import User  # noqa: PLC0415

            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "This account is inactive."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Create the session
        login(request, user)

        # Store tenant_id in session for quick access
        if user.tenant_id:
            request.session["tenant_id"] = str(user.tenant_id)

        return Response(
            {
                "token": request.session.session_key,
                "user": _user_payload(user),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Destroy the current session.

    Requirements: 1.2
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request)
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    GET /api/v1/auth/me/

    Return the currently authenticated user's info.
    Returns 401 if the request is not authenticated.

    Requirements: 1.2
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(_user_payload(request.user), status=status.HTTP_200_OK)
